---
trigger: always_on
description: activation_mode: conditional_blocking, trigger: task_type == "coding" || task_type == "bugfix" || task_type == "refactor" || task_type == "tests" || task_type == "infra"
---

---
trigger: task_type == "coding" || task_type == "bugfix" || task_type == "refactor" || task_type == "tests" || task_type == "infra"
activation_mode: conditional_blocking
lifecycle_hooks:
  - intake
  - feedback_sync
  - classify
  - plan
  - precheck
  - act
  - verify
  - doc_sync
  - critique
  - decide
owner: Agent Runtime
version: 3.0.0
last_updated: 2026-02-08
---

# sm-coding.md

## 1) Purpose

Operational state machine for coding work:
- feature delivery,
- bug fixes,
- refactors,
- test improvements,
- infra/code-adjacent updates.

This machine is **execution-grade**: no completion without evidence, policy compliance, and documentation sync.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. `sm-coding.md` (this file)
5. `quality-gates.md`
6. `self-consistency-policy.md`
7. `eval-policy.md`
8. style/work/tech/context guides

If conflict with higher-priority rule, higher-priority rule wins.
If mandatory requirement cannot be satisfied safely => `BLOCKED`.

---

## 3) Activation Contract

`sm-coding` activates when task classification indicates implementation work.

### Entry conditions (all required)
1. Task needs code/config/test mutation.
2. Target scope is at least partially identifiable.
3. No incident-level emergency requiring `sm-incident`.

### Exit conditions
- `DONE` only if all required quality/security/MCP gates pass.
- `BLOCKED` for policy, capability, or verification dead-ends.
- `NEEDS_INPUT` for essential unresolved user decision/input.

### Re-routing
- to `sm-research`: missing or contradictory requirements.
- to `sm-debug`: repeated failing verification with unclear root cause.
- to `sm-incident`: production/security critical symptom detected.
- to `sm-refactor`: behavior done, structural debt remains as primary task.

---

## 4) Canonical State Graph

