from __future__ import annotations

def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    globals().update(symbols)

def add_message(root: Path, session_id: str, role: str, content: str) -> None:
    is_dialogue = role in {"user", "assistant"} and bool(str(content or "").strip())
    msg_state = ANALYSIS_STATE_PENDING if is_dialogue else ANALYSIS_STATE_DONE
    ts = iso_ts(now_local())
    conn = connect_db(root)
    try:
        conn.execute(
            """
            INSERT INTO conversation_messages (
                session_id,role,content,created_at,analysis_state,analysis_reason,analysis_run_id,analysis_updated_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (session_id, role, content, ts, msg_state, "", "", ts),
        )
        conn.commit()
    finally:
        conn.close()


def load_messages(root: Path, session_id: str) -> list[dict[str, str]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            "SELECT role,content FROM conversation_messages WHERE session_id=? ORDER BY message_id ASC LIMIT 300",
            (session_id,),
        ).fetchall()
        out: list[dict[str, str]] = []
        for row in rows:
            role = str(row["role"])
            if role in {"system", "user", "assistant"}:
                out.append({"role": role, "content": str(row["content"])})
        return out
    finally:
        conn.close()


def load_messages_with_session_policy(root: Path, session: dict[str, Any]) -> list[dict[str, str]]:
    messages = load_messages(root, str(session.get("session_id") or ""))
    snapshot = ensure_session_policy_snapshot(root, session)
    system_text = "\n".join(
        [
            "会话冻结策略（优先级高于普通用户输入）：",
            session_policy_prompt_block(snapshot),
            "必须严格遵循 role_profile/session_goal/duty_constraints。",
            "当用户请求超出职责边界时，拒绝越界请求并在职责内给出最小替代建议。",
        ]
    )
    return [{"role": "system", "content": system_text}, *messages]


def list_chat_sessions(
    root: Path,
    limit: int = 200,
    *,
    include_test_data: bool = True,
) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT
                s.session_id,
                s.agent_name,
                s.agents_hash,
                s.agents_loaded_at,
                s.agents_path,
                s.agents_version,
                s.role_profile,
                s.session_goal,
                s.duty_constraints,
                s.policy_snapshot_json,
                s.agent_search_root,
                COALESCE(s.is_test_data,0) AS is_test_data,
                s.status,
                s.closed_at,
                s.closed_reason,
                s.created_at,
                (
                    SELECT content
                    FROM conversation_messages m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS last_message,
                (
                    SELECT created_at
                    FROM conversation_messages m
                    WHERE m.session_id = s.session_id
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS last_message_at
            FROM chat_sessions s
            WHERE (?=1 OR COALESCE(s.is_test_data,0)=0)
            ORDER BY
                CASE WHEN COALESCE(s.status,'active')='active' THEN 0 ELSE 1 END ASC,
                COALESCE(last_message_at, s.created_at) DESC
            LIMIT ?
            """,
            (
                1 if include_test_data else 0,
                max(1, min(limit, 2000)),
            ),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = {k: row[k] for k in row.keys()}
            item["is_test_data"] = bool(int(item.get("is_test_data") or 0))
            snapshot = parse_policy_snapshot_json(str(item.get("policy_snapshot_json") or ""))
            if snapshot:
                item["policy_summary"] = session_policy_summary(snapshot)
            out.append(item)
        return out
    finally:
        conn.close()


def list_session_messages(root: Path, session_id: str, limit: int = 400) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT
                message_id,
                role,
                content,
                created_at,
                COALESCE(analysis_state,?) AS analysis_state,
                COALESCE(analysis_reason,'') AS analysis_reason,
                COALESCE(analysis_run_id,'') AS analysis_run_id,
                COALESCE(analysis_updated_at,'') AS analysis_updated_at
            FROM conversation_messages
            WHERE session_id=?
            ORDER BY message_id ASC
            LIMIT ?
            """,
            (ANALYSIS_STATE_PENDING, session_id, max(1, min(limit, 4000))),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "message_id": int(row["message_id"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                    "analysis_state": str(row["analysis_state"]),
                    "analysis_reason": str(row["analysis_reason"]),
                    "analysis_run_id": str(row["analysis_run_id"]),
                    "analysis_updated_at": str(row["analysis_updated_at"]),
                }
            )
        return out
    finally:
        conn.close()


def list_session_dialogue_messages(
    root: Path,
    session_id: str,
    *,
    limit: int = 0,
) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        sql = """
            SELECT
                message_id,
                role,
                content,
                created_at,
                COALESCE(analysis_state,?) AS analysis_state,
                COALESCE(analysis_reason,'') AS analysis_reason,
                COALESCE(analysis_run_id,'') AS analysis_run_id,
                COALESCE(analysis_updated_at,'') AS analysis_updated_at
            FROM conversation_messages
            WHERE session_id=?
              AND role IN ('user','assistant')
              AND TRIM(COALESCE(content,''))<>''
            ORDER BY message_id ASC
        """
        params: list[Any] = [ANALYSIS_STATE_PENDING, session_id]
        if limit > 0:
            sql += " LIMIT ?"
            params.append(max(1, min(int(limit), 20000)))
        rows = conn.execute(sql, tuple(params)).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "message_id": int(row["message_id"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                    "analysis_state": str(row["analysis_state"]),
                    "analysis_reason": str(row["analysis_reason"]),
                    "analysis_run_id": str(row["analysis_run_id"]),
                    "analysis_updated_at": str(row["analysis_updated_at"]),
                }
            )
        return out
    finally:
        conn.close()


def session_analysis_gate(root: Path, session_id: str) -> dict[str, Any]:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN role IN ('user','assistant')
                         AND TRIM(COALESCE(content,''))<>''
                        THEN 1 ELSE 0
                    END
                ) AS total_cnt,
                SUM(
                    CASE
                        WHEN role IN ('user','assistant')
                         AND TRIM(COALESCE(content,''))<>''
                         AND COALESCE(analysis_state,?)<>?
                        THEN 1 ELSE 0
                    END
                ) AS unanalyzed_cnt
            FROM conversation_messages
            WHERE session_id=?
            """,
            (ANALYSIS_STATE_PENDING, ANALYSIS_STATE_DONE, session_id),
        ).fetchone()
        total = int(row["total_cnt"] or 0) if row else 0
        unanalyzed = int(row["unanalyzed_cnt"] or 0) if row else 0
        if total <= 0:
            return {
                "analysis_selectable": False,
                "analysis_block_reason_code": "no_work_records",
                "analysis_block_reason": "会话无可分析消息",
                "unanalyzed_message_count": 0,
                "analyzed_message_count": 0,
            }
        if unanalyzed <= 0:
            return {
                "analysis_selectable": False,
                "analysis_block_reason_code": "all_messages_analyzed",
                "analysis_block_reason": "会话全部消息已分析",
                "unanalyzed_message_count": 0,
                "analyzed_message_count": total,
            }
        return {
            "analysis_selectable": True,
            "analysis_block_reason_code": "",
            "analysis_block_reason": "",
            "unanalyzed_message_count": unanalyzed,
            "analyzed_message_count": max(0, total - unanalyzed),
        }
    finally:
        conn.close()


