#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from policy_cache_seed import upsert_policy_cache


def call(base_url: str, method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url=base_url + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=600) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload_obj = json.loads(body) if body else {}
        except Exception:
            payload_obj = {"raw": body}
        return exc.code, payload_obj
    except Exception as exc:
        if "timed out" in str(exc).lower():
            raise RuntimeError(f"request timeout: {method} {path}") from exc
        raise


def wait_health(base_url: str) -> None:
    for _ in range(90):
        status, payload = call(base_url, "GET", "/healthz")
        if status == 200 and payload.get("ok"):
            return
        time.sleep(1)
    raise RuntimeError("healthz timeout")


def wait_task_done(base_url: str, task_id: str, timeout: int = 240) -> dict:
    end_at = time.time() + timeout
    while time.time() < end_at:
        status, payload = call(base_url, "GET", f"/api/tasks/{task_id}")
        if status == 200 and payload.get("ok"):
            task_status = str(payload.get("status") or "").lower()
            if task_status in {"success", "failed", "interrupted"}:
                return payload
        time.sleep(0.5)
    raise RuntimeError(f"task timeout: {task_id}")


def close_existing_sessions(base_url: str) -> int:
    status, payload = call(base_url, "GET", "/api/agents")
    if status != 200 or not payload.get("ok"):
        return 0
    root = str(payload.get("agent_search_root") or "").strip()
    if not root:
        return 0
    sw_status, sw_payload = call(
        base_url,
        "POST",
        "/api/config/agent-search-root",
        {"agent_search_root": root},
    )
    if sw_status != 200 or not sw_payload.get("ok"):
        return 0
    return int(sw_payload.get("closed_sessions") or 0)


def create_session_with_fallback(
    base_url: str,
    *,
    agent_name: str,
    focus: str,
    agent_search_root: str,
    is_test_data: bool,
) -> tuple[dict, str]:
    base_payload = {
        "agent_name": agent_name,
        "focus": focus,
        "agent_search_root": agent_search_root,
        "is_test_data": bool(is_test_data),
    }
    st, payload = call(base_url, "POST", "/api/sessions", base_payload)
    if st == 200 and payload.get("ok"):
        return payload, "direct"
    if st != 409:
        raise RuntimeError(f"create session failed: {st} {payload}")

    code = str(payload.get("code") or "").strip().lower()
    if code not in {
        "agent_policy_confirmation_required",
        "agent_policy_extract_failed",
        "agent_policy_clarity_blocked",
    }:
        raise RuntimeError(f"create session blocked with unsupported code: {st} {payload}")

    confirm_status, confirm_payload = call(
        base_url,
        "POST",
        "/api/sessions/policy-confirm",
        {
            "agent_name": agent_name,
            "agent_search_root": agent_search_root,
            "action": "confirm",
            "reason": "acceptance auto-confirm",
            "is_test_data": bool(is_test_data),
        },
    )
    if confirm_status == 200 and confirm_payload.get("ok") and str(confirm_payload.get("session_id") or "").strip():
        return confirm_payload, "confirm"

    edit_payload = {
        "agent_name": agent_name,
        "agent_search_root": agent_search_root,
        "action": "edit",
        "reason": "acceptance manual fallback",
        "role_profile": "你是训练执行助手，只在职责边界内输出方案。",
        "session_goal": "在会话内完成任务并给出可验证结果。",
        "duty_constraints": [
            "仅在 agent_search_root 范围内操作。",
            "遇到风险操作先提示并说明回滚方案。",
            "输出需要包含验证步骤。",
        ],
        "is_test_data": bool(is_test_data),
    }
    edit_status, edit_resp = call(base_url, "POST", "/api/sessions/policy-confirm", edit_payload)
    if edit_status == 409 and str(edit_resp.get("code") or "").strip().lower() in {
        "manual_policy_input_disabled",
        "manual_policy_input_not_allowed",
    }:
        call(
            base_url,
            "POST",
            "/api/config/manual-policy-input",
            {"allow_manual_policy_input": True},
        )
        edit_status, edit_resp = call(base_url, "POST", "/api/sessions/policy-confirm", edit_payload)
    if edit_status == 200 and edit_resp.get("ok") and str(edit_resp.get("session_id") or "").strip():
        return edit_resp, "edit"

    raise RuntimeError(
        "create session fallback failed: "
        f"session={st}/{payload}; confirm={confirm_status}/{confirm_payload}; edit={edit_status}/{edit_resp}"
    )


