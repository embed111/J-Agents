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
