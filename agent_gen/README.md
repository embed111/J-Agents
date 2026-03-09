# agent_gen 工作目录说明

## 目录结构

- `agent.md`：Agent 生成主规范（配置驱动规则）
- `config.yaml`：主配置文件（可调参数面板）
- `agent_principles.yaml`：生成原则统一配置（人机可读）
- `docs/agent_framework.md`：框架设计说明（不执行生成）
- `docs/config_dashboard.md`：配置看板（直观查看与快速入口）
- `templates/framework.template.yaml`：框架模板（与 `config.yaml` 绑定）
- `reports/`：报告产物目录（校验、映射、测试追踪、OO/Token/脚本化/双域合规等）

## 使用建议

1. 先改 `config.yaml`（控制开关与约束）。
2. 通过 `agent_principles.yaml` 快速查看“统一原则总表”（含双域合规）。
3. 通过 `docs/config_dashboard.md` 快速确认关键参数。
4. 需要扩展框架时再调整 `docs/agent_framework.md` 与 `templates/framework.template.yaml`。

## 工作区合规检查

- 运行检查：`python workspace_compliance_checker.py --workspace . --report reports/workspace_compliance.md`
- 可选 JSON：`python workspace_compliance_checker.py --json-report .unit_test/workspace_compliance_result.json`

## 生成 Agent 工作区

- 生成工作区：`python agent_workspace_generator.py --target .unit_test/generated_workspace`
- 生成并写报告：`python agent_workspace_generator.py --target .unit_test/generated_workspace --report .unit_test/workspace_generation_result.json`
- 生成后校验：`python workspace_compliance_checker.py --workspace .unit_test/generated_workspace --report .unit_test/generated_workspace/reports/workspace_compliance.md`