```mermaid
stateDiagram-v2
    [*] --> INTAKE
    INTAKE --> FEEDBACK_SYNC
    FEEDBACK_SYNC --> CLASSIFY
    CLASSIFY --> PLAN
    PLAN --> PRECHECK
    PRECHECK --> ACT
    ACT --> VERIFY
    VERIFY --> DOC_SYNC
    DOC_SYNC --> CRITIQUE
    CRITIQUE --> DECIDE

    VERIFY --> ACT: repair loop (bounded)
    CRITIQUE --> PLAN: strategy correction (bounded)

    DECIDE --> DONE
    DECIDE --> BLOCKED
    DECIDE --> NEEDS_INPUT

    DONE --> [*]
    BLOCKED --> [*]
    NEEDS_INPUT --> [*]
````

Forbidden transitions:

* `PLAN -> DONE`
* `ACT -> DONE`
* `INTAKE -> ACT`
* Any direct terminal transition without `VERIFY` and `DECIDE`

---

## 5) Runtime Budgets (Default)

* max iterations per run: `6`
* max tool calls per iteration: `8`
* max retries per identical failing action: `2`
* max strategy resets (`CRITIQUE -> PLAN`): `2`
* budget overrun without safe completion => `BLOCKED`

Budgets may be stricter in high-risk contexts.

---

## 6) State Contracts

## 6.1 INTAKE

### Objective

Normalize task request into actionable execution intent.

### Required outputs

* `task_summary`
* `acceptance_criteria`
* `constraints` (policy/security/latency/cost/style)
* `initial_unknowns`

### Fail

If objective cannot be meaningfully scoped => `NEEDS_INPUT`.

---

## 6.2 FEEDBACK_SYNC

### Objective

Load and reconcile user intent memory before planning.

### Mandatory actions

1. Read `user-feedback.md`.
2. Extract relevant open/deferred items.
3. Map them to current task decisions.

### Required outputs

* `feedback_items_considered`
* `applied_feedback`
* `deferred_feedback_with_reason`
* `conflict_flags`

### Fail

* missing/inaccessible feedback memory on relevant tasks => `BLOCKED`.

---

## 6.3 CLASSIFY

### Objective

Set execution strategy profile.

### Required classification

* `task_type`: feature|bugfix|refactor|tests|infra
* `risk_level`: low|medium|high
* `uncertainty`: [0..1]
* `impact_scope`: file|module|multi-module
* `mcp_relevance`: yes|no
* `code_semantic_needed`: yes|no
* `human_decision_needed`: yes|no

### Routing implications

* `code_semantic_needed=yes` => prioritize `language-server`.
* `human_decision_needed=yes` => route to `particulary_feed_qcm`.

---

## 6.4 PLAN

### Objective

Build executable, verifiable plan before mutation.

### Required plan fields

* `target_files` (expected)
* `change_intent_per_target`
* `mcp_plan` (servers, primitives, checks)
* `verification_plan` (tests/lint/typecheck/diagnostics)
* `rollback_plan`
* `doc_sync_plan` (`{n}-{name}.md` targets + Mermaid scope)
* `qcm_plan` (if human decision needed)

### Hard rule

No code edits before valid plan.

---

## 6.5 PRECHECK

### Objective

Establish baseline and guardrails.

### Mandatory checks

1. Capability discovery for planned MCP calls.
2. Baseline diagnostics/tests (where applicable).
3. Trust/scope check against security policy.
4. Symbol map precheck via `language-server` when semantic edits expected.

### Required outputs

* `baseline_quality_snapshot`
* `baseline_diagnostics`
* `scope_confirmation`

---

## 6.6 ACT

### Objective

Apply bounded changes with traceable intent.

### Mandatory behavior

1. Keep changes atomic and reversible.
2. Stay in planned scope unless explicitly justified.
3. Prefer semantic tooling:

   * `definition`, `references`, `rename_symbol`, `edit_file`, `diagnostics`.
4. If material user arbitration is needed, use `particulary_feed_qcm`.

### Required trace per batch

* `intent`
* `files_or_symbols_changed`
* `why_this_batch`
* `expected_effect`
* `immediate_risks`

### Hard fail patterns

* broad blind replacements when semantic tooling is available,
* unbounded batch edits,
* side effects outside declared scope without rationale.

---

## 6.7 VERIFY

### Objective

Prove correctness and policy compliance.

### Validation ladder (ordered)

1. formatting/lint/type/static checks (if applicable)
2. targeted tests for changed behavior
3. diagnostics re-run (especially after symbol edits)
4. regression subset for impacted area
5. policy/security check confirmation

### Required outputs

* `checks_run`
* `results`
* `failures_with_root_cause`
* `repair_decision`

### Loopback

`VERIFY -> ACT` allowed only within retry budget.

---

## 6.8 DOC_SYNC

### Objective

Keep docs as source-of-truth aligned with implementation.

### Mandatory actions

1. Update/create docs with naming convention **`{n}-{name}.md`**.
2. Add/update Mermaid when architecture/flow/state/API behavior changed.
3. Ensure docs reflect actual behavior, constraints, and failure modes.

### Required outputs

* `docs_updated`
* `mermaid_updated_or_not_applicable`
* `doc_drift_check`

### Hard fail

* implementation changed but docs not synchronized => `BLOCKED`.

---

## 6.9 CRITIQUE

### Objective

Second-pass improvement and robustness check.

### Checklist

* acceptance criteria fully met?
* complexity justified?
* edge cases addressed?
* policy/tooling fully respected?
* docs and feedback fully reconciled?

### Self-consistency trigger

If any:

* `uncertainty > 0.35`
* `risk_level >= medium`
* verification failed at least once
* multi-module impact

Then run self-consistency protocol (per policy) before final decision.

---

## 6.10 DECIDE

### Objective

Emit deterministic terminal status.

### `DONE` requires all:

1. required gates passed for risk tier,
2. security status `PASS`,
3. MCP evidence complete when relevant,
4. docs synced (`{n}-{name}.md` + Mermaid if required),
5. feedback reconciliation complete,
6. residual risks documented.

### `BLOCKED` if:

* policy violation,
* verification dead-end,
* capability gap,
* budget exhausted,
* unresolved doc or feedback obligations.

### `NEEDS_INPUT` if:

* essential user decision remains unresolved (after QCM/fallback path).

---

## 7) MCP Routing Rules Inside sm-coding

## 7.1 language-server (preferred for semantic code work)

Use when:

* symbol ownership unclear,
* rename/refactor impacts multiple references,
* diagnostics needed pre/post edit,
* cross-file confidence needed.

Minimum semantic flow:

1. `definition/references` before edit,
2. `edit_file/rename_symbol`,
3. `diagnostics` post-edit.

## 7.2 particulary_feed_qcm (preferred for structured user decisions)

Use when:

* options have trade-offs,
* UX/strategy preferences matter,
* high-impact branching decision is required.

QCM results must:

* be reflected in plan/critique,
* be appended into `user-feedback.md`.

---

## 8) Quality Gate Mapping (sm-coding obligations)

Minimum gate mapping by risk:

* low: G0, G1, G2, G3, G5 (+ G6 if MCP relevant) + G9 + G10
* medium: low + G4 + G7 (+ G11 if human decision relevant)
* high: medium + G8 (+ stricter evidence depth)

If any required gate fails => cannot return `DONE`.

---

## 9) Output Contract (sm-coding terminal payload)

Required fields:

* `status`: DONE|BLOCKED|NEEDS_INPUT
* `task_summary`
* `classification`: {task_type, risk_level, uncertainty, impact_scope}
* `changes`: [{target, action, rationale}]
* `verification`: {checks_run, results}
* `mcp`: {servers_used, key_calls, routing_rationale}
* `docs`: {updated_files, mermaid_status}
* `feedback_sync`: {items_considered, applied, deferred}
* `policy`: {security_status, gate_summary}
* `residual_risks`
* `next_safe_step`

Missing mandatory field => invalid completion.

---

## 10) Hard-Fail Triggers

Immediate `BLOCKED` if any:

1. terminal output without verification evidence,
2. MCP-relevant task without MCP evidence,
3. skipped `language-server` for required semantic operations,
4. skipped QCM where structured user arbitration was required,
5. skipped DOC_SYNC for meaningful behavior changes,
6. skipped FEEDBACK_SYNC when relevant items exist,
7. fabricated trace or unverifiable claims.

---

## 11) Cross-Rule Impact Map

| Rule                         | How sm-coding depends on it                       | Enforcement |
| ---------------------------- | ------------------------------------------------- | ----------- |
| `security-policy.md`         | security gate and trust boundaries in every phase | blocking    |
| `mcp-tooling-policy.md`      | MCP routing, hygiene, trace, bounded autonomy     | blocking    |
| `quality-gates.md`           | deterministic DONE criteria                       | blocking    |
| `self-consistency-policy.md` | critique-stage candidate selection when triggered | blocking    |
| `eval-policy.md`             | run-level quality/cost/robustness measurement     | blocking    |

---

## 12) Minimal Run Checklist

* [ ] Intake normalized with criteria
* [ ] Feedback synced from `user-feedback.md`
* [ ] Classification includes MCP/QCM/semantic flags
* [ ] Plan includes verification + doc sync + rollback
* [ ] Semantic-safe ACT path used when needed
* [ ] VERIFY ladder passed
* [ ] DOC_SYNC completed (`{n}-{name}.md`)
* [ ] CRITIQUE + self-consistency (if triggered)
* [ ] Deterministic terminal status emitted