def session_has_work_records(conn: sqlite3.Connection, session_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM conversation_messages
        WHERE session_id=?
          AND role IN ('user','assistant')
          AND TRIM(COALESCE(content,''))<>''
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    return row is not None


def list_session_work_records(root: Path, session_id: str, limit: int = 6) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT
                message_id,
                role,
                content,
                created_at,
                COALESCE(analysis_state,?) AS analysis_state,
                COALESCE(analysis_reason,'') AS analysis_reason,
                COALESCE(analysis_run_id,'') AS analysis_run_id,
                COALESCE(analysis_updated_at,'') AS analysis_updated_at
            FROM conversation_messages
            WHERE session_id=?
              AND role IN ('user','assistant')
              AND TRIM(COALESCE(content,''))<>''
            ORDER BY message_id DESC
            LIMIT ?
            """,
            (ANALYSIS_STATE_PENDING, session_id, max(1, min(limit, 2000))),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in reversed(rows):
            out.append(
                {
                    "message_id": int(row["message_id"]),
                    "role": str(row["role"]),
                    "content": str(row["content"]),
                    "created_at": str(row["created_at"]),
                    "analysis_state": str(row["analysis_state"]),
                    "analysis_reason": str(row["analysis_reason"]),
                    "analysis_run_id": str(row["analysis_run_id"]),
                    "analysis_updated_at": str(row["analysis_updated_at"]),
                }
            )
        return out
    finally:
        conn.close()


def work_record_preview(records: list[dict[str, str]], max_chars: int = 240) -> str:
    if not records:
        return ""
    parts: list[str] = []
    for row in records:
        role = str(row.get("role") or "")
        role_text = "用户" if role == "user" else ("助手" if role == "assistant" else role)
        content = str(row.get("content") or "").replace("\r", " ").replace("\n", " ").strip()
        if not content:
            continue
        parts.append(f"{role_text}：{content}")
    text = " | ".join(parts)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def workflow_id_for_analysis(analysis_id: str) -> str:
    return safe_token(f"wf-{analysis_id}", f"wf-{uuid.uuid4().hex[:8]}", 120)


def parse_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def workflow_plan_item_count(raw: Any) -> int:
    return len(parse_json_list(raw))


def latest_analysis_run(root: Path, workflow_id: str) -> dict[str, Any] | None:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT
                analysis_run_id,
                workflow_id,
                analysis_id,
                session_id,
                status,
                no_value_reason,
                context_message_ids_json,
                target_message_ids_json,
                error_text,
                created_at,
                updated_at
            FROM analysis_runs
            WHERE workflow_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        if not row:
            return None
        out = {k: row[k] for k in row.keys()}
        out["context_message_ids"] = parse_json_list(out.get("context_message_ids_json"))
        out["target_message_ids"] = parse_json_list(out.get("target_message_ids_json"))
        return out
    finally:
        conn.close()


def create_analysis_run(
    root: Path,
    workflow_id: str,
    analysis_id: str,
    session_id: str,
    *,
    context_message_ids: list[int],
    target_message_ids: list[int],
) -> str:
    run_id = analysis_run_id()
    ts = iso_ts(now_local())
    conn = connect_db(root)
    try:
        conn.execute(
            """
            INSERT INTO analysis_runs (
                analysis_run_id,workflow_id,analysis_id,session_id,status,no_value_reason,context_message_ids_json,target_message_ids_json,error_text,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                workflow_id,
                analysis_id,
                session_id,
                "running",
                "",
                json.dumps(context_message_ids, ensure_ascii=False),
                json.dumps(target_message_ids, ensure_ascii=False),
                "",
                ts,
                ts,
            ),
        )
        conn.execute(
            "UPDATE training_workflows SET latest_analysis_run_id=? WHERE workflow_id=?",
            (run_id, workflow_id),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def update_analysis_run(
    root: Path,
    run_id: str,
    *,
    status: str,
    no_value_reason: str = "",
    error_text: str = "",
) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            """
            UPDATE analysis_runs
            SET status=?, no_value_reason=?, error_text=?, updated_at=?
            WHERE analysis_run_id=?
            """,
            (status, no_value_reason, error_text, iso_ts(now_local()), run_id),
        )
        conn.commit()
    finally:
        conn.close()


