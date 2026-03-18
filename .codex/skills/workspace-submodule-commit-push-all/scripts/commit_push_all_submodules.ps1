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

function Get-RemoteHeadBranchName {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $remoteHeadRef = Get-RemoteHeadRef -RepoRoot $RepoRoot
    if (-not $remoteHeadRef) {
        return $null
    }

    $prefix = "refs/remotes/origin/"
    if ($remoteHeadRef.StartsWith($prefix)) {
        return $remoteHeadRef.Substring($prefix.Length)
    }

    return $null
}

function Test-HeadContainedInRemote {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("branch", "-r", "--contains", "HEAD") -AllowFailure -Quiet
    if ($result.ExitCode -ne 0) {
        return $false
    }

    return @($result.Output | ForEach-Object { $_.Trim() } | Where-Object { $_ }).Count -gt 0
}

function Test-LocalBranchExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$BranchName
    )

    return (Invoke-Git -RepoRoot $RepoRoot -Arguments @("show-ref", "--verify", "--quiet", "refs/heads/$BranchName") -AllowFailure -Quiet).ExitCode -eq 0
}

function Ensure-CommitBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [switch]$DryRun
    )

    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    if ($branch) {
        return $branch
    }

    $remoteHeadRef = Get-RemoteHeadRef -RepoRoot $RepoRoot
    $remoteHeadBranch = Get-RemoteHeadBranchName -RepoRoot $RepoRoot
    if ((-not $remoteHeadRef) -or (-not $remoteHeadBranch)) {
        return $null
    }

    $trackingRef = "origin/$remoteHeadBranch"
    $localBranchExists = Test-LocalBranchExists -RepoRoot $RepoRoot -BranchName $remoteHeadBranch

    if ($DryRun) {
        if ($localBranchExists) {
            Write-Host "[DRY-RUN] Would switch $Label from detached HEAD to branch '$remoteHeadBranch'."
        } else {
            Write-Host "[DRY-RUN] Would create branch '$remoteHeadBranch' for $Label from $trackingRef."
        }
        return $remoteHeadBranch
    }

    if ($localBranchExists) {
        Invoke-Git -RepoRoot $RepoRoot -Arguments @("checkout", $remoteHeadBranch) -Quiet | Out-Null
        Write-Host "[INFO] Switched $Label to branch '$remoteHeadBranch'."
        return $remoteHeadBranch
    }

    Invoke-Git -RepoRoot $RepoRoot -Arguments @("checkout", "-b", $remoteHeadBranch, "--track", $trackingRef) -Quiet | Out-Null
    Write-Host "[INFO] Created branch '$remoteHeadBranch' for $Label from $trackingRef."
    return $remoteHeadBranch
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

function Get-GitConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("config", "--get", $Key) -AllowFailure -Quiet
    if ($result.ExitCode -ne 0) {
        return $null
    }

    $firstLine = $result.Output | Select-Object -First 1
    if ($null -eq $firstLine) {
        return $null
    }

    $value = $firstLine.Trim()
    if ($value) {
        return $value
    }

    return $null
}

function Set-GitConfigValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Key,

        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    Invoke-Git -RepoRoot $RepoRoot -Arguments @("config", $Key, $Value) -Quiet | Out-Null
}

