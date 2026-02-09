---
trigger: always_on
description: activation_mode: completion_blocking, trigger: on_verify_or_decide
---

---
trigger: on_verify_or_decide
activation_mode: completion_blocking
lifecycle_hooks:
  - verification
  - critique
  - decide
  - completion
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# quality-gates.md

## 1) Purpose

Define deterministic pass/fail gates required before any terminal status.
This file prevents:
- unverifiable completion,
- silent regressions,
- policy/security bypass,
- documentation drift,
- ignored user feedback.

`DONE` is valid only when all required gates pass.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. selected `sm-*.md`
5. `quality-gates.md` (this file)
6. `self-consistency-policy.md`
7. `eval-policy.md`
8. style/work/tech/context guides

If a higher-priority rule is violated, gate result is automatic FAIL.

---

## 3) Activation Contract

This policy activates as a blocking layer during:
- `VERIFY`
- `CRITIQUE`
- `DECIDE`
- `COMPLETION`

No terminal status may be emitted before gate evaluation.

---

## 4) Status Contract

Terminal statuses:
- `DONE`
- `BLOCKED`
- `NEEDS_INPUT`

Rules:
1. `DONE` requires all mandatory gates to pass.
2. `BLOCKED` if any blocking gate fails and cannot be repaired safely within budget.
3. `NEEDS_INPUT` only when missing user input is the sole blocker.

---

## 5) Gate Set (G0 -> G11)

## G0 — Scope Integrity Gate (Blocking)
**Goal:** confirm execution stayed in declared scope.

Pass:
- changed artifacts are planned or explicitly justified,
- no unexplained side effects.

Fail:
- hidden scope expansion,
- unrelated files changed without rationale.

---

## G1 — Spec Coverage Gate (Blocking)
**Goal:** ensure acceptance criteria are fully mapped to evidence.

Pass:
- each criterion has explicit proof,
- unresolved ambiguities are escalated with status.

Fail:
- “looks correct” without criterion-level mapping,
- partial requirement coverage.

---

## G2 — Static Quality Gate (Blocking where applicable)
**Goal:** baseline code health.

Pass (if supported by stack):
- format checks pass,
- lint checks pass,
- type/static checks pass.

Risk note:
- low risk may allow targeted scope;
- medium/high require broader relevant scope.

---

## G3 — Functional Verification Gate (Blocking)
**Goal:** prove behavior correctness.

Pass:
- targeted tests for changed behavior pass,
- critical path checks pass.

Fail:
- no feasible tests run,
- failing tests ignored/suppressed.

---

## G4 — Regression Gate (Blocking for medium/high risk)
**Goal:** prevent breaking existing behavior.

Pass:
- regression subset on impacted surface passes,
- no critical regressions introduced.

High risk:
- broader regression confidence required.

---

## G5 — Security & Policy Gate (Always Blocking)
**Goal:** enforce security-policy invariants.

Pass:
- no policy violation,
- sensitive actions passed Security Gate,
- no secret leakage,
- trust boundary and injection protections respected.

Any critical violation => immediate FAIL.

---

## G6 — MCP Evidence Gate (Blocking on MCP-relevant tasks)
**Goal:** ensure real, validated MCP execution happened when relevant.

Pass:
- MCP relevance assessed and logged,
- precheck/postcheck performed,
- outputs validated before reuse,
- trace present.

Additional expectation for code tasks:
- `language-server` used when semantic safety required, or justified bypass.

Fail:
- MCP-relevant task completed with no MCP evidence,
- unvalidated tool output consumption.

---

## G7 — Robustness Gate (Blocking for medium/high risk)
**Goal:** ensure solution handles realistic edge cases.

Pass:
- key edge cases identified and handled/tested/rationalized,
- known limitations documented,
- fallback path documented for risky operations.

---

## G8 — Operability Gate (Blocking for deployable/high-impact changes)
**Goal:** enforce release/operations readiness.

Pass:
- rollback path is explicit and practical,
- runtime observability impact acknowledged if relevant,
- operational risk summary present.

---

## G9 — Documentation Sync Gate (Blocking)
**Goal:** keep docs accurate with implementation.

Pass:
- docs updated for meaningful behavior/API/architecture/workflow changes,
- naming convention `"{n}-{name}.md"` respected,
- Mermaid included when flow/architecture/state transitions changed,
- no obvious doc drift.

