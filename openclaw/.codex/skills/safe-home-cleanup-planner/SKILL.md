---
name: safe-home-cleanup-planner
description: Plan and execute safe file cleanup in home/workspace directories. Use when user asks to remove useless files, temporary files, logs, or cache data without risking important documents.
---

# Safe Home Cleanup Planner

1. Scan and classify candidates (`tmp`, `log`, cache, empty folders).
2. Exclude source code, configs, and user documents by default.
3. Produce a preview list with path, size, and reason.
4. Ask user confirmation before deletion.
5. Delete in small batches and record what changed.
6. Prefer reversible deletion when available.
7. Report summary (`count`, `freed space`, `remaining candidates`).

## Examples

- Input: “清理一下 C:\\Users\\jmqj 没用文件。”
- Action: Run preview first and wait for approval.
- Output: Candidate list + safe execution plan.

- Input: “把临时文件都删掉。”
- Action: Restrict to temporary/cache patterns only.
- Output: Targeted cleanup with low risk.

- Input: “先别删，只给我清单。”
- Action: Scan only; no deletion.
- Output: Reviewable report for user confirmation.