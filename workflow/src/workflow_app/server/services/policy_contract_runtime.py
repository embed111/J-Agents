from __future__ import annotations


def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    globals().update(symbols)


def parse_markdown_sections(markdown_text: str) -> list[tuple[str, int, str]]:
    text = str(markdown_text or "")
    if not text.strip():
        return []
    lines = text.splitlines()
    heading_re = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
    headings: list[tuple[int, int, str]] = []
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\n")
        matched = heading_re.match(line)
        if not matched:
            continue
        level = int(len(matched.group(1)))
        title = matched.group(2).strip()
        if not title:
            continue
        headings.append((idx, level, title))
    sections: list[tuple[str, int, str]] = []
    for idx, (line_no, level, title) in enumerate(headings):
        end_line = len(lines)
        for next_line_no, next_level, _next_title in headings[idx + 1 :]:
            if next_level <= level:
                end_line = next_line_no
                break
        block = "\n".join(lines[line_no + 1 : end_line]).strip()
        sections.append((title, level, block))
    return sections


def policy_text_compact(text: str, *, max_chars: int) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    if len(value) > max_chars:
        return value[:max_chars].rstrip() + "\n...(已截断)"
    return value


def normalize_heading_title(title: str) -> str:
    value = str(title or "").strip().lower()
    value = value.replace(" ", "")
    value = re.sub(r"[`~!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|，。！？；：（）【】《》、]", "", value)
    return value


def heading_matches(title: str, anchor: str) -> bool:
    norm_title = normalize_heading_title(title)
    norm_anchor = normalize_heading_title(anchor)
    return bool(norm_anchor and norm_title.startswith(norm_anchor))


def find_first_section_by_headings(
    sections: list[tuple[str, int, str]],
    headings: tuple[str, ...],
) -> tuple[str, int, str] | None:
    for anchor in headings:
        for section in sections:
            title, _level, _content = section
            if heading_matches(title, anchor):
                return section
    return None


def find_sections_by_headings(
    sections: list[tuple[str, int, str]],
    headings: tuple[str, ...],
    *,
    limit: int,
) -> list[tuple[str, int, str]]:
    picked: list[tuple[str, int, str]] = []
    seen_titles: set[str] = set()
    for anchor in headings:
        for section in sections:
            title, _level, _content = section
            key = normalize_heading_title(title)
            if key in seen_titles:
                continue
            if heading_matches(title, anchor):
                picked.append(section)
                seen_titles.add(key)
            if len(picked) >= max(1, limit):
                return picked
    return picked


def heading_contains(title: str, anchor: str) -> bool:
    norm_title = normalize_heading_title(title)
    norm_anchor = normalize_heading_title(anchor)
    return bool(norm_anchor and norm_anchor in norm_title)


def find_sections_by_heading_contains(
    sections: list[tuple[str, int, str]],
    headings: tuple[str, ...],
    *,
    limit: int,
) -> list[tuple[str, int, str]]:
    picked: list[tuple[str, int, str]] = []
    seen_titles: set[str] = set()
    for section in sections:
        title, _level, _content = section
        key = normalize_heading_title(title)
        if key in seen_titles:
            continue
        if any(heading_contains(title, anchor) for anchor in headings):
            picked.append(section)
            seen_titles.add(key)
            if len(picked) >= max(1, limit):
                break
    return picked


def line_clean_for_summary(text: str) -> str:
    value = str(text or "").strip()
    value = re.sub(r"^\s*(?:[-*+]|[0-9]+[.)]|[（(]?[0-9]+[）)])\s*", "", value)
    return value.strip()


def summarize_section_content(
    text: str,
    *,
    max_chars: int,
    max_lines: int,
) -> str:
    lines = []
    for raw in str(text or "").splitlines():
        item = line_clean_for_summary(raw)
        if not item:
            continue
        lines.append(item)
        if len(lines) >= max(1, max_lines):
            break
    if not lines:
        return ""
    merged = " ".join(lines)
    return policy_text_compact(merged, max_chars=max_chars)


def extract_list_items_from_text(
    text: str,
    *,
    max_items: int = 12,
) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    bullet_re = re.compile(r"^\s*(?:[-*+]|[0-9]+[.)]|[（(]?[0-9]+[）)])\s*(.+?)\s*$")
    for raw in str(text or "").splitlines():
        matched = bullet_re.match(raw)
        if not matched:
            continue
        value = line_clean_for_summary(matched.group(1))
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        items.append(value)
        seen.add(key)
        if len(items) >= max(1, max_items):
            return items
    if items:
        return items
    for raw in str(text or "").splitlines():
        value = line_clean_for_summary(raw)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        items.append(value)
        seen.add(key)
        if len(items) >= max(1, max_items):
            break
    return items


