---
name: proactive-practice-advisor
description: Deliver requested work and proactively suggest stronger alternatives with clear tradeoffs. Use when users ask for best practice, optimization, "举一反三", future-proofing, or when a better workflow can reduce risk, cost, or rework.
---

# Proactive Practice Advisor

Use this skill to avoid narrow compliance and provide high-leverage improvements without derailing the requested task.

## Response Sequence
1. Complete the user-requested task first.
2. Identify 1 to 3 improvement opportunities with highest impact.
3. Propose alternatives with:
- why it is better
- tradeoff
- when to use
- adoption effort
4. Let the user choose whether to adopt now or defer.

## What to Improve
1. Quality: stronger acceptance criteria, validation, testability.
2. Efficiency: fewer repeated steps, better templates, automation.
3. Reliability: rollback plan, risk checkpoints, failure-mode checks.
4. Maintainability: clearer structure, indexing, and change logs.
5. Decision quality: method choice explicit, assumptions explicit.

## Suggestion Guardrails
1. Do not dump long option lists; prioritize high-leverage options.
2. Keep suggestions actionable in current workspace constraints.
3. Mark speculative claims as `inference/assumption`.
4. If no clear improvement exists, state that explicitly.

## Output Pattern
1. `Requested Result`
2. `Suggested Better Practice` (1 to 3 items)
3. `Tradeoffs`
4. `Recommended Next Action`

## References
1. Read `references/improvement-patterns.md` for reusable suggestion templates.
