# 工作区状态变更日志

## 2026-02-24
1. 新增 `workspace_state/` 目录与重启恢复机制文件：
   - `workspace_state/workspace-state-overview.md`
   - `workspace_state/startup-checklist.md`
   - `workspace_state/session-snapshot.md`
   - `workspace_state/state-change-log.md`
2. 明确启动读取顺序和每轮维护规则。
3. 目标从“依赖对话上下文”升级为“依赖本地可追溯文档状态”。
4. 启动读取顺序新增 `skills/local-skills-overview.md`，纳入本地技能恢复。
5. 新增 3 个本地技能目录并通过校验：
   - `skills/method-selection-orchestrator/`
   - `skills/session-state-maintainer/`
   - `skills/proactive-practice-advisor/`
6. 方法库从 3 种扩展到 6 种，并补充新增方法对应案例。
7. 新增“工作区私有技能作用域”机制：
   - 新增工作区私有目录 `./.codex-home/skills/`。
   - 新增本地启动脚本 `start-codex-local.ps1` 与 `start-codex-local.cmd`。
   - `startup-checklist` 增加“优先使用本地启动脚本”步骤，避免回退到全局 `~/.codex/skills`。
8. 自定义技能从全局目录移回工作区私有目录，全局仅保留 `.system`。
9. 根据用户确认切换到工作区原生技能路径：
   - 将自定义技能迁移到 `./.codex/skill/`。
   - 删除 `start-codex-local.ps1` 与 `start-codex-local.cmd`。
   - 不再使用 `./.codex-home/skills/` 作为默认加载路径。
10. 本轮完成路径基线纠偏并补齐缺失索引：
   - `workspace_state/startup-checklist.md` 技能路径修正为 `./.codex/skills/`。
   - 新增 `skills/local-skills-overview.md`，记录本地技能目录与触发策略。

## 2026-02-25
1. 新增“能力扩展评估”机制，要求每轮分析默认判断是否需要新增 skill 或 agent 角色。
2. `AGENTS.md` 标准工作流新增步骤：
   - 在文档交付前完成“新增 skill/agent 角色”的触发判断、成本收益与采用结论记录。
3. `AGENTS.md` 质量检查清单新增自检项：
   - 必须明确“采用/暂不采用 + 理由”。
4. `workspace_state/startup-checklist.md` 执行前自检新增：
   - 是否完成能力扩展评估（skill/agent）。
5. `skills/local-skills-overview.md` 新增：
   - 能力扩展评估默认启用规则。
   - 新增 skill 与新增 agent 角色的触发信号与输出格式。
6. 新增“偏好归属隔离”机制，防止训练师/外部角色偏好误写入用户档案：
   - `AGENTS.md` 新增 owner 与 external 的记录边界规则。
   - `workspace_state/startup-checklist.md` 新增“偏好归属检查”自检项。
   - 新增 `workspace_state/external-input-observations.md` 作为外部偏好落盘文件。
   - 重启读取顺序新增外部输入观察文件（`AGENTS.md` 与 `workspace-state-overview.md` 同步）。
7. 新增 `workspace_state/preference-attribution-policy.md`：
   - 明确 fail-closed、来源标签、写入矩阵、写入前检查与污染回滚流程。
   - 启动读取顺序与检查清单同步纳入该策略文件。
8. 偏好治理升级为“二阶段提交”：
   - 未经 owner 明确确认，偏好仅允许暂存，不允许写入 `user_profile/`。
   - `AGENTS.md` 与 `startup-checklist.md` 已同步新增对应约束。
9. 新增 `AGENTS.md` 顶部运行开关 `MEMORY_UPDATE_SWITCH`：
   - `ON`: 允许自动更新状态/偏好档案。
   - `OFF`: 禁止自动更新（仅在用户明确指令时更新）。
   - `startup-checklist` 与 `preference-attribution-policy` 已同步接入该开关约束。
10. 新增“跨工作区需求文档一致性校验”流程：
   - `startup-checklist` 执行前自检新增双工作区 `docs/workflow` 文件集与哈希一致性检查。
   - 目标是避免分析工作区与执行工作区需求版本分叉。

## 2026-02-26
1. 新增本地技能 `snapshot-archive-governor`：
   - 路径：`./.codex/skills/snapshot-archive-governor/SKILL.md`
   - 能力：基于工作量阈值对 `workspace_state/session-snapshot.md` 进行归档压缩，并维护历史索引引用。
2. 更新技能目录索引：
   - `skills/local-skills-overview.md` 新增该技能与适用场景说明。
3. 更新顶层约束文件：
   - `AGENTS.md` 的“工作区本地技能”新增该技能，纳入默认可用能力范围。
4. 变更原因：
   - `session-snapshot.md` 体量持续增长，需引入可复用的归档治理流程，降低启动读取成本与维护噪音。
