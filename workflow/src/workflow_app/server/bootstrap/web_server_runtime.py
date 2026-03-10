#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ...runtime.agent_runtime import AgentConfigError, AgentRuntimeError, chat_once, stream_chat
from ...entry.workflow_entry_cli import (
    append_decision_markdown as append_decision_log,
    create_training_id,
    decision_to_status,
    run_trainer_once,
)
from ...history.workflow_history_admin import (
    cleanup_history as admin_cleanup_history,
    delete_session_history,
    delete_training_content,
)
from ...runtime.training_center_runtime import (
    TrainingCenterError,
    bind_runtime as bind_training_center_runtime,
    clone_training_agent_from_current,
    confirm_training_agent_release_review,
    create_training_plan_and_enqueue,
    discard_agent_pre_release,
    discard_training_agent_release_review,
    dispatch_next_training_queue_item,
    discover_training_trainers,
    enter_training_agent_release_review,
    get_training_agent_release_review,
    execute_training_queue_item,
    get_training_run_detail,
    list_training_agent_releases,
    list_training_agents_overview,
    list_training_queue_items,
    remove_training_queue_item,
    set_training_agent_avatar,
    submit_manual_release_evaluation,
    submit_training_agent_release_review_manual,
    switch_training_agent_release,
)

from ..presentation.pages import load_index_page_css, load_index_page_html

