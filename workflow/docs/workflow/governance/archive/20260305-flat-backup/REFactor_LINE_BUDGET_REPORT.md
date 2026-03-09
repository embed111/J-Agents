# REFactor_LINE_BUDGET_REPORT

## 1. 硬门禁结论
- `src/workflow_app/workflow_web_server.py`: `8242 -> 11`（pass，`<= 3000`）
- `src/workflow_app/server/api/legacy.py`: `1929 -> 6`（pass，`<= 1000`）
- 判定：`pass_hard_gate`

## 2. Top 15 大文件行数（重构前 vs 重构后）

### 重构前（基线）
| rank | lines | file |
|---|---:|---|
| 1 | 8242 | `src/workflow_app/workflow_web_server.py` |
| 2 | 2513 | `src/workflow_app/server/presentation/templates/index.html` |
| 3 | 2139 | `src/workflow_app/training_center_runtime.py` |
| 4 | 1955 | `src/workflow_app/web_client/03_policy_confirm_and_interactions.js` |
| 5 | 1929 | `src/workflow_app/server/api/legacy.py` |
| 6 | 1688 | `src/workflow_app/server/services/policy_analysis.py` |
| 7 | 1610 | `src/workflow_app/web_client/02_session_and_agent_meta.js` |
| 8 | 1484 | `src/workflow_app/web_client/04_workflow_queue_and_batch.js` |
| 9 | 1471 | `src/workflow_app/web_client/00_app_state_and_utils.js` |
| 10 | 1352 | `src/workflow_app/workflow_entry_cli.py` |
| 11 | 1131 | `src/workflow_app/web_client/01_policy_gate_and_cache.js` |
| 12 | 1096 | `src/workflow_app/web_client/05_training_center_and_bootstrap.js` |
| 13 | 865 | `src/workflow_app/web_client/06_app_shell_and_bootstrap.js` |
| 14 | 498 | `src/workflow_app/task_agent_runner.py` |
| 15 | 457 | `src/workflow_app/workflow_history_admin.py` |

### 重构后（当前）
| rank | lines | file |
|---|---:|---|
| 1 | 8243 | `src/workflow_app/server/bootstrap/web_server_runtime.py` |
| 2 | 2513 | `src/workflow_app/server/presentation/templates/index.html` |
| 3 | 2139 | `src/workflow_app/training_center_runtime.py` |
| 4 | 1955 | `src/workflow_app/web_client/03_policy_confirm_and_interactions.js` |
| 5 | 1929 | `src/workflow_app/server/api/legacy_route_handlers.py` |
| 6 | 1688 | `src/workflow_app/server/services/policy_analysis.py` |
| 7 | 1610 | `src/workflow_app/web_client/02_session_and_agent_meta.js` |
| 8 | 1484 | `src/workflow_app/web_client/04_workflow_queue_and_batch.js` |
| 9 | 1471 | `src/workflow_app/web_client/00_app_state_and_utils.js` |
| 10 | 1352 | `src/workflow_app/workflow_entry_cli.py` |
| 11 | 1131 | `src/workflow_app/web_client/01_policy_gate_and_cache.js` |
| 12 | 1096 | `src/workflow_app/web_client/05_training_center_and_bootstrap.js` |
| 13 | 865 | `src/workflow_app/web_client/06_app_shell_and_bootstrap.js` |
| 14 | 498 | `src/workflow_app/task_agent_runner.py` |
| 15 | 457 | `src/workflow_app/workflow_history_admin.py` |

## 3. 超阈值文件拆分计划（下一阶段）

> 阈值口径：后端建议 `<= 1500`，前端建议 `<= 1200`，入口门面建议 `<= 500`。

1. `src/workflow_app/server/bootstrap/web_server_runtime.py`（8243，后端超阈值）
   - 计划：
     - 拆为 `bootstrap/app_startup.py`（启动/参数）；
     - `services/session_orchestration.py`（会话与任务编排）；
     - `services/training_workflow.py`（分析/训练编排）；
     - `infra/audit_runtime.py`（审计写入与事件桥接）。
   - 预计降幅：`-5000 ~ -6200` 行（目标 `< 3000`）。

2. `src/workflow_app/server/api/legacy_route_handlers.py`（1929，后端超阈值）
   - 计划：
     - 按域拆为 `legacy_chat_handlers.py`、`legacy_task_handlers.py`、`legacy_admin_handlers.py`。
   - 预计降幅：单文件降至 `< 900`。

