# Windows Desktop Control Gate 接入说明

## 适用场景

- 业务脚本要发送 `SendKeys`、鼠标点击或快捷键。
- 业务脚本需要把浏览器或桌面窗口抢到前台。
- 用户要求控制前先审批，并在控制期间始终显示“Agent正在操作”。

## 安装

```bash
python .codex/skills/windows-desktop-control-gate/scripts/install_skill.py --workspace-root C:\path\to\workspace
```

安装后目标仓库至少会得到以下文件：

- `scripts/control_ui.py`
- `scripts/lib/interactive-control.ps1`
- `scripts/lib/window-activation.ps1`
- `scripts/test-control-request.ps1`

## PowerShell 接入范式

```powershell
. (Join-Path $PSScriptRoot "lib\\interactive-control.ps1")
. (Join-Path $PSScriptRoot "lib\\window-activation.ps1")

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$control = Request-InteractiveControl `
  -OperationName "执行桌面自动化" `
  -Details "会激活目标窗口并发送系统输入" `
  -WorkspaceRoot $workspaceRoot `
  -PromptTimeoutSeconds 10

if (-not $control.Approved) {
  return
}

try {
  $process = Start-Process "msedge.exe" -ArgumentList "https://example.com" -PassThru
  Focus-WindowProcess -WindowProcess $process -Maximize | Out-Null

  # 在这里执行 SendKeys / 鼠标 / 业务输入
} finally {
  Stop-InteractiveControl -ControlSession $control
}
```

## 验证步骤

1. 跑 `powershell -ExecutionPolicy Bypass -File scripts/test-control-request.ps1`。
2. 观察 `workspace_state/control/control-log.jsonl` 是否记录：
   - `control_requested`
   - `control_granted` 或 `control_auto_granted`
   - `control_released`
3. 做一次真实安全预览，只展示审批窗和操作中提示，不立刻发送业务输入。

## 运行依赖

- Windows
- PowerShell
- Python 3
- `PySide6`（真实 UI 预览时需要；mock 测试不依赖）

## 安全约束

- 只复用本机当前会话，不保存密码或 Cookie。
- 不允许绕过审批直接发送系统输入。
- 默认 10 秒自动授权仅用于减少阻塞，不等于可以省略屏幕提示。
