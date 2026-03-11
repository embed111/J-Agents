Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "..\scripts\lib\interactive-control.ps1")

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$runId = (Get-Date).ToString("yyyy-MM-ddTHH-mm-ss") + "-control-request-tests"
$runDir = Join-Path $workspaceRoot (".test\runs\" + $runId)
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$script:OriginalInvokeControlApprovalUi = (Get-Command Invoke-ControlApprovalUi).ScriptBlock
$script:OriginalStartControlBannerProcess = (Get-Command Start-ControlBannerProcess).ScriptBlock

function Restore-ControlMocks {
  Set-Item -Path Function:Invoke-ControlApprovalUi -Value $script:OriginalInvokeControlApprovalUi
  Set-Item -Path Function:Start-ControlBannerProcess -Value $script:OriginalStartControlBannerProcess
}

function Set-ControlMocks {
  param(
    [Parameter(Mandatory = $true)]
    [hashtable]$ApprovalResult,

    [int]$BannerPid = 43210,

    [switch]$RejectBannerStart
  )

  $script:MockApprovalResult = $ApprovalResult
  $script:MockBannerPid = $BannerPid

  Set-Item -Path Function:Invoke-ControlApprovalUi -Value {
    param(
      [string]$OperationName,
      [string]$Details = "",
      [int]$PromptTimeoutSeconds = 10
    )

    return [pscustomobject]$script:MockApprovalResult
  }

  if ($RejectBannerStart.IsPresent) {
    Set-Item -Path Function:Start-ControlBannerProcess -Value {
      throw "Start-ControlBannerProcess should not be called in this test."
    }
    return
  }

  Set-Item -Path Function:Start-ControlBannerProcess -Value {
    param(
      [string]$LeasePath,
      [string]$OperationName,
      [string]$Details = ""
    )

    return $script:MockBannerPid
  }
}

function New-IsolatedWorkspace {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name
  )

  $root = Join-Path $runDir $Name
  New-Item -ItemType Directory -Force -Path $root | Out-Null
  return $root
}

function Get-ControlLogEntries {
  param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspacePath
  )

  $logPath = Join-Path $WorkspacePath "workspace_state\control\control-log.jsonl"
  if (-not (Test-Path $logPath)) {
    return @()
  }

  return @(Get-Content -Path $logPath | Where-Object { $_.Trim() } | ForEach-Object { $_ | ConvertFrom-Json })
}

function Assert-True {
  param(
    [Parameter(Mandatory = $true)]
    [bool]$Condition,

    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  if (-not $Condition) {
    throw $Message
  }
}

function Assert-Equal {
  param(
    [Parameter(Mandatory = $true)]
    $Actual,

    [Parameter(Mandatory = $true)]
    $Expected,

    [Parameter(Mandatory = $true)]
    [string]$Message
  )

  if ($Actual -ne $Expected) {
    throw "$Message`nExpected: $Expected`nActual: $Actual"
  }
}

function Invoke-TestCase {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Name,

    [Parameter(Mandatory = $true)]
    [scriptblock]$Body
  )

  $startedAt = Get-Date
  try {
    & $Body
    return [pscustomobject]@{
      name = $Name
      status = "passed"
      startedAt = $startedAt.ToString("o")
      finishedAt = (Get-Date).ToString("o")
    }
  } catch {
    return [pscustomobject]@{
      name = $Name
      status = "failed"
      startedAt = $startedAt.ToString("o")
      finishedAt = (Get-Date).ToString("o")
      error = ($_ | Out-String).Trim()
    }
  } finally {
    Restore-ControlMocks
  }
}

$results = @()

$results += Invoke-TestCase -Name "denied_request_blocks_and_logs" -Body {
  $workspace = New-IsolatedWorkspace -Name "denied-request"
  Set-ControlMocks -ApprovalResult @{
    approved = $false
    decision = "cancelled"
    autoApproved = $false
  } -RejectBannerStart

  $session = Request-InteractiveControl `
    -OperationName "拒绝测试" `
    -Details "测试用户拒绝路径" `
    -WorkspaceRoot $workspace `
    -PromptTimeoutSeconds 10

  Assert-True (-not $session.Approved) "拒绝路径下 Approved 应为 false。"
  Assert-Equal $session.ApprovalDecision "cancelled" "拒绝路径下 ApprovalDecision 不正确。"

  $controlRoot = Join-Path $workspace "workspace_state\control"
  $leases = @(Get-ChildItem -Path $controlRoot -Filter "active-control-*.json" -ErrorAction SilentlyContinue)
  Assert-Equal $leases.Count 0 "拒绝路径不应生成 lease 文件。"

  $entries = Get-ControlLogEntries -WorkspacePath $workspace
  Assert-Equal $entries.Count 2 "拒绝路径应写入 2 条日志。"
  Assert-Equal $entries[0].event "control_requested" "第一条日志应为 control_requested。"
  Assert-Equal $entries[1].event "control_denied" "第二条日志应为 control_denied。"
}

