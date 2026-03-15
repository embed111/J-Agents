# TOOLS.md - Local Notes

_Use this file for environment-specific facts that are not part of shared skills._

## GitHub Access Notes

- A local PAC file currently resolves GitHub-bound proxy traffic through `127.0.0.1:10808`.
- A working process-local Git combination for flaky GitHub access in this workspace was:
  - `http.proxy=http://127.0.0.1:10808`
  - `https.proxy=http://127.0.0.1:10808`
  - `http.sslBackend=openssl`
  - `http.version=HTTP/1.1`

## Workspace Skill Entry Points

- Pull all submodules: `.codex/skills/workspace-submodule-pull-all/SKILL.md`
- Commit and push all submodules: `.codex/skills/workspace-submodule-commit-push-all/SKILL.md`
- Legacy full-commit compatibility flow: `.codex/skills/workspace-full-commit/SKILL.md`

## Workflow Notes

- The standard order in this workspace is: pull submodules -> commit/push submodules -> commit/push root repo.
- Root repo pull is opt-in; default submodule pull should not implicitly pull the root repo.
- Detached HEAD in a submodule is a reportable skip reason, not an automatic repair target.

## What Belongs Here

- Local network quirks
- Useful host aliases
- Device names
- Environment-specific operational shortcuts

Keep secrets out of this file.
