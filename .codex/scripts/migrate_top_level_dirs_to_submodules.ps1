[CmdletBinding()]
param(
    [string]$WorkspaceRoot = ".",
    [string[]]$Directories,
    [string]$RemotesRoot,
    [string]$StageRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Quote-ProcessArgument {
    param([Parameter(Mandatory = $true)][string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    $escaped = $Value -replace '(\\*)"', '$1$1\"'
    $escaped = $escaped -replace '(\\+)$', '$1$1'
    return '"' + $escaped + '"'
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
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
        $renderedOutput = if ($lines.Count -gt 0) { $lines -join [Environment]::NewLine } else { "(no git output)" }
        throw "git $($Arguments -join ' ') failed in '$RepoRoot' with exit code $exitCode.`n$renderedOutput"
    }

    return [pscustomobject]@{
        ExitCode = $exitCode
        Output   = $lines
    }
}

function Resolve-TopLevelGitRoot {
    param([Parameter(Mandatory = $true)][string]$Path)

    $resolved = (Resolve-Path -LiteralPath $Path).Path
    $result = Invoke-Git -RepoRoot $resolved -Arguments @("rev-parse", "--show-toplevel") -Quiet
    $root = ($result.Output | Select-Object -First 1).Trim()
    if (-not $root) {
        throw "Unable to resolve top-level Git repo for '$Path'."
    }
    return (Resolve-Path -LiteralPath $root).Path
}

function Ensure-DirectoryRepo {
    param(
        [Parameter(Mandatory = $true)][string]$DirectoryPath,
        [Parameter(Mandatory = $true)][string]$UserName,
        [Parameter(Mandatory = $true)][string]$UserEmail
    )

    $gitPath = Join-Path $DirectoryPath ".git"
    if (-not (Test-Path -LiteralPath $gitPath)) {
        Write-Host "[INIT] $DirectoryPath"
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("init", "-b", "main") -Quiet | Out-Null
    }

    $configuredName = (Invoke-Git -RepoRoot $DirectoryPath -Arguments @("config", "--get", "user.name") -AllowFailure -Quiet).Output | Select-Object -First 1
    if (-not $configuredName) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("config", "user.name", $UserName) -Quiet | Out-Null
    }

    $configuredEmail = (Invoke-Git -RepoRoot $DirectoryPath -Arguments @("config", "--get", "user.email") -AllowFailure -Quiet).Output | Select-Object -First 1
    if (-not $configuredEmail) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("config", "user.email", $UserEmail) -Quiet | Out-Null
    }
}

function Ensure-DirectoryCommitted {
    param(
        [Parameter(Mandatory = $true)][string]$DirectoryPath,
        [Parameter(Mandatory = $true)][string]$CommitMessage
    )

    $hasHead = (Invoke-Git -RepoRoot $DirectoryPath -Arguments @("rev-parse", "--verify", "HEAD") -AllowFailure -Quiet).ExitCode -eq 0
    Invoke-Git -RepoRoot $DirectoryPath -Arguments @("add", "-A") -Quiet | Out-Null
    $hasStagedChanges = (Invoke-Git -RepoRoot $DirectoryPath -Arguments @("diff", "--cached", "--quiet", "--exit-code") -AllowFailure -Quiet).ExitCode -eq 1

    if ((-not $hasHead) -or $hasStagedChanges) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", $CommitMessage) -Quiet | Out-Null
        $head = ((Invoke-Git -RepoRoot $DirectoryPath -Arguments @("rev-parse", "--short", "HEAD") -Quiet).Output | Select-Object -First 1).Trim()
        Write-Host "[COMMIT] $DirectoryPath -> $head"
    } else {
        Write-Host "[COMMIT] $DirectoryPath already clean"
    }
}

function Ensure-BareRemote {
    param(
        [Parameter(Mandatory = $true)][string]$DirectoryPath,
        [Parameter(Mandatory = $true)][string]$RemotePath
    )

    if (-not (Test-Path -LiteralPath $RemotePath)) {
        $remoteParent = Split-Path -Parent $RemotePath
        if (-not (Test-Path -LiteralPath $remoteParent)) {
            New-Item -ItemType Directory -Path $remoteParent -Force | Out-Null
        }
        Write-Host "[REMOTE] Creating bare remote $RemotePath"
        $startInfo = New-Object System.Diagnostics.ProcessStartInfo
        $startInfo.FileName = "git"
        $startInfo.Arguments = "clone --bare $(Quote-ProcessArgument -Value $DirectoryPath) $(Quote-ProcessArgument -Value $RemotePath)"
        $startInfo.RedirectStandardOutput = $true
        $startInfo.RedirectStandardError = $true
        $startInfo.UseShellExecute = $false
        $startInfo.CreateNoWindow = $true
        $process = [System.Diagnostics.Process]::Start($startInfo)
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            throw "git clone --bare failed for '$DirectoryPath'.`n$stdout`n$stderr"
        }
    }
}

function Ensure-OriginRemote {
    param(
        [Parameter(Mandatory = $true)][string]$DirectoryPath,
        [Parameter(Mandatory = $true)][string]$RemotePath
    )

    $existingOrigin = (Invoke-Git -RepoRoot $DirectoryPath -Arguments @("remote", "get-url", "origin") -AllowFailure -Quiet)
    if ($existingOrigin.ExitCode -ne 0) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("remote", "add", "origin", $RemotePath) -Quiet | Out-Null
        return
    }

    $originUrl = ($existingOrigin.Output | Select-Object -First 1).Trim()
    if ($originUrl -ne $RemotePath) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("remote", "set-url", "origin", $RemotePath) -Quiet | Out-Null
    }
}

