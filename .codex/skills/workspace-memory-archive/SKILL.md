---
name: workspace-memory-archive
description: 归档当前工作区的记忆文件，用于用户要求“归档昨日记忆”、“把月度记忆汇总到全局总览”、“处理日切/月切记忆维护”或 `workspace-memory-context` 提示存在待归档告警的场景。会把昨日每日记忆写入对应月度总览，并在跨月时把上月月度总览写入全局记忆总览。
---

# Workspace Memory Archive

## Overview

在当前工作区执行记忆归档动作，覆盖两类归档：
- 日切归档：把昨日每日记忆摘要写入对应月份的 `记忆总览.md`
- 月切归档：把上月 `记忆总览.md` 摘要写入 `全局记忆总览.md`

## Workflow

1. 解析 `-WorkspaceRoot` 并确保 `.codex/memory/` 基础结构存在。
2. 查找昨日每日记忆文件；若存在且尚未归档，则抽取其中的摘要条目并追加到对应月度总览。
3. 查找上月月度总览；若存在且尚未归档，则抽取其中的日期与关键摘要并追加到全局记忆总览。
4. 若目标总览中已存在对应日期或月份标题，则跳过，不重复归档。
5. 输出本次归档结果；需要预演时可使用 `-DryRun`。

## Script

Use `scripts/archive_memory.ps1`.
The skill script delegates to the workspace canonical script at `.codex/scripts/archive_memory.ps1`.

### Archive yesterday and previous month if needed

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-memory-archive\scripts\archive_memory.ps1 `
  -WorkspaceRoot C:\work\J-Agents
```

### Preview archive changes

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-memory-archive\scripts\archive_memory.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -DryRun
```

### Simulate day/month rollover

```powershell
powershell -ExecutionPolicy Bypass -File .codex\skills\workspace-memory-archive\scripts\archive_memory.ps1 `
  -WorkspaceRoot C:\work\J-Agents `
  -Now "2026-04-01 09:00:00 +08:00"
```

## Rules

- 不归档今天的每日记忆。
- 如果昨日或上月已经归档，直接跳过，不重复写入。
- 只做追加式归档，不删除原始每日记忆或月度总览内容。
- 当 `workspace-memory-context` 报出待归档告警时，优先使用这个技能收口。

## Examples

User: 把昨天的记忆归档到本月总览里。

Action: run the script with `-WorkspaceRoot .`.

User: 现在是月初，帮我检查并归档上个月记忆总览。

Action: run the script, or use `-DryRun` first if the user asks for preview.
