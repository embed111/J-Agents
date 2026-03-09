# 验收证据矩阵 - Phase0

## 文档状态（Legacy）
- 状态: `legacy_keep`
- 保留原因: 作为 Phase0 验收证据矩阵模板，仍用于历史结果追溯。
- 当前执行口径:
  - 证据生命周期和截图归档以 `docs/workflow/governance/截图索引与归档规范.md` 为主。
  - 新轮次验收以对应轮次执行提示词要求为准。
- 迁移策略（2026-03-05）:
  - 保留本文档作为历史证据对照。
  - 新增验收矩阵采用独立文件按轮次维护。

- 更新时间: 2026-02-25 10:05 +0800
- 说明: 本表对应本轮 Gate-1~Gate-5；无证据视为未完成。

| Gate | 目标 | 状态 | 证据路径 | 备注 |
|---|---|---|---|---|
| Gate-1 | 聊天结构改造 + 多会话并发 + 等效交互 | pass | `logs/runs/gate-phase0-acceptance-20260225-101322.md` | 含 `five_session_parallel`、`send_interrupt_retry` |
| Gate-2 | 独立 Training Workflow 模块 | pass | `logs/runs/gate-phase0-acceptance-20260225-101322.md`, `src/workflow_app/web_client/*.js` | 队列/详情/计划勾选执行已落地 |
| Gate-3 | 指派分析师 -> 分析输出 -> 计划勾选 -> 执行可见 | pass | `logs/runs/gate-phase0-acceptance-20260225-101322.md` | `event_stages` 含 `assignment/analysis/plan/select/train` |
| Gate-4 | A/B 升级入口下线、默认路由禁用 | pass | `logs/runs/gate-phase0-acceptance-20260225-101322.md`, `scripts/workflow_web_server.py` | `/api/ab/*` 返回 `ab_disabled`，页面无入口 |
| Gate-5 | 文档同步，声明 out-of-scope | pass | `docs/workflow/overview/需求概述.md`, `docs/workflow/requirements/需求详情-训练闭环监控系统-Phase0.md` | 明确本轮 out-of-scope 为 workflow 自升级 |

## 关键日志与数据库路径
1. `logs/events/events-20260225.jsonl`
2. `state/workflow.db`
3. `logs/runs/task-20260225-b427b129.md`
4. `logs/runs/task-20260225-f50bd0f5.md`
5. `logs/runs/task-20260225-04e0af40.md`
6. `logs/runs/task-20260225-cf6792cb.md`
7. `logs/runs/task-20260225-27db6a19.md`

## 截图证据入口
1. 索引文档：`docs/workflow/governance/截图索引与归档规范.md`
2. 截图目录：`docs/workflow/screenshots/`



