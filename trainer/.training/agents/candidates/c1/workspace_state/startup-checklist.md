# 工作区重启检查清单

## 目标
确保每次重启后快速恢复到一致的分析与交付状态。

## 启动步骤
1. 检查工作区技能加载目录 `./.codex/skill/` 是否存在且包含所需技能。
2. 读取 `AGENTS.md`，确认职责、输出规范与维护要求。
3. 读取 `workspace_state/workspace-state-overview.md`，确认当前机制版本。
4. 读取 `workspace_state/session-snapshot.md`，恢复上次会话状态。
5. 读取 `user_profile/thinking-patterns-overview.md`，恢复用户思维模式上下文。
6. 读取 `knowledge_base/analysis-methods-overview.md`，恢复可用分析方法与案例索引。
7. 读取 `skills/local-skills-overview.md`，恢复本地技能使用策略。
8. 检查 `user_profile/thinking-patterns-change-log.md` 最近一条，确认最新偏好变化。

## 执行前自检
1. 是否识别当前任务所属领域？
2. 是否选择了合适分析方法（或方法组合）？
3. 是否明确哪些内容是事实、哪些是推断/假设？
4. 是否计划在本轮结束后更新状态文件和变更日志？
