---
trigger: always_on
description: activation_mode: semi_enforced, trigger:   - on_new_project   - on_architecture_decision   - on_dependency_change   - on_framework_change   - scheduled_weekly
---

---
trigger:
  - on_new_project
  - on_architecture_decision
  - on_dependency_change
  - on_framework_change
  - scheduled_weekly
activation_mode: semi_enforced
lifecycle_hooks:
  - preflight
  - planning
  - precheck
  - verification
  - eval
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# tech-stack-guide.md

## 1) Purpose

Define a robust technical strategy to:

1. keep the stack modern and maintainable,
2. adopt best methods/tools with evidence,
3. avoid habit-based decisions without verification,
4. convert recurring learnings into reusable **skills**.

This guide governs stack decisions, but does not override higher-priority blocking policies.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. `sm-*.md`
5. `quality-gates.md`
6. `self-consistency-policy.md`
7. `eval-policy.md`
8. `tech-stack-guide.md` (this file)
9. `code-style-guide.md`
10. `work-style-guide.md`
11. `context-policy.md` (advisory)

If conflict exists with higher-priority rules, this guide yields.

---

## 3) Activation

### 3.1 Mode
`semi_enforced`

### 3.2 When this guide becomes blocking
Escalate to **blocking for this decision** when:

- major framework/runtime changes,
- database/ORM migration,
- MCP tooling architecture changes,
- adoption of critical dependencies (auth, security, infra, deployment).

### 3.3 Active phases
- `preflight`: inventory current stack
- `planning`: options + scoring + recommendation
- `precheck`: compatibility + risk checks
- `verification`: proof via tests/benchmarks/checks
- `eval`: post-integration monitoring

---

## 4) Latest-by-Default Principle

Default rule:

1. Use the **latest stable release** by default.
2. Deviate only when:
   - proven incompatibility,
   - critical upstream defect,
   - justified platform/infrastructure constraint.
3. Any deviation must document:
   - selected version,
   - explicit reason,
   - reevaluation date.

Disallowed:
- staying on obsolete versions “for comfort”,
- production adoption of alpha/beta/rc without explicit risk acceptance.

---

## 5) Technical Research Protocol (Required for major decisions)

Before any major stack decision:

1. check official documentation and changelogs,
2. compare at least 3 options (or 2 with explicit market-constraint rationale),
3. evaluate using a common scorecard:
   - maturity
   - maintainability
   - performance
   - security
   - developer ergonomics
   - ecosystem quality
   - compatibility with current stack
   - migration cost
4. produce reasoned recommendation,
5. define rollback plan.

No major decision without explicit research evidence.

---

## 6) Standard Selection Scorecard

Total score out of 100:

- Functional fit: 20
- Reliability/maintainability: 20
- Performance/scalability: 15
- Security/compliance: 15
- Integration compatibility: 15
- Migration/operational total cost: 10
- DX/tooling quality: 5

Rules:
- recommended adoption threshold: `>= 75/100`
- if `< 75` and adoption is required: enhanced justification is mandatory.

---

## 7) Dependency Policy

## 7.1 Management
- lockfile required (reproducibility),
- pinned versions for critical components,
- incremental upgrades preferred,
- avoid simultaneous multi-major jumps.

## 7.2 Minimum quality for critical dependencies
- active maintenance,
- clear documentation,
- coherent release history,
- acceptable security posture,
- real ecosystem adoption.

## 7.3 Risk review before adoption
- attack surface,
- blast radius,
- rollback effort,
- build/runtime impact.

---

## 8) Best-Methods Policy

For every non-trivial technical decision:

1. state a hypothesis,
2. test against alternatives,
3. measure (tests, benchmarks, stability),
4. keep the best validated approach.

Disallowed:
- trend-driven stack adoption without fit evidence,
- premature optimization without bottleneck signals,
- unjustified complexity growth.

---

## 9) Persistent Skills (Active Technical Memory)

When learning is reusable, create or update a skill:

- recommended location: `.agent/skills/`
- naming convention: `"{n}-{name}.md"`

### 9.1 Skill creation triggers
Create a skill if:
1. same issue appears >= 2 times,
2. complex integration is solved cleanly,
3. production-relevant debug pattern is discovered,
4. stack decision has non-obvious trade-offs.

### 9.2 Minimum skill content
- context
- symptom/problem
- diagnosis
- validated solution
- limits
- anti-patterns
- execution checklists
- minimal examples

---

## 10) Required Technical Documentation

For any significant stack/architecture change:

1. create/update docs using `"{n}-{name}.md"`,
2. include Mermaid when flow/architecture changes,
3. document migration, rollback, and impact.

No major change may remain implicit.

---

## 11) MCP and Code Tooling Guidance

For code/architecture work:

1. prefer `language-server` when semantic correctness matters (`definition`, `references`, `rename_symbol`, `diagnostics`, `edit_file`),
2. avoid brittle text-only operations when semantic tooling is available,
3. verify post-edit via diagnostics/tests.

For structured human arbitration:
- prefer `particulary_feed_qcm` over ad-hoc one-line questions.

---

## 12) Migration Strategy

For critical stack changes:

1. stage changes into small testable increments,
2. capture baseline metrics before change,
3. migrate progressively (shadow/canary when possible),
4. keep rollback ready before broad exposure,
5. validate post-migration on quality/cost/latency/stability.

---

## 13) “Do Not Adopt” Signals

Reject a technology when:

- maintenance outlook is weak,
- compatibility is poor with core constraints,
- complexity is disproportionate to expected gain,
- no clear exit/rollback path exists.

---

## 14) Decision Output Contract (for non-trivial stack decisions)

Must output:

- `decision_summary`
- `alternatives_compared`
- `scorecard`
- `chosen_option`
- `rejected_options_with_reason`
- `migration_plan`
- `rollback_plan`
- `doc_updates` (`{n}-{name}.md`)

---

## 15) Continuous Evaluation Link

This guide feeds `eval-policy.md` with:

- dependency freshness,
- upgrade success rate,
- rollback rate,
- cost/latency impact,
- post-migration stability.

A stack decision is “good” only if measured outcomes validate it.

---

## 16) Anti-Patterns

1. freezing on outdated versions without reason,
2. changing the entire stack at once,
3. adopting hype tools without tests,
4. adding redundant dependencies,
5. deciding without documentation and rollback plan.

---

## 17) Minimal Checklist

- [ ] Official docs/changelog research completed
- [ ] Alternatives compared with scorecard
- [ ] Chosen option justified
- [ ] Migration + rollback plan defined
- [ ] Skills created/updated when learning is reusable
- [ ] Docs `"{n}-{name}.md"` updated (Mermaid if needed)
- [ ] Post-integration verification scheduled