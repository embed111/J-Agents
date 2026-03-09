# ARCHITECTURE_REFACTOR_MAP

## 1. 重构目标
- 将 `workflow_web_server.py` 从“全量承载”改为“薄入口门面”。
- 将路由分发下沉至 `server/api/*`，并按领域分层。
- 将模板迁移到 `presentation`，DB 连接/迁移迁移到 `infra/db`。
- 将 Agent 发现与策略解析链路迁移到 `services`。
- 前端拆分至少一个高耦合域（训练中心域）。

## 2. 旧职责 -> 新模块映射

| 旧职责（原集中在 `workflow_web_server.py`） | 新模块 |
|---|---|
| `do_GET/do_POST` 全量分支 | `src/workflow_app/server/api/router.py` + `config.py/chat.py/training.py/policy.py/dashboard.py` |
| 兼容全量路由逻辑（兜底） | `src/workflow_app/server/api/legacy.py`（薄门面） + `legacy_route_handlers.py` |
| 内联 HTML/CSS 页面模板 | `src/workflow_app/server/presentation/templates/index.html` + `pages.py` |
| DB 连接 | `src/workflow_app/server/infra/db/connection.py` |
| 建表/迁移 | `src/workflow_app/server/infra/db/migrations.py` |
| Agent 发现 + 策略解析主链路 | `src/workflow_app/server/services/policy_analysis.py` |
| 主服务入口实现 | `src/workflow_app/workflow_web_server.py`（兼容薄门面） + `src/workflow_app/server/bootstrap/web_server_runtime.py` |
| 根目录历史运行时模块 | `src/workflow_app/runtime/agent_runtime.py` + `src/workflow_app/runtime/task_agent_runner.py` + `src/workflow_app/runtime/training_center_runtime.py` |
| 根目录历史闭环入口模块 | `src/workflow_app/entry/workflow_entry_cli.py` + `workflow_entry_summary_ops.py` + `workflow_entry_training_ops.py` |
| 根目录历史治理模块 | `src/workflow_app/history/workflow_history_admin.py` |
| 前端训练中心 + 启动混合逻辑 | `src/workflow_app/web_client/training_center_and_bootstrap.js`（域） + `app_shell_and_bootstrap.js`（壳与启动） |
| 前端会话/队列/策略大文件收敛 | `app_status_and_icon_utils.js` + `session_policy_card_helpers.js` + `policy_gate_and_session_core.js` + `workflow_queue_selection_core.js` |
| 前端显式装配 | `src/workflow_app/web_client/bundle_manifest.json` + `load_web_client_bundle_manifest()` |

## 3. 兼容入口
- 保留启动入口不变：
  - `scripts/workflow_web_server.py`
  - `run_workflow.bat`

## 4. 阶段记录与回归

| Phase | 目标 | 结果 | 证据 |
|---|---|---|---|
| Phase 0 | 基线冻结 | pass | `.output/evidence/training-center-uo-20260303-172110/` + `.output/evidence/agent-release-ar-20260303-172110/` |
| Phase 1 | 路由拆分 | pass | `.output/evidence/training-center-uo-20260303-172826/` + `.output/evidence/agent-release-ar-20260303-172826/` |
| Phase 2 | 模板/DB 拆分 | pass | `.output/evidence/training-center-uo-20260303-173355/` + `.output/evidence/agent-release-ar-20260303-173355/` |
| Phase 3 | 服务拆分 | pass | `.output/evidence/training-center-uo-20260303-174013/` + `.output/evidence/agent-release-ar-20260303-174013/` |
| Phase 4 | 前端域拆分 | pass | `.output/evidence/training-center-uo-20260303-174431/` + `.output/evidence/agent-release-ar-20260303-174431/` |
| Phase 5 | 硬门禁瘦身（门面化） | pass | `.output/evidence/training-center-uo-20260303-181739/` + `.output/evidence/agent-release-ar-20260303-181851/` |
| Phase 6 | 二轮反规避拆分 | pass | `.output/evidence/training-center-uo-20260304-085647/` + `.output/evidence/agent-release-ar-20260304-085757/` |
| Phase 7 | 三轮体积收敛 | pass | `.output/evidence/training-center-uo-20260304-092633/` + `.output/evidence/agent-release-ar-20260304-092745/` |
| Phase 8 | 四轮结构契约化 | pass | `.output/evidence/training-center-uo-20260304-133839/` + `.output/evidence/agent-release-ar-20260304-134022/` |
| Phase 9 | 五六轮合并（体积+命名+装配） | pass | `.output/evidence/training-center-uo-20260304-152336/` + `.output/evidence/agent-release-ar-20260304-152506/` |
| Phase 10 | 七轮边界收敛与根目录瘦身 | pass | `.output/evidence/engineering-refactor-er-v7-20260304-174904/` + `.output/evidence/training-center-uo-20260304-174904/` + `.output/evidence/agent-release-ar-20260304-175037/` |
| Phase 11 | 八轮 scripts 目录治理 | pass | `.output/evidence/engineering-refactor-er-v8-20260304-185345/` + `.output/evidence/training-center-uo-20260304-190057/` + `.output/evidence/agent-release-ar-20260304-190231/` |
| Final Regression | 当前轮复核 | pass | `.output/evidence/training-center-uo-20260304-190057/` + `.output/evidence/agent-release-ar-20260304-190231/` |

## 5. 说明
- 本轮保持 API 路径、关键响应字段、错误码语义兼容。
- 本轮未夹带新功能，仅做工程化重构与目录治理。
- 第七轮补充：`server/api` 与 `server/services` 已移除对 `workflow_web_server` 的依赖；`src/workflow_app` 根目录仅保留薄门面与包元信息。
- 第八轮补充：`scripts/` 按 `bin/quality/dev/acceptance` 分层，顶层收敛为稳定入口与兼容 stub（`<= 4`），并新增 `scripts/README.md` 提供旧路径映射。


