---
name: workspace-memory-context
description: 读取并校验当前工作区的记忆上下文，用于用户要求“读取记忆”、“加载连续性上下文”、“检查记忆文件是否齐全”、“开始工作前先看记忆”或需要确认日切/月切归档告警的场景。会创建缺失的模板文件，并按规范输出应读取的记忆文件路径。
---

# Workspace Memory Context

## Overview

在当前工作区执行记忆上下文准备与一致性检查。
该技能不会写入当日工作总结；它只负责确保记忆文件存在、指出应读取的文件，以及提示昨日或上月是否还有待归档内容。

## Workflow

1. 解析 `-WorkspaceRoot` 并定位 `.codex/MEMORY.md` 与 `.codex/memory/`。
2. 确保以下文件存在；缺失时创建模板：
   - `.codex/memory/全局记忆总览.md`
   - `.codex/memory/YYYY-MM/记忆总览.md`
   - `.codex/memory/YYYY-MM/YYYY-MM-DD.md`
3. 输出本轮必须读取的记忆文件路径：
   - `.codex/MEMORY.md`
   - 全局记忆总览
   - 当月记忆总览
   - 当日记忆
4. 检查昨日每日记忆是否已归档进对应的月度总览。
5. 检查上月月度总览是否已归档进全局记忆总览。
6. 只输出告警，不自动归档；需要归档时改用 `workspace-memory-archive`。

## Script

Use `scripts/ensure_memory_context.ps1`.
The skill script delegates to the workspace canonical script at `.codex/scripts/ensure_memory_context.ps1`.

### Check current memory context

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-memory-context\scripts\ensure_memory_context.ps1 `
  -WorkspaceRoot C:\work\J-Agents
```

### Check with a specific date

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-memory-context\scripts\ensure_memory_context.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Now "2026-04-01 09:00:00 +08:00"
```

## Rules

- 只负责“读前检查”和“模板补齐”，不追加每日总结。
- 发现归档缺口时只告警，不擅自把昨日或上月内容写入总览。
- 如果用户要求开始新一轮工作前先读取记忆，应优先使用这个技能。

## Examples

User: 开始之前先把这次要读的记忆都准备好。

Action: run the script with `-WorkspaceRoot .`.

User: 看一下今天开工前有没有昨天或上月还没归档的记忆。

Action: run the script and report any warnings.
