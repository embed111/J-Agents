# 详细设计-agent发布管理与版本切换

## 1. 设计目标
1. 在训练中心内实现“全部 agent 统一发布管理 + 已发布版本切换”。
2. 将“切换门禁、训练门禁、预发布治理、发布评估”串成可执行生命周期。
3. 维持当前阶段“人工评估优先”，并预留后续自动评估/自动发布扩展位。

## 2. 设计范围与非范围
1. 设计范围：
   1. 发布版本时间线展示（仅已发布版本）。
   2. 单 agent 版本切换（直接覆盖工作区）。
   3. 切换后的禁训门禁与“切回最新发布版本解冻”。
   4. 克隆角色并继续训练。
   5. 预发布状态识别与单 agent 舍弃预发布内容。
   6. 人工发布评估流程入口。
2. 非范围：
   1. 自动评估算法与阈值策略。
   2. 自动发布执行器实现。
   3. 切换/舍弃操作的可视化审计中心（后续增强）。

## 3. 信息架构（IA）
1. 一级入口：`训练中心`。
2. 二级结构建议：
   1. `Agent资产与版本`：版本时间线、切换、克隆入口。
   2. `训练运营`：训练计划与队列。
   3. `预发布与发布评估`：状态查看、舍弃预发布、人工评估。
3. agent-first 规则：
   1. 所有页面列表第一维度均为 `agent_id`。
   2. 所有操作上下文必须绑定单个 agent。

## 4. 生命周期与状态机
1. 生命周期状态（`lifecycle_state`）：
   1. `released`：发布态（工作区与某已发布版本一致）。
   2. `pre_release`：预发布态（存在发布版本之外修改；训练后默认进入）。
2. 训练门禁状态（`training_gate_state`）：
   1. `trainable`：允许训练。
   2. `frozen_switched`：因版本切换被冻结训练。
3. 关键状态流转：
   1. `released + trainable` --训练完成--> `pre_release + trainable`
   2. `released + trainable` --切换到非最新发布版本--> `released + frozen_switched`
   3. `released + frozen_switched` --切回最新发布版本--> `released + trainable`
   4. `pre_release + trainable` --舍弃预发布--> `released + trainable`
   5. `pre_release + trainable` --人工评估通过并发布--> `released + trainable`
4. 克隆角色特例：
   1. 原角色冻结不影响克隆角色。
   2. 克隆角色创建后默认 `released + trainable`，允许继续训练。

## 5. 数据模型设计（逻辑模型）
1. 扩展 `agent_registry`：
   1. `agent_id`（PK）
   2. `agent_name`
   3. `workspace_path`
   4. `current_version`
   5. `latest_release_version`
   6. `bound_release_version`（当前绑定的发布版本）
   7. `lifecycle_state`（`released|pre_release`）
   8. `training_gate_state`（`trainable|frozen_switched`）
   9. `parent_agent_id`（克隆来源，可空）
   10. `updated_at`
2. 扩展 `agent_release_history`（保持对外只读口径）：
   1. `release_id`（PK）
   2. `agent_id`
   3. `version_label`
   4. `released_at`
   5. `change_summary`
   6. `release_source_ref`（内部追溯字段，不在视图展示）
3. 新增 `agent_release_evaluation`：
   1. `evaluation_id`（PK）
   2. `agent_id`
   3. `target_version`
   4. `decision`（`approve|reject_continue_training|reject_discard`）
   5. `reviewer`
   6. `summary`
   7. `created_at`

## 6. 关键规则实现口径
1. 已发布版本判定：
   1. 固定为 `tag + release note`。
2. 版本切换校验：
   1. 目标版本必须存在于 `agent_release_history`。
   2. 若目标版本不在发布历史，直接拒绝。
3. 切换执行：
   1. 使用“直接覆盖工作区”策略。
   2. 切换成功后更新 `bound_release_version` 与 `current_version`。
4. 切换后禁训：
   1. 若 `current_version != latest_release_version`，设置 `training_gate_state=frozen_switched`。
   2. 若切回 `latest_release_version`，设置 `training_gate_state=trainable`。
