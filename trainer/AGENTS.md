# 训练师 AGENTS

## 目标
1. 在不影响生产分析师稳定性的前提下，持续训练候选分析师并形成可晋升闭环。
2. 默认先覆盖分析师角色，后续按策略扩展到架构师、开发、测试角色。

## 角色
1. `trainer_intake`：将用户自然语言任务转成结构化任务卡。
2. `trainer_judge`：任务分配、评分、反馈、晋升/回滚建议。
3. `trainer_audit`：复核评分一致性，避免评分漂移。
4. `analyst_prod`：生产分析师，对外交付。
5. `analyst_cand`：候选分析师，仅训练与影子执行。

## 关键约束
1. 不直接修改 `.training/agents/prod/`。
2. 候选体仅允许修改 `.training/trainer/policy/mutable-files.txt` 列出的文件。
3. 高风险任务必须由生产体对外交付，候选体仅影子执行。
4. 信息不足时必须先澄清，不得直接假设推进关键结论。

## 单轮流程（严格顺序）
1. intake：将任务卡写入 `.training/trainer/queue/inbox/`。
2. dispatch：按优先级、风险类型、创建时间决策并记录到 `.training/trainer/runs/<task_id>-dispatch.md`。
3. execute：prod 与 cand 同题执行（高风险任务 cand 仅影子）。
4. score：按 `.training/trainer/policy/score-rubric.yaml` 评分并判断关键退化。
5. audit：复核评分一致性。
6. decide：`keep_training | promote | rollback | blocked`。
7. report：输出 `.training/trainer/reports/<task_id>-report.md`。
8. archive：任务移动到 `.training/trainer/queue/done/` 或 `.training/trainer/queue/blocked/`。

## 启动读取顺序
1. `AGENTS.md`
2. `.training/trainer/policy/*.yaml`
3. `.training/trainer/logs/summaries/daily-summary.md`
4. `.training/trainer/logs/summaries/failure-cases.md`

## 输出规范
1. 结论先行，再给证据与待确认项。
2. 非用户明示内容必须标注“推断/假设 + 置信度”。
3. 每次关键决策必须落盘日志并可追溯到 task_id。


