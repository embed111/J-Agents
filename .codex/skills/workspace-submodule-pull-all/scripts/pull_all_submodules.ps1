[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [switch]$IncludeRoot,
    [switch]$DryRun,
    [switch]$SaveMemoryAfterPull,
    [string]$MemorySummary,
    [string]$MemoryDetails,
    [int]$RetryCount = 3,
    [int]$RetryDelaySeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-CodexScriptPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,

        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )

    return Join-Path (Join-Path $WorkspaceRoot ".codex") $RelativePath
}

function Join-Labels {
    param(
        [AllowEmptyCollection()]
        [object[]]$Items
    )

    $labels = @(
        $Items |
            Where-Object { $_ } |
            ForEach-Object { $_.ToString().Trim() } |
            Where-Object { $_ }
    )

    if ($labels.Count -eq 0) {
        return "none"
    }

    return ($labels -join ", ")
}

function Invoke-MemoryCheckpoint {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,

        [Parameter(Mandatory = $true)]
        [string]$Summary,

        [string]$Details,

        [switch]$DryRun
    )

    $ensureScript = Get-CodexScriptPath -WorkspaceRoot $WorkspaceRoot -RelativePath "scripts\ensure_memory_context.ps1"
    $archiveScript = Get-CodexScriptPath -WorkspaceRoot $WorkspaceRoot -RelativePath "scripts\archive_memory.ps1"
    $appendScript = Get-CodexScriptPath -WorkspaceRoot $WorkspaceRoot -RelativePath "scripts\append_daily_memory.ps1"

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would save memory after pull via .codex scripts."
        return
    }

    foreach ($scriptPath in @($ensureScript, $archiveScript, $appendScript)) {
        if (-not (Test-Path -LiteralPath $scriptPath)) {
            throw "Required memory script is missing: $scriptPath"
        }
    }

    & $ensureScript -WorkspaceRoot $WorkspaceRoot | Out-Host
    & $archiveScript -WorkspaceRoot $WorkspaceRoot | Out-Host
    & $appendScript -WorkspaceRoot $WorkspaceRoot -Summary $Summary -Details $Details | Out-Host

    Write-Host "[OK] Saved memory after pull."
}

function Quote-ProcessArgument {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [switch]$AllowFailure,

        [switch]$Quiet
    )

    $allArguments = @("-c", "http.version=HTTP/1.1", "-C", $RepoRoot) + $Arguments
    $argumentString = ($allArguments | ForEach-Object { Quote-ProcessArgument -Value $_ }) -join " "

    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = "git"
    $startInfo.Arguments = $argumentString
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $startInfo
    $null = $process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    $lines = @()
    if ($stdout) {
        $lines += @($stdout -split "`r?`n" | Where-Object { $_ -ne "" })
    }
    if ($stderr) {
        $lines += @($stderr -split "`r?`n" | Where-Object { $_ -ne "" })
    }

    if ((-not $Quiet) -and $lines.Count -gt 0) {
        $lines | ForEach-Object { Write-Host $_ }
    }

    if ((-not $AllowFailure) -and $process.ExitCode -ne 0) {
        $renderedOutput = if ($lines.Count -gt 0) {
            $lines -join [Environment]::NewLine
        } else {
            "(no git output)"
        }
        throw "git $($Arguments -join ' ') failed in '$RepoRoot' with exit code $($process.ExitCode).`n$renderedOutput"
    }

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Output   = $lines
    }
}

function Resolve-WorkspaceGitRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath
    )

    $resolvedCandidate = (Resolve-Path -LiteralPath $CandidatePath).Path
    $result = Invoke-Git -RepoRoot $resolvedCandidate -Arguments @("rev-parse", "--show-toplevel") -Quiet
    $repoRoot = ($result.Output | Select-Object -First 1).Trim()
    if (-not $repoRoot) {
        throw "Unable to resolve the top-level Git repository for '$CandidatePath'."
    }
    return (Resolve-Path -LiteralPath $repoRoot).Path
}

