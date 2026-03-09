#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def connect_db(root: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(root / "state" / "workflow.db")
    conn.row_factory = sqlite3.Row
    return conn


def _safe_ref_to_path(root: Path, ref: str) -> Path | None:
    text = str(ref or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = (root / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)
    try:
        path.relative_to(root.resolve(strict=False))
    except ValueError:
        return None
    return path


def _delete_ref_file(root: Path, ref: str) -> bool:
    path = _safe_ref_to_path(root, ref)
    if path is None or not path.exists() or not path.is_file():
        return False
    path.unlink(missing_ok=True)
    return True


def _delete_many_task_refs(root: Path, conn: sqlite3.Connection, task_ids: list[str]) -> int:
    deleted = 0
    for task_id in task_ids:
        row = conn.execute(
            "SELECT ref FROM task_runs WHERE task_id=?",
            (task_id,),
        ).fetchone()
        if row and _delete_ref_file(root, str(row["ref"])):
            deleted += 1
    return deleted


def _collect_task_ids_by_session(conn: sqlite3.Connection, session_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT task_id FROM task_runs WHERE session_id=?",
        (session_id,),
    ).fetchall()
    return [str(row["task_id"]) for row in rows]


def _collect_analysis_ids_by_session(conn: sqlite3.Connection, session_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT analysis_id FROM analysis_tasks WHERE session_id=?",
        (session_id,),
    ).fetchall()
    return [str(row["analysis_id"]) for row in rows]


def _collect_training_ids_by_analysis(conn: sqlite3.Connection, analysis_ids: list[str]) -> list[str]:
    if not analysis_ids:
        return []
    marks = ",".join("?" for _ in analysis_ids)
    rows = conn.execute(
        f"SELECT training_id FROM training_tasks WHERE analysis_id IN ({marks})",
        tuple(analysis_ids),
    ).fetchall()
    return [str(row["training_id"]) for row in rows]


def _collect_workflow_ids_by_analysis_or_session(
    conn: sqlite3.Connection,
    analysis_ids: list[str],
    session_id: str,
) -> list[str]:
    ids: list[str] = []
    if analysis_ids:
        marks = ",".join("?" for _ in analysis_ids)
        rows = conn.execute(
            f"SELECT workflow_id FROM training_workflows WHERE analysis_id IN ({marks})",
            tuple(analysis_ids),
        ).fetchall()
        ids.extend(str(row["workflow_id"]) for row in rows)
    rows2 = conn.execute(
        "SELECT workflow_id FROM training_workflows WHERE session_id=?",
        (session_id,),
    ).fetchall()
    ids.extend(str(row["workflow_id"]) for row in rows2)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        dedup.append(item)
    return dedup


def delete_session_history(root: Path, session_id: str, *, delete_artifacts: bool = True) -> dict[str, Any]:
    session_id = str(session_id or "").strip()
    if not session_id:
        raise RuntimeError("session_id required")
    conn = connect_db(root)
    result = {
        "session_id": session_id,
        "deleted_chat_sessions": 0,
        "deleted_messages": 0,
        "deleted_events": 0,
        "deleted_ingress": 0,
        "deleted_analysis_tasks": 0,
        "deleted_training_tasks": 0,
        "deleted_workflows": 0,
        "deleted_workflow_events": 0,
        "deleted_task_runs": 0,
        "deleted_task_events": 0,
        "deleted_artifacts": 0,
    }
    try:
        row = conn.execute(
            "SELECT session_id,status FROM chat_sessions WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not row:
            raise RuntimeError("session not found")

        task_ids = _collect_task_ids_by_session(conn, session_id)
        analysis_ids = _collect_analysis_ids_by_session(conn, session_id)
        training_ids = _collect_training_ids_by_analysis(conn, analysis_ids)
        workflow_ids = _collect_workflow_ids_by_analysis_or_session(conn, analysis_ids, session_id)

        if delete_artifacts and task_ids:
            result["deleted_artifacts"] += _delete_many_task_refs(root, conn, task_ids)

        if task_ids:
            marks = ",".join("?" for _ in task_ids)
            ret = conn.execute(
                f"DELETE FROM task_events WHERE task_id IN ({marks})",
                tuple(task_ids),
            )
            result["deleted_task_events"] = int(ret.rowcount or 0)
            ret = conn.execute(
                f"DELETE FROM task_runs WHERE task_id IN ({marks})",
                tuple(task_ids),
            )
            result["deleted_task_runs"] = int(ret.rowcount or 0)

        if workflow_ids:
            marks = ",".join("?" for _ in workflow_ids)
            ret = conn.execute(
                f"DELETE FROM training_workflow_events WHERE workflow_id IN ({marks})",
                tuple(workflow_ids),
            )
            result["deleted_workflow_events"] = int(ret.rowcount or 0)
            ret = conn.execute(
                f"DELETE FROM training_workflows WHERE workflow_id IN ({marks})",
                tuple(workflow_ids),
            )
            result["deleted_workflows"] = int(ret.rowcount or 0)

        if training_ids:
            marks = ",".join("?" for _ in training_ids)
            ret = conn.execute(
                f"DELETE FROM conversation_events WHERE task_id IN ({marks}) AND stage='train'",
                tuple(training_ids),
            )
            result["deleted_events"] += int(ret.rowcount or 0)

        if analysis_ids:
            marks = ",".join("?" for _ in analysis_ids)
            ret = conn.execute(
                f"DELETE FROM training_tasks WHERE analysis_id IN ({marks})",
                tuple(analysis_ids),
            )
            result["deleted_training_tasks"] = int(ret.rowcount or 0)
            ret = conn.execute(
                f"DELETE FROM analysis_tasks WHERE analysis_id IN ({marks})",
                tuple(analysis_ids),
            )
            result["deleted_analysis_tasks"] = int(ret.rowcount or 0)
            ret = conn.execute(
                f"DELETE FROM conversation_events WHERE task_id IN ({marks}) AND stage IN ('analyze','training_workflow')",
                tuple(analysis_ids),
            )
            result["deleted_events"] += int(ret.rowcount or 0)

        ret = conn.execute(
            "DELETE FROM conversation_messages WHERE session_id=?",
            (session_id,),
        )
        result["deleted_messages"] = int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM conversation_events WHERE session_id=?",
            (session_id,),
        )
        result["deleted_events"] += int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM ingress_requests WHERE session_id=?",
            (session_id,),
        )
        result["deleted_ingress"] = int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM chat_sessions WHERE session_id=?",
            (session_id,),
        )
        result["deleted_chat_sessions"] = int(ret.rowcount or 0)

        conn.commit()
    finally:
        conn.close()
    return result


