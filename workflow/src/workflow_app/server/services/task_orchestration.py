from __future__ import annotations

def bind_runtime_symbols(symbols: dict[str, object]) -> None:
    globals().update(symbols)

def session_lock_for(state: RuntimeState, session_id: str) -> threading.Lock:
    with state.session_lock_guard:
        lock = state.session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
            state.session_locks[session_id] = lock
        return lock


def acquire_generation_slot(state: RuntimeState, session_id: str) -> threading.Lock:
    lock = session_lock_for(state, session_id)
    lock.acquire()
    if not state.generation_semaphore.acquire(blocking=False):
        lock.release()
        raise ConcurrencyLimitError(
            f"generation concurrency limit reached ({MAX_GENERATION_CONCURRENCY})"
        )
    return lock


def release_generation_slot(state: RuntimeState, lock: threading.Lock | None) -> None:
    if lock is None:
        return
    state.generation_semaphore.release()
    lock.release()


def new_task_id() -> str:
    ts = now_local()
    return f"task-{date_key(ts)}-{uuid.uuid4().hex[:8]}"


def redact_command(parts: list[str]) -> list[str]:
    out: list[str] = []
    for item in parts:
        text = str(item)
        lower = text.lower()
        if any(key in lower for key in ["api_key", "token", "secret", "password"]):
            out.append("***")
            continue
        if text.startswith("sk-"):
            out.append("***")
            continue
        out.append(text)
    return out


def build_agent_command(
    cfg: AppConfig,
    task_id_text: str,
    session: dict[str, str],
    message: str,
    focus: str,
    write_targets: list[str],
) -> tuple[list[str], list[str]]:
    runner = (cfg.root / "scripts" / "task_agent_runner.py").resolve()
    if not runner.exists():
        runner = (WORKFLOW_APP_ROOT / "task_agent_runner.py").resolve()
    trace_file = task_trace_file(cfg.root, task_id_text)
    cmd = [
        sys.executable,
        "-u",
        str(runner),
        "--root",
        str(cfg.root),
        "--session-id",
        session["session_id"],
        "--agent",
        session["agent_name"],
        "--agent-search-root",
        session["agent_search_root"],
        "--focus",
        focus,
        "--message",
        message,
        "--trace-file",
        str(trace_file),
    ]
    for target in write_targets:
        cmd.extend(["--write-target", target])
    return cmd, redact_command(cmd)


