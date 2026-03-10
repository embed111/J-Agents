Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ControlStateRoot {
  param(
    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot
  )

  $resolvedWorkspace = (Resolve-Path $WorkspaceRoot).Path
  $stateRoot = Join-Path $resolvedWorkspace "workspace_state\control"
  New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null
  return $stateRoot
}

function Write-ControlLogEntry {
  param(
    [Parameter(Mandatory = $true)]
    [string]$StateRoot,

    [Parameter(Mandatory = $true)]
    [string]$Event,

    [Parameter(Mandatory = $true)]
    [hashtable]$Detail
  )

  $logPath = Join-Path $StateRoot "control-log.jsonl"
  $entry = [ordered]@{
    timestamp = (Get-Date).ToString("o")
    event = $Event
    detail = $Detail
  }

  Add-Content -Path $logPath -Encoding UTF8 -Value ($entry | ConvertTo-Json -Compress)
}

function Remove-StaleControlLeases {
  param(
    [Parameter(Mandatory = $true)]
    [string]$StateRoot,

    [int]$MaxAgeMinutes = 30
  )

  $cutoff = (Get-Date).AddMinutes(-1 * $MaxAgeMinutes)
  $leaseFiles = Get-ChildItem -Path $StateRoot -Filter "active-control-*.json" -ErrorAction SilentlyContinue

  foreach ($leaseFile in $leaseFiles) {
    $reason = $null
    $requestId = $leaseFile.BaseName -replace "^active-control-", ""

    try {
      $lease = Get-Content -Raw -Path $leaseFile.FullName | ConvertFrom-Json
      $approvedAt =
        if ($lease.approvedAt) {
          [datetime]$lease.approvedAt
        } else {
          $leaseFile.LastWriteTime
        }

      $processAlive =
        if ($lease.processId) {
          [bool](Get-Process -Id ([int]$lease.processId) -ErrorAction SilentlyContinue)
        } else {
          $false
        }

      if (-not $processAlive) {
        $reason = "owner_process_missing"
      } elseif ($approvedAt -lt $cutoff) {
        $reason = "lease_expired"
      }
    } catch {
      $reason = "invalid_lease"
    }

    if (-not $reason) {
      continue
    }

    Remove-Item -Path $leaseFile.FullName -Force -ErrorAction SilentlyContinue

    Write-ControlLogEntry -StateRoot $StateRoot -Event "control_lease_cleaned" -Detail @{
      requestId = $requestId
      leasePath = $leaseFile.FullName
      reason = $reason
      ui = "pyside6"
    }
  }
}

function Get-ControlUiScriptPath {
  return (Join-Path (Split-Path $PSScriptRoot -Parent) "control_ui.py")
}

function Get-PythonwPath {
  $pythonPath = (Get-Command python -ErrorAction Stop).Source
  $candidate = Join-Path (Split-Path $pythonPath -Parent) "pythonw.exe"

  if (Test-Path $candidate) {
    return $candidate
  }

  $command = Get-Command pythonw -ErrorAction SilentlyContinue
  if ($command) {
    return $command.Source
  }

  return $pythonPath
}

