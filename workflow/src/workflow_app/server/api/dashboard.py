from __future__ import annotations

from ..bootstrap import web_server_runtime as ws


def try_handle_get(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    root_ready = bool(ctx.get("root_ready"))
    root_error = str(ctx.get("root_error") or "")
    root_text = str(ctx.get("root_text") or "")

    if path != "/api/status" and path != "/api/dashboard":
        return False

    if path == "/api/status":
        include_test_data = ws.current_show_test_data(cfg, state)
        pa, pt = ws.pending_counts(cfg.root, include_test_data=include_test_data)
        if ws.AB_FEATURE_ENABLED:
            ab = ws.ab_status(cfg)
        else:
            ab = {"active_version": "disabled", "active_slot": "disabled"}
        handler.send_json(
            200,
            {
                "ok": True,
                "pending_analysis": pa,
                "pending_training": pt,
                "active_version": ab["active_version"],
                "active_slot": ab["active_slot"],
                "available_agents": len(ws.list_available_agents(cfg)) if root_ready else 0,
                "show_test_data": bool(include_test_data),
                "agent_search_root": root_text,
                "agent_search_root_ready": bool(root_ready),
                "agent_search_root_error": root_error,
                "features_locked": not bool(root_ready),
            },
        )
        return True

    query = ctx.get("query") or {}
    include_test_data = ws.resolve_include_test_data(query, cfg, state)
    handler.send_json(
        200,
        {
            **ws.dashboard(cfg, include_test_data=include_test_data),
            "show_test_data": bool(ws.current_show_test_data(cfg, state)),
            "include_test_data": bool(include_test_data),
        },
    )
    return True