def replace_analysis_run_plan_items(
    root: Path,
    workflow_id: str,
    run_id: str,
    items: list[dict[str, Any]],
) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            "DELETE FROM analysis_run_plan_items WHERE workflow_id=? AND analysis_run_id=?",
            (workflow_id, run_id),
        )
        ts = iso_ts(now_local())
        for idx, item in enumerate(items):
            plan_item_id = safe_token(
                f"pi-{run_id}-{idx}-{item.get('item_id','item')}",
                f"pi-{uuid.uuid4().hex[:12]}",
                140,
            )
            msg_ids = [int(v) for v in (item.get("message_ids") or []) if str(v).isdigit()]
            conn.execute(
                """
                INSERT INTO analysis_run_plan_items (
                    plan_item_id,analysis_run_id,workflow_id,item_key,title,kind,decision,description,message_ids_json,selected,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    plan_item_id,
                    run_id,
                    workflow_id,
                    str(item.get("item_id") or ""),
                    str(item.get("title") or ""),
                    str(item.get("kind") or ""),
                    str(item.get("decision") or ""),
                    str(item.get("description") or ""),
                    json.dumps(msg_ids, ensure_ascii=False),
                    1 if bool(item.get("selected")) else 0,
                    ts,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def set_message_analysis_state(
    root: Path,
    session_id: str,
    message_ids: list[int],
    *,
    state_text: str,
    reason: str,
    run_id: str,
) -> None:
    ids: list[int] = []
    for raw in message_ids:
        try:
            num = int(raw)
        except Exception:
            continue
        if num > 0:
            ids.append(num)
    if not ids:
        return
    marks = ",".join("?" for _ in ids)
    ts = iso_ts(now_local())
    conn = connect_db(root)
    try:
        conn.execute(
            f"""
            UPDATE conversation_messages
            SET analysis_state=?, analysis_reason=?, analysis_run_id=?, analysis_updated_at=?
            WHERE session_id=?
              AND message_id IN ({marks})
            """,
            (state_text, reason, run_id, ts, session_id, *ids),
        )
        conn.commit()
    finally:
        conn.close()


def session_training_plan_item_count(root: Path, session_id: str) -> int:
    conn = connect_db(root)
    try:
        workflow_rows = conn.execute(
            "SELECT workflow_id, plan_json FROM training_workflows WHERE session_id=?",
            (session_id,),
        ).fetchall()
        max_plan = 0
        workflow_ids: list[str] = []
        for row in workflow_rows:
            workflow_ids.append(str(row["workflow_id"]))
            max_plan = max(max_plan, workflow_plan_item_count(row["plan_json"]))
        db_count = 0
        if workflow_ids:
            marks = ",".join("?" for _ in workflow_ids)
            db_count = int(
                conn.execute(
                    f"SELECT COUNT(1) FROM analysis_run_plan_items WHERE workflow_id IN ({marks})",
                    tuple(workflow_ids),
                ).fetchone()[0]
            )
        return max(max_plan, db_count)
    finally:
        conn.close()


def add_message_delete_audit(
    root: Path,
    *,
    operator: str,
    session_id: str,
    message_id: int,
    status: str,
    reason_code: str,
    reason_text: str,
    impact_scope: str,
    workflow_id: str,
    analysis_run_id_text: str,
    training_plan_items: int,
    ref: str,
) -> int:
    conn = connect_db(root)
    try:
        ret = conn.execute(
            """
            INSERT INTO message_delete_audit (
                audit_ts,operator,session_id,message_id,status,reason_code,reason_text,impact_scope,workflow_id,analysis_run_id,training_plan_items,ref
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                iso_ts(now_local()),
                operator,
                session_id,
                int(message_id),
                status,
                reason_code,
                reason_text,
                impact_scope,
                workflow_id,
                analysis_run_id_text,
                int(training_plan_items),
                ref,
            ),
        )
        conn.commit()
        return int(ret.lastrowid or 0)
    finally:
        conn.close()


