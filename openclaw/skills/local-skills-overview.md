# 本地技能总览

- 最后更新: 2026-03-07
- 加载目录: `./.codex/skills/`

## 可用技能
1. `session-bootstrap-check`
   - 路径: `./.codex/skills/session-bootstrap-check/SKILL.md`
   - 作用: 会话启动时按顺序恢复身份、用户与记忆上下文。
2. `chat-preference-recorder`
   - 路径: `./.codex/skills/chat-preference-recorder/SKILL.md`
   - 作用: 从聊天提取偏好，区分已确认/待验证并回写记忆。
3. `workspace-scope-guard`
   - 路径: `./.codex/skills/workspace-scope-guard/SKILL.md`
   - 作用: 约束跨目录操作，阻止越界或误删误改。
4. `safe-home-cleanup-planner`
   - 路径: `./.codex/skills/safe-home-cleanup-planner/SKILL.md`
   - 作用: 无用文件清理先预览、后确认、再执行。

## 使用策略
1. 命中场景时优先使用本地技能，减少重复推理。
2. 先加载最相关单个技能，再按需扩展读取。
3. 涉及删除/跨目录写入时，默认联动 `workspace-scope-guard`。