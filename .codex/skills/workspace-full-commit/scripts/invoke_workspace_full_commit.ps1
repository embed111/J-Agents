[CmdletBinding(DefaultParameterSetName = "Commit")]
param(
    [Parameter(ParameterSetName = "Commit")]
    [string]$WorkspaceRoot = ".",

    [Parameter(ParameterSetName = "Commit")]
    [string]$Message,

    [Parameter(ParameterSetName = "Commit")]
    [string]$Remote = "origin",

    [Parameter(ParameterSetName = "Commit")]
    [switch]$NoCommit,

    [Parameter(ParameterSetName = "Commit")]
    [switch]$NoPush,

    [Parameter(ParameterSetName = "Commit")]
    [switch]$DryRun,

    [Parameter(Mandatory = $true, ParameterSetName = "Restore")]
    [string]$RestoreFromManifest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Normalize-Path {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path)
    if ($fullPath.Length -gt 3) {
        return $fullPath.TrimEnd("\", "/")
    }
    return $fullPath
}

function Get-RelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $normalizedBase = Normalize-Path -Path $BasePath
    $normalizedTarget = Normalize-Path -Path $TargetPath
    $baseUri = [System.Uri]::new($normalizedBase + [System.IO.Path]::DirectorySeparatorChar)
    $targetUri = [System.Uri]::new($normalizedTarget)
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace("/", "\")
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
    $exitCode = $process.ExitCode

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

    if ((-not $AllowFailure) -and $exitCode -ne 0) {
        $renderedOutput = if ($lines.Count -gt 0) {
            ($lines -join [Environment]::NewLine)
        } else {
            "(no git output)"
        }
        throw "git $($Arguments -join ' ') failed with exit code $exitCode.`n$renderedOutput"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
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

function Get-NestedGitMetadataEntries {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    $rootPath = Normalize-Path -Path $WorkspaceRoot
    $rootGitPath = Normalize-Path -Path (Join-Path $rootPath ".git")
    $pending = [System.Collections.Generic.Stack[string]]::new()
    $found = New-Object System.Collections.Generic.List[object]
    $pending.Push($rootPath)

    while ($pending.Count -gt 0) {
        $currentPath = $pending.Pop()
        foreach ($child in Get-ChildItem -LiteralPath $currentPath -Force -ErrorAction SilentlyContinue) {
            if ($child.Name -eq ".git") {
                $candidatePath = Normalize-Path -Path $child.FullName
                if ($candidatePath -ne $rootGitPath) {
                    $found.Add($child)
                }
                continue
            }

            if (-not $child.PSIsContainer) {
                continue
            }

            $isReparsePoint = ($child.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
            if (-not $isReparsePoint) {
                $pending.Push($child.FullName)
            }
        }
    }

    return $found | Sort-Object FullName
}

function Save-Manifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath,

        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot,

        [Parameter(Mandatory = $true)]
        [string]$Stage,

        [Parameter()]
        [AllowNull()]
        [object[]]$Entries,

        [Parameter()]
        [string]$CommitMessage,

        [Parameter()]
        [string]$LastError
    )

    $payload = [pscustomobject]@{
        generated_at   = (Get-Date).ToString("o")
        workspace_root = $WorkspaceRoot
        stage          = $Stage
        commit_message = $CommitMessage
        last_error     = $LastError
        entries        = @($Entries)
    }

    $json = $payload | ConvertTo-Json -Depth 6
    Set-Content -LiteralPath $ManifestPath -Value $json -Encoding UTF8
}

function Restore-NestedGitMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [object[]]$Entries
    )

    if ($Entries.Count -eq 0) {
        return
    }

    $failures = New-Object System.Collections.Generic.List[string]
    foreach ($entry in ($Entries | Sort-Object { $_.relative_git_path.Length } -Descending)) {
        if (-not (Test-Path -LiteralPath $entry.stash_path)) {
            $failures.Add("Missing stash path: $($entry.stash_path)")
            continue
        }

        $destinationParent = Split-Path -Parent $entry.original_path
        if (-not (Test-Path -LiteralPath $destinationParent)) {
            New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
        }

        if (Test-Path -LiteralPath $entry.original_path) {
            $failures.Add("Restore destination already exists: $($entry.original_path)")
            continue
        }

        Move-Item -LiteralPath $entry.stash_path -Destination $entry.original_path
        Write-Host "[RESTORE] $($entry.relative_git_path)"
    }

    if ($failures.Count -gt 0) {
        throw ($failures -join [Environment]::NewLine)
    }
}