function Invoke-ControlApprovalUi {
  param(
    [Parameter(Mandatory = $true)]
    [string]$OperationName,

    [string]$Details = "",

    [int]$PromptTimeoutSeconds = 10
  )

  $scriptPath = Get-ControlUiScriptPath
  $raw = & python -X utf8 $scriptPath approval `
    --operation-name $OperationName `
    --details $Details `
    --timeout $PromptTimeoutSeconds

  if (-not $raw) {
    throw "PySide6 审批窗没有返回结果。"
  }

  return ($raw | ConvertFrom-Json)
}

function Start-ControlBannerProcess {
  param(
    [Parameter(Mandatory = $true)]
    [string]$LeasePath,

    [Parameter(Mandatory = $true)]
    [string]$OperationName,

    [string]$Details = ""
  )

  $pythonwPath = Get-PythonwPath
  $scriptPath = Get-ControlUiScriptPath
  $argumentList = @(
    "-X", "utf8",
    $scriptPath,
    "banner",
    "--lease-path", $LeasePath,
    "--operation-name", $OperationName,
    "--details", $Details
  )

  $process = Start-Process -FilePath $pythonwPath -ArgumentList $argumentList -PassThru
  return $process.Id
}

function Request-InteractiveControl {
  param(
    [Parameter(Mandatory = $true)]
    [string]$OperationName,

    [string]$Details = "",

    [Parameter(Mandatory = $true)]
    [string]$WorkspaceRoot,

    [int]$PromptTimeoutSeconds = 10
  )

  $stateRoot = Get-ControlStateRoot -WorkspaceRoot $WorkspaceRoot
  Remove-StaleControlLeases -StateRoot $stateRoot
  $requestId = [guid]::NewGuid().ToString()

  Write-ControlLogEntry -StateRoot $stateRoot -Event "control_requested" -Detail @{
    requestId = $requestId
    operationName = $OperationName
    details = $Details
    processId = $PID
    promptTimeoutSeconds = $PromptTimeoutSeconds
    timeoutPolicy = "auto_approve"
    ui = "pyside6"
  }

  $approvalResult = Invoke-ControlApprovalUi `
    -OperationName $OperationName `
    -Details $Details `
    -PromptTimeoutSeconds $PromptTimeoutSeconds

  if (-not $approvalResult.approved) {
    Write-ControlLogEntry -StateRoot $stateRoot -Event "control_denied" -Detail @{
      requestId = $requestId
      operationName = $OperationName
      processId = $PID
      decision = [string]$approvalResult.decision
      ui = "pyside6"
    }

    return [pscustomobject]@{
      Approved = $false
      Reason = "用户未授权本次系统级鼠标/键盘控制，操作已取消。"
      RequestId = $requestId
      StateRoot = $stateRoot
      ApprovalDecision = [string]$approvalResult.decision
    }
  }

  $leasePath = Join-Path $stateRoot ("active-control-{0}.json" -f $requestId)
  $lease = [ordered]@{
    requestId = $requestId
    operationName = $OperationName
    details = $Details
    approvedAt = (Get-Date).ToString("o")
    processId = $PID
    host = $env:COMPUTERNAME
    user = $env:USERNAME
    ui = "pyside6"
  }
  if ($approvalResult.PSObject.Properties.Name -contains "targetScreen" -and $approvalResult.targetScreen) {
    $lease.targetScreen = $approvalResult.targetScreen
  }
  Set-Content -Path $leasePath -Encoding UTF8 -Value ($lease | ConvertTo-Json -Depth 4)

  $bannerPid = Start-ControlBannerProcess -LeasePath $leasePath -OperationName $OperationName -Details $Details
  $grantEvent =
    if ($approvalResult.autoApproved) {
      "control_auto_granted"
    } else {
      "control_granted"
    }

  Write-ControlLogEntry -StateRoot $stateRoot -Event $grantEvent -Detail @{
    requestId = $requestId
    operationName = $OperationName
    processId = $PID
    bannerPid = $bannerPid
    leasePath = $leasePath
    decision = [string]$approvalResult.decision
    ui = "pyside6"
  }

  return [pscustomobject]@{
    Approved = $true
    AutoApproved = [bool]$approvalResult.autoApproved
    ApprovalDecision = [string]$approvalResult.decision
    RequestId = $requestId
    LeasePath = $leasePath
    BannerPid = $bannerPid
    OperationName = $OperationName
    StateRoot = $stateRoot
  }
}

function Stop-InteractiveControl {
  param(
    [Parameter(Mandatory = $true)]
    $ControlSession
  )

  $leasePath = [string]$ControlSession.LeasePath
  $stateRoot =
    if ($ControlSession.StateRoot) {
      [string]$ControlSession.StateRoot
    } elseif ($leasePath) {
      Split-Path -Parent $leasePath
    } else {
      ""
    }

  if ($leasePath -and (Test-Path $leasePath)) {
    if ($ControlSession.BannerPid) {
      Stop-Process -Id ([int]$ControlSession.BannerPid) -Force -ErrorAction SilentlyContinue
    }

    for ($attempt = 0; $attempt -lt 5; $attempt += 1) {
      Remove-Item -Path $leasePath -Force -ErrorAction SilentlyContinue
      if (-not (Test-Path $leasePath)) {
        break
      }
      Start-Sleep -Milliseconds 150
    }
  } elseif ($ControlSession.BannerPid) {
    Stop-Process -Id ([int]$ControlSession.BannerPid) -Force -ErrorAction SilentlyContinue
  }

  if ($stateRoot) {
    Write-ControlLogEntry -StateRoot $stateRoot -Event "control_released" -Detail @{
      requestId = [string]$ControlSession.RequestId
      operationName = [string]$ControlSession.OperationName
      processId = $PID
      bannerPid = [int]$ControlSession.BannerPid
      ui = "pyside6"
    }
  }
}
