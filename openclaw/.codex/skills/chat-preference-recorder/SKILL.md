---
name: chat-preference-recorder
description: Capture and maintain user preferences from conversation. Use when the user states likes/dislikes, style requests, constraints, or says “remember this”, then update daily notes and long-term memory safely.
---

# Chat Preference Recorder

1. Extract preference candidates as atomic statements.
2. Label each candidate as `confirmed` or `pending`.
3. Mark confidence as `high`/`medium`/`low` for inferred items.
4. Write `pending` items to `memory/<today>.md` with short evidence.
5. Promote only `confirmed` items to `MEMORY.md`.
6. Deduplicate semantically similar entries before writing.
7. Keep entries concise and action-oriented.

## Examples

- Input: “以后回答先给结论。”
- Action: Record as confirmed output preference.
- Output: Add to `MEMORY.md` and reflect in future replies.

- Input: “我可能更喜欢短一点。”
- Action: Record as pending with medium confidence.
- Output: Add to daily memory; ask for confirmation in later turn.

- Input: “记住，不要动 ../Analyst。”
- Action: Record as confirmed hard constraint.
- Output: Enforce as path guard in subsequent operations.