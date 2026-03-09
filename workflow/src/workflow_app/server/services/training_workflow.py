from __future__ import annotations

from . import training_workflow_execution_service as _execution_service


def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    globals().update(symbols)
    _execution_service.bind_runtime_symbols(globals())

def detect_context_gap(records: list[dict[str, Any]]) -> str:
    if not records:
        return "no_training_value"
    first_role = str(records[0].get("role") or "")
    last_role = str(records[-1].get("role") or "")
    if first_role == "assistant":
        return "missing_previous_context"
    if last_role == "user":
        return "missing_next_context"
    return ""


def sync_training_workflows(root: Path) -> int:
    conn = connect_db(root)
    created = 0
    try:
        rows = conn.execute(
            """
            SELECT analysis_id, session_id, created_at, updated_at
            FROM analysis_tasks
            ORDER BY created_at ASC
            """
        ).fetchall()
        for row in rows:
            analysis_id = str(row["analysis_id"])
            session_id = str(row["session_id"])
            if not session_has_work_records(conn, session_id):
                continue
            created_at = str(row["created_at"] or iso_ts(now_local()))
            updated_at = str(row["updated_at"] or created_at)
            workflow_id = workflow_id_for_analysis(analysis_id)
            ret = conn.execute(
                """
                INSERT OR IGNORE INTO training_workflows (
                    workflow_id,analysis_id,session_id,status,created_at,updated_at
                ) VALUES (?,?,?,?,?,?)
                """,
                (workflow_id, analysis_id, session_id, "queued", created_at, updated_at),
            )
            created += int(ret.rowcount > 0)
            conn.execute(
                """
                UPDATE training_workflows
                SET session_id=?
                WHERE analysis_id=?
                  AND COALESCE(session_id,'')=''
                """,
                (session_id, analysis_id),
            )
        conn.commit()
        return created
    finally:
        conn.close()


