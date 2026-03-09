# Agent 生成框架（定义版，不执行）

## 1. 目标

构建一个“配置驱动”的 Agent 生成框架，仅完成框架定义与校验流程设计，不执行最终生成动作。

## 2. 框架边界

- 做什么：定义模块、流程、输入输出契约、质量门禁、错误模型。
- 不做什么：不调用生成步骤，不输出最终目标 Agent 文档。

## 3. 模块划分

1. `ConfigLoader`：读取并规范化配置。
2. `ConfigValidator`：校验必填项、类型、冲突关系。
3. `FieldMapper`：将用户字段映射到框架标准字段。
4. `SpecBuilder`：构建 Agent 规格草案（结构化中间产物）。
5. `TestCasePlanner`：为每个改动项生成对应测试用例草案与映射。
6. `OODesignChecker`：检查最小依赖、开闭原则等 OO 约束。
7. `TokenEfficiencyGuard`：检查日志读取与上下文装载是否最小化 Token 消耗。
8. `ScriptizationPlanner`：识别可重复流程并输出脚本化建议与清单。
9. `DualScopeComplianceChecker`：检查“本工作区 + 生成 Agent”双域是否同时合规。
10. `QualityGate`：执行规则检查并输出可追溯报告。
11. `Generator`：最终文档生成模块（当前禁用）。

## 4. 标准流程

1. 读取 `config.yaml`。
2. 解析并规范化配置结构。
3. 校验必填字段与冲突字段。
4. 输出字段映射结果与规格草案。
5. 生成“改动项 -> 测试用例”映射草案。
6. 执行面向对象设计原则检查。
7. 执行 Token 最小消耗检查。
8. 执行可重复流程脚本化检查。
9. 执行双域合规检查（workspace + generated_agents）。
10. 执行质量门禁检查。
11. 记录“可生成”状态，但不触发生成。

## 5. 输入契约

- 主输入文件：`config.yaml`
- 允许格式：`yaml/json/toml`
- 最低必填字段：
  - `agent.name`
  - `agent.role`
  - `agent.goal`
  - `outputs`

## 6. 输出契约（框架阶段）

- `validation_report`：配置合法性结果与缺失项。
- `mapping_report`：字段映射与推断项。
- `test_traceability_report`：改动项与测试用例对应关系。
- `oo_design_report`：OO 设计原则合规结果与违规项。
- `token_efficiency_report`：Token 消耗策略合规结果与高消耗风险项。
- `scriptization_report`：可重复流程脚本化覆盖率与脚本清单。
- `workspace_compliance_report`：本工作区设计要求合规结果。
- `generated_agent_compliance_report`：生成 Agent 设计要求合规结果。
- `quality_report`：质量门禁通过/失败项。
- `ready_state`：`ready | blocked`

## 7. 质量门禁

1. 必填字段齐全。
2. `non_goals` 不与 `workflow` 冲突。
3. `outputs` 包含失败输出格式定义。
4. 未声明工具不允许进入可执行状态。
5. 每个改动项都存在至少一个对应测试用例。
6. 每个改动项都满足 OO 原则（最小依赖、开闭原则、单一职责、依赖倒置）。
7. 高 Token 消耗操作被限制（禁止无差别读大日志，优先定向检索与摘要）。
8. 可重复流程优先脚本化（满足阈值时必须提供脚本实现或脚本化计划）。
9. 本工作区与生成 Agent 双域均通过同一套设计要求校验。

## 8. 错误模型

统一错误码：`AGENT_CONFIG_INVALID`

错误结构：

```text
ERROR: AGENT_CONFIG_INVALID
reason: <具体原因>
missing_or_conflict:
  - <字段A>
  - <字段B>
fix_suggestion:
  - <建议1>
  - <建议2>
```

## 9. 运行规则

- 当前阶段固定为：`design_only`
- 强制不执行：`execute_generation = false`
- 仅允许产出报告类中间结果，不产出最终 Agent 文档

## 10. 配置入口（用于调整框架要求）

- 常用开关：`config.yaml` 下的 `controls`
- 框架要求：`config.yaml` 下的 `framework_requirements`
- 流程启停：`config.yaml` 下的 `pipeline`
- 字段兼容：`config.yaml` 下的 `field_mapping.aliases`
- 改测要求：`config.yaml` 下的 `framework_requirements.change_testing`
- OO 要求：`config.yaml` 下的 `framework_requirements.oo_design`
- Token 要求：`config.yaml` 下的 `framework_requirements.token_efficiency`
- 脚本化要求：`config.yaml` 下的 `framework_requirements.scriptization`
- 双域要求：`config.yaml` 下的 `framework_requirements.compliance_scope`
- 直观查看：`docs/config_dashboard.md`
