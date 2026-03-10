Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not ("NativeWindowActivation" -as [type])) {
  Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class NativeWindowActivation {
  [DllImport("user32.dll")]
  public static extern bool SetForegroundWindow(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern bool BringWindowToTop(IntPtr hWnd);

  [DllImport("user32.dll")]
  public static extern IntPtr GetForegroundWindow();

  [DllImport("user32.dll")]
  public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

  [DllImport("user32.dll")]
  public static extern bool IsIconic(IntPtr hWnd);

  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool SetWindowPos(
    IntPtr hWnd,
    IntPtr hWndInsertAfter,
    int X,
    int Y,
    int cx,
    int cy,
    uint uFlags
  );
}
"@
}

$WindowTopMost = [IntPtr]::new(-1)
$WindowNoTopMost = [IntPtr]::new(-2)
$SetPosFlagsNoMoveNoSize = 0x0001 -bor 0x0002 -bor 0x0040
$ShowRestore = 9
$ShowMaximized = 3

function Wait-ProcessMainWindow {
  param(
    [Parameter(Mandatory = $true)]
    [System.Diagnostics.Process]$Process,

    [int]$TimeoutSeconds = 10
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if ($Process.HasExited) {
      return $null
    }

    $Process.Refresh()
    if ($Process.MainWindowHandle -ne 0) {
      return $Process
    }

    Start-Sleep -Milliseconds 250
  }

  return $null
}

function Focus-WindowProcess {
  param(
    [Parameter(Mandatory = $true)]
    [System.Diagnostics.Process]$WindowProcess,

    [switch]$Maximize,

    [int]$Attempts = 8,

    [int]$DelayMilliseconds = 250
  )

  $shell = New-Object -ComObject WScript.Shell
  $readyProcess = Wait-ProcessMainWindow -Process $WindowProcess
  if (-not $readyProcess) {
    return $false
  }

  for ($attempt = 0; $attempt -lt $Attempts; $attempt += 1) {
    if ($readyProcess.HasExited) {
      return $false
    }

    $readyProcess.Refresh()
    $handle = $readyProcess.MainWindowHandle
    if ($handle -eq 0) {
      Start-Sleep -Milliseconds $DelayMilliseconds
      continue
    }

    if ([NativeWindowActivation]::IsIconic($handle)) {
      [NativeWindowActivation]::ShowWindow($handle, $ShowRestore) | Out-Null
    } elseif ($Maximize.IsPresent) {
      [NativeWindowActivation]::ShowWindow($handle, $ShowMaximized) | Out-Null
    } else {
      [NativeWindowActivation]::ShowWindow($handle, $ShowRestore) | Out-Null
    }

    Start-Sleep -Milliseconds 120
    $null = $shell.AppActivate($readyProcess.Id)
    [NativeWindowActivation]::BringWindowToTop($handle) | Out-Null
    [NativeWindowActivation]::SetForegroundWindow($handle) | Out-Null
    [NativeWindowActivation]::SetWindowPos($handle, $WindowTopMost, 0, 0, 0, 0, $SetPosFlagsNoMoveNoSize) | Out-Null
    Start-Sleep -Milliseconds 100
    [NativeWindowActivation]::SetWindowPos($handle, $WindowNoTopMost, 0, 0, 0, 0, $SetPosFlagsNoMoveNoSize) | Out-Null
    Start-Sleep -Milliseconds $DelayMilliseconds

    if ([NativeWindowActivation]::GetForegroundWindow() -eq $handle) {
      return $true
    }
  }

  return $false
}
