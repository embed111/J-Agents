# 本地技能总览

- 最后更新: 2026-03-06
- 加载目录: `./.codex/skills/`
- 目标: 统一记录当前工作区可用本地技能与触发建议。

## 可用技能
1. `method-selection-orchestrator`
   - 路径: `./.codex/skills/method-selection-orchestrator/SKILL.md`
   - 适用: 复杂/模糊问题的方法选择与组合。
2. `session-state-maintainer`
   - 路径: `./.codex/skills/session-state-maintainer/SKILL.md`
   - 适用: 会话启动恢复、回合结束状态回写。
3. `proactive-practice-advisor`
   - 路径: `./.codex/skills/proactive-practice-advisor/SKILL.md`
   - 适用: 在完成主任务后给出高杠杆改进建议。
4. `snapshot-archive-governor`
   - 路径: `./.codex/skills/snapshot-archive-governor/SKILL.md`
   - 适用: 会话快照过长时按工作量触发归档，并维护顶层摘要与历史索引引用。
5. `requirement-convergence-gate`
   - 路径: `./.codex/skills/requirement-convergence-gate/SKILL.md`
   - 适用: 在需求尚未收敛时阻止提前进入设计，按需提问（0~3）并给出收敛门禁结论。
6. `preference-cap-review-governor`
   - 路径: `./.codex/skills/preference-cap-review-governor/SKILL.md`
   - 适用: 当长期偏好主档超出 200 行时，执行“保留长期核心 + 降级短期偏好”的评审机制。
7. `requirements-doc-structure-governor`
   - 路径: `./.codex/skills/requirements-doc-structure-governor/SKILL.md`
   - 适用: 当需求文档目录混乱、索引漂移或出现过期内容时，执行目录收敛、状态分级、归档治理，并对新文档自动落位到标准模块目录。
8. `directory-maintenance-governor`
   - 路径: `./.codex/skills/directory-maintenance-governor/SKILL.md`
   - 适用: 当任意目录需要“顶层单导读 + 模块化落位 + 阈值归档”治理时，执行通用目录整理与动态维护。

## 使用策略
1. 命中技能适用场景时优先使用，避免重复造轮子。
2. 仅按任务需要读取技能文件，控制上下文体积。
3. 若技能文件缺失或不可读，记录问题并按兜底流程继续执行。
4. 需求讨论场景默认先触发 `requirement-convergence-gate` 并完成内部收敛自检，未到 `start_design` 不进入文档细化与任务拆解。

## 能力扩展评估（默认启用）
1. 每轮分析增加“能力扩展评估”小节，至少回答三件事：
   - 是否需要新增 skill。
   - 是否需要新增 agent 角色。
   - 若暂不新增，当前兜底方案是什么。
2. 新增 skill 触发信号（满足任一即可进入候选）：
   - 同类手工分析步骤重复 >= 3 次。
   - 已有技能无法覆盖关键决策步骤。
   - 频繁出现“同类问题重复解释”的返工。
3. 新增 agent 角色触发信号（满足任一即可进入候选）：
   - 单角色长期混合承担 2 类以上专业职责并出现冲突。
   - 信息架构、需求分析、工程实现之间反复拉扯导致决策变慢。
   - 已出现“可见性不足/信息过载”并存，且靠提示词难稳定解决。
4. 候选结论输出格式：
   - 结论：新增/暂不新增。
   - 理由：基于事实与约束。
   - 代价：新增维护成本与协作复杂度。
   - 验证：下一轮如何验证这次判断是否正确。

## 技能质量门禁（新增）
1. 所有本地技能 `SKILL.md` 必须包含 `## Examples` 段。
2. 示例至少 1 个，建议 2~3 个，覆盖：
   - 触发条件；
   - 执行动作；
   - 预期输出。
3. 新增或修改技能后，建议执行：
   - `powershell -ExecutionPolicy Bypass -File scripts/check-skill-examples.ps1`