function Load-Manifest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "Manifest not found: $ManifestPath"
    }

    $content = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8
    return $content | ConvertFrom-Json
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
    throw "Unable to determine whether staged changes exist."
}

function Get-CurrentBranch {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RepoRoot
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("branch", "--show-current") -Quiet
    $branch = ($result.Output | Select-Object -First 1).Trim()
    if (-not $branch) {
        throw "Current repository is in detached HEAD state; push target is ambiguous."
    }
    return $branch
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
    throw "Unable to resolve upstream branch."
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

function Restore-FromManifestFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ManifestPath
    )

    $manifest = Load-Manifest -ManifestPath $ManifestPath
    $entries = @($manifest.entries)
    Restore-NestedGitMetadata -Entries $entries

    $runDirectory = Split-Path -Parent $ManifestPath
    if (Test-Path -LiteralPath $runDirectory) {
        Remove-Item -LiteralPath $runDirectory -Recurse -Force
    }

    Write-Host "[OK] Restored $($entries.Count) nested Git metadata entries from manifest."
}

if ($PSCmdlet.ParameterSetName -eq "Restore") {
    Restore-FromManifestFile -ManifestPath $RestoreFromManifest
    exit 0
}

$workspaceRoot = Resolve-WorkspaceGitRoot -CandidatePath $WorkspaceRoot
$nestedEntries = @(Get-NestedGitMetadataEntries -WorkspaceRoot $workspaceRoot)
$commitMessage = if ($Message) {
    $Message
} else {
    "workspace sync $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
}

Write-Host "[INFO] Workspace root: $workspaceRoot"
Write-Host "[INFO] Nested Git metadata count: $($nestedEntries.Count)"

if ($nestedEntries.Count -gt 0) {
    $nestedEntries |
        ForEach-Object { Get-RelativePath -BasePath $workspaceRoot -TargetPath $_.FullName } |
        ForEach-Object { Write-Host "[INFO] Nested Git: $_" }
}

if ($DryRun) {
    Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot add -A"
    if ($NoCommit) {
        Write-Host "[DRY-RUN] Commit and push are disabled because -NoCommit was supplied."
    } else {
        Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot commit -m `"$commitMessage`""
        if ($NoPush) {
            Write-Host "[DRY-RUN] Push is disabled because -NoPush was supplied."
        } else {
            $branch = Get-CurrentBranch -RepoRoot $workspaceRoot
            $upstream = Get-UpstreamRef -RepoRoot $workspaceRoot
            if ($upstream) {
                Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot push"
            } else {
                Write-Host "[DRY-RUN] Would run: git -C $workspaceRoot push -u $Remote $branch"
            }
        }
    }
    exit 0
}

$workspaceDirectory = Get-Item -LiteralPath $workspaceRoot
$workspaceParent = $workspaceDirectory.Parent.FullName
$cacheRoot = Join-Path $workspaceParent ".workspace-full-commit-cache"
$runId = "$(Get-Date -Format 'yyyyMMdd-HHmmss')-$([System.Guid]::NewGuid().ToString('N').Substring(0, 8))"
$runDirectory = Join-Path $cacheRoot $runId
$payloadDirectory = Join-Path $runDirectory "payloads"
$manifestPath = Join-Path $runDirectory "manifest.json"
$movedEntries = @()
$failureMessages = New-Object System.Collections.Generic.List[string]
$commitCreated = $false
$commitHash = $null
$shouldPush = (-not $NoCommit.IsPresent) -and (-not $NoPush.IsPresent)

if ($nestedEntries.Count -gt 0) {
    New-Item -ItemType Directory -Path $payloadDirectory -Force | Out-Null
    Save-Manifest -ManifestPath $manifestPath -WorkspaceRoot $workspaceRoot -Stage "initialized" -Entries $movedEntries -CommitMessage $commitMessage
}