Fail:
- changed implementation without matching docs.

---

## G10 — User Feedback Memory Gate (Blocking)
**Goal:** ensure user intent memory is applied.

Pass:
- `user-feedback.md` read during run,
- relevant items mapped to decisions,
- new relevant feedback appended with status/rationale.

Fail:
- relevant feedback ignored,
- missing reconciliation evidence.

---

## G11 — Human Decision Capture Gate (Conditional Blocking)
**Goal:** ensure structured user arbitration when needed.

Applies when decision is:
- multi-option with trade-offs,
- preference-sensitive,
- high-impact branch.

Pass:
- `particulary_feed_qcm` used and integrated, OR
- explicit justified bypass + safe fallback + clear `NEEDS_INPUT` if unresolved.

Fail:
- ad-hoc guessing where structured user decision was required.

---

## 6) Risk-Tier Mandatory Gate Matrix

## Low Risk
Required: `G0, G1, G2, G3, G5, G9, G10` (+ `G6` if MCP-relevant, + `G11` if human decision relevant)

## Medium Risk
Required: Low + `G4, G7` (+ `G6/G11` if applicable)

## High Risk
Required: Medium + `G8` (+ stronger evidence depth across all required gates)

No risk-tier downgrade without explicit rationale in trace.

---

## 7) Gate Evaluation Record (Required Shape)

Each evaluated gate must produce:

- `gate_id`
- `applicable` (true/false)
- `status` (PASS|FAIL|N/A)
- `evidence_summary`
- `artifacts_refs` (non-sensitive refs)
- `failure_reason` (if FAIL)
- `repair_action` (if FAIL and retry possible)

Missing record for applicable gate => treated as FAIL.

---

## 8) Blocking Logic

1. If any mandatory applicable gate = FAIL:
   - attempt bounded repair loop only if safe and budget allows.
2. If repair fails or budget exhausted:
   - terminal status = `BLOCKED`.
3. `DONE` forbidden while any mandatory gate is FAIL or unevaluated.

---

## 9) Repair Loop Policy

Allowed repair loops are bounded by state machine budget.

Repair loop requires:
- concise root cause,
- minimal corrective action plan,
- re-evaluation of failed gates only (plus dependencies).

No infinite or near-infinite loops.

---

## 10) Completion Criteria (Global)

`DONE` requires all:
1. every mandatory applicable gate PASS,
2. no unresolved critical policy/security issue,
3. acceptance criteria fully evidenced,
4. residual risks explicitly documented,
5. next-step recommendation included.

Else:
- `BLOCKED` or `NEEDS_INPUT` according to blocker type.

---

## 11) Terminal Output Contract (Quality Section)

Final output must include:

- `quality_gates`: list of evaluated gates with status
- `risk_tier`
- `mandatory_gates_passed`: true/false
- `failed_gates`: list
- `repair_attempts`: summary
- `final_status`: DONE|BLOCKED|NEEDS_INPUT

If missing => invalid completion payload.

---

## 12) Cross-Rule Impact Map

| Rule | Dependency on quality gates | Enforcement |
|---|---|---|
| `sm-*.md` | determines applicability and risk tier | blocking |
| `security-policy.md` | feeds G5 decisions | blocking |
| `mcp-tooling-policy.md` | feeds G6/G11 decisions | blocking |
| `self-consistency-policy.md` | influences critique confidence before decide | conditional blocking |
| `eval-policy.md` | tracks gate pass/fail trends across versions | release blocking |

---

## 13) Hard-Fail Triggers

Immediate terminal `BLOCKED` if any:

1. fake or unverifiable evidence,
2. critical security violation (G5),
3. missing doc sync on meaningful change (G9),
4. ignored relevant user feedback memory (G10),
5. skipped structured human arbitration when required (G11),
6. attempt to mark `DONE` with unevaluated mandatory gate.

---

## 14) Minimal Checklist

- [ ] Applicable gates resolved
- [ ] Mandatory gates pass for risk tier
- [ ] MCP and security evidence included
- [ ] Docs synchronized (`{n}-{name}.md` + Mermaid when required)
- [ ] User feedback reconciled
- [ ] Terminal payload complete and auditable