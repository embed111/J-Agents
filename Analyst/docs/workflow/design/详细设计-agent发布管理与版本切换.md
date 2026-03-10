# 详细设计-agent发布管理与版本切换

## 1. 设计目标
1. 在训练中心内实现“全部 agent 统一发布管理 + 已发布版本切换”。
2. 将“切换门禁、训练门禁、预发布治理、发布评审、人工审核、确认发布”串成可执行生命周期。
3. 维持当前阶段“对应工作区 agent 生成发布报告 + 人工审核 + 人工确认发布”的门禁模式，并预留后续自动评估/自动发布扩展位。
4. 让发布报告在正式发布成功后可直接作为角色详情页的最新正式发布介绍来源。

## 2. 设计范围与非范围
1. 设计范围：
   1. 发布版本时间线展示（仅已发布版本）。
   2. 单 agent 版本切换（直接覆盖工作区）。
   3. 切换后的禁训门禁与“切回最新发布版本解冻”。
   4. 克隆角色并继续训练。
   5. 预发布状态识别与单 agent 舍弃预发布内容。
   6. 发布评审入口、发布报告生成、人工审核与确认发布流程。
2. 非范围：
   1. 自动评估算法与阈值策略。
   2. 自动发布执行器实现。
   3. 切换/舍弃操作的可视化审计中心（后续增强）。

## 3. 信息架构（IA）
1. 一级入口：`训练中心`。
2. 二级结构建议：
   1. `Agent资产与版本`：版本时间线、切换、克隆入口。
   2. `训练运营`：训练计划与队列。
   3. `预发布与发布评审`：仅展示当前活跃评审的状态查看、进入发布评审、舍弃预发布、人工审核、确认发布。
   4. `发布版本历史`：查看已发布版本列表，并通过“查看发布报告”按版本下钻历史发布评审记录。
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
3. 发布评审状态（`release_review_state`）：
   1. `idle`：未进入发布评审。
   2. `report_generating`：已进入发布评审，正在委派对应工作区 agent 生成发布报告。
   3. `report_ready`：发布报告已生成，等待人工审核。
   4. `review_approved`：人工审核通过，等待最终确认发布。
   5. `review_rejected`：人工审核未通过。
   6. `publish_running`：已进入确认发布执行阶段，正在执行 Git 发布、release note 处理与成功校验。
   7. `publish_failed`：确认发布失败，已触发或正在等待兜底结果。
   8. `report_failed`：发布报告生成失败。
4. 关键状态流转：
   1. `released + trainable` --训练完成--> `pre_release + trainable`
   2. `released + trainable` --切换到非最新发布版本--> `released + frozen_switched`
   3. `released + frozen_switched` --切回最新发布版本--> `released + trainable`
   4. `pre_release + trainable + idle` --进入发布评审--> `pre_release + trainable + report_generating`
   5. `pre_release + trainable + report_generating` --Codex 成功生成发布报告--> `pre_release + trainable + report_ready`
   6. `pre_release + trainable + report_ready` --人工审核通过--> `pre_release + trainable + review_approved`
   7. `pre_release + trainable + report_ready` --人工审核不通过--> `pre_release + trainable + review_rejected`
   8. `pre_release + trainable + review_approved` --点击确认发布--> `pre_release + trainable + publish_running`
   9. `pre_release + trainable + publish_running` --Git + release note 校验通过--> `released + trainable + idle`
   10. `pre_release + trainable + publish_running` --Git 失败 / release note 失败 / 校验失败--> `pre_release + trainable + publish_failed`
   11. `pre_release + trainable` --舍弃预发布--> `released + trainable + idle`
5. 克隆角色特例：
   1. 原角色冻结不影响克隆角色。
   2. 克隆角色创建后默认 `released + trainable + idle`，允许继续训练。

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
   10. `release_review_state`（`idle|report_generating|report_ready|review_approved|review_rejected|publish_running|publish_failed|report_failed`）
   11. `active_role_profile_release_id`（当前角色详情绑定的正式发布版本，可空）
   12. `active_role_profile_ref`（当前角色详情绑定的正式发布介绍快照路径，可空）
   13. `updated_at`