def delete_training_content(root: Path, workflow_id: str, *, delete_artifacts: bool = True) -> dict[str, Any]:
    workflow_id = str(workflow_id or "").strip()
    if not workflow_id:
        raise RuntimeError("workflow_id required")
    conn = connect_db(root)
    result = {
        "workflow_id": workflow_id,
        "analysis_id": "",
        "session_id": "",
        "deleted_training_tasks": 0,
        "deleted_workflow_events": 0,
        "deleted_workflows": 0,
        "deleted_events": 0,
        "deleted_artifacts": 0,
        "analysis_reset": 0,
    }
    try:
        workflow = conn.execute(
            """
            SELECT workflow_id,analysis_id,session_id
            FROM training_workflows
            WHERE workflow_id=?
            LIMIT 1
            """,
            (workflow_id,),
        ).fetchone()
        if not workflow:
            raise RuntimeError("workflow not found")
        analysis_id = str(workflow["analysis_id"])
        session_id = str(workflow["session_id"])
        result["analysis_id"] = analysis_id
        result["session_id"] = session_id

        training_rows = conn.execute(
            """
            SELECT training_id,trainer_run_ref
            FROM training_tasks
            WHERE analysis_id=?
            """,
            (analysis_id,),
        ).fetchall()
        training_ids = [str(row["training_id"]) for row in training_rows]

        if delete_artifacts:
            for row in training_rows:
                if _delete_ref_file(root, str(row["trainer_run_ref"])):
                    result["deleted_artifacts"] += 1

        ret = conn.execute(
            "DELETE FROM training_workflow_events WHERE workflow_id=?",
            (workflow_id,),
        )
        result["deleted_workflow_events"] = int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM training_workflows WHERE workflow_id=?",
            (workflow_id,),
        )
        result["deleted_workflows"] = int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM training_tasks WHERE analysis_id=?",
            (analysis_id,),
        )
        result["deleted_training_tasks"] = int(ret.rowcount or 0)
        ret = conn.execute(
            """
            UPDATE analysis_tasks
            SET status='pending', decision=NULL, decision_reason=NULL, updated_at=datetime('now')
            WHERE analysis_id=?
            """,
            (analysis_id,),
        )
        result["analysis_reset"] = int(ret.rowcount or 0)
        if training_ids:
            marks = ",".join("?" for _ in training_ids)
            ret = conn.execute(
                f"DELETE FROM conversation_events WHERE task_id IN ({marks}) AND stage='train'",
                tuple(training_ids),
            )
            result["deleted_events"] += int(ret.rowcount or 0)
        ret = conn.execute(
            "DELETE FROM conversation_events WHERE task_id=? AND stage='analyze'",
            (analysis_id,),
        )
        result["deleted_events"] += int(ret.rowcount or 0)
        conn.commit()
    finally:
        conn.close()
    return result


