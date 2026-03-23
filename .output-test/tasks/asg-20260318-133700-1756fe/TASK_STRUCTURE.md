# 单任务目录结构说明

该文件由 workflow 自动维护。

## 当前任务
- ticket_id: asg-20260318-133700-1756fe
- 任务目录: D:/code/AI/J-Agents/.output-test/tasks/asg-20260318-133700-1756fe
- graph_name: 任务中心原型测试图
- source_workflow: assignment-prototype-test-data
- scheduler_state: running
- active_nodes: 20
- deleted_nodes: 0
- runs: 0

## 目录结构约定
- `task.json`: 任务图头、依赖边与调度元数据。
- `nodes/`: 单任务节点明细，逻辑删除节点也在此保留删除标记。
- `runs/<run_id>/`: 完整提示词、stdout/stderr、result 与事件链路。
- `artifacts/<node_id>/output/`: 节点自留产物。
- `artifacts/<node_id>/delivery/<receiver_agent_id>/`: 指定交付对象时的交付副本。
- `TASK_STRUCTURE.md`: 本目录结构说明。