def constraint_text_key(text: str) -> str:
    value = str(text or "").strip().lower()
    value = re.sub(r"\s+", "", value)
    value = value.replace("必须", "").replace("应当", "").replace("不得", "").replace("禁止", "")
    value = value.replace("不能", "").replace("不可", "").replace("must", "").replace("mustnot", "")
    value = re.sub(r"[`~!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|，。！？；：（）【】《》、]", "", value)
    return value


def extract_constraint_entries_from_sections(
    sections: list[tuple[str, int, str]],
    *,
    max_items: int = 10,
) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for section in sections:
        title, _level, content = section
        for item in extract_list_items_from_text(content, max_items=max_items):
            text = policy_text_compact(str(item or "").strip(), max_chars=220)
            if not text:
                continue
            key = constraint_text_key(text)
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "text": text,
                    "evidence": policy_text_compact(f"{title}\n{text}", max_chars=260),
                    "source_title": str(title or ""),
                }
            )
            if len(entries) >= max(1, max_items):
                return entries
    return entries


def text_contains_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    value = str(text or "").strip().lower()
    if not value:
        return False
    compact = re.sub(r"\s+", "", value)
    for keyword in keywords:
        probe = str(keyword or "").strip().lower()
        if not probe:
            continue
        if probe in value:
            return True
        probe_compact = re.sub(r"\s+", "", probe)
        if probe_compact and probe_compact in compact:
            return True
    return False


def classify_constraint_kind(entry: dict[str, str]) -> str:
    title = str(entry.get("source_title") or "").strip()
    text = str(entry.get("text") or "").strip()
    combined = f"{title}\n{text}".strip()
    if title and any(heading_contains(title, anchor) for anchor in _AGENT_MUST_NOT_HEADINGS):
        return "must_not"
    if title and any(heading_contains(title, anchor) for anchor in _AGENT_PRECONDITION_HEADINGS):
        return "preconditions"
    if title and any(heading_contains(title, anchor) for anchor in _AGENT_MUST_HEADINGS):
        return "must"
    if text_contains_any_keyword(combined, _CONSTRAINT_MUST_NOT_TERMS):
        return "must_not"
    if text_contains_any_keyword(combined, _CONSTRAINT_PRECONDITION_TERMS):
        return "preconditions"
    if re.search(r"在.{0,12}前", combined):
        return "preconditions"
    if text_contains_any_keyword(combined, _CONSTRAINT_MUST_TERMS):
        return "must"
    return ""


def classify_constraint_entries(
    entries: list[dict[str, str]],
    *,
    max_items: int = 10,
) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {
        "must": [],
        "must_not": [],
        "preconditions": [],
    }
    seen_by_kind: dict[str, set[str]] = {
        "must": set(),
        "must_not": set(),
        "preconditions": set(),
    }
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        text = policy_text_compact(str(raw.get("text") or "").strip(), max_chars=220)
        if not text:
            continue
        kind = classify_constraint_kind(raw)
        if kind not in grouped:
            continue
        key = constraint_text_key(text)
        if not key or key in seen_by_kind[kind]:
            continue
        seen_by_kind[kind].add(key)
        grouped[kind].append(
            {
                "text": text,
                "evidence": policy_text_compact(str(raw.get("evidence") or "").strip(), max_chars=260),
                "source_title": str(raw.get("source_title") or "").strip(),
            }
        )
        if len(grouped[kind]) >= max(1, max_items):
            grouped[kind] = grouped[kind][: max(1, max_items)]
    return grouped


def filter_constraint_entries_by_kind(
    entries: list[dict[str, str]],
    *,
    kind: str,
    max_items: int = 10,
) -> list[dict[str, str]]:
    picked: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        if classify_constraint_kind(raw) != kind:
            continue
        text = policy_text_compact(str(raw.get("text") or "").strip(), max_chars=220)
        if not text:
            continue
        key = constraint_text_key(text)
        if not key or key in seen:
            continue
        seen.add(key)
        picked.append(
            {
                "text": text,
                "evidence": policy_text_compact(str(raw.get("evidence") or "").strip(), max_chars=260),
                "source_title": str(raw.get("source_title") or "").strip(),
            }
        )
        if len(picked) >= max(1, max_items):
            break
    return picked