function Ensure-CommitIdentity {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [string]$FallbackRepoRoot,

        [switch]$DryRun
    )

    $userName = Get-GitConfigValue -RepoRoot $RepoRoot -Key "user.name"
    $userEmail = Get-GitConfigValue -RepoRoot $RepoRoot -Key "user.email"

    if ((-not $userName) -and $FallbackRepoRoot) {
        $fallbackUserName = Get-GitConfigValue -RepoRoot $FallbackRepoRoot -Key "user.name"
        if ($fallbackUserName) {
            if ($DryRun) {
                Write-Host "[DRY-RUN] Would set $Label user.name from workspace root."
            } else {
                Set-GitConfigValue -RepoRoot $RepoRoot -Key "user.name" -Value $fallbackUserName
                Write-Host "[INFO] Set $Label user.name from workspace root."
            }
            $userName = $fallbackUserName
        }
    }

    if ((-not $userEmail) -and $FallbackRepoRoot) {
        $fallbackUserEmail = Get-GitConfigValue -RepoRoot $FallbackRepoRoot -Key "user.email"
        if ($fallbackUserEmail) {
            if ($DryRun) {
                Write-Host "[DRY-RUN] Would set $Label user.email from workspace root."
            } else {
                Set-GitConfigValue -RepoRoot $RepoRoot -Key "user.email" -Value $fallbackUserEmail
                Write-Host "[INFO] Set $Label user.email from workspace root."
            }
            $userEmail = $fallbackUserEmail
        }
    }

    if ((-not $userName) -or (-not $userEmail)) {
        throw "Commit identity missing in '$RepoRoot'. Configure user.name and user.email, or set them in the workspace root so child repos can inherit them."
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

function Invoke-PushWithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot,

        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,

        [int]$MaxAttempts = 3,

        [int]$DelaySeconds = 5
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        $result = Invoke-Git -RepoRoot $RepoRoot -Arguments $Arguments -AllowFailure -Quiet
        if ($result.ExitCode -eq 0) {
            return
        }

        $renderedOutput = if ($result.Output.Count -gt 0) {
            $result.Output -join [Environment]::NewLine
        } else {
            "(no git output)"
        }

        if ($attempt -lt $MaxAttempts) {
            Write-Host "[WARN] Push attempt $attempt/$MaxAttempts failed for $Label; retrying in $DelaySeconds seconds."
            Start-Sleep -Seconds $DelaySeconds
            continue
        }

        throw "git $($Arguments -join ' ') failed in '$RepoRoot' with exit code $($result.ExitCode).`n$renderedOutput"
    }
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

        Invoke-PushWithRetry -RepoRoot $RepoRoot -Label $Label -Arguments @("push")
        Write-Host "[OK] Pushed $Label via $upstream"
        return [pscustomobject]@{ Label = $Label; Status = "pushed" }
    }

    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    if (-not $branch) {
        throw "$Label is in detached HEAD; push target is ambiguous."
    }

    Assert-RemoteExists -RepoRoot $RepoRoot -Remote $Remote
    Invoke-PushWithRetry -RepoRoot $RepoRoot -Label $Label -Arguments @("push", "-u", $Remote, $branch)
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

        [string]$FallbackIdentityRepoRoot,

        [switch]$NoPush,

        [switch]$DryRun
    )

    $dirty = Test-RepoDirty -RepoRoot $RepoRoot
    $hasHead = Test-RepoHasHead -RepoRoot $RepoRoot
    $upstream = Get-UpstreamRef -RepoRoot $RepoRoot
    $branch = Get-CurrentBranch -RepoRoot $RepoRoot
    if ($dirty -and (-not $branch)) {
        $branch = Ensure-CommitBranch -RepoRoot $RepoRoot -Label $Label -DryRun:$DryRun
        if ((-not $DryRun) -and $branch) {
            $upstream = Get-UpstreamRef -RepoRoot $RepoRoot
        }
    }
    $aheadCount = if ($upstream) { Get-AheadCount -RepoRoot $RepoRoot } else { $null }
    $headContainedInRemote = if ($hasHead -and (-not $upstream) -and (-not $branch)) {
        Test-HeadContainedInRemote -RepoRoot $RepoRoot
    } else {
        $null
    }
    $pushRequired = if ($NoPush) {
        $false
    } elseif ($dirty -or (-not $hasHead)) {
        $true
    } elseif ($upstream) {
        $aheadCount -gt 0
    } elseif ($branch) {
        $true
    } else {
        -not $headContainedInRemote
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
        Ensure-CommitIdentity -RepoRoot $RepoRoot -Label $Label -FallbackRepoRoot $FallbackIdentityRepoRoot -DryRun:$DryRun
        Invoke-Git -RepoRoot $RepoRoot -Arguments @("commit", "-m", $CommitMessage) -Quiet | Out-Null
        $commitCreated = $true
        $commitHash = ((Invoke-Git -RepoRoot $RepoRoot -Arguments @("rev-parse", "--short", "HEAD") -Quiet).Output | Select-Object -First 1).Trim()
        Write-Host "[OK] Committed $Label -> $commitHash"
    } else {
        Write-Host "[SKIP] $Label has no new staged changes."
    }

    $pushStatus = "skip"
    if ((-not $NoPush) -and $pushRequired) {
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
} else {
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot submodule sync --recursive"
}

$results = New-Object System.Collections.Generic.List[object]
$submodulePaths = @(Get-SubmodulePaths -RepoRoot $workspaceRoot)
Write-Host "[INFO] Recursive submodule count: $($submodulePaths.Count)"

foreach ($relativePath in $submodulePaths) {
    $repoRoot = Join-Path $workspaceRoot $relativePath
    $results.Add((Invoke-RepoCommitAndPush -RepoRoot $repoRoot -Label $relativePath -CommitMessage $submoduleMessage -Remote $Remote -FallbackIdentityRepoRoot $workspaceRoot -NoPush:$NoPush -DryRun:$DryRun))
}

$results.Add((Invoke-RepoCommitAndPush -RepoRoot $workspaceRoot -Label "." -CommitMessage $rootCommitMessage -Remote $Remote -FallbackIdentityRepoRoot $workspaceRoot -NoPush:$NoPush -DryRun:$DryRun))

$commitCount = @($results | Where-Object { $_.Committed }).Count
$pushCount = @($results | Where-Object { $_.Pushed }).Count
$skipCount = @($results | Where-Object { (-not $_.Committed) -and (-not $_.Pushed) }).Count

Write-Host "[SUMMARY] committed=$commitCount pushed=$pushCount untouched=$skipCount"