def create_task_run(
    root: Path,
    task_id_text: str,
    session_id: str,
    agent_name: str,
    agent_search_root: str,
    message: str,
    command: list[str],
    command_display: list[str],
) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            """
            INSERT INTO task_runs (
                task_id,session_id,agent_name,agent_search_root,default_agents_root,target_path,status,message,command_json,command_display,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id_text,
                session_id,
                agent_name,
                agent_search_root,
                agent_search_root,
                agent_search_root,
                "pending",
                message,
                json.dumps(command, ensure_ascii=False),
                json.dumps(command_display, ensure_ascii=False),
                iso_ts(now_local()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def append_task_event(
    root: Path,
    task_id_text: str,
    event_type: str,
    payload: dict[str, Any],
) -> int:
    ts = iso_ts(now_local())
    conn = connect_db(root)
    try:
        ret = conn.execute(
            "INSERT INTO task_events (task_id,timestamp,event_type,payload_json) VALUES (?,?,?,?)",
            (
                task_id_text,
                ts,
                event_type,
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(ret.lastrowid or 0)
    finally:
        conn.close()


def get_task_run(root: Path, task_id_text: str) -> dict[str, Any] | None:
    conn = connect_db(root)
    try:
        row = conn.execute(
            """
            SELECT task_id,session_id,agent_name,agent_search_root,default_agents_root,target_path,status,message,command_json,command_display,start_at,end_at,duration_ms,stdout,stderr,summary,ref,created_at
            FROM task_runs
            WHERE task_id=?
            """,
            (task_id_text,),
        ).fetchone()
        if not row:
            return None
        out = {k: row[k] for k in row.keys()}
        try:
            out["command"] = json.loads(str(out.get("command_display") or "[]"))
        except Exception:
            out["command"] = []
        return out
    finally:
        conn.close()


def list_session_task_runs(root: Path, session_id: str, limit: int = 200) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT task_id,session_id,agent_name,status,message,summary,created_at,start_at,end_at,duration_ms,command_display,ref
            FROM task_runs
            WHERE session_id=?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (session_id, max(1, min(limit, 2000))),
        ).fetchall()
        out: list[dict[str, Any]] = []
        for row in rows:
            item = {k: row[k] for k in row.keys()}
            try:
                item["command"] = json.loads(str(item.get("command_display") or "[]"))
            except Exception:
                item["command"] = []
            task_id_text = str(item.get("task_id") or "")
            item["trace_available"] = bool(task_id_text and task_trace_file(root, task_id_text).exists())
            out.append(item)
        return out
    finally:
        conn.close()


def list_task_events(root: Path, task_id_text: str, since_id: int, limit: int = 400) -> list[dict[str, Any]]:
    conn = connect_db(root)
    try:
        rows = conn.execute(
            """
            SELECT event_id,timestamp,event_type,payload_json
            FROM task_events
            WHERE task_id=? AND event_id>?
            ORDER BY event_id ASC
            LIMIT ?
            """,
            (task_id_text, max(0, since_id), max(1, min(limit, 1000))),
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
                    "timestamp": str(row["timestamp"]),
                    "event_type": str(row["event_type"]),
                    "payload": payload,
                }
            )
        return out
    finally:
        conn.close()


def update_task_run_result(
    root: Path,
    task_id_text: str,
    *,
    status: str,
    start_at: str | None,
    end_at: str | None,
    duration_ms: int | None,
    stdout_text: str,
    stderr_text: str,
    summary: str,
    ref: str,
) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            """
            UPDATE task_runs
            SET status=?,start_at=?,end_at=?,duration_ms=?,stdout=?,stderr=?,summary=?,ref=?
            WHERE task_id=?
            """,
            (
                status,
                start_at,
                end_at,
                duration_ms,
                stdout_text,
                stderr_text,
                summary,
                ref,
                task_id_text,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def mark_task_status(root: Path, task_id_text: str, status: str, *, started_at: str | None = None) -> None:
    conn = connect_db(root)
    try:
        if started_at:
            conn.execute(
                "UPDATE task_runs SET status=?,start_at=COALESCE(start_at,?) WHERE task_id=?",
                (status, started_at, task_id_text),
            )
        else:
            conn.execute("UPDATE task_runs SET status=? WHERE task_id=?", (status, task_id_text))
        conn.commit()
    finally:
        conn.close()


def task_run_file(root: Path, task_id_text: str) -> Path:
    return root / "logs" / "runs" / f"{task_id_text}.md"


def task_trace_file(root: Path, task_id_text: str) -> Path:
    return root / "logs" / "runs" / f"{task_id_text}.trace.json"


def load_task_trace(root: Path, task_id_text: str) -> dict[str, Any]:
    path = task_trace_file(root, task_id_text)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        return {}
    return {}


def write_task_run_file(
    root: Path,
    task_id_text: str,
    *,
    session_id: str,
    agent_name: str,
    agent_search_root: str,
    status: str,
    start_at: str,
    end_at: str,
    duration_ms: int,
    command_display: list[str],
    stdout_text: str,
    stderr_text: str,
    summary: str,
) -> str:
    path = task_run_file(root, task_id_text)
    trace_rel = relative_to_root(root, task_trace_file(root, task_id_text))
    content = "\n".join(
        [
            f"# Task Run - {task_id_text}",
            "",
            f"- task_id: {task_id_text}",
            f"- session_id: {session_id}",
            f"- agent_name: {agent_name}",
            f"- agent_search_root: {agent_search_root}",
            f"- status: {status}",
            f"- start_at: {start_at}",
            f"- end_at: {end_at}",
            f"- duration_ms: {duration_ms}",
            f"- command: {' '.join(command_display)}",
            f"- trace: {trace_rel}",
            "",
            "## Summary",
            summary or "none",
            "",
            "## STDOUT",
            stdout_text or "",
            "",
            "## STDERR",
            stderr_text or "",
        ]
    )
    path.write_text(content + "\n", encoding="utf-8")
    return relative_to_root(root, path)


def set_runtime_task(state: RuntimeState, runtime: TaskRuntime | None, task_id_text: str) -> None:
    with state.task_runtime_lock:
        if runtime is None:
            state.active_tasks.pop(task_id_text, None)
        else:
            state.active_tasks[task_id_text] = runtime


def get_runtime_task(state: RuntimeState, task_id_text: str) -> TaskRuntime | None:
    with state.task_runtime_lock:
        return state.active_tasks.get(task_id_text)


def active_runtime_task_count(state: RuntimeState) -> int:
    with state.task_runtime_lock:
        return len(state.active_tasks)


def has_session_runtime_task(state: RuntimeState, session_id: str) -> bool:
    with state.task_runtime_lock:
        return any(rt.session_id == session_id for rt in state.active_tasks.values())


def training_workflow_has_running_task(root: Path, state: RuntimeState, workflow_id: str) -> bool:
    workflow = get_training_workflow(root, workflow_id)
    if not workflow:
        return False
    session_id = str(workflow.get("session_id") or "")
    if session_id and has_session_runtime_task(state, session_id):
        return True
    analysis_id = str(workflow.get("analysis_id") or "")
    if not analysis_id:
        return False
    conn = connect_db(root)
    try:
        row = conn.execute(
            "SELECT COUNT(1) AS cnt FROM training_tasks WHERE analysis_id=? AND status='running'",
            (analysis_id,),
        ).fetchone()
        return bool(int(row["cnt"] if row else 0) > 0)
    finally:
        conn.close()


def append_admin_event(
    root: Path,
    *,
    session_id: str,
    action: str,
    status: str,
    reason_tags: list[str],
    ref: str,
) -> None:
    persist_event(
        root,
        {
            "event_id": event_id(),
            "timestamp": iso_ts(now_local()),
            "session_id": session_id,
            "actor": "workflow",
            "stage": "governance",
            "action": action,
            "status": status,
            "latency_ms": 0,
            "task_id": "",
            "reason_tags": reason_tags,
            "ref": ref,
        },
    )


def execute_task_worker(
    cfg: AppConfig,
    state: RuntimeState,
    task_id_text: str,
    session: dict[str, str],
    message: str,
    focus: str,
    command: list[str],
    command_display: list[str],
) -> None:
    runtime = TaskRuntime(
        task_id=task_id_text,
        session_id=session["session_id"],
        agent_name=session["agent_name"],
    )
    set_runtime_task(state, runtime, task_id_text)
    append_task_event(
        cfg.root,
        task_id_text,
        "queued",
        {
            "task_id": task_id_text,
            "session_id": session["session_id"],
            "agent_name": session["agent_name"],
        },
    )
    lock: threading.Lock | None = None
    start_ts = now_local()
    start_at = iso_ts(start_ts)
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    status = "failed"
    summary = ""
    ref = ""
    try:
        mark_task_status(cfg.root, task_id_text, "queued")
        lock = session_lock_for(state, session["session_id"])
        lock.acquire()
        state.generation_semaphore.acquire()
        if runtime.stop_event.is_set():
            status = "interrupted"
            summary = "interrupted before command start"
            append_task_event(cfg.root, task_id_text, "interrupted", {"reason": summary})
            return

        mark_task_status(cfg.root, task_id_text, "running", started_at=start_at)
        append_task_event(
            cfg.root,
            task_id_text,
            "running",
            {"task_id": task_id_text, "command": command_display},
        )
        runtime.process = subprocess.Popen(
            command,
            cwd=str(cfg.root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        append_task_event(
            cfg.root,
            task_id_text,
            "process_started",
            {"pid": int(runtime.process.pid)},
        )

        def read_stream(name: str, pipe: Any, collector: list[str]) -> None:
            if pipe is None:
                return
            pending: list[str] = []
            while True:
                chunk = pipe.read(1)
                if chunk == "":
                    break
                collector.append(chunk)
                pending.append(chunk)
                if chunk == "\n" or len(pending) >= 64:
                    text = "".join(pending)
                    pending.clear()
                    append_task_event(
                        cfg.root,
                        task_id_text,
                        f"{name}_chunk",
                        {"chunk": text},
                    )
                if runtime.stop_event.is_set() and runtime.process and runtime.process.poll() is not None:
                    break
            if pending:
                append_task_event(
                    cfg.root,
                    task_id_text,
                    f"{name}_chunk",
                    {"chunk": "".join(pending)},
                )

        t_out = threading.Thread(
            target=read_stream,
            args=("stdout", runtime.process.stdout, stdout_chunks),
            daemon=True,
        )
        t_err = threading.Thread(
            target=read_stream,
            args=("stderr", runtime.process.stderr, stderr_chunks),
            daemon=True,
        )
        t_out.start()
        t_err.start()
        rc = runtime.process.wait()
        t_out.join(timeout=2)
        t_err.join(timeout=2)
        if runtime.stop_event.is_set():
            status = "interrupted"
            summary = "process interrupted by user"
        elif rc == 0:
            status = "success"
            summary = "command completed successfully"
        else:
            status = "failed"
            summary = f"command exit code={rc}"
    except Exception as exc:
        status = "failed"
        summary = f"{exc.__class__.__name__}: {exc}"
        stderr_chunks.append(summary + "\n")
        append_task_event(
            cfg.root,
            task_id_text,
            "error",
            {"error": summary},
        )
    finally:
        end_ts = now_local()
        end_at = iso_ts(end_ts)
        duration_ms = max(0, int((end_ts - start_ts).total_seconds() * 1000))
        stdout_text = "".join(stdout_chunks)
        stderr_text = "".join(stderr_chunks)
        if not summary:
            summary = "no summary"
        assistant_reply = stdout_text.rstrip("\n")
        if status == "success" and assistant_reply:
            try:
                add_message(cfg.root, session["session_id"], "assistant", assistant_reply)
            except Exception:
                pass
        ref = write_task_run_file(
            cfg.root,
            task_id_text,
            session_id=session["session_id"],
            agent_name=session["agent_name"],
            agent_search_root=session["agent_search_root"],
            status=status,
            start_at=start_at,
            end_at=end_at,
            duration_ms=duration_ms,
            command_display=command_display,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            summary=summary,
        )
        update_task_run_result(
            cfg.root,
            task_id_text,
            status=status,
            start_at=start_at,
            end_at=end_at,
            duration_ms=duration_ms,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
            summary=summary,
            ref=ref,
        )
        append_task_event(
            cfg.root,
            task_id_text,
            "done",
            {
                "task_id": task_id_text,
                "status": status,
                "summary": summary,
                "duration_ms": duration_ms,
                "ref": ref,
            },
        )
        persist_event(
            cfg.root,
            {
                "event_id": event_id(),
                "timestamp": iso_ts(now_local()),
                "session_id": session["session_id"],
                "actor": "agent",
                "stage": "chat",
                "action": "send_message",
                "status": "success" if status == "success" else "failed",
                "latency_ms": duration_ms,
                "task_id": task_id_text,
                "reason_tags": (
                    session_policy_reason_tags(session)
                    if status == "success"
                    else [status, *session_policy_reason_tags(session)]
                ),
                "ref": ref,
            },
        )
        persist_event(
            cfg.root,
            {
                "event_id": event_id(),
                "timestamp": iso_ts(now_local()),
                "session_id": session["session_id"],
                "actor": "workflow",
                "stage": "chat",
                "action": "task_execute",
                "status": "success" if status == "success" else "failed",
                "latency_ms": duration_ms,
                "task_id": task_id_text,
                "reason_tags": (
                    session_policy_reason_tags(session)
                    if status == "success"
                    else [status, *session_policy_reason_tags(session)]
                ),
                "ref": ref,
            },
        )
        try:
            refresh_status(cfg)
            sync_analysis_tasks(cfg.root)
            sync_training_workflows(cfg.root)
        except Exception:
            pass
        if lock is not None:
            state.generation_semaphore.release()
            lock.release()
        set_runtime_task(state, None, task_id_text)


def request_task_interrupt(cfg: AppConfig, state: RuntimeState, task_id_text: str) -> tuple[bool, str]:
    runtime = get_runtime_task(state, task_id_text)
    if runtime is None:
        row = get_task_run(cfg.root, task_id_text)
        if not row:
            return False, "task not found"
        status = str(row.get("status") or "")
        if status in {"pending", "queued"}:
            mark_task_status(cfg.root, task_id_text, "interrupted")
            append_task_event(cfg.root, task_id_text, "interrupted", {"reason": "cancelled before start"})
            return True, "interrupted"
        return False, f"task not running (status={status})"
    runtime.stop_event.set()
    runtime.interrupted = True
    append_task_event(cfg.root, task_id_text, "interrupt_requested", {"task_id": task_id_text})
    proc = runtime.process
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        except Exception:
            pass
    return True, "interrupt requested"


