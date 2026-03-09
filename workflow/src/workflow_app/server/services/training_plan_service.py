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

def _detect_similar_training_plans(
    conn: sqlite3.Connection,
    *,
    target_agent_id: str,
    capability_goal: str,
    training_tasks: list[str],
    acceptance_criteria: str,
    is_test_data: bool = False,
) -> tuple[int, list[str]]:
    test_flag = 1 if is_test_data else 0
    rows = conn.execute(
        """
        SELECT
            p.plan_id,
            p.capability_goal,
            p.training_tasks_json,
            p.acceptance_criteria
        FROM training_plan p
        INNER JOIN training_queue q ON q.plan_id=p.plan_id
        WHERE p.target_agent_id=?
          AND q.status <> 'removed'
          AND COALESCE(p.is_test_data,0)=?
        ORDER BY p.created_at DESC
        LIMIT 120
        """,
        (target_agent_id, test_flag),
    ).fetchall()
    similar_ids: list[str] = []
    for row in rows:
        try:
            existed_tasks = json.loads(str(row["training_tasks_json"] or "[]"))
            if not isinstance(existed_tasks, list):
                existed_tasks = []
        except Exception:
            existed_tasks = []
        if training_plan_similarity_hit(
            candidate_goal=capability_goal,
            candidate_tasks=training_tasks,
            candidate_criteria=acceptance_criteria,
            existing_goal=str(row["capability_goal"] or ""),
            existing_tasks=[str(item or "") for item in existed_tasks],
            existing_criteria=str(row["acceptance_criteria"] or ""),
        ):
            similar_ids.append(str(row["plan_id"] or ""))
    similar_ids = [pid for pid in similar_ids if pid][:8]
    return (1 if similar_ids else 0), similar_ids


