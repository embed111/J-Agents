---
name: subrole-invocation-orchestrator
description: Explicitly activate and orchestrate the workspace's internal subroles so responsibilities, parallelizable steps, and acceptance checks are visible to the user. Use when a task spans multiple workstreams such as requirements, design, prototypes, screenshots, validation, or state updates; when the user asks whether subroles are being used; when directory-wide consistency must be checked; or when you need to make subrole participation externally visible instead of keeping it implicit.
---

# Subrole Invocation Orchestrator

## Overview

Use this skill to turn the workspace's internal subroles into an explicit operating protocol.
The goal is not to pretend they are independent agents, but to make their activation, ownership, and output visible and testable during execution.

## Workflow

1. Read `workspace_state/collaboration/通用子角色协作卡.md`.
2. Choose only the 1 to 3 subroles that add clear value to the current task.
3. Externalize activation before substantial work:
   - name the activated subroles
   - state what each one is responsible for
   - state which steps are parallel vs serial
4. Keep the roles honest during execution:
   - `任务拆解与并行编排者` decides dependency order and parallelizable tool calls
   - `信息结构审查者` challenges layout, density, scroll semantics, and reading order
   - `需求追溯与验收检查者` checks requirement/design/prototype/acceptance consistency before close-out
5. Reflect subrole output in commentary updates, not only in private reasoning.
6. Before the final answer, state whether subrole checks materially changed the result.

## Activation Rules

1. Do not activate subroles for trivial one-step tasks.
2. Do activate them when at least one of these is true:
   - the task includes 2 or more deliverable types
   - directory-wide consistency matters
   - the user is questioning your process quality or visibility
   - acceptance depends on multiple files staying aligned
3. Do not activate a subrole without assigning it a concrete responsibility.
4. Do not claim parallel subrole work if the underlying steps are actually serial.
5. Do not present subroles as separate autonomous models; present them as internal functional roles.

## Externalization Pattern

Use a short visible pattern in commentary when the skill is active:

1. `Subrole Activation`
   - which subroles are active
   - what each one owns
2. `Execution Shape`
   - what is parallel
   - what is serial
3. `Check Result`
   - what each subrole found or confirmed

Keep this concise. The user should be able to tell that subroles were actually used without reading a long audit log.

## Output Contract

When externalizing, prefer this order:

1. `Activated Subroles`
2. `Ownership`
3. `Parallel vs Serial`
4. `Key Findings`
5. `What Changed Because of the Subroles`

## Interaction Guardrails

1. If a subrole did not materially affect the result, say so briefly.
2. If only one subrole is useful, activate just one.
3. If the user explicitly complains that subroles are invisible, make activation visible in the next commentary update, not only in the final answer.
4. If a task later becomes simple, deactivate the extra subroles rather than carrying them through by inertia.

## Examples

1. Example A (prototype directory alignment):
   - Situation: One task touches `html`, `png`, overview page, and sketch file.
   - Activated Subroles:
     - `任务拆解与并行编排者`: split serial and parallel steps
     - `需求追溯与验收检查者`: check asset consistency before close-out
   - Output:
     - user sees which files were checked as a group, not only the edited HTML
2. Example B (layout-quality complaint):
   - Situation: User says the page still feels messy and doubts subroles were used.
   - Activated Subroles:
     - `信息结构审查者`: identify density, reading-order, and scroll problems
     - `任务拆解与并行编排者`: sequence doc updates, prototype edits, and screenshot refresh
   - Output:
     - commentary names the two subroles and what each one is checking
3. Example C (simple request):
   - Situation: User asks to add one acceptance line to a single requirement file.
   - Action:
     - do not activate the skill
   - Output:
     - no subrole commentary overhead is added
