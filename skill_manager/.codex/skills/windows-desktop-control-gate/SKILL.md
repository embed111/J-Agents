---
name: windows-desktop-control-gate
description: 为 Windows 自动化仓库补齐“桌面控制申请 + 操作中提示条 + 前台激活 + 留痕”能力。适用于需要发送鼠标/键盘输入、激活窗口、抢前台焦点，但又必须保留人工确认与审计日志的场景。
---

# Windows Desktop Control Gate

## Overview

给当前仓库增加一套本地可落地的 Windows 桌面控制门禁能力。
它覆盖审批弹窗、10 秒默认自动授权、操作中提示条、前台窗口激活、lease 留痕和最小测试闭环。

## When To Use

在以下情况使用本技能：

1. 自动化脚本会发送系统级鼠标或键盘输入。
2. 自动化脚本需要把浏览器、桌面程序或 Docker 窗口抢到前台。
3. 用户要求“先申请控制，再执行，并在屏幕上明确显示正在操作”。
4. 需要把控制申请、授权、释放写入 `workspace_state/control/control-log.jsonl`。

## Workflow

1. 盘点目标仓库，确认它是 Windows 桌面自动化场景，并且允许新增 `scripts/`、`.test/` 与 `workspace_state/`。
2. 运行 `scripts/install_skill.py --workspace-root <target-workspace>`，把脚本复制到目标仓库本地。
3. 在目标业务脚本里引入 `scripts/lib/interactive-control.ps1` 和 `scripts/lib/window-activation.ps1`。
4. 用 `Request-InteractiveControl` 包裹所有系统级输入动作，并在 `finally` 中调用 `Stop-InteractiveControl`。
5. 对需要前台焦点的窗口调用 `Focus-WindowProcess`。
6. 先跑 `powershell -ExecutionPolicy Bypass -File .test/test-control-request.ps1`，再做一次真实安全预览。

## Integration Contract

- **审批门禁**：所有 `SendKeys`、鼠标点击、窗口激活前，先申请控制。
- **默认策略**：等待 10 秒；用户无响应则自动授权，但仍显示审批窗和操作中提示。
- **屏幕提示**：UI 标题统一为“Agent正在操作”。
- **留痕路径**：控制日志固定写入 `workspace_state/control/control-log.jsonl`。
- **资源释放**：一切真实控制流程都要在 `finally` 中执行 `Stop-InteractiveControl`。
- **本地作用域**：只安装到目标仓库，不写入 `~/.codex/skills`。

## Bundled Files

- `scripts/install_skill.py`：把本 skill 的控制脚本安装到任意目标仓库。
- `scripts/control_ui.py`：PySide6 审批窗与“操作中”提示条。
- `scripts/lib/interactive-control.ps1`：控制申请、lease 与日志核心实现。
- `scripts/lib/window-activation.ps1`：前台激活与置顶辅助函数。
- `.test/test-control-request.ps1`：mock 测试脚本，验证请求/授权/释放/过期清理。
- `references/integration.md`：接入代码片段、运行依赖和验证步骤。

## Validation

最低验证顺序：

1. `python .codex/skills/windows-desktop-control-gate/scripts/install_skill.py --workspace-root <target-workspace>`
2. `powershell -ExecutionPolicy Bypass -File <target-workspace>\\.test\\test-control-request.ps1`
3. 在目标仓库做一次真实预览，只展示审批窗与操作中提示条，不直接发送业务输入。
4. 确认目标仓库生成 `workspace_state/control/control-log.jsonl`，且日志包含 `control_requested` 与 `control_released`；mock 测试结果写入 `.test/runs/<run-id>/result.json`。

## Examples

### 为现有自动化仓库接入审批门禁

用户：给这个 Windows 自动化仓库加上桌面控制申请和操作中提示。

执行方式：

```bash
python .codex/skills/windows-desktop-control-gate/scripts/install_skill.py --workspace-root C:\work\my-automation
```

### 在业务脚本里包裹系统输入

用户：这个脚本会打开 Edge 并发送快捷键，帮我加上人工确认。

执行方式：

```powershell
. (Join-Path $PSScriptRoot "lib\\interactive-control.ps1")
. (Join-Path $PSScriptRoot "lib\\window-activation.ps1")

$control = Request-InteractiveControl `
  -OperationName "创建飞书文档" `
  -Details "会激活 Edge 并发送系统输入" `
  -WorkspaceRoot $workspaceRoot `
  -PromptTimeoutSeconds 10

if (-not $control.Approved) { return }

try {
  # 真正的窗口激活与输入动作
} finally {
  Stop-InteractiveControl -ControlSession $control
}
```

### 验证测试脚本

用户：先别真动桌面，先验证控制申请链路是不是完整。

执行方式：

```bash
powershell -ExecutionPolicy Bypass -File C:\work\my-automation\.test\test-control-request.ps1
```