def create_training_plan_and_enqueue(
    cfg: AppConfig,
    body: dict[str, Any],
    *,
    forced_source: str | None = None,
) -> dict[str, Any]:
    source = normalize_training_source(
        forced_source if forced_source is not None else body.get("source"),
        default="manual",
    )
    target_agent = str(
        body.get("target_agent_id")
        or body.get("target_agent")
        or body.get("agent_id")
        or body.get("agent_name")
        or ""
    ).strip()
    if not target_agent:
        raise TrainingCenterError(400, "target_agent 必填", "target_agent_required")

    capability_goal = str(body.get("capability_goal") or "").strip()
    if not capability_goal:
        raise TrainingCenterError(400, "capability_goal 必填", "capability_goal_required")
    training_tasks = normalize_training_tasks(body.get("training_tasks"))
    if not training_tasks:
        raise TrainingCenterError(400, "training_tasks 必填", "training_tasks_required")
    acceptance_criteria = str(body.get("acceptance_criteria") or "").strip()
    if not acceptance_criteria:
        raise TrainingCenterError(400, "acceptance_criteria 必填", "acceptance_criteria_required")
    priority = normalize_training_priority(body.get("priority"), required=True)
    operator = safe_token(str(body.get("operator") or "web-user"), "web-user", 80)
    created_by = safe_token(str(body.get("created_by") or operator), operator, 80)
    is_test_data = normalize_training_test_flag(
        body.get("is_test_data", body.get("isTestData")),
        default=False,
    )

    sync_training_agent_registry(cfg)
    conn = connect_db(cfg.root)
    try:
        agent = _resolve_training_agent(conn, target_agent)
        if agent is None:
            raise TrainingCenterError(
                404,
                "target agent not found",
                "target_agent_not_found",
                {"target_agent": target_agent},
            )
        target_agent_id = str(agent.get("agent_id") or "")
        target_agent_name = str(agent.get("agent_name") or "")
        training_gate_state = normalize_training_gate_state(agent.get("training_gate_state"))
        if training_gate_state == "frozen_switched":
            raise TrainingCenterError(
                409,
                "当前 agent 已冻结训练，请切回最新发布版本后再训练",
                "training_frozen_after_switch",
                {"target_agent_id": target_agent_id, "training_gate_state": training_gate_state},
            )

        similar_flag, similar_ids = _detect_similar_training_plans(
            conn,
            target_agent_id=target_agent_id,
            capability_goal=capability_goal,
            training_tasks=training_tasks,
            acceptance_criteria=acceptance_criteria,
            is_test_data=is_test_data,
        )
        plan_id_text = training_plan_id()
        queue_task_id_text = training_queue_task_id()
        ts = iso_ts(now_local())
        trainer_match = str(body.get("trainer_match") or "").strip()
        if not trainer_match:
            trainer_query = str(body.get("trainer_query") or "").strip()
            trainer_rows = discover_training_trainers(
                query=trainer_query or capability_goal,
                limit=20,
            )
            if trainer_rows:
                trainer_match = str(trainer_rows[0].get("trainer_name") or "").strip()

        conn.execute(
            """
            INSERT INTO training_plan (
                plan_id,source,target_agent_id,capability_goal,training_tasks_json,acceptance_criteria,priority,similar_flag,created_by,is_test_data,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                plan_id_text,
                source,
                target_agent_id,
                capability_goal,
                json.dumps(training_tasks, ensure_ascii=False),
                acceptance_criteria,
                priority,
                int(similar_flag),
                created_by,
                1 if is_test_data else 0,
                ts,
            ),
        )
        conn.execute(
            """
            INSERT INTO training_queue (
                queue_task_id,plan_id,priority,status,trainer_match,is_test_data,enqueued_at,started_at,finished_at
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                queue_task_id_text,
                plan_id_text,
                priority,
                "queued",
                trainer_match,
                1 if is_test_data else 0,
                ts,
                "",
                "",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    enqueue_audit_id = append_training_center_audit(
        cfg.root,
        action="enqueue",
        operator=operator,
        target_id=queue_task_id_text,
        detail={
            "plan_id": plan_id_text,
            "source": source,
            "target_agent_id": target_agent_id,
            "target_agent_name": target_agent_name,
            "priority": priority,
            "is_test_data": bool(is_test_data),
            "similar_flag": bool(similar_flag),
            "trainer_match": trainer_match,
        },
    )
    similar_audit_id = ""
    if similar_flag:
        similar_audit_id = append_training_center_audit(
            cfg.root,
            action="mark_similar",
            operator=operator,
            target_id=plan_id_text,
            detail={"similar_plan_ids": similar_ids},
        )

    return {
        "plan_id": plan_id_text,
        "queue_task_id": queue_task_id_text,
        "source": source,
        "target_agent_id": target_agent_id,
        "target_agent_name": target_agent_name,
        "target_agent_lifecycle_state": normalize_lifecycle_state(agent.get("lifecycle_state")),
        "target_agent_training_gate_state": normalize_training_gate_state(agent.get("training_gate_state")),
        "capability_goal": capability_goal,
        "training_tasks": training_tasks,
        "acceptance_criteria": acceptance_criteria,
        "priority": priority,
        "is_test_data": bool(is_test_data),
        "similar_flag": bool(similar_flag),
        "similar_plan_ids": similar_ids,
        "trainer_match": trainer_match,
        "can_execute": bool(trainer_match),
        "audit_ids": {
            "enqueue": enqueue_audit_id,
            "mark_similar": similar_audit_id,
        },
    }


def list_training_queue_items(
    root: Path,
    *,
    include_removed: bool = True,
    include_test_data: bool = True,
) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        sql = """
            SELECT
                q.queue_task_id,q.plan_id,q.priority,q.status,q.trainer_match,q.enqueued_at,q.started_at,q.finished_at,
                p.source,p.target_agent_id,p.capability_goal,p.training_tasks_json,p.acceptance_criteria,p.similar_flag,p.created_by,p.created_at,p.is_test_data,
                a.agent_name,a.lifecycle_state,a.training_gate_state,
                (
                    SELECT r.run_id
                    FROM training_run r
                    WHERE r.queue_task_id=q.queue_task_id
                    ORDER BY r.updated_at DESC
                    LIMIT 1
                ) AS latest_run_id,
                (
                    SELECT r.status
                    FROM training_run r
                    WHERE r.queue_task_id=q.queue_task_id
                    ORDER BY r.updated_at DESC
                    LIMIT 1
                ) AS latest_run_status,
                (
                    SELECT r.run_ref
                    FROM training_run r
                    WHERE r.queue_task_id=q.queue_task_id
                    ORDER BY r.updated_at DESC
                    LIMIT 1
                ) AS latest_run_ref,
                (
                    SELECT r.result_summary
                    FROM training_run r
                    WHERE r.queue_task_id=q.queue_task_id
                    ORDER BY r.updated_at DESC
                    LIMIT 1
                ) AS latest_result_summary,
                (
                    SELECT r.updated_at
                    FROM training_run r
                    WHERE r.queue_task_id=q.queue_task_id
                    ORDER BY r.updated_at DESC
                    LIMIT 1
                ) AS latest_run_updated_at
            FROM training_queue q
            INNER JOIN training_plan p ON p.plan_id=q.plan_id
            LEFT JOIN agent_registry a ON a.agent_id=p.target_agent_id
            {where_clause}
            ORDER BY
                CASE q.priority
                    WHEN 'P0' THEN 0
                    WHEN 'P1' THEN 1
                    WHEN 'P2' THEN 2
                    WHEN 'P3' THEN 3
                    ELSE 99
                END ASC,
                q.enqueued_at ASC
        """
        where_parts: list[str] = []
        params: list[Any] = []
        if not include_removed:
            where_parts.append("q.status <> 'removed'")
        if not include_test_data:
            where_parts.append("COALESCE(p.is_test_data,0)=0")
        where_clause = ""
        if where_parts:
            where_clause = "WHERE " + " AND ".join(where_parts)
        rows = conn.execute(sql.format(where_clause=where_clause), tuple(params)).fetchall()
    finally:
        conn.close()
    items: list[dict[str, Any]] = []
    for row in rows:
        tasks = []
        try:
            payload = json.loads(str(row["training_tasks_json"] or "[]"))
            if isinstance(payload, list):
                tasks = [str(item or "").strip() for item in payload if str(item or "").strip()]
        except Exception:
            tasks = []
        item = {name: row[name] for name in row.keys()}
        item["training_tasks"] = tasks
        item["is_test_data"] = bool(int(row["is_test_data"] or 0))
        item["similar_flag"] = bool(int(row["similar_flag"] or 0))
        item["priority_rank"] = TRAINING_PRIORITY_RANK.get(str(row["priority"] or "").upper(), 999)
        item["lifecycle_state"] = normalize_lifecycle_state(row["lifecycle_state"])
        item["training_gate_state"] = normalize_training_gate_state(row["training_gate_state"])
        item["can_execute"] = bool(
            str(row["trainer_match"] or "").strip()
            and item["training_gate_state"] != "frozen_switched"
        )
        items.append(item)
    return items


def remove_training_queue_item(
    root: Path,
    *,
    queue_task_id_text: str,
    operator: str,
    reason: str = "",
) -> dict[str, Any]:
    qid = safe_token(str(queue_task_id_text or ""), "", 160)
    if not qid:
        raise TrainingCenterError(400, "queue_task_id required", "queue_task_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)
    reason_text = str(reason or "").strip()
    now_text = iso_ts(now_local())

    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT q.queue_task_id,q.plan_id,q.status,q.priority,q.trainer_match,q.enqueued_at,
                   p.source,p.target_agent_id,p.capability_goal
            FROM training_queue q
            INNER JOIN training_plan p ON p.plan_id=q.plan_id
            WHERE q.queue_task_id=?
            LIMIT 1
            """,
            (qid,),
        ).fetchone()
        if row is None:
            raise TrainingCenterError(404, "queue task not found", "queue_task_not_found", {"queue_task_id": qid})

        old_status = str(row["status"] or "")
        if old_status != "removed":
            conn.execute(
                """
                UPDATE training_queue
                SET status='removed',finished_at=?
                WHERE queue_task_id=?
                """,
                (now_text, qid),
            )
            conn.execute(
                """
                UPDATE training_run
                SET status='removed',updated_at=?
                WHERE queue_task_id=? AND status='running'
                """,
                (now_text, qid),
            )
            conn.commit()
    finally:
        conn.close()

    audit_id = append_training_center_audit(
        root,
        action="remove",
        operator=operator_text,
        target_id=qid,
        detail={
            "reason": reason_text,
            "risk_tip": "风险提示：移除后不可自动恢复，如需恢复请重新入队。",
        },
    )
    return {
        "queue_task_id": qid,
        "status": "removed",
        "risk_tip": "风险提示：移除后不可自动恢复，如需恢复请重新入队。",
        "audit_id": audit_id,
    }


def execute_training_queue_item(
    root: Path,
    *,
    queue_task_id_text: str,
    operator: str,
) -> dict[str, Any]:
    qid = safe_token(str(queue_task_id_text or ""), "", 160)
    if not qid:
        raise TrainingCenterError(400, "queue_task_id required", "queue_task_id_required")
    operator_text = safe_token(str(operator or "web-user"), "web-user", 80)

    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT q.queue_task_id,q.plan_id,q.priority,q.status,q.trainer_match,q.enqueued_at,q.started_at,q.finished_at,
                   p.source,p.target_agent_id,p.capability_goal,p.training_tasks_json,p.acceptance_criteria,p.similar_flag,
                   a.training_gate_state,a.lifecycle_state
            FROM training_queue q
            INNER JOIN training_plan p ON p.plan_id=q.plan_id
            LEFT JOIN agent_registry a ON a.agent_id=p.target_agent_id
            WHERE q.queue_task_id=?
            LIMIT 1
            """,
            (qid,),
        ).fetchone()
        if row is None:
            raise TrainingCenterError(404, "queue task not found", "queue_task_not_found", {"queue_task_id": qid})
        status = str(row["status"] or "")
        trainer_match = str(row["trainer_match"] or "").strip()
        target_agent_id = str(row["target_agent_id"] or "").strip()
        training_gate_state = normalize_training_gate_state(row["training_gate_state"])
        if not trainer_match:
            raise TrainingCenterError(
                409,
                "trainer 无匹配结果，当前任务不可启动执行",
                "trainer_unmatched",
                {"queue_task_id": qid},
            )
        if training_gate_state == "frozen_switched":
            raise TrainingCenterError(
                409,
                "当前 agent 已冻结训练，请切回最新发布版本后再训练",
                "training_frozen_after_switch",
                {"queue_task_id": qid, "target_agent_id": target_agent_id},
            )
        if status == "removed":
            raise TrainingCenterError(409, "queue task removed", "queue_task_removed", {"queue_task_id": qid})
        if status == "running":
            raise TrainingCenterError(409, "queue task running", "queue_task_running", {"queue_task_id": qid})
        if status == "done":
            raise TrainingCenterError(409, "queue task already done", "queue_task_done", {"queue_task_id": qid})

        run_id = training_run_id_text()
        start_ts = now_local()
        start_text = iso_ts(start_ts)
        run_ref = f"trainer://{trainer_match}/{run_id}"
        conn.execute(
            """
            UPDATE training_queue
            SET status='running',started_at=?
            WHERE queue_task_id=?
            """,
            (start_text, qid),
        )
        conn.execute(
            """
            INSERT INTO training_run (
                run_id,queue_task_id,run_ref,status,result_summary,updated_at
            ) VALUES (?,?,?,?,?,?)
            """,
            (
                run_id,
                qid,
                run_ref,
                "running",
                "",
                start_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    start_audit_id = append_training_center_audit(
        root,
        action="start",
        operator=operator_text,
        target_id=qid,
        detail={"run_id": run_id, "run_ref": run_ref},
    )

    finish_ts = now_local()
    finish_text = iso_ts(finish_ts)
    result_summary = (
        "训练执行骨架已完成："
        + f"queue_task_id={qid}, trainer={trainer_match}, mode=skeleton, "
        + "后续可替换为真实 trainer 调度。"
    )
    conn = connect_db(root)
    try:
        conn.execute(
            """
            UPDATE training_queue
            SET status='done',finished_at=?
            WHERE queue_task_id=?
            """,
            (finish_text, qid),
        )
        conn.execute(
            """
            UPDATE training_run
            SET status='done',result_summary=?,updated_at=?
            WHERE run_id=?
            """,
            (result_summary, finish_text, run_id),
        )
        conn.execute(
            """
            UPDATE agent_registry
            SET lifecycle_state='pre_release',training_gate_state='trainable',updated_at=?
            WHERE agent_id=?
            """,
            (finish_text, target_agent_id),
        )
        conn.commit()
    finally:
        conn.close()

    finish_audit_id = append_training_center_audit(
        root,
        action="finish",
        operator=operator_text,
        target_id=qid,
        detail={"run_id": run_id, "status": "done", "result_summary": result_summary},
    )
    return {
        "queue_task_id": qid,
        "run_id": run_id,
        "run_ref": run_ref,
        "status": "done",
        "target_agent_id": target_agent_id,
        "target_agent_lifecycle_state": "pre_release",
        "result_summary": result_summary,
        "updated_at": finish_text,
        "audit_ids": {"start": start_audit_id, "finish": finish_audit_id},
    }


def dispatch_next_training_queue_item(root: Path, *, operator: str) -> dict[str, Any]:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT q.queue_task_id
            FROM training_queue q
            INNER JOIN training_plan p ON p.plan_id=q.plan_id
            LEFT JOIN agent_registry a ON a.agent_id=p.target_agent_id
            WHERE q.status='queued'
              AND COALESCE(a.training_gate_state,'trainable') <> 'frozen_switched'
            ORDER BY
                CASE q.priority
                    WHEN 'P0' THEN 0
                    WHEN 'P1' THEN 1
                    WHEN 'P2' THEN 2
                    WHEN 'P3' THEN 3
                    ELSE 99
                END ASC,
                q.enqueued_at ASC
            LIMIT 1
            """
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return {"dispatched": False, "message": "queue empty"}
    queue_task_id_text = str(row["queue_task_id"] or "")
    result = execute_training_queue_item(
        root,
        queue_task_id_text=queue_task_id_text,
        operator=operator,
    )
    return {"dispatched": True, "queue_task_id": queue_task_id_text, "result": result}


def get_training_run_detail(root: Path, run_id_text: str) -> dict[str, Any] | None:
    run_id = safe_token(str(run_id_text or ""), "", 160)
    if not run_id:
        return None
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT
                r.run_id,r.queue_task_id,r.run_ref,r.status,r.result_summary,r.updated_at,
                q.plan_id,q.priority,q.status AS queue_status,q.trainer_match,q.enqueued_at,q.started_at,q.finished_at,
                p.source,p.target_agent_id,p.capability_goal,p.training_tasks_json,p.acceptance_criteria,p.similar_flag,p.is_test_data,
                a.agent_name,a.lifecycle_state,a.training_gate_state
            FROM training_run r
            INNER JOIN training_queue q ON q.queue_task_id=r.queue_task_id
            INNER JOIN training_plan p ON p.plan_id=q.plan_id
            LEFT JOIN agent_registry a ON a.agent_id=p.target_agent_id
            WHERE r.run_id=?
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    tasks: list[str] = []
    try:
        payload = json.loads(str(row["training_tasks_json"] or "[]"))
        if isinstance(payload, list):
            tasks = [str(item or "").strip() for item in payload if str(item or "").strip()]
    except Exception:
        tasks = []
    out = {name: row[name] for name in row.keys()}
    out["training_tasks"] = tasks
    out["similar_flag"] = bool(int(row["similar_flag"] or 0))
    out["is_test_data"] = bool(int(row["is_test_data"] or 0))
    out["lifecycle_state"] = normalize_lifecycle_state(row["lifecycle_state"])
    out["training_gate_state"] = normalize_training_gate_state(row["training_gate_state"])
    return out
