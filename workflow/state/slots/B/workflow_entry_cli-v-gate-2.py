#!/usr/bin/env python3
"""Phase 0 chat entrypoint.

Scope for this script:
1. Chat entry via CLI.
2. Event logging to JSONL.
3. Auto-update:
   - logs/summaries/daily-summary.md
   - state/session-snapshot.md

Both markdown files are refreshed after every completed chat round.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_FOCUS = "Phase0 Day3: minimal web chat page + closed loop ops"


@dataclass
class Metrics:
    new_sessions: int
    pending_analysis: int
    pending_training: int
    ab_switch_count: int
    critical_failures: int
    top_failure_tags: list[tuple[str, int]]
    total_events: int
    latest_switch_at: str
    latest_decision: str
    latest_training: str


def now_local() -> datetime:
    return datetime.now().astimezone()


def ensure_layout(root: Path) -> None:
    required_dirs = [
        "logs/events",
        "logs/decisions",
        "logs/runs",
        "logs/summaries",
        "state",
        "incidents",
        "metrics",
    ]
    for rel in required_dirs:
        (root / rel).mkdir(parents=True, exist_ok=True)


def db_file(root: Path) -> Path:
    return root / "state" / "workflow.db"


def _ensure_columns(conn: sqlite3.Connection, table: str, required: list[tuple[str, str]]) -> None:
    existing = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for col_name, col_def in required:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")


def init_db(root: Path) -> None:
    conn = sqlite3.connect(db_file(root))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                stage TEXT NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER NOT NULL DEFAULT 0,
                task_id TEXT,
                reason_tags_json TEXT NOT NULL DEFAULT '[]',
                ref TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_events_session_id
            ON conversation_events(session_id)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_events_timestamp
            ON conversation_events(timestamp)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                analysis_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL UNIQUE,
                source_event_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                decision TEXT,
                decision_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status
            ON analysis_tasks(status)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS training_tasks (
                training_id TEXT PRIMARY KEY,
                analysis_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                result_summary TEXT,
                trainer_run_ref TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_training_tasks_status
            ON training_tasks(status)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_training_tasks_analysis_id_unique
            ON training_tasks(analysis_id)
            """
        )
        _ensure_columns(
            conn,
            "training_tasks",
            [
                ("attempts", "attempts INTEGER NOT NULL DEFAULT 0"),
                ("last_error", "last_error TEXT"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def date_key(ts: datetime) -> str:
    return ts.strftime("%Y%m%d")


def timestamp_key(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M:%S%z")


def event_file(root: Path, ts: datetime) -> Path:
    return root / "logs" / "events" / f"events-{date_key(ts)}.jsonl"


def run_file(root: Path, ts: datetime) -> Path:
    base = root / "logs" / "runs" / f"run-{date_key(ts)}-{ts.strftime('%H%M')}.md"
    if not base.exists():
        return base

    # Keep the required run filename prefix and avoid overwriting same-minute runs.
    stem = base.stem
    suffix = base.suffix
    idx = 1
    while True:
        candidate = base.with_name(f"{stem}-{idx:02d}{suffix}")
        if not candidate.exists():
            return candidate
        idx += 1


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def generate_event_id(ts: datetime) -> str:
    return f"evt-{date_key(ts)}-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"


def generate_task_id(ts: datetime) -> str:
    return f"REQ-{date_key(ts)}-{uuid.uuid4().hex[:6]}"


def append_event(path: Path, event: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def persist_event_to_db(root: Path, event: dict[str, Any]) -> None:
    conn = sqlite3.connect(db_file(root))
    try:
        _insert_event_row(conn, event)
        conn.commit()
    finally:
        conn.close()


def _event_reason_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def _normalize_event(raw: dict[str, Any], fallback_ref: str = "") -> dict[str, Any]:
    ts = str(raw.get("timestamp") or now_local().isoformat(timespec="seconds"))
    session_id = str(raw.get("session_id") or "")
    event_id = str(raw.get("event_id") or "")
    if not event_id:
        event_id = generate_event_id(now_local())
    return {
        "event_id": event_id,
        "timestamp": ts,
        "session_id": session_id,
        "actor": str(raw.get("actor") or "workflow"),
        "stage": str(raw.get("stage") or "chat"),
        "action": str(raw.get("action") or "send_message"),
        "status": str(raw.get("status") or "success"),
        "latency_ms": int(raw.get("latency_ms") or 0),
        "task_id": str(raw.get("task_id") or ""),
        "reason_tags": _event_reason_tags(raw.get("reason_tags")),
        "ref": str(raw.get("ref") or fallback_ref or ""),
    }


def _insert_event_row(conn: sqlite3.Connection, event: dict[str, Any]) -> int:
    result = conn.execute(
        """
        INSERT OR IGNORE INTO conversation_events (
            event_id,
            timestamp,
            session_id,
            actor,
            stage,
            action,
            status,
            latency_ms,
            task_id,
            reason_tags_json,
            ref
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(event.get("event_id", "")),
            str(event.get("timestamp", "")),
            str(event.get("session_id", "")),
            str(event.get("actor", "")),
            str(event.get("stage", "")),
            str(event.get("action", "")),
            str(event.get("status", "")),
            int(event.get("latency_ms") or 0),
            str(event.get("task_id", "")),
            json.dumps(event.get("reason_tags") or [], ensure_ascii=False),
            str(event.get("ref", "")),
        ),
    )
    return int(result.rowcount > 0)


def backfill_events_from_jsonl(root: Path) -> tuple[int, int, int, int]:
    events_dir = root / "logs" / "events"
    files = sorted(events_dir.glob("events-*.jsonl"))
    scanned = 0
    inserted = 0
    malformed = 0

    conn = sqlite3.connect(db_file(root))
    try:
        for path in files:
            fallback_ref = relative_to_root(root, path)
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    text = line.strip()
                    if not text:
                        continue
                    scanned += 1
                    try:
                        raw = json.loads(text)
                        if not isinstance(raw, dict):
                            malformed += 1
                            continue
                        event = _normalize_event(raw, fallback_ref=fallback_ref)
                        inserted += _insert_event_row(conn, event)
                    except Exception:
                        malformed += 1
                        continue
        conn.commit()
    finally:
        conn.close()

    created_analysis = sync_analysis_tasks(root)
    return scanned, inserted, malformed, created_analysis


def persist_event(root: Path, path: Path, event: dict[str, Any]) -> None:
    # JSONL is the human-auditable event log; SQLite supports queueing and metrics.
    append_event(path, event)
    persist_event_to_db(root, event)


def sync_analysis_tasks(root: Path) -> int:
    conn = sqlite3.connect(db_file(root))
    created = 0
    try:
        user_events = conn.execute(
            """
            SELECT event_id, session_id, timestamp
            FROM conversation_events
            WHERE actor = 'user'
              AND stage = 'chat'
              AND action = 'send_message'
              AND status = 'success'
            ORDER BY timestamp ASC
            """
        ).fetchall()

        for event_id, session_id, event_ts in user_events:
            analysis_id = f"ana-{session_id}"
            now_ts = now_local().isoformat(timespec="seconds")
            result = conn.execute(
                """
                INSERT OR IGNORE INTO analysis_tasks (
                    analysis_id,
                    session_id,
                    source_event_id,
                    status,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (analysis_id, session_id, event_id, event_ts or now_ts, now_ts),
            )
            created += int(result.rowcount > 0)

        conn.commit()
        return created
    finally:
        conn.close()


def get_pending_counts(root: Path) -> tuple[int, int]:
    conn = sqlite3.connect(db_file(root))
    try:
        pending_analysis = conn.execute(
            "SELECT COUNT(1) FROM analysis_tasks WHERE status = 'pending'"
        ).fetchone()[0]
        pending_training = conn.execute(
            "SELECT COUNT(1) FROM training_tasks WHERE status = 'pending'"
        ).fetchone()[0]
        return int(pending_analysis), int(pending_training)
    finally:
        conn.close()


def get_latest_results(root: Path) -> tuple[str, str]:
    conn = sqlite3.connect(db_file(root))
    try:
        latest_decision_row = conn.execute(
            """
            SELECT analysis_id, decision, status
            FROM analysis_tasks
            WHERE decision IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
        latest_training_row = conn.execute(
            """
            SELECT training_id, status
            FROM training_tasks
            WHERE status IN ('done', 'failed')
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()

        latest_decision = (
            f"{latest_decision_row[0]}:{latest_decision_row[1]}({latest_decision_row[2]})"
            if latest_decision_row
            else "none"
        )
        latest_training = (
            f"{latest_training_row[0]}:{latest_training_row[1]}"
            if latest_training_row
            else "none"
        )
        return latest_decision, latest_training
    finally:
        conn.close()


def latest_session_id_from_events(events: list[dict[str, Any]]) -> str:
    for item in reversed(events):
        sid = str(item.get("session_id", "")).strip()
        if sid:
            return sid
    return ""


def refresh_outputs(root: Path, focus: str, preferred_session_id: str = "") -> None:
    ts = now_local()
    events_path = event_file(root, ts)
    all_today_events = load_events(events_path)
    pending_analysis, pending_training = get_pending_counts(root)
    latest_decision, latest_training = get_latest_results(root)
    metrics = compute_metrics(
        all_today_events,
        pending_analysis=pending_analysis,
        pending_training=pending_training,
        latest_decision=latest_decision,
        latest_training=latest_training,
    )
    latest_session_id = preferred_session_id or latest_session_id_from_events(all_today_events)
    write_daily_summary(root, ts, metrics, latest_session_id=latest_session_id)
    write_session_snapshot(root, ts, metrics, focus=focus, latest_session_id=latest_session_id)


def append_decision_markdown(
    root: Path,
    ts: datetime,
    analysis_id: str,
    session_id: str,
    decision: str,
    reason: str,
) -> str:
    path = root / "logs" / "decisions" / f"decisions-{date_key(ts)}.md"
    rel = relative_to_root(root, path)
    if not path.exists():
        path.write_text(
            "\n".join(
                [
                    f"# Decisions - {ts.strftime('%Y-%m-%d')}",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    with path.open("a", encoding="utf-8") as fh:
        fh.write(
            f"- {timestamp_key(ts)} analysis_id={analysis_id} session_id={session_id} "
            f"decision={decision} reason={reason or 'n/a'}\n"
        )
    return rel


def decision_to_status(decision: str) -> str:
    mapping = {
        "train": "decided_train",
        "skip": "decided_skip",
        "need_info": "blocked",
    }
    return mapping[decision]


def create_training_id(analysis_id: str) -> str:
    return f"trn-{analysis_id}"


def run_decision_batch(
    root: Path,
    decision: str,
    reason: str,
    limit: int,
    focus: str,
    actor: str = "workflow",
) -> tuple[int, int]:
    conn = sqlite3.connect(db_file(root))
    processed = 0
    created_training = 0
    try:
        rows = conn.execute(
            """
            SELECT analysis_id, session_id
            FROM analysis_tasks
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()

        for analysis_id, session_id in rows:
            ts = now_local()
            status = decision_to_status(decision)
            conn.execute(
                """
                UPDATE analysis_tasks
                SET status = ?, decision = ?, decision_reason = ?, updated_at = ?
                WHERE analysis_id = ?
                """,
                (status, decision, reason, ts.isoformat(timespec="seconds"), analysis_id),
            )
            if decision == "train":
                training_id = create_training_id(str(analysis_id))
                insert_result = conn.execute(
                    """
                    INSERT OR IGNORE INTO training_tasks (
                        training_id,
                        analysis_id,
                        status,
                        attempts,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, 'pending', 0, ?, ?)
                    """,
                    (
                        training_id,
                        str(analysis_id),
                        ts.isoformat(timespec="seconds"),
                        ts.isoformat(timespec="seconds"),
                    ),
                )
                created_training += int(insert_result.rowcount > 0)
            conn.commit()

            ref = append_decision_markdown(
                root,
                ts,
                analysis_id=str(analysis_id),
                session_id=str(session_id),
                decision=decision,
                reason=reason,
            )
            event = {
                "event_id": generate_event_id(ts),
                "timestamp": ts.isoformat(timespec="seconds"),
                "session_id": str(session_id),
                "actor": actor,
                "stage": "analyze",
                "action": "decision",
                "status": "success",
                "latency_ms": 0,
                "task_id": str(analysis_id),
                "reason_tags": [decision],
                "ref": ref,
            }
            persist_event(root, event_file(root, ts), event)
            processed += 1
    finally:
        conn.close()

    refresh_outputs(root, focus=focus)
    return processed, created_training


def training_report_path(root: Path, ts: datetime, training_id: str, attempt: int) -> Path:
    safe_id = "".join(ch for ch in training_id if ch.isalnum() or ch in {"-", "_"})
    return (
        root
        / "logs"
        / "runs"
        / f"train-{date_key(ts)}-{ts.strftime('%H%M%S')}-{safe_id}-a{attempt}.md"
    )


def write_training_report(
    root: Path,
    ts: datetime,
    training_id: str,
    analysis_id: str,
    session_id: str,
    attempt: int,
) -> str:
    path = training_report_path(root, ts, training_id, attempt)
    content = "\n".join(
        [
            f"# Training Report - {training_id}",
            "",
            f"- timestamp: {timestamp_key(ts)}",
            f"- analysis_id: {analysis_id}",
            f"- session_id: {session_id}",
            f"- attempt: {attempt}",
            "- result: done",
            "",
            "## Summary",
            "Mock trainer completed successfully.",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")
    return relative_to_root(root, path)


def run_training_batch(
    root: Path,
    limit: int,
    max_retries: int,
    focus: str,
    actor: str = "trainer",
) -> tuple[int, int]:
    conn = sqlite3.connect(db_file(root))
    processed = 0
    done = 0
    try:
        rows = conn.execute(
            """
            SELECT t.training_id, t.analysis_id, t.attempts, a.session_id
            FROM training_tasks t
            JOIN analysis_tasks a ON a.analysis_id = t.analysis_id
            WHERE t.status IN ('pending', 'failed')
              AND t.attempts < ?
            ORDER BY t.created_at ASC
            LIMIT ?
            """,
            (max(1, max_retries), max(1, limit)),
        ).fetchall()

        for training_id, analysis_id, attempts, session_id in rows:
            last_exc: Exception | None = None
            current_attempts = int(attempts or 0)
            while current_attempts < max(1, max_retries):
                ts = now_local()
                current_attempts += 1
                conn.execute(
                    """
                    UPDATE training_tasks
                    SET status = 'running', attempts = ?, updated_at = ?
                    WHERE training_id = ?
                    """,
                    (current_attempts, ts.isoformat(timespec="seconds"), training_id),
                )
                conn.commit()

                try:
                    report_ref = write_training_report(
                        root,
                        ts=ts,
                        training_id=str(training_id),
                        analysis_id=str(analysis_id),
                        session_id=str(session_id),
                        attempt=current_attempts,
                    )
                    summary = (
                        f"training_id={training_id} done at attempt={current_attempts}; "
                        f"report={report_ref}"
                    )
                    conn.execute(
                        """
                        UPDATE training_tasks
                        SET status = 'done',
                            result_summary = ?,
                            trainer_run_ref = ?,
                            last_error = NULL,
                            updated_at = ?
                        WHERE training_id = ?
                        """,
                        (summary, report_ref, ts.isoformat(timespec="seconds"), training_id),
                    )
                    conn.commit()
                    event = {
                        "event_id": generate_event_id(ts),
                        "timestamp": ts.isoformat(timespec="seconds"),
                        "session_id": str(session_id),
                        "actor": actor,
                        "stage": "train",
                        "action": "run_training",
                        "status": "success",
                        "latency_ms": 0,
                        "task_id": str(training_id),
                        "reason_tags": [],
                        "ref": report_ref,
                    }
                    persist_event(root, event_file(root, ts), event)
                    done += 1
                    break
                except Exception as exc:  # pragma: no cover - defensive path
                    last_exc = exc
                    next_status = "pending" if current_attempts < max(1, max_retries) else "failed"
                    conn.execute(
                        """
                        UPDATE training_tasks
                        SET status = ?, last_error = ?, updated_at = ?
                        WHERE training_id = ?
                        """,
                        (
                            next_status,
                            f"{exc.__class__.__name__}: {exc}",
                            ts.isoformat(timespec="seconds"),
                            training_id,
                        ),
                    )
                    conn.commit()
                    event = {
                        "event_id": generate_event_id(ts),
                        "timestamp": ts.isoformat(timespec="seconds"),
                        "session_id": str(session_id),
                        "actor": actor,
                        "stage": "train",
                        "action": "run_training",
                        "status": "failed",
                        "latency_ms": 0,
                        "task_id": str(training_id),
                        "reason_tags": [exc.__class__.__name__],
                        "ref": "logs/runs",
                    }
                    persist_event(root, event_file(root, ts), event)

            if last_exc is None:
                processed += 1
            elif current_attempts >= max(1, max_retries):
                processed += 1
    finally:
        conn.close()

    refresh_outputs(root, focus=focus)
    return processed, done


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            text = line.strip()
            if not text:
                continue
            try:
                events.append(json.loads(text))
            except json.JSONDecodeError:
                # Skip malformed rows without failing the chat entrypoint.
                continue
    return events


def compute_metrics(
    events: list[dict[str, Any]],
    pending_analysis: int,
    pending_training: int,
    latest_decision: str,
    latest_training: str,
) -> Metrics:
    sessions = {str(item.get("session_id")) for item in events if item.get("session_id")}
    failures = [item for item in events if item.get("status") == "failed"]
    reason_counter: Counter[str] = Counter()
    for item in failures:
        tags = item.get("reason_tags") or ["unknown"]
        for tag in tags:
            reason_counter[str(tag)] += 1

    latest_switch = ""
    for item in reversed(events):
        if (
            item.get("stage") == "switch"
            and item.get("action") == "ab_switch"
            and item.get("status") == "success"
        ):
            latest_switch = str(item.get("timestamp", ""))
            break

    return Metrics(
        new_sessions=len(sessions),
        pending_analysis=pending_analysis,
        pending_training=pending_training,
        ab_switch_count=sum(
            1
            for item in events
            if item.get("stage") == "switch"
            and item.get("action") == "ab_switch"
            and item.get("status") == "success"
        ),
        critical_failures=len(failures),
        top_failure_tags=reason_counter.most_common(3),
        total_events=len(events),
        latest_switch_at=latest_switch,
        latest_decision=latest_decision,
        latest_training=latest_training,
    )


def write_daily_summary(
    root: Path,
    ts: datetime,
    metrics: Metrics,
    latest_session_id: str,
) -> None:
    summary_path = root / "logs" / "summaries" / "daily-summary.md"
    tags = ", ".join(f"{tag}({count})" for tag, count in metrics.top_failure_tags) or "none"
    latest_switch = metrics.latest_switch_at or "none"

    if metrics.top_failure_tags:
        top_tag = metrics.top_failure_tags[0][0]
        tomorrow_priority = f"Fix top failure tag first: {top_tag}"
    else:
        tomorrow_priority = "No critical failures today. Continue Phase0 Day3 scope."

    content = "\n".join(
        [
            f"# Daily Summary - {ts.strftime('%Y-%m-%d')}",
            "",
            f"- last_update: {timestamp_key(ts)}",
            "- source: scripts/workflow_entry_cli.py",
            "",
            "## Must-Track (Top 5)",
            f"1. New sessions total: {metrics.new_sessions}",
            (
                "2. Pending tasks: "
                f"analysis={metrics.pending_analysis}, training={metrics.pending_training}"
            ),
            (
                "3. A/B switch record: "
                f"switch_count={metrics.ab_switch_count}, latest_switch_at={latest_switch}"
            ),
            f"4. Top3 failure reason tags: {tags}",
            f"5. Tomorrow first priority: {tomorrow_priority}",
            "",
            "## Extra",
            f"- total_events_today: {metrics.total_events}",
            f"- latest_session_id: {latest_session_id}",
            f"- latest_decision: {metrics.latest_decision}",
            f"- latest_training: {metrics.latest_training}",
        ]
    )
    summary_path.write_text(content + "\n", encoding="utf-8")


def write_session_snapshot(
    root: Path,
    ts: datetime,
    metrics: Metrics,
    focus: str,
    latest_session_id: str,
) -> None:
    snapshot_path = root / "state" / "session-snapshot.md"
    events_path = relative_to_root(root, event_file(root, ts))

    blocker = "none"
    if metrics.top_failure_tags:
        blocker = f"failure tag: {metrics.top_failure_tags[0][0]}"

    content = "\n".join(
        [
            "# Session Snapshot",
            "",
            f"- last_update: {timestamp_key(ts)}",
            "- current_phase: phase0-day3",
            f"- current_focus: {focus}",
            "",
            "## Today",
            (
                "1. Completed: chat entry active; event logs, analysis task auto-creation, "
                "decision + training execution, minimal web chat page, and per-round markdown "
                "snapshots are auto-updated."
            ),
            (
                "2. <span style=\"color:red\">Not completed: Gate-level acceptance still pending for "
                "real-agent streaming equivalence, automated reconciliation alerts, and A/B switch "
                "RTO/RPO proof.</span>"
            ),
            f"3. Largest blocker: {blocker}",
            "",
            "## Key Metrics",
            f"1. new_sessions: {metrics.new_sessions}",
            f"2. pending_analysis: {metrics.pending_analysis}",
            f"3. pending_training: {metrics.pending_training}",
            f"4. ab_switch_count: {metrics.ab_switch_count}",
            f"5. critical_failures: {metrics.critical_failures}",
            f"6. latest_decision: {metrics.latest_decision}",
            f"7. latest_training: {metrics.latest_training}",
            "",
            "## Next Start",
            f"1. First log to check: {events_path}",
            "2. First action: continue chat rounds and keep logs complete.",
            "",
            "## Session",
            f"- latest_session_id: {latest_session_id}",
        ]
    )
    snapshot_path.write_text(content + "\n", encoding="utf-8")


def mock_agent_reply(agent: str, message: str) -> str:
    return f"[{agent}] received: {message}"


def append_run_round(
    run_path: Path,
    ts: datetime,
    round_index: int,
    user_message: str,
    agent_reply: str,
) -> None:
    with run_path.open("a", encoding="utf-8") as fh:
        fh.write(f"\n## Round {round_index} - {timestamp_key(ts)}\n")
        fh.write(f"- user: {user_message}\n")
        fh.write(f"- agent: {agent_reply}\n")


def process_round(
    root: Path,
    agent: str,
    session_id: str,
    user_message: str,
    focus: str,
    run_path: Path,
    round_index: int,
) -> None:
    round_ts = now_local()
    start = time.perf_counter()
    events_path = event_file(root, round_ts)
    ref_path = relative_to_root(root, run_path)
    task_id = generate_task_id(round_ts)

    user_event = {
        "event_id": generate_event_id(round_ts),
        "timestamp": round_ts.isoformat(timespec="seconds"),
        "session_id": session_id,
        "actor": "user",
        "stage": "chat",
        "action": "send_message",
        "status": "success",
        "latency_ms": 0,
        "task_id": task_id,
        "reason_tags": [],
        "ref": ref_path,
    }
    persist_event(root, events_path, user_event)

    try:
        reply = mock_agent_reply(agent, user_message)
        latency_ms = int((time.perf_counter() - start) * 1000)
        agent_event = {
            "event_id": generate_event_id(now_local()),
            "timestamp": now_local().isoformat(timespec="seconds"),
            "session_id": session_id,
            "actor": "agent",
            "stage": "chat",
            "action": "send_message",
            "status": "success",
            "latency_ms": latency_ms,
            "task_id": task_id,
            "reason_tags": [],
            "ref": ref_path,
        }
        persist_event(root, events_path, agent_event)
        append_run_round(run_path, round_ts, round_index, user_message, reply)
        print(f"{agent}> {reply}")
    except Exception as exc:  # pragma: no cover - defensive logging path
        latency_ms = int((time.perf_counter() - start) * 1000)
        failed_event = {
            "event_id": generate_event_id(now_local()),
            "timestamp": now_local().isoformat(timespec="seconds"),
            "session_id": session_id,
            "actor": "workflow",
            "stage": "chat",
            "action": "send_message",
            "status": "failed",
            "latency_ms": latency_ms,
            "task_id": task_id,
            "reason_tags": [exc.__class__.__name__],
            "ref": ref_path,
        }
        persist_event(root, events_path, failed_event)
        print(f"{agent}> failed to generate reply ({exc.__class__.__name__})")

    sync_analysis_tasks(root)
    refresh_outputs(root, focus=focus, preferred_session_id=session_id)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Phase0 chat entrypoint with event logging, auto queueing, and summary/snapshot updates."
        )
    )
    parser.add_argument("--root", default=".", help="Workspace root path.")
    parser.add_argument(
        "--mode",
        choices=["chat", "decide", "train", "status", "backfill"],
        default="chat",
        help="Execution mode.",
    )
    parser.add_argument("--agent", default="agent", help="Target agent name for chat mode.")
    parser.add_argument("--session-id", default="", help="Reuse an existing session id in chat mode.")
    parser.add_argument(
        "--focus",
        default=DEFAULT_FOCUS,
        help="Current focus written into state/session-snapshot.md",
    )
    parser.add_argument(
        "--message",
        default="",
        help="Run one non-interactive chat round then exit.",
    )
    parser.add_argument(
        "--decision",
        choices=["train", "skip", "need_info"],
        default="",
        help="Decision to apply for pending analysis tasks in decide mode.",
    )
    parser.add_argument(
        "--reason",
        default="batch decision",
        help="Decision reason used in decide mode.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum tasks processed in decide/train mode.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retries per training task in train mode.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    ensure_layout(root)
    init_db(root)

    if args.mode == "status":
        sync_analysis_tasks(root)
        refresh_outputs(root, focus=args.focus)
        pending_analysis, pending_training = get_pending_counts(root)
        print(f"status> pending_analysis={pending_analysis} pending_training={pending_training}")
        return

    if args.mode == "backfill":
        scanned, inserted, malformed, created_analysis = backfill_events_from_jsonl(root)
        refresh_outputs(root, focus=args.focus)
        pending_analysis, pending_training = get_pending_counts(root)
        print(
            "backfill> "
            f"scanned={scanned} inserted={inserted} malformed={malformed} "
            f"created_analysis={created_analysis} "
            f"pending_analysis={pending_analysis} pending_training={pending_training}"
        )
        return

    if args.mode == "decide":
        if not args.decision:
            raise SystemExit("--decision is required when --mode=decide")
        sync_analysis_tasks(root)
        processed, created_training = run_decision_batch(
            root=root,
            decision=args.decision,
            reason=args.reason,
            limit=args.limit,
            focus=args.focus,
        )
        print(
            "decide> "
            f"processed={processed} decision={args.decision} "
            f"created_training={created_training}"
        )
        return

    if args.mode == "train":
        processed, done = run_training_batch(
            root=root,
            limit=args.limit,
            max_retries=max(1, args.max_retries),
            focus=args.focus,
        )
        print(f"train> processed={processed} done={done}")
        return

    current_ts = now_local()
    session_id = args.session_id.strip() or f"sess-{date_key(current_ts)}-{uuid.uuid4().hex[:6]}"
    run_path = run_file(root, current_ts)
    run_path.write_text(
        "\n".join(
            [
                f"# Run Log - {current_ts.strftime('%Y-%m-%d %H:%M:%S%z')}",
                "",
                f"- session_id: {session_id}",
                f"- agent: {args.agent}",
                f"- focus: {args.focus}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    if args.message:
        process_round(
            root=root,
            agent=args.agent,
            session_id=session_id,
            user_message=args.message,
            focus=args.focus,
            run_path=run_path,
            round_index=1,
        )
        return

    print(f"session_id={session_id}")
    print("Type /exit to end the session.")
    round_index = 0
    while True:
        try:
            message = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSession ended.")
            break

        if not message:
            continue
        if message.lower() in {"/exit", "exit", "quit"}:
            print("Session ended.")
            break

        round_index += 1
        process_round(
            root=root,
            agent=args.agent,
            session_id=session_id,
            user_message=message,
            focus=args.focus,
            run_path=run_path,
            round_index=round_index,
        )


if __name__ == "__main__":
    main()

