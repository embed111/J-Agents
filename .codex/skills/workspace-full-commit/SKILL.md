---
name: workspace-full-commit
description: 在当前工作区执行“全量提交 + 自动推送”工作流，即使工作区里混有多个嵌套 Git 仓库也能安全完成。用于用户要求一次性提交当前仓库全部变更、递归处理嵌套 `.git`、提交后恢复嵌套仓库并把顶层分支推送到 GitHub 的场景。
---

# Workspace Full Commit

## Overview

在顶层 Git 仓库执行一次安全的全量提交。
脚本会把嵌套仓库的 `.git` 元数据临时移动到工作区外的缓存目录，执行 `git add -A` 和 `git commit`，随后无论成功失败都尽量还原这些 `.git`，最后在提交成功后自动 `git push`。

## Workflow

1. 解析 `-WorkspaceRoot` 对应的顶层 Git 仓库。
2. 递归查找除根仓自身之外的所有 `.git` 文件或目录。
3. 把这些 `.git` 元数据临时移动到工作区外的缓存目录，并写出 `manifest.json` 供异常恢复。
4. 执行顶层 `git add -A`。
5. 如存在 staged 变更则执行 `git commit`；默认提交成功后自动推送当前分支。
6. 在 `finally` 中还原所有嵌套 `.git` 元数据。
7. 如上一次运行被中断，可用 `-RestoreFromManifest` 进行恢复。

## Script

Use `scripts/invoke_workspace_full_commit.ps1`.

### Commit and push

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-full-commit\scripts\invoke_workspace_full_commit.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Message "chore: workspace sync"
```

### Dry run

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-full-commit\scripts\invoke_workspace_full_commit.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -DryRun
```

### Restore after interrupted run

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-full-commit\scripts\invoke_workspace_full_commit.ps1 `
  -RestoreFromManifest C:\work\.workspace-full-commit-cache\<run-id>\manifest.json
```

## Rules

- 只处理顶层仓库以下的嵌套 `.git`；不会移动根仓自己的 `.git`。
- 临时缓存目录放在工作区父目录下，避免被当前 `git add -A` 收进去。
- `git push` 默认走当前分支已有 upstream；若无 upstream，则推送到 `origin/<current-branch>` 并设置 upstream。
- `-NoCommit` 只执行“移走嵌套 `.git` + `git add -A` + 还原”，不提交不推送。
- `-NoPush` 在提交后停止，不执行远端推送。
- 如果没有 staged 变更，脚本会跳过 commit/push，但仍会还原 `.git`。

## Examples

User: 帮我把当前工作区全量提交并推到 GitHub，里面有好几个嵌套 Git 仓库。

Action: run the script with `-WorkspaceRoot . -Message "<commit message>"`.

User: 先别真的提交，先看会处理哪些嵌套仓库。

Action: run the script with `-DryRun`.

User: 上次执行过程中断了，帮我把嵌套 `.git` 还原回来。

Action: run the script with `-RestoreFromManifest <manifest.json>`.