$results += Invoke-TestCase -Name "approved_request_writes_lease_and_releases" -Body {
  $workspace = New-IsolatedWorkspace -Name "approved-request"
  Set-ControlMocks -ApprovalResult @{
    approved = $true
    decision = "approved"
    autoApproved = $false
    targetScreen = @{
      name = "Primary"
      left = 0
      top = 0
      width = 1920
      height = 1080
    }
  } -BannerPid 54321

  $session = Request-InteractiveControl `
    -OperationName "批准测试" `
    -Details "测试正常批准路径" `
    -WorkspaceRoot $workspace `
    -PromptTimeoutSeconds 10

  Assert-True $session.Approved "批准路径下 Approved 应为 true。"
  Assert-Equal $session.BannerPid 54321 "BannerPid 未使用 mock 返回值。"
  Assert-True (Test-Path $session.LeasePath) "批准路径应写入 lease 文件。"

  $lease = Get-Content -Raw -Path $session.LeasePath | ConvertFrom-Json
  Assert-Equal $lease.operationName "批准测试" "lease 中 operationName 不正确。"
  Assert-Equal $lease.targetScreen.name "Primary" "lease 中 targetScreen 未写入。"

  Stop-InteractiveControl -ControlSession $session
  Assert-True (-not (Test-Path $session.LeasePath)) "释放后应删除 lease 文件。"

  $entries = Get-ControlLogEntries -WorkspacePath $workspace
  Assert-Equal $entries.Count 3 "批准路径应写入 3 条日志。"
  Assert-Equal $entries[1].event "control_granted" "第二条日志应为 control_granted。"
  Assert-Equal $entries[2].event "control_released" "第三条日志应为 control_released。"
}

$results += Invoke-TestCase -Name "auto_approved_request_logs_auto_granted" -Body {
  $workspace = New-IsolatedWorkspace -Name "auto-approved-request"
  Set-ControlMocks -ApprovalResult @{
    approved = $true
    decision = "auto_approved"
    autoApproved = $true
  } -BannerPid 65432

  $session = Request-InteractiveControl `
    -OperationName "自动授权测试" `
    -Details "测试 auto approve 路径" `
    -WorkspaceRoot $workspace `
    -PromptTimeoutSeconds 10

  Assert-True $session.AutoApproved "自动授权路径下 AutoApproved 应为 true。"
  Stop-InteractiveControl -ControlSession $session

  $entries = Get-ControlLogEntries -WorkspacePath $workspace
  Assert-Equal $entries[1].event "control_auto_granted" "第二条日志应为 control_auto_granted。"
}

$results += Invoke-TestCase -Name "stale_lease_cleanup_removes_invalid_and_expired_entries" -Body {
  $workspace = New-IsolatedWorkspace -Name "stale-cleanup"
  $stateRoot = Get-ControlStateRoot -WorkspaceRoot $workspace

  $invalidLease = Join-Path $stateRoot "active-control-invalid.json"
  "{invalid json" | Set-Content -Path $invalidLease -Encoding UTF8

  $missingOwnerLease = Join-Path $stateRoot "active-control-missing-owner.json"
  @{
    requestId = "missing-owner"
    processId = 999999
    approvedAt = (Get-Date).ToString("o")
  } | ConvertTo-Json | Set-Content -Path $missingOwnerLease -Encoding UTF8

  $expiredLease = Join-Path $stateRoot "active-control-expired.json"
  @{
    requestId = "expired"
    processId = $PID
    approvedAt = (Get-Date).AddHours(-2).ToString("o")
  } | ConvertTo-Json | Set-Content -Path $expiredLease -Encoding UTF8

  Remove-StaleControlLeases -StateRoot $stateRoot -MaxAgeMinutes 30

  $remaining = @(Get-ChildItem -Path $stateRoot -Filter "active-control-*.json" -ErrorAction SilentlyContinue)
  Assert-Equal $remaining.Count 0 "清理后不应残留 stale lease 文件。"

  $entries = Get-ControlLogEntries -WorkspacePath $workspace
  Assert-Equal $entries.Count 3 "stale cleanup 应记录 3 条日志。"
  $reasons = @($entries | ForEach-Object { $_.detail.reason })
  Assert-True ($reasons -contains "invalid_lease") "应记录 invalid_lease。"
  Assert-True ($reasons -contains "owner_process_missing") "应记录 owner_process_missing。"
  Assert-True ($reasons -contains "lease_expired") "应记录 lease_expired。"
}

$summary = [pscustomobject]@{
  status = if (@($results | Where-Object { $_.status -ne "passed" }).Count -eq 0) { "passed" } else { "failed" }
  createdAt = (Get-Date).ToString("o")
  runDir = $runDir
  testCount = $results.Count
  passedCount = @($results | Where-Object { $_.status -eq "passed" }).Count
  failedCount = @($results | Where-Object { $_.status -ne "passed" }).Count
  results = $results
}

$summary | ConvertTo-Json -Depth 6 | Set-Content -Path (Join-Path $runDir "result.json") -Encoding UTF8
$summary | ConvertTo-Json -Depth 6

if ($summary.status -ne "passed") {
  exit 1
}
