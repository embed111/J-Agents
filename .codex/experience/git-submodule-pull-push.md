# Git Submodule Pull Push

## Symptom

- Root pull is skipped even though the user asked to pull the latest code.
- Root push or submodule push is slow, hangs, or gets blocked halfway through.
- `workflow` cannot `pull --ff-only` even when `git status` looks clean.
- A submodule looks dirty after pull/push, but the file content does not seem to
  have changed.

## Cause

- Pull order was wrong: writing memory before pulling made the root repo dirty,
  so the pull skill skipped the root repo.
- Large repos such as `workflow` were staged with broad commands like
  `git add -A`, which is slow and can hang when the repo has many runtime files.
- Some Git helper code read `stdout` and `stderr` serially; when Git emitted many
  warnings, the process could deadlock on a full `stderr` buffer.
- `workflow` had tracked runtime cache files under `.running/prod/.../__pycache__`
  marked with `skip-worktree`; normal `git status` did not show them, but
  `git pull --ff-only` still refused to overwrite them.
- Global `core.autocrlf=true` on Windows caused repeated false-dirty states in
  some tracked files inside `workflow`.

## Avoidance

- For pull requests in this workspace, pull first and save memory after pull.
- For push requests in this workspace, save memory before the root commit/push.
- Prefer the local workspace skills and scripts over ad-hoc commands.
- In large repos, stage tracked and untracked paths by path list instead of
  relying on a blanket `git add -A`.
- Do not proactively stop `workflow/.running/prod` related processes during pull.
  That directory should normally stay outside Git tracking; only intervene if Git
  explicitly shows tracked runtime files there are blocking `pull --ff-only`.
- Keep `workflow` local Git settings aligned to avoid false-dirty line-ending
  churn:
  - `git -C workflow config core.autocrlf false`
  - `git -C workflow config core.eol lf`

## Recovery

### Root repo was dirtied by memory before pull

- Revert the premature memory-file edits first.
- Reset submodules back to the gitlinks currently recorded by the root repo.
- Re-run pull in the correct order: pull first, then save memory.

### Large repo stage or commit hangs

- Check for stuck `git.exe` processes.
- Check for leftover `index.lock` files.
- Use pathspec-based staging rather than broad worktree scans.
- If a wrapper script hangs, inspect whether `stderr` buffering is blocking the
  Git child process.

### `workflow` pull is blocked by tracked runtime files

- First confirm Git is actually blocked by tracked files under
  `.running/prod`; do not kill processes just because the service is running.
- Only if tracked runtime files are the blocker, restore them even if they are
  hidden by `skip-worktree`:

```powershell
git -C workflow restore --worktree --ignore-skip-worktree-bits -- .running/prod
```

- Retry:

```powershell
git -C workflow pull --ff-only
```

### Submodule looks dirty after pull/push

- Check whether the root repo is only dirty because submodule gitlinks advanced.
- In the submodule, compare index blob hashes and worktree hashes before assuming
  there is a real content change.
- If content hashes match but Git still shows modified paths, suspect line-ending
  or stat-state noise before making another commit.

## Verified In This Workspace

- Pull skill should tolerate unexpected result objects during summary reporting.
- Push skill should allow empty path collections and should not block on
  sequential `stdout`/`stderr` reads.
- `workflow` runtime artifacts are a recurring source of false-clean and
  hidden-dirty confusion; inspect `.running/prod` early when pull behaves
  inconsistently.