def extract_constraints_from_policy(
    *,
    sections: list[tuple[str, int, str]],
    duty_items: list[str],
) -> dict[str, Any]:
    must_sections = find_sections_by_heading_contains(sections, _AGENT_MUST_HEADINGS, limit=3)
    must_not_sections = find_sections_by_heading_contains(sections, _AGENT_MUST_NOT_HEADINGS, limit=3)
    pre_sections = find_sections_by_heading_contains(sections, _AGENT_PRECONDITION_HEADINGS, limit=3)

    limit_sections = find_sections_by_heading_contains(sections, _AGENT_LIMIT_HEADINGS, limit=3)

    must_entries = extract_constraint_entries_from_sections(must_sections, max_items=10)
    must_not_entries = extract_constraint_entries_from_sections(must_not_sections, max_items=10)
    pre_entries = extract_constraint_entries_from_sections(pre_sections, max_items=10)
    must_entries = filter_constraint_entries_by_kind(must_entries, kind="must", max_items=10)
    must_not_entries = filter_constraint_entries_by_kind(must_not_entries, kind="must_not", max_items=10)
    pre_entries = filter_constraint_entries_by_kind(pre_entries, kind="preconditions", max_items=10)

    if limit_sections and (not must_entries or not must_not_entries or not pre_entries):
        limit_entries = extract_constraint_entries_from_sections(limit_sections, max_items=24)
        grouped_from_limit = classify_constraint_entries(limit_entries, max_items=10)
        if not must_entries:
            must_entries = grouped_from_limit.get("must") or []
        if not must_not_entries:
            must_not_entries = grouped_from_limit.get("must_not") or []
        if not pre_entries:
            pre_entries = grouped_from_limit.get("preconditions") or []

    if not must_entries or not must_not_entries or not pre_entries:
        duty_raw_entries: list[dict[str, str]] = []
        for item in duty_items:
            text = str(item or "").strip()
            if not text:
                continue
            duty_raw_entries.append(
                {
                    "text": policy_text_compact(text, max_chars=220),
                    "evidence": policy_text_compact(f"职责边界\n{text}", max_chars=260),
                    "source_title": "职责边界",
                }
            )
            if len(duty_raw_entries) >= 24:
                break
        grouped_from_duty = classify_constraint_entries(duty_raw_entries, max_items=10)
        if not must_entries:
            must_entries = grouped_from_duty.get("must") or []
        if not must_not_entries:
            must_not_entries = grouped_from_duty.get("must_not") or []
        if not pre_entries:
            pre_entries = grouped_from_duty.get("preconditions") or []

    all_entries = [*must_entries, *must_not_entries, *pre_entries]
    missing_evidence_count = sum(1 for entry in all_entries if not str(entry.get("evidence") or "").strip())

    conflicts: list[str] = []
    must_core_map: dict[str, str] = {}
    for entry in must_entries:
        core = constraint_text_key(entry.get("text") or "")
        if core:
            must_core_map[core] = str(entry.get("text") or "")
    for entry in must_not_entries:
        core = constraint_text_key(entry.get("text") or "")
        if core and core in must_core_map:
            conflicts.append(
                f"必须项“{must_core_map[core]}”与禁止项“{str(entry.get('text') or '')}”存在冲突"
            )

    issues: list[dict[str, str]] = []
    total_constraints = len(all_entries)
    if total_constraints <= 0:
        issues.append({"code": "constraints_missing", "message": "职责边界缺失，需人工确认。"})
    if missing_evidence_count > 0:
        issues.append(
            {
                "code": "constraints_evidence_missing",
                "message": f"职责边界存在 {missing_evidence_count} 条无证据映射，需人工确认。",
            }
        )
    if conflicts:
        issues.append(
            {
                "code": "constraints_conflict",
                "message": "职责边界存在冲突描述，需人工确认。",
            }
        )

    return {
        "must": must_entries,
        "must_not": must_not_entries,
        "preconditions": pre_entries,
        "issues": issues,
        "conflicts": conflicts,
        "missing_evidence_count": int(missing_evidence_count),
        "total": total_constraints,
    }


def first_non_empty_sentence(text: str, *, max_chars: int = 180) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ""
    for sep in ("。", ".", "；", ";", "!", "！", "?", "？"):
        pos = value.find(sep)
        if 0 < pos <= max_chars:
            return value[: pos + 1]
    if len(value) > max_chars:
        return value[:max_chars].rstrip() + "..."
    return value


def section_evidence_snippet(
    section: tuple[str, int, str] | None,
    *,
    max_lines: int = 6,
    max_chars: int = 420,
) -> str:
    if not section:
        return ""
    title, _level, content = section
    lines: list[str] = []
    for raw in str(content or "").splitlines():
        cleaned = line_clean_for_summary(raw)
        if not cleaned:
            continue
        lines.append(cleaned)
        if len(lines) >= max(1, max_lines):
            break
    body = "\n".join(lines).strip()
    if not body:
        body = policy_text_compact(str(content or ""), max_chars=max_chars)
    return policy_text_compact(f"{title}\n{body}".strip(), max_chars=max_chars)


