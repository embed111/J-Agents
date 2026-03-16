[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [switch]$IncludeRoot,
    [switch]$DryRun,
    [int]$RetryCount = 3,
    [int]$RetryDelaySeconds = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

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

$updatedCount = @($results | Where-Object { $_.Status -eq "updated" }).Count
$skippedCount = @($results | Where-Object { $_.Status -like "skipped-*" }).Count
$dryRunCount = @($results | Where-Object { $_.Status -eq "dry-run" }).Count
$failedResults = @($results | Where-Object { $_.Status -eq "failed" })
$failedCount = $failedResults.Count

Write-Host "[SUMMARY] updated=$updatedCount skipped=$skippedCount dry_run=$dryRunCount failed=$failedCount"
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
