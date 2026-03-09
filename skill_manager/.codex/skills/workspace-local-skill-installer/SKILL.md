---
name: workspace-local-skill-installer
description: Create and install Codex skills scoped to the current workspace only (no global pollution). Use when a user asks to create a new skill in a repo, import/copy an existing skill into `.codex/skills`, or register a local skill in `AGENTS.md` without writing to `~/.codex/skills`.
---

# Workspace Local Skill Installer

## Overview

Create and install skills inside the active repository.
Keep all skill files local to the workspace and avoid global skill directories.

## Workflow

1. Resolve workspace root and target directory (`.codex/skills` by default).
2. Create or install the skill directory locally.
3. Register the skill path in `AGENTS.md` when an `Available skills` section exists.
4. Report exact paths and any skipped registration reason.

## Script

Use `scripts/workspace_local_skill.py`.

### Create new local skill

```bash
python scripts/workspace_local_skill.py create --name my-skill --workspace-root .
```

### Install existing skill directory locally

```bash
python scripts/workspace_local_skill.py install --source C:\path\to\existing-skill --workspace-root .
```

### Register an already-local skill in AGENTS.md

```bash
python scripts/workspace_local_skill.py register --skill-dir .codex\skills\my-skill --workspace-root .
```

## Rules

- Default install location: `<workspace>/.codex/skills/<skill-name>`.
- Do not write to `~/.codex/skills` unless user explicitly asks.
- If `AGENTS.md` does not contain `### Available skills`, skip registration and report it.
- Keep generated skill names in lowercase hyphen-case.