2. 扩展 `agent_release_history`（保持对外只读口径）：
   1. `release_id`（PK）
   2. `agent_id`
   3. `version_label`
   4. `released_at`
   5. `change_summary`
   6. `release_source_ref`（内部追溯字段，不在视图展示）
   7. `public_profile_ref`（角色详情展示用的公开发布报告快照）
   8. `capability_snapshot_ref`（全量能力结构化快照）
3. 新增 `agent_release_review`：
   1. `review_id`（PK）
   2. `agent_id`
   3. `target_version`
   4. `workspace_agent_ref`
   5. `report_task_id`
   6. `report_status`（`queued|running|succeeded|failed`）
   7. `report_prompt_version`
   8. `report_markdown_path`
   9. `report_json_path`
   10. `public_profile_markdown_path`
   11. `capability_snapshot_json_path`
   12. `analysis_chain_ref`
   13. `review_decision`（`approve_publish|reject_continue_training|reject_discard_pre_release`）
   14. `reviewer`
   15. `review_comment`
   16. `reviewed_at`
   17. `publish_verification_status`（`pending|passed|failed`）
   18. `publish_log_ref`
   19. `fallback_task_id`
   20. `fallback_status`（`idle|running|succeeded|failed`）
   21. `created_at`
4. 新增 `agent_release_publish_log`：
   1. `log_id`（PK）
   2. `review_id`
   3. `agent_id`
   4. `stage`（`prepare|git_execute|release_note|verify|fallback_trigger|fallback_result`）
   5. `status`（`running|succeeded|failed`）
   6. `summary`
   7. `command_ref`
   8. `stdout_ref`
   9. `stderr_ref`
   10. `extra_payload_ref`
   11. `created_at`

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
6. 进入发布评审：
   1. 仅允许 `lifecycle_state=pre_release` 的 agent 进入。
   2. 进入后创建 `agent_release_review` 记录，并将 `release_review_state` 设置为 `report_generating`。
   3. 进入发布评审前先做元数据预检：
      1. 检查 `target_version/current_registry_version/latest_release_version/released_versions` 是否自洽；
      2. 若存在明显冲突，优先输出 `metadata_conflict` 类失败信息，并写入评审记录；
      3. 不把元数据冲突直接伪装成 agent 能力风险。