try {
    $index = 0
    foreach ($entry in $nestedEntries) {
        $index += 1
        $relativeGitPath = Get-RelativePath -BasePath $workspaceRoot -TargetPath $entry.FullName
        $stashPath = Join-Path $payloadDirectory ("git-{0:D4}" -f $index)
        Move-Item -LiteralPath $entry.FullName -Destination $stashPath

        $record = [pscustomobject]@{
            index             = $index
            relative_git_path = $relativeGitPath
            original_path     = $entry.FullName
            stash_path        = $stashPath
            item_type         = if ($entry.PSIsContainer) { "directory" } else { "file" }
        }
        $movedEntries += $record
        Save-Manifest -ManifestPath $manifestPath -WorkspaceRoot $workspaceRoot -Stage "metadata_moved" -Entries $movedEntries -CommitMessage $commitMessage
        Write-Host "[MOVE] $relativeGitPath"
    }

    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("add", "-A") -Quiet | Out-Null
    Write-Host "[OK] Staged workspace changes with git add -A."

    if ($NoCommit) {
        $shouldPush = $false
        Write-Host "[INFO] Commit skipped because -NoCommit was supplied."
    } elseif (-not (Test-StagedChanges -RepoRoot $workspaceRoot)) {
        $shouldPush = $false
        Write-Host "[INFO] No staged changes detected; commit and push skipped."
    } else {
        Invoke-Git -RepoRoot $workspaceRoot -Arguments @("commit", "-m", $commitMessage) -Quiet | Out-Null
        $commitCreated = $true
        $commitHash = ((Invoke-Git -RepoRoot $workspaceRoot -Arguments @("rev-parse", "HEAD") -Quiet).Output | Select-Object -First 1).Trim()
        Write-Host "[OK] Created commit $commitHash"
    }
} catch {
    $failureMessages.Add($_.Exception.Message)
    if (Test-Path -LiteralPath $manifestPath) {
        Save-Manifest -ManifestPath $manifestPath -WorkspaceRoot $workspaceRoot -Stage "failed" -Entries $movedEntries -CommitMessage $commitMessage -LastError $_.Exception.Message
    }
} finally {
    if ($movedEntries.Count -gt 0) {
        try {
            Restore-NestedGitMetadata -Entries $movedEntries
            if (Test-Path -LiteralPath $manifestPath) {
                Save-Manifest -ManifestPath $manifestPath -WorkspaceRoot $workspaceRoot -Stage "restored" -Entries $movedEntries -CommitMessage $commitMessage
            }
            if (Test-Path -LiteralPath $runDirectory) {
                Remove-Item -LiteralPath $runDirectory -Recurse -Force
            }
            if ((Test-Path -LiteralPath $cacheRoot) -and @((Get-ChildItem -LiteralPath $cacheRoot -Force)).Count -eq 0) {
                Remove-Item -LiteralPath $cacheRoot -Force
            }
        } catch {
            $failureMessages.Add("Restore failed. Use -RestoreFromManifest `"$manifestPath`" to recover.`n$($_.Exception.Message)")
            if (Test-Path -LiteralPath $manifestPath) {
                Save-Manifest -ManifestPath $manifestPath -WorkspaceRoot $workspaceRoot -Stage "restore_failed" -Entries $movedEntries -CommitMessage $commitMessage -LastError $_.Exception.Message
            }
        }
    }
}

if ($failureMessages.Count -gt 0) {
    throw ("Workspace full commit failed.`n" + ($failureMessages -join "`n`n"))
}

if (-not $shouldPush) {
    exit 0
}

$branch = Get-CurrentBranch -RepoRoot $workspaceRoot
$upstream = Get-UpstreamRef -RepoRoot $workspaceRoot
if ($upstream) {
    Invoke-Git -RepoRoot $workspaceRoot -Arguments @("push") -Quiet | Out-Null
    Write-Host "[OK] Pushed branch $branch using existing upstream $upstream."
    exit 0
}

Assert-RemoteExists -RepoRoot $workspaceRoot -Remote $Remote
Invoke-Git -RepoRoot $workspaceRoot -Arguments @("push", "-u", $Remote, $branch) -Quiet | Out-Null
Write-Host "[OK] Pushed branch $branch to $Remote and set upstream."
