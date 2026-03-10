from __future__ import annotations

import os
import time

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

def training_release_evaluation_id() -> str:
    ts = now_local()
    return f"trev-{date_key(ts)}-{ts.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"


RELEASE_REVIEW_STATES = (
    "idle",
    "report_generating",
    "report_ready",
    "review_approved",
    "review_rejected",
    "review_discarded",
    "publish_running",
    "publish_failed",
    "report_failed",
)
RELEASE_REVIEW_PROMPT_VERSION = "2026-03-10-release-review-v8"
RELEASE_REVIEW_FALLBACK_PROMPT_VERSION = "2026-03-10-release-review-fallback-v2"
RELEASE_REVIEW_CODEX_TIMEOUT_S = 900
RELEASE_REVIEW_ENTERABLE_STATES = ("idle", "review_rejected", "review_discarded", "publish_failed", "report_failed")
RELEASE_REVIEW_DISCARDABLE_STATES = ("report_generating", "report_ready", "review_approved")
RELEASE_REVIEW_CONFIRMABLE_STATES = ("review_approved", "publish_failed")
RELEASE_REVIEW_REPORT_FIELDS = (
    "target_version",
    "current_workspace_ref",
    "previous_release_version",
    "first_person_summary",
    "full_capability_inventory",
    "knowledge_scope",
    "agent_skills",
    "applicable_scenarios",
    "change_summary",
    "capability_delta",
    "risk_list",
    "validation_evidence",
    "release_recommendation",
    "next_action_suggestion",
    "warnings",
)
RELEASE_REVIEW_REQUIRED_FIELDS = (
    "target_version",
    "current_workspace_ref",
    "first_person_summary",
    "full_capability_inventory",
    "knowledge_scope",
    "agent_skills",
    "applicable_scenarios",
    "change_summary",
    "release_recommendation",
    "next_action_suggestion",
)
RELEASE_REVIEW_FAILURE_REPORT_FIELDS = (
    "target_version",
    "current_workspace_ref",
    "change_summary",
    "release_recommendation",
    "next_action_suggestion",
)


