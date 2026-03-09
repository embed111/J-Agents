# 工作区状态概述

- 最后更新: 2026-03-06
- 目标: 在重启工作区后，用最小读取成本恢复一致的工作状态。

## 启动时读取顺序
1. `AGENTS.md`
2. `workspace_state/目录导读.md`
3. `user_profile/目录导读.md`
4. `workspace_state/core/startup-checklist.md`
5. `workspace_state/core/session-snapshot.md`
6. `workspace_state/policies/preference-attribution-policy.md`
7. `workspace_state/observations/external-input-observations.md`
8. `user_profile/core/thinking-patterns-overview.md`
9. `knowledge_base/analysis-methods-overview.md`
10. `skills/local-skills-overview.md`

## 当前状态快照
1. 已建立用户思维模式档案体系（`user_profile/`）。
2. 已建立思维分析方法与案例库（`knowledge_base/`）。
3. 已建立重启恢复机制（`workspace_state/`）。
4. 已建立工作区本地技能库（`skills/`）。
5. 自定义技能作用域已隔离到工作区原生路径：`./.codex/skills/`。
6. 已启用“能力扩展评估”默认门禁：每轮分析前检查是否需要新增 skill 或 agent 角色。
7. 已启用“偏好归属隔离”机制：用户偏好与训练师/外部角色偏好分开记录。
8. 已启用档案更新开关：`MEMORY_UPDATE_SWITCH` 控制是否自动写入状态/偏好档案。
9. 已启用双档案归档机制：`session-snapshot.md` 与 `thinking-patterns-change-log.md` 支持历史归档与索引追溯。
10. 已启用长期偏好行数门禁：长期偏好主档单文件超过 200 行时触发评审并降级到短期偏好池。
11. 已启用目录顶层治理：`workspace_state/` 与 `user_profile/` 顶层均仅保留一个 `目录导读.md` 文件。
12. 已启用动态维护脚本：按阈值自动触发归档并更新索引。
13. 已启用通用目录治理能力：可对任意目录执行“单导读 + 模块化 + 动态归档”。

## 维护规则
1. 每轮对话后更新 `workspace_state/core/session-snapshot.md`。
2. 若流程或目录变更，更新 `workspace_state/core/startup-checklist.md`。
3. 每次机制调整后，写入 `workspace_state/logs/state-change-log.md`。
4. 需求分析输出默认包含“能力扩展评估（新增 skill/agent 角色）”结论。
5. 档案自动更新前先检查 `MEMORY_UPDATE_SWITCH`，OFF 时仅按用户明确指令更新。
6. 归档仅做“移动与索引”，不删除历史事实；历史块分别写入：
   - `workspace_state/logs/session-history/`
   - `user_profile/logs/change-log-history/`
7. 长期偏好治理采用“主档精简 + 短期池缓冲”：
   - 主档：`thinking-patterns-global/domain-*/overview.md`
   - 短期池：`user_profile/core/thinking-patterns-short-term.md`
8. 动态维护命令：
   - 巡检: `scripts/maintain-state-health.ps1`
   - 自动归档: `scripts/maintain-state-health.ps1 -AutoArchive`
9. 通用目录维护命令：
   - 巡检: `scripts/maintain-directory-health.ps1 -TargetDir <dir>`
   - 指定文件自动归档: `scripts/maintain-directory-health.ps1 -TargetDir <dir> -AutoArchive -ArchiveFiles <rel-paths>`