3. `src/workflow_app/training_center_runtime.py`（2139，后端超阈值）
   - 计划：
     - 拆为 `services/training_plan_service.py`、`services/release_management_service.py`、`infra/db/repositories/training_repo.py`。
   - 预计降幅：`-900 ~ -1200` 行。

4. `src/workflow_app/web_client/03_policy_confirm_and_interactions.js`（1955，前端超阈值）
   - 计划：
     - 拆为 `domains/session/policy_confirm_render.js` 与 `domains/session/policy_confirm_actions.js`。
   - 预计降幅：单文件降至 `< 1000`。

5. `src/workflow_app/server/services/policy_analysis.py`（1688，后端超阈值）
   - 计划：
     - 拆为 `services/agent_discovery_service.py`、`services/policy_payload_builder.py`。
   - 预计降幅：主文件降至 `< 1200`。

## 4. 二轮反规避结果（2026-03-04）
- `src/workflow_app/server/bootstrap/web_server_runtime.py`: `2248`（pass，`<= 3000`）
- `src/workflow_app/server/api/legacy_route_handlers.py`: `15`（pass，`<= 1000`）
- `src/workflow_app/workflow_web_server.py`: `11`（兼容薄门面，pass）
- `src/workflow_app/server/api/legacy.py`: `6`（兼容薄门面，pass）
- 证据：`.output/evidence/engineering-refactor-er-v2-20260304-090036/metrics/hard_gate_v2_counts.txt`

## 5. 三轮体积收敛结果（2026-03-04）
- `src/workflow_app/training_center_runtime.py`: `497`（pass，`<= 1500`）
- `src/workflow_app/server/services/policy_analysis.py`: `418`（pass，`<= 1200`）
- `src/workflow_app/server/api/legacy_task_handlers.py`: `775`（pass，`<= 900`）
- `src/workflow_app/server/bootstrap/web_server_runtime.py`: `2248`（回归 pass，`<= 3000`）
- `src/workflow_app/server/api/legacy_route_handlers.py`: `15`（回归 pass，`<= 1000`）
- 证据：`.output/evidence/engineering-refactor-er-v3-20260304-093148/metrics/hard_gate_v3_counts.txt`

## 6. 四轮结构契约化结果（2026-03-04）
- README 契约化：
  - `src/workflow_app/server/README.md`
  - `src/workflow_app/server/api/README.md`
  - `src/workflow_app/server/services/README.md`
  - `src/workflow_app/server/infra/README.md`
  - `src/workflow_app/server/presentation/README.md`
  - `src/workflow_app/server/bootstrap/README.md`
  - 契约检查结果：`pass`
- 原型文案清理：`src/workflow_app/**/*.py` 与 `src/workflow_app/web_client/**/*.js` 中 `Phase0/Phase 0/Phase1/Phase 1` 扫描结果 `0`。
- 体量回归：
  - `src/workflow_app/server/bootstrap/web_server_runtime.py`: `1985`（pass，`<= 3000`）
  - `src/workflow_app/server/api/legacy_route_handlers.py`: `10`（pass，`<= 1000`）
- 验收回归：UO/AR `exit code 0`。
- 证据目录：`.output/evidence/engineering-refactor-er-v4-20260304-133816/`

## 7. 五六轮合并结果（2026-03-04）
- 大文件门禁（目标文件）：
  - `src/workflow_app/server/bootstrap/web_server_runtime.py`: `1237`（pass，`<= 1500`）
  - `src/workflow_app/server/services/training_workflow.py`: `725`（pass，`<= 900`）
  - `src/workflow_app/workflow_entry_cli.py`: `881`（pass，`<= 900`）
  - `src/workflow_app/server/presentation/templates/index.html`: `430`（pass，`<= 1200`）
  - `src/workflow_app/web_client/policy_confirm_and_interactions.js`: `931`（pass，`<= 1200`）
  - `src/workflow_app/web_client/session_and_agent_meta.js`: `1074`（pass，`<= 1200`）
  - `src/workflow_app/web_client/workflow_queue_and_batch.js`: `1011`（pass，`<= 1200`）
  - `src/workflow_app/web_client/app_state_and_utils.js`: `1059`（pass，`<= 1200`）
