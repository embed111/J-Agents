---
name: workspace-submodule-commit-push-all
description: 递归提交并推送当前工作区的全部 Git submodule，再提交并推送根仓。用于用户要求“一次性提交所有子仓和本仓”、“批量 commit + push 全部 submodule”、“把子仓改动和根仓 gitlink 一起推送”，或需要统一处理根仓与子仓远端同步的场景。
---

# Workspace Submodule Commit Push All

## Overview

先处理全部子仓，再处理根仓，确保子仓新提交对应的 gitlink 会进入根仓提交。
脚本会优先用 `git add -u` 暂存 tracked 变更，再按路径清单补暂存 untracked 文件，避免大仓在 `git add -A` 上长时间卡住；如需在根仓提交前把本轮同步结果写入 `.codex/memory/`，可显式传入 `-SaveMemoryBeforeRootCommit`。如果某个子仓的 `origin` 仍是本地 bare 仓，推送也只会停留在本机，直到你把 `origin` 改成 GitHub URL。

## Workflow

1. 解析 `-WorkspaceRoot` 对应的顶层 Git 仓库，并初始化递归 submodule。
2. 按路径深度从深到浅遍历全部子仓，避免父仓先于子仓提交 gitlink。
3. 对每个子仓优先暂存 tracked 变更，再按路径清单补暂存 untracked 文件；如存在 staged 变更或仓库还没有首个提交，则创建提交。
4. 若启用推送，则优先推送已有 upstream；无 upstream 时推送到 `origin/<current-branch>` 并建立追踪关系。
5. 如传入 `-SaveMemoryBeforeRootCommit`，在处理根仓前调用工作区记忆脚本，把本轮同步结果追加到当日记忆。
6. 全部子仓完成后，对根仓执行同样的提交与推送流程。
7. 输出每个仓库的 commit/push 结果，并在失败时直接中止。

## Script

Use `scripts/commit_push_all_submodules.ps1`.

### Commit and push all submodules plus root

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-commit-push-all\scripts\commit_push_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: workspace sync"
```

### Use a different root commit message

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-commit-push-all\scripts\commit_push_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: child repo sync" `
  -RootMessage "chore: update gitlinks and workspace skills"
```

### Dry run

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-commit-push-all\scripts\commit_push_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: workspace sync" `
  -DryRun
```

### Commit only, do not push

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-commit-push-all\scripts\commit_push_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: workspace sync" `
  -NoPush
```

### Save memory before root commit and push

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-commit-push-all\scripts\commit_push_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: workspace sync" `
  -RootMessage "chore: update gitlinks and workspace skills" `
  -SaveMemoryBeforeRootCommit
```

## Rules

- 始终先提交子仓，再提交根仓。
- 默认推送到每个仓当前配置的 `origin`；脚本不会擅自替换远端地址。
- 遇到 detached HEAD 不猜测推送目标，直接报错。
- 无变更但存在未推送提交时，仍然执行推送。
- 如启用记忆保存，顺序始终是先写记忆，再提交根仓，再推送根仓。
- `-NoPush` 只做提交，不做任何远端写入。

## Examples

User: 把所有子仓和根仓一次性提交并推上去。

Action: run the script with `-Message "<commit message>"`.

User: 子仓统一一个提交信息，根仓单独一个提交信息。

Action: run the script with `-Message "<submodule message>" -RootMessage "<root message>"`.

User: 先看本次会提交和推送哪些仓。

Action: run the script with `-DryRun`.

User: 先把本轮同步结果写进记忆，再提交并推送根仓。

Action: run the script with `-SaveMemoryBeforeRootCommit`.
