# 执行门禁 - Phase0

## 文档状态（Legacy）
- 状态: `legacy_keep`
- 保留原因: 作为 Phase0 执行门禁基线，仍用于历史门禁追溯。
- 当前执行口径:
  - 以 `docs/workflow/prompts/` 最新执行提示词为主。
  - 本文档用于历史对照，不承载新增门禁规则。
- 迁移策略（2026-03-05）:
  - 不删除历史门禁记录。
  - 新轮次门禁写入对应执行提示词与最新验收文件。

- 更新时间: 2026-02-25 10:05 +0800
- 执行范围: 本轮 Gate-1~Gate-5（聊天结构 / 训练模块 / 过程可见 / 范围收敛 / 文档更新）
- 结论: **本轮 Gate 全部通过**

## Gate-1 聊天结构
- 当前状态: **pass**
- 判定:
  - 页面为微信式结构（左会话列表、右聊天窗、底部输入区）。
  - 支持多会话并发任务执行（跨会话并发 <= 5，同会话串行）。
  - 保留流式增量显示、中断、重试、Enter/Shift+Enter。
- 证据:
  - 命令: `python scripts/acceptance/run_acceptance_workflow_gate.py --root . --host 127.0.0.1 --port 8098`
  - `logs/runs/gate-phase0-acceptance-20260225-101322.md`（`five_session_parallel`、`send_interrupt_retry`）
  - `src/workflow_app/web_client/*.js`
  - `scripts/workflow_web_server.py`

## Gate-2 训练模块
- 当前状态: **pass**
- 判定:
  - 页面存在独立 Training Workflow 模块（队列、详情、计划勾选执行）。
  - 不再是“两个按钮”模式。
- 证据:
  - `logs/runs/gate-phase0-acceptance-20260225-101322.md`（`workflow_chain_visible`）
  - `src/workflow_app/web_client/*.js`
  - `scripts/workflow_web_server.py`

## Gate-3 过程可见
- 当前状态: **pass**
- 判定:
  - 可见完整链路：`assignment -> analysis -> plan -> select -> train`。
  - 事件可通过 `/api/workflows/training/{workflow_id}/events` 回放。
- 证据:
  - `logs/runs/gate-phase0-acceptance-20260225-101322.md`（`workflow_chain_visible` 的 `event_stages`）
  - `state/workflow.db`（`training_workflows`、`training_workflow_events`）

## Gate-4 范围收敛（A/B 下线）
- 当前状态: **pass**
- 判定:
  - 页面无 A/B 升级入口。
  - 默认 API 路由返回禁用（`ab_disabled`），不可直接触发。
- 证据:
  - `logs/runs/gate-phase0-acceptance-20260225-101322.md`（`ab_disabled`）
  - `scripts/workflow_web_server.py`（`AB_FEATURE_ENABLED` 默认关闭）

## Gate-5 文档更新
- 当前状态: **pass**
- 判定:
  - 已同步更新概述与详情，明确本轮 out-of-scope 为 workflow 自升级。
- 证据:
  - `docs/workflow/overview/需求概述.md`
  - `docs/workflow/requirements/需求详情-训练闭环监控系统-Phase0.md`