5. 预发布判定：
   1. 训练任务成功回写后，将 `lifecycle_state` 更新为 `pre_release`。
6. 舍弃预发布：
   1. 仅单 agent 执行。
   2. 将工作区恢复到 `bound_release_version` 对应发布内容。
   3. 执行后 `lifecycle_state` 回到 `released`。

## 7. 接口草案（需求级）
1. `GET /api/training/agents`
   1. 返回 agent 列表与状态（含 `lifecycle_state/training_gate_state`）。
2. `GET /api/training/agents/{agent_id}/releases`
   1. 返回已发布版本时间线。
3. `POST /api/training/agents/{agent_id}/switch`
   1. 入参：`version_label`
   2. 语义：切换到已发布版本并覆盖工作区。
4. `POST /api/training/agents/{agent_id}/clone`
   1. 入参：`new_agent_id/new_agent_name`
   2. 语义：从当前版本克隆新角色并纳入管理。
5. `POST /api/training/agents/{agent_id}/pre-release/discard`
   1. 语义：单 agent 舍弃预发布内容，回到发布态。
6. `POST /api/training/agents/{agent_id}/release-evaluations/manual`
   1. 入参：`decision/reviewer/summary`
   2. 语义：记录人工评估并驱动后续发布决策。

## 8. 页面交互与门禁细节
1. 切换按钮门禁：
   1. 仅在选择“已发布版本”后可点击。
2. 训练入口门禁：
   1. `training_gate_state=frozen_switched` 时，训练入口禁用并显示“切回最新发布版本后可训练”。
3. 克隆入口：
   1. 原角色冻结时仍允许创建克隆角色。
4. 舍弃预发布入口：
   1. 仅在 `lifecycle_state=pre_release` 时可见。
   2. 仅支持单 agent 操作，不提供批量入口。
5. 人工评估入口：
   1. 仅在 `pre_release` 且有真实使用记录后可提交。

## 9. 异常处理
1. 切换目标版本不存在：
   1. 返回 `version_not_released`。
2. 冻结状态下尝试训练：
   1. 返回 `training_frozen_after_switch`。
3. 非预发布态执行舍弃：
   1. 返回幂等成功或 `not_in_pre_release`（实现选一种固定口径）。
4. 克隆目标 ID 已存在：
   1. 返回 `agent_id_conflict`。

## 10. 验收映射
1. `FR-AR-01~FR-AR-03` -> 第 3、6、7 节。
2. `FR-AR-04~FR-AR-07` -> 第 4、6、8 节。
3. `FR-AR-08~FR-AR-10` -> 第 5、7、8 节。

## 11. 与现有模块关系
1. 与“统一入口与训练优化模块”关系：
   1. 该设计是其发布治理子域增强，不替换原训练队列能力。
2. 对话模块关系：
   1. 对话、训练、发布评估共享同一 `agent_id` 维度，避免跨模块主键割裂。

## 12. 推断/假设与确认项
1. 推断/假设（置信度: 中）：
   1. “真实使用记录”短期可用会话数量/时长做最小代理指标，正式指标后续再定。
2. 已确认：
   1. 当前发布评估采用人工审核。
   2. 后续目标支持自动评估驱动自动训练/自动发布。
3. 待后续专题：
   1. 自动评估策略、阈值与回滚机制设计。

## 13. 验收取证规范
1. 每条 AC 必备证据：
   1. 页面截图。
   2. 接口请求/响应样例。
   3. 日志或数据库记录路径。
4. 对应代码文件路径。
5. 门禁统计表/汇总矩阵截图仅可作为辅助，不可替代功能页面截图。
6. 证据生命周期：
   1. 验收执行阶段保留完整证据用于判定。
   2. 验收通过后可按策略精简，仅保留门禁截图与汇总文件。
2. 必须录屏/GIF 的关键链路：
   1. 版本切换拒绝中间 commit（`AC-AR-03`）。
   2. 切换后禁训与切回解冻（`AC-AR-04/05`）。
   3. 克隆后训练（`AC-AR-06`）。
   4. 舍弃预发布回到发布态（`AC-AR-08`）。