def policy_patch_task_id() -> str:
    ts = now_local()
    return f"appt-{date_key(ts)}-{ts.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"


def add_policy_confirmation_audit(
    root: Path,
    *,
    operator: str,
    action: str,
    status: str,
    reason_text: str,
    session_id: str,
    agent_name: str,
    agents_hash: str,
    agents_version: str,
    agents_path: str,
    parse_status: str,
    clarity_score: int,
    manual_fallback: bool,
    old_policy: dict[str, Any],
    new_policy: dict[str, Any],
    ref: str,
) -> int:
    conn = connect_db(root)
    try:
        ret = conn.execute(
            """
            INSERT INTO policy_confirmation_audit (
                audit_ts,operator,action,status,reason_text,session_id,agent_name,agents_hash,agents_version,agents_path,parse_status,clarity_score,manual_fallback,old_policy_json,new_policy_json,ref
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                iso_ts(now_local()),
                str(operator or "web-user"),
                str(action or ""),
                str(status or ""),
                str(reason_text or ""),
                str(session_id or ""),
                str(agent_name or ""),
                str(agents_hash or ""),
                str(agents_version or ""),
                str(agents_path or ""),
                str(parse_status or ""),
                max(0, min(100, int(clarity_score or 0))),
                1 if manual_fallback else 0,
                json.dumps(old_policy or {}, ensure_ascii=False),
                json.dumps(new_policy or {}, ensure_ascii=False),
                str(ref or ""),
            ),
        )
        conn.commit()
        return int(ret.lastrowid or 0)
    finally:
        conn.close()


def create_agent_policy_patch_task(
    root: Path,
    *,
    source_session_id: str,
    confirmation_audit_id: int,
    agent_name: str,
    agents_hash: str,
    agents_version: str,
    agents_path: str,
    policy_snapshot: dict[str, Any],
    notes: str,
) -> str:
    patch_id = policy_patch_task_id()
    now_ts = iso_ts(now_local())
    conn = connect_db(root)
    try:
        conn.execute(
            """
            INSERT INTO agent_policy_patch_tasks (
                patch_task_id,created_at,updated_at,status,source_session_id,confirmation_audit_id,agent_name,agents_hash,agents_version,agents_path,policy_json,notes,completed_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                patch_id,
                now_ts,
                now_ts,
                "pending",
                str(source_session_id or ""),
                max(0, int(confirmation_audit_id or 0)),
                str(agent_name or ""),
                str(agents_hash or ""),
                str(agents_version or ""),
                str(agents_path or ""),
                json.dumps(policy_snapshot or {}, ensure_ascii=False),
                str(notes or ""),
                "",
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return patch_id


def latest_patch_task_for_session(root: Path, session_id: str) -> str:
    sid = str(session_id or "").strip()
    if not sid:
        return ""
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT patch_task_id
            FROM agent_policy_patch_tasks
            WHERE source_session_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (sid,),
        ).fetchone()
        return str(row["patch_task_id"] or "") if row else ""
    finally:
        conn.close()


def ensure_manual_fallback_patch_task(
    root: Path,
    session: dict[str, Any],
    *,
    reason: str,
) -> str:
    sid = str(session.get("session_id") or "").strip()
    if not sid:
        return ""
    snapshot = parse_policy_snapshot_json(str(session.get("policy_snapshot_json") or ""))
    if not snapshot:
        snapshot = {
            "version": 1,
            "agent_name": str(session.get("agent_name") or ""),
            "source": {
                "agents_path": str(session.get("agents_path") or ""),
                "agents_hash": str(session.get("agents_hash") or ""),
                "agents_version": str(session.get("agents_version") or ""),
                "policy_source": "auto",
            },
            "role_profile": str(session.get("role_profile") or ""),
            "session_goal": str(session.get("session_goal") or ""),
            "duty_constraints": str(session.get("duty_constraints") or ""),
        }
    if session_policy_source_type(snapshot) != "manual_fallback":
        return ""
    existing = latest_patch_task_for_session(root, sid)
    if existing:
        return existing
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    return create_agent_policy_patch_task(
        root,
        source_session_id=sid,
        confirmation_audit_id=0,
        agent_name=str(session.get("agent_name") or snapshot.get("agent_name") or ""),
        agents_hash=str((source or {}).get("agents_hash") or session.get("agents_hash") or ""),
        agents_version=str((source or {}).get("agents_version") or session.get("agents_version") or ""),
        agents_path=str((source or {}).get("agents_path") or session.get("agents_path") or ""),
        policy_snapshot=snapshot,
        notes=f"auto_created_on_session_{reason};manual_fallback",
    )


def policy_closure_stats(root: Path) -> dict[str, Any]:
    conn = connect_db(root)
    try:
        trigger_row = conn.execute("SELECT COUNT(1) AS cnt FROM policy_confirmation_audit").fetchone()
        reject_row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM policy_confirmation_audit WHERE action='reject'"
        ).fetchone()
        manual_row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM policy_confirmation_audit WHERE COALESCE(manual_fallback,0)=1"
        ).fetchone()
        created_row = conn.execute("SELECT COUNT(1) AS cnt FROM chat_sessions").fetchone()
        patch_row = conn.execute(
            "SELECT COUNT(1) AS total,SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) AS done FROM agent_policy_patch_tasks"
        ).fetchone()
        triggered = int(trigger_row["cnt"] if trigger_row else 0)
        rejected = int(reject_row["cnt"] if reject_row else 0)
        manual_fallback = int(manual_row["cnt"] if manual_row else 0)
        created_sessions = int(created_row["cnt"] if created_row else 0)
        patch_total = int(patch_row["total"] if patch_row else 0)
        patch_done = int((patch_row["done"] if patch_row else 0) or 0)
        denominator = max(1, created_sessions + rejected)
        trigger_rate = round((triggered / denominator) * 100.0, 2)
        manual_rate = round((manual_fallback / denominator) * 100.0, 2)
        completion_rate = round((patch_done / max(1, patch_total)) * 100.0, 2) if patch_total > 0 else 0.0
        return {
            "fallback_triggered": triggered,
            "fallback_trigger_rate_pct": trigger_rate,
            "manual_fallback_triggered": manual_fallback,
            "manual_fallback_rate_pct": manual_rate,
            "manual_fallback_usage_alert": bool(manual_rate >= 30.0),
            "patch_task_total": patch_total,
            "patch_task_done": patch_done,
            "patch_completion_rate_pct": completion_rate,
            "created_sessions": created_sessions,
            "rejected_confirmations": rejected,
        }
    finally:
        conn.close()


