# 任务产物目录结构说明

该文件由 workflow 自动维护。
启动程序时，或在设置中修改任务产物路径后，系统都会生成或刷新本说明文件。

## 当前配置
- 任务产物路径: D:/code/AI/J-Agents/.output-test
- 任务目录根: D:/code/AI/J-Agents/.output-test/tasks
- 根目录说明文件: TASKS_STRUCTURE.md

## 目录结构约定
- `<任务产物路径>/tasks/<ticket_id>/task.json`: 任务图头、调度状态与依赖边元数据。
- `<任务产物路径>/tasks/<ticket_id>/nodes/<node_id>.json`: 单任务节点明细。
- `<任务产物路径>/tasks/<ticket_id>/runs/<run_id>/...`: 完整提示词、stdout/stderr、结果与事件链路。
- `<任务产物路径>/tasks/<ticket_id>/artifacts/<node_id>/output/...`: 当前节点自留产物。
- `<任务产物路径>/tasks/<ticket_id>/artifacts/<node_id>/delivery/<receiver_agent_id>/...`: 指定交付对象时的交付副本。
- `<任务产物路径>/delivery/<agent_name>/<task_name>/...`: 面向 agent 的顶层交付收件箱投影，系统会在这里写入最终交付件与交付标记。
- `<任务产物路径>/tasks/<ticket_id>/TASK_STRUCTURE.md`: 单任务目录结构说明。

## 维护规则
- workflow 仅保留运行中的内存调度工作集，不在自身目录持久化任务明文。
- 任务图、任务详情、执行链路与产物都应从本目录动态加载。
- 每次真实执行完成并落盘后，系统会同步刷新根目录与单任务目录说明文件。