7. 发布报告委派：
   1. 系统必须基于 `agent_id -> workspace_path` 选择对应工作区 agent。
   2. 执行方式固定复用“会话入口 agent 分析”链路：`codex exec` + 提示词版本 + 证据落盘 + 分析链路可见。
   3. 发布报告输出契约至少包含：
      1. `target_version/current_workspace_ref`
      2. `first_person_summary`
      3. `full_capability_inventory`
      4. `knowledge_scope`
      5. `agent_skills`
      6. `applicable_scenarios`
      7. `change_summary`
      8. `capability_delta`
      9. `risk_list`
      10. `validation_evidence`
      11. `release_recommendation`
      12. `next_action_suggestion`
   4. `first_person_summary/change_summary/risk_list/validation_evidence/next_action_suggestion` 等自然语言字段统一使用第一人称视角。
   5. 发布报告必须同时输出“全量能力清单快照”与“版本增量说明”；前者用于角色详情，后者用于评审判断。
   6. 成功生成报告后，需落盘 `public_profile_markdown_path` 与 `capability_snapshot_json_path`，但在正式发布成功前不得激活到角色详情页。
   7. 报告生成的事实来源优先级固定为：
      1. 当前工作区 `AGENTS.md`；
      2. 当前已知角色画像字段与本地 skills；
      3. 当前版本上下文（目标版本、上一正式版本、绑定版本）；
      4. 可读的 `README/CHANGELOG/release note` 与工作区内相关说明文档。
   8. 若 `README/CHANGELOG/release note` 缺失，默认只写入 `warnings`，不作为单独的拒绝门禁；除非上层产品规则已显式声明其为必备发布材料。
   9. Git 风险判断默认只读取目标工作区路径范围内的状态与差异；仓库外或兄弟工作区噪声仅可作为辅助提示，不得主导 `release_recommendation`。
   10. 若不存在上一正式发布版本，则进入 `initial_release` 评审模式：
      1. `previous_release_version` 允许为空；
      2. 仍必须输出完整 `first_person_summary/full_capability_inventory/knowledge_scope/agent_skills/applicable_scenarios`；
      3. `capability_delta` 用于描述“当前首发基线包含什么”，而不是退化为空或只输出拒绝理由。
   11. `release_recommendation` 只允许使用 `approve/reject/needs_more_validation`；
      1. 服务端负责把历史旧枚举（如 `reject_continue_training/reject_discard_pre_release`）映射到新建议枚举；
      2. 人工审核决策仍保持独立字段，不与报告建议复用。
   12. 若 Codex 执行失败、超时或输出不符合契约，则设置 `release_review_state=report_failed`，并阻断确认发布。
   13. `report_failed` 时仍需落盘“失败报告骨架”：
      1. 优先保留已解析出的结构化字段；
      2. 至少补齐 `target_version/current_workspace_ref/change_summary/release_recommendation/next_action_suggestion`；
      3. 保留 `raw_result/warnings` 供前端与人工排查；
      4. 禁止仅向前端回传空 `report_json`。
8. 人工审核：
   1. 仅当 `release_review_state=report_ready` 时允许提交审核结论。
   2. 审核通过后设置 `release_review_state=review_approved`。
   3. 审核不通过后设置 `release_review_state=review_rejected`。
9. 确认发布：
   1. 仅当 `release_review_state=review_approved` 时允许执行。
   2. 点击后先将 `release_review_state` 设置为 `publish_running`。
   3. 发布动作必须以 Git 与 release note 作为正式发布事实来源，不得只写业务库状态。
   4. 执行步骤至少包括：
      1. 准备发布参数与 release note；
      2. 执行 Git 发布命令；
      3. 写入或关联 release note；
      4. 重新读取当前“Git + release note”识别结果做成功校验。
   5. 成功校验规则至少包括：
      1. 新发布版本可被当前“已发布版本识别器”读到；
      2. 新版本已进入该 agent 的已发布版本时间线；
      3. `publish_verification_status=passed`；
      4. 当前评审记录已落盘 `public_profile_markdown_path` 与 `capability_snapshot_json_path`；
      5. 仅在满足上述条件后，才写入 `agent_release_history`、更新 `agent_registry.active_role_profile_release_id/active_role_profile_ref`，并将状态切回 `released + idle`。
   6. 全过程必须写入 `agent_release_publish_log`。
   7. 任一阶段失败时，设置 `release_review_state=publish_failed`、`publish_verification_status=failed`。
   8. 失败后必须自动启动 `../workflow` 工作区 agent 进行兜底。
   9. 兜底 agent 的默认执行步骤固定为：
      1. 分析并输出失败原因；
      2. 自动重试一次 Git 发布；
      3. 再次执行“Git + release note”成功校验；
      4. 输出重试结果与下一步建议。
   10. 兜底 agent 的输出至少包含：失败原因、已执行的重试动作、重试结果、下一步建议。
   11. 不论兜底是否尝试补救，只有再次通过“Git + release note”成功校验，才可算作正式发布成功。
10. 舍弃预发布：
   1. 仅单 agent 执行。
   2. 将工作区恢复到 `bound_release_version` 对应发布内容。
   3. 执行后 `lifecycle_state` 回到 `released`，`release_review_state` 回到 `idle`。

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
6. `POST /api/training/agents/{agent_id}/release-review/enter`
   1. 语义：进入发布评审，并自动触发对应工作区 agent 的发布报告生成任务。
