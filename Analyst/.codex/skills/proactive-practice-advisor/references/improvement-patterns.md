# Improvement Patterns

## 1) Add a Lightweight Decision Record
- Use when: Scope, tradeoff, or priority changes frequently.
- Pattern: Capture decision, reason, alternatives, revisit trigger.
- Benefit: Reduces repeated debates.

## 2) Add a Minimal Validation Gate
- Use when: Output quality drifts between iterations.
- Pattern: Define 3 to 5 pass/fail checks before completion.
- Benefit: Improves consistency with low overhead.

## 3) Shift from One-Pass to Iterative Delivery
- Use when: Uncertainty is high or requirements evolve.
- Pattern: Deliver a small valid version, then iterate with evidence.
- Benefit: Faster learning and lower rework risk.

## 4) Separate Facts vs Assumptions
- Use when: Discussions mix certainty and speculation.
- Pattern: Maintain explicit lists with confidence labels.
- Benefit: Improves decision clarity.

## 5) Add a Premortem Before High-Cost Changes
- Use when: A change is costly or hard to roll back.
- Pattern: Ask "If this fails, what caused it?" and add preventions.
- Benefit: Surfaces hidden risks early.