- 防回流门禁：
  - `src/workflow_app/server/api/legacy_route_handlers.py`: `10`（pass，`<= 1000`）
  - `src/workflow_app/server/api/legacy_task_handlers.py`: `767`（pass，`<= 1000`）
  - 新增源码文件 `>1500`：`无`
- 命名与装配门禁：
  - `web_client` 去序号命名：`pass`（无 `^\d{2}_.*\.js$`）
  - 前端装配：从“按文件名排序”迁移为 `bundle_manifest.json` 显式清单。
  - `/static/workflow-web-client.js` 保持兼容路径不变，新增 `/static/workflow-web.css` 承载外置样式。
- 验收回归：UO/AR `exit code 0`。
- 证据目录：`.output/evidence/engineering-refactor-er-v56-20260304-152938/`

## 8. 七轮边界收敛与根目录瘦身结果（2026-03-04）
- 依赖边界：
  - `server/api/*` 对 `workflow_app.workflow_web_server` 依赖：`0`（pass）。
  - `server/services/*` 对 `workflow_app.workflow_web_server` 依赖：`0`（pass）。
  - 证据：`.output/evidence/engineering-refactor-er-v7-20260304-174904/metrics/dependency_boundary_v7.txt`
- bootstrap 反向依赖：
  - `web_server_runtime.py` 不再直接导入根目录历史模块（`...training_center_runtime` / `...workflow_entry_cli` / `...workflow_history_admin`）。
  - 证据：`.output/evidence/engineering-refactor-er-v7-20260304-174904/metrics/bootstrap_reverse_dependency_v7.txt`
- 根目录瘦身（`src/workflow_app`）：
  - 根目录 `.py`：`2` 个（`workflow_web_server.py`、`__init__.py`），满足 `<= 4`。
  - 非 `workflow_web_server.py` 根文件：`__init__.py` 为 `2` 行，满足 `<= 40` 且无业务实现。
  - 根目录无新增 `> 200` 行源码文件。
  - 证据：`.output/evidence/engineering-refactor-er-v7-20260304-174904/metrics/root_layout_v7.json`
- 关键体量快照（当前）：
  - `src/workflow_app/workflow_web_server.py`: `11`
  - `src/workflow_app/server/api/legacy.py`: `6`
  - `src/workflow_app/server/bootstrap/web_server_runtime.py`: `1241`
  - `src/workflow_app/server/services/policy_analysis.py`: `419`
  - `src/workflow_app/runtime/training_center_runtime.py`: `501`
  - `src/workflow_app/entry/workflow_entry_cli.py`: `877`
- 回归门禁：
  - `compileall`、`check-module-readme-contract`、`check-prototype-text`、UO、AR 均 `exit code 0`。
  - 证据：`.output/evidence/engineering-refactor-er-v7-20260304-174904/metrics/hard_gate_v7_counts.txt`

## 9. 八轮 scripts 目录治理结果（2026-03-04）
- scripts 分层：
  - `scripts/bin/`: 入口 Python 脚本（`workflow_web_server.py`、`workflow_entry_cli.py` 及其他运行入口）。
  - `scripts/quality/`: `check-*` 与质量门禁脚本。
  - `scripts/dev/`: 启动与开发辅助脚本（PowerShell 等）。
  - `scripts/acceptance/`: 验收脚本保持不变。
- 顶层瘦身：
  - `scripts/` 顶层文件数：`4`（`README.md`、`launch_workflow.ps1`、`workflow_web_server.py`、`workflow_entry_cli.py`）。
  - 满足门禁 `<= 4`。
- 分类门禁：
  - `check-*.py` 均在 `scripts/quality/`。
  - 启动 `.ps1` 均在 `scripts/dev/`，顶层仅保留兼容 `launch_workflow.ps1` stub。
- 兼容抽测（历史命令）：
  - 抽测 `5/5` 成功（含旧路径 `scripts/workflow_web_server.py` 与 `scripts/workflow_entry_cli.py`）。
  - 证据：`.output/evidence/engineering-refactor-er-v8-20260304-185345/scripts_compatibility_v8.md`
- 回归门禁：
  - `compileall`、quality 检查、UO、AR 均 `exit code 0`。
  - 证据：`.output/evidence/engineering-refactor-er-v8-20260304-185345/hard_gate_v8_counts.txt`