def _release_review_codex_timeout_s() -> int:
    raw = str(os.getenv("WORKFLOW_RELEASE_REVIEW_CODEX_TIMEOUT_S") or "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return max(60, min(1200, value))
        except Exception:
            pass
    return max(60, int(RELEASE_REVIEW_CODEX_TIMEOUT_S))


def training_release_review_id() -> str:
    ts = now_local()
    return f"trrv-{date_key(ts)}-{ts.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"


def _can_enter_release_review(lifecycle_state: str, current_state: str) -> bool:
    return normalize_lifecycle_state(lifecycle_state) == "pre_release" and str(current_state or "").strip() in RELEASE_REVIEW_ENTERABLE_STATES


def _can_confirm_release_review(lifecycle_state: str, current_state: str, review_decision: str) -> bool:
    return (
        normalize_lifecycle_state(lifecycle_state) == "pre_release"
        and str(current_state or "").strip() in RELEASE_REVIEW_CONFIRMABLE_STATES
        and str(review_decision or "").strip() == "approve_publish"
    )


def _can_discard_release_review(lifecycle_state: str, current_state: str, review_id: str) -> bool:
    return (
        normalize_lifecycle_state(lifecycle_state) == "pre_release"
        and bool(str(review_id or "").strip())
        and str(current_state or "").strip() in RELEASE_REVIEW_DISCARDABLE_STATES
    )


def _release_review_field_present(value: Any) -> bool:
    if isinstance(value, list):
        return bool([item for item in value if str(item or "").strip()])
    if isinstance(value, dict):
        return bool(value)
    return bool(str(value or "").strip())


def _release_review_missing_fields(report: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    node = report if isinstance(report, dict) else {}
    return [field for field in fields if not _release_review_field_present(node.get(field))]


def _json_dumps_text(payload: Any, fallback: str) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return str(fallback or "")


def _json_load_dict(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _json_load_list(raw: Any) -> list[Any]:
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def _release_review_trace_root(root: Path) -> Path:
    path = root / "logs" / "release-review"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _release_review_trace_dir(root: Path, agent_name: str, review_id: str) -> Path:
    stamp = now_local().strftime("%Y%m%d-%H%M%S")
    token = safe_token(agent_name, "agent", 40) or "agent"
    folder = _release_review_trace_root(root) / f"{stamp}-{token}-{safe_token(review_id, 'review', 80)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _release_review_attempt_dir(trace_dir: Path, prefix: str) -> Path:
    stamp = now_local().strftime("%Y%m%d-%H%M%S")
    token = safe_token(prefix, "attempt", 40) or "attempt"
    folder = trace_dir / f"{token}-{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _write_release_review_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(text or ""), encoding="utf-8")


def _write_release_review_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _path_for_ui(root: Path, path: Path | str) -> str:
    try:
        if isinstance(path, Path):
            target = path.resolve(strict=False)
        else:
            target = Path(str(path or "")).resolve(strict=False)
        return relative_to_root(root, target)
    except Exception:
        if isinstance(path, Path):
            return path.as_posix()
        return str(path or "")


def _release_review_extract_codex_event_text(event: dict[str, Any]) -> str:
    if not isinstance(event, dict):
        return ""
    if str(event.get("type") or "").strip() != "item.completed":
        return ""
    item = event.get("item")
    if not isinstance(item, dict):
        return ""
    if str(item.get("type") or "").strip() != "agent_message":
        return ""
    text = str(item.get("text") or "").strip()
    if text:
        return text
    content = item.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for node in content:
        if not isinstance(node, dict):
            continue
        part = str(node.get("text") or node.get("output_text") or "").strip()
        if part:
            parts.append(part)
    return "\n".join(parts).strip()


def _release_review_extract_json_objects(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").strip()
    if not raw:
        return []
    out: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    idx = 0
    total = len(raw)
    while idx < total:
        start = raw.find("{", idx)
        if start < 0:
            break
        try:
            value, consumed = decoder.raw_decode(raw[start:])
        except Exception:
            idx = start + 1
            continue
        idx = start + max(1, consumed)
        if isinstance(value, dict):
            out.append(value)
    return out


def _release_review_structured_result_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    expected_keys = {
        "target_version",
        "current_workspace_ref",
        "previous_release_version",
        "first_person_summary",
        "full_capability_inventory",
        "knowledge_scope",
        "agent_skills",
        "applicable_scenarios",
        "change_summary",
        "capability_delta",
        "risk_list",
        "validation_evidence",
        "release_recommendation",
        "next_action_suggestion",
        "failure_reason",
        "retry_target_version",
        "retry_release_notes",
    }
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        keys = {str(key or "").strip() for key in candidate.keys()}
        if keys & expected_keys:
            out.append(candidate)
    return out


def _release_review_collect_payload_candidates(raw: Any, *, depth: int = 0) -> list[dict[str, Any]]:
    if depth > 4 or raw is None:
        return []
    out: list[dict[str, Any]] = []
    if isinstance(raw, dict):
        out.append(raw)
        for key, value in raw.items():
            key_text = str(key or "").strip().lower()
            if key_text in {
                "item",
                "report",
                "result",
                "data",
                "output",
                "final",
                "response",
                "message",
                "text",
                "content",
                "payload",
                "output_text",
            }:
                out.extend(_release_review_collect_payload_candidates(value, depth=depth + 1))
    elif isinstance(raw, list):
        for item in raw[:10]:
            out.extend(_release_review_collect_payload_candidates(item, depth=depth + 1))
    elif isinstance(raw, str) and "{" in raw:
        for item in _release_review_extract_json_objects(raw):
            out.extend(_release_review_collect_payload_candidates(item, depth=depth + 1))
    return out


def _release_review_payload_score(candidate: dict[str, Any]) -> int:
    if not isinstance(candidate, dict):
        return -1
    score = 0
    for key in (
        "target_version",
        "current_workspace_ref",
        "previous_release_version",
        "first_person_summary",
        "full_capability_inventory",
        "knowledge_scope",
        "agent_skills",
        "applicable_scenarios",
        "change_summary",
        "capability_delta",
        "risk_list",
        "validation_evidence",
        "release_recommendation",
        "next_action_suggestion",
        "warnings",
        "failure_reason",
        "retry_target_version",
        "retry_release_notes",
    ):
        if key not in candidate:
            continue
        value = candidate.get(key)
        if isinstance(value, list):
            score += 3 if value else 1
        elif isinstance(value, dict):
            score += 1 if value else 0
        else:
            score += 3 if str(value or "").strip() else 1
    for alias_key in ("summary", "recommendation", "next_action", "workspace_ref", "version"):
        if alias_key in candidate and str(candidate.get(alias_key) or "").strip():
            score += 1
    return score


def _release_review_best_payload(raw: Any) -> dict[str, Any]:
    candidates = _release_review_collect_payload_candidates(raw)
    if not candidates:
        return {}
    ranked = sorted(candidates, key=_release_review_payload_score, reverse=True)
    best = ranked[0] if ranked else {}
    return best if isinstance(best, dict) else {}


def _release_review_pick_text(source: dict[str, Any], *keys: str) -> str:
    if not isinstance(source, dict):
        return ""
    for key in keys:
        if key not in source:
            continue
        value = source.get(key)
        if isinstance(value, list):
            text = "\n".join([str(item or "").strip() for item in value if str(item or "").strip()]).strip()
        else:
            text = str(value or "").strip()
        if text:
            return text
    return ""


def _release_review_normalize_recommendation(value: Any) -> str:
    key = str(value or "").strip().lower()
    if not key:
        return ""
    mapping = {
        "approve_publish": "approve",
        "approve": "approve",
        "approve_release": "approve",
        "publish": "approve",
        "go": "approve",
        "通过": "approve",
        "review_approved": "approve",
        "reject_continue_training": "needs_more_validation",
        "continue_training": "needs_more_validation",
        "continue_train": "needs_more_validation",
        "needs_more_validation": "needs_more_validation",
        "hold": "needs_more_validation",
        "retry": "needs_more_validation",
        "继续训练": "needs_more_validation",
        "reject_discard_pre_release": "reject",
        "discard_pre_release": "reject",
        "discard": "reject",
        "abandon": "reject",
        "舍弃预发布": "reject",
        "reject": "reject",
    }
    return mapping.get(key, "")


def _release_review_default_next_action(recommendation: str, *, has_structured_content: bool) -> str:
    key = str(recommendation or "").strip().lower()
    if key == "approve":
        return "我建议人工复核风险与验证证据，无误后提交审核结论并进入确认发布。"
    if key == "reject":
        return "我建议人工确认本次预发布是否应直接舍弃；若确认无保留价值，可提交“不通过：舍弃预发布”。"
    if has_structured_content:
        return "我建议先根据本次报告补齐风险说明或验证证据，再重新进入发布评审。"
    return "我建议先查看分析链路中的 stdout / stderr / 报告文件，修正结构化输出后重新进入发布评审。"


def _normalize_text_list(raw: Any, *, limit: int = 280) -> list[str]:
    if isinstance(raw, list):
        out = []
        for item in raw:
            text = _short_text(str(item or "").strip(), limit)
            if text:
                out.append(text)
        return out
    text = str(raw or "").strip()
    if not text:
        return []
    return [_short_text(line.strip("- •\t "), limit) for line in text.splitlines() if line.strip()]


def _text_items(raw: Any, *, limit: int = 8, item_limit: int = 220) -> list[str]:
    values = raw if isinstance(raw, list) else re.split(r"[\r\n]+|(?<=[。；;!?！？])", str(raw or "").strip())
    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _short_text(str(item or "").strip().strip("-•* \t"), item_limit)
        if not text:
            continue
        key = re.sub(r"\s+", "", text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max(1, int(limit or 1)):
            break
    return out


def _ensure_first_person_text(value: Any, prefix: str, *, limit: int = 320) -> str:
    text = _short_text(str(value or "").strip(), limit)
    if not text:
        return ""
    if text.startswith(("我是", "我当前", "我能", "我已", "我会", "我建议", "本次发布", "当前工作区")):
        return text
    if text.startswith("你是"):
        return "我" + text[1:]
    if text.startswith("作为"):
        return "我" + text
    return prefix + text


def _ensure_first_person_list(raw: Any, prefix: str, *, limit: int = 8, item_limit: int = 220) -> list[str]:
    out: list[str] = []
    for item in _text_items(raw, limit=limit, item_limit=item_limit):
        out.append(_ensure_first_person_text(item, prefix, limit=item_limit))
    return out


def _release_review_agent_context(agent: dict[str, Any]) -> dict[str, Any]:
    workspace = Path(str(agent.get("workspace_path") or "")).resolve(strict=False)
    agents_md_path = workspace / "AGENTS.md"
    portrait_parser = globals().get("extract_agent_role_portrait")
    policy_parser = globals().get("extract_agent_policy_fields")
    list_workspace_local_skills = globals().get("_list_workspace_local_skills")

    portrait: dict[str, Any] = {}
    if callable(portrait_parser):
        try:
            portrait = portrait_parser(agents_md_path)
        except Exception:
            portrait = {}

    agents_text = ""
    try:
        if agents_md_path.exists():
            agents_text = agents_md_path.read_text(encoding="utf-8")
    except Exception:
        agents_text = ""

    policy_payload: dict[str, Any] = {}
    if agents_text and callable(policy_parser):
        try:
            policy_payload = policy_parser(agents_text)
        except Exception:
            policy_payload = {}

    duty_constraints = [
        _short_text(str(item or "").strip(), 220)
        for item in (policy_payload.get("duty_constraints") or [])
        if str(item or "").strip()
    ]
    capability_inventory: list[str] = []
    for item in _text_items(policy_payload.get("session_goal"), limit=3, item_limit=220):
        if item not in capability_inventory:
            capability_inventory.append(item)
    for item in duty_constraints:
        if item not in capability_inventory:
            capability_inventory.append(item)
        if len(capability_inventory) >= 12:
            break
    if not capability_inventory:
        for item in _text_items(
            str(portrait.get("capability_summary") or agent.get("core_capabilities") or policy_payload.get("role_profile") or ""),
            limit=8,
            item_limit=220,
        ):
            if item not in capability_inventory:
                capability_inventory.append(item)
    if not capability_inventory:
        fallback_item = _short_text(str(agent.get("capability_summary") or portrait.get("capability_summary") or "").strip(), 220)
        if fallback_item:
            capability_inventory.append(fallback_item)

    knowledge_scope = str(
        portrait.get("knowledge_scope")
        or agent.get("knowledge_scope")
        or policy_payload.get("session_goal")
        or policy_payload.get("role_profile")
        or ""
    ).strip()
    applicable_scenarios = _text_items(
        portrait.get("applicable_scenarios") or agent.get("applicable_scenarios") or policy_payload.get("session_goal") or "",
        limit=6,
        item_limit=140,
    )
    local_skills: list[str] = []
    if callable(list_workspace_local_skills):
        try:
            local_skills = _skills_list(list_workspace_local_skills(workspace))
        except Exception:
            local_skills = []
    if not local_skills:
        local_skills = _skills_list(portrait.get("skills") or agent.get("skills") or agent.get("skills_json"))

    first_person_seed = str(
        portrait.get("capability_summary")
        or agent.get("capability_summary")
        or policy_payload.get("role_profile")
        or policy_payload.get("session_goal")
        or ""
    ).strip()
    return {
        "first_person_summary": _ensure_first_person_text(first_person_seed, "我当前的核心能力是：", limit=320),
        "full_capability_inventory": capability_inventory,
        "knowledge_scope": knowledge_scope,
        "agent_skills": local_skills,
        "applicable_scenarios": applicable_scenarios,
        "previous_release_version": str(agent.get("latest_release_version") or "").strip(),
    }


def _derive_what_i_can_do(summary: str, inventory: list[str]) -> list[str]:
    items = _ensure_first_person_list(inventory, "我当前可以：", limit=5, item_limit=180)
    if items:
        return items[:5]
    return _ensure_first_person_list(summary, "我当前可以：", limit=5, item_limit=180)


def _release_review_warning_text(value: Any, *, limit: int = 220) -> str:
    return _ensure_first_person_text(value, "我当前补充说明：", limit=limit)


def _release_review_is_traceability_warning(text: str) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False
    return any(
        token in value
        for token in (
            "readme",
            "changelog",
            "release note",
            "release-note",
            "release notes",
            "release_note",
            "发布说明",
            "发布 note",
        )
    )


def _release_review_is_workspace_external_warning(text: str) -> bool:
    value = str(text or "").strip()
    lowered = value.lower()
    if not value:
        return False
    if "../" in value or "..\\" in value:
        return True
    return any(
        token in lowered
        for token in (
            "工作区外",
            "兄弟目录",
            "sibling",
            "outside workspace",
            "external workspace",
            "other workspace",
        )
    )


def _release_review_is_metadata_conflict_text(text: str) -> bool:
    value = str(text or "").strip()
    lowered = value.lower()
    if not value:
        return False
    if "metadata_conflict" in lowered:
        return True
    keys = (
        "target_version",
        "current_registry_version",
        "latest_release_version",
        "bound_release_version",
        "released_versions",
    )
    conflict_markers = ("冲突", "矛盾", "不一致", "conflict", "mismatch", "inconsistent")
    return any(key in lowered for key in keys) and any(marker in lowered for marker in conflict_markers)


def _release_review_filter_risks(raw_items: Any) -> dict[str, Any]:
    filtered: list[str] = []
    warnings: list[str] = []
    metadata_conflicts: list[str] = []
    demoted_count = 0
    for item in _normalize_text_list(raw_items, limit=220):
        if _release_review_is_traceability_warning(item):
            warnings.append(_release_review_warning_text(item))
            demoted_count += 1
            continue
        if _release_review_is_workspace_external_warning(item):
            warnings.append(_release_review_warning_text(item))
            demoted_count += 1
            continue
        if _release_review_is_metadata_conflict_text(item):
            metadata_conflicts.append(_short_text(item, 220))
            warnings.append(_release_review_warning_text("我识别到版本元数据存在冲突，本次需要先修复元数据再重新进入发布评审。"))
            continue
        filtered.append(_ensure_first_person_text(item, "我当前识别到的风险是：", limit=220))
    return {
        "risk_list": filtered,
        "warnings": warnings,
        "metadata_conflicts": metadata_conflicts,
        "demoted_count": demoted_count,
    }


def _release_review_metadata_conflicts(
    *,
    agent: dict[str, Any],
    target_version: str,
    released_versions: list[str],
) -> list[str]:
    labels = [str(item or "").strip() for item in released_versions if str(item or "").strip()]
    label_set = set(labels)
    conflicts: list[str] = []
    latest_release_version = str(agent.get("latest_release_version") or "").strip()
    bound_release_version = str(agent.get("bound_release_version") or "").strip()
    if target_version and target_version in label_set:
        conflicts.append(f"target_version={target_version} 已存在于 released_versions 中，无法作为新的正式发布目标版本。")
    if latest_release_version and label_set and latest_release_version not in label_set:
        conflicts.append(
            f"latest_release_version={latest_release_version} 未出现在 released_versions 中，请先修复版本元数据。"
        )
    if bound_release_version and label_set and bound_release_version not in label_set:
        conflicts.append(
            f"bound_release_version={bound_release_version} 未出现在 released_versions 中，请先修复版本元数据。"
        )
    return conflicts


def _build_release_public_profile_snapshot(
    *,
    agent: dict[str, Any],
    report: dict[str, Any],
    analysis_chain: dict[str, Any],
    review_id: str,
) -> dict[str, Any]:
    summary = _ensure_first_person_text(report.get("first_person_summary"), "我当前的核心能力是：", limit=320)
    inventory = _ensure_first_person_list(report.get("full_capability_inventory"), "我当前可以：", limit=12, item_limit=220)
    knowledge_scope = _ensure_first_person_text(report.get("knowledge_scope"), "我当前覆盖的知识范围是：", limit=320)
    scenarios = _text_items(report.get("applicable_scenarios"), limit=6, item_limit=140)
    return {
        "profile_source": "latest_release_report",
        "review_id": review_id,
        "agent_id": str(agent.get("agent_id") or "").strip(),
        "agent_name": str(agent.get("agent_name") or "").strip(),
        "source_release_version": str(report.get("target_version") or "").strip(),
        "first_person_summary": summary,
        "what_i_can_do": _derive_what_i_can_do(summary, inventory),
        "full_capability_inventory": inventory,
        "knowledge_scope": knowledge_scope,
        "agent_skills": _skills_list(report.get("agent_skills")),
        "applicable_scenarios": scenarios,
        "version_notes": _short_text(str(report.get("change_summary") or "").strip(), 320),
        "change_summary": _short_text(str(report.get("change_summary") or "").strip(), 1000),
        "capability_delta": _ensure_first_person_list(report.get("capability_delta"), "我本次主要补充了：", limit=8, item_limit=220),
        "risk_list": _ensure_first_person_list(report.get("risk_list"), "我当前识别到的风险是：", limit=8, item_limit=220),
        "validation_evidence": _ensure_first_person_list(report.get("validation_evidence"), "我当前已确认的证据是：", limit=8, item_limit=240),
        "release_recommendation": str(report.get("release_recommendation") or "").strip(),
        "next_action_suggestion": _ensure_first_person_text(report.get("next_action_suggestion"), "我建议下一步：", limit=320),
        "analysis_chain_ref": str(analysis_chain.get("report_path") or analysis_chain.get("trace_dir") or "").strip(),
        "public_profile_ref": "",
        "capability_snapshot_ref": "",
    }


def _build_release_public_profile_markdown(snapshot: dict[str, Any]) -> str:
    lines = [
        "# 最新正式发布角色述职报告",
        "",
        f"- 角色：{str(snapshot.get('agent_name') or snapshot.get('agent_id') or '').strip() or '-'}",
        f"- 目标版本：{str(snapshot.get('source_release_version') or '').strip() or '-'}",
        "",
        "## 我是 / 我当前能做什么",
        str(snapshot.get("first_person_summary") or "").strip() or "我当前暂无可展示的正式发布摘要。",
        "",
    ]
    what_i_can_do = snapshot.get("what_i_can_do") if isinstance(snapshot.get("what_i_can_do"), list) else []
    if what_i_can_do:
        lines.append("## 我当前能做什么")
        lines.extend([f"- {str(item or '').strip()}" for item in what_i_can_do if str(item or "").strip()])
        lines.append("")
    inventory = snapshot.get("full_capability_inventory") if isinstance(snapshot.get("full_capability_inventory"), list) else []
    if inventory:
        lines.append("## 全量能力清单")
        lines.extend([f"- {str(item or '').strip()}" for item in inventory if str(item or "").strip()])
        lines.append("")
    if str(snapshot.get("knowledge_scope") or "").strip():
        lines.extend(["## 角色知识范围", str(snapshot.get("knowledge_scope") or "").strip(), ""])
    skills = snapshot.get("agent_skills") if isinstance(snapshot.get("agent_skills"), list) else []
    if skills:
        lines.append("## Agent Skills")
        lines.extend([f"- {str(item or '').strip()}" for item in skills if str(item or "").strip()])
        lines.append("")
    scenarios = snapshot.get("applicable_scenarios") if isinstance(snapshot.get("applicable_scenarios"), list) else []
    if scenarios:
        lines.append("## 适用场景")
        lines.extend([f"- {str(item or '').strip()}" for item in scenarios if str(item or "").strip()])
        lines.append("")
    if str(snapshot.get("version_notes") or "").strip():
        lines.extend(["## 版本说明", str(snapshot.get("version_notes") or "").strip(), ""])
    delta = snapshot.get("capability_delta") if isinstance(snapshot.get("capability_delta"), list) else []
    if delta:
        lines.append("## 相对上一正式发布版本的能力增量")
        lines.extend([f"- {str(item or '').strip()}" for item in delta if str(item or "").strip()])
        lines.append("")
    risks = snapshot.get("risk_list") if isinstance(snapshot.get("risk_list"), list) else []
    if risks:
        lines.append("## 风险清单")
        lines.extend([f"- {str(item or '').strip()}" for item in risks if str(item or "").strip()])
        lines.append("")
    evidence = snapshot.get("validation_evidence") if isinstance(snapshot.get("validation_evidence"), list) else []
    if evidence:
        lines.append("## 验证证据")
        lines.extend([f"- {str(item or '').strip()}" for item in evidence if str(item or "").strip()])
        lines.append("")
    if str(snapshot.get("next_action_suggestion") or "").strip():
        lines.extend(["## 下一步建议", str(snapshot.get("next_action_suggestion") or "").strip(), ""])
    return "\n".join(lines).strip() + "\n"


def _write_release_review_profile_assets(
    *,
    root: Path,
    trace_dir: Path,
    agent: dict[str, Any],
    review_id: str,
    report: dict[str, Any],
    analysis_chain: dict[str, Any],
) -> dict[str, Any]:
    snapshot = _build_release_public_profile_snapshot(
        agent=agent,
        report=report,
        analysis_chain=analysis_chain,
        review_id=review_id,
    )
    public_profile_path = trace_dir / "public-role-profile.md"
    capability_snapshot_path = trace_dir / "capability-snapshot.json"
    _write_release_review_text(public_profile_path, _build_release_public_profile_markdown(snapshot))
    snapshot["public_profile_ref"] = _path_for_ui(root, public_profile_path)
    snapshot["capability_snapshot_ref"] = _path_for_ui(root, capability_snapshot_path)
    _write_release_review_json(capability_snapshot_path, snapshot)
    return {
        "public_profile_markdown_path": snapshot["public_profile_ref"],
        "capability_snapshot_json_path": snapshot["capability_snapshot_ref"],
        "snapshot": snapshot,
    }


def _workspace_current_ref(workspace: Path) -> str:
    ok, out = _run_git_readonly(workspace, ["rev-parse", "--short", "HEAD"], timeout_s=12)
    return str(out or "").strip() if ok else ""


def _next_release_version_label(release_labels: list[str], preferred: str = "") -> str:
    labels = [str(item or "").strip() for item in release_labels if str(item or "").strip()]
    used = set(labels)
    preferred_text = str(preferred or "").strip()
    if preferred_text and preferred_text not in used:
        return preferred_text
    semvers: list[tuple[int, int, int]] = []
    for label in labels:
        matched = re.fullmatch(r"[vV]?(\d+)\.(\d+)\.(\d+)", label)
        if not matched:
            continue
        semvers.append((int(matched.group(1)), int(matched.group(2)), int(matched.group(3))))
    if not semvers:
        return "v1.0.0"
    major, minor, patch = sorted(semvers, reverse=True)[0]
    return f"v{major}.{minor}.{patch + 1}"


def _workspace_release_labels(workspace: Path) -> list[str]:
    _, _, rows = _parse_git_release_rows(workspace, limit=160)
    labels: list[str] = []
    for row in rows:
        version_label = str(row.get("version_label") or "").strip()
        if not version_label:
            continue
        labels.append(version_label)
    return labels


def _build_release_review_prompt(
    *,
    agent: dict[str, Any],
    workspace_path: Path,
    target_version: str,
    current_workspace_ref: str,
    released_versions: list[str],
) -> str:
    agents_md_path = workspace_path / "AGENTS.md"
    return "\n".join(
        [
            "你是“角色发布评审助手”。请在指定 agent 工作区内生成结构化发布评审报告，只输出 JSON。",
            "",
            f"prompt_version: {RELEASE_REVIEW_PROMPT_VERSION}",
            "",
            "输入上下文:",
            f"- agent_id: {str(agent.get('agent_id') or '').strip()}",
            f"- agent_name: {str(agent.get('agent_name') or '').strip()}",
            f"- workspace_path: {workspace_path.as_posix()}",
            f"- agents_md_path: {agents_md_path.as_posix()}",
            f"- target_version: {target_version or '-'}",
            f"- current_workspace_ref: {current_workspace_ref or '-'}",
            f"- current_registry_version: {str(agent.get('current_version') or '').strip() or '-'}",
            f"- latest_release_version: {str(agent.get('latest_release_version') or '').strip() or '-'}",
            f"- bound_release_version: {str(agent.get('bound_release_version') or '').strip() or '-'}",
            f"- released_versions: {', '.join(released_versions[:20]) or '(none)'}",
            "",
            "任务:",
            "1) 这是一份“角色发布评审报告”，不是纯仓库卫生巡检单。你的主目标是回答：",
            "   - 当前角色完整能做什么；",
            "   - 相对上一正式发布版本变了什么；",
            "   - 当前是否适合确认发布。",
            "2) 这是一次性发布评审任务，不是常规对话，也不是工作区状态维护任务。",
            "   - 不要执行会话恢复、状态快照维护、偏好写回、复盘归档、训练计划、方法编排、技能编排等与发布评审无关的流程。",
            "   - 不要读取 `workspace_state/`、`user_profile/`、`logs/`、`runs/`、`incidents/`、`metrics/` 等目录来做会话恢复或工作流维护。",
            "   - 不要读取本地 skill 的 `SKILL.md` 正文来展开技能工作流；如需识别技能，只允许根据 `.codex/skills/` 目录名枚举技能名称。",
            "   - 不要输出过程说明、计划、进度播报、todo、推理文字；只允许在任务结束时输出最终 JSON。",
            "3) 阅读 AGENTS.md、当前工作区 Git 信息、最近已发布版本，评估当前预发布内容是否适合确认发布。",
            "   - 生成 first_person_summary / full_capability_inventory / knowledge_scope / agent_skills / applicable_scenarios 时，优先结合 AGENTS.md、当前角色画像字段、本地 skills、工作区说明文档与版本上下文补齐。",
            "   - 优先只读取：AGENTS.md、README.md、CHANGELOG.md（若存在）、最近 release note、git status、git log 最近 20 条、git tag 最近 20 条。",
            "   - 不要递归扫描大型目录；不要遍历 .git 全量历史、node_modules、dist、build、coverage、.venv、site-packages、logs 等大目录。",
            "   - Git 风险判断默认只限当前目标工作区路径范围；工作区外或兄弟目录的脏文件只能作为 warnings，不能主导 release_recommendation。",
            "   - README / CHANGELOG / release note 缺失默认写入 warnings，除非输入上下文明确声明其为硬门禁，不要仅因这些缺失直接 reject。",
            "4) 报告要同时服务两个用途：",
            "   - 用途 A：作为发布评审页的“功能差异报告”，重点说明相对上一正式发布版本的变化、风险与证据。",
            "   - 用途 B：作为正式发布成功后可绑定到角色详情页的“第一人称角色述职介绍”，用于说明当前正式发布版本完整能做什么。",
            "5) 输出一份结构化发布报告，必须覆盖：",
            "   - target_version",
            "   - current_workspace_ref",
            "   - previous_release_version",
            "   - first_person_summary",
            "   - full_capability_inventory",
            "   - knowledge_scope",
            "   - agent_skills",
            "   - applicable_scenarios",
            "   - change_summary",
            "   - capability_delta",
            "   - risk_list",
            "   - validation_evidence",
            "   - release_recommendation",
            "   - next_action_suggestion",
            "6) full_capability_inventory / agent_skills / applicable_scenarios / capability_delta / risk_list / validation_evidence 必须是字符串数组。",
            "7) release_recommendation 只允许输出：approve / reject / needs_more_validation 之一。不要输出人工审核决策枚举。",
            "8) 将这份报告理解为该 agent 面向发布评审环节提交的“述职报告”，自然语言字段统一使用第一人称视角描述。",
            "   - 例如：“我当前补充了… / 我识别到… / 我已完成… / 我建议下一步…”。",
            "   - 适用字段包括：first_person_summary、change_summary、capability_delta[]、risk_list[]、validation_evidence[]、next_action_suggestion、warnings[]。",
            "   - 人工审核结论不在本 JSON 中表达，因此这里不需要输出 reviewer 视角内容。",
            "9) full_capability_inventory 必须描述“当前目标版本完整能做什么”，不能只写 capability_delta。",
            "10) capability_delta 必须明确说明“相对上一正式发布版本”的变化；若上一正式发布版本不存在，则按“首发基线评审”处理：previous_release_version 允许为空，但仍必须输出完整第一人称全量能力报告，并在 warnings[] 里写明当前是首发基线。",
            "11) 若输入上下文中的版本元数据自相矛盾，请在 warnings[] 和 next_action_suggestion 中明确指出元数据冲突，不要把它伪装成 agent 能力风险。",
            "12) 若信息不足，不要编造；在 warnings[] 里明确指出。",
            "13) target_version 必须直接复制输入上下文中的 target_version；current_workspace_ref 必须直接复制输入上下文中的 current_workspace_ref。",
            "14) 即使信息不足，也不要省略字段；必须保留完整 JSON 结构，并在 warnings[] / next_action_suggestion 里说明不足。",
            "",
            "输出要求:",
            "- 仅输出一个 JSON 对象。",
            "- 不要输出 Markdown，不要输出代码块，不要输出额外解释文字。",
            "- 任何字段都不要改名。",
            "- 字段至少包含：",
            "{",
            '  "target_version": "",',
            '  "current_workspace_ref": "",',
            '  "previous_release_version": "",',
            '  "first_person_summary": "",',
            '  "full_capability_inventory": ["..."],',
            '  "knowledge_scope": "",',
            '  "agent_skills": ["..."],',
            '  "applicable_scenarios": ["..."],',
            '  "change_summary": "",',
            '  "capability_delta": ["..."],',
            '  "risk_list": ["..."],',
            '  "validation_evidence": ["..."],',
            '  "release_recommendation": "approve|reject|needs_more_validation",',
            '  "next_action_suggestion": "",',
            '  "warnings": []',
            "}",
        ]
    )


def _build_release_review_fallback_prompt(
    *,
    review: dict[str, Any],
    publish_version: str,
    publish_error: str,
    execution_logs: list[dict[str, Any]],
) -> str:
    payload = json.dumps(
        {
            "review_id": review.get("review_id"),
            "agent_id": review.get("agent_id"),
            "target_version": review.get("target_version"),
            "publish_version": publish_version,
            "publish_error": publish_error,
            "execution_logs": execution_logs,
            "report": review.get("report") if isinstance(review.get("report"), dict) else {},
        },
        ensure_ascii=False,
        indent=2,
    )
    return "\n".join(
        [
            "你是“角色发布失败兜底助手”。请先分析失败原因，再尽量在当前 agent 工作区内执行可落地修复，然后给出一次自动重试所需的结构化结果，只输出 JSON。",
            "",
            f"prompt_version: {RELEASE_REVIEW_FALLBACK_PROMPT_VERSION}",
            "",
            "输入上下文(JSON):",
            payload,
            "",
            "任务:",
            "1) 分析本次 Git 发布 / release note / 校验失败原因。",
            "2) 若问题位于当前 agent 工作区内且你能在当前权限内修复，请直接执行修复动作；若属于环境/系统依赖问题且当前权限无法修复，请明确说明无法自动修复。",
            "3) 给出并执行一次自动重试前需要补充的 release note 建议（如无需修改可留空）。",
            "4) 输出已执行的修复动作、自动重试建议与下一步人工建议。",
            "",
            "输出要求:",
            "{",
            '  "failure_reason": "",',
            '  "repair_summary": "",',
            '  "repair_actions": ["..."],',
            '  "retry_target_version": "",',
            '  "retry_release_notes": "",',
            '  "next_action_suggestion": "",',
            '  "warnings": []',
            "}",
        ]
    )


def _run_codex_exec_for_release_review(
    *,
    root: Path,
    workspace_root: Path,
    trace_dir: Path,
    prompt_text: str,
) -> dict[str, Any]:
    prompt_path = trace_dir / "prompt.txt"
    stdout_path = trace_dir / "stdout.txt"
    stderr_path = trace_dir / "stderr.txt"
    raw_result_path = trace_dir / "codex-result.raw.json"
    parsed_result_path = trace_dir / "parsed-result.json"
    _write_release_review_text(prompt_path, prompt_text)

    command_summary = "codex exec --json --skip-git-repo-check --sandbox workspace-write --add-dir <workspace_root> -C <workspace_root> -"
    codex_bin = shutil.which("codex")
    stdout_text = ""
    stderr_text = ""
    codex_exit_code = None
    error_text = ""
    codex_events: list[dict[str, Any]] = []
    parsed_result: dict[str, Any] = {}
    started_ms = int(time.time() * 1000)
    finished_ms = started_ms
    if not codex_bin:
        error_text = "codex_command_not_found"
    else:
        command = [
            codex_bin,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox",
            "workspace-write",
            "--add-dir",
            workspace_root.as_posix(),
            "-C",
            workspace_root.as_posix(),
            "-",
        ]
        proc = None
        try:
            proc = subprocess.Popen(
                command,
                cwd=workspace_root.as_posix(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            stdout_text, stderr_text = proc.communicate(prompt_text + "\n", timeout=_release_review_codex_timeout_s())
            codex_exit_code = int(proc.returncode or 0)
            if codex_exit_code != 0:
                error_text = f"codex_exec_failed_exit_{codex_exit_code}"
        except subprocess.TimeoutExpired:
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    stdout_text, stderr_text = proc.communicate(timeout=3)
                except Exception:
                    stdout_text, stderr_text = "", ""
                codex_exit_code = int(proc.returncode or 124)
            error_text = "codex_exec_timeout"
        except Exception as exc:
            error_text = f"codex_exec_exception:{exc}"
        finally:
            finished_ms = int(time.time() * 1000)

    _write_release_review_text(stdout_path, stdout_text)
    _write_release_review_text(stderr_path, stderr_text)

    message_texts: list[str] = []
    event_errors: list[str] = []
    for line in stdout_text.splitlines():
        cleaned = str(line or "").strip()
        if not cleaned:
            continue
        try:
            event = json.loads(cleaned)
        except Exception:
            continue
        if isinstance(event, dict):
            codex_events.append(event)
            msg = _release_review_extract_codex_event_text(event)
            if msg:
                message_texts.append(msg)
            err_text = str(event.get("message") or "").strip()
            if err_text and str(event.get("type") or "").strip().lower() == "error":
                event_errors.append(err_text)
            failed_error = event.get("error")
            if isinstance(failed_error, dict):
                failed_message = str(failed_error.get("message") or "").strip()
                if failed_message:
                    event_errors.append(failed_message)

    stream_disconnected = any(
        "stream disconnected before completion" in str(item or "").strip().lower()
        or "stream closed before response.completed" in str(item or "").strip().lower()
        for item in event_errors
    )
    if stream_disconnected:
        error_text = "codex_stream_disconnected"

    message_candidates: list[dict[str, Any]] = []
    for text in message_texts:
        message_candidates.extend(_release_review_extract_json_objects(text))
    stdout_candidates = _release_review_extract_json_objects(stdout_text)
    structured_candidates = _release_review_structured_result_candidates(message_candidates)
    if not structured_candidates:
        structured_candidates = _release_review_structured_result_candidates(stdout_candidates)
    if structured_candidates:
        parsed_result = _release_review_best_payload(structured_candidates[-1]) or structured_candidates[-1]
    elif message_candidates:
        parsed_result = _release_review_best_payload(message_candidates[-1]) or message_candidates[-1]
    else:
        parsed_result = _release_review_best_payload(message_texts + stdout_candidates + [stdout_text])

    raw_payload = {
        "command_summary": command_summary,
        "exit_code": codex_exit_code,
        "error": error_text,
        "event_count": len(codex_events),
        "events": codex_events,
    }
    _write_release_review_json(raw_result_path, raw_payload)
    _write_release_review_json(parsed_result_path, parsed_result if parsed_result else {})

    analysis_chain = {
        "trace_dir": _path_for_ui(root, trace_dir),
        "prompt_path": _path_for_ui(root, prompt_path),
        "stdout_path": _path_for_ui(root, stdout_path),
        "stderr_path": _path_for_ui(root, stderr_path),
        "report_path": _path_for_ui(root, parsed_result_path),
        "raw_result_path": _path_for_ui(root, raw_result_path),
        "prompt_text": prompt_text,
        "stdout_preview": _short_text(stdout_text, 2000),
        "stderr_preview": _short_text(stderr_text, 1600),
        "command_summary": command_summary,
        "codex_summary": {
            "exit_code": codex_exit_code,
            "event_count": len(codex_events),
            "duration_ms": max(0, finished_ms - started_ms),
        },
    }
    return {
        "ok": not error_text and bool(parsed_result),
        "error": error_text or ("codex_result_missing" if not parsed_result else ""),
        "analysis_chain": analysis_chain,
        "parsed_result": parsed_result,
    }


def _normalize_release_review_report(
    raw_result: dict[str, Any],
    *,
    agent: dict[str, Any] | None = None,
    target_version: str,
    current_workspace_ref: str,
    codex_error: str = "",
    allow_incomplete: bool = False,
) -> dict[str, Any]:
    raw = raw_result if isinstance(raw_result, dict) else {}
    source = _release_review_best_payload(raw) if raw else {}
    if not source and raw:
        source = raw
    agent_payload = agent if isinstance(agent, dict) else {}
    context = _release_review_agent_context(agent_payload) if agent_payload else {}
    warnings = _normalize_text_list(source.get("warnings") if isinstance(source, dict) else [], limit=180)
    if raw and source is not raw:
        warnings.append("已自动从嵌套输出中提取结构化发布报告。")
    if str(codex_error or "").strip().lower() == "codex_result_missing":
        warnings.append("Codex 未直接返回标准结构化 JSON，系统已根据上下文自动补齐报告字段。")

    full_capability_inventory = _normalize_text_list(
        source.get("full_capability_inventory")
        if isinstance(source, dict) and "full_capability_inventory" in source
        else (
            source.get("capability_inventory")
            if isinstance(source, dict)
            else []
        ),
        limit=220,
    )
    if not full_capability_inventory:
        full_capability_inventory = _ensure_first_person_list(
            context.get("full_capability_inventory"),
            "我当前可以：",
            limit=12,
            item_limit=220,
        )
        if full_capability_inventory:
            warnings.append("全量能力清单缺失，系统已根据 AGENTS.md 与工作区上下文自动补齐。")

    knowledge_scope = _short_text(
        _release_review_pick_text(source, "knowledge_scope", "knowledge", "scope")
        or str(context.get("knowledge_scope") or "").strip(),
        320,
    )
    if knowledge_scope and not _release_review_pick_text(source, "knowledge_scope", "knowledge", "scope"):
        warnings.append("知识范围缺失，系统已根据 AGENTS.md 自动补齐。")

    agent_skills = _normalize_text_list(
        source.get("agent_skills")
        if isinstance(source, dict) and "agent_skills" in source
        else (source.get("skills") if isinstance(source, dict) else []),
        limit=80,
    )
    if not agent_skills:
        agent_skills = _skills_list(context.get("agent_skills"))
        if agent_skills:
            warnings.append("Agent Skills 缺失，系统已根据工作区本地技能自动补齐。")

    applicable_scenarios = _normalize_text_list(
        source.get("applicable_scenarios")
        if isinstance(source, dict) and "applicable_scenarios" in source
        else (source.get("scenarios") if isinstance(source, dict) else []),
        limit=140,
    )
    if not applicable_scenarios:
        applicable_scenarios = _text_items(context.get("applicable_scenarios"), limit=6, item_limit=140)
        if applicable_scenarios:
            warnings.append("适用场景缺失，系统已根据 AGENTS.md 自动补齐。")

    first_person_summary = _ensure_first_person_text(
        _release_review_pick_text(
            source,
            "first_person_summary",
            "self_summary",
            "role_summary",
            "capability_summary",
            "summary",
        )
        or str(context.get("first_person_summary") or "").strip(),
        "我当前的核心能力是：",
        limit=320,
    )
    if not _release_review_pick_text(source, "first_person_summary", "self_summary", "role_summary", "capability_summary"):
        warnings.append("第一人称角色摘要缺失，系统已根据 AGENTS.md 自动补齐。")

    capability_delta = _normalize_text_list(
        source.get("capability_delta")
        if isinstance(source, dict) and "capability_delta" in source
        else (source.get("capability_changes") if isinstance(source, dict) else []),
        limit=280,
    )
    previous_release_version = _short_text(
        _release_review_pick_text(source, "previous_release_version", "latest_release_version", "base_release_version")
        or str(context.get("previous_release_version") or "").strip(),
        80,
    )
    if not previous_release_version:
        warnings.append("当前未找到上一正式发布版本，本次按首发基线评审处理。")
    if not capability_delta and not previous_release_version and full_capability_inventory:
        capability_delta = [f"我本次首发基线已包含：{item}" for item in full_capability_inventory[:3]]
    capability_delta = _ensure_first_person_list(
        capability_delta,
        "我本次主要补充了：",
        limit=8,
        item_limit=220,
    )
    risk_filter = _release_review_filter_risks(
        source.get("risk_list")
        if isinstance(source, dict) and "risk_list" in source
        else (source.get("risks") if isinstance(source, dict) else []),
    )
    risk_list = risk_filter["risk_list"]
    warnings.extend(risk_filter["warnings"])
    validation_evidence = _normalize_text_list(
        source.get("validation_evidence")
        if isinstance(source, dict) and "validation_evidence" in source
        else (source.get("evidence") if isinstance(source, dict) else []),
        limit=320,
    )
    validation_evidence = _ensure_first_person_list(validation_evidence, "我当前已确认的验证证据是：", limit=8, item_limit=240)

    change_summary = _ensure_first_person_text(
        _release_review_pick_text(source, "change_summary", "summary", "change_overview", "release_summary"),
        "我本次版本的主要变化是：",
        limit=1000,
    )
    if not change_summary:
        if capability_delta:
            change_summary = _short_text("我本次预发布的主要变化是：" + "；".join(capability_delta[:3]), 1000)
            warnings.append("变更摘要由 capability_delta 自动汇总生成。")
        elif risk_list:
            change_summary = _short_text("我当前仍识别到待确认风险：" + "；".join(risk_list[:2]), 1000)
            warnings.append("变更摘要由 risk_list 自动汇总生成。")
        elif validation_evidence:
            change_summary = _short_text("我当前已收集的验证证据包括：" + "；".join(validation_evidence[:2]), 1000)
            warnings.append("变更摘要由 validation_evidence 自动汇总生成。")
        else:
            change_summary = "我暂未能从 Codex 输出中提取结构化变更摘要，请人工查看分析链路中的 stdout / 报告文件。"
            warnings.append("未提取到结构化变更摘要，已填入人工复核提示。")

    recommendation = _release_review_normalize_recommendation(
        _release_review_pick_text(source, "release_recommendation", "recommendation", "decision", "review_decision")
    )
    if not recommendation:
        recommendation = "needs_more_validation"
        warnings.append("未提取到有效发布建议，系统已默认保守建议为 needs_more_validation。")
    if risk_filter["metadata_conflicts"]:
        if recommendation == "approve":
            recommendation = "needs_more_validation"
            warnings.append("检测到版本元数据冲突，本次发布建议已自动降级为 needs_more_validation。")
    elif risk_filter["demoted_count"] and not risk_list and recommendation == "reject":
        recommendation = "needs_more_validation"
        warnings.append("仅识别到可追溯性或工作区外告警，系统已将发布建议从 reject 降级为 needs_more_validation。")

    has_structured_content = bool(full_capability_inventory or capability_delta or risk_list or validation_evidence or raw)
    next_action_suggestion = _ensure_first_person_text(
        _release_review_pick_text(source, "next_action_suggestion", "next_action", "suggestion", "recommended_action")
        or _release_review_default_next_action(recommendation, has_structured_content=has_structured_content),
        "我建议下一步：",
        limit=320,
    )
    if not _release_review_pick_text(source, "next_action_suggestion", "next_action", "suggestion", "recommended_action"):
        warnings.append("未提取到下一步建议，系统已自动补齐。")

    report = {
        "target_version": _short_text(
            _release_review_pick_text(source, "target_version", "version", "proposed_version") or target_version,
            80,
        ),
        "current_workspace_ref": _short_text(
            _release_review_pick_text(source, "current_workspace_ref", "workspace_ref", "current_ref", "current_version")
            or current_workspace_ref,
            80,
        ),
        "previous_release_version": previous_release_version,
        "first_person_summary": first_person_summary,
        "what_i_can_do": _derive_what_i_can_do(first_person_summary, full_capability_inventory),
        "full_capability_inventory": full_capability_inventory,
        "knowledge_scope": knowledge_scope,
        "agent_skills": _skills_list(agent_skills),
        "applicable_scenarios": applicable_scenarios,
        "change_summary": change_summary,
        "capability_delta": capability_delta,
        "risk_list": risk_list,
        "validation_evidence": validation_evidence,
        "release_recommendation": _short_text(recommendation, 80),
        "version_notes": _short_text(change_summary, 320),
        "next_action_suggestion": next_action_suggestion,
        "warnings": [
            item
            for item in dict.fromkeys(
                [
                    _release_review_warning_text(item, limit=220)
                    for item in warnings
                    if str(item or "").strip()
                ]
            )
            if item
        ],
        "raw_result": raw,
    }
    missing = _release_review_missing_fields(report, RELEASE_REVIEW_REQUIRED_FIELDS)
    if missing and not allow_incomplete:
        raise TrainingCenterError(
            500,
            "release review report incomplete",
            "release_review_report_incomplete",
            {"missing_fields": missing},
        )
    return report


def _build_release_review_failure_report(
    raw_result: dict[str, Any],
    *,
    agent: dict[str, Any] | None = None,
    target_version: str,
    current_workspace_ref: str,
    codex_error: str = "",
    error_code: str = "",
    error_message: str = "",
    missing_fields: list[str] | None = None,
    metadata_conflicts: list[str] | None = None,
) -> dict[str, Any]:
    report = _normalize_release_review_report(
        raw_result,
        agent=agent,
        target_version=target_version,
        current_workspace_ref=current_workspace_ref,
        codex_error=codex_error,
        allow_incomplete=True,
    )
    warning_items = _normalize_text_list(report.get("warnings"), limit=220)
    missing = [str(item or "").strip() for item in (missing_fields or []) if str(item or "").strip()]
    conflicts = [str(item or "").strip() for item in (metadata_conflicts or []) if str(item or "").strip()]
    code = str(error_code or "").strip().lower()

    if conflicts:
        warning_items.extend([_release_review_warning_text("版本元数据冲突：" + item) for item in conflicts])
    if missing:
        warning_items.append(_release_review_warning_text("结构化报告仍缺少关键字段：" + " / ".join(missing)))
    if error_message:
        warning_items.append(_release_review_warning_text(error_message))

    report["target_version"] = _short_text(str(report.get("target_version") or "").strip() or target_version, 80)
    report["current_workspace_ref"] = _short_text(
        str(report.get("current_workspace_ref") or "").strip() or current_workspace_ref,
        80,
    )
    if not _release_review_field_present(report.get("change_summary")):
        if code == "release_review_metadata_conflict":
            report["change_summary"] = "我在进入发布评审前识别到版本元数据存在冲突，因此本次未继续执行正常发布报告生成。"
        elif missing:
            report["change_summary"] = "我已从当前链路中提取到部分结构化内容，但关键字段仍不完整。"
        else:
            report["change_summary"] = "我本次未能成功产出完整结构化发布报告，当前已保留失败排查所需的骨架信息。"
    if not _release_review_field_present(report.get("release_recommendation")):
        report["release_recommendation"] = "needs_more_validation"
    if not _release_review_field_present(report.get("next_action_suggestion")):
        if code == "release_review_metadata_conflict":
            report["next_action_suggestion"] = "我建议先修复 target_version / latest_release_version / released_versions 等版本元数据冲突，再重新进入发布评审。"
        elif missing:
            report["next_action_suggestion"] = "我建议先检查报告文件与 stdout，补齐缺失字段后再重新进入发布评审。"
        else:
            report["next_action_suggestion"] = "我建议先查看分析链路中的 stdout / stderr / 报告文件，定位失败原因后再重新进入发布评审。"
    if not isinstance(raw_result, dict):
        report["raw_result"] = {"raw_text": _short_text(str(raw_result or "").strip(), 4000)}
    else:
        report["raw_result"] = raw_result
    report["warnings"] = [
        item
        for item in dict.fromkeys(
            [
                _release_review_warning_text(item, limit=220)
                for item in warning_items
                if str(item or "").strip()
            ]
        )
        if item
    ]
    return report


def _describe_release_review_report_failure(
    exc: TrainingCenterError,
    *,
    codex_result: dict[str, Any] | None = None,
) -> str:
    code = str(getattr(exc, "code", "") or "").strip().lower()
    extra = getattr(exc, "extra", {}) if isinstance(getattr(exc, "extra", {}), dict) else {}
    codex_payload = codex_result if isinstance(codex_result, dict) else {}
    codex_error = str(codex_payload.get("error") or extra.get("reason") or "").strip().lower()

    if code == "release_review_report_incomplete":
        missing = [
            str(item or "").strip()
            for item in (extra.get("missing_fields") or [])
            if str(item or "").strip()
        ]
        if missing:
            return "结构化发布报告缺少关键字段（" + " / ".join(missing) + "）。请先检查分析链路中的报告文件与 stdout 输出，修正后点击“重新进入发布评审”。"
        return "结构化发布报告字段不完整。请先检查分析链路中的报告文件与 stdout 输出，修正后点击“重新进入发布评审”。"

    if code == "release_review_metadata_conflict":
        conflicts = [
            str(item or "").strip()
            for item in (extra.get("metadata_conflicts") or [])
            if str(item or "").strip()
        ]
        if conflicts:
            return "进入发布评审前检测到版本元数据冲突（" + " / ".join(conflicts[:3]) + "）。请先修复版本元数据后再重新进入发布评审。"
        return "进入发布评审前检测到版本元数据冲突。请先修复 target_version / latest_release_version / released_versions 等元数据后再重新进入发布评审。"

    if code == "release_review_report_failed":
        if codex_error == "codex_command_not_found":
            return "生成发布报告失败：当前环境未找到 codex 命令。请先确认服务端已安装并可执行 codex，然后点击“重新进入发布评审”。"
        if codex_error == "codex_exec_timeout":
            return "生成发布报告失败：Codex 执行超时。请先查看分析链路中的 stdout / stderr / trace 目录定位卡点，必要时缩小本次改动范围后重试。"
        if codex_error == "codex_stream_disconnected":
            return "生成发布报告失败：Codex 在流式返回过程中断线，任务未完成。请先检查目标工作区是否触发了冗长的会话恢复/技能编排链路，再重新进入发布评审。"
        if codex_error.startswith("codex_exec_failed_exit_"):
            exit_code = codex_error.rsplit("_", 1)[-1]
            return f"生成发布报告失败：Codex 执行异常退出（exit={exit_code}）。请先查看分析链路中的 stderr / stdout，修复工作区或提示词问题后重新进入发布评审。"
        if codex_error.startswith("codex_exec_exception:"):
            detail = str(codex_payload.get("error") or extra.get("reason") or "").strip()
            return "生成发布报告失败：调用 Codex 时发生异常" + (f"（{detail}）" if detail else "") + "。请先检查服务端日志与分析链路，再重新进入发布评审。"
        if codex_error == "codex_result_missing":
            return "生成发布报告失败：Codex 已执行，但没有产出可解析的结构化 JSON 报告。请先检查 stdout / 报告文件是否混入额外文本，修正后重新进入发布评审。"
        if codex_error:
            return "生成发布报告失败：" + codex_error + "。请先查看分析链路中的 stdout / stderr / 报告文件，定位原因后重新进入发布评审。"
        return "生成发布报告失败。请先查看分析链路中的 stdout / stderr / 报告文件，定位具体原因后点击“重新进入发布评审”。"

    return str(exc)


def _append_release_review_log(
    logs: list[dict[str, Any]],
    *,
    phase: str,
    status: str,
    message: str,
    path: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    logs.append(
        {
            "phase": str(phase or "").strip() or "unknown",
            "status": str(status or "").strip() or "pending",
            "message": _short_text(str(message or "").strip(), 400),
            "path": str(path or "").strip(),
            "details": details if isinstance(details, dict) else {},
            "ts": iso_ts(now_local()),
        }
    )


def _run_git_mutation(
    workspace: Path,
    args: list[str],
    *,
    timeout_s: int = 30,
) -> tuple[bool, str, str]:
    cmd = ["git", "-C", workspace.as_posix()] + [str(arg) for arg in args]
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_s,
        )
    except Exception as exc:
        return False, "", str(exc or "")
    return proc.returncode == 0, str(proc.stdout or ""), str(proc.stderr or "")


def _git_publish_identity_defaults(agent: dict[str, Any]) -> tuple[str, str]:
    token = safe_token(
        str(agent.get("agent_id") or agent.get("agent_name") or "workflow-release"),
        "workflow-release",
        80,
    )
    name = str(agent.get("agent_name") or token or "workflow-release").strip() or "workflow-release"
    email = f"{token or 'workflow-release'}@workflow.local"
    return _short_text(name, 120), _short_text(email, 160)


def _workspace_has_own_git_repo(workspace: Path) -> tuple[bool, str]:
    ok_root, root_out, _ = _run_git_readonly_verbose(
        workspace,
        ["rev-parse", "--show-toplevel"],
        timeout_s=12,
    )
    if not ok_root:
        return False, ""
    root_line = ""
    for line in str(root_out or "").splitlines():
        candidate = str(line or "").strip()
        if candidate:
            root_line = candidate
    if not root_line:
        return False, ""
    repo_root = Path(root_line).resolve(strict=False)
    workspace_root = workspace.resolve(strict=False)
    same_root = os.path.normcase(str(repo_root)) == os.path.normcase(str(workspace_root))
    return same_root, repo_root.as_posix()


def _ensure_workspace_git_ready_for_publish(
    cfg: AppConfig,
    *,
    workspace: Path,
    agent: dict[str, Any],
    execution_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    has_own_repo, detected_repo_root = _workspace_has_own_git_repo(workspace)
    repo_initialized = False
    if not has_own_repo:
        ok_init, init_out, init_err = _run_git_mutation(workspace, ["init"], timeout_s=30)
        if not ok_init:
            _append_release_review_log(
                execution_logs,
                phase="prepare",
                status="failed",
                message="自动初始化 Git 仓库失败",
                details={"stdout": _short_text(init_out, 300), "stderr": _short_text(init_err, 400)},
            )
            return {"ok": False, "error": "git_init_failed", "stdout": init_out, "stderr": init_err}
        repo_initialized = True
        _append_release_review_log(
            execution_logs,
            phase="prepare",
            status="done",
            message="当前 agent 工作区未绑定独立 Git 仓库，已自动执行 git init",
            details={
                "stdout": _short_text(init_out, 240),
                "detected_repo_root": detected_repo_root,
            },
        )

    if repo_initialized:
        desired_name, desired_email = _git_publish_identity_defaults(agent)
        ok_name, name_out, _ = _run_git_mutation(workspace, ["config", "--get", "user.name"], timeout_s=12)
        ok_email, email_out, _ = _run_git_mutation(workspace, ["config", "--get", "user.email"], timeout_s=12)
        current_name = str(name_out or "").strip() if ok_name else ""
        current_email = str(email_out or "").strip() if ok_email else ""
        configured_fields: list[str] = []
        if not current_name:
            set_name_ok, _, set_name_err = _run_git_mutation(
                workspace,
                ["config", "--local", "user.name", desired_name],
                timeout_s=12,
            )
            if not set_name_ok:
                _append_release_review_log(
                    execution_logs,
                    phase="prepare",
                    status="failed",
                    message="自动写入 Git 用户名失败",
                    details={"stderr": _short_text(set_name_err, 400)},
                )
                return {"ok": False, "error": "git_identity_config_failed", "stderr": set_name_err}
            configured_fields.append("user.name")
        if not current_email:
            set_email_ok, _, set_email_err = _run_git_mutation(
                workspace,
                ["config", "--local", "user.email", desired_email],
                timeout_s=12,
            )
            if not set_email_ok:
                _append_release_review_log(
                    execution_logs,
                    phase="prepare",
                    status="failed",
                    message="自动写入 Git 邮箱失败",
                    details={"stderr": _short_text(set_email_err, 400)},
                )
                return {"ok": False, "error": "git_identity_config_failed", "stderr": set_email_err}
            configured_fields.append("user.email")
        if configured_fields:
            _append_release_review_log(
                execution_logs,
                phase="prepare",
                status="done",
                message="已为自动初始化的 Git 仓库补齐本地提交身份",
                details={"configured_fields": configured_fields, "user_name": desired_name, "user_email": desired_email},
            )

    status_ok, _, status_err = _run_git_readonly_verbose(
        workspace,
        ["status", "--porcelain", "--untracked-files=normal"],
        timeout_s=12,
    )
    if not status_ok:
        _append_release_review_log(
            execution_logs,
            phase="prepare",
            status="failed",
            message="Git 仓库已就绪，但读取状态失败",
            details={"stderr": _short_text(status_err, 400)},
        )
        return {"ok": False, "error": "git_status_failed", "stderr": status_err}

    return {"ok": True, "repo_initialized": repo_initialized}


def _build_publish_release_note(
    *,
    agent: dict[str, Any],
    report: dict[str, Any],
    publish_version: str,
    review_comment: str,
) -> str:
    def note_first_person(value: Any, prefix: str, *, limit: int = 280) -> str:
        text = _short_text(str(value or "").strip(), limit)
        if not text:
            return ""
        if text.startswith(("我", "当前工作区", "本次发布", "本次版本")):
            return text
        return prefix + text

    workspace = Path(str(agent.get("workspace_path") or "")).resolve(strict=False)
    portrait = extract_agent_role_portrait(workspace / "AGENTS.md")
    skills = _skills_list(portrait.get("skills"))
    if not skills:
        skills = _skills_list(agent.get("skills_json"))
    if not skills:
        skills = _skills_list(agent.get("skills"))
    list_workspace_local_skills = globals().get("_list_workspace_local_skills")
    if not skills and callable(list_workspace_local_skills):
        try:
            skills = _skills_list(list_workspace_local_skills(workspace))
        except Exception:
            skills = []
    if not skills:
        skills = ["workflow"]
    capability_summary = str(
        report.get("first_person_summary")
        or portrait.get("capability_summary")
        or agent.get("capability_summary")
        or report.get("change_summary")
        or "见本次发布评审报告"
    ).strip()
    knowledge_scope = str(
        report.get("knowledge_scope")
        or portrait.get("knowledge_scope")
        or agent.get("knowledge_scope")
        or report.get("next_action_suggestion")
        or "参考当前角色知识范围"
    ).strip()
    applicable_scenarios = "；".join(_normalize_text_list(report.get("applicable_scenarios"), limit=120)) or str(
        portrait.get("applicable_scenarios")
        or agent.get("applicable_scenarios")
        or "角色发布评审与确认发布"
    ).strip()
    version_notes = str(report.get("change_summary") or review_comment or agent.get("version_notes") or publish_version).strip()
    what_i_can_do = _normalize_text_list(report.get("what_i_can_do"), limit=180)
    full_capability_inventory = _normalize_text_list(report.get("full_capability_inventory"), limit=180)
    capability_delta = _normalize_text_list(report.get("capability_delta"), limit=180)
    risk_list = _normalize_text_list(report.get("risk_list"), limit=180)
    evidence_list = _normalize_text_list(report.get("validation_evidence"), limit=220)
    lines = [
        f"发布版本: {publish_version}",
        f"第一人称摘要: {note_first_person(capability_summary, '我当前的核心能力是：')}",
        f"角色能力摘要: {note_first_person(capability_summary, '我当前的核心能力是：')}",
        f"角色知识范围: {note_first_person(knowledge_scope, '我当前覆盖的知识范围是：')}",
        "技能: " + ", ".join(skills[:12]),
        "技能明细:",
    ]
    lines.extend([f"- {item}" for item in skills[:12]])
    if what_i_can_do:
        lines.extend(["我当前能做什么:"])
        lines.extend([f"- {note_first_person(item, '我当前可以：', limit=180)}" for item in what_i_can_do[:5]])
    if full_capability_inventory:
        lines.extend(["全量能力清单:"])
        lines.extend([f"- {note_first_person(item, '我当前可以：', limit=180)}" for item in full_capability_inventory[:12]])
    lines.extend(
        [
            f"适用场景: {note_first_person(applicable_scenarios, '我当前适合用于：')}",
            f"版本说明: {note_first_person(version_notes, '我本次发布主要更新了：')}",
            "",
            "发布评审摘要:",
            f"- 工作区基线: {note_first_person(str(report.get('current_workspace_ref') or '').strip() or '-', '我当前工作区基线是：', limit=120)}",
            f"- 发布建议: {note_first_person(str(report.get('release_recommendation') or '').strip() or '-', '我当前给出的发布建议是：', limit=120)}",
        ]
    )
    if capability_delta:
        lines.append("- 能力变化: 我本次主要补充/调整了：" + "；".join(capability_delta[:5]))
    if risk_list:
        lines.append("- 风险提示: 我当前识别到的风险包括：" + "；".join(risk_list[:5]))
    if evidence_list:
        lines.append("- 验证证据: 我当前已确认的验证证据包括：" + "；".join(evidence_list[:5]))
    if review_comment:
        lines.append("- 审核意见: " + note_first_person(review_comment, "我本次发布收到的审核意见是：", limit=220))
    next_action = str(report.get("next_action_suggestion") or "").strip()
    if next_action:
        lines.append("- 下一步建议: " + note_first_person(next_action, "我建议下一步：", limit=220))
    return "\n".join(lines).strip() + "\n"


def _bind_release_profile_after_publish(
    cfg: AppConfig,
    *,
    agent_id: str,
    publish_version: str,
    review_id: str,
    analysis_chain: dict[str, Any],
    public_profile_markdown_path: str,
    capability_snapshot_json_path: str,
) -> None:
    source_agent_id = safe_token(str(agent_id or ""), "", 120)
    if not source_agent_id:
        return
    release_row: dict[str, Any] | None = None
    conn = connect_db(cfg.root)
    try:
        row = conn.execute(
            """
            SELECT release_id,version_label,released_at
            FROM agent_release_history
            WHERE agent_id=?
              AND version_label=?
              AND COALESCE(classification,'normal_commit')='release'
            ORDER BY released_at DESC, created_at DESC
            LIMIT 1
            """,
            (source_agent_id, str(publish_version or "").strip()),
        ).fetchone()
        if row is not None:
            release_row = {name: row[name] for name in row.keys()}
            conn.execute(
                """
                UPDATE agent_release_history
                SET release_source_ref=?,
                    public_profile_ref=?,
                    capability_snapshot_ref=?
                WHERE release_id=?
                """,
                (
                    str((analysis_chain or {}).get("report_path") or "").strip(),
                    str(public_profile_markdown_path or "").strip(),
                    str(capability_snapshot_json_path or "").strip(),
                    str(row["release_id"] or "").strip(),
                ),
            )
            conn.execute(
                """
                UPDATE agent_registry
                SET active_role_profile_release_id=?,
                    active_role_profile_ref=?,
                    updated_at=?
                WHERE agent_id=?
                """,
                (
                    str(row["release_id"] or "").strip(),
                    str(public_profile_markdown_path or capability_snapshot_json_path or "").strip(),
                    iso_ts(now_local()),
                    source_agent_id,
                ),
            )
            conn.commit()
    finally:
        conn.close()
    if release_row is not None:
        append_training_center_audit(
            cfg.root,
            action="release_profile_bound",
            operator="system",
            target_id=source_agent_id,
            detail={
                "review_id": review_id,
                "release_id": str(release_row.get("release_id") or "").strip(),
                "publish_version": str(publish_version or "").strip(),
                "public_profile_ref": str(public_profile_markdown_path or "").strip(),
                "capability_snapshot_ref": str(capability_snapshot_json_path or "").strip(),
            },
        )


def _verify_release_note_before_tag(
    workspace: Path,
    publish_version: str,
    release_note_text: str,
) -> tuple[bool, dict[str, Any], str]:
    parser = globals().get("parse_release_portrait_fields")
    validator = globals().get("validate_release_portrait_fields")
    skills_parser = globals().get("_skills_list")
    list_workspace_local_skills = globals().get("_list_workspace_local_skills")
    if not callable(parser) or not callable(validator):
        return True, {}, ""
    try:
        parsed = parser(str(release_note_text or ""))
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    parsed_skills = skills_parser(parsed.get("skills")) if callable(skills_parser) else []
    note_text = str(release_note_text or "")
    if (
        not parsed_skills
        and callable(list_workspace_local_skills)
        and "发布版本:" in note_text
        and "技能:" in note_text
    ):
        try:
            fallback_skills = list_workspace_local_skills(workspace)
        except Exception:
            fallback_skills = []
        parsed_skills = skills_parser(fallback_skills) if callable(skills_parser) else []
        if parsed_skills:
            parsed["skills"] = parsed_skills
    try:
        release_valid, invalid_reasons = validator(parsed)
    except Exception:
        release_valid, invalid_reasons = False, ["release_note_validate_failed"]
    reason_list = [str(item or "").strip() for item in invalid_reasons if str(item or "").strip()]
    payload = {
        "version_label": str(publish_version or "").strip(),
        "capability_summary": str(parsed.get("capability_summary") or "").strip(),
        "knowledge_scope": str(parsed.get("knowledge_scope") or "").strip(),
        "skills_json": _json_dumps_text(parsed_skills, "[]"),
        "applicable_scenarios": str(parsed.get("applicable_scenarios") or "").strip(),
        "version_notes": str(parsed.get("version_notes") or "").strip(),
        "release_valid": bool(release_valid),
        "invalid_reasons_json": _json_dumps_text(reason_list, "[]"),
        "classification": "release" if release_valid else "normal_commit",
        "raw_notes": _short_text(note_text, 4000),
    }
    if release_valid:
        return True, payload, ""
    return False, payload, ",".join(reason_list) or "release_note_invalid"


def _verify_published_release(workspace: Path, publish_version: str) -> tuple[bool, dict[str, Any], str]:
    _, _, rows = _parse_git_release_rows(workspace, limit=120)
    for row in rows:
        version_label = str(row.get("version_label") or "").strip()
        if version_label != str(publish_version or "").strip():
            continue
        if str(row.get("classification") or "normal_commit").strip().lower() != "release":
            reasons = _json_load_list(row.get("invalid_reasons_json"))
            return False, row, ",".join([str(item or "").strip() for item in reasons if str(item or "").strip()]) or "release_note_invalid"
        return True, row, ""
    return False, {}, "release_version_not_found_after_publish"


def _update_agent_after_publish(
    cfg: AppConfig,
    *,
    agent_id: str,
    publish_version: str,
    released_at: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, agent_id)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": agent_id})
        training_gate_state = derive_training_gate_state(
            lifecycle_state="released",
            current_version=publish_version,
            latest_release_version=publish_version,
            parent_agent_id=str(agent.get("parent_agent_id") or "").strip(),
            preferred=agent.get("training_gate_state"),
        )
        conn.execute(
            """
            UPDATE agent_registry
            SET current_version=?,
                latest_release_version=?,
                bound_release_version=?,
                lifecycle_state='released',
                training_gate_state=?,
                last_release_at=?,
                updated_at=?
            WHERE agent_id=?
            """,
            (
                publish_version,
                publish_version,
                publish_version,
                training_gate_state,
                released_at,
                iso_ts(now_local()),
                agent_id,
            ),
        )
        conn.commit()
        return _resolve_training_agent(conn, agent_id) or {}
    finally:
        conn.close()


def _insert_release_evaluation_shadow_record(
    root: Path,
    *,
    agent_id: str,
    target_version: str,
    decision: str,
    reviewer: str,
    summary: str,
) -> str:
    evaluation_id = training_release_evaluation_id()
    conn = connect_db(root)
    try:
        conn.execute(
            """
            INSERT INTO agent_release_evaluation (
                evaluation_id,agent_id,target_version,decision,reviewer,summary,created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                evaluation_id,
                agent_id,
                target_version,
                decision,
                reviewer,
                _short_text(summary, 1000),
                iso_ts(now_local()),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return evaluation_id


def _latest_release_review_row(conn: sqlite3.Connection, agent_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT
            review_id,agent_id,target_version,current_workspace_ref,release_review_state,prompt_version,
            analysis_chain_json,report_json,report_error,review_decision,reviewer,review_comment,reviewed_at,
            publish_version,publish_status,publish_error,execution_log_json,fallback_json,
            public_profile_markdown_path,capability_snapshot_json_path,created_at,updated_at
        FROM agent_release_review
        WHERE agent_id=?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (agent_id,),
    ).fetchone()
    if row is None:
        return None
    return {name: row[name] for name in row.keys()}


def _update_release_review_row(root: Path, review_id: str, fields: dict[str, Any]) -> None:
    payload = {str(key): value for key, value in (fields or {}).items() if str(key)}
    if not payload:
        return
    payload["updated_at"] = iso_ts(now_local())
    params: list[Any] = []
    assignments: list[str] = []
    json_defaults = {
        "analysis_chain_json": "{}",
        "report_json": "{}",
        "execution_log_json": "[]",
        "fallback_json": "{}",
    }
    for key, value in payload.items():
        assignments.append(f"{key}=?")
        if key in json_defaults:
            params.append(_json_dumps_text(value, json_defaults[key]))
        else:
            params.append(str(value or ""))
    params.append(review_id)
    conn = connect_db(root)
    try:
        conn.execute(
            f"UPDATE agent_release_review SET {', '.join(assignments)} WHERE review_id=?",
            tuple(params),
        )
        conn.commit()
    finally:
        conn.close()


def _release_review_payload(agent: dict[str, Any], row: dict[str, Any] | None) -> dict[str, Any]:
    lifecycle_state = normalize_lifecycle_state(agent.get("lifecycle_state"))
    current_state = str((row or {}).get("release_review_state") or "idle").strip() or "idle"
    if current_state not in RELEASE_REVIEW_STATES:
        current_state = "idle"
    analysis_chain = _json_load_dict((row or {}).get("analysis_chain_json"))
    report = _json_load_dict((row or {}).get("report_json"))
    execution_logs = _json_load_list((row or {}).get("execution_log_json"))
    fallback = _json_load_dict((row or {}).get("fallback_json"))
    review_decision = str((row or {}).get("review_decision") or "").strip()
    publish_status = str((row or {}).get("publish_status") or "").strip()
    report_error_code = str(analysis_chain.get("report_error_code") or "").strip()
    report_missing_fields = [
        str(item or "").strip()
        for item in (analysis_chain.get("report_missing_fields") or [])
        if str(item or "").strip()
    ] if isinstance(analysis_chain.get("report_missing_fields"), list) else []
    payload = {
        "review_id": str((row or {}).get("review_id") or "").strip(),
        "agent_id": str(agent.get("agent_id") or "").strip(),
        "agent_name": str(agent.get("agent_name") or "").strip(),
        "release_review_state": current_state,
        "target_version": str((row or {}).get("target_version") or "").strip(),
        "current_workspace_ref": str((row or {}).get("current_workspace_ref") or "").strip(),
        "prompt_version": str((row or {}).get("prompt_version") or "").strip(),
        "analysis_chain": analysis_chain,
        "report": report,
        "report_error": str((row or {}).get("report_error") or "").strip(),
        "report_error_code": report_error_code,
        "report_missing_fields": report_missing_fields,
        "required_report_fields": list(RELEASE_REVIEW_REQUIRED_FIELDS),
        "review_decision": review_decision,
        "reviewer": str((row or {}).get("reviewer") or "").strip(),
        "review_comment": str((row or {}).get("review_comment") or "").strip(),
        "reviewed_at": str((row or {}).get("reviewed_at") or "").strip(),
        "publish_version": str((row or {}).get("publish_version") or "").strip(),
        "publish_status": publish_status,
        "publish_error": str((row or {}).get("publish_error") or "").strip(),
        "execution_logs": execution_logs,
        "fallback": fallback,
        "public_profile_markdown_path": str((row or {}).get("public_profile_markdown_path") or "").strip(),
        "capability_snapshot_json_path": str((row or {}).get("capability_snapshot_json_path") or "").strip(),
        "created_at": str((row or {}).get("created_at") or "").strip(),
        "updated_at": str((row or {}).get("updated_at") or "").strip(),
        "can_enter": _can_enter_release_review(lifecycle_state, current_state),
        "can_discard": _can_discard_release_review(lifecycle_state, current_state, str((row or {}).get("review_id") or "").strip()),
        "can_review": current_state == "report_ready",
        "can_confirm": _can_confirm_release_review(lifecycle_state, current_state, review_decision),
        "publish_succeeded": publish_status == "success",
        "lifecycle_state": lifecycle_state,
    }
    return payload

def _list_agent_release_labels(conn: sqlite3.Connection, agent_id: str) -> list[str]:
    rows = conn.execute(
        """
        SELECT version_label
        FROM agent_release_history
        WHERE agent_id=?
          AND COALESCE(classification,'normal_commit')='release'
        ORDER BY released_at DESC, created_at DESC
        """,
        (agent_id,),
    ).fetchall()
    return [str(row["version_label"] or "").strip() for row in rows if str(row["version_label"] or "").strip()]


def _switch_workspace_to_released_version(workspace_path: Path, version_label: str) -> None:
    target = str(version_label or "").strip()
    if not target:
        raise TrainingCenterError(400, "version_label required", "version_label_required")
    workspace = workspace_path.resolve(strict=False)
    if not workspace.exists() or not workspace.is_dir():
        raise TrainingCenterError(
            409,
            f"workspace missing: {workspace.as_posix()}",
            "workspace_missing",
            {"workspace_path": workspace.as_posix()},
        )
    ok, _ = _run_git_readonly(workspace, ["rev-parse", "--is-inside-work-tree"])
    if not ok:
        raise TrainingCenterError(
            409,
            "workspace git unavailable",
            "git_unavailable",
            {"workspace_path": workspace.as_posix()},
        )

    switch_cmd = [
        "git",
        "-C",
        workspace.as_posix(),
        "checkout",
        "-f",
        target,
        "--",
        ".",
    ]
    clean_cmd = ["git", "-C", workspace.as_posix(), "clean", "-fd"]
    for cmd in (switch_cmd, clean_cmd):
        try:
            proc = subprocess.run(
                cmd,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=30,
            )
        except Exception as exc:  # pragma: no cover - subprocess failure branch
            raise TrainingCenterError(
                500,
                f"switch workspace failed: {exc}",
                "workspace_overwrite_failed",
                {"workspace_path": workspace.as_posix(), "version_label": target},
            ) from exc
        if proc.returncode != 0:
            raise TrainingCenterError(
                500,
                "switch workspace failed",
                "workspace_overwrite_failed",
                {
                    "workspace_path": workspace.as_posix(),
                    "version_label": target,
                    "stderr": str(proc.stderr or "").strip(),
                },
            )


def switch_training_agent_release(
    cfg: AppConfig,
    *,
    agent_id: str,
    version_label: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    target_version = str(version_label or "").strip()
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    if not target_version:
        raise TrainingCenterError(400, "version_label required", "version_label_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)

    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        releases = _list_agent_release_labels(conn, source_agent_id)
    finally:
        conn.close()

    if target_version not in set(releases):
        raise TrainingCenterError(
            409,
            "仅支持已发布版本",
            "version_not_released",
            {"agent_id": source_agent_id, "version_label": target_version, "released_versions": releases[:80]},
        )

    current_version = str(agent.get("current_version") or "").strip()
    latest_release_version = (
        str(agent.get("latest_release_version") or "").strip()
        or (releases[0] if releases else "")
    )
    parent_agent_id = str(agent.get("parent_agent_id") or "").strip()
    if current_version != target_version:
        _switch_workspace_to_released_version(Path(str(agent.get("workspace_path") or "")), target_version)

    training_gate_state = derive_training_gate_state(
        lifecycle_state="released",
        current_version=target_version,
        latest_release_version=latest_release_version,
        parent_agent_id=parent_agent_id,
    )
    ts = iso_ts(now_local())
    conn = connect_db(cfg.root)
    try:
        conn.execute(
            """
            UPDATE agent_registry
            SET current_version=?,
                bound_release_version=?,
                lifecycle_state='released',
                training_gate_state=?,
                updated_at=?
            WHERE agent_id=?
            """,
            (target_version, target_version, training_gate_state, ts, source_agent_id),
        )
        conn.commit()
        updated = _resolve_training_agent(conn, source_agent_id) or {}
    finally:
        conn.close()

    audit_id = append_training_center_audit(
        cfg.root,
        action="switch_release",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "mode": "overwrite_workspace",
            "from_version": current_version,
            "to_version": target_version,
            "latest_release_version": latest_release_version,
            "training_gate_state": training_gate_state,
        },
    )
    return {
        "agent_id": source_agent_id,
        "current_version": target_version,
        "bound_release_version": target_version,
        "latest_release_version": latest_release_version,
        "lifecycle_state": "released",
        "training_gate_state": training_gate_state,
        "frozen": training_gate_state == "frozen_switched",
        "audit_id": audit_id,
        "agent": updated,
    }


def clone_training_agent_from_current(
    cfg: AppConfig,
    *,
    agent_id: str,
    new_agent_name: str,
    operator: str,
) -> dict[str, Any]:
    root = cfg.agent_search_root
    if root is None:
        raise TrainingCenterError(
            409,
            "agent_search_root 未设置",
            "agent_search_root_not_ready",
    )
    source_agent_key = safe_token(str(agent_id or ""), "", 120)
    clone_agent_name = safe_token(str(new_agent_name or ""), "", 80).strip("-._:")
    clone_agent_id = safe_token(clone_agent_name, clone_agent_name, 120).strip("-._:")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)
    if not source_agent_key:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    if not clone_agent_name:
        raise TrainingCenterError(400, "new_agent_name required", "new_agent_name_required")
    if not clone_agent_id:
        raise TrainingCenterError(400, "new_agent_name invalid", "new_agent_name_invalid")

    sync_training_agent_registry(cfg)
    conn = connect_db(cfg.root)
    try:
        source = _resolve_training_agent(conn, source_agent_key)
        if source is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": source_agent_key})
        source_agent_id = str(source.get("agent_id") or "").strip()
        name_exists = conn.execute(
            "SELECT agent_id FROM agent_registry WHERE agent_name=? COLLATE NOCASE LIMIT 1",
            (clone_agent_name,),
        ).fetchone()
        if name_exists is not None:
            raise TrainingCenterError(
                409,
                "new_agent_name already exists",
                "agent_name_conflict",
                {"new_agent_name": clone_agent_name},
            )
        exists = conn.execute(
            "SELECT 1 AS ok FROM agent_registry WHERE agent_id=? LIMIT 1",
            (clone_agent_id,),
        ).fetchone()
        if exists is not None:
            raise TrainingCenterError(
                409,
                "new_agent_id already exists",
                "agent_id_conflict",
                {"new_agent_id": clone_agent_id},
            )
    finally:
        conn.close()

    source_workspace = Path(str(source.get("workspace_path") or "")).resolve(strict=False)
    if not source_workspace.exists() or not source_workspace.is_dir():
        raise TrainingCenterError(
            409,
            "source workspace missing",
            "workspace_missing",
            {"workspace_path": source_workspace.as_posix()},
        )
    clone_workspace = (root / clone_agent_id).resolve(strict=False)
    if not path_in_scope(clone_workspace, root.resolve(strict=False)):
        raise TrainingCenterError(
            409,
            "clone workspace out of scope",
            "workspace_out_of_scope",
            {"workspace_path": clone_workspace.as_posix()},
        )
    if clone_workspace.exists():
        raise TrainingCenterError(
            409,
            "clone workspace already exists",
            "agent_id_conflict",
            {"new_agent_id": clone_agent_id},
        )
    try:
        shutil.copytree(source_workspace, clone_workspace)
    except Exception as exc:  # pragma: no cover - copy failure branch
        raise TrainingCenterError(
            500,
            f"clone workspace failed: {exc}",
            "clone_workspace_failed",
            {"source": source_workspace.as_posix(), "target": clone_workspace.as_posix()},
        ) from exc

    sync_training_agent_registry(cfg)
    ts = iso_ts(now_local())
    source_current_version = str(source.get("current_version") or "").strip()
    source_bound_version = str(source.get("bound_release_version") or "").strip()
    clone_base_version = source_current_version or source_bound_version
    conn = connect_db(cfg.root)
    try:
        conn.execute(
            """
            UPDATE agent_registry
            SET agent_name=?,
                parent_agent_id=?,
                current_version=CASE WHEN ?<>'' THEN ? ELSE current_version END,
                latest_release_version=CASE WHEN ?<>'' THEN ? ELSE latest_release_version END,
                bound_release_version=CASE WHEN ?<>'' THEN ? ELSE bound_release_version END,
                lifecycle_state='released',
                training_gate_state='trainable',
                updated_at=?
            WHERE agent_id=?
            """,
            (
                clone_agent_name,
                source_agent_id,
                clone_base_version,
                clone_base_version,
                clone_base_version,
                clone_base_version,
                clone_base_version,
                clone_base_version,
                ts,
                clone_agent_id,
            ),
        )
        conn.commit()
        cloned = _resolve_training_agent(conn, clone_agent_id) or {}
    finally:
        conn.close()

    sync_training_agent_registry(cfg)
    audit_id = append_training_center_audit(
        cfg.root,
        action="clone_agent",
        operator=operator_text,
        target_id=clone_agent_id,
        detail={
            "clone_agent_id_generated": True,
            "source_agent_id": source_agent_id,
            "source_workspace": source_workspace.as_posix(),
            "clone_workspace": clone_workspace.as_posix(),
            "clone_agent_name": clone_agent_name,
            "clone_base_version": clone_base_version,
        },
    )
    return {
        "agent_id": clone_agent_id,
        "agent_name": str(cloned.get("agent_name") or clone_agent_name or clone_agent_id),
        "workspace_path": clone_workspace.as_posix(),
        "parent_agent_id": source_agent_id,
        "current_version": str(cloned.get("current_version") or clone_base_version),
        "latest_release_version": str(cloned.get("latest_release_version") or clone_base_version),
        "bound_release_version": str(cloned.get("bound_release_version") or clone_base_version),
        "lifecycle_state": normalize_lifecycle_state(cloned.get("lifecycle_state")),
        "training_gate_state": normalize_training_gate_state(cloned.get("training_gate_state")),
        "audit_id": audit_id,
        "agent": cloned,
    }


def discard_agent_pre_release(
    cfg: AppConfig,
    *,
    agent_id: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)

    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        lifecycle_state = normalize_lifecycle_state(agent.get("lifecycle_state"))
        release_labels = _list_agent_release_labels(conn, source_agent_id)
    finally:
        conn.close()

    if lifecycle_state != "pre_release":
        return {
            "agent_id": source_agent_id,
            "lifecycle_state": lifecycle_state,
            "training_gate_state": normalize_training_gate_state(agent.get("training_gate_state")),
            "discarded": False,
            "message": "not_in_pre_release",
            "code": "not_in_pre_release",
        }
    if not release_labels:
        raise TrainingCenterError(
            409,
            "discard requires at least one released version",
            "no_released_version_to_discard",
            {"agent_id": source_agent_id},
        )

    current_version = str(agent.get("current_version") or "").strip()
    latest_release_version = str(agent.get("latest_release_version") or "").strip()
    parent_agent_id = str(agent.get("parent_agent_id") or "").strip()
    bound_release_version = str(agent.get("bound_release_version") or "").strip()
    release_set = set(release_labels)
    target_release_version = bound_release_version
    if release_labels:
        if not target_release_version or target_release_version not in release_set:
            target_release_version = latest_release_version or release_labels[0]
    if target_release_version and target_release_version != current_version and target_release_version in release_set:
        _switch_workspace_to_released_version(
            Path(str(agent.get("workspace_path") or "")),
            target_release_version,
        )

    final_version = target_release_version or current_version
    training_gate_state = derive_training_gate_state(
        lifecycle_state="released",
        current_version=final_version,
        latest_release_version=latest_release_version,
        parent_agent_id=parent_agent_id,
        preferred=agent.get("training_gate_state"),
    )
    ts = iso_ts(now_local())
    conn = connect_db(cfg.root)
    try:
        conn.execute(
            """
            UPDATE agent_registry
            SET current_version=CASE WHEN ?<>'' THEN ? ELSE current_version END,
                bound_release_version=CASE WHEN ?<>'' THEN ? ELSE bound_release_version END,
                lifecycle_state='released',
                training_gate_state=?,
                updated_at=?
            WHERE agent_id=?
            """,
            (
                final_version,
                final_version,
                final_version,
                final_version,
                training_gate_state,
                ts,
                source_agent_id,
            ),
        )
        conn.commit()
        updated = _resolve_training_agent(conn, source_agent_id) or {}
    finally:
        conn.close()

    audit_id = append_training_center_audit(
        cfg.root,
        action="discard_pre_release",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "from_version": current_version,
            "to_version": final_version,
            "bound_release_version": bound_release_version,
            "latest_release_version": latest_release_version,
        },
    )
    return {
        "agent_id": source_agent_id,
        "discarded": True,
        "current_version": final_version,
        "bound_release_version": final_version,
        "lifecycle_state": "released",
        "training_gate_state": training_gate_state,
        "audit_id": audit_id,
        "agent": updated,
    }


def submit_manual_release_evaluation(
    cfg: AppConfig,
    *,
    agent_id: str,
    decision: str,
    reviewer: str,
    summary: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    decision_text = str(decision or "").strip().lower()
    if decision_text not in {"approve", "reject_continue_training", "reject_discard"}:
        raise TrainingCenterError(
            400,
            "decision invalid",
            "decision_invalid",
            {"allowed": ["approve", "reject_continue_training", "reject_discard"]},
        )
    reviewer_text = safe_token(str(reviewer or ""), "", 80)
    if not reviewer_text:
        raise TrainingCenterError(400, "reviewer required", "reviewer_required")
    summary_text = str(summary or "").strip()
    operator_text = safe_token(str(operator or reviewer_text or "web-user"), "web-user", 80)

    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        lifecycle_state = normalize_lifecycle_state(agent.get("lifecycle_state"))
        release_labels = _list_agent_release_labels(conn, source_agent_id)
        if lifecycle_state != "pre_release":
            raise TrainingCenterError(
                409,
                "agent not in pre_release",
                "not_in_pre_release",
                {"agent_id": source_agent_id, "lifecycle_state": lifecycle_state},
            )
        if decision_text == "reject_discard" and not release_labels:
            raise TrainingCenterError(
                409,
                "reject_discard requires at least one released version",
                "no_released_version_to_discard",
                {"agent_id": source_agent_id},
            )

        evaluation_id = training_release_evaluation_id()
        ts = iso_ts(now_local())
        target_version = str(agent.get("current_version") or "").strip()
        conn.execute(
            """
            INSERT INTO agent_release_evaluation (
                evaluation_id,agent_id,target_version,decision,reviewer,summary,created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                evaluation_id,
                source_agent_id,
                target_version,
                decision_text,
                reviewer_text,
                _short_text(summary_text, 1000),
                ts,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    decision_result: dict[str, Any] = {}
    if decision_text == "approve":
        latest_release_version = str(agent.get("latest_release_version") or "").strip()
        parent_agent_id = str(agent.get("parent_agent_id") or "").strip()
        current_version = str(agent.get("current_version") or "").strip()
        bound_release_version = str(agent.get("bound_release_version") or "").strip() or current_version
        training_gate_state = derive_training_gate_state(
            lifecycle_state="released",
            current_version=current_version,
            latest_release_version=latest_release_version,
            parent_agent_id=parent_agent_id,
            preferred=agent.get("training_gate_state"),
        )
        ts = iso_ts(now_local())
        conn = connect_db(cfg.root)
        try:
            conn.execute(
                """
                UPDATE agent_registry
                SET lifecycle_state='released',
                    bound_release_version=CASE WHEN ?<>'' THEN ? ELSE bound_release_version END,
                    training_gate_state=?,
                    updated_at=?
                WHERE agent_id=?
                """,
                (
                    bound_release_version,
                    bound_release_version,
                    training_gate_state,
                    ts,
                    source_agent_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        decision_result = {
            "decision_action": "approved_to_released",
            "lifecycle_state": "released",
            "training_gate_state": training_gate_state,
        }
    elif decision_text == "reject_discard":
        decision_result = {
            "decision_action": "rejected_and_discarded",
            "discard_result": discard_agent_pre_release(
                cfg,
                agent_id=source_agent_id,
                operator=operator_text,
            ),
        }
    else:
        decision_result = {
            "decision_action": "rejected_continue_training",
            "lifecycle_state": "pre_release",
            "training_gate_state": normalize_training_gate_state(agent.get("training_gate_state")),
        }

    conn = connect_db(cfg.root)
    try:
        updated = _resolve_training_agent(conn, source_agent_id) or {}
    finally:
        conn.close()

    audit_id = append_training_center_audit(
        cfg.root,
        action="manual_release_evaluation",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "evaluation_id": evaluation_id,
            "decision": decision_text,
            "reviewer": reviewer_text,
            "summary": _short_text(summary_text, 180),
            "decision_action": decision_result.get("decision_action"),
        },
    )
    return {
        "evaluation_id": evaluation_id,
        "agent_id": source_agent_id,
        "target_version": str(agent.get("current_version") or ""),
        "decision": decision_text,
        "reviewer": reviewer_text,
        "summary": summary_text,
        "audit_id": audit_id,
        "decision_result": decision_result,
        "agent": updated,
    }


def get_training_agent_release_review(
    root: Path,
    agent_id: str,
) -> dict[str, Any]:
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    conn = connect_db(root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        row = _latest_release_review_row(conn, source_agent_id)
    finally:
        conn.close()
    return {"review": _release_review_payload(agent, row)}


def enter_training_agent_release_review(
    cfg: AppConfig,
    *,
    agent_id: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)
    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        lifecycle_state = normalize_lifecycle_state(agent.get("lifecycle_state"))
        if lifecycle_state != "pre_release":
            raise TrainingCenterError(
                409,
                "agent not in pre_release",
                "not_in_pre_release",
                {"agent_id": source_agent_id, "lifecycle_state": lifecycle_state},
            )
        latest_row = _latest_release_review_row(conn, source_agent_id)
        latest_state = str((latest_row or {}).get("release_review_state") or "idle").strip() or "idle"
        if not _can_enter_release_review(lifecycle_state, latest_state):
            raise TrainingCenterError(
                409,
                "release review already active",
                "release_review_already_active",
                {"agent_id": source_agent_id, "release_review_state": latest_state},
            )
        release_labels = _list_agent_release_labels(conn, source_agent_id)
    finally:
        conn.close()

    workspace_path = Path(str(agent.get("workspace_path") or "")).resolve(strict=False)
    if not workspace_path.exists() or not workspace_path.is_dir():
        raise TrainingCenterError(
            409,
            "workspace missing",
            "workspace_missing",
            {"workspace_path": workspace_path.as_posix()},
        )
    current_workspace_ref = _workspace_current_ref(workspace_path) or str(agent.get("current_version") or "").strip()
    review_id = training_release_review_id()
    created_at = iso_ts(now_local())
    target_version = _next_release_version_label(release_labels)
    trace_dir = _release_review_trace_dir(cfg.root, str(agent.get("agent_name") or source_agent_id), review_id)
    conn = connect_db(cfg.root)
    try:
        conn.execute(
            """
            INSERT INTO agent_release_review (
                review_id,agent_id,target_version,current_workspace_ref,release_review_state,prompt_version,
                analysis_chain_json,report_json,report_error,review_decision,reviewer,review_comment,reviewed_at,
                publish_version,publish_status,publish_error,execution_log_json,fallback_json,
                public_profile_markdown_path,capability_snapshot_json_path,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                review_id,
                source_agent_id,
                target_version,
                current_workspace_ref,
                "report_generating",
                RELEASE_REVIEW_PROMPT_VERSION,
                "{}",
                "{}",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "[]",
                "{}",
                "",
                "",
                created_at,
                created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    enter_audit_id = append_training_center_audit(
        cfg.root,
        action="release_review_enter",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "review_id": review_id,
            "target_version": target_version,
            "current_workspace_ref": current_workspace_ref,
            "prompt_version": RELEASE_REVIEW_PROMPT_VERSION,
        },
    )

    metadata_conflicts = _release_review_metadata_conflicts(
        agent=agent,
        target_version=target_version,
        released_versions=release_labels,
    )
    if metadata_conflicts:
        metadata_exc = TrainingCenterError(
            409,
            "release review metadata conflict",
            "release_review_metadata_conflict",
            {"metadata_conflicts": metadata_conflicts},
        )
        report_error = _describe_release_review_report_failure(metadata_exc)
        failure_report = _build_release_review_failure_report(
            {"metadata_conflicts": metadata_conflicts},
            agent=agent,
            target_version=target_version,
            current_workspace_ref=current_workspace_ref,
            codex_error="metadata_conflict",
            error_code=metadata_exc.code,
            error_message=report_error,
            metadata_conflicts=metadata_conflicts,
        )
        _write_release_review_json(trace_dir / "parsed-result.json", failure_report)
        analysis_chain = {
            "trace_dir": _path_for_ui(cfg.root, trace_dir),
            "report_path": _path_for_ui(cfg.root, trace_dir / "parsed-result.json"),
            "prompt_version": RELEASE_REVIEW_PROMPT_VERSION,
            "error": "metadata_conflict",
            "report_error_code": metadata_exc.code,
            "report_missing_fields": [],
            "metadata_conflicts": metadata_conflicts,
        }
        _update_release_review_row(
            cfg.root,
            review_id,
            {
                "release_review_state": "report_failed",
                "analysis_chain_json": analysis_chain,
                "report_json": failure_report,
                "report_error": report_error,
            },
        )
        append_training_center_audit(
            cfg.root,
            action="release_review_report_failed",
            operator=operator_text,
            target_id=source_agent_id,
            detail={
                "review_id": review_id,
                "error": str(metadata_exc),
                "code": metadata_exc.code,
                "metadata_conflicts": metadata_conflicts,
                "enter_audit_id": enter_audit_id,
            },
        )
        return get_training_agent_release_review(cfg.root, source_agent_id)

    prompt_text = _build_release_review_prompt(
        agent=agent,
        workspace_path=workspace_path,
        target_version=target_version,
        current_workspace_ref=current_workspace_ref,
        released_versions=release_labels,
    )
    codex_result = _run_codex_exec_for_release_review(
        root=cfg.root,
        workspace_root=workspace_path,
        trace_dir=trace_dir,
        prompt_text=prompt_text,
    )
    try:
        codex_error = str(codex_result.get("error") or "").strip()
        if codex_error and codex_error != "codex_result_missing":
            raise TrainingCenterError(
                500,
                "release review report failed",
                "release_review_report_failed",
                {"reason": codex_error or "codex_result_missing"},
            )
        report = _normalize_release_review_report(
            codex_result.get("parsed_result") if isinstance(codex_result.get("parsed_result"), dict) else {},
            agent=agent,
            target_version=target_version,
            current_workspace_ref=current_workspace_ref,
            codex_error=codex_error,
        )
        analysis_chain = codex_result.get("analysis_chain") if isinstance(codex_result.get("analysis_chain"), dict) else {}
        analysis_chain["prompt_version"] = RELEASE_REVIEW_PROMPT_VERSION
        analysis_chain["report_error_code"] = ""
        analysis_chain["report_missing_fields"] = []
        _write_release_review_json(trace_dir / "parsed-result.json", report)
        profile_assets = _write_release_review_profile_assets(
            root=cfg.root,
            trace_dir=trace_dir,
            agent=agent,
            review_id=review_id,
            report=report,
            analysis_chain=analysis_chain,
        )
        analysis_chain["public_profile_markdown_path"] = str(profile_assets.get("public_profile_markdown_path") or "")
        analysis_chain["capability_snapshot_json_path"] = str(profile_assets.get("capability_snapshot_json_path") or "")
        _update_release_review_row(
            cfg.root,
            review_id,
            {
                "target_version": str(report.get("target_version") or "").strip(),
                "current_workspace_ref": str(report.get("current_workspace_ref") or "").strip(),
                "release_review_state": "report_ready",
                "analysis_chain_json": analysis_chain,
                "report_json": report,
                "report_error": "",
                "public_profile_markdown_path": str(profile_assets.get("public_profile_markdown_path") or ""),
                "capability_snapshot_json_path": str(profile_assets.get("capability_snapshot_json_path") or ""),
            },
        )
        append_training_center_audit(
            cfg.root,
            action="release_review_report_ready",
            operator=operator_text,
            target_id=source_agent_id,
            detail={
                "review_id": review_id,
                "prompt_version": RELEASE_REVIEW_PROMPT_VERSION,
                "report_path": str(analysis_chain.get("report_path") or ""),
                "stdout_path": str(analysis_chain.get("stdout_path") or ""),
                "stderr_path": str(analysis_chain.get("stderr_path") or ""),
                "public_profile_markdown_path": str(profile_assets.get("public_profile_markdown_path") or ""),
                "capability_snapshot_json_path": str(profile_assets.get("capability_snapshot_json_path") or ""),
            },
        )
    except TrainingCenterError as exc:
        analysis_chain = codex_result.get("analysis_chain") if isinstance(codex_result.get("analysis_chain"), dict) else {}
        analysis_chain["prompt_version"] = RELEASE_REVIEW_PROMPT_VERSION
        analysis_chain["error"] = str(codex_result.get("error") or exc.code or "").strip()
        extra = getattr(exc, "extra", {}) if isinstance(getattr(exc, "extra", {}), dict) else {}
        report_error = _describe_release_review_report_failure(exc, codex_result=codex_result)
        missing_fields = [
            str(item or "").strip()
            for item in (extra.get("missing_fields") or [])
            if str(item or "").strip()
        ]
        metadata_conflicts = [
            str(item or "").strip()
            for item in (extra.get("metadata_conflicts") or [])
            if str(item or "").strip()
        ]
        failure_report = _build_release_review_failure_report(
            codex_result.get("parsed_result") if isinstance(codex_result.get("parsed_result"), dict) else {},
            agent=agent,
            target_version=target_version,
            current_workspace_ref=current_workspace_ref,
            codex_error=str(codex_result.get("error") or "").strip(),
            error_code=str(exc.code or "").strip(),
            error_message=report_error,
            missing_fields=missing_fields,
            metadata_conflicts=metadata_conflicts,
        )
        _write_release_review_json(trace_dir / "parsed-result.json", failure_report)
        analysis_chain["report_error_code"] = str(exc.code or "").strip()
        analysis_chain["report_missing_fields"] = missing_fields
        if metadata_conflicts:
            analysis_chain["metadata_conflicts"] = metadata_conflicts
        _update_release_review_row(
            cfg.root,
            review_id,
            {
                "release_review_state": "report_failed",
                "analysis_chain_json": analysis_chain,
                "report_json": failure_report,
                "report_error": report_error,
            },
        )
        append_training_center_audit(
            cfg.root,
            action="release_review_report_failed",
            operator=operator_text,
            target_id=source_agent_id,
            detail={
                "review_id": review_id,
                "error": str(exc),
                "code": exc.code,
                "enter_audit_id": enter_audit_id,
            },
        )
    return get_training_agent_release_review(cfg.root, source_agent_id)


def discard_training_agent_release_review(
    cfg: AppConfig,
    *,
    agent_id: str,
    operator: str,
    reason: str = "",
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)
    reason_text = _short_text(str(reason or "").strip(), 500)

    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        lifecycle_state = normalize_lifecycle_state(agent.get("lifecycle_state"))
        row = _latest_release_review_row(conn, source_agent_id)
    finally:
        conn.close()

    if lifecycle_state != "pre_release":
        raise TrainingCenterError(
            409,
            "agent not in pre_release",
            "not_in_pre_release",
            {"agent_id": source_agent_id, "lifecycle_state": lifecycle_state},
        )
    if row is None:
        raise TrainingCenterError(409, "release review not found", "release_review_not_found", {"agent_id": pid})

    review_id = str(row.get("review_id") or "").strip()
    current_state = str(row.get("release_review_state") or "").strip().lower() or "idle"
    if not _can_discard_release_review(lifecycle_state, current_state, review_id):
        raise TrainingCenterError(
            409,
            "release review not discardable",
            "release_review_not_discardable",
            {"agent_id": source_agent_id, "release_review_state": current_state},
        )

    execution_logs = _json_load_list(row.get("execution_log_json"))
    reviewed_at = iso_ts(now_local())
    comment_text = reason_text or "已废弃当前发布评审记录"
    _append_release_review_log(
        execution_logs,
        phase="review_discard",
        status="done",
        message="已废弃当前发布评审记录，可重新进入发布评审",
        details={
            "operator": operator_text,
            "reason": reason_text,
            "from_state": current_state,
        },
    )
    _update_release_review_row(
        cfg.root,
        review_id,
        {
            "release_review_state": "review_discarded",
            "review_decision": "discard_review",
            "reviewer": operator_text,
            "review_comment": comment_text,
            "reviewed_at": reviewed_at,
            "execution_log_json": execution_logs,
        },
    )
    append_training_center_audit(
        cfg.root,
        action="release_review_discard",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "review_id": review_id,
            "from_state": current_state,
            "reason": reason_text,
        },
    )
    payload = get_training_agent_release_review(cfg.root, source_agent_id)
    payload["discarded"] = True
    payload["discard_reason"] = reason_text
    return payload


def submit_training_agent_release_review_manual(
    cfg: AppConfig,
    *,
    agent_id: str,
    decision: str,
    reviewer: str,
    review_comment: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    decision_text = str(decision or "").strip().lower()
    allowed = {"approve_publish", "reject_continue_training", "reject_discard_pre_release"}
    if decision_text not in allowed:
        raise TrainingCenterError(400, "decision invalid", "decision_invalid", {"allowed": sorted(allowed)})
    reviewer_text = safe_token(str(reviewer or ""), "", 80)
    if not reviewer_text:
        raise TrainingCenterError(400, "reviewer required", "reviewer_required")
    comment_text = str(review_comment or "").strip()
    operator_text = safe_token(str(operator or reviewer_text or "web-user"), "web-user", 80)

    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        row = _latest_release_review_row(conn, source_agent_id)
    finally:
        conn.close()
    if row is None:
        raise TrainingCenterError(409, "release review not found", "release_review_not_found", {"agent_id": pid})
    current_state = str(row.get("release_review_state") or "").strip().lower()
    if current_state != "report_ready":
        raise TrainingCenterError(
            409,
            "release review report not ready",
            "release_review_report_not_ready",
            {"agent_id": source_agent_id, "release_review_state": current_state},
        )

    reviewed_at = iso_ts(now_local())
    next_state = "review_approved" if decision_text == "approve_publish" else "review_rejected"
    _update_release_review_row(
        cfg.root,
        str(row.get("review_id") or ""),
        {
            "release_review_state": next_state,
            "review_decision": decision_text,
            "reviewer": reviewer_text,
            "review_comment": comment_text,
            "reviewed_at": reviewed_at,
        },
    )

    legacy_decision = {
        "approve_publish": "approve",
        "reject_continue_training": "reject_continue_training",
        "reject_discard_pre_release": "reject_discard",
    }[decision_text]
    shadow_eval_id = _insert_release_evaluation_shadow_record(
        cfg.root,
        agent_id=source_agent_id,
        target_version=str(row.get("target_version") or ""),
        decision=legacy_decision,
        reviewer=reviewer_text,
        summary=comment_text,
    )

    decision_result: dict[str, Any] = {}
    if decision_text == "reject_discard_pre_release":
        decision_result = {
            "decision_action": "rejected_and_discarded",
            "discard_result": discard_agent_pre_release(
                cfg,
                agent_id=source_agent_id,
                operator=operator_text,
            ),
        }
    elif decision_text == "approve_publish":
        decision_result = {"decision_action": "approved_wait_confirm_publish"}
    else:
        decision_result = {"decision_action": "rejected_continue_training"}

    append_training_center_audit(
        cfg.root,
        action="release_review_manual",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "review_id": str(row.get("review_id") or ""),
            "decision": decision_text,
            "reviewer": reviewer_text,
            "shadow_evaluation_id": shadow_eval_id,
        },
    )
    payload = get_training_agent_release_review(cfg.root, source_agent_id)
    payload["shadow_evaluation_id"] = shadow_eval_id
    payload["decision_result"] = decision_result
    return payload


def _execute_publish_attempt(
    cfg: AppConfig,
    *,
    agent: dict[str, Any],
    report: dict[str, Any],
    publish_version: str,
    review_comment: str,
    trace_dir: Path,
    execution_logs: list[dict[str, Any]],
    release_note_override: str = "",
) -> dict[str, Any]:
    workspace = Path(str(agent.get("workspace_path") or "")).resolve(strict=False)
    if not workspace.exists() or not workspace.is_dir():
        return {"ok": False, "error": "workspace_missing", "agent": agent}
    git_ready = _ensure_workspace_git_ready_for_publish(
        cfg,
        workspace=workspace,
        agent=agent,
        execution_logs=execution_logs,
    )
    if not git_ready.get("ok"):
        return {
            "ok": False,
            "error": str(git_ready.get("error") or "git_unavailable").strip() or "git_unavailable",
            "agent": agent,
            "stderr": str(git_ready.get("stderr") or "").strip(),
        }

    current_ref_before = _workspace_current_ref(workspace)
    status_ok, status_out, status_err = _run_git_readonly_verbose(
        workspace,
        ["status", "--porcelain", "--untracked-files=normal"],
        timeout_s=12,
    )
    if not status_ok:
        return {"ok": False, "error": "git_status_failed", "agent": agent, "stderr": status_err}
    dirty_lines = [str(line or "").rstrip() for line in str(status_out or "").splitlines() if str(line or "").strip()]
    _append_release_review_log(
        execution_logs,
        phase="prepare",
        status="done",
        message=f"准备发布版本 {publish_version}，工作区基线 {current_ref_before or '-'}，变更数={len(dirty_lines)}",
    )

    release_note_path = trace_dir / (f"release-note-{safe_token(publish_version, 'version', 80)}.md")
    release_note_text = (
        str(release_note_override or "").strip()
        if str(release_note_override or "").strip() and ("角色能力摘要" in str(release_note_override) or "version_notes" in str(release_note_override).lower())
        else _build_publish_release_note(
            agent=agent,
            report=report,
            publish_version=publish_version,
            review_comment=str(release_note_override or "").strip() or review_comment,
        )
    )
    _write_release_review_text(release_note_path, release_note_text)
    _append_release_review_log(
        execution_logs,
        phase="release_note",
        status="done",
        message="已生成 release note",
        path=_path_for_ui(cfg.root, release_note_path),
    )

    if dirty_lines:
        ok_add, _, add_err = _run_git_mutation(workspace, ["add", "-A"], timeout_s=30)
        if not ok_add:
            _append_release_review_log(
                execution_logs,
                phase="git_execute",
                status="failed",
                message="git add -A 失败",
                details={"stderr": _short_text(add_err, 400)},
            )
            return {"ok": False, "error": "git_add_failed", "agent": agent, "stderr": add_err}
        ok_commit, commit_out, commit_err = _run_git_mutation(
            workspace,
            ["commit", "-m", f"release: {publish_version}"],
            timeout_s=60,
        )
        if not ok_commit:
            _append_release_review_log(
                execution_logs,
                phase="git_execute",
                status="failed",
                message="git commit 失败",
                details={"stdout": _short_text(commit_out, 300), "stderr": _short_text(commit_err, 400)},
            )
            return {"ok": False, "error": "git_commit_failed", "agent": agent, "stderr": commit_err or commit_out}
        _append_release_review_log(
            execution_logs,
            phase="git_execute",
            status="done",
            message="已提交当前预发布内容",
            details={"stdout": _short_text(commit_out, 240)},
        )
    else:
        _append_release_review_log(
            execution_logs,
            phase="git_execute",
            status="done",
            message="工作区无额外改动，跳过提交",
        )

    preverified, precheck_row, precheck_error = _verify_release_note_before_tag(
        workspace,
        publish_version,
        release_note_text,
    )
    if not preverified:
        _append_release_review_log(
            execution_logs,
            phase="verify",
            status="failed",
            message="发布预校验失败，未创建标签",
            details={"reason": precheck_error, "publish_version": publish_version},
        )
        return {
            "ok": False,
            "error": precheck_error,
            "agent": agent,
            "publish_row": precheck_row,
            "release_note_path": _path_for_ui(cfg.root, release_note_path),
        }
    _append_release_review_log(
        execution_logs,
        phase="verify",
        status="done",
        message="发布预校验通过，准备创建标签",
        details={"publish_version": publish_version},
    )

    ok_tag, tag_out, tag_err = _run_git_mutation(
        workspace,
        ["tag", "-a", publish_version, "-F", release_note_path.as_posix()],
        timeout_s=30,
    )
    if not ok_tag:
        _append_release_review_log(
            execution_logs,
            phase="git_execute",
            status="failed",
            message="git tag 发布失败",
            details={"stdout": _short_text(tag_out, 300), "stderr": _short_text(tag_err, 400)},
        )
        return {"ok": False, "error": "git_tag_failed", "agent": agent, "stderr": tag_err or tag_out}
    _append_release_review_log(
        execution_logs,
        phase="git_execute",
        status="done",
        message=f"已创建发布标签 {publish_version}",
    )

    verified, publish_row, verify_error = _verify_published_release(workspace, publish_version)
    if not verified:
        _append_release_review_log(
            execution_logs,
            phase="verify",
            status="failed",
            message="发布成功校验失败",
            details={"reason": verify_error, "publish_version": publish_version},
        )
        return {"ok": False, "error": verify_error, "agent": agent, "publish_row": publish_row}
    released_at = str(publish_row.get("released_at") or "").strip() or iso_ts(now_local())
    updated_agent = _update_agent_after_publish(
        cfg,
        agent_id=str(agent.get("agent_id") or ""),
        publish_version=publish_version,
        released_at=released_at,
    )
    _append_release_review_log(
        execution_logs,
        phase="verify",
        status="done",
        message=f"发布成功校验通过：{publish_version}",
    )
    return {
        "ok": True,
        "agent": updated_agent,
        "publish_version": publish_version,
        "publish_row": publish_row,
        "release_note_path": _path_for_ui(cfg.root, release_note_path),
    }


def _run_publish_fallback_once(
    cfg: AppConfig,
    *,
    review_payload: dict[str, Any],
    agent: dict[str, Any],
    failed_publish_version: str,
    failed_error: str,
    trace_dir: Path,
    execution_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    _append_release_review_log(
        execution_logs,
        phase="fallback_trigger",
        status="running",
        message="已触发失败兜底，准备分析失败原因并自动重试一次",
    )
    fallback_dir = trace_dir / "fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = _build_release_review_fallback_prompt(
        review=review_payload,
        publish_version=failed_publish_version,
        publish_error=failed_error,
        execution_logs=execution_logs,
    )
    codex_result = _run_codex_exec_for_release_review(
        root=cfg.root,
        workspace_root=Path(str(agent.get("workspace_path") or "")).resolve(strict=False),
        trace_dir=fallback_dir,
        prompt_text=prompt_text,
    )
    fallback_payload = {
        "status": "fallback_failed",
        "error": str(codex_result.get("error") or ""),
        "analysis_chain": codex_result.get("analysis_chain") if isinstance(codex_result.get("analysis_chain"), dict) else {},
        "result": codex_result.get("parsed_result") if isinstance(codex_result.get("parsed_result"), dict) else {},
        "repair_summary": "",
        "repair_actions": [],
        "warnings": [],
        "retry_result": {},
        "next_action_suggestion": "请先根据失败原因修复工作区或环境，再重试发布；若报告本身需要更新，再重新进入发布评审。",
    }
    if not codex_result.get("ok"):
        _append_release_review_log(
            execution_logs,
            phase="fallback_result",
            status="failed",
            message="兜底启动失败，需人工介入",
            details={"error": fallback_payload["error"]},
        )
        return fallback_payload

    fallback_result = codex_result.get("parsed_result") if isinstance(codex_result.get("parsed_result"), dict) else {}
    reason_text = _short_text(str(fallback_result.get("failure_reason") or failed_error or "发布失败").strip(), 320)
    repair_summary = _short_text(str(fallback_result.get("repair_summary") or "").strip(), 320)
    repair_actions = _ensure_first_person_list(fallback_result.get("repair_actions"), "我已执行的修复动作：", limit=8, item_limit=220)
    fallback_warnings = _ensure_first_person_list(fallback_result.get("warnings"), "我还需要提示：", limit=8, item_limit=220)
    retry_note_text = str(fallback_result.get("retry_release_notes") or "").strip()
    _append_release_review_log(
        execution_logs,
        phase="fallback_trigger",
        status="done",
        message="兜底已完成失败诊断，并给出修复动作后准备自动重试",
        details={
            "failure_reason": reason_text,
            "repair_summary": repair_summary,
            "repair_actions": repair_actions,
            "warnings": fallback_warnings,
        },
    )
    _, _, rows = _parse_git_release_rows(Path(str(agent.get("workspace_path") or "")).resolve(strict=False), limit=120)
    existing_labels = [str(row.get("version_label") or "").strip() for row in rows if str(row.get("version_label") or "").strip()]
    retry_version = _next_release_version_label(existing_labels, str(fallback_result.get("retry_target_version") or failed_publish_version).strip())
    retry_attempt = _execute_publish_attempt(
        cfg,
        agent=agent,
        report=review_payload.get("report") if isinstance(review_payload.get("report"), dict) else {},
        publish_version=retry_version,
        review_comment=str(review_payload.get("review_comment") or "").strip(),
        trace_dir=fallback_dir,
        execution_logs=execution_logs,
        release_note_override=retry_note_text,
    )
    fallback_payload = {
        "status": "fallback_done" if retry_attempt.get("ok") else "fallback_failed",
        "failure_reason": reason_text,
        "analysis_chain": codex_result.get("analysis_chain") if isinstance(codex_result.get("analysis_chain"), dict) else {},
        "result": fallback_result,
        "repair_summary": repair_summary,
        "repair_actions": repair_actions,
        "warnings": fallback_warnings,
        "retry_result": retry_attempt,
        "next_action_suggestion": _short_text(
            str(
                fallback_result.get("next_action_suggestion")
                or "请先根据兜底诊断修复工作区或环境，然后直接重试发布；若报告本身需要更新，再重新进入发布评审。"
            ).strip(),
            320,
        ),
    }
    _append_release_review_log(
        execution_logs,
        phase="fallback_result",
        status="done" if retry_attempt.get("ok") else "failed",
        message="兜底自动重试完成" if retry_attempt.get("ok") else "兜底自动重试后仍失败",
        details={
            "retry_version": retry_version,
            "error": str(retry_attempt.get("error") or ""),
        },
    )
    return fallback_payload


def confirm_training_agent_release_review(
    cfg: AppConfig,
    *,
    agent_id: str,
    operator: str,
) -> dict[str, Any]:
    sync_training_agent_registry(cfg)
    pid = safe_token(str(agent_id or ""), "", 120)
    if not pid:
        raise TrainingCenterError(400, "agent_id required", "agent_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)
    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, pid)
        if agent is None:
            raise TrainingCenterError(404, "agent not found", "agent_not_found", {"agent_id": pid})
        source_agent_id = str(agent.get("agent_id") or "").strip()
        row = _latest_release_review_row(conn, source_agent_id)
    finally:
        conn.close()
    if row is None:
        raise TrainingCenterError(409, "release review not found", "release_review_not_found", {"agent_id": pid})
    current_state = str(row.get("release_review_state") or "").strip()
    review_decision = str(row.get("review_decision") or "").strip()
    lifecycle_state = str(agent.get("lifecycle_state") or "").strip()
    if not _can_confirm_release_review(lifecycle_state, current_state, review_decision):
        raise TrainingCenterError(
            409,
            "release review not approved",
            "release_review_not_approved",
            {"release_review_state": current_state, "review_decision": review_decision, "lifecycle_state": lifecycle_state},
        )
    if review_decision != "approve_publish":
        raise TrainingCenterError(
            409,
            "review decision is not approve_publish",
            "review_decision_not_approve_publish",
            {"review_decision": review_decision},
        )

    review_payload = _release_review_payload(agent, row)
    review_id = str(row.get("review_id") or "").strip()
    trace_dir_text = str((review_payload.get("analysis_chain") or {}).get("trace_dir") or "").strip()
    trace_dir = (cfg.root / trace_dir_text).resolve(strict=False) if trace_dir_text else _release_review_trace_dir(cfg.root, str(agent.get("agent_name") or source_agent_id), review_id)
    execution_logs = review_payload.get("execution_logs") if isinstance(review_payload.get("execution_logs"), list) else []
    workspace = Path(str(agent.get("workspace_path") or "")).resolve(strict=False)
    retrying_failed_publish = current_state == "publish_failed"
    attempt_trace_dir = _release_review_attempt_dir(trace_dir, "manual-retry") if retrying_failed_publish else trace_dir
    if retrying_failed_publish:
        _append_release_review_log(
            execution_logs,
            phase="prepare",
            status="running",
            message="检测到上次确认发布失败，开始基于当前评审记录手动重试发布",
            details={"review_id": review_id},
        )
    publish_version = _next_release_version_label(
        _workspace_release_labels(workspace),
        str(review_payload.get("target_version") or "").strip(),
    )
    _update_release_review_row(
        cfg.root,
        review_id,
        {
            "release_review_state": "publish_running",
            "publish_status": "",
            "publish_error": "",
            "publish_version": publish_version,
            "execution_log_json": execution_logs,
            "fallback_json": {},
        },
    )

    append_training_center_audit(
        cfg.root,
        action="release_review_confirm",
        operator=operator_text,
        target_id=source_agent_id,
        detail={"review_id": review_id, "publish_version": publish_version, "retry_mode": "manual" if retrying_failed_publish else "initial"},
    )

    publish_result = _execute_publish_attempt(
        cfg,
        agent=agent,
        report=review_payload.get("report") if isinstance(review_payload.get("report"), dict) else {},
        publish_version=publish_version,
        review_comment=str(review_payload.get("review_comment") or "").strip(),
        trace_dir=attempt_trace_dir,
        execution_logs=execution_logs,
    )
    if publish_result.get("ok"):
        _bind_release_profile_after_publish(
            cfg,
            agent_id=source_agent_id,
            publish_version=str(publish_result.get("publish_version") or publish_version),
            review_id=review_id,
            analysis_chain=review_payload.get("analysis_chain") if isinstance(review_payload.get("analysis_chain"), dict) else {},
            public_profile_markdown_path=str(row.get("public_profile_markdown_path") or "").strip(),
            capability_snapshot_json_path=str(row.get("capability_snapshot_json_path") or "").strip(),
        )
        _update_release_review_row(
            cfg.root,
            review_id,
            {
                "release_review_state": "idle",
                "publish_status": "success",
                "publish_error": "",
                "publish_version": str(publish_result.get("publish_version") or publish_version),
                "execution_log_json": execution_logs,
                "fallback_json": {},
            },
        )
        return get_training_agent_release_review(cfg.root, source_agent_id)

    publish_error = str(publish_result.get("error") or "publish_failed").strip() or "publish_failed"
    fallback_payload = _run_publish_fallback_once(
        cfg,
        review_payload=review_payload,
        agent=agent,
        failed_publish_version=publish_version,
        failed_error=publish_error,
        trace_dir=attempt_trace_dir,
        execution_logs=execution_logs,
    )
    retry_result = fallback_payload.get("retry_result") if isinstance(fallback_payload.get("retry_result"), dict) else {}
    if retry_result.get("ok"):
        _bind_release_profile_after_publish(
            cfg,
            agent_id=source_agent_id,
            publish_version=str(retry_result.get("publish_version") or publish_version),
            review_id=review_id,
            analysis_chain=review_payload.get("analysis_chain") if isinstance(review_payload.get("analysis_chain"), dict) else {},
            public_profile_markdown_path=str(row.get("public_profile_markdown_path") or "").strip(),
            capability_snapshot_json_path=str(row.get("capability_snapshot_json_path") or "").strip(),
        )
        _update_release_review_row(
            cfg.root,
            review_id,
            {
                "release_review_state": "idle",
                "publish_status": "success",
                "publish_error": "",
                "publish_version": str(retry_result.get("publish_version") or publish_version),
                "execution_log_json": execution_logs,
                "fallback_json": fallback_payload,
            },
        )
        return get_training_agent_release_review(cfg.root, source_agent_id)

    _update_release_review_row(
        cfg.root,
        review_id,
        {
            "release_review_state": "publish_failed",
            "publish_status": "failed",
            "publish_error": publish_error,
            "publish_version": publish_version,
            "execution_log_json": execution_logs,
            "fallback_json": fallback_payload,
        },
    )
    append_training_center_audit(
        cfg.root,
        action="release_review_publish_failed",
        operator=operator_text,
        target_id=source_agent_id,
        detail={
            "review_id": review_id,
            "publish_version": publish_version,
            "publish_error": publish_error,
            "fallback_status": str(fallback_payload.get("status") or ""),
        },
    )
    return get_training_agent_release_review(cfg.root, source_agent_id)


