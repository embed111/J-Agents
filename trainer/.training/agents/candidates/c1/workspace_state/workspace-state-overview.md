# 工作区状态概述

- 最后更新: 2026-02-24
- 目标: 在重启工作区后，用最小读取成本恢复一致的工作状态。

## 启动时读取顺序
1. `AGENTS.md`
2. `workspace_state/startup-checklist.md`
3. `workspace_state/session-snapshot.md`
4. `user_profile/thinking-patterns-overview.md`
5. `knowledge_base/analysis-methods-overview.md`
6. `skills/local-skills-overview.md`

## 当前状态快照
1. 已建立用户思维模式档案体系（`user_profile/`）。
2. 已建立思维分析方法与案例库（`knowledge_base/`）。
3. 已建立重启恢复机制（`workspace_state/`）。
4. 已建立工作区本地技能库（`skills/`）。
5. 自定义技能作用域已隔离到工作区原生路径：`./.codex/skill/`。

## 维护规则
1. 每轮对话后更新 `workspace_state/session-snapshot.md`。
2. 若流程或目录变更，更新 `workspace_state/startup-checklist.md`。
3. 每次机制调整后，写入 `workspace_state/state-change-log.md`。