7. `GET /api/training/agents/{agent_id}/release-review`
   1. 语义：返回当前发布评审状态、报告摘要、分析链路引用、人工审核结果、发布执行日志摘要、成功校验结果与兜底状态。
8. `POST /api/training/agents/{agent_id}/release-review/manual`
   1. 入参：`review_decision/reviewer/review_comment`
   2. 语义：记录人工审核结论。
9. `POST /api/training/agents/{agent_id}/release-review/confirm`
   1. 语义：仅在人工审核通过后，启动 Git + release note 方式的确认发布任务，并在成功校验通过后写入正式发布记录。

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
5. 发布评审入口：
   1. 仅在 `pre_release` 且有真实使用记录后可点击。
   2. 点击后页面进入四步状态条：`进入发布评审 -> 生成发布报告 -> 人工审核 -> 确认发布`。
6. 首页评审区展示口径：
   1. 首页“发布评审”区块只展示当前活跃评审。
   2. “当前活跃评审”定义为：当前 agent 最近一条尚未因“确认发布成功”或“显式废弃”而结束的评审记录。
   3. 若当前不存在活跃评审，则首页不常驻渲染完整发布评审内容。
   4. 历史已发布版本对应的评审记录不得继续常驻在首页评审区。
7. 发布报告展示：
   1. 报告生成阶段必须展示排队中/执行中/已完成/失败状态。
   2. 报告顶部优先展示“第一人称述职摘要 + 全量能力清单”，再展示版本增量、风险与证据。
   3. 报告正文、提示词、Codex 执行摘要、stdout/stderr、结构化结果默认折叠展示，但必须支持完整下钻。
   4. 若进入失败态，页面错误文案优先显示后端返回的真实失败原因；
      1. 仅当后端明确返回“结构化报告不完整”时，才显示“缺字段”提示；
      2. 缺字段列表必须与服务端 `RELEASE_REVIEW_REQUIRED_FIELDS` 一致，不允许前后端各自维护不同口径。
8. 历史发布报告弹窗：
   1. “发布版本”列表中的每个已发布版本按 `release_id/version_label` 独立渲染。
   2. 若该版本存在 `release_source_ref/public_profile_ref/capability_snapshot_ref` 等可展示来源，则显示“查看发布报告”按钮。
   3. 点击“查看发布报告”后，页面以 `dialog/modal` 方式展示该版本对应的历史发布报告/发布评审记录。
   4. 弹窗数据源必须与当前点击版本一一绑定，不得复用当前活跃评审状态。
   5. 历史报告弹窗只承担“按版本查看历史报告/评审记录”职责，不承载当前评审的步骤条、人工审核按钮或确认发布按钮。
   6. 若该版本未绑定可展示报告，则列表仅显示不可查看原因，不展示“查看发布报告”按钮。
9. 人工审核入口：
   1. 仅在 `release_review_state=report_ready` 时可提交。
10. 确认发布按钮：
   1. 仅在 `release_review_state=review_approved` 时可点击。
   2. 其余状态必须禁用并展示原因。
   3. 点击后必须展示子阶段进度：`Git 发布中 -> release note 处理中 -> 成功校验中 -> 完成/失败`。
   4. 若失败触发兜底，页面需展示 `兜底中/兜底完成/兜底失败`。
11. 发布执行日志展示：
   1. 发布评审详情需提供“发布执行日志”区块，默认折叠。
   2. 展开后至少可查看 Git 命令摘要、release note 引用、成功校验结果、兜底任务引用与结果摘要。
12. 角色详情联动：
   1. 正式发布成功后，角色详情页优先读取 `agent_registry.active_role_profile_ref`。
   2. 预发布报告在正式发布成功前仅显示于发布评审页，不得覆盖当前正式发布角色详情。

## 9. 异常处理
1. 切换目标版本不存在：
   1. 返回 `version_not_released`。
2. 冻结状态下尝试训练：
   1. 返回 `training_frozen_after_switch`。
