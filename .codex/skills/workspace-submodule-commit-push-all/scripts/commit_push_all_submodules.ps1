[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [string]$Message,
    [string]$RootMessage,
    [string]$Remote = "origin",
    [switch]$NoPush,
    [switch]$DryRun
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

    $allArguments = @("-C", $RepoRoot) + $Arguments
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

    return $paths | Sort-Object { ($_ -split "[\\/]").Count } -Descending
}

function Test-RepoDirty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("status", "--porcelain") -Quiet
    return $result.Output.Count -gt 0
}

function Test-RepoHasHead {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    return (Invoke-Git -RepoRoot $RepoRoot -Arguments @("rev-parse", "--verify", "HEAD") -AllowFailure -Quiet).ExitCode -eq 0
}

function Test-StagedChanges {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("diff", "--cached", "--quiet", "--exit-code") -AllowFailure -Quiet
    if ($result.ExitCode -eq 0) {
        return $false
    }
    if ($result.ExitCode -eq 1) {
        return $true
    }
    throw "Unable to determine whether staged changes exist in '$RepoRoot'."
}

function Get-CurrentBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("branch", "--show-current") -Quiet
    $branchLine = $result.Output | Select-Object -First 1
    if (-not $branchLine) {
        return $null
    }

    $branch = $branchLine.Trim()
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
        return (($result.Output | Select-Object -First 1).Trim())
    }
    if ($result.ExitCode -eq 128) {
        return $null
    }
    throw "Unable to resolve upstream branch for '$RepoRoot'."
}

function Assert-RemoteExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Remote
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("remote", "get-url", $Remote) -AllowFailure -Quiet
    if ($result.ExitCode -ne 0) {
        throw "Git remote '$Remote' does not exist in '$RepoRoot'."
    }
}

function Get-AheadCount {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $upstream = Get-UpstreamRef -RepoRoot $RepoRoot
    if (-not $upstream) {
        return $null
    }

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("rev-list", "--count", "@{u}..HEAD") -Quiet
    return [int](($result.Output | Select-Object -First 1).Trim())
}

function Push-Repo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$Remote
    )

    $upstream = Get-UpstreamRef -RepoRoot $RepoRoot
    if ($upstream) {
        $aheadCount = Get-AheadCount -RepoRoot $RepoRoot
        if ($aheadCount -le 0) {
            Write-Host "[SKIP] $Label has nothing to push."
            return [pscustomobject]@{ Label = $Label; Status = "push-skipped" }
        }

        Invoke-Git -RepoRoot $RepoRoot -Arguments @("push") -Quiet | Out-Null
        Write-Host "[OK] Pushed $Label via $upstream"
        return [pscustomobject]@{ Label = $Label; Status = "pushed" }
    }

    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    if (-not $branch) {
        throw "$Label is in detached HEAD; push target is ambiguous."
    }

    Assert-RemoteExists -RepoRoot $RepoRoot -Remote $Remote
    Invoke-Git -RepoRoot $RepoRoot -Arguments @("push", "-u", $Remote, $branch) -Quiet | Out-Null
    Write-Host "[OK] Pushed $Label to $Remote/$branch"
    return [pscustomobject]@{ Label = $Label; Status = "pushed" }
}

