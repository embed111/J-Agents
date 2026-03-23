---
name: workspace-submodule-pull-all
description: 同步并拉取当前工作区的全部 Git submodule，默认递归处理子模块并在需要时初始化缺失子仓。用于用户要求“一次性拉取全部子仓”、“同步所有 submodule”、“更新当前工作区所有子仓到远端最新”，或需要批量识别哪些子仓因本地改动而不能 fast-forward 拉取的场景。
---

# Workspace Submodule Pull All

## Overview

在当前工作区递归执行 submodule 同步和拉取。
脚本会先同步 `.gitmodules` 配置并初始化缺失子仓，再对子仓执行 `git fetch --all --prune` 与 `git pull --ff-only`。默认不拉取根仓；如需一起拉取根仓，显式传入 `-IncludeRoot`。如需在拉取完成后把本轮结果写入 `.codex/memory/`，可显式传入 `-SaveMemoryAfterPull`。

## Workflow

1. 解析 `-WorkspaceRoot` 对应的顶层 Git 仓库。
2. 执行 `git submodule sync --recursive` 与 `git submodule update --init --recursive`。
3. 如传入 `-IncludeRoot`，先尝试对根仓执行 `git pull --ff-only`。
4. 递归遍历全部子仓；对子仓先检查本地是否 dirty，再执行 `fetch` 和 `pull --ff-only`。
5. 对 dirty 仓库、无 upstream 仓库或 detached HEAD 仓库只报告跳过，不强行合并。
6. 如传入 `-SaveMemoryAfterPull`，在拉取动作结束后调用工作区记忆脚本，把本轮结果追加到当日记忆。
7. 输出更新结果，并提示根仓可能因为 gitlink 变化而变脏。

## Script

Use `scripts/pull_all_submodules.ps1`.

### Pull all submodules

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-pull-all\scripts\pull_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents
```

### Pull root plus all submodules

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-pull-all\scripts\pull_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -IncludeRoot
```

### Pull root plus all submodules, then save memory

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-pull-all\scripts\pull_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -IncludeRoot `
  -SaveMemoryAfterPull
```

### Dry run

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-submodule-pull-all\scripts\pull_all_submodules.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -DryRun
```

## Rules

- 只使用 `git pull --ff-only`，不自动创建 merge commit。
- 发现本地未提交改动时直接跳过该仓库，避免把拉取流程变成冲突处理流程。
- 默认只拉取子仓，不拉取根仓。
- 如启用记忆保存，顺序始终是先完成拉取，再写入 `.codex/memory/`。
- 子仓拉取成功后，根仓可能因为 gitlink 更新而出现未提交变更；这是正常现象。

## Examples

User: 把当前工作区所有子仓都拉到远端最新。

Action: run the script with `-WorkspaceRoot .`.

User: 先别真拉，先看哪些仓会被跳过。

Action: run the script with `-DryRun`.

User: 连根仓一起 fast-forward 拉取。

Action: run the script with `-IncludeRoot`.

User: 连根仓一起拉取，拉完把结果记到记忆里。

Action: run the script with `-IncludeRoot -SaveMemoryAfterPull`.
