from __future__ import annotations

def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    if not isinstance(symbols, dict):
        return
    target = globals()
    module_name = str(target.get('__name__') or '')
    for key, value in symbols.items():
        if str(key).startswith('__'):
            continue
        current = target.get(key)
        if callable(current) and getattr(current, '__module__', '') == module_name:
            continue
        target[key] = value

def discover_agents(
    agents_root: Path,
    *,
    cache_root: Path | None = None,
    analyze_policy: bool = True,
    target_agent_name: str = "",
) -> list[dict[str, Any]]:
    if not agents_root.exists():
        return []
    workspace_root = agents_root.resolve(strict=False)
    workspace_ok, _workspace_error = validate_workspace_root_semantics(workspace_root)
    if not workspace_ok:
        return []
    target_name = safe_token(str(target_agent_name or ""), "", 80)
    seen: set[str] = set()
    agents: list[dict[str, Any]] = []
    cache_conn: sqlite3.Connection | None = None
    cache_probe_rows: dict[str, dict[str, Any]] = {}
    if not analyze_policy:
        cache_probe_rows = _load_policy_cache_probe_rows(cache_root)
    if analyze_policy and cache_root is not None:
        try:
            cache_conn = connect_db(cache_root)
        except Exception:
            cache_conn = None
    for agents_file in sorted(agents_root.rglob("AGENTS.md"), key=lambda p: str(p).lower()):
        if not agents_file.is_file():
            continue
        try:
            rel_parts = agents_file.relative_to(agents_root).parts[:-1]
        except Exception:
            rel_parts = agents_file.parts[:-1]
        # Hidden-style directories (e.g. .test, .cache, .git) are not exposed as selectable agents.
        if any(part.startswith(".") for part in rel_parts):
            continue
        rel_parts_lower = [str(part).strip().lower() for part in rel_parts]
        if "test-runtime" in rel_parts_lower:
            continue
        agent_name = safe_token(agents_file.parent.name, "", 80)
        if not agent_name or agent_name in seen:
            continue
        if target_name and agent_name != target_name:
            continue
        try:
            stat = agents_file.stat()
            raw = agents_file.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            agents_mtime = float(stat.st_mtime or 0.0)
            loaded_at = datetime.fromtimestamp(agents_mtime).astimezone()
        except Exception:
            continue
        if not analyze_policy:
            cache_hit = False
            cache_status = "pending"
            cache_reason = "not_analyzed"
            cache_cached_at = ""
            cache_trace: list[dict[str, str]] = []
            payload: dict[str, Any] = {}
            cache_row = cache_probe_rows.get(agents_file.as_posix())

            def push_cache_trace(step: str, status: str, detail: str) -> None:
                cache_trace.append(
                    {
                        "step": str(step or ""),
                        "status": str(status or ""),
                        "detail": str(detail or ""),
                    }
                )

            if cache_root is None:
                cache_status = "disabled"
                cache_reason = "cache_disabled"
                push_cache_trace("lookup", "disabled", "未配置缓存根目录")
            elif cache_row is None:
                push_cache_trace("lookup", "miss", "轻量模式未找到缓存记录")
            else:
                push_cache_trace("lookup", "found", "找到缓存记录，开始轻量校验")
                invalid_reasons: list[str] = []
                row_hash = str(cache_row.get("agents_hash") or "").strip()
                if not row_hash or row_hash != digest:
                    invalid_reasons.append("agents_hash_mismatch")
                cached_at_epoch = float(cache_row.get("cached_at") or 0.0)
                if cached_at_epoch <= 0:
                    invalid_reasons.append("cached_at_missing")
                elif cached_at_epoch < agents_mtime:
                    invalid_reasons.append("cached_before_agents_mtime")
                else:
                    cache_cached_at = iso_ts(datetime.fromtimestamp(cached_at_epoch).astimezone())
                row_agents_mtime = float(cache_row.get("agents_mtime") or 0.0)
                if row_agents_mtime <= 0:
                    invalid_reasons.append("agents_mtime_missing")
                payload = _parse_agent_policy_cache_payload(str(cache_row.get("policy_payload_json") or ""))
                if payload:
                    _ensure_analysis_chain_ui_progress(
                        payload,
                        cache_root if cache_root is not None else workspace_root,
                    )
                if not payload:
                    invalid_reasons.append("cache_payload_invalid_json")
                else:
                    payload_prompt_version = str(payload.get("policy_prompt_version") or "").strip()
                    if payload_prompt_version != POLICY_PROMPT_VERSION:
                        invalid_reasons.append("cache_prompt_version_mismatch")
                    payload_extract_source = str(payload.get("policy_extract_source") or "").strip()
                    if payload_extract_source and payload_extract_source != POLICY_EXTRACT_SOURCE:
                        invalid_reasons.append("cache_extract_source_mismatch")
                    parse_status_text = str(payload.get("parse_status") or "").strip().lower()
                    if parse_status_text not in {"ok", "incomplete", "failed"}:
                        invalid_reasons.append("cache_parse_status_missing")
                    try:
                        int(payload.get("clarity_score") or 0)
                    except Exception:
                        invalid_reasons.append("cache_clarity_score_invalid")
                if invalid_reasons:
                    payload = {}
                    cache_status = "stale"
                    cache_reason = ",".join(invalid_reasons)
                    push_cache_trace("validate", "invalid", f"缓存不可用：{cache_reason}")
                else:
                    cache_hit = True
                    cache_status = "hit"
                    cache_reason = "cache_hit"
                    push_cache_trace("validate", "valid", "轻量校验通过，复用缓存摘要")

            constraints_default = {
                "must": [],
                "must_not": [],
                "preconditions": [],
                "issues": [],
                "conflicts": [],
                "missing_evidence_count": 0,
                "total": 0,
            }
            clarity_details_default = {
                "completeness": 0,
                "specificity": 0,
                "consistency": 0,
                "traceability": 0,
            }
            parse_status = str(payload.get("parse_status") or "").strip().lower()
            if parse_status not in {"ok", "incomplete", "failed"}:
                parse_status = ""
            clarity_gate = str(payload.get("clarity_gate") or "").strip().lower()
            if clarity_gate not in {"auto", "confirm", "block"}:
                clarity_gate = ""
            try:
                clarity_score = max(0, min(100, int(payload.get("clarity_score") or 0)))
            except Exception:
                clarity_score = 0
            try:
                score_total = max(0, min(100, int(payload.get("score_total") or payload.get("clarity_score") or 0)))
            except Exception:
                score_total = clarity_score
            constraints = payload.get("constraints") if isinstance(payload.get("constraints"), dict) else constraints_default
            evidence_snippets = (
                payload.get("evidence_snippets")
                if isinstance(payload.get("evidence_snippets"), dict)
                else {"role": "", "goal": "", "duty": ""}
            )
            score_weights = payload.get("score_weights") if isinstance(payload.get("score_weights"), dict) else dict(POLICY_SCORE_WEIGHTS)
            score_dimensions = payload.get("score_dimensions") if isinstance(payload.get("score_dimensions"), dict) else {}
            clarity_details = payload.get("clarity_details") if isinstance(payload.get("clarity_details"), dict) else clarity_details_default
            agents.append(
                {
                    "agent_name": agent_name,
                    "agents_hash": digest,
                    "agents_loaded_at": iso_ts(loaded_at),
                    "agents_version": digest[:12],
                    "agents_md_path": agents_file.as_posix(),
                    "duty_title": str(payload.get("duty_title") or ""),
                    "duty_excerpt": str(payload.get("duty_excerpt") or ""),
                    "duty_text": str(payload.get("duty_text") or ""),
                    "duty_truncated": bool(payload.get("duty_truncated")),
                    "role_profile": str(payload.get("role_profile") or ""),
                    "session_goal": str(payload.get("session_goal") or ""),
                    "duty_constraints": [
                        str(item).strip()
                        for item in (payload.get("duty_constraints") or [])
                        if str(item or "").strip()
                    ],
                    "duty_constraints_text": str(payload.get("duty_constraints_text") or ""),
                    "constraints": constraints,
                    "parse_status": parse_status,
                    "parse_warnings": [
                        str(item).strip()
                        for item in (payload.get("parse_warnings") or [])
                        if str(item or "").strip()
                    ],
                    "evidence_snippets": evidence_snippets,
                    "score_model": str(payload.get("score_model") or POLICY_SCORE_MODEL),
                    "score_total": score_total,
                    "score_weights": score_weights,
                    "score_dimensions": score_dimensions,
                    "clarity_score": clarity_score,
                    "clarity_details": clarity_details,
                    "clarity_gate": clarity_gate,
                    "clarity_gate_reason": str(payload.get("clarity_gate_reason") or ""),
                    "risk_tips": [
                        str(item).strip()
                        for item in (payload.get("risk_tips") or [])
                        if str(item or "").strip()
                    ],
                    "policy_extract_ok": bool(payload.get("policy_extract_ok")),
                    "policy_error": str(payload.get("policy_error") or ""),
                    "policy_extract_source": str(payload.get("policy_extract_source") or POLICY_EXTRACT_SOURCE),
                    "policy_prompt_version": str(payload.get("policy_prompt_version") or POLICY_PROMPT_VERSION),
                    "analysis_chain": payload.get("analysis_chain") if isinstance(payload.get("analysis_chain"), dict) else {},
                    "policy_contract_status": str(payload.get("policy_contract_status") or ""),
                    "policy_contract_missing_fields": [
                        str(item).strip()
                        for item in (payload.get("policy_contract_missing_fields") or [])
                        if str(item or "").strip()
                    ],
                    "policy_contract_issues": [
                        str(item).strip()
                        for item in (payload.get("policy_contract_issues") or [])
                        if str(item or "").strip()
                    ],
                    "policy_gate_state": str(payload.get("policy_gate_state") or ""),
                    "policy_gate_reason": str(payload.get("policy_gate_reason") or ""),
                    "policy_cache_hit": bool(cache_hit),
                    "policy_cache_status": cache_status,
                    "policy_cache_reason": cache_reason,
                    "policy_cache_cached_at": cache_cached_at,
                    "policy_cache_trace": cache_trace,
                    "agents_mtime": agents_mtime,
                }
            )
            seen.add(agent_name)
            continue

        cache_hit = False
        cache_status = "disabled" if cache_conn is None else "miss"
        cache_reason = "cache_disabled" if cache_conn is None else "cache_not_found"
        cache_cached_at = ""
        cache_trace: list[dict[str, str]] = []
        payload: dict[str, Any] = {}
        cache_row: sqlite3.Row | None = None

        def push_cache_trace(step: str, status: str, detail: str) -> None:
            cache_trace.append(
                {
                    "step": str(step or ""),
                    "status": str(status or ""),
                    "detail": str(detail or ""),
                }
            )

        if cache_conn is None:
            push_cache_trace("lookup", "disabled", "缓存未启用，直接实时解析 AGENTS.md")
        else:
            try:
                cache_row = cache_conn.execute(
                    """
                    SELECT agent_path,agents_hash,agents_mtime,parse_status,clarity_score,cached_at,policy_payload_json
                    FROM agent_policy_cache
                    WHERE agent_path=?
                    LIMIT 1
                    """,
                    (agents_file.as_posix(),),
                ).fetchone()
            except Exception:
                cache_row = None
            if cache_row is None:
                push_cache_trace("lookup", "miss", "未找到缓存记录，准备重算")
            if cache_row is not None:
                push_cache_trace("lookup", "found", "找到缓存记录，开始校验")
                invalid_reasons: list[str] = []
                row_hash = str(cache_row["agents_hash"] or "").strip()
                if not row_hash or row_hash != digest:
                    invalid_reasons.append("agents_hash_mismatch")
                try:
                    cached_at_epoch = float(cache_row["cached_at"] or 0.0)
                except Exception:
                    cached_at_epoch = 0.0
                if cached_at_epoch <= 0:
                    invalid_reasons.append("cached_at_missing")
                elif cached_at_epoch < agents_mtime:
                    invalid_reasons.append("cached_before_agents_mtime")
                else:
                    cache_cached_at = iso_ts(datetime.fromtimestamp(cached_at_epoch).astimezone())
                try:
                    row_agents_mtime = float(cache_row["agents_mtime"] or 0.0)
                except Exception:
                    row_agents_mtime = 0.0
                if row_agents_mtime <= 0:
                    invalid_reasons.append("agents_mtime_missing")
                payload = _parse_agent_policy_cache_payload(str(cache_row["policy_payload_json"] or ""))
                if payload:
                    _ensure_analysis_chain_ui_progress(
                        payload,
                        cache_root if cache_root is not None else workspace_root,
                    )
                if not payload:
                    invalid_reasons.append("cache_payload_invalid_json")
                else:
                    missing_keys = [
                        key
                        for key in _policy_cache_required_payload_keys()
                        if key not in payload
                    ]
                    if missing_keys:
                        invalid_reasons.append("cache_payload_incomplete")
                    payload_prompt_version = str(payload.get("policy_prompt_version") or "").strip()
                    if payload_prompt_version != POLICY_PROMPT_VERSION:
                        invalid_reasons.append("cache_prompt_version_mismatch")
                    payload_extract_source = str(payload.get("policy_extract_source") or "").strip()
                    if payload_extract_source and payload_extract_source != POLICY_EXTRACT_SOURCE:
                        invalid_reasons.append("cache_extract_source_mismatch")
                    parse_status_text = str(payload.get("parse_status") or "").strip().lower()
                    if not parse_status_text:
                        invalid_reasons.append("cache_parse_status_missing")
                    try:
                        int(payload.get("clarity_score") or 0)
                    except Exception:
                        invalid_reasons.append("cache_clarity_score_invalid")
                if invalid_reasons:
                    payload = {}
                    cache_status = "recomputed"
                    cache_reason = ",".join(invalid_reasons)
                    push_cache_trace(
                        "validate",
                        "invalid",
                        f"缓存失效：{cache_reason}",
                    )
                else:
                    cache_hit = True
                    cache_status = "hit"
                    cache_reason = "cache_hit"
                    push_cache_trace("validate", "valid", "hash/mtime/字段校验通过")
                    push_cache_trace("reuse", "hit", "复用缓存提取结果")

        if not payload:
            push_cache_trace("recompute", "start", "读取 AGENTS.md 并重新提取角色与职责")
            payload = build_agent_policy_payload_via_codex(
                runtime_root=cache_root if cache_root is not None else workspace_root,
                workspace_root=workspace_root,
                agent_name=agent_name,
                agents_file=agents_file,
                agents_hash=digest,
                agents_version=digest[:12],
            )
            push_cache_trace(
                "recompute",
                "done",
                (
                    "重算完成："
                    f"parse_status={str(payload.get('parse_status') or 'failed')},"
                    f"clarity={int(payload.get('clarity_score') or 0)}"
                ),
            )
            if cache_conn is None:
                push_cache_trace("write", "skipped", "缓存未启用，跳过写入")
            else:
                cached_at_epoch = time.time()
                cache_cached_at = iso_ts(datetime.fromtimestamp(cached_at_epoch).astimezone())
                cache_status = "recomputed"
                if cache_reason == "cache_not_found":
                    cache_reason = "cache_miss"
                try:
                    cache_conn.execute(
                        """
                        INSERT INTO agent_policy_cache (
                            agent_path,agents_hash,agents_mtime,parse_status,clarity_score,cached_at,policy_payload_json
                        ) VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(agent_path) DO UPDATE SET
                            agents_hash=excluded.agents_hash,
                            agents_mtime=excluded.agents_mtime,
                            parse_status=excluded.parse_status,
                            clarity_score=excluded.clarity_score,
                            cached_at=excluded.cached_at,
                            policy_payload_json=excluded.policy_payload_json
                        """,
                        (
                            agents_file.as_posix(),
                            digest,
                            agents_mtime,
                            str(payload.get("parse_status") or "failed"),
                            int(payload.get("clarity_score") or 0),
                            cached_at_epoch,
                            json.dumps(payload, ensure_ascii=False),
                        ),
                    )
                    push_cache_trace("write", "success", "重算结果已写入缓存")
                except Exception:
                    cache_status = "recomputed"
                    cache_reason = "cache_write_failed"
                    push_cache_trace("write", "failed", "缓存写入失败，保留实时重算结果")

        _ensure_analysis_chain_ui_progress(
            payload,
            cache_root if cache_root is not None else workspace_root,
        )

        agents.append(
            {
                "agent_name": agent_name,
                "agents_hash": digest,
                "agents_loaded_at": iso_ts(loaded_at),
                "agents_version": digest[:12],
                "agents_md_path": agents_file.as_posix(),
                "duty_title": str(payload.get("duty_title") or ""),
                "duty_excerpt": str(payload.get("duty_excerpt") or ""),
                "duty_text": str(payload.get("duty_text") or ""),
                "duty_truncated": bool(payload.get("duty_truncated")),
                "role_profile": str(payload.get("role_profile") or ""),
                "session_goal": str(payload.get("session_goal") or ""),
                "duty_constraints": [
                    str(item).strip()
                    for item in (payload.get("duty_constraints") or [])
                    if str(item or "").strip()
                ],
                "duty_constraints_text": str(payload.get("duty_constraints_text") or ""),
                "constraints": payload.get("constraints")
                if isinstance(payload.get("constraints"), dict)
                else {
                    "must": [],
                    "must_not": [],
                    "preconditions": [],
                    "issues": [],
                    "conflicts": [],
                    "missing_evidence_count": 0,
                    "total": 0,
                },
                "parse_status": str(payload.get("parse_status") or "failed"),
                "parse_warnings": [
                    str(item).strip()
                    for item in (payload.get("parse_warnings") or [])
                    if str(item or "").strip()
                ],
                "evidence_snippets": payload.get("evidence_snippets")
                if isinstance(payload.get("evidence_snippets"), dict)
                else {"role": "", "goal": "", "duty": ""},
                "score_model": str(payload.get("score_model") or POLICY_SCORE_MODEL),
                "score_total": max(0, min(100, int(payload.get("score_total") or payload.get("clarity_score") or 0))),
                "score_weights": payload.get("score_weights")
                if isinstance(payload.get("score_weights"), dict)
                else dict(POLICY_SCORE_WEIGHTS),
                "score_dimensions": payload.get("score_dimensions")
                if isinstance(payload.get("score_dimensions"), dict)
                else {},
                "clarity_score": max(0, min(100, int(payload.get("clarity_score") or 0))),
                "clarity_details": payload.get("clarity_details")
                if isinstance(payload.get("clarity_details"), dict)
                else {
                    "completeness": 0,
                    "specificity": 0,
                    "consistency": 0,
                    "traceability": 0,
                },
                "clarity_gate": str(payload.get("clarity_gate") or "block"),
                "clarity_gate_reason": str(payload.get("clarity_gate_reason") or ""),
                "risk_tips": [
                    str(item).strip()
                    for item in (payload.get("risk_tips") or [])
                    if str(item or "").strip()
                ],
                "policy_extract_ok": bool(payload.get("policy_extract_ok")),
                "policy_error": str(payload.get("policy_error") or ""),
                "policy_extract_source": str(payload.get("policy_extract_source") or POLICY_EXTRACT_SOURCE),
                "policy_prompt_version": str(payload.get("policy_prompt_version") or POLICY_PROMPT_VERSION),
                "analysis_chain": payload.get("analysis_chain") if isinstance(payload.get("analysis_chain"), dict) else {},
                "policy_contract_status": str(payload.get("policy_contract_status") or "failed"),
                "policy_contract_missing_fields": [
                    str(item).strip()
                    for item in (payload.get("policy_contract_missing_fields") or [])
                    if str(item or "").strip()
                ],
                "policy_contract_issues": [
                    str(item).strip()
                    for item in (payload.get("policy_contract_issues") or [])
                    if str(item or "").strip()
                ],
                "policy_gate_state": str(payload.get("policy_gate_state") or ""),
                "policy_gate_reason": str(payload.get("policy_gate_reason") or ""),
                "policy_cache_hit": bool(cache_hit),
                "policy_cache_status": cache_status,
                "policy_cache_reason": cache_reason,
                "policy_cache_cached_at": cache_cached_at,
                "policy_cache_trace": cache_trace,
                "agents_mtime": agents_mtime,
            }
        )
        seen.add(agent_name)
        if target_name and agent_name == target_name:
            break
    if cache_conn is not None:
        try:
            cache_conn.commit()
        finally:
            cache_conn.close()

    if not analyze_policy:
        agents.sort(key=lambda item: str(item.get("agent_name") or "").lower())
    else:
        def gate_rank(item: dict[str, Any]) -> tuple[int, str]:
            gate = str(item.get("clarity_gate") or "").strip().lower()
            parse_status = str(item.get("parse_status") or "").strip().lower()
            if gate == "auto" and parse_status == "ok":
                return (0, str(item.get("agent_name") or "").lower())
            if gate == "auto":
                return (1, str(item.get("agent_name") or "").lower())
            if gate == "confirm":
                return (2, str(item.get("agent_name") or "").lower())
            if parse_status == "failed":
                return (4, str(item.get("agent_name") or "").lower())
            return (3, str(item.get("agent_name") or "").lower())
        agents.sort(key=gate_rank)
    return agents


