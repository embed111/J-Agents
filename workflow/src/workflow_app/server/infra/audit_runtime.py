from __future__ import annotations

def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    globals().update(symbols)

def last_user_message(root: Path, session_id: str) -> str:
    conn = connect_db(root)
    try:
        row = conn.execute(
            "SELECT content FROM conversation_messages WHERE session_id=? AND role='user' ORDER BY message_id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return str(row["content"]) if row else ""
    finally:
        conn.close()


def record_ingress(root: Path, request_id: str, session_id: str, route: str) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO ingress_requests (request_id,session_id,route,created_at,event_logged) VALUES (?,?,?,?,0)",
            (request_id, session_id, route, iso_ts(now_local())),
        )
        conn.commit()
    finally:
        conn.close()


def mark_ingress_logged(root: Path, request_id: str) -> None:
    conn = connect_db(root)
    try:
        conn.execute("UPDATE ingress_requests SET event_logged=1 WHERE request_id=?", (request_id,))
        conn.commit()
    finally:
        conn.close()


def sync_analysis_tasks(root: Path) -> int:
    conn = connect_db(root)
    created = 0
    try:
        rows = conn.execute(
            "SELECT event_id,session_id,timestamp FROM conversation_events WHERE actor='user' AND stage='chat' AND action='send_message' AND status='success' ORDER BY timestamp ASC"
        ).fetchall()
        for row in rows:
            aid = f"ana-{row['session_id']}"
            now_ts = iso_ts(now_local())
            ret = conn.execute(
                "INSERT OR IGNORE INTO analysis_tasks (analysis_id,session_id,source_event_id,status,created_at,updated_at) VALUES (?,?,?,'pending',?,?)",
                (aid, str(row["session_id"]), str(row["event_id"]), str(row["timestamp"] or now_ts), now_ts),
            )
            created += int(ret.rowcount > 0)
        conn.commit()
        return created
    finally:
        conn.close()


def pending_counts(root: Path, *, include_test_data: bool = True) -> tuple[int, int]:
    conn = connect_db(root)
    try:
        pa = conn.execute(
            """
            SELECT COUNT(1)
            FROM analysis_tasks a
            LEFT JOIN chat_sessions s ON s.session_id = a.session_id
            WHERE a.status='pending'
              AND (?=1 OR COALESCE(s.is_test_data,0)=0)
            """,
            (1 if include_test_data else 0,),
        ).fetchone()[0]
        pt = conn.execute(
            """
            SELECT COUNT(1)
            FROM training_tasks t
            JOIN analysis_tasks a ON a.analysis_id = t.analysis_id
            LEFT JOIN chat_sessions s ON s.session_id = a.session_id
            WHERE t.status='pending'
              AND (?=1 OR COALESCE(s.is_test_data,0)=0)
            """,
            (1 if include_test_data else 0,),
        ).fetchone()[0]
        return int(pa), int(pt)
    finally:
        conn.close()


def latest_results(root: Path, *, include_test_data: bool = True) -> tuple[str, str]:
    conn = connect_db(root)
    try:
        d = conn.execute(
            """
            SELECT a.analysis_id,a.decision,a.status
            FROM analysis_tasks a
            LEFT JOIN chat_sessions s ON s.session_id = a.session_id
            WHERE a.decision IS NOT NULL
              AND (?=1 OR COALESCE(s.is_test_data,0)=0)
            ORDER BY a.updated_at DESC
            LIMIT 1
            """,
            (1 if include_test_data else 0,),
        ).fetchone()
        t = conn.execute(
            """
            SELECT t.training_id,t.status
            FROM training_tasks t
            JOIN analysis_tasks a ON a.analysis_id = t.analysis_id
            LEFT JOIN chat_sessions s ON s.session_id = a.session_id
            WHERE (?=1 OR COALESCE(s.is_test_data,0)=0)
            ORDER BY t.updated_at DESC
            LIMIT 1
            """,
            (1 if include_test_data else 0,),
        ).fetchone()
        return (
            f"{d['analysis_id']}:{d['decision']}({d['status']})" if d else "none",
            f"{t['training_id']}:{t['status']}" if t else "none",
        )
    finally:
        conn.close()