function Get-SubmodulePaths {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("submodule", "status", "--recursive") -AllowFailure -Quiet
    if ($result.ExitCode -ne 0) {
        throw "Unable to enumerate submodules from '$RepoRoot'."
    }

    $paths = New-Object System.Collections.Generic.List[string]
    foreach ($line in $result.Output) {
        $trimmed = $line.Trim()
        if (-not $trimmed) {
            continue
        }

        $parts = $trimmed -split "\s+"
        if ($parts.Count -lt 2) {
            continue
        }

        $paths.Add($parts[1])
    }

    return $paths | Sort-Object -Unique
}

function Test-RepoDirty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("status", "--porcelain") -Quiet
    return $result.Output.Count -gt 0
}

function Get-CurrentBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("branch", "--show-current") -Quiet
    $firstLine = $result.Output | Select-Object -First 1
    if ($null -eq $firstLine) {
        return $null
    }

    $branch = $firstLine.Trim()
    if ($branch) {
        return $branch
    }
    return $null
}

function Get-UpstreamRef {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") -AllowFailure -Quiet
    if ($result.ExitCode -eq 0) {
        $firstLine = $result.Output | Select-Object -First 1
        if ($null -eq $firstLine) {
            return $null
        }

        return $firstLine.Trim()
    }
    if ($result.ExitCode -eq 128) {
        return $null
    }
    throw "Unable to resolve upstream branch for '$RepoRoot'."
}

function Get-RemoteHeadRef {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("symbolic-ref", "refs/remotes/origin/HEAD") -AllowFailure -Quiet
    if ($result.ExitCode -eq 0) {
        $firstLine = $result.Output | Select-Object -First 1
        if ($null -eq $firstLine) {
            return $null
        }

        $remoteHeadRef = $firstLine.Trim()
        if ($remoteHeadRef) {
            return $remoteHeadRef
        }
    }

    return $null
}

function Invoke-RepoPull {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [switch]$DryRun,

        [int]$RetryCount,

        [int]$RetryDelaySeconds
    )

    $dirty = Test-RepoDirty -RepoRoot $RepoRoot
    if ($dirty) {
        Write-Host "[SKIP] $Label has local changes."
        return [pscustomobject]@{ Label = $Label; Status = "skipped-dirty" }
    }

    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    $upstream = Get-UpstreamRef -RepoRoot $RepoRoot

    if ($DryRun) {
        if ($upstream) {
            Write-Host "[DRY-RUN] Would fetch and pull $Label via $upstream."
            return [pscustomobject]@{ Label = $Label; Status = "dry-run" }
        }

        if ($branch) {
            Write-Host "[SKIP] $Label branch '$branch' has no upstream."
            return [pscustomobject]@{ Label = $Label; Status = "skipped-no-upstream" }
        }

        Write-Host "[DRY-RUN] Would fetch and advance detached HEAD for $Label to origin/HEAD."
        return [pscustomobject]@{ Label = $Label; Status = "dry-run" }
    }

    $attempt = 0
    while ($attempt -lt $RetryCount) {
        $attempt += 1
        try {
            Invoke-Git -RepoRoot $RepoRoot -Arguments @("fetch", "--all", "--prune") -Quiet | Out-Null

            if ($upstream) {
                Invoke-Git -RepoRoot $RepoRoot -Arguments @("pull", "--ff-only") -Quiet | Out-Null
            } else {
                if ($branch) {
                    Write-Host "[SKIP] $Label branch '$branch' has no upstream."
                    return [pscustomobject]@{ Label = $Label; Status = "skipped-no-upstream" }
                }

                $remoteHeadRef = Get-RemoteHeadRef -RepoRoot $RepoRoot
                if (-not $remoteHeadRef) {
                    Write-Host "[SKIP] $Label detached HEAD has no origin/HEAD."
                    return [pscustomobject]@{ Label = $Label; Status = "skipped-detached" }
                }

                Invoke-Git -RepoRoot $RepoRoot -Arguments @("checkout", "--detach", $remoteHeadRef) -Quiet | Out-Null
            }

            Write-Host "[OK] Updated $Label"
            return [pscustomobject]@{ Label = $Label; Status = "updated" }
        } catch {
            if ($attempt -ge $RetryCount) {
                Write-Host "[FAIL] $Label pull failed after $attempt attempt(s)."
                return [pscustomobject]@{
                    Label   = $Label
                    Status  = "failed"
                    Message = $_.Exception.Message
                }
            }

            Write-Host "[RETRY] $Label pull failed on attempt $attempt/$RetryCount. Waiting $RetryDelaySeconds second(s)."
            Start-Sleep -Seconds $RetryDelaySeconds
        }
    }
}

