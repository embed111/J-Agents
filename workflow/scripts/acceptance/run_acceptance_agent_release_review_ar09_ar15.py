#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REQ_GIF = ("AC-AR-10", "AC-AR-12", "AC-AR-14")


def call(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url=base_url + path, data=data, method=method, headers=headers)
    try:
        with urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, (json.loads(body) if body else {})
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload_obj = json.loads(body) if body else {}
        except Exception:
            payload_obj = {"raw": body}
        return exc.code, payload_obj


def wait_health(base_url: str, timeout_s: int = 60) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status, payload = call(base_url, "GET", "/healthz")
        if status == 200 and bool(payload.get("ok")):
            return
        time.sleep(0.5)
    raise RuntimeError("healthz timeout")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_sql(db_path: Path, sql: str, params: tuple[Any, ...], out_path: Path) -> None:
    conn = sqlite3.connect(db_path.as_posix())
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    write_json(out_path, [{"_row_index": i + 1, **{k: row[k] for k in row.keys()}} for i, row in enumerate(rows)])


def run_cmd(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    proc = subprocess.run(args, cwd=cwd.as_posix(), capture_output=True, text=True, encoding="utf-8", env=env)
    if proc.returncode != 0:
        raise RuntimeError("cmd failed: " + " ".join(args) + "\n" + str(proc.stdout) + "\n" + str(proc.stderr))


def release_note_text(
    version: str,
    *,
    capability_summary: str,
    knowledge_scope: str,
    skills: list[str],
    applicable_scenarios: str,
    version_notes: str,
) -> str:
    return "\n".join(
        [
            f"发布版本: {version}",
            f"角色能力摘要: {capability_summary}",
            f"角色知识范围: {knowledge_scope}",
            "技能: " + ", ".join(skills),
            f"适用场景: {applicable_scenarios}",
            f"版本说明: {version_notes}",
            "",
        ]
    )


def write_agent_workspace(
    root: Path,
    agent_name: str,
    *,
    persist_git_identity: bool,
    pre_release_note: str,
    fail_commit_hook: bool = False,
) -> Path:
    workspace = root / agent_name
    workspace.mkdir(parents=True, exist_ok=True)
    agents_md = "\n".join(
        [
            "# AGENT",
            "",
            "角色能力摘要: 我负责角色发布评审、发布执行校验与角色画像整理。",
            "角色知识范围: 我覆盖发布治理、Git 发布校验、角色画像快照绑定与验收证据组织。",
            "技能: release-governance, evidence-packaging",
            "适用场景: 角色发布评审；确认发布；发布失败兜底；角色详情展示来源绑定",
            "版本说明: 我当前维护发布评审流与角色画像展示口径。",
            "",
        ]
    )
    (workspace / "AGENTS.md").write_text(agents_md + "\n", encoding="utf-8")
    skill_dir = workspace / ".codex" / "skills" / "release-governance"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "\n".join(
            [
                "---",
                "name: release-governance",
                "description: Handle release review, publish evidence, and profile binding.",
                "---",
                "",
                "# Release Governance",
                "",
                "Keep release review evidence structured and traceable.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    run_cmd(["git", "init"], workspace)
    identity_env = os.environ.copy()
    if persist_git_identity:
        run_cmd(["git", "config", "user.email", f"{agent_name}@example.com"], workspace)
        run_cmd(["git", "config", "user.name", agent_name], workspace)
        cmd_env = None
    else:
        identity_env["GIT_AUTHOR_NAME"] = agent_name
        identity_env["GIT_AUTHOR_EMAIL"] = f"{agent_name}@example.com"
        identity_env["GIT_COMMITTER_NAME"] = agent_name
        identity_env["GIT_COMMITTER_EMAIL"] = f"{agent_name}@example.com"
        cmd_env = identity_env

    run_cmd(["git", "add", "AGENTS.md", ".codex/skills/release-governance/SKILL.md"], workspace, env=cmd_env)
    run_cmd(["git", "commit", "-m", "init"], workspace, env=cmd_env)
    note_v100 = release_note_text(
        "v1.0.0",
        capability_summary="我负责角色发布评审与正式版本维护。",
        knowledge_scope="我覆盖基础发布治理与角色能力说明。",
        skills=["release-governance", "evidence-packaging"],
        applicable_scenarios="正式发布基线维护；角色详情初始化",
        version_notes="首个正式发布基线。",
    )
    note_path = workspace / ".release-note-v1.0.0.md"
    note_path.write_text(note_v100, encoding="utf-8")
    run_cmd(["git", "tag", "-a", "v1.0.0", "-F", note_path.as_posix()], workspace, env=cmd_env)
    if fail_commit_hook:
        hook_path = workspace / ".git" / "hooks" / "pre-commit"
        hook_path.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    (workspace / "WIP.md").write_text(pre_release_note + "\n", encoding="utf-8")
    return workspace


def fixture_agents(workspace_root: Path) -> dict[str, Path]:
    (workspace_root / "workflow").mkdir(parents=True, exist_ok=True)
    (workspace_root / "workflow" / "README.md").write_text("fixture\n", encoding="utf-8")
    return {
        "success-agent": write_agent_workspace(workspace_root, "success-agent", persist_git_identity=True, pre_release_note="success agent pre-release change"),
        "reject-agent": write_agent_workspace(workspace_root, "reject-agent", persist_git_identity=True, pre_release_note="reject agent pre-release change"),
        "publish-fail-agent": write_agent_workspace(
            workspace_root,
            "publish-fail-agent",
            persist_git_identity=False,
            pre_release_note="publish fail agent pre-release change",
            fail_commit_hook=True,
        ),
        "report-fail-agent": write_agent_workspace(workspace_root, "report-fail-agent", persist_git_identity=True, pre_release_note="report fail agent pre-release change"),
    }


def find_agent(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    key = name.strip().lower()
    for row in items:
        if str(row.get("agent_name") or "").strip().lower() == key:
            return row
    raise RuntimeError(f"agent not found: {name}")


def find_browser() -> Path:
    candidates = [
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    raise RuntimeError("headless browser not found")


def edge_shot(browser_path: Path, url: str, shot_path: Path, width: int = 1440, height: int = 1500, budget_ms: int = 15000) -> None:
    shot_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={max(1000, int(budget_ms))}",
        f"--screenshot={shot_path.as_posix()}",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"browser screenshot failed: {proc.stderr}")


def edge_dom(browser_path: Path, url: str, width: int = 1440, height: int = 1500, budget_ms: int = 15000) -> str:
    cmd = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={max(1000, int(budget_ms))}",
        "--dump-dom",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if proc.returncode != 0:
        raise RuntimeError(f"browser dump-dom failed: {proc.stderr}")
    return proc.stdout


def parse_probe(dom_text: str) -> dict[str, Any]:
    if "trainingCenterProbeOutput" not in dom_text:
        raise RuntimeError("trainingCenterProbeOutput_not_found")
    start = dom_text.find("trainingCenterProbeOutput")
    pre_start = dom_text.rfind("<pre", 0, start)
    pre_end = dom_text.find("</pre>", start)
    if pre_start < 0 or pre_end < 0:
        raise RuntimeError("trainingCenterProbeOutput_not_found")
    pre_html = dom_text[pre_start:pre_end]
    tag_end = pre_html.find(">")
    if tag_end < 0:
        raise RuntimeError("trainingCenterProbeOutput_invalid")
    raw = html.unescape(pre_html[tag_end + 1 :]).strip()
    if not raw:
        raise RuntimeError("trainingCenterProbeOutput_empty")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("trainingCenterProbeOutput_not_dict")
    return payload


def ps_quote(text: str) -> str:
    return "'" + str(text or "").replace("'", "''") + "'"


def make_gif(gif_path: Path, frames: list[Path]) -> None:
    use_frames = [frame.resolve(strict=False) for frame in frames if frame and frame.exists()]
    if not use_frames:
        raise RuntimeError(f"gif frames missing: {gif_path.as_posix()}")
    frames_literal = ",".join([ps_quote(path.as_posix()) for path in use_frames])
    out_literal = ps_quote(gif_path.resolve(strict=False).as_posix())
    cmd = (
        "Add-Type -AssemblyName PresentationCore; "
        "$encoder = New-Object System.Windows.Media.Imaging.GifBitmapEncoder; "
        + f"foreach($f in @({frames_literal}))"
        + "{"
        + "$uri = New-Object System.Uri($f); "
        + "$frame = [System.Windows.Media.Imaging.BitmapFrame]::Create($uri); "
        + "$encoder.Frames.Add($frame);"
        + "}; "
        + f"$out={out_literal}; "
        + "$stream=[System.IO.File]::Open($out,[System.IO.FileMode]::Create); "
        + "try{$encoder.Save($stream)} finally {$stream.Close()}"
    )
    proc = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, encoding="utf-8", timeout=120)
    if proc.returncode != 0:
        raise RuntimeError("gif failed\n" + str(proc.stdout) + "\n" + str(proc.stderr))


def tc_probe_url(base_url: str, case_id: str, extra: dict[str, str] | None = None) -> str:
    query: dict[str, str] = {"tc_probe": "1", "tc_probe_case": str(case_id), "_ts": str(int(time.time() * 1000))}
    if extra:
        for key, value in extra.items():
            query[str(key)] = str(value)
    return base_url.rstrip("/") + "/?" + urlencode(query)


def capture_probe(
    browser_path: Path,
    base_url: str,
    evidence_root: Path,
    name: str,
    case_id: str,
    extra: dict[str, str] | None = None,
    *,
    budget_ms: int = 15000,
) -> tuple[str, str, dict[str, Any]]:
    url = tc_probe_url(base_url, case_id, extra)
    shot = evidence_root / "screenshots" / f"{name}.png"
    probe_file = evidence_root / "screenshots" / f"{name}.probe.json"
    edge_shot(browser_path, url, shot, budget_ms=budget_ms)
    probe = parse_probe(edge_dom(browser_path, url, budget_ms=budget_ms))
    write_json(probe_file, probe)
    return shot.as_posix(), probe_file.as_posix(), probe


def write_codex_stub(bin_dir: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script_path = bin_dir / "codex_stub.py"
    cmd_path = bin_dir / "codex.cmd"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "import re",
                "import sys",
                "import time",
                "prompt = sys.stdin.read()",
                "is_fallback = '角色发布失败兜底助手' in prompt",
                "def extract(label, default=''):",
                "    matched = re.search(r'^\\s*[-]?\\s*' + re.escape(label) + r'\\s*:\\s*(.+)$', prompt, flags=re.M)",
                "    if matched:",
                "        return matched.group(1).strip()",
                "    matched = re.search(r'\\\"' + re.escape(label) + r'\\\"\\s*:\\s*\\\"([^\\\"]+)\\\"', prompt)",
                "    if matched:",
                "        return matched.group(1).strip()",
                "    return default",
                "agent_name = extract('agent_name') or extract('agent_id')",
                "target_version = extract('target_version', 'v1.0.1')",
                "current_workspace_ref = extract('current_workspace_ref', 'workspace-ref')",
                "def emit(payload):",
                "    print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(payload, ensure_ascii=False)}}, ensure_ascii=False))",
                "if is_fallback:",
                "    emit({'failure_reason': '我识别到当前工作区缺少 Git 用户身份配置，导致提交或打标签失败。', 'retry_target_version': target_version, 'retry_release_notes': '', 'next_action_suggestion': '我建议先补齐 Git 用户身份后再重新确认发布。', 'warnings': []})",
                "    raise SystemExit(0)",
                "if agent_name == 'report-fail-agent':",
                "    raise SystemExit(2)",
                "if agent_name == 'success-agent':",
                "    time.sleep(2.5)",
                "summary_name = agent_name or 'release-agent'",
                "emit({'target_version': target_version, 'current_workspace_ref': current_workspace_ref, 'previous_release_version': 'v1.0.0', 'first_person_summary': f'我是 {summary_name}，我当前负责角色发布评审、功能差异梳理与正式版本画像绑定。', 'full_capability_inventory': ['我当前可以输出第一人称全量能力介绍并生成公开展示快照。', '我当前可以梳理相对上一正式版本的功能差异、风险与验证证据。', '我当前可以在正式发布成功后把报告绑定为角色详情页的展示来源。'], 'knowledge_scope': '我当前覆盖角色发布治理、Git 发布校验、角色画像绑定与验收证据组织。', 'agent_skills': ['release-governance', 'evidence-packaging'], 'applicable_scenarios': ['角色发布评审', '确认发布前差异审阅', '正式发布后的角色详情展示'], 'change_summary': '我本次相对上一正式版本补充了第一人称全量能力介绍输出，以及功能差异、风险与证据的结构化报告。', 'capability_delta': ['我本次新增了正式发布后可直接复用的第一人称全量能力介绍。', '我本次补充了相对上一正式版本的功能差异、风险和证据说明。'], 'risk_list': ['我当前识别到的风险是：如果 Git 用户身份未配置，确认发布会失败。'], 'validation_evidence': ['我当前已确认的验证证据是：结构化报告、stdout、stderr 和快照文件都已落盘。'], 'release_recommendation': 'approve', 'next_action_suggestion': '我建议进入人工审核，并在审核通过后执行确认发布。', 'warnings': []})",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cmd_path.write_text("@echo off\r\n" + f"\"{sys.executable}\" \"{script_path.as_posix()}\" %*\r\n", encoding="utf-8")


def wait_review_state(base_url: str, agent_id: str, expected: str, timeout_s: int = 20) -> tuple[int, dict[str, Any]]:
    deadline = time.time() + timeout_s
    last_status = 0
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        last_status, last_payload = call(base_url, "GET", f"/api/training/agents/{agent_id}/release-review")
        review = last_payload.get("review") if isinstance(last_payload, dict) else {}
        if last_status == 200 and str((review or {}).get("release_review_state") or "").strip().lower() == expected:
            return last_status, last_payload
        time.sleep(0.3)
    raise RuntimeError(f"wait review state timeout: {agent_id} -> {expected} last={last_status} {last_payload}")


def api_file(api_dir: Path, name: str, method: str, path: str, payload: dict[str, Any] | None, status: int, body: dict[str, Any]) -> str:
    out = api_dir / f"{name}.api.json"
    write_json(out, {"request": {"method": method, "path": path, "payload": payload}, "response": {"status": status, "body": body}})
    return out.as_posix()


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description="AC-AR-09~15 acceptance with UI evidence")
    parser.add_argument("--root", default=".", help="repo root")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8133)
    args = parser.parse_args()

    repo_root = Path(args.root).resolve()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    runtime_root = (repo_root / ".test" / "runtime" / "agent-release-review-ar09-ar15").resolve()
    evidence_root = (repo_root / ".output" / "evidence" / f"agent-release-review-ar09-ar15-{ts}").resolve()
    api_dir = evidence_root / "api"
    db_dir = evidence_root / "db"
    shots_dir = evidence_root / "screenshots"
    rec_dir = evidence_root / "recordings"
    for directory in [evidence_root, api_dir, db_dir, shots_dir, rec_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    if runtime_root.exists():
        shutil.rmtree(runtime_root, ignore_errors=True)
    runtime_root.mkdir(parents=True, exist_ok=True)

    workspace_root = runtime_root / "workspace-root"
    fixture_agents(workspace_root)
    db_path = runtime_root / "state" / "workflow.db"
    stub_bin = runtime_root / "bin"
    write_codex_stub(stub_bin)

    base_url = f"http://{args.host}:{args.port}"
    server_stdout = evidence_root / "server.stdout.log"
    server_stderr = evidence_root / "server.stderr.log"
    server_env = os.environ.copy()
    server_env["PATH"] = stub_bin.as_posix() + os.pathsep + server_env.get("PATH", "")
    server_env["WORKFLOW_RELEASE_REVIEW_CODEX_TIMEOUT_S"] = "30"
    proc = subprocess.Popen(
        [
            sys.executable,
            str((repo_root / "scripts" / "workflow_web_server.py").resolve()),
            "--root",
            runtime_root.as_posix(),
            "--entry-script",
            str((repo_root / "scripts" / "workflow_entry_cli.py").resolve()),
            "--host",
            args.host,
            "--port",
            str(args.port),
        ],
        cwd=repo_root.as_posix(),
        stdout=server_stdout.open("w", encoding="utf-8"),
        stderr=server_stderr.open("w", encoding="utf-8"),
        text=True,
        env=server_env,
    )

    ac: dict[str, dict[str, Any]] = {}
    ac_ev: dict[str, dict[str, list[str]]] = {}
    code_refs_common = [
        (repo_root / "src" / "workflow_app" / "server" / "services" / "release_management_service.py").resolve().as_posix(),
        (repo_root / "src" / "workflow_app" / "server" / "services" / "training_registry_service.py").resolve().as_posix(),
        (repo_root / "src" / "workflow_app" / "server" / "infra" / "db" / "migrations.py").resolve().as_posix(),
        (repo_root / "src" / "workflow_app" / "web_client" / "training_center_and_bootstrap.js").resolve().as_posix(),
        (repo_root / "scripts" / "acceptance" / "run_acceptance_agent_release_review_ar09_ar15.py").resolve().as_posix(),
    ]

    try:
        wait_health(base_url)
        browser = find_browser()

        setup_payload = {"agent_search_root": workspace_root.as_posix()}
        st_sw, body_sw = call(base_url, "POST", "/api/config/agent-search-root", setup_payload)
        api_file(api_dir, "setup_switch_root", "POST", "/api/config/agent-search-root", setup_payload, st_sw, body_sw)
        ensure(st_sw == 200 and bool(body_sw.get("ok")), f"switch root failed: {st_sw} {body_sw}")

        st_agents, body_agents = call(base_url, "GET", "/api/training/agents")
        api_agents = api_file(api_dir, "agents_initial", "GET", "/api/training/agents", None, st_agents, body_agents)
        ensure(st_agents == 200, f"list agents failed: {st_agents} {body_agents}")
        items = list(body_agents.get("items") or [])
        success_id = str(find_agent(items, "success-agent").get("agent_id") or "")
        reject_id = str(find_agent(items, "reject-agent").get("agent_id") or "")
        publish_fail_id = str(find_agent(items, "publish-fail-agent").get("agent_id") or "")
        report_fail_id = str(find_agent(items, "report-fail-agent").get("agent_id") or "")

        enter_results: dict[str, tuple[int, dict[str, Any]]] = {}

        def do_success_enter() -> None:
            enter_results["success"] = call(base_url, "POST", f"/api/training/agents/{success_id}/release-review/enter", {"operator": "ar-reviewer"})

        enter_thread = threading.Thread(target=do_success_enter, daemon=True)
        enter_thread.start()
        st09r, body09r = wait_review_state(base_url, success_id, "report_generating", timeout_s=10)
        api09_get = api_file(api_dir, "ac_ar_09_review_running", "GET", f"/api/training/agents/{success_id}/release-review", None, st09r, body09r)
        shot09, probe09, probe09_payload = capture_probe(
            browser,
            base_url,
            evidence_root,
            "ac_ar_09_enter_release_review",
            "ac_ar_rr_09",
            {"tc_probe_agent": "success-agent"},
            budget_ms=900,
        )
        enter_thread.join(timeout=40)
        ensure(not enter_thread.is_alive(), "success-agent enter thread timeout")
        st10_enter, body10_enter = enter_results["success"]
        api10_enter = api_file(api_dir, "ac_ar_10_enter_success_agent", "POST", f"/api/training/agents/{success_id}/release-review/enter", {"operator": "ar-reviewer"}, st10_enter, body10_enter)
        st10r, body10r = wait_review_state(base_url, success_id, "report_ready", timeout_s=10)
        api10_get = api_file(api_dir, "ac_ar_10_review_ready", "GET", f"/api/training/agents/{success_id}/release-review", None, st10r, body10r)
        dump_sql(db_path, "SELECT review_id,agent_id,target_version,current_workspace_ref,release_review_state,prompt_version,public_profile_markdown_path,capability_snapshot_json_path,report_error,created_at,updated_at FROM agent_release_review WHERE agent_id=? ORDER BY created_at DESC", (success_id,), db_dir / "ac_ar_10_success_review.db.json")
        shot10, probe10, probe10_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_10_report_ready", "ac_ar_rr_10", {"tc_probe_agent": "success-agent"})

        review10 = body10r.get("review", {}) if isinstance(body10r, dict) else {}
        report10 = review10.get("report", {}) if isinstance(review10, dict) else {}
        chain10 = review10.get("analysis_chain", {}) if isinstance(review10, dict) else {}
        ac["AC-AR-09"] = {"pass": bool(st09r == 200 and str(body09r.get("review", {}).get("release_review_state") or "") == "report_generating"), "api": [api09_get, api_agents]}
        ac_ev["AC-AR-09"] = {"screenshots": [shot09], "recordings": [], "api": [api09_get], "db_or_logs": [(db_dir / "ac_ar_10_success_review.db.json").as_posix(), probe09, server_stdout.as_posix(), server_stderr.as_posix()], "code": code_refs_common}
        ac["AC-AR-10"] = {"pass": bool(st10_enter == 200 and st10r == 200 and probe10_payload.get("pass") and str(review10.get("release_review_state") or "") == "report_ready" and str(report10.get("first_person_summary") or "").startswith("我") and bool(report10.get("full_capability_inventory")) and bool(report10.get("capability_delta")) and all(str(chain10.get(key) or "").strip() for key in ("prompt_path", "stdout_path", "stderr_path", "report_path"))), "api": [api10_enter, api10_get]}
        ac_ev["AC-AR-10"] = {"screenshots": [shot10], "recordings": [], "api": [api10_enter, api10_get], "db_or_logs": [probe10, str(chain10.get("prompt_path") or ""), str(chain10.get("stdout_path") or ""), str(chain10.get("stderr_path") or ""), str(chain10.get("report_path") or ""), str(review10.get("public_profile_markdown_path") or ""), str(review10.get("capability_snapshot_json_path") or "")], "code": code_refs_common}

        approve_payload = {"decision": "approve_publish", "reviewer": "release-owner", "review_comment": "我确认当前报告可以进入正式发布。", "operator": "release-owner"}
        st11a, body11a = call(base_url, "POST", f"/api/training/agents/{success_id}/release-review/manual", approve_payload)
        api11a = api_file(api_dir, "ac_ar_11_manual_approve_success", "POST", f"/api/training/agents/{success_id}/release-review/manual", approve_payload, st11a, body11a)
        st11r, body11r = wait_review_state(base_url, success_id, "review_approved", timeout_s=10)
        api11r = api_file(api_dir, "ac_ar_11_review_approved", "GET", f"/api/training/agents/{success_id}/release-review", None, st11r, body11r)
        shot11, probe11, probe11_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_11_review_approved", "ac_ar_rr_11", {"tc_probe_agent": "success-agent"})
        st11e, body11e = call(base_url, "POST", f"/api/training/agents/{reject_id}/release-review/enter", {"operator": "ar-reviewer"})
        api11e = api_file(api_dir, "ac_ar_11_enter_reject_agent", "POST", f"/api/training/agents/{reject_id}/release-review/enter", {"operator": "ar-reviewer"}, st11e, body11e)
        reject_payload = {"decision": "reject_continue_training", "reviewer": "release-owner", "review_comment": "我要求继续训练后再发版。", "operator": "release-owner"}
        st11b, body11b = call(base_url, "POST", f"/api/training/agents/{reject_id}/release-review/manual", reject_payload)
        api11b = api_file(api_dir, "ac_ar_11_manual_reject", "POST", f"/api/training/agents/{reject_id}/release-review/manual", reject_payload, st11b, body11b)
        st11c, body11c = wait_review_state(base_url, reject_id, "review_rejected", timeout_s=10)
        api11c = api_file(api_dir, "ac_ar_11_review_rejected", "GET", f"/api/training/agents/{reject_id}/release-review", None, st11c, body11c)
        dump_sql(db_path, "SELECT review_id,agent_id,release_review_state,review_decision,reviewer,review_comment,reviewed_at FROM agent_release_review WHERE agent_id IN (?,?) ORDER BY created_at DESC", (success_id, reject_id), db_dir / "ac_ar_11_manual_review.db.json")
        approved_review = body11r.get("review", {}) if isinstance(body11r, dict) else {}
        rejected_review = body11c.get("review", {}) if isinstance(body11c, dict) else {}
        ac["AC-AR-11"] = {"pass": bool(st11a == 200 and st11r == 200 and probe11_payload.get("pass") and str(approved_review.get("reviewer") or "").strip() == "release-owner" and str(approved_review.get("review_decision") or "").strip() == "approve_publish" and bool(str(approved_review.get("reviewed_at") or "").strip()) and st11e == 200 and st11b == 200 and str(rejected_review.get("release_review_state") or "").strip() == "review_rejected" and not bool(rejected_review.get("can_confirm"))), "api": [api11a, api11r, api11e, api11b, api11c]}
        ac_ev["AC-AR-11"] = {"screenshots": [shot11], "recordings": [], "api": [api11a, api11r, api11e, api11b, api11c], "db_or_logs": [(db_dir / "ac_ar_11_manual_review.db.json").as_posix(), probe11], "code": code_refs_common}

        st12c, body12c = call(base_url, "POST", f"/api/training/agents/{success_id}/release-review/confirm", {"operator": "release-owner"})
        api12c = api_file(api_dir, "ac_ar_12_confirm_publish_success", "POST", f"/api/training/agents/{success_id}/release-review/confirm", {"operator": "release-owner"}, st12c, body12c)
        st12a, body12a = call(base_url, "GET", "/api/training/agents")
        api12a = api_file(api_dir, "ac_ar_12_agents_after_publish", "GET", "/api/training/agents", None, st12a, body12a)
        st12r, body12r = call(base_url, "GET", f"/api/training/agents/{success_id}/releases?page=1&page_size=20")
        api12r = api_file(api_dir, "ac_ar_12_releases_after_publish", "GET", f"/api/training/agents/{success_id}/releases?page=1&page_size=20", None, st12r, body12r)
        shot12, probe12, probe12_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_12_publish_success_and_role_profile", "ac_ar_rr_12", {"tc_probe_agent": "success-agent"})
        dump_sql(db_path, "SELECT agent_id,current_version,latest_release_version,bound_release_version,lifecycle_state,training_gate_state,active_role_profile_release_id,active_role_profile_ref FROM agent_registry WHERE agent_id=?", (success_id,), db_dir / "ac_ar_12_agent_registry.db.json")
        dump_sql(db_path, "SELECT release_id,agent_id,version_label,classification,release_source_ref,public_profile_ref,capability_snapshot_ref FROM agent_release_history WHERE agent_id=? ORDER BY created_at DESC", (success_id,), db_dir / "ac_ar_12_release_history.db.json")
        success_after = find_agent(list(body12a.get("items") or []), "success-agent")
        releases12 = list(body12r.get("releases") or []) if isinstance(body12r, dict) else []
        latest_release12 = releases12[0] if releases12 else {}
        ac["AC-AR-12"] = {
            "pass": bool(
                st12c == 200
                and st12a == 200
                and st12r == 200
                and probe12_payload.get("pass")
                and str(success_after.get("lifecycle_state") or "").strip() == "released"
                and str(probe12_payload.get("role_profile_source") or "").strip() == "latest_release_report"
                and bool(str(success_after.get("active_role_profile_ref") or "").strip())
                and bool(str(latest_release12.get("public_profile_ref") or "").strip())
            ),
            "api": [api12c, api12a, api12r],
        }
        ac_ev["AC-AR-12"] = {"screenshots": [shot12], "recordings": [], "api": [api12c, api12a, api12r], "db_or_logs": [probe12, (db_dir / "ac_ar_12_agent_registry.db.json").as_posix(), (db_dir / "ac_ar_12_release_history.db.json").as_posix()], "code": code_refs_common}

        st14e, body14e = call(base_url, "POST", f"/api/training/agents/{publish_fail_id}/release-review/enter", {"operator": "ar-reviewer"})
        api14e = api_file(api_dir, "ac_ar_14_enter_publish_fail", "POST", f"/api/training/agents/{publish_fail_id}/release-review/enter", {"operator": "ar-reviewer"}, st14e, body14e)
        st14m, body14m = call(base_url, "POST", f"/api/training/agents/{publish_fail_id}/release-review/manual", approve_payload)
        api14m = api_file(api_dir, "ac_ar_14_manual_approve_publish_fail", "POST", f"/api/training/agents/{publish_fail_id}/release-review/manual", approve_payload, st14m, body14m)
        shot14_pre, probe14_pre, _ = capture_probe(browser, base_url, evidence_root, "ac_ar_14_before_confirm_publish_fail", "ac_ar_rr_11", {"tc_probe_agent": "publish-fail-agent"})
        st14c, body14c = call(base_url, "POST", f"/api/training/agents/{publish_fail_id}/release-review/confirm", {"operator": "release-owner"})
        api14c = api_file(api_dir, "ac_ar_14_confirm_publish_fail", "POST", f"/api/training/agents/{publish_fail_id}/release-review/confirm", {"operator": "release-owner"}, st14c, body14c)
        st14r, body14r = wait_review_state(base_url, publish_fail_id, "publish_failed", timeout_s=15)
        api14r = api_file(api_dir, "ac_ar_14_review_publish_failed", "GET", f"/api/training/agents/{publish_fail_id}/release-review", None, st14r, body14r)
        shot14, probe14, probe14_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_14_publish_failed_with_fallback", "ac_ar_rr_14", {"tc_probe_agent": "publish-fail-agent"})
        dump_sql(db_path, "SELECT review_id,agent_id,release_review_state,publish_status,publish_error,execution_log_json,fallback_json FROM agent_release_review WHERE agent_id=? ORDER BY created_at DESC", (publish_fail_id,), db_dir / "ac_ar_14_publish_failed_review.db.json")
        fail_review = body14r.get("review", {}) if isinstance(body14r, dict) else {}
        fail_logs = fail_review.get("execution_logs") if isinstance(fail_review, dict) else []
        fail_phases = {str(item.get("phase") or "").strip() for item in fail_logs if isinstance(item, dict)}
        fallback_payload = fail_review.get("fallback") if isinstance(fail_review, dict) else {}
        ac["AC-AR-14"] = {"pass": bool(st14e == 200 and st14m == 200 and st14c == 200 and st14r == 200 and probe14_payload.get("pass") and str(fail_review.get("publish_status") or "").strip() == "failed" and str(fail_review.get("release_review_state") or "").strip() == "publish_failed" and "fallback_trigger" in fail_phases and "fallback_result" in fail_phases and bool(str((fallback_payload or {}).get("failure_reason") or "").strip()) and isinstance((fallback_payload or {}).get("retry_result"), dict)), "api": [api14e, api14m, api14c, api14r]}
        ac_ev["AC-AR-14"] = {"screenshots": [shot14], "recordings": [], "api": [api14e, api14m, api14c, api14r], "db_or_logs": [(db_dir / "ac_ar_14_publish_failed_review.db.json").as_posix(), probe14_pre, probe14], "code": code_refs_common}

        st13r, body13r = call(base_url, "GET", f"/api/training/agents/{publish_fail_id}/release-review")
        api13r = api_file(api_dir, "ac_ar_13_review_logs", "GET", f"/api/training/agents/{publish_fail_id}/release-review", None, st13r, body13r)
        shot13, probe13, probe13_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_13_publish_logs", "ac_ar_rr_13", {"tc_probe_agent": "success-agent"})
        success_logs = (body12c.get("review") or {}).get("execution_logs") if isinstance(body12c, dict) else []
        success_phases = {str(item.get("phase") or "").strip() for item in success_logs if isinstance(item, dict)}
        failure_logs = (body13r.get("review") or {}).get("execution_logs") if isinstance(body13r, dict) else []
        failure_phases = {str(item.get("phase") or "").strip() for item in failure_logs if isinstance(item, dict)}
        ac["AC-AR-13"] = {"pass": bool(st13r == 200 and probe13_payload.get("pass") and {"prepare", "git_execute", "release_note", "verify"} <= success_phases and {"fallback_trigger", "fallback_result"} <= failure_phases), "api": [api13r, api12c]}
        ac_ev["AC-AR-13"] = {"screenshots": [shot13], "recordings": [], "api": [api13r, api12c], "db_or_logs": [probe13, (db_dir / "ac_ar_14_publish_failed_review.db.json").as_posix()], "code": code_refs_common}

        st15e, body15e = call(base_url, "POST", f"/api/training/agents/{report_fail_id}/release-review/enter", {"operator": "ar-reviewer"})
        api15e = api_file(api_dir, "ac_ar_15_enter_report_fail", "POST", f"/api/training/agents/{report_fail_id}/release-review/enter", {"operator": "ar-reviewer"}, st15e, body15e)
        st15r, body15r = wait_review_state(base_url, report_fail_id, "report_failed", timeout_s=10)
        api15r = api_file(api_dir, "ac_ar_15_review_report_failed", "GET", f"/api/training/agents/{report_fail_id}/release-review", None, st15r, body15r)
        shot15, probe15, probe15_payload = capture_probe(browser, base_url, evidence_root, "ac_ar_15_report_failed_blocked", "ac_ar_rr_15", {"tc_probe_agent": "report-fail-agent"})
        dump_sql(db_path, "SELECT review_id,agent_id,release_review_state,report_error,analysis_chain_json FROM agent_release_review WHERE agent_id=? ORDER BY created_at DESC", (report_fail_id,), db_dir / "ac_ar_15_report_failed_review.db.json")
        report_fail_review = body15r.get("review", {}) if isinstance(body15r, dict) else {}
        ac["AC-AR-15"] = {"pass": bool(st15e == 200 and st15r == 200 and probe15_payload.get("pass") and str(report_fail_review.get("release_review_state") or "").strip() == "report_failed" and "重新进入发布评审" in str(report_fail_review.get("report_error") or "") and not bool(report_fail_review.get("can_confirm"))), "api": [api15e, api15r]}
        ac_ev["AC-AR-15"] = {"screenshots": [shot15], "recordings": [], "api": [api15e, api15r], "db_or_logs": [(db_dir / "ac_ar_15_report_failed_review.db.json").as_posix(), probe15], "code": code_refs_common}

        gif10 = rec_dir / "ac_ar_10_release_review.gif"
        gif12 = rec_dir / "ac_ar_12_confirm_publish.gif"
        gif14 = rec_dir / "ac_ar_14_publish_failed_fallback.gif"
        make_gif(gif10, [Path(shot09), Path(shot10)])
        make_gif(gif12, [Path(shot10), Path(shot11), Path(shot12)])
        make_gif(gif14, [Path(shot14_pre), Path(shot14)])
        ac_ev["AC-AR-10"]["recordings"] = [gif10.as_posix()]
        ac_ev["AC-AR-12"]["recordings"] = [gif12.as_posix()]
        ac_ev["AC-AR-14"]["recordings"] = [gif14.as_posix()]

        manifest = evidence_root / "ac_ar_09_15_evidence_manifest.json"
        write_json(manifest, ac_ev)
        summary_md = evidence_root / "ac_ar_09_15_summary.md"
        summary_lines = [
            f"# AC-AR-09~15 Acceptance Summary ({ts})",
            "",
            f"- runtime_root: {runtime_root.as_posix()}",
            f"- workspace_root: {workspace_root.as_posix()}",
            f"- db_path: {db_path.as_posix()}",
            f"- server_stdout: {server_stdout.as_posix()}",
            f"- server_stderr: {server_stderr.as_posix()}",
            f"- screenshots_dir: {shots_dir.as_posix()}",
            f"- recordings_dir: {rec_dir.as_posix()}",
            f"- api_dir: {api_dir.as_posix()}",
            f"- db_dir: {db_dir.as_posix()}",
            f"- evidence_manifest: {manifest.as_posix()}",
            "",
            "| AC | pass | evidence |",
            "|---|---|---|",
        ]
        for ac_id in [f"AC-AR-{i:02d}" for i in range(9, 16)]:
            row = ac.get(ac_id, {"pass": False})
            evidence = ac_ev.get(ac_id, {})
            refs: list[str] = []
            if evidence.get("screenshots"):
                refs.append("screenshot=" + "<br>".join(evidence["screenshots"]))
            if evidence.get("recordings"):
                refs.append("recording=" + "<br>".join(evidence["recordings"]))
            if evidence.get("api"):
                refs.append("api=" + "<br>".join(evidence["api"]))
            if evidence.get("db_or_logs"):
                refs.append("db/log=" + "<br>".join([item for item in evidence["db_or_logs"] if item]))
            if evidence.get("code"):
                refs.append("code=" + "<br>".join(evidence["code"]))
            summary_lines.append(f"| {ac_id} | {'pass' if row.get('pass') else 'fail'} | {'<br><br>'.join(refs)} |")
        summary_md.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
        write_json(evidence_root / "ac_ar_09_15_summary.json", ac)
        print(summary_md.as_posix())
        return 0 if all(bool(ac.get(f"AC-AR-{i:02d}", {}).get("pass")) for i in range(9, 16)) else 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
