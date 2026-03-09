# 工作区状态概述

- 最后更新: 2026-02-25
- 目标: 在重启工作区后，用最小读取成本恢复一致的工作状态。

## 启动时读取顺序
1. `AGENTS.md`
2. `workspace_state/startup-checklist.md`
3. `workspace_state/session-snapshot.md`
4. `workspace_state/preference-attribution-policy.md`
5. `workspace_state/external-input-observations.md`
6. `user_profile/thinking-patterns-overview.md`
7. `knowledge_base/analysis-methods-overview.md`
8. `skills/local-skills-overview.md`

## 当前状态快照
1. 已建立用户思维模式档案体系（`user_profile/`）。
2. 已建立思维分析方法与案例库（`knowledge_base/`）。
3. 已建立重启恢复机制（`workspace_state/`）。
4. 已建立工作区本地技能库（`skills/`）。
5. 自定义技能作用域已隔离到工作区原生路径：`./.codex/skills/`。
6. 已启用“能力扩展评估”默认门禁：每轮分析前检查是否需要新增 skill 或 agent 角色。
7. 已启用“偏好归属隔离”机制：用户偏好与训练师/外部角色偏好分开记录。
8. 已启用档案更新开关：`MEMORY_UPDATE_SWITCH` 控制是否自动写入状态/偏好档案。

## 维护规则
1. 每轮对话后更新 `workspace_state/session-snapshot.md`。
2. 若流程或目录变更，更新 `workspace_state/startup-checklist.md`。
3. 每次机制调整后，写入 `workspace_state/state-change-log.md`。
4. 需求分析输出默认包含“能力扩展评估（新增 skill/agent 角色）”结论。
5. 档案自动更新前先检查 `MEMORY_UPDATE_SWITCH`，OFF 时仅按用户明确指令更新。
