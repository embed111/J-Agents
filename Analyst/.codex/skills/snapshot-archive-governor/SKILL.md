---
name: snapshot-archive-governor
description: Keep workspace session snapshots concise with workload-triggered archiving and top-level index references. Use when `workspace_state/core/session-snapshot.md` grows too long, when users ask for historical summary classification, or when state files need compacting without losing traceability.
---

# Snapshot Archive Governor

Use this workflow to keep `workspace_state/core/session-snapshot.md` readable while preserving full history.

## Inputs
1. Read `workspace_state/core/session-snapshot.md`.
2. Read `AGENTS.md` and honor `MEMORY_UPDATE_SWITCH`.
3. Read `workspace_state/core/startup-checklist.md` to preserve required sections.
4. Prefer running `scripts/maintain-state-health.ps1 -AutoArchive` for threshold check + archive execution.

## Archive Decision
Use workload-first with time fallback. Trigger archive when any condition is true:
1. New update items since last archive >= 20.
2. Snapshot new lines since last archive >= 200.
3. Snapshot file size >= 120 KB.
4. Time fallback: 14 days without archive.

If user provides thresholds, use user values instead of defaults.

## Archive Workflow
1. Keep required top-level sections intact:
   - `最后更新`
   - `当前长期机制`
   - `当前默认工作方式`
   - `本次新增资产`
   - `下一轮启动时优先关注`
2. Move older update blocks to history file:
   - Directory: `workspace_state/logs/session-history/`
   - File pattern: `session-history-<yyyy-mm-dd>-to-<yyyy-mm-dd>.md`
3. Keep top-level snapshot focused:
   - Retain only recent key updates (default 10 items).
   - Replace moved blocks with one-line summary + link.
4. Maintain index file:
   - `workspace_state/logs/session-history-index.md`
   - One line per archive: period, short summary, link.

## Output Format
For each archive run, output:
1. Trigger reason (which threshold was hit).
2. What moved (date range and item count).
3. What remained in top-level snapshot.
4. Open assumptions as `推断/假设 + 置信度`.

## Quality Gates
1. Preserve chronological traceability.
2. Do not delete historical facts; only move and reference.
3. Keep facts and assumptions separated.
4. Ensure all links resolve to existing files.

## Examples
1. Example A (size trigger):
- Signal: `session-snapshot.md >= 120 KB`.
- Action: 归档历史块到 `workspace_state/logs/session-history/`，保留顶层近 10 条更新。
- Evidence: 更新 `session-history-index.md`。
2. Example B (workload trigger):
- Signal: 新增更新块 >= 20。
- Action: 按时间段移动老块，顶层仅保留最近关键更新与引用。
- Evidence: 顶层新增“历史归档引用”段。
3. Example C (no trigger):
- Signal: 文件体量和增量均未达到阈值。
- Action: 不归档，仅记录“未触发”结论。
- Evidence: 回合输出包含 trigger check 结果。

