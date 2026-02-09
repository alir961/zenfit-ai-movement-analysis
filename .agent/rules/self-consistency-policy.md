---
trigger: always_on
description: activation_mode: conditional_blocking, trigger: conditional
---

---
trigger: conditional
activation_mode: conditional_blocking
lifecycle_hooks:
  - classify
  - plan
  - verify
  - critique
  - decide
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# self-consistency-policy.md

## 1) Purpose

Define how the agent performs multi-strategy reasoning to improve decision quality on complex tasks, while controlling:
- cost,
- latency,
- drift,
- fake confidence.

This policy is **mandatory when triggered** and becomes blocking.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. selected `sm-*.md`
5. `quality-gates.md`
6. `self-consistency-policy.md` (this file)
7. `eval-policy.md`
8. style/work/tech/context guides

If a higher-priority policy is violated, self-consistency output is invalid.

---

## 3) Activation Contract

Self-consistency runs only when needed, but is mandatory once triggered.

### Activation modes
- `off`: trivial deterministic tasks
- `recommended`: moderate ambiguity, low-risk optimizations
- `mandatory`: risk/uncertainty thresholds exceeded

### Lifecycle placement
- Trigger decision in `CLASSIFY`
- Candidate generation in `PLAN`
- Strategy arbitration in `CRITIQUE`
- Confidence enforcement in `DECIDE`

---

## 4) Trigger Matrix (Mandatory Conditions)

Self-consistency is **mandatory** if any condition is true:

1. `risk_level >= medium`
2. `uncertainty > 0.35`
3. first verification cycle failed
4. multi-module impact scope
5. conflicting MCP evidence (resource/tool disagreement)
6. two or more viable strategies with material trade-offs
7. human preference branch likely (ties to G11)

If mandatory and skipped => `BLOCKED`.

---

## 5) Candidate Generation Protocol

When triggered, produce `K` strategy candidates:

- default `K=3`
- `K=2` allowed only for medium complexity with explicit justification
- `K=4` only for high-risk/high-impact changes

Each candidate must include:

1. strategy summary,
2. targeted scope,
3. expected benefits,
4. expected failure modes,
5. verification plan,
6. policy compliance statement,
7. rollback/fallback plan (medium/high risk).

Candidates that violate higher-priority policies are discarded immediately.

---

## 6) Candidate Diversity Requirement

Candidates must be substantively different (not paraphrases).

Minimum diversity dimensions:
- execution path (tooling/order/approach),
- risk handling,
- validation depth,
- cost/latency profile.

Near-duplicate candidates are collapsed and replaced.

---

## 7) Evidence-Backed Scoring Model

Score each candidate with weighted components:

- correctness: `0.40`
- constraint compliance: `0.25`
- robustness: `0.20`
- cost/latency efficiency: `0.15`

Each component scored in `[0..1]` with evidence.
No evidence => component score defaults to `0`.

### Optional risk-aware weighting
For high-risk tasks, robustness may be increased (e.g. `0.25`) while cost weight decreases, if justified.

---

## 8) Feasibility Filter (Pre-Score)

Before scoring, reject any candidate that:

1. violates security constraints,
2. lacks verifiable MCP path when MCP is relevant,
3. requires unavailable capability,
4. has no credible verification plan,
5. conflicts with accepted user feedback constraints.

Rejected candidates must be logged with reason.

---

## 9) Selection & Merge Rules

After scoring:

1. select highest score if delta to second >= `0.03`
2. if delta < `0.03`, prefer lower-risk/lower-cost compliant option
3. merge top 2 only when complementarity is explicit and verification remains bounded

No merge allowed if it increases blast radius without clear benefit.

---

## 10) Confidence Model

Compute post-verification confidence:

`confidence = 0.5 * verification_pass_rate + 0.3 * evidence_quality + 0.2 * inter_candidate_agreement`

Where each term is `[0..1]`.

### Minimum confidence thresholds
- low risk: `>= 0.65`
- medium risk: `>= 0.75`
- high risk: `>= 0.85`

Below threshold:
- iterate (if budget remains), or
- return `BLOCKED` / `NEEDS_INPUT` depending on blocker type.

---

## 11) Budget Controls (Anti-Cost Explosion)

Per run defaults:

- max SC rounds: `2`
- max candidates per round: `3` (unless high-risk justified)
- max re-score loops: `1`
- max strategy resets (`CRITIQUE -> PLAN`): align with active state machine budget
- budget exhaustion without decision confidence => `BLOCKED`

No unbounded exploration.

---

## 12) Integration with MCP Policy

When MCP-relevant:

1. candidate viability must include MCP path (`discover -> call -> postcheck`)
2. tool outputs must be validated before being used as scoring evidence
3. for semantic code decisions, prioritize `language-server` evidence when relevant
4. for preference-sensitive branches, use `particulary_feed_qcm` when relevant (or justified bypass)

SC cannot bypass MCP/security constraints.

---

## 13) Integration with User Feedback Memory

Self-consistency must consume `user-feedback.md` constraints during candidate generation.

Required:
- mark which feedback items each candidate satisfies/conflicts with
- penalize candidates that ignore relevant user constraints
- if conflict cannot be resolved safely, prefer `NEEDS_INPUT` with explicit alternatives

---

## 14) Integration with Quality Gates

Self-consistency directly supports:
- `G7` (robustness),
- `G11` (human decision capture when relevant),
and indirectly improves `G1/G3/G4`.

A candidate cannot be selected if it cannot plausibly pass mandatory gates for the current risk tier.

---

## 15) Output Contract (SC Section)

When SC triggered, terminal payload must include:

- `sc_triggered`: true
- `trigger_reasons`: list
- `candidate_count`
- `candidate_score_table` (id + component scores + total)
- `selected_candidate` (or merged set)
- `selection_rationale`
- `confidence`
- `budget_used` (rounds/candidates/retries)
- `discarded_candidates` (optional + reasons)
- `lessons_learned` (concise)

If SC mandatory and section missing => invalid completion.

---

## 16) Anti-Laziness / Anti-Drift Hard Rules

Immediate `BLOCKED` if any:

1. mandatory SC skipped
2. first candidate auto-selected without scoring
3. fabricated score with no evidence
4. repetitive no-op candidate generation
5. verbosity inflation with no strategy differentiation
6. confidence declared without formula inputs

---

## 17) Failure Handling

If SC fails to produce a safe winner:

1. emit blocker class:
   - capability gap
   - evidence conflict
   - unresolved user arbitration
   - budget exhaustion
2. choose terminal status:
   - `NEEDS_INPUT` for essential user decision,
   - `BLOCKED` otherwise
3. provide smallest safe next step.

---

## 18) Cross-Rule Impact Map

| Rule | How SC depends on it | Enforcement |
|---|---|---|
| `security-policy.md` | invalidates unsafe candidates | blocking |
| `mcp-tooling-policy.md` | requires viable MCP evidence paths | blocking |
| `sm-*.md` | defines phase hooks and retry budgets | blocking |
| `quality-gates.md` | candidate must be gate-pass feasible | blocking |
| `eval-policy.md` | tracks SC efficacy vs cost over time | release-significant |

---

## 19) Minimal Checklist

- [ ] Trigger matrix evaluated
- [ ] Valid candidate set generated
- [ ] Feasibility filter applied
- [ ] Weighted scoring recorded
- [ ] Winner selected/merged with rationale
- [ ] Confidence computed from verified evidence
- [ ] Budget respected
- [ ] SC output contract included