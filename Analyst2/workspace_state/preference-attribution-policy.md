# 偏好归属与防污染策略

- 最后更新: 2026-02-25
- 目标: 防止 trainer/外部输入污染 owner 偏好档案。

## 原则
1. fail-closed: 归属不清时，默认不写入 `user_profile/`。
2. source-first: 先判定来源，再决定写入位置。
3. reversible: 任何偏好写入必须可回滚、可追溯。
4. two-phase-commit: 偏好先入“待归属/外部观察”，经 owner 明确确认后才可写入 `user_profile/`。
5. switch-governed: 当 `MEMORY_UPDATE_SWITCH: OFF` 时，禁止自动写入 `user_profile/*` 与会话快照文件。

## 来源标签
1. `owner_confirmed`: 明确来自用户本人，允许进入 `user_profile/`。
2. `external_confirmed`: 明确来自 trainer/外部角色，写入 `workspace_state/external-input-observations.md`。
3. `pending_attribution`: 归属不明确，写入外部观察日志并等待确认。

## 写入矩阵
1. owner_confirmed -> `user_profile/*`
2. external_confirmed -> `workspace_state/external-input-observations.md`
3. pending_attribution -> `workspace_state/external-input-observations.md`

## 二阶段提交流程（默认启用）
1. Phase-1 暂存:
   - 新观察先记到 `workspace_state/external-input-observations.md`（`pending_attribution` 或 `external_confirmed`）。
2. Phase-2 提交:
   - 只有当 owner 在当前会话明确确认“这是我的长期偏好”后，才迁移写入 `user_profile/*`。
3. 未确认处理:
   - 若无 owner 明确确认，保持暂存状态，不得写入用户偏好档案。

## 写入前检查（必须全部通过）
1. 是否有明确来源角色（owner/trainer/other）？
2. 是否有证据片段（本轮原话或明确转述）？
3. 是否标注了置信度？
4. 是否标注了“推断/假设”与否？

## 污染应急回滚
1. 在 `workspace_state/external-input-observations.md` 记录污染事件与时间点。
2. 在 `user_profile/thinking-patterns-change-log.md` 增加“污染回滚记录”条目。
3. 从相关 `user_profile` 文件移除误写条目，并在回滚记录里写明原因与影响范围。
