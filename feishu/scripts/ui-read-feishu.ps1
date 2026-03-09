param(
  [Parameter(Mandatory = $true)]
  [string]$Url,

  [int]$WaitSeconds = 12
)

Add-Type -AssemblyName System.Windows.Forms

$edgePath = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'

if (-not (Test-Path $edgePath)) {
  throw "未找到 Edge: $edgePath"
}

Set-Clipboard -Value ' '
Start-Process -FilePath $edgePath -ArgumentList @('--new-window', $Url) | Out-Null
Start-Sleep -Seconds $WaitSeconds

$shell = New-Object -ComObject WScript.Shell
$targetWindow = Get-Process msedge -ErrorAction SilentlyContinue |
  Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle } |
  Sort-Object StartTime -Descending |
  Select-Object -First 1

$activated = $false

if ($targetWindow) {
  $activated = $shell.AppActivate($targetWindow.Id)
}

if (-not $activated) {
  $activated = $shell.AppActivate('Microsoft Edge')
}

if (-not $activated) {
  throw '未能激活 Edge 窗口。'
}

Start-Sleep -Milliseconds 800
[System.Windows.Forms.SendKeys]::SendWait('^a')
Start-Sleep -Milliseconds 500
[System.Windows.Forms.SendKeys]::SendWait('^c')
Start-Sleep -Milliseconds 1200

$text = Get-Clipboard -Raw

if (-not $text) {
  throw '剪贴板为空，未能读取页面内容。'
}

$normalized = $text -replace "\r\n", "`n"

@{
  url = $Url
  captured_at = (Get-Date).ToString('s')
  text_length = $normalized.Length
  preview = if ($normalized.Length -gt 1200) { $normalized.Substring(0, 1200) } else { $normalized }
  raw = $normalized
} | ConvertTo-Json -Depth 4