def cleanup_history(
    root: Path,
    *,
    mode: str = "closed_sessions",
    delete_artifacts: bool = True,
    delete_log_files: bool = False,
    max_age_hours: int = 168,
    include_active_test_sessions: bool = False,
) -> dict[str, Any]:
    mode_text = str(mode or "").strip().lower()
    if mode_text not in {"closed_sessions", "all", "test_data"}:
        raise RuntimeError("invalid cleanup mode")

    result: dict[str, Any] = {
        "mode": mode_text,
        "deleted_sessions": 0,
        "deleted_workflows": 0,
        "deleted_logs": 0,
    }

    if mode_text == "closed_sessions":
        conn = connect_db(root)
        try:
            rows = conn.execute(
                """
                SELECT session_id
                FROM chat_sessions
                WHERE COALESCE(status,'active')='closed'
                ORDER BY created_at ASC
                """
            ).fetchall()
            session_ids = [str(row["session_id"]) for row in rows]
        finally:
            conn.close()
        for session_id in session_ids:
            delete_session_history(root, session_id, delete_artifacts=delete_artifacts)
            result["deleted_sessions"] += 1
        return result

    if mode_text == "test_data":
        cutoff_hours = max(0, int(max_age_hours or 0))
        now_ts = datetime.now().astimezone()
        cutoff_dt = now_ts - timedelta(hours=cutoff_hours)
        conn = connect_db(root)
        try:
            rows = conn.execute(
                """
                SELECT session_id,status,created_at
                FROM chat_sessions
                WHERE COALESCE(is_test_data,0)=1
                ORDER BY created_at ASC
                """
            ).fetchall()
        finally:
            conn.close()

        candidates: list[str] = []
        skipped_active = 0
        skipped_recent = 0
        skipped_invalid_ts = 0
        for row in rows:
            session_id = str(row["session_id"] or "").strip()
            if not session_id:
                continue
            status = str(row["status"] or "active").strip().lower() or "active"
            if (not include_active_test_sessions) and status == "active":
                skipped_active += 1
                continue
            if cutoff_hours > 0:
                created_text = str(row["created_at"] or "").strip()
                try:
                    created_dt = datetime.fromisoformat(created_text)
                    if created_dt.tzinfo is None:
                        created_dt = created_dt.replace(tzinfo=now_ts.tzinfo)
                    created_dt = created_dt.astimezone(now_ts.tzinfo)
                except Exception:
                    skipped_invalid_ts += 1
                    continue
                if created_dt > cutoff_dt:
                    skipped_recent += 1
                    continue
            candidates.append(session_id)

        for session_id in candidates:
            try:
                delete_session_history(root, session_id, delete_artifacts=delete_artifacts)
                result["deleted_sessions"] += 1
            except RuntimeError:
                continue

        result["candidate_sessions"] = len(candidates)
        result["max_age_hours"] = cutoff_hours
        result["include_active_test_sessions"] = bool(include_active_test_sessions)
        result["skipped_active"] = skipped_active
        result["skipped_recent"] = skipped_recent
        result["skipped_invalid_ts"] = skipped_invalid_ts
        return result

    conn = connect_db(root)
    try:
        if delete_artifacts:
            rows = conn.execute("SELECT ref FROM task_runs WHERE COALESCE(ref,'')<>''").fetchall()
            for row in rows:
                if _delete_ref_file(root, str(row["ref"])):
                    result["deleted_logs"] += 1
            rows = conn.execute(
                "SELECT trainer_run_ref FROM training_tasks WHERE COALESCE(trainer_run_ref,'')<>''"
            ).fetchall()
            for row in rows:
                if _delete_ref_file(root, str(row["trainer_run_ref"])):
                    result["deleted_logs"] += 1

        table_order = [
            "task_events",
            "task_runs",
            "training_workflow_events",
            "training_workflows",
            "training_tasks",
            "analysis_tasks",
            "conversation_messages",
            "conversation_events",
            "ingress_requests",
            "chat_sessions",
            "reconcile_runs",
        ]
        for table in table_order:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    finally:
        conn.close()

    if delete_log_files:
        for rel in ["logs/events", "logs/decisions", "logs/runs"]:
            folder = root / rel
            if not folder.exists():
                continue
            for item in folder.iterdir():
                if item.is_file():
                    item.unlink(missing_ok=True)
                    result["deleted_logs"] += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    result["deleted_logs"] += 1
    result["deleted_sessions"] = -1
    result["deleted_workflows"] = -1
    return result
