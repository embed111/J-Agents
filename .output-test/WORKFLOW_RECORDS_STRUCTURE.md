# 工作记录目录结构说明

该文件由 workflow 自动维护。
任务中心之外的会话、分析、运行、审计和系统级工作记录统一落在本目录契约中。

## 当前配置
- 任务产物路径: D:/code/AI/J-Agents/.output-test
- 工作记录根目录: D:/code/AI/J-Agents/.output-test/records
- 顶层入口索引: D:/code/AI/J-Agents/.output-test/records/index.json
- 会话索引: D:/code/AI/J-Agents/.output-test/records/sessions/index.json
- 分析索引: D:/code/AI/J-Agents/.output-test/records/analysis/index.json
- 运行索引: D:/code/AI/J-Agents/.output-test/records/runs/index.json
- SQLite 辅助索引: D:/code/AI/J-Agents/.output-test/.index/index.db

## 稳定目录契约
- `<任务产物路径>/tasks/<ticket_id>/...`: 任务中心任务图、节点、执行链路与产物。
- `<任务产物路径>/records/sessions/<session_id>/session.json`: 会话头信息与索引字段。
- `<任务产物路径>/records/sessions/<session_id>/messages.jsonl`: 会话消息与分析状态。
- `<任务产物路径>/records/analysis/<analysis_id>/analysis.json`: 分析任务主记录。
- `<任务产物路径>/records/analysis/<analysis_id>/workflow.json`: 工作记录与训练编排状态。
- `<任务产物路径>/records/analysis/<analysis_id>/runs/<analysis_run_id>.json`: 单次分析运行记录。
- `<任务产物路径>/records/analysis/<analysis_id>/workflow-events.jsonl`: 分析/计划/执行链路事件。
- `<任务产物路径>/records/runs/<task_id>/run.json`: 会话任务运行头信息。
- `<任务产物路径>/records/runs/<task_id>/{stdout.txt,stderr.txt,trace.json,events.log,summary.md}`: 会话任务执行证据。
- `<任务产物路径>/records/audit/message-delete.jsonl`: 消息删除审计。
- `<任务产物路径>/records/audit/policy-confirmation.jsonl`: 策略确认审计。
- `<任务产物路径>/records/audit/policy-patch-tasks/*.json`: 策略补丁任务记录。
- `<任务产物路径>/records/system/workflow-events.jsonl`: 全局工作事件留痕。
- `<任务产物路径>/.index/index.db`: 只读辅助索引层，丢失后可由文件重建。

## 使用规则
- `workflow/state/`、`workflow/.runtime/state/`、`workflow/logs/` 不再持久化用户工作记录明文。
- 页面刷新或服务重启后，工作记录页签应从本目录动态加载。
- 其他 agent 做工作记录分析时，先看本文件，再看顶层入口索引和 SQLite 辅助索引契约。
