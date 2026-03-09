# 工作区重启检查清单

## 目标
确保每次重启后快速恢复到一致的分析与交付状态。

## 启动步骤
1. 检查工作区技能加载目录 `./.codex/skills/` 是否存在且包含所需技能。
2. 读取 `AGENTS.md`，确认职责、输出规范与维护要求。
3. 读取 `workspace_state/workspace-state-overview.md`，确认当前机制版本。
4. 读取 `workspace_state/session-snapshot.md`，恢复上次会话状态。
5. 读取 `workspace_state/preference-attribution-policy.md`，确认偏好防污染规则。
6. 读取 `workspace_state/external-input-observations.md`，确认外部角色偏好与待归属事项。
7. 读取 `user_profile/thinking-patterns-overview.md`，恢复用户思维模式上下文。
8. 读取 `knowledge_base/analysis-methods-overview.md`，恢复可用分析方法与案例索引。
9. 读取 `skills/local-skills-overview.md`，恢复本地技能使用策略。
10. 检查 `user_profile/thinking-patterns-change-log.md` 最近一条，确认最新偏好变化。

## 执行前自检
1. 是否识别当前任务所属领域？
2. 是否选择了合适分析方法（或方法组合）？
3. 是否明确哪些内容是事实、哪些是推断/假设？
4. 是否计划在本轮结束后更新状态文件和变更日志？
5. 是否完成“能力扩展评估”（是否需要新增 skill 或 agent 角色）？
6. 是否完成“偏好归属检查”（owner vs trainer/外部角色），避免写错到 `user_profile/`？
7. 若无 owner 明确确认，本轮是否保持偏好“只暂存不提交”？
8. 是否读取并遵守 `AGENTS.md` 顶部 `MEMORY_UPDATE_SWITCH`（OFF 时不自动写档案）？
9. 是否遵守“分析师硬边界”（仅做需求文档，不做其他工作区工程改造）？
10. 若存在执行工作区，是否完成 `docs/workflow` 双工作区文档一致性校验（文件集与哈希）？