def new_sessions_24h(root: Path, *, include_test_data: bool = True) -> int:
    since = iso_ts(now_local() - timedelta(hours=24))
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT e.session_id)
            FROM conversation_events e
            LEFT JOIN chat_sessions s ON s.session_id = e.session_id
            WHERE e.actor='user'
              AND e.stage='chat'
              AND e.action='send_message'
              AND e.status='success'
              AND e.timestamp>=?
              AND (?=1 OR COALESCE(s.is_test_data,0)=0)
            """,
            (
                since,
                1 if include_test_data else 0,
            ),
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def append_markdown(path: Path, header: str | None, lines: list[str]) -> None:
    if not path.exists() and header:
        path.write_text(header + "\n\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line + "\n")
        fh.write("\n")


def append_failure_case(root: Path, title: str, detail: str) -> None:
    append_markdown(
        root / "logs" / "summaries" / "failure-cases.md",
        "# Failure Cases",
        [f"## {now_local().strftime('%Y-%m-%d %H:%M:%S%z')} - {title}", f"- detail: {detail}"],
    )


def append_change_log(root: Path, title: str, detail: str) -> None:
    append_markdown(
        root / "state" / "change-log.md",
        "# Change Log",
        [f"## {now_local().strftime('%Y-%m-%d %H:%M:%S%z')} - {title}", f"- {detail}"],
    )


def append_web_e2e(
    root: Path,
    request_id: str,
    stream_id: str,
    session_id: str,
    user_message: str,
    reply: str,
    first_token_ms: int | None,
    total_ms: int,
    status: str,
    note: str,
) -> str:
    path = root / "logs" / "runs" / f"web-e2e-{date_key(now_local())}.md"
    if not path.exists():
        path.write_text(f"# Web E2E - {now_local().strftime('%Y-%m-%d')}\n\n", encoding="utf-8")
    append_markdown(
        path,
        None,
        [
            f"## {now_local().strftime('%Y-%m-%d %H:%M:%S%z')}",
            f"- request_id: {request_id}",
            f"- stream_id: {stream_id or 'n/a'}",
            f"- session_id: {session_id}",
            f"- status: {status}",
            f"- first_token_ms: {first_token_ms}",
            f"- total_ms: {total_ms}",
            f"- user: {user_message}",
            f"- agent: {reply}",
            f"- note: {note or 'none'}",
        ],
    )
    return relative_to_root(root, path)


def run_script(script: Path, root: Path, args: list[str], timeout_s: int = 240) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script)] + args,
        cwd=str(root),
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=timeout_s,
    )


def parse_kv(output: str, prefix: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for line in output.splitlines():
        if not line.strip().startswith(prefix):
            continue
        for key, val in re.findall(r"([a-zA-Z_]+)=(-?\d+)", line):
            out[key] = int(val)
    return out


def ab_file(root: Path) -> Path:
    return root / AB_STATE_FILE


def init_ab_state(cfg: AppConfig) -> None:
    path = ab_file(cfg.root)
    if path.exists():
        return
    rel_script = relative_to_root(cfg.root, cfg.entry_script)
    data = {
        "active_slot": "A",
        "previous_slot": "",
        "slots": {
            "A": {"version": "v1", "script": rel_script, "updated_at": iso_ts(now_local())},
            "B": {"version": "v0-standby", "script": rel_script, "updated_at": iso_ts(now_local())},
        },
        "last_switch": {},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_ab_state(cfg: AppConfig) -> dict[str, Any]:
    return json.loads(ab_file(cfg.root).read_text(encoding="utf-8"))


def save_ab_state(cfg: AppConfig, data: dict[str, Any]) -> None:
    ab_file(cfg.root).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def active_entry_script(cfg: AppConfig) -> Path:
    state = load_ab_state(cfg)
    active = str(state.get("active_slot") or "A")
    rel_script = str((state.get("slots") or {}).get(active, {}).get("script") or relative_to_root(cfg.root, cfg.entry_script))
    path = (cfg.root / rel_script).resolve()
    return path if path.exists() else cfg.entry_script


def refresh_status(cfg: AppConfig) -> None:
    run_script(active_entry_script(cfg), cfg.root, ["--mode", "status", "--focus", cfg.focus], timeout_s=120)


def ab_status(cfg: AppConfig) -> dict[str, Any]:
    state = load_ab_state(cfg)
    active = str(state.get("active_slot") or "A")
    standby = "B" if active == "A" else "A"
    slots = state.get("slots") or {}
    return {
        "active_slot": active,
        "standby_slot": standby,
        "active_version": str((slots.get(active) or {}).get("version") or "unknown"),
        "standby_version": str((slots.get(standby) or {}).get("version") or "unknown"),
        "last_switch": state.get("last_switch") or {},
    }


def estimate_rpo_ms(root: Path, switch_ts: datetime) -> int:
    conn = connect_db(root)
    try:
        row = conn.execute("SELECT MAX(timestamp) FROM conversation_events").fetchone()
        max_ts = row[0] if row else None
    finally:
        conn.close()
    if not max_ts:
        return 0
    try:
        return max(0, int((switch_ts - datetime.fromisoformat(str(max_ts))).total_seconds() * 1000))
    except Exception:
        return 0


def append_switch_event(root: Path, task_id_text: str, status: str, tags: list[str], ref: str) -> None:
    persist_event(
        root,
        {
            "event_id": event_id(),
            "timestamp": iso_ts(now_local()),
            "session_id": "sess-ab-switch",
            "actor": "workflow",
            "stage": "switch",
            "action": "ab_switch",
            "status": status,
            "latency_ms": 0,
            "task_id": task_id_text,
            "reason_tags": tags,
            "ref": ref,
        },
    )


def deploy_and_switch(cfg: AppConfig, version: str, trigger: str) -> dict[str, Any]:
    state = load_ab_state(cfg)
    active = str(state.get("active_slot") or "A")
    standby = "B" if active == "A" else "A"
    src = active_entry_script(cfg)
    safe_ver = safe_token(version, f"v-{date_key(now_local())}", 80)
    slot_dir = cfg.root / "state" / "slots" / standby
    slot_dir.mkdir(parents=True, exist_ok=True)
    dst = slot_dir / f"workflow_entry_cli-{safe_ver}.py"
    shutil.copy2(src, dst)

    start = time.perf_counter()
    health = run_script(dst, cfg.root, ["--mode", "status", "--focus", cfg.focus], timeout_s=90)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    run_path = unique_run_file(cfg.root, "ab-switch")
    if health.returncode != 0:
        run_path.write_text(
            "\n".join(
                [
                    "# AB Switch Failed",
                    f"- trigger: {trigger}",
                    f"- version: {safe_ver}",
                    f"- from_slot: {active}",
                    f"- to_slot: {standby}",
                    f"- elapsed_ms: {elapsed_ms}",
                    f"- detail: {(health.stderr or health.stdout or 'health failed').strip()}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ref = relative_to_root(cfg.root, run_path)
        append_switch_event(cfg.root, f"AB-{safe_ver}", "failed", ["health_check_failed"], ref)
        append_change_log(cfg.root, "AB switch failed", f"version={safe_ver}")
        refresh_status(cfg)
        return {"ok": False, "status": "failed", "detail": (health.stderr or health.stdout or "health failed").strip(), "elapsed_ms": elapsed_ms}

    state["slots"][standby] = {"version": safe_ver, "script": relative_to_root(cfg.root, dst), "updated_at": iso_ts(now_local())}
    state["previous_slot"] = active
    state["active_slot"] = standby
    rto_ms = elapsed_ms
    rpo_ms = estimate_rpo_ms(cfg.root, now_local())
    state["last_switch"] = {
        "timestamp": iso_ts(now_local()),
        "trigger": trigger,
        "version": safe_ver,
        "from_slot": active,
        "to_slot": standby,
        "rto_ms": rto_ms,
        "rpo_ms": rpo_ms,
        "result": "success",
    }
    save_ab_state(cfg, state)
    gate_ok = rto_ms <= 30000 and rpo_ms <= 5000
    run_path.write_text(
        "\n".join(
            [
                "# AB Switch Success",
                f"- trigger: {trigger}",
                f"- version: {safe_ver}",
                f"- from_slot: {active}",
                f"- to_slot: {standby}",
                f"- rto_ms: {rto_ms}",
                f"- rpo_ms: {rpo_ms}",
                f"- gate_target_met: {gate_ok}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ref = relative_to_root(cfg.root, run_path)
    append_switch_event(cfg.root, f"AB-{safe_ver}", "success", ["auto_switch"], ref)
    append_change_log(cfg.root, "AB switch success", f"version={safe_ver}, from={active}, to={standby}, rto_ms={rto_ms}, rpo_ms={rpo_ms}")
    refresh_status(cfg)
    return {"ok": True, "status": "success", "active_slot": standby, "previous_slot": active, "version": safe_ver, "rto_ms": rto_ms, "rpo_ms": rpo_ms, "gate_target_met": gate_ok, "ref": ref}


def rollback_switch(cfg: AppConfig, trigger: str) -> dict[str, Any]:
    state = load_ab_state(cfg)
    active = str(state.get("active_slot") or "A")
    previous = str(state.get("previous_slot") or "")
    if previous not in {"A", "B"}:
        return {"ok": False, "status": "failed", "detail": "no previous slot"}
    rel_script = str((state.get("slots") or {}).get(previous, {}).get("script") or "")
    target = (cfg.root / rel_script).resolve() if rel_script else cfg.entry_script
    health = run_script(target, cfg.root, ["--mode", "status", "--focus", cfg.focus], timeout_s=90)
    run_path = unique_run_file(cfg.root, "ab-switch")
    if health.returncode != 0:
        run_path.write_text(
            "\n".join(
                [
                    "# AB Rollback Failed",
                    f"- trigger: {trigger}",
                    f"- from_slot: {active}",
                    f"- to_slot: {previous}",
                    f"- detail: {(health.stderr or health.stdout or 'health failed').strip()}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ref = relative_to_root(cfg.root, run_path)
        append_switch_event(cfg.root, "AB-ROLLBACK", "failed", ["rollback_health_check_failed"], ref)
        append_change_log(cfg.root, "AB rollback failed", "health check failed")
        refresh_status(cfg)
        return {"ok": False, "status": "failed", "detail": (health.stderr or health.stdout or "health failed").strip()}

    state["active_slot"] = previous
    state["previous_slot"] = active
    state["last_switch"] = {
        "timestamp": iso_ts(now_local()),
        "trigger": trigger,
        "version": str((state.get("slots") or {}).get(previous, {}).get("version") or "unknown"),
        "from_slot": active,
        "to_slot": previous,
        "result": "rollback_success",
    }
    save_ab_state(cfg, state)
    run_path.write_text(
        "\n".join(
            [
                "# AB Rollback Success",
                f"- trigger: {trigger}",
                f"- from_slot: {active}",
                f"- to_slot: {previous}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    ref = relative_to_root(cfg.root, run_path)
    append_switch_event(cfg.root, "AB-ROLLBACK", "success", ["rollback"], ref)
    append_change_log(cfg.root, "AB rollback success", f"from={active}, to={previous}")
    refresh_status(cfg)
    return {"ok": True, "status": "success", "active_slot": previous, "previous_slot": active, "ref": ref}


def run_decide(cfg: AppConfig, decision: str, reason: str, limit: int) -> dict[str, Any]:
    result = run_script(
        active_entry_script(cfg),
        cfg.root,
        ["--mode", "decide", "--decision", decision, "--reason", reason, "--limit", str(max(1, limit)), "--focus", cfg.focus],
        timeout_s=180,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "decide failed").strip())
    data = parse_kv(result.stdout, "decide>")
    sync_training_workflows(cfg.root)
    append_change_log(cfg.root, "decide action", f"decision={decision}, processed={data.get('processed',0)}, created_training={data.get('created_training',0)}")
    return {"processed": data.get("processed", 0), "decision": decision, "created_training": data.get("created_training", 0)}


def run_train(cfg: AppConfig, limit: int, max_retries: int) -> dict[str, Any]:
    result = run_script(
        active_entry_script(cfg),
        cfg.root,
        ["--mode", "train", "--limit", str(max(1, limit)), "--max-retries", str(max(1, max_retries)), "--focus", cfg.focus],
        timeout_s=300,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "train failed").strip())
    data = parse_kv(result.stdout, "train>")
    sync_training_workflows(cfg.root)
    append_change_log(cfg.root, "train action", f"processed={data.get('processed',0)}, done={data.get('done',0)}")
    return {"processed": data.get("processed", 0), "done": data.get("done", 0)}


def ingress_count_today(root: Path) -> int:
    key = now_local().strftime("%Y-%m-%d")
    route_marks = ",".join("?" for _ in CHAT_INGRESS_ROUTES)
    conn = connect_db(root)
    try:
        return int(
            conn.execute(
                f"""
                SELECT COUNT(1)
                FROM ingress_requests
                WHERE created_at LIKE ?
                  AND route IN ({route_marks})
                """,
                (f"{key}%", *CHAT_INGRESS_ROUTES),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def event_count_today(root: Path) -> int:
    key = now_local().strftime("%Y-%m-%d")
    conn = connect_db(root)
    try:
        return int(
            conn.execute(
                """
                SELECT COUNT(1)
                FROM conversation_events
                WHERE timestamp LIKE ?
                  AND actor='user'
                  AND stage='chat'
                  AND action='send_message'
                """,
                (f"{key}%",),
            ).fetchone()[0]
        )
    finally:
        conn.close()


def _reconcile_backfill_from_ingress(
    root: Path,
    ref: str,
    max_insert: int | None = None,
) -> tuple[int, int]:
    day_key = now_local().strftime("%Y-%m-%d")
    inserted = 0
    touched_rows = 0
    route_marks = ",".join("?" for _ in CHAT_INGRESS_ROUTES)
    conn = connect_db(root)
    try:
        ingress_rows = conn.execute(
            f"""
            SELECT request_id, session_id, created_at
            FROM ingress_requests
            WHERE created_at LIKE ?
              AND route IN ({route_marks})
            ORDER BY created_at ASC
            """,
            (f"{day_key}%", *CHAT_INGRESS_ROUTES),
        ).fetchall()
        if not ingress_rows:
            return 0, 0

        event_counts = {
            str(row["session_id"]): int(row["cnt"])
            for row in conn.execute(
                """
                SELECT session_id, COUNT(1) AS cnt
                FROM conversation_events
                WHERE timestamp LIKE ?
                  AND actor='user'
                  AND stage='chat'
                  AND action='send_message'
                GROUP BY session_id
                """,
                (f"{day_key}%",),
            ).fetchall()
        }

        by_session: dict[str, list[sqlite3.Row]] = {}
        for row in ingress_rows:
            sid = str(row["session_id"] or "")
            by_session.setdefault(sid, []).append(row)

        for session_id, rows in by_session.items():
            expected = len(rows)
            actual = int(event_counts.get(session_id, 0))
            missing = max(0, expected - actual)
            if missing <= 0:
                continue
            candidates = rows[-missing:]
            for item in candidates:
                if max_insert is not None and inserted >= max(0, max_insert):
                    conn.commit()
                    return inserted, touched_rows
                rid = str(item["request_id"] or "")
                if not rid:
                    continue
                created_at = str(item["created_at"] or iso_ts(now_local()))
                synthetic_id = safe_token(f"evt-rec-{rid}", f"evt-rec-{uuid.uuid4().hex[:12]}", 120)
                ret = conn.execute(
                    """
                    INSERT OR IGNORE INTO conversation_events (
                        event_id,timestamp,session_id,actor,stage,action,status,latency_ms,task_id,reason_tags_json,ref
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        synthetic_id,
                        created_at,
                        session_id,
                        "user",
                        "chat",
                        "send_message",
                        "failed",
                        0,
                        f"REC-{rid}",
                        json.dumps(["reconcile_backfill", f"request_id:{rid}"], ensure_ascii=False),
                        ref,
                    ),
                )
                if ret.rowcount > 0:
                    inserted += 1
                conn.execute(
                    "UPDATE ingress_requests SET event_logged=1 WHERE request_id=?",
                    (rid,),
                )
                touched_rows += 1
        conn.commit()
    finally:
        conn.close()
    return inserted, touched_rows