def policy_warning_text(code: str) -> str:
    mapping = {
        "agents_md_empty": "AGENTS.md 为空",
        "missing_role_section": "未识别到角色章节",
        "missing_goal_section": "未识别到目标章节",
        "goal_inferred_from_role_profile": "目标由角色内容推断",
        "missing_duty_section": "未识别到职责章节",
        "empty_duty_constraints": "职责章节缺少清晰条目",
        "missing_required_policy_fields": "关键字段不足",
        "constraints_missing": "职责边界缺失",
        "constraints_evidence_missing": "职责边界存在无证据条目",
        "constraints_conflict": "职责边界存在冲突",
    }
    key = str(code or "").strip()
    return mapping.get(key, key)


def compute_policy_clarity(
    *,
    role_profile: str,
    session_goal: str,
    duty_constraints: list[str],
    parse_status: str,
    parse_warnings: list[str],
    evidence_snippets: dict[str, str],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_text = str(role_profile or "").strip()
    goal_text = str(session_goal or "").strip()
    duty_items = [str(item or "").strip() for item in duty_constraints if str(item or "").strip()]
    warnings = [str(item or "").strip() for item in (parse_warnings or []) if str(item or "").strip()]
    status = str(parse_status or "failed").strip().lower() or "failed"
    constraints_data = constraints if isinstance(constraints, dict) else {}
    must_items = [item for item in (constraints_data.get("must") or []) if isinstance(item, dict)]
    must_not_items = [item for item in (constraints_data.get("must_not") or []) if isinstance(item, dict)]
    pre_items = [item for item in (constraints_data.get("preconditions") or []) if isinstance(item, dict)]
    constraint_issues = [item for item in (constraints_data.get("issues") or []) if isinstance(item, dict)]
    constraint_conflicts = [str(item).strip() for item in (constraints_data.get("conflicts") or []) if str(item or "").strip()]
    missing_evidence_count = int(constraints_data.get("missing_evidence_count") or 0)
    constraint_total = int(constraints_data.get("total") or (len(must_items) + len(must_not_items) + len(pre_items)))

    role_evidence = str((evidence_snippets or {}).get("role") or "").strip()
    goal_evidence = str((evidence_snippets or {}).get("goal") or "").strip()
    duty_evidence = str((evidence_snippets or {}).get("duty") or "").strip()
    constraints_evidence = [
        str(item.get("evidence") or "").strip()
        for item in [*must_items, *must_not_items, *pre_items]
        if str(item.get("evidence") or "").strip()
    ]

    def _safe_score(value: int) -> int:
        return max(0, min(100, int(value)))

    def _dimension(
        *,
        key: str,
        label: str,
        raw_score: int,
        evidence_refs: list[dict[str, str]],
        deduction_reason: str,
        repair_suggestion: str,
        threshold: int = 80,
    ) -> dict[str, Any]:
        score = _safe_score(raw_score)
        cleaned_refs = []
        seen_refs: set[str] = set()
        for ref in evidence_refs:
            ref_id = str((ref or {}).get("ref") or "").strip()
            snippet = policy_text_compact(str((ref or {}).get("snippet") or ""), max_chars=220)
            # 证据条目必须有可读片段；仅有 ref 但无 snippet 视为无证据。
            if not snippet:
                continue
            key_ref = f"{ref_id}:{snippet}"
            if key_ref in seen_refs:
                continue
            seen_refs.add(key_ref)
            cleaned_refs.append(
                {
                    "ref": ref_id or "unknown",
                    "snippet": snippet,
                }
            )
        has_evidence = bool(cleaned_refs)
        manual_review_required = False
        status_text = "ok"
        reason_text = ""
        if not has_evidence:
            # 无证据不扣分：保持中性分，强制人工确认。
            score = 80
            manual_review_required = True
            status_text = "manual_review"
            reason_text = "证据不足，需人工确认（无证据不直接扣分）。"
        elif score < threshold:
            status_text = "low"
            reason_text = str(deduction_reason or "").strip()
        return {
            "label": label,
            "score": score,
            "weight": float(POLICY_SCORE_WEIGHTS.get(key) or 0.0),
            "status": status_text,
            "has_evidence": has_evidence,
            "manual_review_required": manual_review_required,
            "deduction_reason": reason_text,
            "evidence_map": cleaned_refs,
            "repair_suggestion": str(repair_suggestion or "").strip(),
            "threshold": int(threshold),
        }

    duty_count = len(duty_items)
    duty_blob = "\n".join(duty_items)
    vague_terms = ("帮助", "支持", "相关", "适当", "尽量", "一些", "通用", "等等", "多种")
    vague_hits = sum(1 for term in vague_terms if term in f"{role_text}\n{goal_text}\n{duty_blob}")
    open_words = ("不限", "任何请求", "任意请求", "无边界", "都可以", "全部请求")
    limit_words = ("仅", "只", "不得", "禁止", "必须", "严禁", "边界")
    conflict_hits = 0
    if any(term in duty_blob for term in open_words) and any(term in duty_blob for term in limit_words):
        conflict_hits += 1
    if constraint_conflicts:
        conflict_hits += len(constraint_conflicts)

    completeness_raw = 0
    if role_text:
        completeness_raw += 34
    if goal_text:
        completeness_raw += 33
    if duty_items:
        completeness_raw += 33
    if status == "failed":
        completeness_raw = min(completeness_raw, 35)
    elif status == "incomplete":
        completeness_raw = min(completeness_raw, 75)

    executability_raw = 25
    if must_items:
        executability_raw += 30
    if must_not_items:
        executability_raw += 30
    if pre_items:
        executability_raw += 15
    if any(term in duty_blob for term in ("边界", "仅", "只", "不得", "禁止")):
        executability_raw += 10
    if constraint_total <= 0:
        executability_raw = min(executability_raw, 45)
    if conflict_hits > 0:
        executability_raw -= 20

    consistency_raw = 88
    if not (role_text and goal_text):
        consistency_raw = min(consistency_raw, 60)
    if not duty_items:
        consistency_raw = min(consistency_raw, 55)
    if "goal_inferred_from_role_profile" in warnings:
        consistency_raw -= 12
    if conflict_hits > 0:
        consistency_raw -= min(40, 18 * conflict_hits)
    if status == "failed":
        consistency_raw = min(consistency_raw, 40)
    elif status == "incomplete":
        consistency_raw = min(consistency_raw, 70)

    evidence_count = 0
    for key in ("role", "goal", "duty"):
        if str((evidence_snippets or {}).get(key) or "").strip():
            evidence_count += 1
    base_traceability = int(round((evidence_count / 3.0) * 70))
    constraint_trace = 0
    if constraint_total > 0:
        constraint_trace = int(round((len(constraints_evidence) / max(1, constraint_total)) * 30))
    traceability_raw = base_traceability + constraint_trace
    if status == "failed":
        traceability_raw = min(traceability_raw, 40)

    risk_raw = 28
    if must_not_items:
        risk_raw += 42
        if len(must_not_items) >= 3:
            risk_raw += 10
    risk_terms = ("高风险", "敏感", "生产", "删除", "覆盖", "密钥", "权限", "安全", "泄露")
    risk_hits = sum(
        1
        for term in risk_terms
        if term in duty_blob or any(term in str(item.get("text") or "") for item in must_not_items)
    )
    risk_raw += min(20, risk_hits * 4)
    if constraint_total <= 0:
        risk_raw = min(risk_raw, 48)

    action_terms = (
        "分析",
        "拆解",
        "验证",
        "检查",
        "输出",
        "给出",
        "澄清",
        "评估",
        "记录",
        "复盘",
    )
    action_hits = sum(1 for term in action_terms if term in f"{goal_text}\n{duty_blob}")
    operability_raw = 30 + min(42, duty_count * 12) + min(20, action_hits * 3)
    if len(goal_text) >= 16:
        operability_raw += 8
    if vague_hits >= 3:
        operability_raw -= 16
    elif vague_hits >= 1:
        operability_raw -= 8

    score_dimensions = {
        "completeness": _dimension(
            key="completeness",
            label="完整性",
            raw_score=completeness_raw,
            evidence_refs=[
                {"ref": "role", "snippet": role_evidence},
                {"ref": "goal", "snippet": goal_evidence},
                {"ref": "duty", "snippet": duty_evidence},
            ],
            deduction_reason="角色/目标/职责字段不完整，信息覆盖不足。",
            repair_suggestion="补充 AGENTS.md 中“角色定位 / 会话目标 / 职责边界”三段基础内容。",
        ),
        "executability": _dimension(
            key="executability",
            label="可执行边界",
            raw_score=executability_raw,
            evidence_refs=(
                [{"ref": "must", "snippet": str(item.get("evidence") or "")} for item in must_items]
                + [{"ref": "must_not", "snippet": str(item.get("evidence") or "")} for item in must_not_items]
                + [{"ref": "preconditions", "snippet": str(item.get("evidence") or "")} for item in pre_items]
            ),
            deduction_reason="能做/不能做边界不清晰，职责边界条目不足或存在冲突。",
            repair_suggestion="在 AGENTS.md 新增/完善“职责边界（must/must_not/preconditions）”章节。",
        ),
        "consistency": _dimension(
            key="consistency",
            label="一致性",
            raw_score=consistency_raw,
            evidence_refs=[
                {"ref": "duty", "snippet": duty_evidence},
                {"ref": "constraints", "snippet": "\n".join(constraint_conflicts)},
            ],
            deduction_reason="角色、目标或职责间存在冲突描述。",
            repair_suggestion="统一 AGENTS.md 中角色目标和职责描述，删除互相矛盾条目。",
        ),
        "traceability": _dimension(
            key="traceability",
            label="可追溯性",
            raw_score=traceability_raw,
            evidence_refs=(
                [
                    {"ref": "role", "snippet": role_evidence},
                    {"ref": "goal", "snippet": goal_evidence},
                    {"ref": "duty", "snippet": duty_evidence},
                ]
                + [{"ref": "constraints", "snippet": text} for text in constraints_evidence[:4]]
            ),
            deduction_reason="评分依据无法稳定映射到 AGENTS.md 原文证据。",
            repair_suggestion="将关键限制条目改为清晰列表，并在同段补充可定位描述。",
        ),
        "risk_coverage": _dimension(
            key="risk_coverage",
            label="风险覆盖度",
            raw_score=risk_raw,
            evidence_refs=(
                [{"ref": "must_not", "snippet": str(item.get("evidence") or "")} for item in must_not_items]
                + [{"ref": "duty", "snippet": duty_evidence}]
            ),
            deduction_reason="高风险行为约束覆盖不足，禁止项不充分。",
            repair_suggestion="补充 AGENTS.md 中禁止项（must_not），明确高风险操作处理边界。",
        ),
        "operability": _dimension(
            key="operability",
            label="可操作性",
            raw_score=operability_raw,
            evidence_refs=[
                {"ref": "goal", "snippet": goal_evidence},
                {"ref": "duty", "snippet": duty_evidence},
            ],
            deduction_reason="目标和职责可执行指令不足，难以直接指导会话行为。",
            repair_suggestion="将职责边界改写为可执行动作列表（动词 + 条件 + 输出）。",
        ),
    }

    total_score = 0.0
    for key, _label in POLICY_SCORE_DIMENSION_META:
        dim = score_dimensions.get(key) or {}
        total_score += float(POLICY_SCORE_WEIGHTS.get(key) or 0.0) * float(dim.get("score") or 0.0)
    clarity_score = _safe_score(int(round(total_score)))
    if status == "incomplete":
        clarity_score = _safe_score(clarity_score - 6)
    if len(warnings) >= 2:
        clarity_score = _safe_score(clarity_score - 3)

    manual_review_required = any(
        bool((score_dimensions.get(key) or {}).get("manual_review_required"))
        for key, _label in POLICY_SCORE_DIMENSION_META
    )

    issue_codes = {
        str(item.get("code") or "").strip().lower()
        for item in constraint_issues
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    }
    constraints_block_auto = bool(
        constraint_total <= 0
        or missing_evidence_count > 0
        or bool(constraint_conflicts)
        or "constraints_missing" in issue_codes
        or "constraints_evidence_missing" in issue_codes
        or "constraints_conflict" in issue_codes
    )

    if status == "failed" or clarity_score < POLICY_CLARITY_CONFIRM_THRESHOLD:
        gate = "block"
    elif status == "incomplete" or clarity_score < POLICY_CLARITY_AUTO_THRESHOLD:
        gate = "confirm"
    else:
        gate = "auto"
    if gate == "auto" and (constraints_block_auto or manual_review_required):
        gate = "confirm"

    gate_reason = ""
    if gate == "block":
        if status == "failed":
            gate_reason = "parse_failed"
        else:
            gate_reason = "score_below_60"
    elif gate == "confirm":
        if status == "incomplete":
            gate_reason = "parse_incomplete"
        elif constraints_block_auto:
            if "constraints_conflict" in issue_codes or constraint_conflicts:
                gate_reason = "constraints_conflict"
            elif "constraints_evidence_missing" in issue_codes or missing_evidence_count > 0:
                gate_reason = "constraints_evidence_missing"
            else:
                gate_reason = "constraints_missing"
        elif manual_review_required:
            gate_reason = "score_evidence_insufficient"
        else:
            gate_reason = "score_60_79"

    risk_tips: list[str] = []
    if status == "incomplete":
        risk_tips.append("策略提取不完整，存在职责漂移风险。")
    if status == "failed":
        risk_tips.append("策略提取失败，无法保证会话与训练一致约束。")
    if gate != "auto":
        risk_tips.append("清晰度不足或证据不充分，建议人工确认后再执行任务。")
    for key, label in POLICY_SCORE_DIMENSION_META:
        dim = score_dimensions.get(key) or {}
        reason_text = str(dim.get("deduction_reason") or "").strip()
        if not reason_text:
            continue
        if dim.get("status") == "low":
            risk_tips.append(f"{label}偏低：{reason_text}")
        elif dim.get("status") == "manual_review":
            risk_tips.append(f"{label}待人工确认：{reason_text}")
    for item in constraint_issues:
        message = str((item or {}).get("message") or "").strip()
        if message and message not in risk_tips:
            risk_tips.append(message)
    for conflict_text in constraint_conflicts:
        if conflict_text and conflict_text not in risk_tips:
            risk_tips.append(conflict_text)
    for code in warnings:
        text = policy_warning_text(code)
        if text and text not in risk_tips:
            risk_tips.append(text)

    completeness = int((score_dimensions.get("completeness") or {}).get("score") or 0)
    executability = int((score_dimensions.get("executability") or {}).get("score") or 0)
    consistency = int((score_dimensions.get("consistency") or {}).get("score") or 0)
    traceability = int((score_dimensions.get("traceability") or {}).get("score") or 0)
    risk_coverage = int((score_dimensions.get("risk_coverage") or {}).get("score") or 0)
    operability = int((score_dimensions.get("operability") or {}).get("score") or 0)

    return {
        "score_model": POLICY_SCORE_MODEL,
        "score_total": clarity_score,
        "score_weights": dict(POLICY_SCORE_WEIGHTS),
        "score_dimensions": score_dimensions,
        "clarity_score": clarity_score,
        "clarity_details": {
            # 兼容旧字段
            "completeness": completeness,
            "specificity": int(round((executability + operability) / 2.0)),
            "consistency": consistency,
            "traceability": traceability,
            # 新增字段
            "executability": executability,
            "risk_coverage": risk_coverage,
            "operability": operability,
        },
        "clarity_gate": gate,
        "clarity_gate_reason": gate_reason,
        "risk_tips": risk_tips,
    }


def extract_agent_policy_fields(
    markdown_text: str,
    *,
    max_chars: int = 2400,
) -> dict[str, Any]:
    text = str(markdown_text or "")
    sections = parse_markdown_sections(text)
    if not text.strip():
        clarity = compute_policy_clarity(
            role_profile="",
            session_goal="",
            duty_constraints=[],
            parse_status="failed",
            parse_warnings=["agents_md_empty"],
            evidence_snippets={"role": "", "goal": "", "duty": ""},
        )
        return {
            "role_profile": "",
            "session_goal": "",
            "duty_constraints": [],
            "duty_constraints_text": "",
            "parse_status": "failed",
            "parse_warnings": ["agents_md_empty"],
            "evidence_snippets": {"role": "", "goal": "", "duty": ""},
            **clarity,
        }

    warnings: list[str] = []
    role_section = find_first_section_by_headings(sections, _AGENT_ROLE_HEADINGS)
    goal_section = find_first_section_by_headings(sections, _AGENT_GOAL_HEADINGS)
    duty_sections = find_sections_by_headings(sections, _AGENT_DUTY_HEADINGS, limit=3)

    role_profile = ""
    if role_section:
        role_profile = summarize_section_content(
            role_section[2],
            max_chars=min(max_chars, 720),
            max_lines=4,
        )
    else:
        warnings.append("missing_role_section")

    session_goal = ""
    if goal_section:
        session_goal = summarize_section_content(
            goal_section[2],
            max_chars=min(max_chars, 520),
            max_lines=3,
        )
    else:
        warnings.append("missing_goal_section")
        if role_profile:
            inferred = first_non_empty_sentence(role_profile, max_chars=120)
            if inferred:
                session_goal = f"围绕角色定位提供需求分析与澄清能力：{inferred}"
                warnings.append("goal_inferred_from_role_profile")

    duty_items: list[str] = []
    if duty_sections:
        merged_blocks = []
        for section in duty_sections:
            merged_blocks.append(section[2])
        duty_items = extract_list_items_from_text(
            "\n".join(merged_blocks),
            max_items=12,
        )
        if not duty_items:
            warnings.append("empty_duty_constraints")
    else:
        warnings.append("missing_duty_section")

    duty_items = [policy_text_compact(item, max_chars=280) for item in duty_items if str(item or "").strip()]
    duty_text = policy_text_compact("\n".join(duty_items), max_chars=max_chars) if duty_items else ""

    has_required = bool(role_profile and session_goal and duty_items)
    if has_required:
        structural_missing = any(
            code in warnings for code in ("missing_role_section", "missing_goal_section", "missing_duty_section")
        )
        parse_status = "incomplete" if structural_missing else "ok"
    else:
        parse_status = "failed" if not (role_profile or session_goal or duty_items) else "incomplete"
        if "missing_required_policy_fields" not in warnings:
            warnings.append("missing_required_policy_fields")

    duty_evidence_parts: list[str] = []
    for section in duty_sections:
        snippet = section_evidence_snippet(section)
        if snippet:
            duty_evidence_parts.append(snippet)
    evidence_snippets = {
        "role": section_evidence_snippet(role_section),
        "goal": section_evidence_snippet(goal_section),
        "duty": policy_text_compact("\n\n".join(duty_evidence_parts), max_chars=680) if duty_evidence_parts else "",
    }
    constraints = extract_constraints_from_policy(
        sections=sections,
        duty_items=duty_items,
    )
    for issue in (constraints.get("issues") or []):
        code = str((issue or {}).get("code") or "").strip()
        if code and code not in warnings:
            warnings.append(code)
    clarity = compute_policy_clarity(
        role_profile=role_profile,
        session_goal=session_goal,
        duty_constraints=duty_items,
        parse_status=parse_status,
        parse_warnings=warnings,
        evidence_snippets=evidence_snippets,
        constraints=constraints,
    )

    return {
        "role_profile": role_profile,
        "session_goal": session_goal,
        "duty_constraints": duty_items,
        "duty_constraints_text": duty_text,
        "constraints": constraints,
        "parse_status": parse_status,
        "parse_warnings": warnings,
        "evidence_snippets": evidence_snippets,
        **clarity,
    }


def extract_agent_duty_info(
    markdown_text: str,
    *,
    max_sections: int = 2,
    max_chars: int = 2400,
) -> tuple[str, str, str, bool]:
    text = str(markdown_text or "")
    if not text.strip():
        return "", "", "", False

    sections = parse_markdown_sections(text)

    selected_indexes: list[int] = []
    for keyword in _AGENT_DUTY_KEYWORDS:
        for idx, (title, _level, content) in enumerate(sections):
            if not content:
                continue
            if keyword in title and idx not in selected_indexes:
                selected_indexes.append(idx)
    if not selected_indexes:
        for idx, (_title, _level, content) in enumerate(sections):
            if content:
                selected_indexes.append(idx)
                break

    picked = [sections[idx] for idx in selected_indexes[:max_sections] if idx < len(sections)]
    if not picked:
        fallback = re.sub(r"^\s*#\s*", "", text.strip(), count=1)
        collapsed = re.sub(r"\s+", " ", fallback).strip()
        excerpt = collapsed[:96] + ("..." if len(collapsed) > 96 else "")
        if len(fallback) > max_chars:
            return "AGENTS 摘要", excerpt, fallback[:max_chars].rstrip() + "\n...(已截断)", True
        return "AGENTS 摘要", excerpt, fallback, False

    title = " / ".join([item[0] for item in picked]).strip()
    blocks = []
    for sec_title, _sec_level, content in picked:
        blocks.append(sec_title + "\n" + content)
    full = "\n\n".join(blocks).strip()
    truncated = False
    if len(full) > max_chars:
        full = full[:max_chars].rstrip() + "\n...(已截断)"
        truncated = True
    collapsed = re.sub(r"\s+", " ", full).strip()
    excerpt = collapsed[:120] + ("..." if len(collapsed) > 120 else "")
    return title, excerpt, full, truncated


def build_agent_policy_payload_via_codex(
    *,
    runtime_root: Path,
    workspace_root: Path,
    agent_name: str,
    agents_file: Path,
    agents_hash: str,
    agents_version: str,
) -> dict[str, Any]:
    # Avoid importing from policy_analysis facade, which re-exports runtime symbols
    # and can recurse back into this function.
    from ..services.policy_fallback_service import (
        build_agent_policy_payload_via_codex as _build_agent_policy_payload_via_codex,
    )

    return _build_agent_policy_payload_via_codex(
        runtime_root=runtime_root,
        workspace_root=workspace_root,
        agent_name=agent_name,
        agents_file=agents_file,
        agents_hash=agents_hash,
        agents_version=agents_version,
    )
