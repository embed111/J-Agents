# 工作区状态变更日志

## 2026-02-24
1. 新增 `workspace_state/` 目录与重启恢复机制文件：
   - `workspace_state/core/workspace-state-overview.md`
   - `workspace_state/core/startup-checklist.md`
   - `workspace_state/core/session-snapshot.md`
   - `workspace_state/logs/state-change-log.md`
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
   - `workspace_state/core/startup-checklist.md` 技能路径修正为 `./.codex/skills/`。
   - 新增 `skills/local-skills-overview.md`，记录本地技能目录与触发策略。

## 2026-02-25
1. 新增“能力扩展评估”机制，要求每轮分析默认判断是否需要新增 skill 或 agent 角色。
2. `AGENTS.md` 标准工作流新增步骤：
   - 在文档交付前完成“新增 skill/agent 角色”的触发判断、成本收益与采用结论记录。
3. `AGENTS.md` 质量检查清单新增自检项：
   - 必须明确“采用/暂不采用 + 理由”。
4. `workspace_state/core/startup-checklist.md` 执行前自检新增：
   - 是否完成能力扩展评估（skill/agent）。
5. `skills/local-skills-overview.md` 新增：
   - 能力扩展评估默认启用规则。
   - 新增 skill 与新增 agent 角色的触发信号与输出格式。
6. 新增“偏好归属隔离”机制，防止训练师/外部角色偏好误写入用户档案：
   - `AGENTS.md` 新增 owner 与 external 的记录边界规则。
   - `workspace_state/core/startup-checklist.md` 新增“偏好归属检查”自检项。
   - 新增 `workspace_state/observations/external-input-observations.md` 作为外部偏好落盘文件。
   - 重启读取顺序新增外部输入观察文件（`AGENTS.md` 与 `workspace-state-overview.md` 同步）。
7. 新增 `workspace_state/policies/preference-attribution-policy.md`：
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
   - 能力：基于工作量阈值对 `workspace_state/core/session-snapshot.md` 进行归档压缩，并维护历史索引引用。
2. 更新技能目录索引：
   - `skills/local-skills-overview.md` 新增该技能与适用场景说明。
3. 更新顶层约束文件：
   - `AGENTS.md` 的“工作区本地技能”新增该技能，纳入默认可用能力范围。
4. 变更原因：
   - `session-snapshot.md` 体量持续增长，需引入可复用的归档治理流程，降低启动读取成本与维护噪音。

## 2026-03-02
1. 新增提示词专用目录治理：
   - 新增 `docs/workflow/prompts/`，用于集中存放 `执行提示词-*.md`。
   - 将 `docs/workflow/` 根目录下历史执行提示词迁移至该目录。
2. 新增滚动保留机制：
   - 新增脚本 `scripts/trim-workflow-prompts.ps1`。
   - 默认规则：每次新增后仅保留最近 7 轮提示词。
3. 执行工作区同步策略更新：
   - `../workflow/docs/workflow/prompts/` 同步执行提示词目录结构与文件。
4. 变更原因：
   - 降低目录噪音，提升提示词资产检索效率与跨工作区分发稳定性。

## 2026-03-03
1. 新增工作区档案归档脚本：
   - `scripts/archive-analyst-state.ps1`
   - 能力：对 `workspace_state/core/session-snapshot.md` 与 `user_profile/logs/thinking-patterns-change-log.md` 执行“先备份、再归档、后索引”的无损压缩。
2. 新增归档目录与索引文件：
   - `workspace_state/logs/session-history/`
   - `workspace_state/logs/session-history-index.md`
   - `user_profile/logs/change-log-history/`
   - `user_profile/logs/change-log-history-index.md`
3. 启动检查清单更新：
   - 增加归档索引可读性检查与“体量增长后执行归档脚本”的自检项。
4. 首次归档执行结果：
   - `session-snapshot.md`：1492 行 -> 241 行（历史 80 块归档）。
   - `thinking-patterns-change-log.md`：1089 行 -> 193 行（历史 71 块归档）。
5. 变更原因：
   - 在不丢失历史事实的前提下，降低启动读取成本与维护噪音。
6. 新增长期偏好精简门禁：
   - 新增 `scripts/check-long-term-preference-cap.ps1`（默认上限 200 行）。
   - 新增 `user_profile/core/thinking-patterns-short-term.md` 与 `user_profile/governance/preference-review-log.md`。
   - 当长期偏好超限时，启动评审并将非核心条目降级到短期偏好池。

## 2026-03-06
1. 完成状态目录结构重排：
   - `workspace_state/` 顶层仅保留 `目录导读.md`；
   - 状态文件下沉到 `core/`、`policies/`、`observations/`、`logs/`。
2. 完成偏好目录结构重排：
   - `user_profile/` 顶层仅保留 `目录导读.md`；
   - 偏好文件下沉到 `core/`、`governance/`、`logs/`。
3. 新增动态维护脚本：
   - `scripts/maintain-state-health.ps1`
   - 能力：按行数/体积/归档间隔阈值巡检，并可联动执行归档。
4. 归档脚本路径修正：
   - `scripts/archive-analyst-state.ps1` 的归档输出目录调整为：
     1) `workspace_state/logs/session-history/`
     2) `user_profile/logs/change-log-history/`
5. 机制文件同步更新：
   - `AGENTS.md`
   - `workspace_state/core/startup-checklist.md`
   - `workspace_state/core/workspace-state-overview.md`
   - `workspace_state/目录导读.md`
   - `user_profile/目录导读.md`
   - 相关本地技能 `SKILL.md`
6. 动态归档执行结果：
   - `workspace_state/core/session-snapshot.md`：1081 -> 447 行。
   - `user_profile/logs/thinking-patterns-change-log.md`：650 -> 180 行。
7. 新增通用目录治理技能：
   - `./.codex/skills/directory-maintenance-governor/SKILL.md`
   - 能力：将“顶层单导读 + 模块化落位 + 阈值归档”推广到任意目录整理场景。
8. 新增通用目录巡检脚本：
   - `scripts/maintain-directory-health.ps1`
   - 能力：对任意目录执行单导读门禁检查、阈值巡检，并按指定文件执行归档。
9. 技能与规则接入更新：
   - `AGENTS.md` 本地技能清单新增 `directory-maintenance-governor`。
   - `skills/local-skills-overview.md` 新增该技能说明。
   - `workspace_state/core/startup-checklist.md` 新增“目录整理前通用门禁检查”自检项。

## 2026-03-10
1. 展示/交互需求协作规则升级：
   - `AGENTS.md` 标准工作流新增“原型预览”步骤。
   - 明确：对已有系统的展示/交互类需求，需求确认后需先提供与现有设计风格一致的原型，再进行跨工作区交付。
2. 质量门禁同步更新：
   - `AGENTS.md` 质量检查清单新增“原型已确认”自检项。
   - `workspace_state/core/startup-checklist.md` 执行前自检新增“展示类需求先原型预览”检查项。
3. 变更原因：
   - 用户明确要求“需求确认后先确认原型图”，且原型必须保持现有产品设计风格。

