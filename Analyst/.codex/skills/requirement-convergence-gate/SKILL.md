---
name: requirement-convergence-gate
description: Gate design work until requirements are converged. Use when the user wants discussion-first, scope is still moving, or design should not start before explicit confirmation. Ask only the minimum needed questions (0 to 3), flag divergence risks, and issue a clear go/no-go design decision.
---

# Requirement Convergence Gate

Use this skill to prevent premature design and keep requirement discussions tight and testable.

## Trigger Signals
1. The user asks for discussion-first, clarification, or "do not start implementation/design yet".
2. Scope is moving across turns or conflicts appear between goals and constraints.
3. The user feedback indicates "you started too early" or "analysis/guidance is weak".
4. Requirement intent is ambiguous but implementation pressure is high.

## Workflow
1. Build a convergence checklist with four fields:
- objective
- scope
- constraints
- acceptance
2. Mark each field as `confirmed` or `open`.
3. Start with a short understanding replay:
- explicit goal (user-stated)
- inferred hidden need (`inference/assumption + confidence`)
4. Ask questions only when needed:
- no open field: ask 0 questions
- 1 to 2 open fields: ask 1 to 2 questions
- 3 or more open fields: ask top 3 questions only
5. If scope is expanding, add one explicit divergence risk note and a narrowing suggestion.
6. End each turn with a gate decision (internal check required):
- `hold_design` (requirements not converged)
- `start_design` (requirements converged)
7. Enforce action boundary:
- if `hold_design`, do not create design details or implementation task lists
- if `start_design`, proceed to requirement docs/design docs in the next step

## Output Contract (When Externalizing)
1. `Understanding Replay`
2. `Convergence Checklist` (objective/scope/constraints/acceptance)
3. `Open Items`
4. `Questions (0-3)`
5. `Divergence Risk` (only if present)
6. `Gate Decision`

## Rules
1. Do not produce feature design details while `Gate Decision=hold_design`.
2. Keep questions high-impact and non-overlapping.
3. Prefer user language over framework jargon.
4. When assumptions are unavoidable, label them as `inference/assumption` with confidence.
5. When all four convergence fields are confirmed, stop asking questions and move to `start_design`.
6. Never skip the gate decision check; external display is only required when blocked/risky or user asks.

## Examples
1. Example A (one open item):
- Open item: acceptance metric missing.
- Ask one question: "What metric defines success for this phase?"
- Decision: `hold_design`.
2. Example B (many open items):
- Open items: objective unclear, scope unclear, constraints unclear.
- Ask top three questions only (one per field).
- Add divergence risk note: "UI/API/algorithm being discussed together."
- Decision: `hold_design`.
3. Example C (fully confirmed):
- All four fields confirmed.
- Ask no question.
- Decision: `start_design`, then move to design output.
4. Example D (user says "you started too early"):
- Trigger signal hit: guidance quality issue.
- Output starts with explicit replay + inferred hidden need.
- Ask only top 1 to 2 high-value questions.
- Decision: `hold_design` until checklist fields are confirmed.
