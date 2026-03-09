---
name: session-bootstrap-check
description: Restore context for this workspace at chat start. Use when a new session begins or after restart to read identity, user, and memory files in a fixed order before doing other tasks.
---

# Session Bootstrap Check

1. Read `SOUL.md`.
2. Read `USER.md`.
3. Read `memory/<today>.md` and `memory/<yesterday>.md` when they exist.
4. In direct chat sessions, read `MEMORY.md`.
5. If `BOOTSTRAP.md` exists and identity/user fields are still blank, run onboarding questions and update `IDENTITY.md` and `USER.md`.
6. Summarize recovered context in 3-6 concise bullets before executing user tasks.
7. Write important decisions to `memory/<today>.md`.

## Examples

- Input: “你好，今天继续。”
- Action: Read startup files in order, recover context, then continue tasks.
- Output: Brief context summary + next actionable step.

- Input: “你还记得我之前说的吗？”
- Action: Read `MEMORY.md` + recent daily notes first.
- Output: Answer with confirmed memory and mark uncertain items clearly.