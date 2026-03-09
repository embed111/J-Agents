# 配置看板（直观版）

> 用途：快速查看并调整“对生成框架的要求”。  
> 当前状态：`design_only` + `execute_generation=false`（不会执行生成）。

## 1) 核心开关（最常调整）

| 参数 | 配置路径 | 当前值 | 作用 |
|---|---|---|---|
| 运行模式 | `controls.mode` | `design_only` | 控制仅设计框架还是进入生成 |
| 执行生成 | `controls.execute_generation` | `false` | `false` 时严格不生成最终 Agent |
| 严格度 | `controls.strictness` | `high` | 决定校验和门禁强度 |
| 允许推断 | `controls.allow_inference` | `false` | 是否允许自动补全未声明项 |
| 输出详细度 | `controls.detail_level` | `detailed` | 控制产出文档详略 |
| 输出语言 | `controls.language` | `zh-CN` | 控制生成内容语言 |

## 2) 生成框架要求（可调）

| 要求项 | 配置路径 | 当前值 |
|---|---|---|
| 必填字段 | `framework_requirements.required_keys` | `agent.name/agent.role/agent.goal/outputs` |
| 固定章节 | `framework_requirements.required_sections` | 11 个固定一级章节 |
| Workflow 编号步骤 | `framework_requirements.workflow_rules.numbered_steps` | `true` |
| Workflow 动词开头 | `framework_requirements.workflow_rules.step_start_with_verb` | `true` |
| 输出契约含失败格式 | `framework_requirements.output_contract_rules.require_failure_output_schema` | `true` |
| 安全策略含拒绝条件 | `framework_requirements.safety_rules.require_refusal_conditions` | `true` |
| 安全策略含降级策略 | `framework_requirements.safety_rules.require_fallback_strategy` | `true` |
| 每个改动必须有测试 | `framework_requirements.change_testing.require_test_for_each_change` | `true` |
| 需要改测映射矩阵 | `framework_requirements.change_testing.require_traceability_matrix` | `true` |
| 缺失测试允许仅说明 | `framework_requirements.change_testing.allow_missing_test_with_justification` | `false` |
| 最小依赖原则 | `framework_requirements.oo_design.require_minimal_dependency` | `true` |
| 开闭原则 | `framework_requirements.oo_design.require_open_closed_principle` | `true` |
| 单一职责原则 | `framework_requirements.oo_design.require_single_responsibility` | `true` |
| 依赖倒置原则 | `framework_requirements.oo_design.require_dependency_inversion` | `true` |
| 低耦合高内聚 | `framework_requirements.oo_design.require_low_coupling_high_cohesion` | `true` |
| Token 最小消耗 | `framework_requirements.token_efficiency.require_minimal_token_usage` | `true` |
| 禁止无界日志读取 | `framework_requirements.token_efficiency.forbid_unbounded_log_read` | `true` |
| 单次日志读取上限 | `framework_requirements.token_efficiency.max_log_lines_per_read` | `200` |
| 重复流程脚本化 | `framework_requirements.scriptization.require_script_for_repeatable_flows` | `true` |
| 重复阈值 | `framework_requirements.scriptization.repeatability_threshold` | `2` |
| 需要脚本清单 | `framework_requirements.scriptization.require_script_manifest` | `true` |
| 工作区合规校验 | `framework_requirements.compliance_scope.enforce_workspace_compliance` | `true` |
| 生成 Agent 合规校验 | `framework_requirements.compliance_scope.enforce_generated_agent_compliance` | `true` |
| 双域失败即阻断 | `framework_requirements.compliance_scope.block_on_scope_violation` | `true` |

## 3) 流水线开关（按模块）

