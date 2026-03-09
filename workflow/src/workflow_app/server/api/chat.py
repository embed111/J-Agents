from __future__ import annotations

from ..bootstrap import web_server_runtime as ws


def try_handle_get(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    root_ready = bool(ctx.get("root_ready"))
    root_error = str(ctx.get("root_error") or "")
    root_text = str(ctx.get("root_text") or "")

    if path == "/api/agents":
        query = ctx.get("query") or {}
        if ws.parse_query_bool(query, "force_show_test_data_read_fail", default=False):
            handler.send_json(
                500,
                {
                    "ok": False,
                    "error": "show_test_data read failed: forced by query",
                    "code": "show_test_data_read_failed",
                },
            )
            return True
        agents = ws.list_available_agents(cfg) if root_ready else []
        handler.send_json(
            200,
            {
                "ok": True,
                "agents_root": root_text,
                "agent_search_root": root_text,
                "workspace_root_valid": bool(root_ready),
                "workspace_root_error": root_error,
                "agent_search_root_ready": bool(root_ready),
                "features_locked": not bool(root_ready),
                "show_test_data": bool(ws.current_show_test_data(cfg, state)),
                "allow_manual_policy_input": bool(ws.current_allow_manual_policy_input(cfg, state)),
                "policy_closure": ws.policy_closure_stats(cfg.root),
                "agents": agents,
                "count": len(agents),
            },
        )
        return True

    if path == "/api/chat/sessions":
        query = ctx.get("query") or {}
        include_test_data = ws.resolve_include_test_data(query, cfg, state)
        handler.send_json(
            200,
            {
                "ok": True,
                "include_test_data": include_test_data,
                "show_test_data": bool(ws.current_show_test_data(cfg, state)),
                "sessions": (
                    ws.list_chat_sessions(
                        cfg.root,
                        include_test_data=include_test_data,
                    )
                    if root_ready
                    else []
                ),
                "agent_search_root": root_text,
                "agent_search_root_ready": bool(root_ready),
                "features_locked": not bool(root_ready),
            },
        )
        return True

    return False