function Push-DirectoryOrigin {
    param([Parameter(Mandatory = $true)][string]$DirectoryPath)

    $branch = ((Invoke-Git -RepoRoot $DirectoryPath -Arguments @("branch", "--show-current") -Quiet).Output | Select-Object -First 1).Trim()
    if (-not $branch) {
        $branch = "main"
    }

    $upstream = Invoke-Git -RepoRoot $DirectoryPath -Arguments @("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}") -AllowFailure -Quiet
    if ($upstream.ExitCode -eq 0) {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("push") -Quiet | Out-Null
    } else {
        Invoke-Git -RepoRoot $DirectoryPath -Arguments @("push", "-u", "origin", $branch) -Quiet | Out-Null
    }
}

function Get-IndexMode {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$Pathspec
    )

    $result = Invoke-Git -RepoRoot $RepoRoot -Arguments @("ls-files", "--stage", "--", $Pathspec) -AllowFailure -Quiet
    if ($result.ExitCode -ne 0 -or $result.Output.Count -eq 0) {
        return $null
    }

    return ($result.Output | Select-Object -First 1).Split("`t")[0].Split(" ")[0]
}

function Convert-ToSubmodule {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$DirectoryName,
        [Parameter(Mandatory = $true)][string]$RemotePath,
        [Parameter(Mandatory = $true)][string]$StageRoot
    )

    $existingMode = Get-IndexMode -RepoRoot $RepoRoot -Pathspec $DirectoryName
    if ($existingMode -eq "160000") {
        Write-Host "[SUBMODULE] $DirectoryName already is a gitlink"
        return
    }

    Invoke-Git -RepoRoot $RepoRoot -Arguments @("rm", "-r", "--cached", "--ignore-unmatch", $DirectoryName) -Quiet | Out-Null
    Invoke-Git -RepoRoot $RepoRoot -Arguments @("-c", "protocol.file.allow=always", "submodule", "add", "--force", $RemotePath, $DirectoryName) -Quiet | Out-Null
    Write-Host "[SUBMODULE] $DirectoryName added"
}

$repoRoot = Resolve-TopLevelGitRoot -Path $WorkspaceRoot
$workspaceName = Split-Path -Leaf $repoRoot
$workspaceParent = Split-Path -Parent $repoRoot

if (-not $PSBoundParameters.ContainsKey("RemotesRoot")) {
    $RemotesRoot = Join-Path $workspaceParent ($workspaceName + "-submodule-remotes")
}
if (-not $PSBoundParameters.ContainsKey("StageRoot")) {
    $StageRoot = Join-Path $workspaceParent ($workspaceName + "-submodule-stage")
}

if (-not (Test-Path -LiteralPath $RemotesRoot)) {
    New-Item -ItemType Directory -Path $RemotesRoot -Force | Out-Null
}
if (-not (Test-Path -LiteralPath $StageRoot)) {
    New-Item -ItemType Directory -Path $StageRoot -Force | Out-Null
}

$rootUserName = ((Invoke-Git -RepoRoot $repoRoot -Arguments @("config", "--get", "user.name") -Quiet).Output | Select-Object -First 1).Trim()
$rootUserEmail = ((Invoke-Git -RepoRoot $repoRoot -Arguments @("config", "--get", "user.email") -Quiet).Output | Select-Object -First 1).Trim()
if (-not $rootUserName -or -not $rootUserEmail) {
    throw "Root repository must have user.name and user.email configured."
}

if (-not $Directories -or $Directories.Count -eq 0) {
    $Directories = Get-ChildItem -LiteralPath $repoRoot -Directory -Force |
        Where-Object { $_.Name -notin @(".git", ".codex") } |
        Select-Object -ExpandProperty Name
}

foreach ($directoryName in $Directories) {
    $directoryPath = Join-Path $repoRoot $directoryName
    if (-not (Test-Path -LiteralPath $directoryPath)) {
        throw "Directory not found: $directoryName"
    }

    Write-Host "=== $directoryName ==="
    Ensure-DirectoryRepo -DirectoryPath $directoryPath -UserName $rootUserName -UserEmail $rootUserEmail
    Ensure-DirectoryCommitted -DirectoryPath $directoryPath -CommitMessage "chore: initialize standalone repo before submodule migration"

    $bareRemotePath = Join-Path $RemotesRoot ($directoryName + ".git")
    Ensure-BareRemote -DirectoryPath $directoryPath -RemotePath $bareRemotePath
    Ensure-OriginRemote -DirectoryPath $directoryPath -RemotePath $bareRemotePath
    Push-DirectoryOrigin -DirectoryPath $directoryPath

    Convert-ToSubmodule -RepoRoot $repoRoot -DirectoryName $directoryName -RemotePath $bareRemotePath -StageRoot $StageRoot
}

if ((Test-Path -LiteralPath $StageRoot) -and @((Get-ChildItem -LiteralPath $StageRoot -Force)).Count -eq 0) {
    Remove-Item -LiteralPath $StageRoot -Force
}

Write-Host "[DONE] Top-level directory migration completed."
