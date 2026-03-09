# 训练师工作区说明

## 1. 结构
- `.training/agents/prod/`：生产分析师（只读使用）。
- `.training/agents/candidates/c1/`：候选分析师（训练改进对象）。
- `.training/trainer/policy/`：训练策略与门禁。
- `.training/trainer/queue/`：任务队列（inbox/processing/done/blocked）。
- `.training/trainer/runs/`：每轮分配与执行记录。
- `.training/trainer/reports/`：评分报告。
- `.training/trainer/snapshots/`：晋升前生产快照。
- `.training/trainer/logs/`：全链路事件日志。
- `.training/trainer/roles/`：角色包策略（analyst/architect/developer/tester）。

## 2. 快速开始
1. 在 `.training/trainer/queue/inbox/` 放入任务卡（可复制 `TASK-TEMPLATE.yaml`）。
2. 按 `.training/trainer/policy/*` 执行一轮训练流程。
3. 将分配记录写入 `.training/trainer/runs/<task_id>-dispatch.md`。
4. 将评测结果写入 `.training/trainer/reports/<task_id>-report.md`。
5. 依据关键退化结果执行 keep_training/promote/rollback。

## 3. 注意事项
1. 不改动 `.training/agents/prod/`。
2. 候选体改动只允许触达 `mutable-files.txt`。
3. 高风险任务保持 prod 对外交付。
4. 晋升默认需要人工审批（见 `human-steering.yaml`）。


