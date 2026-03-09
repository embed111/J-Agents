---
name: preference-cap-review-governor
description: Enforce long-term preference size cap and run downgrade review when cap is exceeded. Use when long-term preference files grow too large, when the user asks to keep preferences concise, or when maintainability of preference files drops.
---

# Preference Cap Review Governor

Use this skill to keep long-term preference files concise while preserving traceability through short-term demotion.

## Scope
1. Long-term cap applies to:
- `user_profile/core/thinking-patterns-global.md`
- `user_profile/core/thinking-patterns-domain-requirements.md`
- `user_profile/core/thinking-patterns-domain-collaboration.md`
- `user_profile/core/thinking-patterns-overview.md`
2. Excluded from cap:
- `user_profile/logs/thinking-patterns-change-log.md` (event stream log)

## Workflow
1. Run cap check:
- `powershell -ExecutionPolicy Bypass -File scripts/check-long-term-preference-cap.ps1 -WriteQueue`
2. If no overflow:
- Keep files unchanged; record pass result in session state if needed.
3. If overflow exists:
- Start review and retain only cross-topic stable preferences in long-term files.
- Demote stage-specific or topic-specific items into `user_profile/core/thinking-patterns-short-term.md`.
- Write review evidence into `user_profile/governance/preference-review-log.md`.
4. Re-run cap check until all long-term files are within cap.

## Review Criteria
1. Keep in long-term:
- Repeated across at least 2 independent topics.
- Directly affects default collaboration strategy.
2. Demote to short-term:
- One-off phase tactics.
- Single-domain implementation details.
- Recently introduced items not yet stable.

## Output Contract
1. `Cap Check Result`
2. `Kept in Long-term`
3. `Demoted to Short-term`
4. `Review Log Updated`
5. `Re-check Result`

## Quality Gates
1. Never delete preference facts directly; move with traceability.
2. Keep demotion rationale explicit.
3. Ensure links exist to short-term pool and review log.
4. Keep long-term files under configured cap (default 200 lines).

## Examples
1. Example A (overflow in requirements):
- Input: `thinking-patterns-domain-requirements.md` exceeds 200 lines.
- Action: keep stable core sections; demote dated incremental blocks.
- Output: long-term file back under cap + review log entry.
2. Example B (no overflow):
- Input: all long-term files under 200 lines.
- Action: run check only, no demotion.
- Output: pass result + empty/clean queue.
3. Example C (multi-file overflow):
- Input: overview and collaboration both exceed cap.
- Action: run one review pass per file, prioritize highest line count first.
- Output: each file reviewed, demotions consolidated in short-term pool.

