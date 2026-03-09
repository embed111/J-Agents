param(
    [string]$SkillRoot = ".codex/skills"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$root = Join-Path $repoRoot $SkillRoot

if (-not (Test-Path $root)) {
    Write-Error "Skill root not found: $root"
    exit 1
}

$skills = Get-ChildItem $root -Directory
if ($skills.Count -eq 0) {
    Write-Host "No skills found under $root"
    exit 0
}

$results = @()
foreach ($dir in $skills) {
    $skillFile = Join-Path $dir.FullName "SKILL.md"
    if (-not (Test-Path $skillFile)) {
        $results += [PSCustomObject]@{
            skill = $dir.Name
            status = "missing_skill_md"
            has_examples = $false
        }
        continue
    }
    $content = Get-Content -Raw $skillFile
    $has = $content -match "(?m)^## Examples\s*$"
    $results += [PSCustomObject]@{
        skill = $dir.Name
        status = if ($has) { "ok" } else { "missing_examples" }
        has_examples = [bool]$has
    }
}

$results | Sort-Object skill | Format-Table -AutoSize

$missing = @($results | Where-Object { $_.status -ne "ok" })
if ($missing.Count -gt 0) {
    Write-Error "Skill example check failed. missing_or_invalid=$($missing.Count)"
    exit 2
}

Write-Host "PASS: all local skills include ## Examples."
