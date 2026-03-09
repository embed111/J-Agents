# 训练中心统一入口与训练运营验收记录（2026-03-02 19:12）

## 1. 变更摘要（文件列表 + 目的）
- `scripts/workflow_web_server.py`
  - 新增训练中心数据与业务函数：agent 资产同步、Git 只读版本历史、trainer 字符串匹配、手动/自动来源计划入队、队列展示、相似计划标注、移除、执行、调度、run 查询、审计写入。
  - 新增 API：
    - `GET /api/training/agents`
    - `GET /api/training/agents/{agent_id}/releases`
    - `POST /api/training/plans/manual`
    - `POST /api/training/plans/auto`（用于 manual/auto 并行验收）
    - `GET /api/training/queue`
    - `POST /api/training/queue/{queue_task_id}/remove`
    - `POST /api/training/queue/{queue_task_id}/execute`
    - `POST /api/training/queue/dispatch-next`
    - `GET /api/training/runs/{run_id}`
    - `GET /api/training/trainers?query=...`
  - 新增前端 HTML/CSS：`训练中心` 一级入口与两个子模块（`Agent资产与版本` / `训练运营`）。
- `scripts/workflow_web_client.js`
  - 新增训练中心状态管理、模块切换、agent 列表/详情渲染、版本历史渲染、trainer 搜索、计划入队、队列渲染、执行与移除操作。
  - 新增门禁联动：`agent_search_root` 不可用时训练中心功能禁用。

## 2. AC 清单结果（AC-ID | pass/fail | evidence）
- `AC-UO-01 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> tc_agents(items 含 agent_name/current_version/core_capabilities); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> agent_registry_sample; 代码: scripts/workflow_web_server.py, scripts/workflow_web_client.js`
- `AC-UO-02 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> tc_releases; DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> agent_release_history_sample; 代码: scripts/workflow_web_server.py(list_training_agent_releases), scripts/workflow_web_client.js(renderTrainingCenterReleases)`
- `AC-UO-03 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/extra.json -> git_releases(releases 含 version_label/tag、commit_ref、change_summary); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> agent_release_history_sample; 代码: scripts/workflow_web_server.py(_run_git_readonly/_parse_git_release_rows)`
- `AC-UO-04 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> tc_agents.items(status_tags 含 git_unavailable, git_available=false); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> agent_registry_sample.status_tags_json; 代码: scripts/workflow_web_server.py(sync_training_agent_registry)`
- `AC-UO-05 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> manual1(source=manual, queue_task_id/plan_id 创建成功); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_plan(source=manual), training_queue; 代码: scripts/workflow_web_server.py(create_training_plan_and_enqueue), scripts/workflow_web_client.js(enqueueTrainingCenterPlan)`
- `AC-UO-06 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/error-cases.json -> priority_missing(status=400,error=优先级必填,code=priority_required) + priority_invalid(status=400,code=priority_invalid); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_plan.priority; 代码: scripts/workflow_web_server.py(normalize_training_priority)`
- `AC-UO-07 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> queue_before_dispatch 顺序为 P0/P1/P2/P3, dispatch_next 选中 P0; DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_queue; 代码: scripts/workflow_web_server.py(list_training_queue_items/dispatch_next_training_queue_item)`
- `AC-UO-08 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> manual2(similar_flag=true,similar_plan_ids 非空); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_plan.similar_flag + training_audit_log.action=mark_similar; 代码: scripts/workflow_web_server.py(_detect_similar_training_plans/training_plan_similarity_hit)`
- `AC-UO-09 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> remove_manual1(无二次确认 API 直接移除, 返回 risk_tip); DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_queue.status=removed + training_audit_log.action=remove + conversation_events_training_center.action=remove; 代码: scripts/workflow_web_server.py(remove_training_queue_item), scripts/workflow_web_client.js(renderTrainingCenterQueue 移除按钮风险提示)`
- `AC-UO-10 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> manual1/manual2/source=manual + auto1/source=auto_analysis, queue_before_dispatch 同队列可见; DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_plan.source 同时存在 manual/auto_analysis; 代码: scripts/workflow_web_server.py(create_training_plan_and_enqueue + /api/training/plans/auto)`
- `AC-UO-11 | pass | 接口: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/responses.json -> manual/auto 计划创建与执行请求均无 session_id 仍成功; DB: .runtime/logs/runs/training-center-ac-evidence-20260302-190658/db-snapshot.json -> training_plan/training_queue/training_run 链路不依赖会话字段; 代码: scripts/workflow_web_server.py(create_training_plan_and_enqueue/execute_training_queue_item)`

## 3. 风险与未完成项
- Git 版本历史仅实现只读，未实现打 tag/回滚/发布写入（符合边界约束）。
- trainer 匹配为字符串匹配，未实现标签画像/语义匹配（符合边界约束）。
- 训练执行为骨架流程（状态流转 + 审计 + run_ref 回写），未接入真实 trainer 执行器（符合边界约束）。

## 4. 下一步建议（最多 3 条）
1. 将 `POST /api/training/plans/auto` 的来源改为分析模块真实产出（替换当前验收样例入口）。
2. 为队列调度增加幂等键与并发锁，补充并发调度回归用例（避免重复 dispatch）。
3. 增加训练中心前端 E2E 脚本（覆盖相似标注、移除风险提示、trainer 未匹配执行拦截）。