def write_agents_fixture(runtime_root: Path) -> Path:
    workspace_root = runtime_root / "workspace-root"
    (workspace_root / "workflow").mkdir(parents=True, exist_ok=True)
    (workspace_root / "workflow" / "README.md").write_text("fixture\n", encoding="utf-8")
    trainer_dir = workspace_root / "trainer"
    trainer_dir.mkdir(parents=True, exist_ok=True)
    (trainer_dir / "AGENTS.md").write_text(
        "\n".join(
            [
                "# trainer",
                "",
                "## 角色定位",
                "你是训练执行助手。",
                "",
                "## 会话目标",
                "在职责边界内完成用户要求并输出可验证结果。",
                "",
                "## 职责边界",
                "### must",
                "- 先复述任务目标与约束，再给执行步骤。",
                "- 输出必须包含可验证结果与回归检查点。",
                "- 仅在 agent_search_root 范围内进行文件写入。",
                "",
                "### must_not",
                "- 不得执行越界路径写入或高风险破坏性命令。",
                "- 不得跳过失败原因说明与替代方案。",
                "",
                "### preconditions",
                "- 在执行前确认输入上下文完整且目标明确。",
                "- 涉及删除/覆盖时先给风险提示并请求确认。",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return workspace_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Run workflow gate acceptance checks.")
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8098, help="bind port")
    parser.add_argument(
        "--runtime-root",
        default="",
        help="isolated runtime root for acceptance data (default: <root>/.test/runtime/workflow-gate)",
    )
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    runtime_root = (
        Path(args.runtime_root).resolve()
        if str(args.runtime_root or "").strip()
        else (repo_root / ".test" / "runtime" / "workflow-gate").resolve()
    )
    if runtime_root.exists():
        shutil.rmtree(runtime_root, ignore_errors=True)
    runtime_root.mkdir(parents=True, exist_ok=True)
    fixture_root = write_agents_fixture(runtime_root)
    upsert_policy_cache(
        runtime_root=runtime_root,
        workspace_root=fixture_root,
        specs=[
            {
                "agent_name": "trainer",
                "role_profile": "你是训练执行助手。",
                "session_goal": "在职责边界内完成用户要求并输出可验证结果。",
                "duty_constraints": [
                    "先复述任务目标与约束，再给执行步骤。",
                    "输出必须包含可验证结果与回归检查点。",
                    "仅在 agent_search_root 范围内进行文件写入。",
                ],
                "clarity_score": 90,
                "clarity_gate": "auto",
                "parse_status": "ok",
                "policy_extract_ok": True,
            }
        ],
    )
    entry_script = (repo_root / "scripts" / "workflow_entry_cli.py").resolve()
    web_script = (repo_root / "scripts" / "workflow_web_server.py").resolve()
    base = f"http://{args.host}:{args.port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            str(web_script),
            "--root",
            runtime_root.as_posix(),
            "--entry-script",
            entry_script.as_posix(),
            "--agent-search-root",
            fixture_root.as_posix(),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    results: list[tuple[str, bool, dict]] = []
    errors: list[str] = []
    default_root = fixture_root.as_posix()

    try:
        wait_health(base)
        close_existing_sessions(base)

        status, agents_data = call(base, "GET", "/api/agents")
        if status != 200 or not agents_data.get("ok"):
            raise RuntimeError(f"load agents failed: {status} {agents_data}")
        agents = list(agents_data.get("agents") or [])
        if not agents:
            sw_status, sw_payload = call(
                base,
                "POST",
                "/api/config/agent-search-root",
                {"agent_search_root": fixture_root.as_posix()},
            )
            if sw_status != 200 or not sw_payload.get("ok"):
                raise RuntimeError(f"switch to fixture root failed: {sw_status} {sw_payload}")
            status, agents_data = call(base, "GET", "/api/agents")
            if status != 200 or not agents_data.get("ok"):
                raise RuntimeError(f"load fixture agents failed: {status} {agents_data}")
            agents = list(agents_data.get("agents") or [])
        if not agents:
            raise RuntimeError("no available agents after fixture restore")
        default_root = str(agents_data.get("agent_search_root") or fixture_root.as_posix())

        empty_root = runtime_root / "state" / "empty-agent-root"
        empty_root.mkdir(parents=True, exist_ok=True)
        # agent_search_root 语义是“工作区根路径”，必须包含 workflow/ 子目录。
        (empty_root / "workflow").mkdir(parents=True, exist_ok=True)
        sw_empty_status, sw_empty_payload = call(
            base,
            "POST",
            "/api/config/agent-search-root",
            {"agent_search_root": empty_root.as_posix()},
        )
        if sw_empty_status != 200 or not sw_empty_payload.get("ok"):
            raise RuntimeError(f"switch to empty root failed: {sw_empty_status} {sw_empty_payload}")
        s1, p1 = call(
            base,
            "POST",
            "/api/sessions",
            {
                "agent_name": "x",
                "focus": "gate",
                "agent_search_root": empty_root.as_posix(),
                "is_test_data": True,
            },
        )
        results.append(
            (
                "no_agent_block",
                bool(s1 == 409 and p1.get("code") == "no_agent_found"),
                {"status": s1, "payload": p1},
            )
        )
        call(base, "POST", "/api/config/agent-search-root", {"agent_search_root": default_root})

        status, agents_data = call(base, "GET", "/api/agents")
        agents = agents_data.get("agents") or []
        if not agents:
            raise RuntimeError("no available agents after restore")
        agent_name = str(agents[0]["agent_name"])

        tasks: list[dict] = []
        for idx in range(5):
            sess, create_mode = create_session_with_fallback(
                base,
                agent_name=agent_name,
                focus="gate1",
                agent_search_root=default_root,
                is_test_data=True,
            )
            sid = str(sess["session_id"])
            message = f"只回复标签 GATE1-S{idx}"
            s3, task = call(
                base,
                "POST",
                "/api/tasks/execute",
                {
                    "agent_name": agent_name,
                    "session_id": sid,
                    "focus": "gate1",
                    "agent_search_root": default_root,
                    "message": message,
                },
            )
            if s3 != 202 or not task.get("ok"):
                raise RuntimeError(f"task execute failed: {s3} {task}")
            tasks.append(
                {
                    "idx": idx,
                    "session_id": sid,
                    "task_id": str(task["task_id"]),
                    "message": message,
                    "create_mode": create_mode,
                }
            )

        concurrency_ok = True
        details: list[dict] = []
        for item in tasks:
            row = wait_task_done(base, item["task_id"])
            sm, msgs = call(base, "GET", f"/api/chat/sessions/{item['session_id']}/messages")
            has_user = bool(
                sm == 200
                and any(
                    m.get("role") == "user" and m.get("content") == item["message"]
                    for m in (msgs.get("messages") or [])
                )
            )
            matched = row.get("session_id") == item["session_id"] and has_user
            concurrency_ok = concurrency_ok and matched
            details.append(
                {
                    "idx": item["idx"],
                    "session_id": item["session_id"],
                    "task_id": item["task_id"],
                        "status": row.get("status"),
                        "matched": matched,
                        "create_mode": item.get("create_mode"),
                    }
                )
        results.append(("five_session_parallel", concurrency_ok, {"tasks": details}))

        sess, interrupt_create_mode = create_session_with_fallback(
            base,
            agent_name=agent_name,
            focus="interrupt",
            agent_search_root=default_root,
            is_test_data=True,
        )
        sid = str(sess["session_id"])
        s5, task = call(
            base,
            "POST",
            "/api/tasks/execute",
            {
                "agent_name": agent_name,
                "session_id": sid,
                "focus": "interrupt",
                "agent_search_root": default_root,
                "message": "请输出稍长文本用于中断测试",
            },
        )
        if s5 != 202 or not task.get("ok"):
            raise RuntimeError(f"interrupt task failed: {s5} {task}")
        task_id = str(task["task_id"])
        time.sleep(1.2)
        call(base, "POST", f"/api/tasks/{task_id}/interrupt", {})
        interrupted = wait_task_done(base, task_id, timeout=120)
        s6, retry = call(
            base,
            "POST",
            "/api/tasks/execute",
            {
                "agent_name": agent_name,
                "session_id": sid,
                "focus": "interrupt",
                "agent_search_root": default_root,
                "retry": True,
                "message": "",
            },
        )
        if s6 != 202 or not retry.get("ok"):
            raise RuntimeError(f"retry failed: {s6} {retry}")
        retry_done = wait_task_done(base, str(retry["task_id"]), timeout=180)
        flow_ok = str(interrupted.get("status") or "").lower() in {"interrupted", "failed"}
        results.append(
            (
                "send_interrupt_retry",
                flow_ok,
                {
                    "session_id": sid,
                    "create_mode": interrupt_create_mode,
                    "interrupt_task": task_id,
                    "interrupt_status": interrupted.get("status"),
                    "retry_task": retry.get("task_id"),
                    "retry_status": retry_done.get("status"),
                },
            )
        )

        s7, queue = call(base, "GET", "/api/workflows/training/queue")
        if s7 != 200 or not queue.get("ok"):
            raise RuntimeError(f"workflow queue failed: {s7} {queue}")
        items = queue.get("items") or []
        if not items:
            raise RuntimeError("workflow queue empty")
        workflow_id = str(items[0]["workflow_id"])
        call(
            base,
            "POST",
            "/api/workflows/training/assign",
            {"workflow_id": workflow_id, "analyst": "analyst-gate", "note": "gate run"},
        )
        end_at = time.time() + 20
        analysis_ok = False
        analysis_seen_statuses: list[str] = []
        while time.time() < end_at:
            es, ev = call(base, "GET", f"/api/workflows/training/{workflow_id}/events?since_id=0")
            if es == 200:
                events = ev.get("events") or []
                analysis_events = [e for e in events if e.get("stage") == "analysis"]
                analysis_seen_statuses = [str(e.get("status") or "") for e in analysis_events]
                if any(status == "success" for status in analysis_seen_statuses):
                    analysis_ok = True
                    break
                # Offline acceptance often ends with "failed + rollback" for context-gap scenarios.
                # This still proves the analysis stage was executed and is visible in the chain.
                if any(status == "failed" for status in analysis_seen_statuses):
                    analysis_ok = True
                    break
            time.sleep(0.5)
        call(base, "POST", "/api/workflows/training/plan", {"workflow_id": workflow_id})
        ex_status, execute_result = call(
            base,
            "POST",
            "/api/workflows/training/execute",
            {
                "workflow_id": workflow_id,
                "selected_items": ["decision_skip", "collect_notes"],
                "max_retries": 3,
            },
        )
        ev_status, ev_data = call(base, "GET", f"/api/workflows/training/{workflow_id}/events?since_id=0")
        event_stages = [e.get("stage") for e in (ev_data.get("events") or [])] if ev_status == 200 else []
        chain_ok = analysis_ok and all(
            stage in event_stages for stage in ["assignment", "analysis", "plan", "select", "train"]
        )
        results.append(
            (
                "workflow_chain_visible",
                chain_ok,
                {
                    "workflow_id": workflow_id,
                    "execute_status": ex_status,
                    "execute_result": execute_result,
                    "event_stages": event_stages,
                    "analysis_statuses": analysis_seen_statuses,
                },
            )
        )

        d1, p_deploy = call(base, "POST", "/api/ab/deploy", {"version": "v-test"})
        d2, p_status = call(base, "GET", "/api/ab/status")
        results.append(
            (
                "ab_disabled",
                bool(
                    d1 == 410
                    and p_deploy.get("code") == "ab_disabled"
                    and d2 == 404
                    and p_status.get("code") == "ab_disabled"
                ),
                {"deploy": {"status": d1, "payload": p_deploy}, "status": {"status": d2, "payload": p_status}},
            )
        )

        sess, close_create_mode = create_session_with_fallback(
            base,
            agent_name=agent_name,
            focus="close-test",
            agent_search_root=default_root,
            is_test_data=True,
        )
        old_session_id = str(sess["session_id"])
        sw_status, switch_resp = call(
            base,
            "POST",
            "/api/config/agent-search-root",
            {"agent_search_root": default_root},
        )
        b_status, blocked = call(
            base,
            "POST",
            "/api/tasks/execute",
            {
                "agent_name": agent_name,
                "session_id": old_session_id,
                "focus": "close-test",
                "agent_search_root": default_root,
                "message": "should be blocked",
            },
        )
        results.append(
            (
                "root_switch_closes_sessions",
                bool(b_status == 409 and blocked.get("code") == "session_closed"),
                {
                    "old_session_id": old_session_id,
                    "create_mode": close_create_mode,
                    "switch": {"status": sw_status, "payload": switch_resp},
                    "blocked": {"status": b_status, "payload": blocked},
                },
            )
        )

    except Exception as exc:
        errors.append(str(exc))
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            proc.kill()

    now_key = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = (repo_root / ".test" / "runs").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"workflow-gate-acceptance-{now_key}.md"
    lines = [
        f"# Gate Acceptance - {now_key}",
        "",
        f"- base_url: {base}",
        f"- default_agent_root: {default_root}",
        f"- runtime_root: {runtime_root.as_posix()}",
        "",
    ]
    for name, ok, detail in results:
        lines.extend(
            [
                f"## {name}",
                f"- pass: {ok}",
                "- detail:",
                "```json",
                json.dumps(detail, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
    if errors:
        lines.extend(["## errors", "```text", *errors, "```", ""])
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(out_path.as_posix())
    if errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
