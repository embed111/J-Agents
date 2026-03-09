param(
    [int]$LineCap = 200,
    [switch]$WriteQueue
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$files = @(
    "user_profile/core/thinking-patterns-global.md",
    "user_profile/core/thinking-patterns-domain-requirements.md",
    "user_profile/core/thinking-patterns-domain-collaboration.md",
    "user_profile/core/thinking-patterns-overview.md"
)

$results = @()
foreach ($rel in $files) {
    $full = Join-Path $root $rel
    if (-not (Test-Path $full)) {
        $results += [PSCustomObject]@{
            file = $rel
            lines = -1
            status = "missing"
        }
        continue
    }
    $lines = (Get-Content $full | Measure-Object -Line).Lines
    $status = if ($lines -gt $LineCap) { "over_cap" } else { "ok" }
    $results += [PSCustomObject]@{
        file = $rel
        lines = $lines
        status = $status
    }
}

$results | Format-Table -AutoSize

$over = @($results | Where-Object { $_.status -eq "over_cap" })
if ($WriteQueue) {
    $queuePath = Join-Path $root "user_profile/governance/preference-review-queue.md"
    $body = New-Object System.Collections.Generic.List[string]
    $body.Add("# 偏好超限评审队列")
    $body.Add("")
    $body.Add("- 生成时间: $((Get-Date).ToString("yyyy-MM-dd HH:mm:ss"))")
    $body.Add("- 行数上限: $LineCap")
    $body.Add("")
    if ($over.Count -eq 0) {
        $body.Add("1. 当前无超限文件。")
    } else {
        $body.Add("1. 触发超限评审的文件：")
        $idx = 1
        foreach ($item in $over) {
            $idx++
            $body.Add("$idx. $($item.file) | lines=$($item.lines)")
        }
        $body.Add("")
        $body.Add("2. 处理动作：")
        $body.Add("   1. 评审保留长期偏好核心条目。")
        $body.Add("   2. 其余条目降级到 `user_profile/core/thinking-patterns-short-term.md`。")
        $body.Add("   3. 在 `user_profile/governance/preference-review-log.md` 记录评审结果。")
    }
    Set-Content -Path $queuePath -Value $body -Encoding UTF8
    Write-Host "Queue updated: $queuePath"
}

if ($over.Count -gt 0) {
    Write-Error "Long-term preference cap exceeded in $($over.Count) file(s)."
    exit 2
}

Write-Host "PASS: all long-term preference files <= $LineCap lines."

