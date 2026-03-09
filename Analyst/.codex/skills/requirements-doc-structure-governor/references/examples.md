# Examples

Use these examples when generating output for doc-structure governance.

## Example 1: Index Drift + Naming Drift

### Input signals
1. `docs/workflow/overview/需求概述.md` does not list `docs/workflow/governance/截图索引与归档规范.md`.
2. Active tree still contains `执行门禁-Phase0.md`.

### Expected output pattern
1. `Current Findings`
- Missing index entry: `截图索引与归档规范.md`.
- Naming drift: `执行门禁-Phase0.md` flagged as `legacy_keep`.
2. `File Decisions`
- `截图索引与归档规范.md` -> `active` (add to index).
- `执行门禁-Phase0.md` -> `legacy_keep` (keep + add migration note).
3. `Acceptance Check`
- Active file index completeness: pass.
- Legacy naming plan recorded: pass.

## Example 2: Overdue Requirement Chapter

### Input signals
1. Requirement chapter still describes a flow replaced by newer accepted rules.
2. Chapter has no active prompt/design references.

### Expected output pattern
1. `Current Findings`
- Content conflict with newer decision set.
- No active downstream references.
2. `File Decisions`
- Mark as `archive_candidate`.
- Create replacement pointer to the newer requirement doc.
3. `Risks and Open Items`
- `推断/假设`: no hidden downstream dependency (置信度: 中).
- Ask for owner confirmation before moving to archive.

## Example 3: Reports Introduced but Not Governed

### Input signals
1. New report files are synced into `docs/workflow/` root.
2. They are referenced by design docs but absent from overview index.

### Expected output pattern
1. `Current Findings`
- Report docs are dependency files, not orphan files.
2. `File Decisions`
- Keep as `active` and add into an “实施附件/报告” section.
3. `Acceptance Check`
- Referenced files indexed: pass.
- Missing/mismatched references: none.

## Example 4: New Requirement Doc Should Auto-Place

### Input signals
1. User asks: “新增需求详情-会话标签治理.md”。
2. Draft file is created at `docs/workflow/需求详情-会话标签治理.md` root.

### Expected output pattern
1. `Current Findings`
- Placement drift: requirement detail is in root, not module folder.
2. `File Decisions`
- Move/create canonical file at `docs/workflow/requirements/需求详情-会话标签治理.md`.
- Update `docs/workflow/overview/需求概述.md` index in same turn.
3. `Acceptance Check`
- Root-level new requirement markdown file: none.
- Index updated in same turn: pass.
