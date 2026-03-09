# Dynamic Rules Template

Use this template when applying directory governance to a new target folder.

## 1. Directory Scope
1. Target directory: `<target>/`
2. Top-level guide file: `<target>/目录导读.md`
3. Allowed top-level files: only `目录导读.md`

## 2. Module Layout
1. `core/`: main state or working files
2. `logs/`: logs, history indexes, archive files
3. `governance/`: review queues and governance evidence
4. `policies/`: constraints and hard rules
5. `observations/`: temporary observations and external inputs
6. Optional custom module: `<module>/` (only if needed)

## 3. Dynamic Archive Thresholds
1. Line threshold: `<N>`
2. Size threshold (KB): `<M>`
3. Idle days threshold: `<D>`
4. Keep-tail lines after archive: `<K>`
5. Archive index path: `<target>/<archive-dir>/archive-index.md`

## 4. Maintenance Commands
1. Check:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/maintain-directory-health.ps1 -TargetDir <target>
```
   - If guide file is not `目录导读.md`, append: `-GuideFileName <guide-file-name>`.
2. Auto archive:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/maintain-directory-health.ps1 -TargetDir <target> -AutoArchive -ArchiveFiles <rel-path-1>,<rel-path-2>
```

## 5. Acceptance Checklist
1. Top-level single guide file rule passes.
2. Path references updated in same turn.
3. Archive action is indexed and traceable.
4. No historical facts were deleted.
