---
name: session-state-maintainer
description: Keep workspace continuity across restarts by restoring and updating key state files. Use when a session starts, ends, or when workflow/process files change and must remain restart-ready without relying on long chat context.
---

# Session State Maintainer

Use this skill to enforce a repeatable restore-update cycle so the next session starts from the same working state.

## Start-of-Session Restore
1. Read files in this order:
- `AGENTS.md`
- `workspace_state/startup-checklist.md`
- `workspace_state/session-snapshot.md`
- `user_profile/thinking-patterns-overview.md`
- `knowledge_base/analysis-methods-overview.md`
2. Identify missing or stale files and mark them for repair before task execution.
3. Summarize restored state in 3 to 6 lines before doing substantive work.

## End-of-Turn Update
1. Update `workspace_state/session-snapshot.md` with:
- what changed
- active defaults
- next-start priorities
2. Update `user_profile/thinking-patterns-change-log.md`.
3. If stable preference changed, also update:
- `user_profile/thinking-patterns-overview.md`
- the relevant domain file under `user_profile/`
4. If process changed, update:
- `workspace_state/startup-checklist.md`
- `workspace_state/state-change-log.md`

## Quality Gates
1. Keep facts and assumptions separated.
2. Mark non-explicit conclusions as `inference/assumption` with confidence.
3. Ensure new files are linked from overview/index files.
4. Fail closed: if critical state file is missing, recreate a minimal valid file first.

## References
1. Read `references/state-file-contracts.md` for required fields per state file.
