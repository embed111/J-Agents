# Experience

## Purpose

`.codex/experience/` stores reusable operational lessons for this workspace.
Use it to capture pitfalls, triggers, diagnostics, and preferred fixes that can
help avoid repeating the same failures during future work.

## What To Record

- Repeated pull/push failure patterns in the root repo or submodules
- Local-environment issues that are not secrets
- Script bugs or workflow ordering mistakes that are easy to repeat
- Practical recovery steps that were verified in this workspace

## What Not To Record

- Tokens, passwords, cookies, or any other secrets
- One-off noise with no reuse value
- Raw logs that belong in the business repo rather than workspace operations

## Suggested Entry Format

Each topic should go into its own markdown file.
Prefer stable topic names over daily filenames.

Recommended structure:

```md
# Topic

## Symptom

- What goes wrong

## Cause

- Why it happens in this workspace

## Avoidance

- How to avoid triggering it

## Recovery

- How to fix it when it already happened
```

## Current Topics

- `git-submodule-pull-push.md`