DEFAULT_WORKFLOW_FOCUS = "Workflow web workbench and runtime orchestration"
AB_STATE_FILE = "state/ab-slots.json"
RUNTIME_CONFIG_FILE = "state/runtime-config.json"
DEFAULT_AGENTS_ROOT = Path(os.getenv("WORKFLOW_AGENTS_ROOT") or "C:/work/agents")
AGENT_SEARCH_ROOT_NOT_SET_CODE = "agent_search_root_not_set"
WORKFLOW_APP_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PROJECT_ROOT = Path(__file__).resolve().parents[4]
TRAINER_SOURCE_ROOT = (WORKFLOW_PROJECT_ROOT.parent / "trainer").resolve(strict=False)
TRAINING_PRIORITY_LEVELS = ("P0", "P1", "P2", "P3")
TRAINING_PRIORITY_RANK = {name: idx for idx, name in enumerate(TRAINING_PRIORITY_LEVELS)}
MAX_GENERATION_CONCURRENCY = 5
CHAT_INGRESS_ROUTES = ("/api/chat", "/api/chat/stream", "/api/tasks/execute")
AB_FEATURE_ENABLED = str(os.getenv("WORKFLOW_AB_ENABLED") or "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def env_int(name: str, default: int) -> int:
    raw = str(os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


TEST_DATA_AUTO_CLEANUP_ENABLED = str(
    os.getenv("WORKFLOW_TESTDATA_AUTO_CLEANUP") or "1"
).strip().lower() in {"1", "true", "yes", "on"}
TEST_DATA_CLEANUP_INTERVAL_S = max(
    3600,
    env_int("WORKFLOW_TESTDATA_CLEANUP_INTERVAL_S", 86400),
)
TEST_DATA_MAX_AGE_HOURS = max(
    1,
    env_int("WORKFLOW_TESTDATA_MAX_AGE_HOURS", 168),
)
ALLOW_MANUAL_POLICY_INPUT_DEFAULT = str(
    os.getenv("WORKFLOW_ALLOW_MANUAL_POLICY_INPUT") or "1"
).strip().lower() in {"1", "true", "yes", "on"}


HTML_PAGE = load_index_page_html()
CSS_PAGE = load_index_page_css()



@dataclass
class AppConfig:
    root: Path
    entry_script: Path
    agent_search_root: Path | None
    show_test_data: bool
    host: str
    port: int
    focus: str
    reconcile_interval_s: int
    allow_manual_policy_input: bool


@dataclass
class RuntimeState:
    stream_lock: threading.Lock = field(default_factory=threading.Lock)
    active_streams: dict[str, threading.Event] = field(default_factory=dict)
    reconcile_lock: threading.Lock = field(default_factory=threading.Lock)
    session_lock_guard: threading.Lock = field(default_factory=threading.Lock)
    session_locks: dict[str, threading.Lock] = field(default_factory=dict)
    task_runtime_lock: threading.Lock = field(default_factory=threading.Lock)
    active_tasks: dict[str, "TaskRuntime"] = field(default_factory=dict)
    generation_semaphore: threading.Semaphore = field(
        default_factory=lambda: threading.Semaphore(MAX_GENERATION_CONCURRENCY)
    )
    config_lock: threading.Lock = field(default_factory=threading.Lock)
    workflow_lock: threading.Lock = field(default_factory=threading.Lock)
    analyzing_workflows: set[str] = field(default_factory=set)
    stop_event: threading.Event = field(default_factory=threading.Event)


@dataclass
class TaskRuntime:
    task_id: str
    session_id: str
    agent_name: str
    process: subprocess.Popen[str] | None = None
    interrupted: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)


class SessionGateError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        code: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.extra = dict(extra or {})


class ConcurrencyLimitError(RuntimeError):
    pass


class WorkflowGateError(RuntimeError):
    def __init__(
        self,
        status_code: int,
        message: str,
        code: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.extra = dict(extra or {})


ANALYSIS_STATE_PENDING = "未分析"
ANALYSIS_STATE_DONE = "已分析"
AGENT_POLICY_ERROR_CODE = "agent_policy_extract_failed"
AGENT_POLICY_CONFIRM_CODE = "agent_policy_confirmation_required"
AGENT_POLICY_CLARITY_BLOCKED_CODE = "agent_policy_clarity_blocked"
AGENT_POLICY_REANALYZE_REQUIRED_CODE = "agent_policy_reanalyze_required"
AGENT_POLICY_OUT_OF_SCOPE_CODE = "target_agents_path_out_of_scope"
MANUAL_POLICY_INPUT_DISABLED_CODE = "manual_policy_input_disabled"
MANUAL_POLICY_INPUT_NOT_ALLOWED_CODE = "manual_policy_input_not_allowed"
POLICY_ALIGNMENT_ALIGNED = "aligned"
POLICY_ALIGNMENT_DEVIATED = "deviated"
POLICY_CLARITY_AUTO_THRESHOLD = 80
POLICY_CLARITY_CONFIRM_THRESHOLD = 60
POLICY_SCORE_MODEL = "v2"
POLICY_EXTRACT_SOURCE = "codex_exec"
POLICY_PROMPT_VERSION = "2026-03-01-codex-exec-v2-evidence"
POLICY_CODEX_TIMEOUT_S = max(
    30,
    env_int("WORKFLOW_POLICY_CODEX_TIMEOUT_S", 180),
)
POLICY_TRACE_DIR = Path(".runtime") / "policy-extract"
POLICY_SCORE_WEIGHTS: dict[str, float] = {
    "completeness": 0.2,
    "executability": 0.2,
    "consistency": 0.2,
    "traceability": 0.15,
    "risk_coverage": 0.15,
    "operability": 0.1,
}
POLICY_SCORE_DIMENSION_META: tuple[tuple[str, str], ...] = (
    ("completeness", "完整性"),
    ("executability", "可执行边界"),
    ("consistency", "一致性"),
    ("traceability", "可追溯性"),
    ("risk_coverage", "风险覆盖度"),
    ("operability", "可操作性"),
)


_WIN_ABS_PATH_PATTERN = re.compile(r"(?i)\b[A-Z]:[\\/][^\s\"'`]+")
_ROOT_ALIAS_PATH_PATTERN = re.compile(r"(?i)\$root(?:[\\/][^\s\"'`]+)?")


def now_local() -> datetime:
    return datetime.now().astimezone()


def iso_ts(ts: datetime) -> str:
    return ts.isoformat(timespec="seconds")


def date_key(ts: datetime) -> str:
    return ts.strftime("%Y%m%d")


def web_asset_path(name: str) -> Path:
    return WORKFLOW_APP_ROOT / name


def web_client_parts_dir() -> Path:
    return WORKFLOW_APP_ROOT / "web_client"


def web_client_bundle_manifest_path() -> Path:
    return web_client_parts_dir() / "bundle_manifest.json"


def load_web_client_bundle_manifest() -> list[str]:
    manifest_path = web_client_bundle_manifest_path()
    if not manifest_path.exists():
        raise FileNotFoundError("web client bundle manifest missing")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"invalid web client bundle manifest: {exc}") from exc
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("web client bundle manifest must be a non-empty array")
    names: list[str] = []
    seen: set[str] = set()
    for raw in payload:
        name = str(raw or "").strip()
        if not name:
            continue
        if "/" in name or "\\" in name:
            raise RuntimeError(f"invalid manifest item path: {name}")
        if not name.lower().endswith(".js"):
            raise RuntimeError(f"manifest item must be .js: {name}")
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    if not names:
        raise RuntimeError("web client bundle manifest has no valid js entries")
    return names


def load_web_client_asset_text() -> str:
    parts_root = web_client_parts_dir()
    if parts_root.exists() and parts_root.is_dir():
        try:
            manifest_names = load_web_client_bundle_manifest()
            chunks: list[str] = []
            for name in manifest_names:
                part = parts_root / name
                if not part.exists() or not part.is_file():
                    raise FileNotFoundError(f"web client manifest part missing: {name}")
                chunks.append(part.read_text(encoding="utf-8"))
            return "\n".join(chunks)
        except FileNotFoundError:
            pass
    asset = web_asset_path("workflow_web_client.js")
    if not asset.exists():
        raise FileNotFoundError("workflow web client asset missing")
    return asset.read_text(encoding="utf-8")


def relative_to_root(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def runtime_config_file(root: Path) -> Path:
    return root / RUNTIME_CONFIG_FILE


def load_runtime_config(root: Path) -> dict[str, Any]:
    path = runtime_config_file(root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_runtime_config(root: Path, patch: dict[str, Any]) -> None:
    if not patch:
        return
    path = runtime_config_file(root)
    current = load_runtime_config(root)
    current.update(patch)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def safe_token(value: str, default: str, max_len: int) -> str:
    text = (value or "").strip()
    if not text:
        text = default
    text = text[:max_len]
    return re.sub(r"[^0-9A-Za-z._:-]", "-", text)


def parse_bool_flag(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    text = str(value).strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def parse_query_bool(query: dict[str, list[str]], key: str, default: bool = False) -> bool:
    values = query.get(key) or []
    if not values:
        return default
    return parse_bool_flag(values[0], default=default)


def new_session_id() -> str:
    return f"sess-web-{now_local().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"


def normalize_abs_path(raw: str, *, base: Path) -> Path:
    text = str(raw or "").strip()
    if not text:
        raise ValueError("empty path")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    return candidate.resolve(strict=False)


def path_in_scope(path: Path, scope: Path) -> bool:
    try:
        path.relative_to(scope)
        return True
    except ValueError:
        return False


def validate_workspace_root_semantics(workspace_root: Path) -> tuple[bool, str]:
    root = workspace_root.resolve(strict=False)
    if not root.exists() or not root.is_dir():
        return False, "workspace_root_not_directory"
    workflow_dir = root / "workflow"
    if not workflow_dir.exists() or not workflow_dir.is_dir():
        return False, "workspace_root_missing_workflow_subdir"
    return True, ""


def agent_search_root_state(agent_search_root: Path | None) -> tuple[bool, str]:
    if agent_search_root is None:
        return False, AGENT_SEARCH_ROOT_NOT_SET_CODE
    ok, code = validate_workspace_root_semantics(agent_search_root)
    if not ok:
        return False, code or "workspace_root_invalid"
    return True, ""


def agent_search_root_text(agent_search_root: Path | None) -> str:
    if isinstance(agent_search_root, Path):
        return agent_search_root.as_posix()
    return ""


def agent_search_root_block_message(error_code: str) -> str:
    code = str(error_code or "").strip().lower()
    if code == AGENT_SEARCH_ROOT_NOT_SET_CODE:
        return "agent_search_root 未设置，请先在设置页配置有效路径。"
    return f"agent_search_root 无效，请先在设置页修正路径（{code}）。"


def policy_extract_trace_root(root: Path) -> Path:
    return root / POLICY_TRACE_DIR


def clean_target_token(raw: str) -> str:
    return str(raw or "").strip().strip("\"'").rstrip(".,;")


def resolve_root_alias(raw: str, scope: Path) -> str:
    text = clean_target_token(raw)
    if not text:
        return text
    low = text.lower()
    if not low.startswith("$root"):
        return text
    suffix = text[5:]
    if suffix and suffix[0] not in ("/", "\\"):
        return text
    relative = suffix[1:] if suffix else ""
    if not relative:
        return scope.as_posix()
    return (scope / Path(relative)).resolve(strict=False).as_posix()


def collect_write_targets(message: str, explicit_targets: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for raw in explicit_targets:
        text = clean_target_token(raw)
        if not text or text in seen:
            continue
        values.append(text)
        seen.add(text)
    for match in _WIN_ABS_PATH_PATTERN.findall(message or ""):
        text = clean_target_token(str(match))
        if not text or text in seen:
            continue
        values.append(text)
        seen.add(text)
    for match in _ROOT_ALIAS_PATH_PATTERN.findall(message or ""):
        text = clean_target_token(str(match))
        if not text or text in seen:
            continue
        values.append(text)
        seen.add(text)
    return values


def normalize_write_targets(scope: Path, values: list[str]) -> list[str]:
    out: list[str] = []
    seen_norm: set[str] = set()
    for raw in values:
        resolved = resolve_root_alias(raw, scope)
        path = normalize_abs_path(resolved, base=scope)
        if not path_in_scope(path, scope):
            raise SessionGateError(400, f"path out of root: {raw}", "path_out_of_root")
        norm = path.as_posix()
        if norm in seen_norm:
            continue
        seen_norm.add(norm)
        out.append(norm)
    return out


def connect_db(root: Path) -> sqlite3.Connection:
    from ..infra.db.connection import connect_db as _connect_db

    return _connect_db(root)


def ensure_dirs(root: Path) -> None:
    for rel in [
        "logs/events",
        "logs/decisions",
        "logs/runs",
        "logs/summaries",
        "metrics",
        "state",
        "state/slots",
        "docs/workflow",
    ]:
        (root / rel).mkdir(parents=True, exist_ok=True)


def ensure_tables(root: Path) -> None:
    from ..infra.db.migrations import ensure_tables as _ensure_tables

    _ensure_tables(
        root,
        analysis_state_pending=ANALYSIS_STATE_PENDING,
        default_agents_root=DEFAULT_AGENTS_ROOT.resolve(strict=False).as_posix(),
    )


def ensure_metric_files(root: Path) -> None:
    cli = root / "metrics" / "cli-baseline-latency.json"
    wf = root / "metrics" / "workflow-latency-daily.json"
    if not cli.exists():
        cli.write_text(
            json.dumps(
                {
                    "date": now_local().strftime("%Y-%m-%d"),
                    "status": "blocked",
                    "reason": "baseline not measured yet or real agent not configured",
                    "samples": [],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    if not wf.exists():
        wf.write_text(
            json.dumps(
                {
                    "date": now_local().strftime("%Y-%m-%d"),
                    "status": "running",
                    "samples": [],
                    "p95_first_token_ms": None,
                    "p95_total_ms": None,
                    "updated_at": iso_ts(now_local()),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    vals = sorted(values)
    idx = max(0, min(len(vals) - 1, int(round((len(vals) - 1) * p))))
    return vals[idx]


def append_workflow_latency(root: Path, sample: dict[str, Any]) -> None:
    path = root / "metrics" / "workflow-latency-daily.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    if not data:
        data = {
            "date": now_local().strftime("%Y-%m-%d"),
            "status": "running",
            "samples": [],
        }
    samples = data.get("samples")
    if not isinstance(samples, list):
        samples = []
    samples.append(sample)
    samples = samples[-500:]
    data["samples"] = samples
    ft = [int(s["first_token_ms"]) for s in samples if s.get("first_token_ms") is not None]
    tt = [int(s["total_ms"]) for s in samples if s.get("total_ms") is not None]
    data["p95_first_token_ms"] = percentile(ft, 0.95)
    data["p95_total_ms"] = percentile(tt, 0.95)
    data["updated_at"] = iso_ts(now_local())
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def event_id() -> str:
    ts = now_local()
    return f"evt-{date_key(ts)}-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"


def task_id() -> str:
    ts = now_local()
    return f"REQ-{date_key(ts)}-{uuid.uuid4().hex[:6]}"


def analysis_run_id() -> str:
    ts = now_local()
    return f"ar-{date_key(ts)}-{ts.strftime('%H%M%S')}-{uuid.uuid4().hex[:6]}"


def event_file(root: Path) -> Path:
    return root / "logs" / "events" / f"events-{date_key(now_local())}.jsonl"


def unique_run_file(root: Path, prefix: str) -> Path:
    ts = now_local()
    return root / "logs" / "runs" / f"{prefix}-{date_key(ts)}-{ts.strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}.md"


def persist_event(root: Path, event: dict[str, Any]) -> None:
    conn = connect_db(root)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO conversation_events (event_id,timestamp,session_id,actor,stage,action,status,latency_ms,task_id,reason_tags_json,ref) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
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
        conn.commit()
    finally:
        conn.close()
    with event_file(root).open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


_AGENT_DUTY_KEYWORDS = (
    "职责边界",
    "核心职责",
    "职责",
    "角色定位",
    "角色",
    "目标",
)

_AGENT_ROLE_HEADINGS = ("角色定位", "角色身份", "角色")
_AGENT_GOAL_HEADINGS = ("会话目标", "任务目标", "目标", "使命", "mission")
_AGENT_DUTY_HEADINGS = ("职责边界", "核心职责", "关键约束", "决策边界", "职责范围", "职责")
_AGENT_LIMIT_HEADINGS = ("限制内容", "约束", "limits", "constraints")
_AGENT_MUST_HEADINGS = ("必须", "must", "硬性要求", "required")
_AGENT_MUST_NOT_HEADINGS = ("不得", "禁止", "mustnot", "must_not", "prohibited")
_AGENT_PRECONDITION_HEADINGS = ("前置条件", "前提", "先决条件", "precondition", "preconditions")
_CONSTRAINT_MUST_TERMS = ("必须", "应当", "务必", "must", "required")
_CONSTRAINT_MUST_NOT_TERMS = (
    "不得",
    "禁止",
    "不可",
    "不能",
    "严禁",
    "must not",
    "must_not",
    "mustnot",
    "prohibited",
)
_CONSTRAINT_PRECONDITION_TERMS = ("前置", "前提", "先决", "需先", "precondition", "prerequisite", "before")


# Policy contract parsing/clarity logic is extracted to services/policy_contract_runtime.py.


def discover_agents(
    agents_root: Path,
    *,
    cache_root: Path | None = None,
    analyze_policy: bool = True,
    target_agent_name: str = "",
) -> list[dict[str, Any]]:
    from ..services.policy_analysis import discover_agents as _discover_agents

    return _discover_agents(
        agents_root,
        cache_root=cache_root,
        analyze_policy=analyze_policy,
        target_agent_name=target_agent_name,
    )


def current_agent_search_root(cfg: AppConfig, state: RuntimeState) -> Path | None:
    with state.config_lock:
        return cfg.agent_search_root


def current_agent_search_root_text(cfg: AppConfig, state: RuntimeState) -> str:
    return agent_search_root_text(current_agent_search_root(cfg, state))


def current_agent_search_root_status(cfg: AppConfig, state: RuntimeState) -> tuple[Path | None, bool, str]:
    root = current_agent_search_root(cfg, state)
    ready, error_code = agent_search_root_state(root)
    return root, ready, error_code


def current_allow_manual_policy_input(cfg: AppConfig, state: RuntimeState) -> bool:
    with state.config_lock:
        return bool(cfg.allow_manual_policy_input)


def current_show_test_data(cfg: AppConfig, state: RuntimeState) -> bool:
    with state.config_lock:
        return bool(cfg.show_test_data)


def set_show_test_data(
    cfg: AppConfig,
    state: RuntimeState,
    value: bool,
) -> tuple[bool, bool]:
    new_value = bool(value)
    with state.config_lock:
        old_value = bool(cfg.show_test_data)
        try:
            save_runtime_config(cfg.root, {"show_test_data": bool(new_value)})
        except Exception as exc:
            raise SessionGateError(
                500,
                f"show_test_data save failed: {exc}",
                "show_test_data_save_failed",
            ) from exc
        cfg.show_test_data = new_value
    return old_value, new_value


def resolve_include_test_data(
    query: dict[str, list[str]],
    cfg: AppConfig,
    state: RuntimeState,
) -> bool:
    default_value = current_show_test_data(cfg, state)
    values = list(query.get("include_test_data") or query.get("includeTestData") or [])
    if not values:
        return bool(default_value)
    return parse_bool_flag(values[0], default=default_value)


def set_agent_search_root(
    cfg: AppConfig,
    state: RuntimeState,
    value: Path,
) -> tuple[Path | None, Path]:
    new_root = value.resolve(strict=False)
    with state.config_lock:
        old_root = cfg.agent_search_root
        save_runtime_config(cfg.root, {"agent_search_root": new_root.as_posix()})
        cfg.agent_search_root = new_root
    return old_root, new_root


def set_allow_manual_policy_input(
    cfg: AppConfig,
    state: RuntimeState,
    value: bool,
) -> tuple[bool, bool]:
    new_value = bool(value)
    with state.config_lock:
        old_value = bool(cfg.allow_manual_policy_input)
        cfg.allow_manual_policy_input = new_value
    return old_value, new_value


def list_available_agents(
    cfg: AppConfig,
    *,
    analyze_policy: bool = False,
    target_agent_name: str = "",
) -> list[dict[str, Any]]:
    if cfg.agent_search_root is None:
        return []
    return discover_agents(
        cfg.agent_search_root,
        cache_root=cfg.root,
        analyze_policy=analyze_policy,
        target_agent_name=target_agent_name,
    )


def load_agent_with_policy(cfg: AppConfig, agent_name: str) -> dict[str, Any] | None:
    name = safe_token(str(agent_name or ""), "", 80)
    if not name:
        return None
    items = list_available_agents(
        cfg,
        analyze_policy=True,
        target_agent_name=name,
    )
    if not items:
        return None
    for item in items:
        if str(item.get("agent_name") or "") == name:
            return item
    return items[0]



_TRAINING_CENTER_RUNTIME_BOUND = False


def bind_training_center_runtime_once() -> None:
    global _TRAINING_CENTER_RUNTIME_BOUND
    if _TRAINING_CENTER_RUNTIME_BOUND:
        return
    bind_training_center_runtime(
        {
            "connect_db": connect_db,
            "safe_token": safe_token,
            "now_local": now_local,
            "iso_ts": iso_ts,
            "date_key": date_key,
            "path_in_scope": path_in_scope,
            "extract_agent_policy_fields": extract_agent_policy_fields,
            "relative_to_root": relative_to_root,
            "event_file": event_file,
            "persist_event": persist_event,
            "event_id": event_id,
            "list_available_agents": list_available_agents,
            "TRAINER_SOURCE_ROOT": TRAINER_SOURCE_ROOT,
            "TRAINING_PRIORITY_LEVELS": TRAINING_PRIORITY_LEVELS,
            "TRAINING_PRIORITY_RANK": TRAINING_PRIORITY_RANK,
        }
    )
    _TRAINING_CENTER_RUNTIME_BOUND = True

_POLICY_REANALYZE_REASON_CODES = {
    "agents_hash_mismatch",
    "cached_before_agents_mtime",
    "cached_at_missing",
    "agents_mtime_missing",
    "cache_payload_invalid_json",
    "cache_payload_incomplete",
    "cache_parse_status_missing",
    "cache_clarity_score_invalid",
    "cache_prompt_version_mismatch",
    "cache_extract_source_mismatch",
    "cache_write_failed",
    "manual_clear",
}
_POLICY_REANALYZE_AGENTS_UPDATED_CODES = {
    "agents_hash_mismatch",
    "cached_before_agents_mtime",
}



# Runtime domain logic is split into layered modules.
from ..services import policy_session_runtime as _policy_session_runtime
from ..services import policy_contract_runtime as _policy_contract_runtime
from ..services import session_orchestration as _session_orchestration
from ..services import task_orchestration as _task_orchestration
from ..services import chat_session_runtime as _chat_session_runtime
from ..services import training_workflow as _training_workflow
from ..infra import audit_runtime as _audit_runtime

_RUNTIME_DOMAIN_MODULES = (
    _policy_contract_runtime,
    _policy_session_runtime,
    _session_orchestration,
    _task_orchestration,
    _chat_session_runtime,
    _training_workflow,
    _audit_runtime,
)

for _runtime_domain_module in _RUNTIME_DOMAIN_MODULES:
    _runtime_domain_module.bind_runtime_symbols(globals())

for _runtime_domain_module in _RUNTIME_DOMAIN_MODULES:
    for _name, _value in _runtime_domain_module.__dict__.items():
        if _name.startswith("__") or _name == "bind_runtime_symbols":
            continue
        globals()[_name] = _value

# Re-bind once after exporting symbols so cross-domain function references
# are visible in every extracted module namespace.
for _runtime_domain_module in _RUNTIME_DOMAIN_MODULES:
    _runtime_domain_module.bind_runtime_symbols(globals())

del _runtime_domain_module, _name, _value

def make_handler(cfg: AppConfig, state: RuntimeState) -> type[BaseHTTPRequestHandler]:
    bind_training_center_runtime_once()

    class Handler(BaseHTTPRequestHandler):
        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def send_html(self, text: str) -> None:
            raw = text.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def send_text(self, status: int, text: str, content_type: str) -> None:
            raw = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            if not body:
                return {}
            obj = json.loads(body.decode("utf-8"))
            return obj if isinstance(obj, dict) else {}

        def root_status(self) -> tuple[Path | None, bool, str, str]:
            root, ready, error_code = current_agent_search_root_status(cfg, state)
            return root, ready, error_code, agent_search_root_text(root)

        def root_not_ready_payload(self) -> dict[str, Any]:
            _root, ready, error_code, root_text = self.root_status()
            if ready:
                return {}
            return {
                "ok": False,
                "error": agent_search_root_block_message(error_code),
                "code": error_code or AGENT_SEARCH_ROOT_NOT_SET_CODE,
                "agent_search_root": root_text,
                "agent_search_root_ready": False,
                "features_locked": True,
            }

        def ensure_root_ready(self) -> bool:
            payload = self.root_not_ready_payload()
            if payload:
                self.send_json(409, payload)
                return False
            return True

        def payload_common(self, body: dict[str, Any]) -> tuple[str, str, str, str, bool]:
            agent = safe_token(str(body.get("agent_name") or body.get("agent") or ""), "", 80)
            session_id = safe_token(str(body.get("session_id") or ""), "", 140)
            focus = str(body.get("focus") or cfg.focus).strip()[:180]
            agent_search_root = str(
                body.get("agent_search_root")
                or body.get("agentSearchRoot")
                or body.get("target_path")
                or body.get("targetPath")
                or ""
            ).strip()
            is_test_data = parse_bool_flag(
                body.get("is_test_data", body.get("isTestData")),
                default=False,
            )
            if not focus:
                focus = cfg.focus
            return agent, session_id, focus, agent_search_root, is_test_data

        def resolve_session(
            self,
            body: dict[str, Any],
            *,
            allow_create: bool,
        ) -> tuple[dict[str, Any], str] | None:
            (
                requested_agent,
                requested_session_id,
                focus,
                requested_agent_search_root,
                requested_is_test_data,
            ) = self.payload_common(body)
            try:
                session, _created = ensure_session(
                    cfg,
                    state,
                    requested_session_id=requested_session_id,
                    requested_agent_name=requested_agent,
                    requested_agent_search_root=requested_agent_search_root,
                    requested_is_test_data=requested_is_test_data,
                    allow_create=allow_create,
                )
            except SessionGateError as exc:
                persist_event(
                    cfg.root,
                    {
                        "event_id": event_id(),
                        "timestamp": iso_ts(now_local()),
                        "session_id": requested_session_id or "sess-gate",
                        "actor": "workflow",
                        "stage": "governance",
                        "action": "session_gate_blocked",
                        "status": "failed",
                        "latency_ms": 0,
                        "task_id": "",
                        "reason_tags": [exc.code],
                        "ref": "",
                    },
                )
                self.send_json(
                    exc.status_code,
                    {
                        "ok": False,
                        "error": str(exc),
                        "code": exc.code,
                        "agent_search_root": current_agent_search_root_text(cfg, state),
                        "available_agents": [
                            {
                                "agent_name": item["agent_name"],
                                "agents_hash": item["agents_hash"],
                                "agents_loaded_at": item["agents_loaded_at"],
                            }
                            for item in list_available_agents(cfg)
                        ],
                        **exc.extra,
                    },
                )
                return None
            return session, focus

        def enforce_session_policy_reanalyze(self, session: dict[str, Any], route: str) -> bool:
            guard = session_policy_reanalyze_guard(cfg, session)
            if not bool(guard.get("required")):
                return True
            reason = str(guard.get("message") or "当前会话角色策略缓存已过期，请先重新分析。")
            reason_codes = [
                str(code).strip()
                for code in (guard.get("reason_codes") or [])
                if str(code or "").strip()
            ]
            tags = [AGENT_POLICY_REANALYZE_REQUIRED_CODE]
            tags.extend(reason_codes[:4])
            persist_event(
                cfg.root,
                {
                    "event_id": event_id(),
                    "timestamp": iso_ts(now_local()),
                    "session_id": str(session.get("session_id") or "sess-gate"),
                    "actor": "workflow",
                    "stage": "governance",
                    "action": "session_policy_reanalyze_blocked",
                    "status": "failed",
                    "latency_ms": 0,
                    "task_id": "",
                    "reason_tags": tags,
                    "ref": "",
                },
            )
            self.send_json(
                409,
                {
                    "ok": False,
                    "error": reason,
                    "code": AGENT_POLICY_REANALYZE_REQUIRED_CODE,
                    "session_id": str(session.get("session_id") or ""),
                    "agent_name": str(session.get("agent_name") or ""),
                    "session_agents_hash": str(session.get("agents_hash") or ""),
                    "action_hint": "请在会话入口点击“生成缓存”并等待分析完成后再发送。",
                    "policy_reanalyze": guard,
                },
            )
            return False

        def refresh_after_round(self) -> None:
            sync_analysis_tasks(cfg.root)
            sync_training_workflows(cfg.root)
            refresh_status(cfg)

        def do_GET(self) -> None:  # noqa: N802
            from ..api.router import dispatch_get

            dispatch_get(self, cfg, state)

        def do_POST(self) -> None:  # noqa: N802
            from ..api.router import dispatch_post

            dispatch_post(self, cfg, state)

        def log_message(self, fmt: str, *args: object) -> None:
            return

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Workflow web workbench")
    parser.add_argument("--root", default=".runtime", help="runtime root")
    parser.add_argument("--entry-script", default="scripts/workflow_entry_cli.py", help="default entry script")
    parser.add_argument(
        "--agent-search-root",
        "--default-agents-root",
        "--agents-root",
        dest="agent_search_root",
        default="",
        help="scan root for AGENTS.md (default: runtime-config -> WORKFLOW_AGENTS_ROOT -> C:/work/agents; invalid path => empty/unset)",
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host")
    parser.add_argument("--port", type=int, default=8090, help="bind port")
    parser.add_argument("--focus", default=DEFAULT_WORKFLOW_FOCUS, help="default focus")
    parser.add_argument("--reconcile-interval-s", type=int, default=86400, help="auto reconcile interval")
    parser.add_argument(
        "--allow-manual-policy-input",
        default="",
        help="allow manual policy fallback input (1/0, true/false). default from WORKFLOW_ALLOW_MANUAL_POLICY_INPUT",
    )
    return parser.parse_args()


def resolve_entry_script(runtime_root: Path, raw_entry_script: str) -> Path:
    token = str(raw_entry_script or "").strip() or "scripts/workflow_entry_cli.py"
    source = Path(token)
    this_dir = WORKFLOW_APP_ROOT
    candidates: list[Path] = []
    if source.is_absolute():
        candidates.append(source.resolve(strict=False))
    else:
        candidates.append((runtime_root / source).resolve(strict=False))
        candidates.append((this_dir / source.name).resolve(strict=False))
        candidates.append((WORKFLOW_PROJECT_ROOT / source).resolve(strict=False))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    checked = ", ".join(item.as_posix() for item in candidates)
    raise SystemExit(f"entry script not found: {token}; checked=[{checked}]")


def resolve_startup_agent_search_root(raw: str, *, base: Path) -> Path | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        candidate = normalize_abs_path(text, base=base)
    except Exception:
        return None
    ready, _code = agent_search_root_state(candidate)
    if not ready:
        return None
    return candidate


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    entry_script = resolve_entry_script(root, args.entry_script)
    runtime_cfg = load_runtime_config(root)
    requested_root_text = str(args.agent_search_root or "").strip()
    if not requested_root_text:
        requested_root_text = str(runtime_cfg.get("agent_search_root") or "").strip()
    if not requested_root_text:
        requested_root_text = DEFAULT_AGENTS_ROOT.as_posix()
    agent_search_root = resolve_startup_agent_search_root(requested_root_text, base=root)
    if requested_root_text and agent_search_root is None:
        print(
            f"web> agent_search_root unavailable on startup, fallback to empty: {requested_root_text}",
            flush=True,
        )
    allow_manual_text = str(args.allow_manual_policy_input or "").strip()
    if allow_manual_text:
        allow_manual_policy_input = parse_bool_flag(
            allow_manual_text,
            default=ALLOW_MANUAL_POLICY_INPUT_DEFAULT,
        )
    else:
        allow_manual_policy_input = ALLOW_MANUAL_POLICY_INPUT_DEFAULT
    show_test_data = parse_bool_flag(runtime_cfg.get("show_test_data"), default=True)
    cfg = AppConfig(
        root=root,
        entry_script=entry_script,
        agent_search_root=agent_search_root,
        show_test_data=show_test_data,
        host=args.host,
        port=int(args.port),
        focus=str(args.focus),
        reconcile_interval_s=max(60, int(args.reconcile_interval_s)),
        allow_manual_policy_input=allow_manual_policy_input,
    )
    state = RuntimeState()
    ensure_dirs(cfg.root)
    save_runtime_config(
        cfg.root,
        {
            "agent_search_root": agent_search_root_text(agent_search_root),
            "show_test_data": bool(show_test_data),
        },
    )
    ensure_tables(cfg.root)
    ensure_metric_files(cfg.root)
    bind_training_center_runtime_once()
    init_ab_state(cfg)
    refresh_status(cfg)
    sync_analysis_tasks(cfg.root)
    sync_training_workflows(cfg.root)
    with state.reconcile_lock:
        run_reconcile(cfg, "startup")
    if TEST_DATA_AUTO_CLEANUP_ENABLED and active_runtime_task_count(state) <= 0:
        try:
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
                    "startup test-data cleanup",
                    (
                        f"deleted_sessions={deleted}, "
                        f"max_age_hours={cleanup_result.get('max_age_hours')}, "
                        f"skipped_active={cleanup_result.get('skipped_active',0)}, "
                        f"skipped_recent={cleanup_result.get('skipped_recent',0)}"
                    ),
                )
        except Exception as exc:
            append_failure_case(cfg.root, "startup_testdata_cleanup_failed", str(exc))
            append_change_log(cfg.root, "startup test-data cleanup failed", str(exc))
    scheduler = start_reconcile_scheduler(cfg, state)
    server = ThreadingHTTPServer((cfg.host, cfg.port), make_handler(cfg, state))
    print(f"web> http://{cfg.host}:{cfg.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        state.stop_event.set()
        scheduler.join(timeout=3)
        server.server_close()


if __name__ == "__main__":
    main()