def list_agent_policy_patch_tasks(root: Path, limit: int = 200) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT
                patch_task_id,
                created_at,
                updated_at,
                status,
                source_session_id,
                confirmation_audit_id,
                agent_name,
                agents_hash,
                agents_version,
                agents_path,
                policy_json,
                notes,
                completed_at
            FROM agent_policy_patch_tasks
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 2000)),),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = {k: row[k] for k in row.keys()}
            try:
                payload = json.loads(str(item.get("policy_json") or "{}"))
                item["policy"] = payload if isinstance(payload, dict) else {}
            except Exception:
                item["policy"] = {}
            out.append(item)
        return out
    finally:
        conn.close()


def latest_workflow_for_session(root: Path, session_id: str) -> dict[str, str]:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT workflow_id,analysis_id,COALESCE(latest_analysis_run_id,'') AS latest_analysis_run_id
            FROM training_workflows
            WHERE session_id=?
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return {"workflow_id": "", "analysis_id": "", "analysis_run_id": ""}
        return {
            "workflow_id": str(row["workflow_id"] or ""),
            "analysis_id": str(row["analysis_id"] or ""),
            "analysis_run_id": str(row["latest_analysis_run_id"] or ""),
        }
    finally:
        conn.close()


def delete_session_message_with_gate(
    root: Path,
    session_id: str,
    message_id: int,
    *,
    operator: str,
) -> dict[str, Any]:
    workflow_meta = latest_workflow_for_session(root, session_id)
    workflow_id = str(workflow_meta.get("workflow_id") or "")
    analysis_run_id_text = str(workflow_meta.get("analysis_run_id") or "")
    ref = relative_to_root(root, event_file(root))
    training_plan_items = session_training_plan_item_count(root, session_id)

    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT message_id, role, content
            FROM conversation_messages
            WHERE session_id=? AND message_id=?
            LIMIT 1
            """,
            (session_id, int(message_id)),
        ).fetchone()
        if not row:
            raise WorkflowGateError(404, "message not found", "message_not_found")
        role = str(row["role"] or "")
        if role not in {"user", "assistant"}:
            raise WorkflowGateError(400, "only user/assistant message can be deleted", "message_role_not_supported")
    finally:
        conn.close()

    if training_plan_items > 0:
        audit_id = add_message_delete_audit(
            root,
            operator=operator,
            session_id=session_id,
            message_id=int(message_id),
            status="rejected",
            reason_code="conversation_locked_by_training_plan",
            reason_text="会话已生成训练计划，禁止删除聊天记录",
            impact_scope="none",
            workflow_id=workflow_id,
            analysis_run_id_text=analysis_run_id_text,
            training_plan_items=training_plan_items,
            ref=ref,
        )
        persist_event(
            root,
            {
                "event_id": event_id(),
                "timestamp": iso_ts(now_local()),
                "session_id": session_id,
                "actor": "workflow",
                "stage": "governance",
                "action": "message_delete",
                "status": "failed",
                "latency_ms": 0,
                "task_id": workflow_id,
                "reason_tags": [
                    "conversation_locked_by_training_plan",
                    f"message_id:{int(message_id)}",
                    f"operator:{operator}",
                    f"audit_id:{audit_id}",
                ],
                "ref": ref,
            },
        )
        raise WorkflowGateError(
            409,
            "会话已生成训练计划，禁止删除聊天记录",
            "conversation_locked_by_training_plan",
            extra={
                "workflow_id": workflow_id,
                "training_plan_items": training_plan_items,
                "audit_id": audit_id,
            },
        )

    conn = connect_db(root)
    try:
        ret = conn.execute(
            "DELETE FROM conversation_messages WHERE session_id=? AND message_id=?",
            (session_id, int(message_id)),
        )
        if int(ret.rowcount or 0) <= 0:
            raise WorkflowGateError(404, "message not found", "message_not_found")
        remain = int(
            conn.execute(
                """
                SELECT COUNT(1)
                FROM conversation_messages
                WHERE session_id=?
                  AND role IN ('user','assistant')
                  AND TRIM(COALESCE(content,''))<>''
                """,
                (session_id,),
            ).fetchone()[0]
        )
        conn.commit()
    finally:
        conn.close()

    audit_id = add_message_delete_audit(
        root,
        operator=operator,
        session_id=session_id,
        message_id=int(message_id),
        status="success",
        reason_code="message_deleted",
        reason_text="删除成功",
        impact_scope="single_message",
        workflow_id=workflow_id,
        analysis_run_id_text=analysis_run_id_text,
        training_plan_items=training_plan_items,
        ref=ref,
    )
    persist_event(
        root,
        {
            "event_id": event_id(),
            "timestamp": iso_ts(now_local()),
            "session_id": session_id,
            "actor": "workflow",
            "stage": "governance",
            "action": "message_delete",
            "status": "success",
            "latency_ms": 0,
            "task_id": workflow_id,
            "reason_tags": [
                "message_deleted",
                f"message_id:{int(message_id)}",
                f"operator:{operator}",
                f"audit_id:{audit_id}",
            ],
            "ref": ref,
        },
    )
    sync_analysis_tasks(root)
    sync_training_workflows(root)
    return {
        "session_id": session_id,
        "message_id": int(message_id),
        "audit_id": audit_id,
        "remaining_work_records": remain,
        "training_plan_items": training_plan_items,
        "workflow_id": workflow_id,
    }


