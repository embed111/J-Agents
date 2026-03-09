---
name: requirements-doc-structure-governor
description: Maintain requirement-document structure and freshness for `docs/workflow`, and auto-place new requirement files into the correct module folders. Use when the docs directory feels messy, indexes drift from actual files, phase-era content becomes outdated, or the user asks to create/update requirement docs with stable folder structure and traceability.
---

# Requirements Doc Structure Governor

Use this skill to keep requirement docs easy to navigate and current while preserving history and traceability.

## Inputs
1. Read `AGENTS.md` and honor role boundaries.
2. Read `docs/workflow/overview/需求概述.md` as the master index.
3. List files in `docs/workflow/` and `docs/workflow/prompts/`.
4. Read `workspace_state/core/session-snapshot.md` for recent scope decisions.

## Auto-Placement Rules
1. Place new overview docs in `docs/workflow/overview/`.
2. Place new requirement details in `docs/workflow/requirements/`.
3. Place new detailed designs in `docs/workflow/design/`.
4. Place new gates/evidence/operation norms in `docs/workflow/governance/`.
5. Place new analysis reports in `docs/workflow/reports/`.
6. Place execution prompts only in `docs/workflow/prompts/`.
7. Do not place new requirement markdown files at `docs/workflow/` root.

## Workflow
1. Build inventory:
- Classify each file as `overview`, `requirement_detail`, `design_detail`, `gate_or_evidence`, `operation_spec`, `report`, `prompt`, or `other`.
2. Detect drift:
- Find files present but not indexed in `overview/需求概述.md`.
- Find indexed files missing on disk.
- Find naming drift (`Phase*`, deprecated product terms, temporary prefixes).
3. Route new docs:
- When creating or rewriting docs this turn, apply Auto-Placement Rules first.
- Normalize links to `docs/workflow/<module>/<file>.md` form.
- Update `overview/需求概述.md` index in the same turn.
4. Evaluate freshness:
- Mark each file as `active`, `legacy_keep`, or `archive_candidate` by using `references/structure-rules.md`.
- Label uncertain judgments as `推断/假设 + 置信度`.
5. Propose structure changes:
- Keep active docs in the active tree.
- Move archive candidates only after owner confirmation.
- Do not delete historical files directly.
6. Reconcile index:
- Update `overview/需求概述.md` so active docs are complete and ordered.
- Add a short archive index line when archive actions happen.
7. Emit acceptance checklist:
- All active docs indexed.
- No broken internal references.
- Naming and status tags consistent.
- No newly-added requirement docs in root.
- Required state/change logs updated.

## Output Contract
1. `Current Findings`
2. `File Decisions`
3. `Proposed/Applied Changes`
4. `Risks and Open Items`
5. `Acceptance Check`

## Resources
1. Read `references/structure-rules.md` for classification, freshness, and archive rules.
2. Read `references/examples.md` when you need detailed output patterns.

## Examples
1. Example A (index drift):
- Signal: a top-level markdown file exists but is absent from `需求概述.md`.
- Action: classify file, decide status, and either add it to active index or mark it as archive candidate with reason.
2. Example B (phase-era residue):
- Signal: active docs still use `Phase0` naming.
- Action: keep file as `legacy_keep`, propose migration mapping, and avoid direct deletion.
3. Example C (content expiry):
- Signal: requirement section conflicts with newer accepted rules.
- Action: mark section `archive_candidate`, provide replacement pointer, and wait for owner confirmation before moving.
4. Example D (new doc creation):
- Signal: user asks for a new requirement detail doc.
- Action: create file under `docs/workflow/requirements/`, update `docs/workflow/overview/需求概述.md` index, and avoid root placement.