def list_training_workflows(
    root: Path,
    limit: int = 300,
    *,
    include_test_data: bool = True,
) -> list[dict[str, Any]]:
    sync_training_workflows(root)
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT
                w.workflow_id,
                w.analysis_id,
                w.session_id,
                COALESCE(s.is_test_data,0) AS is_test_data,
                w.status AS workflow_status,
                w.assigned_analyst,
                w.assignment_note,
                w.analysis_summary,
                w.analysis_recommendation,
                w.latest_analysis_run_id,
                w.latest_no_value_reason,
                w.plan_json,
                w.selected_plan_json,
                w.train_result_ref,
                w.train_result_summary,
                w.updated_at,
                w.created_at,
                a.status AS analysis_status,
                a.decision,
                a.decision_reason,
                t.training_id,
                t.status AS training_status,
                t.trainer_run_ref,
                t.result_summary,
                t.last_error,
                (
                    SELECT COUNT(1)
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role IN ('user','assistant')
                      AND TRIM(COALESCE(m.content,''))<>''
                ) AS work_record_count,
                (
                    SELECT content
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role='user'
                      AND TRIM(COALESCE(m.content,''))<>''
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS latest_user_message,
                (
                    SELECT content
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role='assistant'
                      AND TRIM(COALESCE(m.content,''))<>''
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS latest_assistant_message
            FROM training_workflows w
            JOIN analysis_tasks a ON a.analysis_id = w.analysis_id
            LEFT JOIN chat_sessions s ON s.session_id = w.session_id
            LEFT JOIN training_tasks t ON t.analysis_id = w.analysis_id
            WHERE EXISTS (
                SELECT 1
                FROM conversation_messages m
                WHERE m.session_id = w.session_id
                  AND m.role IN ('user','assistant')
                  AND TRIM(COALESCE(m.content,''))<>''
            )
              AND (?=1 OR COALESCE(s.is_test_data,0)=0)
            ORDER BY w.updated_at DESC, w.created_at DESC
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
            item["plan"] = parse_json_list(item.get("plan_json"))
            item["selected_plan"] = parse_json_list(item.get("selected_plan_json"))
            session_id = str(item.get("session_id") or "")
            workflow_id = str(item.get("workflow_id") or "")
            records = list_session_work_records(root, session_id, limit=60)
            item["work_records"] = records
            item["work_record_preview"] = work_record_preview(records)
            item["work_record_count"] = int(item.get("work_record_count") or len(records))
            item["training_plan_item_count"] = max(
                workflow_plan_item_count(item.get("plan_json")),
                workflow_plan_item_count(item.get("selected_plan_json")),
            )
            item.update(session_analysis_gate(root, session_id))
            latest_run = latest_analysis_run(root, workflow_id)
            if latest_run:
                item["latest_analysis_run_id"] = str(latest_run.get("analysis_run_id") or "")
                item["latest_no_value_reason"] = str(latest_run.get("no_value_reason") or "")
            else:
                item["latest_analysis_run_id"] = ""
                item["latest_no_value_reason"] = ""
            out.append(item)
        return out
    finally:
        conn.close()


def get_training_workflow(root: Path, workflow_id: str) -> dict[str, Any] | None:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT
                w.workflow_id,
                w.analysis_id,
                w.session_id,
                COALESCE(s.is_test_data,0) AS is_test_data,
                w.status AS workflow_status,
                w.assigned_analyst,
                w.assignment_note,
                w.analysis_summary,
                w.analysis_recommendation,
                w.latest_analysis_run_id,
                w.latest_no_value_reason,
                w.plan_json,
                w.selected_plan_json,
                w.train_result_ref,
                w.train_result_summary,
                w.updated_at,
                w.created_at,
                a.status AS analysis_status,
                a.decision,
                a.decision_reason,
                t.training_id,
                t.status AS training_status,
                t.trainer_run_ref,
                t.result_summary,
                t.last_error,
                (
                    SELECT COUNT(1)
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role IN ('user','assistant')
                      AND TRIM(COALESCE(m.content,''))<>''
                ) AS work_record_count,
                (
                    SELECT content
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role='user'
                      AND TRIM(COALESCE(m.content,''))<>''
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS latest_user_message,
                (
                    SELECT content
                    FROM conversation_messages m
                    WHERE m.session_id = w.session_id
                      AND m.role='assistant'
                      AND TRIM(COALESCE(m.content,''))<>''
                    ORDER BY m.message_id DESC
                    LIMIT 1
                ) AS latest_assistant_message
            FROM training_workflows w
            JOIN analysis_tasks a ON a.analysis_id = w.analysis_id
            LEFT JOIN chat_sessions s ON s.session_id = w.session_id
            LEFT JOIN training_tasks t ON t.analysis_id = w.analysis_id
            WHERE w.workflow_id=?
            LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        if not row:
            return None
        out = {k: row[k] for k in row.keys()}
        out["is_test_data"] = bool(int(out.get("is_test_data") or 0))
        out["plan"] = parse_json_list(out.get("plan_json"))
        out["selected_plan"] = parse_json_list(out.get("selected_plan_json"))
        session_id = str(out.get("session_id") or "")
        workflow_id = str(out.get("workflow_id") or "")
        records = list_session_work_records(root, session_id, limit=2000)
        out["work_records"] = records
        out["work_record_preview"] = work_record_preview(records)
        out["work_record_count"] = int(out.get("work_record_count") or len(records))
        out["training_plan_item_count"] = max(
            workflow_plan_item_count(out.get("plan_json")),
            workflow_plan_item_count(out.get("selected_plan_json")),
        )
        out.update(session_analysis_gate(root, session_id))
        latest_run = latest_analysis_run(root, workflow_id)
        if latest_run:
            out["latest_analysis_run_id"] = str(latest_run.get("analysis_run_id") or "")
            out["latest_no_value_reason"] = str(latest_run.get("no_value_reason") or "")
        else:
            out["latest_analysis_run_id"] = ""
            out["latest_no_value_reason"] = ""
        return out
    finally:
        conn.close()


def update_training_workflow_fields(root: Path, workflow_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    allowed = {
        "status",
        "assigned_analyst",
        "assignment_note",
        "analysis_summary",
        "analysis_recommendation",
        "latest_analysis_run_id",
        "latest_no_value_reason",
        "plan_json",
        "selected_plan_json",
        "train_result_ref",
        "train_result_summary",
        "session_id",
    }
    values: list[Any] = []
    sets: list[str] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        sets.append(f"{key}=?")
        values.append(value)
    if not sets:
        return
    sets.append("updated_at=?")
    values.append(iso_ts(now_local()))
    values.append(workflow_id)
    conn = connect_db(root)
    try:
        conn.execute(
            f"UPDATE training_workflows SET {','.join(sets)} WHERE workflow_id=?",
            values,
        )
        conn.commit()
    finally:
        conn.close()


def load_workflow_session_policy_snapshot(root: Path, workflow: dict[str, Any]) -> dict[str, Any]:
    session_id = str(workflow.get("session_id") or "")
    if not session_id:
        raise WorkflowGateError(
            409,
            "workflow missing session_id",
            AGENT_POLICY_ERROR_CODE,
            extra={"workflow_id": str(workflow.get("workflow_id") or ""), "session_id": ""},
        )
    session = get_session(root, session_id)
    if not session:
        raise WorkflowGateError(
            404,
            "session not found for workflow",
            "session_not_found",
            extra={"workflow_id": str(workflow.get("workflow_id") or ""), "session_id": session_id},
        )
    try:
        return ensure_session_policy_snapshot(root, session)
    except SessionGateError as exc:
        raise WorkflowGateError(
            exc.status_code,
            str(exc),
            AGENT_POLICY_ERROR_CODE,
            extra={
                "workflow_id": str(workflow.get("workflow_id") or ""),
                "session_id": session_id,
                **exc.extra,
            },
        ) from exc


def policy_alignment_payload(
    snapshot: dict[str, Any] | None,
    *,
    stage: str,
) -> dict[str, Any]:
    if not snapshot:
        return {
            "policy_alignment": POLICY_ALIGNMENT_DEVIATED,
            "policy_alignment_reason": "session_policy_missing",
            "policy_stage": stage,
            "policy_source_type": "auto",
            "policy_source": {
                "policy_source": "auto",
                "agents_hash": "",
                "agents_version": "",
                "agents_path": "",
            },
        }
    source = snapshot.get("source") if isinstance(snapshot.get("source"), dict) else {}
    source_type = session_policy_source_type(snapshot)
    return {
        "policy_alignment": POLICY_ALIGNMENT_ALIGNED,
        "policy_alignment_reason": "session_policy_injected",
        "policy_stage": stage,
        "policy_summary": session_policy_summary(snapshot),
        "policy_source_type": source_type,
        "policy_source": {
            "policy_source": source_type,
            "agents_hash": str((source or {}).get("agents_hash") or ""),
            "agents_version": str((source or {}).get("agents_version") or ""),
            "agents_path": str((source or {}).get("agents_path") or ""),
        },
    }


def append_training_workflow_event(
    root: Path,
    workflow: dict[str, Any],
    stage: str,
    status: str,
    payload: dict[str, Any],
    *,
    policy_snapshot: dict[str, Any] | None = None,
) -> int:
    workflow_id = str(workflow.get("workflow_id") or "")
    analysis_id = str(workflow.get("analysis_id") or "")
    session_id = str(workflow.get("session_id") or "")
    created_at = iso_ts(now_local())
    snapshot_obj = policy_snapshot
    if snapshot_obj is None and session_id:
        session = get_session(root, session_id)
        if session:
            try:
                snapshot_obj = ensure_session_policy_snapshot(root, session)
            except SessionGateError:
                snapshot_obj = None
    payload_obj = dict(payload or {})
    for key, value in policy_alignment_payload(snapshot_obj, stage=stage).items():
        payload_obj.setdefault(key, value)
    conn = connect_db(root)
    try:
        ret = conn.execute(
            """
            INSERT INTO training_workflow_events (
                workflow_id,analysis_id,session_id,stage,status,payload_json,created_at
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (
                workflow_id,
                analysis_id,
                session_id,
                stage,
                status,
                json.dumps(payload_obj, ensure_ascii=False),
                created_at,
            ),
        )
        conn.commit()
        event_num = int(ret.lastrowid or 0)
    finally:
        conn.close()
    persist_event(
        root,
        {
            "event_id": event_id(),
            "timestamp": created_at,
            "session_id": session_id or "sess-training",
            "actor": "workflow",
            "stage": "training_workflow",
            "action": stage,
            "status": status,
            "latency_ms": 0,
            "task_id": workflow_id,
            "reason_tags": [
                status,
                f"policy_alignment:{str(payload_obj.get('policy_alignment') or POLICY_ALIGNMENT_DEVIATED)}",
                f"policy_reason:{str(payload_obj.get('policy_alignment_reason') or 'unknown')}",
                f"policy_source:{str(payload_obj.get('policy_source_type') or 'auto')}",
            ],
            "ref": relative_to_root(root, event_file(root)),
        },
    )
    return event_num


def list_training_workflow_events(
    root: Path,
    workflow_id: str,
    *,
    since_id: int = 0,
    limit: int = 400,
) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT event_id,workflow_id,analysis_id,session_id,stage,status,payload_json,created_at
            FROM training_workflow_events
            WHERE workflow_id=? AND event_id>?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (workflow_id, max(0, since_id), max(1, min(limit, 2000))),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            payload: dict[str, Any]
            try:
                raw_payload = json.loads(str(row["payload_json"]))
                payload = raw_payload if isinstance(raw_payload, dict) else {}
            except Exception:
                payload = {}
            out.append(
                {
                    "event_id": int(row["event_id"]),
                    "workflow_id": str(row["workflow_id"]),
                    "analysis_id": str(row["analysis_id"]),
                    "session_id": str(row["session_id"]),
                    "stage": str(row["stage"]),
                    "status": str(row["status"]),
                    "payload": payload,
                    "created_at": str(row["created_at"]),
                }
            )
        return out
    finally:
        conn.close()


def build_analysis_snapshot_with_context(
    root: Path,
    session_id: str,
    *,
    policy_snapshot: dict[str, Any] | None = None,
) -> tuple[str, str, list[str], list[int], str]:
    records = list_session_dialogue_messages(root, session_id, limit=0)
    user_msgs = [str(item.get("content") or "").strip() for item in records if item.get("role") == "user"]
    assistant_msgs = [item for item in records if item.get("role") == "assistant"]
    latest_user = [text for text in user_msgs if text][-3:]
    target_message_ids = [
        int(item.get("message_id") or 0)
        for item in records
        if str(item.get("analysis_state") or ANALYSIS_STATE_PENDING) != ANALYSIS_STATE_DONE
    ]
    gap_reason = detect_context_gap(records)
    recommendation = "train" if len(user_msgs) >= 1 else "skip"
    no_value_reason = ""
    if gap_reason in {"missing_previous_context", "missing_next_context"}:
        recommendation = "skip"
        no_value_reason = gap_reason
    elif not user_msgs:
        recommendation = "skip"
        no_value_reason = "no_training_value"
    elif all(len(text) <= 2 for text in user_msgs if text):
        recommendation = "skip"
        no_value_reason = "no_training_value"
    summary_parts = [
        f"context_mode=full_session",
        f"message_count={len(records)}",
        f"user_turns={len(user_msgs)}",
        f"assistant_turns={len(assistant_msgs)}",
        f"target_unanalyzed={len(target_message_ids)}",
        f"latest_user={' | '.join(latest_user) if latest_user else 'none'}",
        f"context_gap={gap_reason or 'none'}",
    ]
    if policy_snapshot:
        source = policy_snapshot.get("source") if isinstance(policy_snapshot.get("source"), dict) else {}
        source_type = session_policy_source_type(policy_snapshot)
        summary_parts.extend(
            [
                f"policy_goal={first_non_empty_sentence(str(policy_snapshot.get('session_goal') or ''), max_chars=80)}",
                f"policy_alignment={POLICY_ALIGNMENT_ALIGNED}",
                f"policy_source={source_type}",
                f"policy_source_version={str((source or {}).get('agents_version') or '')}",
            ]
        )
    else:
        summary_parts.append(f"policy_alignment={POLICY_ALIGNMENT_DEVIATED}")
    return "; ".join(summary_parts), recommendation, latest_user, target_message_ids, no_value_reason


def build_analysis_snapshot(root: Path, session_id: str) -> tuple[str, str, list[str]]:
    summary, recommendation, latest_user, _target_message_ids, _no_value_reason = (
        build_analysis_snapshot_with_context(root, session_id)
    )
    return summary, recommendation, latest_user


def build_training_plan(
    summary: str,
    recommendation: str,
    latest_user: list[str],
    *,
    message_ids: list[int],
    no_value_reason: str = "",
    policy_summary_text_value: str = "",
) -> list[dict[str, Any]]:
    if no_value_reason:
        return []
    latest = " / ".join(latest_user) if latest_user else "no recent user turns"
    train_selected = recommendation == "train"
    skip_selected = recommendation != "train"
    evidence_ids: list[int] = []
    for raw in message_ids:
        try:
            num = int(raw)
        except Exception:
            continue
        if num > 0:
            evidence_ids.append(num)
    return [
        {
            "item_id": "decision_train",
            "title": "判定入训（train）",
            "description": f"依据分析摘要执行 train。summary={summary}; policy={policy_summary_text_value or 'none'}",
            "selected": train_selected,
            "kind": "decision",
            "decision": "train",
            "message_ids": evidence_ids,
            "policy_summary": policy_summary_text_value,
        },
        {
            "item_id": "decision_skip",
            "title": "判定跳过（skip）",
            "description": f"当前不进入训练，保留追踪记录。policy={policy_summary_text_value or 'none'}",
            "selected": skip_selected,
            "kind": "decision",
            "decision": "skip",
            "message_ids": evidence_ids,
            "policy_summary": policy_summary_text_value,
        },
        {
            "item_id": "execute_training",
            "title": "执行训练并回写",
            "description": f"触发训练执行并写入 trainer_run_ref。policy={policy_summary_text_value or 'none'}",
            "selected": train_selected,
            "kind": "train",
            "message_ids": evidence_ids,
            "policy_summary": policy_summary_text_value,
        },
        {
            "item_id": "collect_notes",
            "title": "沉淀分析记录",
            "description": f"最近上下文：{latest}；policy={policy_summary_text_value or 'none'}",
            "selected": True,
            "kind": "record",
            "message_ids": evidence_ids,
            "policy_summary": policy_summary_text_value,
        },
    ]


def apply_analysis_decision(root: Path, workflow: dict[str, Any], decision: str, reason: str) -> dict[str, Any]:
    analysis_id = str(workflow.get("analysis_id") or "")
    session_id = str(workflow.get("session_id") or "")
    if decision not in {"train", "skip", "need_info"}:
        raise RuntimeError(f"invalid decision: {decision}")
    ts = now_local()
    status = decision_to_status(decision)
    training_id = ""
    conn = connect_db(root)
    try:
        conn.execute(
            """
            UPDATE analysis_tasks
            SET status=?, decision=?, decision_reason=?, updated_at=?
            WHERE analysis_id=?
            """,
            (
                status,
                decision,
                reason,
                iso_ts(ts),
                analysis_id,
            ),
        )
        if decision == "train":
            training_id = create_training_id(analysis_id)
            conn.execute(
                """
                INSERT OR IGNORE INTO training_tasks (
                    training_id,analysis_id,status,attempts,created_at,updated_at
                ) VALUES (?,?, 'pending', 0, ?, ?)
                """,
                (training_id, analysis_id, iso_ts(ts), iso_ts(ts)),
            )
        conn.commit()
    finally:
        conn.close()

    decision_ref = append_decision_log(
        root,
        ts,
        analysis_id=analysis_id,
        session_id=session_id,
        decision=decision,
        reason=reason,
    )
    persist_event(
        root,
        {
            "event_id": event_id(),
            "timestamp": iso_ts(ts),
            "session_id": session_id,
            "actor": "workflow",
            "stage": "analyze",
            "action": "decision",
            "status": "success",
            "latency_ms": 0,
            "task_id": analysis_id,
            "reason_tags": [decision],
            "ref": decision_ref,
        },
    )
    return {"analysis_status": status, "decision_ref": decision_ref, "training_id": training_id}

def run_training_once_for_analysis(
    root: Path,
    analysis_id: str,
    *,
    max_retries: int,
) -> dict[str, Any]:
    return _execution_service.run_training_once_for_analysis(
        root,
        analysis_id,
        max_retries=max_retries,
    )


def run_analysis_worker(cfg: AppConfig, state: RuntimeState, workflow_id: str) -> None:
    _execution_service.run_analysis_worker(cfg, state, workflow_id)


def start_analysis_worker(cfg: AppConfig, state: RuntimeState, workflow_id: str) -> bool:
    return _execution_service.start_analysis_worker(cfg, state, workflow_id)


def assign_training_workflow(
    cfg: AppConfig,
    state: RuntimeState,
    workflow_id: str,
    analyst: str,
    note: str = "",
) -> dict[str, Any]:
    return _execution_service.assign_training_workflow(cfg, state, workflow_id, analyst, note)


def generate_training_workflow_plan(cfg: AppConfig, workflow_id: str) -> dict[str, Any]:
    return _execution_service.generate_training_workflow_plan(cfg, workflow_id)


def execute_training_workflow_plan(
    cfg: AppConfig,
    workflow_id: str,
    selected_items: list[str],
    *,
    max_retries: int,
) -> dict[str, Any]:
    return _execution_service.execute_training_workflow_plan(
        cfg,
        workflow_id,
        selected_items,
        max_retries=max_retries,
    )