$workspaceRoot = Resolve-WorkspaceGitRoot -CandidatePath $WorkspaceRoot
Write-Host "[INFO] Workspace root: $workspaceRoot"

if ($DryRun) {
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot submodule sync --recursive"
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot submodule update --init --recursive"
} else {
    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("submodule", "sync", "--recursive") -Quiet | Out-Null
    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("submodule", "update", "--init", "--recursive") -Quiet | Out-Null
}

$results = New-Object System.Collections.Generic.List[object]

if ($IncludeRoot) {
    $results.Add((Invoke-RepoPull -RepoRoot $workspaceRoot -Label "." -DryRun:$DryRun))
}

$submodulePaths = @(Get-SubmodulePaths -RepoRoot $workspaceRoot)
Write-Host "[INFO] Recursive submodule count: $($submodulePaths.Count)"

foreach ($relativePath in $submodulePaths) {
    $repoRoot = Join-Path $workspaceRoot $relativePath
    $results.Add((Invoke-RepoPull -RepoRoot $repoRoot -Label $relativePath -DryRun:$DryRun -RetryCount $RetryCount -RetryDelaySeconds $RetryDelaySeconds))
}

$validResults = @(
    $results |
        Where-Object {
            $_ -and
            $_.PSObject -and
            $_.PSObject.Properties["Status"]
        }
)
$invalidResults = @($results | Where-Object { -not ($_ -and $_.PSObject -and $_.PSObject.Properties["Status"]) })
if ($invalidResults.Count -gt 0) {
    Write-Host "[WARN] Ignoring $($invalidResults.Count) unexpected pull result object(s) during summary."
}

$updatedCount = @($validResults | Where-Object { $_.Status -eq "updated" }).Count
$skippedCount = @($validResults | Where-Object { $_.Status -like "skipped-*" }).Count
$dryRunCount = @($validResults | Where-Object { $_.Status -eq "dry-run" }).Count
$failedResults = @($validResults | Where-Object { $_.Status -eq "failed" })
$failedCount = $failedResults.Count

Write-Host "[SUMMARY] updated=$updatedCount skipped=$skippedCount dry_run=$dryRunCount failed=$failedCount"

if ($SaveMemoryAfterPull) {
    $updatedLabels = Join-Labels -Items @($validResults | Where-Object { $_.Status -eq "updated" } | ForEach-Object { $_.Label })
    $skippedLabels = Join-Labels -Items @($validResults | Where-Object { $_.Status -like "skipped-*" } | ForEach-Object { $_.Label })
    $failedLabels = Join-Labels -Items @($failedResults | ForEach-Object { $_.Label })
    $defaultSummary = "代码拉取完成：include_root=$($IncludeRoot.IsPresent) submodules=$($submodulePaths.Count) updated=$updatedCount skipped=$skippedCount failed=$failedCount"
    $defaultDetails = @"
更新仓库：$updatedLabels
跳过仓库：$skippedLabels
失败仓库：$failedLabels
使用技能：workspace-submodule-pull-all
"@

    Invoke-MemoryCheckpoint -WorkspaceRoot $workspaceRoot -Summary $(if ($MemorySummary) { $MemorySummary } else { $defaultSummary }) -Details $(if ($MemoryDetails) { $MemoryDetails } else { $defaultDetails }) -DryRun:$DryRun
}

if ($failedCount -gt 0) {
    foreach ($failed in $failedResults) {
        Write-Host "[FAILED-REPO] $($failed.Label)"
        if ($failed.PSObject.Properties.Name -contains "Message") {
            Write-Host $failed.Message
        }
    }
    exit 1
}

Write-Host "[NOTE] Successful submodule pulls may leave the root repo dirty because gitlinks changed."
