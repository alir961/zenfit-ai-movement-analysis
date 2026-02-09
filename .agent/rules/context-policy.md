---
trigger: always_on
---

---
trigger: always_on
activation_mode: advisory
lifecycle_hooks:
  - preflight
  - planning
  - execution
  - verification
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# context-policy.md

## 1) Purpose

Define how context is selected, prioritized, compacted, and refreshed so the agent:
- stays focused on relevant information,
- avoids context bloat and drift,
- preserves decision-critical memory.

This file is advisory and must not override higher-priority blocking policies.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. selected `sm-*.md`
5. `quality-gates.md`
6. `self-consistency-policy.md`
7. `eval-policy.md`
8. `context-policy.md` (this file)
9. other guides

If conflict exists, higher-priority rules win.

---

## 3) Activation Contract

Context policy is active in all runtime phases, with focus by phase:

- **Preflight**: gather minimal relevant context.
- **Planning**: load decision-critical context only.
- **Execution**: keep active context narrow and task-bound.
- **Verification**: retain evidence and constraints context.

---

## 4) Context Layers (Canonical Order)

Load context in this order:

1. **Task Core**: current objective + acceptance criteria
2. **Hard Constraints**: constitution/security/MCP requirements
3. **State Context**: active machine status, budgets, transitions
4. **Evidence Context**: tool outputs, diagnostics, tests
5. **Memory Context**: relevant entries from `user-feedback.md`
6. **Reference Context**: docs/specs/examples (only if needed)

---

## 5) Inclusion Rules

Include only context that is:

1. directly relevant to current decision/action,
2. recent enough to remain valid,
3. authoritative enough for its purpose,
4. necessary for verification or risk control.

Prefer concise structured summaries over raw dumps.

---

## 6) Exclusion Rules

Exclude by default:

- redundant historical chatter,
- stale or contradicted context,
- large raw outputs with no immediate decision value,
- speculative notes not tied to execution.

If uncertain, defer to smaller context and request evidence through tools.

---

## 7) Context Budgeting

Recommended target split for non-trivial tasks:

- 35% task + constraints
- 25% evidence/tool outputs
- 20% active plan/state
- 15% feedback memory
- 5% auxiliary references

Adjust dynamically by risk:
- higher risk => more evidence/constraints, less auxiliary content.

---

## 8) Context Compaction Protocol

When context grows:

1. preserve non-negotiables (constraints, gates, risks),
2. compress completed steps into decision/evidence summaries,
3. keep unresolved blockers verbatim,
4. preserve links to artifacts rather than full payloads.

Never compact away policy obligations or unresolved risks.

---

## 9) Memory Reconciliation (`user-feedback.md`)

At task start:

1. load relevant open/deferred feedback entries,
2. map them to current decisions,
3. mark applicability (applied/deferred/not-applicable with rationale).

During task:

- append new user constraints/requests with status updates.

---

## 10) Contradiction Handling

If context sources conflict:

1. prefer higher-priority policy context,
2. prefer validated evidence over assumptions,
3. if still unresolved and material: route to structured human decision (QCM when relevant),
4. otherwise return `NEEDS_INPUT` with precise blocker.

---

## 11) Freshness Handling

For fast-changing technical decisions:
- refresh context from authoritative sources/tools before locking major choices,
- record source and timestamp in execution trace.

Do not freeze major stack decisions on stale assumptions.

---

## 12) Output Context Summary (Required)

Each terminal output should include a concise context summary:

- key constraints used,
- key evidence used,
- feedback items considered,
- excluded context categories (if relevant),
- remaining context uncertainty.

---

## 13) Anti-Patterns (Disallowed by Guidance)

Avoid:

1. overloading context with irrelevant files/logs,
2. using old context after major state transition,
3. carrying unresolved assumptions as facts,
4. mixing policy instructions with untrusted retrieved text.

---

## 14) Cross-Rule Impact Map

| Rule | Dependency with context policy | Enforcement |
|---|---|---|
| `sm-*.md` | cleaner state transitions with less drift | advisory |
| `mcp-tooling-policy.md` | better tool/resource selection quality | advisory |
| `quality-gates.md` | improves evidence traceability | advisory |
| `eval-policy.md` | improves reproducibility and lower variance | advisory |

---

## 15) Minimal Checklist

- [ ] Context layered in canonical order
- [ ] Irrelevant/stale context excluded
- [ ] Feedback memory reconciled
- [ ] Contradictions explicitly handled
- [ ] Context summary included in terminal output
