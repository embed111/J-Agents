from __future__ import annotations

# NOTE: legacy full-route implementation extracted from workflow_web_server.py
# Keep behavior-compatible while routing is being modularized.
from ..bootstrap.web_server_runtime import *  # noqa: F401,F403

from .legacy_task_crud_handlers import try_handle_task_crud_routes
from .legacy_task_queue_handlers import (
    handle_chat_non_stream,
    handle_chat_stream,
    handle_task_execute,
)
from .legacy_task_reconcile_handlers import try_handle_task_reconcile_routes


def handle_post_legacy(self, cfg, state) -> None:
    path = urlparse(self.path).path
    cached_body = getattr(self, "_cached_request_body", None)
    if isinstance(cached_body, dict):
        body = cached_body
    else:
        try:
            body = self.read_json()
        except Exception:
            self.send_json(400, {"ok": False, "error": "invalid json"})
            return
    try:
        delattr(self, "_cached_request_body")
    except Exception:
        pass
    if path == "/api/config/agent-search-root":
        requested_root = str(
            body.get("agent_search_root")
            or body.get("agentSearchRoot")
            or ""
        ).strip()
        if not requested_root:
            self.send_json(400, {"ok": False, "error": "agent_search_root required", "code": "agent_search_root_required"})
            return
        try:
            result = switch_agent_search_root(cfg, state, requested_root)
            self.send_json(200, result)
        except SessionGateError as exc:
            self.send_json(
                exc.status_code,
                {"ok": False, "error": str(exc), "code": exc.code, **exc.extra},
            )
        return
    if path == "/api/config/show-test-data":
        requested = parse_bool_flag(
            body.get("show_test_data", body.get("showTestData")),
            default=current_show_test_data(cfg, state),
        )
        if parse_bool_flag(body.get("force_fail"), default=False):
            self.send_json(
                500,
                {
                    "ok": False,
                    "error": "show_test_data save failed: forced by request",
                    "code": "show_test_data_save_failed",
                },
            )
            return
        try:
            old_value, new_value = set_show_test_data(cfg, state, requested)
        except SessionGateError as exc:
            self.send_json(
                exc.status_code,
                {"ok": False, "error": str(exc), "code": exc.code, **exc.extra},
            )
            return
        append_change_log(
            cfg.root,
            "show test data toggle",
            f"old={int(old_value)}, new={int(new_value)}",
        )
        self.send_json(
            200,
            {
                "ok": True,
                "show_test_data": bool(new_value),
                "previous_show_test_data": bool(old_value),
            },
        )
        return
    if not self.ensure_root_ready():
        return
    if path == "/api/chat":
        handle_chat_non_stream(self, cfg, state, body)
        return
    if path == "/api/chat/stream":
        handle_chat_stream(self, cfg, state, body)
        return
    if path == "/api/tasks/execute":
        handle_task_execute(self, cfg, state, body)
        return
    if path == "/api/config/manual-policy-input":
        requested = parse_bool_flag(
            body.get("allow_manual_policy_input", body.get("allowManualPolicyInput")),
            default=current_allow_manual_policy_input(cfg, state),
        )
        old_value, new_value = set_allow_manual_policy_input(cfg, state, requested)
        append_change_log(
            cfg.root,
            "manual policy input toggle",
            f"old={int(old_value)}, new={int(new_value)}",
        )
        self.send_json(
            200,
            {
                "ok": True,
                "allow_manual_policy_input": bool(new_value),
                "previous_allow_manual_policy_input": bool(old_value),
            },
        )
        return
    if path == "/api/training/plans/manual":
        try:
            data = create_training_plan_and_enqueue(
                cfg,
                body,
                forced_source="manual",
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    if path == "/api/training/plans/auto":
        try:
            data = create_training_plan_and_enqueue(
                cfg,
                body,
                forced_source="auto_analysis",
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mts = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/switch", path)
    if mts:
        try:
            data = switch_training_agent_release(
                cfg,
                agent_id=safe_token(mts.group(1), "", 120),
                version_label=str(
                    body.get("version_label")
                    or body.get("target_version")
                    or ""
                ).strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mtc = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/clone", path)
    if mtc:
        try:
            data = clone_training_agent_from_current(
                cfg,
                agent_id=safe_token(mtc.group(1), "", 120),
                new_agent_name=str(
                    body.get("new_agent_name")
                    or body.get("agent_name")
                    or body.get("clone_agent_name")
                    or ""
                ).strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mtd = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/pre-release/discard", path)
    if mtd:
        try:
            data = discard_agent_pre_release(
                cfg,
                agent_id=safe_token(mtd.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mte = re.fullmatch(
        r"/api/training/agents/([0-9A-Za-z._:-]+)/release-evaluations/manual",
        path,
    )
    if mte:
        try:
            data = submit_manual_release_evaluation(
                cfg,
                agent_id=safe_token(mte.group(1), "", 120),
                decision=str(body.get("decision") or "").strip(),
                reviewer=str(body.get("reviewer") or "").strip(),
                summary=str(body.get("summary") or "").strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mrre = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/enter", path)
    if mrre:
        try:
            data = enter_training_agent_release_review(
                cfg,
                agent_id=safe_token(mrre.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mrrm = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/manual", path)
    if mrrm:
        try:
            data = submit_training_agent_release_review_manual(
                cfg,
                agent_id=safe_token(mrrm.group(1), "", 120),
                decision=str(body.get("decision") or "").strip(),
                reviewer=str(body.get("reviewer") or "").strip(),
                review_comment=str(body.get("review_comment") or body.get("summary") or "").strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mrrc = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/confirm", path)
    if mrrc:
        try:
            data = confirm_training_agent_release_review(
                cfg,
                agent_id=safe_token(mrrc.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mtrm = re.fullmatch(r"/api/training/queue/([0-9A-Za-z._:-]+)/remove", path)
    if mtrm:
        try:
            data = remove_training_queue_item(
                cfg.root,
                queue_task_id_text=safe_token(mtrm.group(1), "", 160),
                operator=str(body.get("operator") or "web-user"),
                reason=str(body.get("reason") or ""),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    mtre = re.fullmatch(r"/api/training/queue/([0-9A-Za-z._:-]+)/execute", path)
    if mtre:
        try:
            data = execute_training_queue_item(
                cfg.root,
                queue_task_id_text=safe_token(mtre.group(1), "", 160),
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    if path == "/api/training/queue/dispatch-next":
        try:
            data = dispatch_next_training_queue_item(
                cfg.root,
                operator=str(body.get("operator") or "web-user"),
            )
            self.send_json(200, {"ok": True, **data})
        except TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        return
    if path == "/api/policy/analyze":
        agent_name = safe_token(str(body.get("agent_name") or ""), "", 80)
        if not agent_name:
            self.send_json(
                400,
                {"ok": False, "error": "agent_name required", "code": "agent_required"},
            )
            return
        requested_agent_search_root = str(
            body.get("agent_search_root")
            or body.get("agentSearchRoot")
            or ""
        ).strip()
        current_root = current_agent_search_root(cfg, state)
        if requested_agent_search_root:
            requested_root = normalize_abs_path(requested_agent_search_root, base=cfg.root)
            if requested_root != current_root:
                self.send_json(
                    409,
                    {
                        "ok": False,
                        "error": (
                            f"agent_search_root mismatch: "
                            f"current={current_root.as_posix()} requested={requested_root.as_posix()}"
                        ),
                        "code": "agent_search_root_mismatch",
                        "agent_search_root": current_root.as_posix(),
                    },
                )
                return
        selected = load_agent_with_policy(cfg, agent_name)
        if not selected:
            self.send_json(
                400,
                {"ok": False, "error": f"agent not available: {agent_name}", "code": "agent_not_available"},
            )
            return
        allow_manual_input = current_allow_manual_policy_input(cfg, state)
        policy_snapshot, policy_error = extract_policy_snapshot_from_agent_item(selected)
        gate_payload = agent_policy_gate_payload(
            selected,
            snapshot=policy_snapshot,
            policy_error=policy_error,
            allow_manual_policy_input=allow_manual_input,
        )
        self.send_json(
            200,
            {
                "ok": True,
                "agent_name": agent_name,
                "policy_confirmation": gate_payload,
                "agent_policy": selected,
            },
        )
        return
    if path == "/api/policy/cache/clear":
        scope = safe_token(str(body.get("scope") or "selected"), "selected", 20).lower()
        requested_agent_name = safe_token(str(body.get("agent_name") or ""), "", 80)
        requested_agent_path = str(
            body.get("agent_path")
            or body.get("agents_path")
            or ""
        ).strip()
        clear_all = bool(scope == "all" or (not requested_agent_name and not requested_agent_path))
        resolved_agent_path = requested_agent_path
        if not clear_all and not resolved_agent_path:
            agents = list_available_agents(cfg)
            selected = next(
                (item for item in agents if item.get("agent_name") == requested_agent_name),
                None,
            )
            if not selected:
                self.send_json(
                    400,
                    {
                        "ok": False,
                        "error": f"agent not available: {requested_agent_name}",
                        "code": "agent_not_available",
                    },
                )
                return
            resolved_agent_path = str(selected.get("agents_md_path") or "")
        result = clear_agent_policy_cache(
            cfg.root,
            clear_all=clear_all,
            agent_path=resolved_agent_path,
        )
        append_change_log(
            cfg.root,
            "policy cache clear",
            (
                f"scope={result.get('scope')}, agent={requested_agent_name or '-'}, "
                f"path={resolved_agent_path or '-'}, deleted={result.get('deleted_count',0)}"
            ),
        )
        self.send_json(
            200,
            {
                "ok": True,
                "scope": result.get("scope", "selected"),
                "agent_name": requested_agent_name,
                "agent_path": resolved_agent_path,
                "deleted_count": int(result.get("deleted_count") or 0),
                "before_count": int(result.get("before_count") or 0),
                "remaining_count": int(result.get("remaining_count") or 0),
            },
        )
        return
    if path == "/api/policy/recommend":
        agent_name = safe_token(str(body.get("agent_name") or ""), "", 80)
        instruction = str(body.get("instruction") or body.get("prompt") or "").strip()
        if not agent_name:
            self.send_json(
                400,
                {"ok": False, "error": "agent_name required", "code": "agent_required"},
            )
            return
        if not instruction:
            self.send_json(
                400,
                {
                    "ok": False,
                    "error": "instruction required",
                    "code": "policy_recommend_instruction_required",
                },
            )
            return
        instruction_valid, instruction_error = validate_policy_recommend_instruction(instruction)
        if not instruction_valid:
            self.send_json(
                400,
                {
                    "ok": False,
                    "error": str(instruction_error or "instruction invalid"),
                    "code": "policy_recommend_instruction_invalid",
                },
            )
            return
        requested_agent_search_root = str(
            body.get("agent_search_root")
            or body.get("agentSearchRoot")
            or ""
        ).strip()
        current_root = current_agent_search_root(cfg, state)
        if requested_agent_search_root:
            requested_root = normalize_abs_path(requested_agent_search_root, base=cfg.root)
            if requested_root != current_root:
                self.send_json(
                    409,
                    {
                        "ok": False,
                        "error": (
                            f"agent_search_root mismatch: "
                            f"current={current_root.as_posix()} requested={requested_root.as_posix()}"
                        ),
                        "code": "agent_search_root_mismatch",
                        "agent_search_root": current_root.as_posix(),
                    },
                )
                return
        role_profile = str(body.get("role_profile") or "").strip()
        session_goal = str(body.get("session_goal") or "").strip()
        duty_items = normalize_duty_constraints_input(
            body.get("duty_constraints", body.get("duty_constraints_text"))
        )
        if not role_profile and not session_goal and not duty_items:
            selected = load_agent_with_policy(cfg, agent_name)
            if selected:
                role_profile = str(selected.get("role_profile") or "").strip()
                session_goal = str(selected.get("session_goal") or "").strip()
                duty_items = normalize_duty_constraints_input(
                    selected.get("duty_constraints")
                    if isinstance(selected.get("duty_constraints"), list)
                    else selected.get("duty_constraints_text")
                )
        recommendation, source, warnings = recommend_agent_policy(
            agent_name=agent_name,
            instruction=instruction,
            role_profile=role_profile,
            session_goal=session_goal,
            duty_constraints=duty_items,
            codex_workspace_root=current_root,
        )
        recommendation_payload = dict(recommendation)
        if not isinstance(recommendation_payload.get("constraints"), dict):
            recommendation_constraints = extract_constraints_from_policy(
                sections=[],
                duty_items=normalize_duty_constraints_input(
                    recommendation_payload.get("duty_constraints")
                    if isinstance(recommendation_payload.get("duty_constraints"), list)
                    else recommendation_payload.get("duty_constraints_text")
                ),
            )
            recommendation_payload["constraints"] = recommendation_constraints
        self.send_json(
            200,
            {
                "ok": True,
                "agent_name": agent_name,
                "instruction": instruction,
                "source": source,
                "warnings": warnings,
                "recommendation": recommendation_payload,
            },
        )
        return
    if path == "/api/policy/rescore":
        agent_name = safe_token(str(body.get("agent_name") or ""), "", 80)
        if not agent_name:
            self.send_json(
                400,
                {"ok": False, "error": "agent_name required", "code": "agent_required"},
            )
            return
        requested_agent_search_root = str(
            body.get("agent_search_root")
            or body.get("agentSearchRoot")
            or ""
        ).strip()
        current_root = current_agent_search_root(cfg, state)
        if requested_agent_search_root:
            requested_root = normalize_abs_path(requested_agent_search_root, base=cfg.root)
            if requested_root != current_root:
                self.send_json(
                    409,
                    {
                        "ok": False,
                        "error": (
                            f"agent_search_root mismatch: "
                            f"current={current_root.as_posix()} requested={requested_root.as_posix()}"
                        ),
                        "code": "agent_search_root_mismatch",
                        "agent_search_root": current_root.as_posix(),
                    },
                )
                return

        selected = load_agent_with_policy(cfg, agent_name)
        if not selected:
            self.send_json(
                400,
                {"ok": False, "error": f"agent not available: {agent_name}", "code": "agent_not_available"},
            )
            return

        role_profile = str(body.get("role_profile") or "").strip()
        session_goal = str(body.get("session_goal") or "").strip()
        edited_duty_raw = body.get("duty_constraints", body.get("duty_constraints_text"))
        edited_duty_items = normalize_duty_constraints_input(edited_duty_raw)
        if not role_profile and not session_goal and not edited_duty_items:
            role_profile = str(selected.get("role_profile") or "").strip()
            session_goal = str(selected.get("session_goal") or "").strip()
            edited_duty_raw = (
                selected.get("duty_constraints")
                if isinstance(selected.get("duty_constraints"), list)
                else selected.get("duty_constraints_text")
            )

        before_preview = _build_policy_rescore_payload_from_agent_item(selected)
        unchanged_input = _policy_rescore_input_matches_agent_item(
            selected,
            role_profile=role_profile,
            session_goal=session_goal,
            duty_constraints_raw=edited_duty_raw,
        )
        if unchanged_input:
            after_preview = json.loads(json.dumps(before_preview, ensure_ascii=False))
        else:
            after_preview = _build_policy_rescore_payload_from_fields(
                role_profile=role_profile,
                session_goal=session_goal,
                duty_constraints_raw=edited_duty_raw,
            )
        diff_preview = _build_policy_rescore_diff(before_preview, after_preview)
        diff_preview["unchanged_input"] = bool(unchanged_input)
        self.send_json(
            200,
            {
                "ok": True,
                "agent_name": agent_name,
                "allow_manual_policy_input": bool(current_allow_manual_policy_input(cfg, state)),
                "preview": {
                    "before": before_preview,
                    "after": after_preview,
                    "diff": diff_preview,
                    "unchanged_input": bool(unchanged_input),
                },
            },
        )
        return
    if path == "/api/sessions/policy-confirm":
        (
            requested_agent,
            requested_session_id,
            _focus,
            requested_agent_search_root,
            requested_is_test_data,
        ) = self.payload_common(body)
        action = str(body.get("action") or "").strip().lower()
        operator = safe_token(str(body.get("operator") or "web-user"), "web-user", 80)
        reason_text = str(body.get("reason") or "").strip()
        edited_role_profile = str(body.get("role_profile") or "").strip()
        edited_session_goal = str(body.get("session_goal") or "").strip()
        edited_duty_constraints = body.get("duty_constraints", body.get("duty_constraints_text"))
        try:
            result = confirm_session_policy_and_create(
                cfg,
                state,
                requested_session_id=requested_session_id,
                requested_agent_name=requested_agent,
                requested_agent_search_root=requested_agent_search_root,
                requested_is_test_data=requested_is_test_data,
                action=action,
                operator=operator,
                reason_text=reason_text,
                edited_role_profile=edited_role_profile,
                edited_session_goal=edited_session_goal,
                edited_duty_constraints=edited_duty_constraints,
            )
        except SessionGateError as exc:
            self.send_json(
                exc.status_code,
                {
                    "ok": False,
                    "error": str(exc),
                    "code": exc.code,
                    "agent_search_root": current_agent_search_root_text(cfg, state),
                    **exc.extra,
                },
            )
            return
        if bool(result.get("terminated")):
            self.send_json(
                200,
                {
                    "ok": True,
                    "terminated": True,
                    "action": result.get("action"),
                    "audit_id": result.get("audit_id"),
                    "manual_fallback": bool(result.get("manual_fallback")),
                    "policy_confirmation": result.get("policy_confirmation") or {},
                },
            )
            return
        session = result.get("session") if isinstance(result.get("session"), dict) else {}
        self.send_json(
            200,
            {
                "ok": True,
                "session_id": session.get("session_id", ""),
                "agent_name": session.get("agent_name", ""),
                "agents_hash": session.get("agents_hash", ""),
                "agents_loaded_at": session.get("agents_loaded_at", ""),
                "agents_path": session.get("agents_path", ""),
                "agents_version": session.get("agents_version", ""),
                "role_profile": session.get("role_profile", ""),
                "session_goal": session.get("session_goal", ""),
                "duty_constraints": session.get("duty_constraints", ""),
                "policy_snapshot_json": session.get("policy_snapshot_json", "{}"),
                "policy_summary": session.get("policy_summary", ""),
                "agent_search_root": session.get("agent_search_root", ""),
                "is_test_data": bool(session.get("is_test_data")),
                "created_at": session.get("created_at", ""),
                "audit_id": result.get("audit_id"),
                "patch_task_id": result.get("patch_task_id"),
                "manual_fallback": bool(result.get("manual_fallback")),
                "policy_confirmation": result.get("policy_confirmation") or {},
            },
        )
        return
    if path == "/api/sessions":
        resolved = self.resolve_session(body, allow_create=True)
        if not resolved:
            return
        session, _focus = resolved
        self.send_json(
            200,
            {
                "ok": True,
                "session_id": session["session_id"],
                "agent_name": session["agent_name"],
                "agents_hash": session["agents_hash"],
                "agents_loaded_at": session["agents_loaded_at"],
                "agents_path": session.get("agents_path", ""),
                "agents_version": session.get("agents_version", ""),
                "role_profile": session.get("role_profile", ""),
                "session_goal": session.get("session_goal", ""),
                "duty_constraints": session.get("duty_constraints", ""),
                "policy_snapshot_json": session.get("policy_snapshot_json", "{}"),
                "policy_summary": session.get("policy_summary", ""),
                "agent_search_root": session["agent_search_root"],
                "is_test_data": bool(session.get("is_test_data")),
                "created_at": session["created_at"],
            },
        )
        return
    mrs = re.fullmatch(r"/api/chat/sessions/([0-9A-Za-z._:-]+)/reopen", path)
    if mrs:
        session_id = safe_token(mrs.group(1), "", 140)
        if not session_id:
            self.send_json(400, {"ok": False, "error": "session_id required", "code": "session_required"})
            return
        try:
            session = reopen_closed_session(cfg, state, session_id)
            self.send_json(200, {"ok": True, **session})
        except SessionGateError as exc:
            self.send_json(
                exc.status_code,
                {
                    "ok": False,
                    "error": str(exc),
                    "code": exc.code,
                    "agent_search_root": current_agent_search_root_text(cfg, state),
                    **exc.extra,
                },
            )
        return
    if path == "/api/chat/interrupt":
        stream_id = str(body.get("stream_id") or "")
        if not stream_id:
            self.send_json(400, {"ok": False, "error": "stream_id required"})
            return
        with state.stream_lock:
            stop_evt = state.active_streams.get(stream_id)
        if not stop_evt:
            self.send_json(404, {"ok": False, "error": "stream not found"})
            return
        stop_evt.set()
        self.send_json(200, {"ok": True, "stream_id": stream_id, "interrupted": True})
        return
    mi = re.fullmatch(r"/api/tasks/([0-9A-Za-z._:-]+)/interrupt", path)
    if mi:
        task_id_text = safe_token(mi.group(1), "", 140)
        ok, msg = request_task_interrupt(cfg, state, task_id_text)
        self.send_json(
            200 if ok else 409,
            {
                "ok": ok,
                "task_id": task_id_text,
                "message": msg,
            },
        )
        return
    if path == "/api/workflows/training/assign":
        workflow_id = safe_token(str(body.get("workflow_id") or ""), "", 120)
        analyst = str(body.get("analyst") or body.get("assignee") or "").strip()
        note = str(body.get("note") or "").strip()
        if not workflow_id:
            self.send_json(400, {"ok": False, "error": "workflow_id required"})
            return
        if not analyst:
            self.send_json(400, {"ok": False, "error": "analyst required"})
            return
        try:
            workflow = assign_training_workflow(cfg, state, workflow_id, analyst, note)
            self.send_json(200, {"ok": True, "workflow": workflow})
        except WorkflowGateError as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "code": exc.code,
            }
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
        return
    if path == "/api/workflows/training/plan":
        workflow_id = safe_token(str(body.get("workflow_id") or ""), "", 120)
        if not workflow_id:
            self.send_json(400, {"ok": False, "error": "workflow_id required"})
            return
        try:
            result = generate_training_workflow_plan(cfg, workflow_id)
            self.send_json(200, {"ok": True, **result})
        except WorkflowGateError as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "code": exc.code,
            }
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        except Exception as exc:
            self.send_json(500, {"ok": False, "error": str(exc)})
        return
    if path == "/api/workflows/training/execute":
        workflow_id = safe_token(str(body.get("workflow_id") or ""), "", 120)
        raw_items = body.get("selected_items")
        selected_items: list[str] = []
        if isinstance(raw_items, list):
            selected_items = [str(item) for item in raw_items]
        elif isinstance(raw_items, str):
            selected_items = [raw_items]
        if not workflow_id:
            self.send_json(400, {"ok": False, "error": "workflow_id required"})
            return
        try:
            result = execute_training_workflow_plan(
                cfg,
                workflow_id,
                selected_items,
                max_retries=int(body.get("max_retries") or 3),
            )
            self.send_json(200, {"ok": True, **result})
        except WorkflowGateError as exc:
            payload = {
                "ok": False,
                "error": str(exc),
                "code": exc.code,
            }
            payload.update(exc.extra)
            self.send_json(exc.status_code, payload)
        except Exception as exc:
            append_failure_case(
                cfg.root,
                "workflow_execute_failed",
                f"workflow_id={workflow_id}, err={exc}",
            )
            self.send_json(500, {"ok": False, "error": str(exc)})
        return
    if try_handle_task_crud_routes(self, cfg, state, path, body):
        return
    if try_handle_task_reconcile_routes(self, cfg, state, path, body):
        return
    self.send_json(404, {"ok": False, "error": "not found"})