function Invoke-RepoCommitAndPush {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$CommitMessage,

        [Parameter(Mandatory = $true)]
        [string]$Remote,

        [switch]$NoPush,

        [switch]$DryRun
    )

    $dirty = Test-RepoDirty -RepoRoot $RepoRoot
    $hasHead = Test-RepoHasHead -RepoRoot $RepoRoot
    $upstream = Get-UpstreamRef -RepoRoot $RepoRoot
    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    $aheadCount = if ($upstream) { Get-AheadCount -RepoRoot $RepoRoot } else { $null }
    $pushRequired = if ($NoPush) {
        $false
    } elseif ($dirty -or (-not $hasHead)) {
        $true
    } elseif ($upstream) {
        $aheadCount -gt 0
    } else {
        $true
    }

    if ($DryRun) {
        if ($dirty -or (-not $hasHead)) {
            Write-Host "[DRY-RUN] Would commit $Label with message '$CommitMessage'."
        } else {
            Write-Host "[DRY-RUN] $Label has no new worktree changes."
        }

        if ($NoPush) {
            Write-Host "[DRY-RUN] Push disabled for $Label."
        } elseif ($pushRequired) {
            if ($upstream) {
                Write-Host "[DRY-RUN] Would push $Label via $upstream."
            } elseif ($branch) {
                Write-Host "[DRY-RUN] Would push $Label to $Remote/$branch and set upstream."
            } else {
                Write-Host "[DRY-RUN] $Label is detached HEAD; push would fail."
            }
        } else {
            Write-Host "[DRY-RUN] $Label has nothing to push."
        }

        return [pscustomobject]@{
            Label      = $Label
            Committed  = $dirty -or (-not $hasHead)
            Pushed     = $pushRequired -and (-not $NoPush)
            CommitHash = $null
            PushStatus = if ($pushRequired -and (-not $NoPush)) { "would-push" } else { "skip" }
        }
    }

    $commitCreated = $false
    $commitHash = $null

    Invoke-Git -RepoRoot $RepoRoot -Arguments @("add", "-A") -Quiet | Out-Null
    $stagedChanges = Test-StagedChanges -RepoRoot $RepoRoot
    if ((-not $hasHead) -or $stagedChanges) {
        Invoke-Git -RepoRoot $RepoRoot -Arguments @("commit", "-m", $CommitMessage) -Quiet | Out-Null
        $commitCreated = $true
        $commitHash = ((Invoke-Git -RepoRoot $RepoRoot -Arguments @("rev-parse", "--short", "HEAD") -Quiet).Output | Select-Object -First 1).Trim()
        Write-Host "[OK] Committed $Label -> $commitHash"
    } else {
        Write-Host "[SKIP] $Label has no new staged changes."
    }

    $pushStatus = "skip"
    if (-not $NoPush) {
        $pushResult = Push-Repo -RepoRoot $RepoRoot -Label $Label -Remote $Remote
        $pushStatus = $pushResult.Status
    }

    return [pscustomobject]@{
        Label      = $Label
        Committed  = $commitCreated
        Pushed     = $pushStatus -eq "pushed"
        CommitHash = $commitHash
        PushStatus = $pushStatus
    }
}

$workspaceRoot = Resolve-WorkspaceGitRoot -CandidatePath $WorkspaceRoot
$submoduleMessage = if ($Message) {
    $Message
} else {
    "chore: workspace sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
}
$rootCommitMessage = if ($RootMessage) {
    $RootMessage
} else {
    $submoduleMessage
}

Write-Host "[INFO] Workspace root: $workspaceRoot"
Write-Host "[INFO] NoPush: $($NoPush.IsPresent)"

if (-not $DryRun) {
    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("submodule", "sync", "--recursive") -Quiet | Out-Null
    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("submodule", "update", "--init", "--recursive") -Quiet | Out-Null
} else {
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot submodule sync --recursive"
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot submodule update --init --recursive"
}

$results = New-Object System.Collections.Generic.List[object]
$submodulePaths = @(Get-SubmodulePaths -RepoRoot $workspaceRoot)
Write-Host "[INFO] Recursive submodule count: $($submodulePaths.Count)"

foreach ($relativePath in $submodulePaths) {
    $repoRoot = Join-Path $workspaceRoot $relativePath
    $results.Add((Invoke-RepoCommitAndPush -RepoRoot $repoRoot -Label $relativePath -CommitMessage $submoduleMessage -Remote $Remote -NoPush:$NoPush -DryRun:$DryRun))
}

$results.Add((Invoke-RepoCommitAndPush -RepoRoot $workspaceRoot -Label "." -CommitMessage $rootCommitMessage -Remote $Remote -NoPush:$NoPush -DryRun:$DryRun))

$commitCount = @($results | Where-Object { $_.Committed }).Count
$pushCount = @($results | Where-Object { $_.Pushed }).Count
$skipCount = @($results | Where-Object { (-not $_.Committed) -and (-not $_.Pushed) }).Count

Write-Host "[SUMMARY] committed=$commitCount pushed=$pushCount untouched=$skipCount"
