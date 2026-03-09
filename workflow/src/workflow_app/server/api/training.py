from __future__ import annotations

import re

from ..bootstrap import web_server_runtime as ws


def try_handle_get(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    root_ready = bool(ctx.get("root_ready"))
    root_text = str(ctx.get("root_text") or "")
    query = ctx.get("query") or {}

    if path == "/api/training/agents":
        if not root_ready:
            handler.send_json(
                200,
                {
                    "ok": True,
                    "items": [],
                    "stats": {
                        "agent_total": 0,
                        "git_available_count": 0,
                        "latest_release_at": "",
                        "training_queue_pending": 0,
                    },
                    "agent_search_root": root_text,
                    "agent_search_root_ready": False,
                    "features_locked": True,
                    "show_test_data": bool(ws.current_show_test_data(cfg, state)),
                    "include_test_data": bool(ws.current_show_test_data(cfg, state)),
                },
            )
            return True
        include_test_data = ws.resolve_include_test_data(query, cfg, state)
        data = ws.list_training_agents_overview(cfg, include_test_data=include_test_data)
        handler.send_json(
            200,
            {
                "ok": True,
                **data,
                "include_test_data": include_test_data,
                "show_test_data": bool(ws.current_show_test_data(cfg, state)),
                "agent_search_root": root_text,
                "agent_search_root_ready": True,
                "features_locked": False,
            },
        )
        return True

    mtr = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/releases", path)
    if mtr:
        try:
            page = int((query.get("page") or ["1"])[0])
        except Exception:
            page = 1
        try:
            page_size = int((query.get("page_size") or ["50"])[0])
        except Exception:
            page_size = 50
        try:
            data = ws.list_training_agent_releases(
                cfg.root,
                ws.safe_token(mtr.group(1), "", 120),
                page=page,
                page_size=page_size,
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    if path == "/api/training/queue":
        if not root_ready:
            handler.send_json(
                200,
                {
                    "ok": True,
                    "items": [],
                    "show_test_data": bool(ws.current_show_test_data(cfg, state)),
                    "include_test_data": bool(ws.current_show_test_data(cfg, state)),
                    "agent_search_root": root_text,
                    "agent_search_root_ready": False,
                    "features_locked": True,
                },
            )
            return True
        include_removed = ws.parse_query_bool(query, "include_removed", default=True)
        include_test_data = ws.resolve_include_test_data(query, cfg, state)
        handler.send_json(
            200,
            {
                "ok": True,
                "items": ws.list_training_queue_items(
                    cfg.root,
                    include_removed=include_removed,
                    include_test_data=include_test_data,
                ),
                "include_removed": include_removed,
                "include_test_data": include_test_data,
                "show_test_data": bool(ws.current_show_test_data(cfg, state)),
            },
        )
        return True

    mrun = re.fullmatch(r"/api/training/runs/([0-9A-Za-z._:-]+)", path)
    if mrun:
        data = ws.get_training_run_detail(cfg.root, ws.safe_token(mrun.group(1), "", 160))
        if data is None:
            handler.send_json(404, {"ok": False, "error": "run not found", "code": "run_not_found"})
            return True
        handler.send_json(200, {"ok": True, **data})
        return True

    if path == "/api/training/trainers":
        query_text = str((query.get("query") or [""])[0] or "").strip()
        handler.send_json(
            200,
            {
                "ok": True,
                "query": query_text,
                "source_root": ws.TRAINER_SOURCE_ROOT.as_posix(),
                "items": ws.discover_training_trainers(query=query_text, limit=100),
            },
        )
        return True

    mrr = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review", path)
    if mrr:
        try:
            data = ws.get_training_agent_release_review(
                cfg.root,
                ws.safe_token(mrr.group(1), "", 120),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    return False


def try_handle_post(handler, cfg, state, ctx: dict) -> bool:
    path = str(ctx.get("path") or "")
    body = ctx.get("body") or {}

    if path.startswith("/api/training") and not handler.ensure_root_ready():
        return True

    if path == "/api/training/plans/manual":
        try:
            data = ws.create_training_plan_and_enqueue(
                cfg,
                body,
                forced_source="manual",
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    if path == "/api/training/plans/auto":
        try:
            data = ws.create_training_plan_and_enqueue(
                cfg,
                body,
                forced_source="auto_analysis",
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mts = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/switch", path)
    if mts:
        try:
            data = ws.switch_training_agent_release(
                cfg,
                agent_id=ws.safe_token(mts.group(1), "", 120),
                version_label=str(
                    body.get("version_label")
                    or body.get("target_version")
                    or ""
                ).strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mtc = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/clone", path)
    if mtc:
        try:
            data = ws.clone_training_agent_from_current(
                cfg,
                agent_id=ws.safe_token(mtc.group(1), "", 120),
                new_agent_name=str(
                    body.get("new_agent_name")
                    or body.get("agent_name")
                    or body.get("clone_agent_name")
                    or ""
                ).strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mta = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/avatar", path)
    if mta:
        try:
            data = ws.set_training_agent_avatar(
                cfg,
                agent_id=ws.safe_token(mta.group(1), "", 120),
                avatar_uri=str(body.get("avatar_uri") or body.get("avatar") or "").strip(),
                upload_name=str(body.get("upload_name") or body.get("file_name") or "").strip(),
                upload_content_type=str(
                    body.get("upload_content_type")
                    or body.get("content_type")
                    or body.get("mime_type")
                    or ""
                ).strip(),
                upload_base64=str(
                    body.get("upload_base64")
                    or body.get("file_base64")
                    or body.get("file_content_base64")
                    or ""
                ).strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mtd = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/pre-release/discard", path)
    if mtd:
        try:
            data = ws.discard_agent_pre_release(
                cfg,
                agent_id=ws.safe_token(mtd.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mte = re.fullmatch(
        r"/api/training/agents/([0-9A-Za-z._:-]+)/release-evaluations/manual",
        path,
    )
    if mte:
        try:
            data = ws.submit_manual_release_evaluation(
                cfg,
                agent_id=ws.safe_token(mte.group(1), "", 120),
                decision=str(body.get("decision") or "").strip(),
                reviewer=str(body.get("reviewer") or "").strip(),
                summary=str(body.get("summary") or "").strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mrre = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/enter", path)
    if mrre:
        try:
            data = ws.enter_training_agent_release_review(
                cfg,
                agent_id=ws.safe_token(mrre.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mrrm = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/manual", path)
    if mrrm:
        try:
            data = ws.submit_training_agent_release_review_manual(
                cfg,
                agent_id=ws.safe_token(mrrm.group(1), "", 120),
                decision=str(body.get("decision") or "").strip(),
                reviewer=str(body.get("reviewer") or "").strip(),
                review_comment=str(body.get("review_comment") or body.get("summary") or "").strip(),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mrrc = re.fullmatch(r"/api/training/agents/([0-9A-Za-z._:-]+)/release-review/confirm", path)
    if mrrc:
        try:
            data = ws.confirm_training_agent_release_review(
                cfg,
                agent_id=ws.safe_token(mrrc.group(1), "", 120),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mtrm = re.fullmatch(r"/api/training/queue/([0-9A-Za-z._:-]+)/remove", path)
    if mtrm:
        try:
            data = ws.remove_training_queue_item(
                cfg.root,
                queue_task_id_text=ws.safe_token(mtrm.group(1), "", 160),
                operator=str(body.get("operator") or "web-user"),
                reason=str(body.get("reason") or ""),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    mtre = re.fullmatch(r"/api/training/queue/([0-9A-Za-z._:-]+)/execute", path)
    if mtre:
        try:
            data = ws.execute_training_queue_item(
                cfg.root,
                queue_task_id_text=ws.safe_token(mtre.group(1), "", 160),
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    if path == "/api/training/queue/dispatch-next":
        try:
            data = ws.dispatch_next_training_queue_item(
                cfg.root,
                operator=str(body.get("operator") or "web-user"),
            )
            handler.send_json(200, {"ok": True, **data})
        except ws.TrainingCenterError as exc:
            payload = {"ok": False, "error": str(exc), "code": exc.code}
            payload.update(exc.extra)
            handler.send_json(exc.status_code, payload)
        return True

    return False

