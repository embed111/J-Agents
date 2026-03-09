# Structure Rules

Use this file when you need a deterministic way to classify and clean requirement docs.

## 1) File Classification
Map each file to one primary class:
1. `overview`: top-level requirement map and scope summary (`需求概述.md`).
2. `requirement_detail`: requirement detail docs (`需求详情-*`).
3. `design_detail`: detailed design docs (`详细设计-*`).
4. `gate_or_evidence`: execution gates and acceptance evidence matrices.
5. `operation_spec`: operation conventions (startup packs, screenshot index norms).
6. `report`: analysis reports for refactor/migration evidence.
7. `prompt`: execution prompts under `docs/workflow/prompts/`.

## 2) Directory Routing Rules
Place files by class:
1. `overview` -> `docs/workflow/overview/`
2. `requirement_detail` -> `docs/workflow/requirements/`
3. `design_detail` -> `docs/workflow/design/`
4. `gate_or_evidence` and `operation_spec` -> `docs/workflow/governance/`
5. `report` -> `docs/workflow/reports/`
6. `prompt` -> `docs/workflow/prompts/`

Hard gates:
1. New requirement markdown files must not be added to `docs/workflow/` root.
2. Any new/renamed file in modules above must be indexed in `docs/workflow/overview/需求概述.md` in the same turn.
3. Links in docs should use `docs/workflow/<module>/<file>.md` canonical form.

## 3) Freshness Decision Rules
Assign one status to every file:
1. `active`
- Referenced by current index and aligned with current goals.
2. `legacy_keep`
- Has historical naming/scope (such as `Phase0`) but still required for traceability or currently referenced.
3. `archive_candidate`
- Not referenced by active index and superseded by newer docs, with no active dependency.

## 4) Drift Signals
Treat any item below as drift:
1. File exists but is not indexed in `需求概述.md` (for active/legacy_keep categories).
2. File is indexed but missing on disk.
3. Naming contradicts current conventions (phase-era or temporary names in active docs).
4. Content conflicts with later confirmed requirement decisions.
5. New requirement/design/governance/report docs appear in root instead of module folders.
6. New module files are created but index is not updated in the same turn.

## 5) Archive Policy
1. Never hard-delete requirement docs directly.
2. Move only after owner confirmation.
3. Use dated folders for archive actions, e.g. `docs/workflow/archive/2026-03-05/`.
4. Add archive index entries in `需求概述.md` and keep move reasons.

## 6) Acceptance Checklist
1. Active docs are fully indexed.
2. No broken internal links.
3. Status (`active/legacy_keep/archive_candidate`) recorded for each touched file.
4. State logs updated when memory switch is on.
5. No new root-level requirement markdown files are introduced.
