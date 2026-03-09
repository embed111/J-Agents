---
name: directory-maintenance-governor
description: Keep any workspace directory clean with a single top-level guide file, module-based subfolders, and threshold-based archival maintenance. Use when users ask to tidy directory structures, enforce directory governance rules, or add ongoing archive cleanup for any directory.
---

# Directory Maintenance Governor

Use this skill to make directory cleanup repeatable across any folder, not only one fixed module.

## Inputs
1. Read `AGENTS.md` and honor non-destructive governance rules.
2. Read target directory `<target>/目录导读.md`; create it if missing.
3. Inventory top-level files and subdirectories under `<target>/`.
4. Identify high-growth files by line count, size, and staleness.

## Governance Rules
1. Keep top-level minimal:
- Keep only one top-level guide file: `目录导读.md`.
- Move other top-level files into module subdirectories.
2. Place files by module:
- `core/`: stable working docs or primary state files.
- `logs/`: change logs, history index, archive payload.
- `governance/`: review queues and policy review records.
- `policies/`: explicit constraints and guardrails.
- `observations/`: external inputs and temporary observations.
- add domain-specific folders only when necessary.
3. Apply dynamic archive:
- Trigger by threshold (line count, file size, idle days).
- Archive by move/trim + index update.
- Never delete historical facts directly.
4. Keep navigation traceable:
- Guide file must include module map + maintenance commands.
- Path refactors and guide updates must happen in the same turn.

## Workflow
1. Inventory and classify:
- Run `scripts/maintain-directory-health.ps1 -TargetDir <target>`.
- If guide filename is not `目录导读.md`, pass `-GuideFileName <name>`.
- Mark findings: `top_level_violation`, `archive_candidate`, `index_drift`.
2. Restructure:
- Move files into module subdirectories.
- Leave only `目录导读.md` at top-level.
3. Repair references:
- Update path references in AGENTS/skills/scripts/docs in same turn.
4. Set dynamic maintenance:
- Re-run check command and confirm trigger reasons.
- If archive should execute now, run:
  - `scripts/maintain-directory-health.ps1 -TargetDir <target> -AutoArchive -ArchiveFiles <rel-paths>`
5. Record process changes:
- Update state/change logs and session snapshot.

## Output Contract
1. `Current Findings`
2. `Structure Decisions`
3. `Reference Repair`
4. `Trigger Check and Archive Actions`
5. `Residual Risks`

## Quality Gates
1. Target directory top-level contains only `目录导读.md`.
2. No broken path references in touched scope.
3. Archive index exists after archive execution.
4. No destructive delete operations.

## Resources
1. Read `references/dynamic-rules-template.md` when defining module layout and thresholds for a new directory.

## Examples
1. Example A (top-level clutter):
- Signal: `docs/foo/` has multiple top-level markdown files.
- Action: move files into `core/` and `logs/`, keep only `docs/foo/目录导读.md`.
- Output: top-level single-entry check passes.
2. Example B (oversized logs):
- Signal: `logs/change-log.md` exceeds thresholds.
- Action: run `maintain-directory-health` with `-AutoArchive -ArchiveFiles logs/change-log.md`.
- Output: source file is trimmed, archive index appended.
3. Example C (clean state):
- Signal: no threshold hit and top-level already compliant.
- Action: keep structure unchanged, only record pass result.
- Output: no archive action, governance check remains green.
