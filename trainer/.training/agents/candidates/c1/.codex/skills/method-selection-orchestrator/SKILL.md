---
name: method-selection-orchestrator
description: Select and combine analysis methods for ambiguous or complex tasks. Use when users ask for "how to analyze", compare frameworks, need a method recommendation, need cross-method validation, or ask for better alternatives beyond one default method.
---

# Method Selection Orchestrator

Use this skill to choose one primary method and optional secondary methods, then produce a defendable analysis path.

## Workflow
1. Classify the problem type:
- `root-cause`: why a problem happens
- `decision`: choose among options
- `strategy`: stage planning under uncertainty
- `argument`: test whether a claim is valid
- `system`: understand feedback loops and side effects
2. Select one primary method and explain why it is the best fit.
3. Add zero to two secondary methods when they reduce blind spots.
4. Run analysis in this order:
- facts
- assumptions (with confidence)
- method steps
- conclusion
- verification plan
5. Output a method rationale section so the user can challenge or adjust the method choice.

## Method Combinations
1. Use `first-principles + logic` when assumptions are likely wrong.
2. Use `dialectical-materialism + systems-thinking` when conflicts evolve over phases.
3. Use `bayesian-updating + decision-analysis` when uncertainty changes over time.
4. Use `premortem + second-order-effects` before committing to a high-impact plan.

## Output Contract
1. `Problem Type`
2. `Chosen Method(s) and Why`
3. `Facts`
4. `Assumptions (confidence: high/medium/low)`
5. `Analysis Steps`
6. `Conclusion`
7. `Risks and Verification Next Steps`

## References
1. Read `references/method-cards.md` for method selection signals, anti-patterns, and quick examples.