3. 非预发布态执行舍弃：
   1. 返回幂等成功或 `not_in_pre_release`（实现选一种固定口径）。
4. 克隆目标 ID 已存在：
   1. 返回 `agent_id_conflict`。
5. 无对应工作区 agent：
   1. 返回 `workspace_agent_not_found`，并阻断发布报告生成。
6. 发布报告生成失败：
   1. 返回 `release_report_generation_failed`，且“确认发布”不可点击。
   2. 若已拿到部分结构化结果，仍需在 `review.report` 中保留失败报告骨架，供页面展示与人工复核。
7. 报告未就绪即提交人工审核：
   1. 返回 `release_report_not_ready`。
8. 人工审核未通过即确认发布：
   1. 返回 `release_review_not_approved`。
9. Git 发布命令执行失败：
   1. 返回 `release_git_execute_failed`，写入发布日志，并触发 `../workflow` 工作区 agent 兜底。
10. release note 写入或关联失败：
   1. 返回 `release_note_write_failed`，写入发布日志，并触发兜底。
11. 发布成功校验失败：
   1. 返回 `release_verification_failed`，不得标记为已发布，并触发兜底。
12. `../workflow` 工作区 agent 兜底启动失败：
   1. 返回 `release_fallback_start_failed`，写入日志并提示人工介入。
13. 兜底自动重试一次后仍失败：
   1. 返回 `release_fallback_retry_failed`，保留失败态与完整日志，并提示人工介入。

## 10. 验收映射
1. `FR-AR-01~FR-AR-03` -> 第 3、6、7 节。
2. `FR-AR-04~FR-AR-07` -> 第 4、6、8 节。
3. `FR-AR-08~FR-AR-13` -> 第 4、5、6、7、8、9 节。

## 11. 与现有模块关系
1. 与“统一入口与训练优化模块”关系：
   1. 该设计是其发布治理子域增强，不替换原训练队列能力。
2. 对话模块关系：
   1. 对话、训练、发布评估共享同一 `agent_id` 维度，避免跨模块主键割裂。
3. 与“会话入口 agent 分析”关系：
   1. 发布报告生成直接复用其 `Codex` 执行链路、提示词版本化、证据落盘与默认折叠下钻展示模式，避免另起一套分析框架。
4. 与 `../workflow` 工作区 agent 关系：
   1. 当确认发布失败时，直接复用该工作区 agent 作为兜底执行器，承担失败诊断、自动重试一次发布与结果回传。
5. 与“角色画像发布格式与预发布判定”关系：
   1. 正式发布成功后，本设计产出的 `active_role_profile_ref` 将成为角色详情页优先展示的数据源。

## 12. 推断/假设与确认项
1. 推断/假设（置信度: 中）：
   1. “真实使用记录”短期可用会话数量/时长做最小代理指标，正式指标后续再定。
   2. “对应工作区 agent” 默认按 `agent_id -> workspace_path -> AGENTS.md` 映射确定。
   3. 历史正式发布版本若无公开发布报告，可先回退到结构化字段渲染角色详情。
2. 已确认：
   1. 当前正式发布前必须先进入发布评审。
   2. 发布报告由对应工作区 agent 通过 `Codex` 生成。
   3. 最终发布仍由人工审核与人工确认把关。
   4. 确认发布必须使用 Git + release note，并在发布后再次校验是否成功。
   5. 若确认发布失败，必须自动启动 `../workflow` 工作区 agent 进行兜底。
   6. 兜底 agent 的默认职责固定为“给出失败原因 + 自动重试一次 + 输出重试结果”。
   7. 后续目标支持自动评估驱动自动训练/自动发布。
   8. 首页只展示当前活跃评审；历史正式发布版本的评审记录通过“查看发布报告”弹窗按版本查看。
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
   5. 进入发布评审并生成发布报告（`AC-AR-09/10`）。
   6. 人工审核后确认发布（`AC-AR-11/12`）。
   7. 发布失败后自动触发兜底（`AC-AR-14`）。


