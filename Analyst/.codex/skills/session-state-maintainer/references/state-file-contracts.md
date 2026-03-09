# State File Contracts

## Purpose
Define minimum required sections so continuity files stay consistent.

## `workspace_state/core/session-snapshot.md`
Required:
1. `最后更新`
2. `当前长期机制`
3. `当前默认工作方式`
4. `本次新增资产`
5. `下一轮启动时优先关注`
6. Per-turn check sentence (when `MEMORY_UPDATE_SWITCH: ON`):
- `快照检查：用户偏好已更新=<是/否>；用户需求已完全理解=<是/否>`
7. Keep all historical check sentences (no overwrite), and keep the latest one at file end.

## `workspace_state/core/startup-checklist.md`
Required:
1. `目标`
2. `启动步骤`
3. `执行前自检`

## `workspace_state/logs/state-change-log.md`
Required:
1. Date header
2. What changed
3. Why changed

## `user_profile/logs/thinking-patterns-change-log.md`
Required:
1. Date header
2. New observations
3. Changed confidence or behavior
4. Pending verification items

## Confidence Labels
- `high`: repeated across scenes and turns
- `medium`: repeated in one scene
- `low`: single signal or ambiguous

