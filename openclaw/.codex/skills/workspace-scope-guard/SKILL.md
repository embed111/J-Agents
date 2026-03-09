---
name: workspace-scope-guard
description: Prevent out-of-scope or unsafe file modifications across directories. Use when tasks involve path switching, cross-workspace reads, cleanup, or any edit/delete command.
---

# Workspace Scope Guard

1. Identify `allowed`, `read-only`, and `forbidden` paths from user instructions.
2. Apply path checks before every edit/delete command.
3. Refuse writes to forbidden paths and explain the block briefly.
4. Allow read-only access when explicitly permitted.
5. Require explicit confirmation for destructive actions.
6. Prefer reversible operations for cleanup (recycle/trash) over permanent deletion.
7. Keep the active `workdir` aligned with the user-selected workspace.
8. When a task has multiple subtasks, create one isolated folder per subtask before writing files.

## Examples

- Input: “不要改 ../Analyst。”
- Action: Mark `../Analyst` as forbidden for writes.
- Output: Read allowed, write blocked.

- Input: “切到 D:\\code\\AI\\workspace\\openclaw。”
- Action: Set command `workdir` to the target path.
- Output: Subsequent commands execute in that workspace.

- Input: “清理 C:\\Users\\jmqj 无用文件。”
- Action: Provide preview list first, ask confirmation, then clean.
- Output: Safe cleanup workflow with audit trail.