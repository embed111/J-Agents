from __future__ import annotations

from ..bootstrap import web_server_runtime as ws


def try_handle_get(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    if path != "/api/config/show-test-data":
        return False
    query = ctx.get("query") or {}
    if ws.parse_query_bool(query, "force_fail", default=False):
        handler.send_json(
            500,
            {
                "ok": False,
                "error": "show_test_data read failed: forced by query",
                "code": "show_test_data_read_failed",
            },
        )
        return True
    handler.send_json(
        200,
        {
            "ok": True,
            "show_test_data": bool(ws.current_show_test_data(cfg, state)),
        },
    )
    return True


def try_handle_post(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    body = ctx.get("body") or {}

    if path == "/api/config/agent-search-root":
        requested_root = str(
            body.get("agent_search_root")
            or body.get("agentSearchRoot")
            or ""
        ).strip()
        if not requested_root:
            handler.send_json(400, {"ok": False, "error": "agent_search_root required", "code": "agent_search_root_required"})
            return True
        try:
            result = ws.switch_agent_search_root(cfg, state, requested_root)
            handler.send_json(200, result)
        except ws.SessionGateError as exc:
            handler.send_json(
                exc.status_code,
                {"ok": False, "error": str(exc), "code": exc.code, **exc.extra},
            )
        return True

    if path == "/api/config/show-test-data":
        requested = ws.parse_bool_flag(
            body.get("show_test_data", body.get("showTestData")),
            default=ws.current_show_test_data(cfg, state),
        )
        if ws.parse_bool_flag(body.get("force_fail"), default=False):
            handler.send_json(
                500,
                {
                    "ok": False,
                    "error": "show_test_data save failed: forced by request",
                    "code": "show_test_data_save_failed",
                },
            )
            return True
        try:
            old_value, new_value = ws.set_show_test_data(cfg, state, requested)
        except ws.SessionGateError as exc:
            handler.send_json(
                exc.status_code,
                {"ok": False, "error": str(exc), "code": exc.code, **exc.extra},
            )
            return True
        ws.append_change_log(
            cfg.root,
            "show test data toggle",
            f"old={int(old_value)}, new={int(new_value)}",
        )
        handler.send_json(
            200,
            {
                "ok": True,
                "show_test_data": bool(new_value),
                "previous_show_test_data": bool(old_value),
            },
        )
        return True

    if path == "/api/config/manual-policy-input":
        if not handler.ensure_root_ready():
            return True
        requested = ws.parse_bool_flag(
            body.get("allow_manual_policy_input", body.get("allowManualPolicyInput")),
            default=ws.current_allow_manual_policy_input(cfg, state),
        )
        old_value, new_value = ws.set_allow_manual_policy_input(cfg, state, requested)
        ws.append_change_log(
            cfg.root,
            "manual policy input toggle",
            f"old={int(old_value)}, new={int(new_value)}",
        )
        handler.send_json(
            200,
            {
                "ok": True,
                "allow_manual_policy_input": bool(new_value),
                "previous_allow_manual_policy_input": bool(old_value),
            },
        )
        return True

    return False