| 模块 | 配置路径 | 当前值 |
|---|---|---|
| 读取配置 | `pipeline.load_config` | `true` |
| 校验配置 | `pipeline.validate_config` | `true` |
| 字段映射 | `pipeline.map_fields` | `true` |
| 构建规格草案 | `pipeline.build_spec` | `true` |
| OO 合规检查 | `pipeline.ood_compliance_check` | `true` |
| Token 效率检查 | `pipeline.token_efficiency_check` | `true` |
| 脚本化检查 | `pipeline.scriptization_check` | `true` |
| 工作区合规检查 | `pipeline.workspace_compliance_check` | `true` |
| 生成 Agent 合规检查 | `pipeline.generated_agent_compliance_check` | `true` |
| 质量门禁 | `pipeline.quality_gate` | `true` |
| 生成 Agent | `pipeline.generate_agent` | `false` |

## 4) 你只需要改哪里

1. 改运行行为：`controls.*`
2. 改框架要求：`framework_requirements.*`
3. 改字段兼容：`field_mapping.aliases.*`
4. 改目标 Agent 语义：`agent/inputs/outputs/workflow/tools/policies/style`

## 5) 测试要求快速入口

| 目标 | 建议修改路径 |
|---|---|
| 强制每个改动都要测试 | `framework_requirements.change_testing.require_test_for_each_change` |
| 要求输出改测映射矩阵 | `framework_requirements.change_testing.require_traceability_matrix` |
| 限制测试类型 | `framework_requirements.change_testing.allowed_test_types` |
| 禁止“无测试仅解释” | `framework_requirements.change_testing.allow_missing_test_with_justification` |

## 6) OO 原则快速入口

| 目标 | 建议修改路径 |
|---|---|
| 强制最小依赖 | `framework_requirements.oo_design.require_minimal_dependency` |
| 强制开闭原则 | `framework_requirements.oo_design.require_open_closed_principle` |
| 强制单一职责 | `framework_requirements.oo_design.require_single_responsibility` |
| 强制依赖倒置 | `framework_requirements.oo_design.require_dependency_inversion` |
| 强制低耦合高内聚 | `framework_requirements.oo_design.require_low_coupling_high_cohesion` |
| 禁止违规仅解释 | `framework_requirements.oo_design.allow_violation_with_justification` |

## 7) Token 最小消耗入口

| 目标 | 建议修改路径 |
|---|---|
| 强制 Token 最小消耗 | `framework_requirements.token_efficiency.require_minimal_token_usage` |
| 禁止无差别读大日志 | `framework_requirements.token_efficiency.forbid_unbounded_log_read` |
| 控制单次日志读取上限 | `framework_requirements.token_efficiency.max_log_lines_per_read` |
| 强制定向检索优先 | `framework_requirements.token_efficiency.require_targeted_search_before_full_read` |
| 强制摘要优先于原文倾倒 | `framework_requirements.token_efficiency.prefer_summary_over_raw_dump` |
| 禁止“高消耗仅解释放行” | `framework_requirements.token_efficiency.allow_exception_with_justification` |

## 8) 重复流程脚本化入口

| 目标 | 建议修改路径 |
|---|---|
| 强制重复流程脚本化 | `framework_requirements.scriptization.require_script_for_repeatable_flows` |
| 调整重复判定阈值 | `framework_requirements.scriptization.repeatability_threshold` |
| 强制输出脚本清单 | `framework_requirements.scriptization.require_script_manifest` |
| 强制可复用入口 | `framework_requirements.scriptization.require_reusable_entrypoint` |
| 一次性任务可手工 | `framework_requirements.scriptization.allow_manual_for_one_off_tasks` |
| 禁止“脚本化例外放行” | `framework_requirements.scriptization.allow_exception_with_justification` |

## 9) 双域合规入口（工作区 + 生成 Agent）

| 目标 | 建议修改路径 |
|---|---|
| 强制校验工作区合规 | `framework_requirements.compliance_scope.enforce_workspace_compliance` |
| 强制校验生成 Agent 合规 | `framework_requirements.compliance_scope.enforce_generated_agent_compliance` |
| 指定统一要求来源 | `framework_requirements.compliance_scope.shared_requirements_source` |
| 双域任一失败即阻断 | `framework_requirements.compliance_scope.block_on_scope_violation` |