def run_reconcile(cfg: AppConfig, reason: str) -> dict[str, Any]:
    root_ready, root_error = agent_search_root_state(cfg.agent_search_root)
    if not root_ready:
        return {
            "run_at": iso_ts(now_local()),
            "reason": reason,
            "status": "blocked",
            "code": root_error or AGENT_SEARCH_ROOT_NOT_SET_CODE,
            "error": agent_search_root_block_message(root_error),
            "agent_search_root": agent_search_root_text(cfg.agent_search_root),
            "features_locked": True,
        }
    ingress_count = ingress_count_today(cfg.root)
    event_before = event_count_today(cfg.root)
    gap_before = max(0, ingress_count - event_before)
    inserted_jsonl = 0
    inserted_ingress = 0
    malformed = 0
    notes: list[str] = []
    run_path = unique_run_file(cfg.root, "reconcile")
    ref = relative_to_root(cfg.root, run_path)
    if gap_before > 0:
        result = run_script(active_entry_script(cfg), cfg.root, ["--mode", "backfill", "--focus", cfg.focus], timeout_s=180)
        if result.returncode == 0:
            data = parse_kv(result.stdout, "backfill>")
            inserted_jsonl = data.get("inserted", 0)
            malformed = data.get("malformed", 0)
            notes.append(f"jsonl_inserted={inserted_jsonl}")
            notes.append(f"malformed={malformed}")
        else:
            notes.append(f"backfill_failed={(result.stderr or result.stdout or '').strip()}")
        remaining_gap = max(0, ingress_count - event_count_today(cfg.root))
        inserted_ingress, touched_rows = _reconcile_backfill_from_ingress(
            cfg.root,
            ref,
            max_insert=remaining_gap,
        )
        notes.append(f"ingress_inserted={inserted_ingress}")
        notes.append(f"ingress_rows_touched={touched_rows}")

    event_after = event_count_today(cfg.root)
    gap_after = max(0, ingress_count - event_after)
    status = "success" if gap_after == 0 else "failed"
    inserted = inserted_jsonl + inserted_ingress
    run_path.write_text(
        "\n".join(
            [
                f"# Reconcile - {now_local().strftime('%Y-%m-%d %H:%M:%S%z')}",
                f"- reason: {reason}",
                f"- ingress_count: {ingress_count}",
                f"- event_count_before: {event_before}",
                f"- event_count_after: {event_after}",
                f"- gap_before: {gap_before}",
                f"- gap_after: {gap_after}",
                f"- backfill_inserted: {inserted}",
                f"- jsonl_inserted: {inserted_jsonl}",
                f"- ingress_inserted: {inserted_ingress}",
                f"- malformed: {malformed}",
                f"- status: {status}",
                f"- notes: {'; '.join(notes) if notes else 'none'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    conn = connect_db(cfg.root)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO reconcile_runs (run_id,run_at,reason,ingress_count,event_count_before,event_count_after,gap_before,gap_after,backfill_inserted,malformed,status,notes,ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"rec-{date_key(now_local())}-{uuid.uuid4().hex[:6]}",
                iso_ts(now_local()),
                reason,
                ingress_count,
                event_before,
                event_after,
                gap_before,
                gap_after,
                inserted,
                malformed,
                status,
                "; ".join(notes),
                ref,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    persist_event(
        cfg.root,
        {
            "event_id": event_id(),
            "timestamp": iso_ts(now_local()),
            "session_id": "sess-reconcile",
            "actor": "workflow",
            "stage": "analyze",
            "action": "reconcile_backfill",
            "status": status,
            "latency_ms": 0,
            "task_id": f"REC-{date_key(now_local())}",
            "reason_tags": ["gap_detected"] if gap_before > 0 else [],
            "ref": ref,
        },
    )
    if gap_before > 0 or gap_after > 0 or malformed > 0:
        append_failure_case(cfg.root, "reconcile_gap", f"reason={reason}, gap_before={gap_before}, gap_after={gap_after}, inserted={inserted}, malformed={malformed}, ref={ref}")
    append_change_log(cfg.root, "reconcile run", f"reason={reason}, ingress={ingress_count}, before={event_before}, after={event_after}, gap_after={gap_after}")
    refresh_status(cfg)
    return {
        "run_at": iso_ts(now_local()),
        "reason": reason,
        "ingress_count": ingress_count,
        "event_count_before": event_before,
        "event_count_after": event_after,
        "gap_before": gap_before,
        "gap_after": gap_after,
        "backfill_inserted": inserted,
        "malformed": malformed,
        "status": status,
        "ref": ref,
    }


def latest_reconcile(root: Path) -> dict[str, Any] | None:
    conn = connect_db(root)
    try:
        row = conn.execute(
            "SELECT run_id,run_at,reason,ingress_count,event_count_before,event_count_after,gap_before,gap_after,backfill_inserted,malformed,status,notes,ref FROM reconcile_runs ORDER BY run_at DESC LIMIT 1"
        ).fetchone()
        return {k: row[k] for k in row.keys()} if row else None
    finally:
        conn.close()


def start_reconcile_scheduler(cfg: AppConfig, state: RuntimeState) -> threading.Thread:
    def worker() -> None:
        reconcile_every = max(60, cfg.reconcile_interval_s)
        cleanup_every = max(3600, TEST_DATA_CLEANUP_INTERVAL_S)
        now_ts = time.time()
        next_reconcile_at = now_ts + reconcile_every
        next_cleanup_at = now_ts + cleanup_every
        while not state.stop_event.is_set():
            now_ts = time.time()
            if now_ts >= next_reconcile_at:
                try:
                    with state.reconcile_lock:
                        run_reconcile(cfg, "scheduled")
                except Exception as exc:
                    append_failure_case(cfg.root, "scheduled_reconcile_failed", str(exc))
                    append_change_log(cfg.root, "scheduled reconcile failed", str(exc))
                next_reconcile_at = now_ts + reconcile_every
            if TEST_DATA_AUTO_CLEANUP_ENABLED and now_ts >= next_cleanup_at:
                try:
                    if active_runtime_task_count(state) <= 0:
                        cleanup_result = admin_cleanup_history(
                            cfg.root,
                            mode="test_data",
                            delete_artifacts=True,
                            delete_log_files=False,
                            max_age_hours=TEST_DATA_MAX_AGE_HOURS,
                            include_active_test_sessions=False,
                        )
                        deleted = int(cleanup_result.get("deleted_sessions") or 0)
                        if deleted > 0:
                            append_change_log(
                                cfg.root,
                                "scheduled test-data cleanup",
                                (
                                    f"deleted_sessions={deleted}, "
                                    f"max_age_hours={cleanup_result.get('max_age_hours')}, "
                                    f"skipped_active={cleanup_result.get('skipped_active',0)}, "
                                    f"skipped_recent={cleanup_result.get('skipped_recent',0)}"
                                ),
                            )
                except Exception as exc:
                    append_failure_case(cfg.root, "scheduled_testdata_cleanup_failed", str(exc))
                    append_change_log(cfg.root, "scheduled test-data cleanup failed", str(exc))
                next_cleanup_at = now_ts + cleanup_every
            sleep_until = next_reconcile_at
            if TEST_DATA_AUTO_CLEANUP_ENABLED:
                sleep_until = min(sleep_until, next_cleanup_at)
            wait_seconds = max(1.0, sleep_until - time.time())
            if state.stop_event.wait(wait_seconds):
                break

    t = threading.Thread(target=worker, daemon=True, name="reconcile-scheduler")
    t.start()
    return t


def dashboard(cfg: AppConfig, *, include_test_data: bool = True) -> dict[str, Any]:
    pa, pt = pending_counts(cfg.root, include_test_data=include_test_data)
    ld, lt = latest_results(cfg.root, include_test_data=include_test_data)
    root_ready, root_error = agent_search_root_state(cfg.agent_search_root)
    if AB_FEATURE_ENABLED:
        ab = ab_status(cfg)
    else:
        ab = {
            "active_slot": "disabled",
            "standby_slot": "disabled",
            "active_version": "disabled",
            "standby_version": "disabled",
        }
    agents = list_available_agents(cfg) if root_ready else []
    closure_stats = policy_closure_stats(cfg.root)
    return {
        "ok": True,
        "new_sessions_24h": new_sessions_24h(cfg.root, include_test_data=include_test_data),
        "pending_analysis": pa,
        "pending_training": pt,
        "latest_decision": ld,
        "latest_training": lt,
        "active_slot": ab["active_slot"],
        "standby_slot": ab["standby_slot"],
        "active_version": ab["active_version"],
        "standby_version": ab["standby_version"],
        "available_agents": len(agents),
        "ab_enabled": AB_FEATURE_ENABLED,
        "policy_closure": closure_stats,
        "agent_search_root": agent_search_root_text(cfg.agent_search_root),
        "agent_search_root_ready": bool(root_ready),
        "agent_search_root_error": root_error,
        "features_locked": not bool(root_ready),
    }


