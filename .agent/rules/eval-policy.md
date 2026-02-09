---
trigger: always_on
description: activation_mode: release_blocking, trigger:   - on_rule_change   - on_prompt_change   - on_runtime_change   - on_model_change   - scheduled
---

---
trigger:
  - on_rule_change
  - on_prompt_change
  - on_runtime_change
  - on_model_change
  - scheduled
activation_mode: release_blocking
lifecycle_hooks:
  - pre_release
  - canary
  - promotion
  - rollback
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# eval-policy.md

## 1) Purpose

Define the mandatory evaluation system that governs:
- rule updates,
- prompt/runtime/model changes,
- promotion decisions,
- rollback decisions.

No change is considered an improvement without measured evidence.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md`
4. selected `sm-*.md`
5. `quality-gates.md`
6. `self-consistency-policy.md`
7. `eval-policy.md` (this file)
8. style/work/tech/context guides

If higher-priority policy is violated, eval result is invalid regardless of score.

---

## 3) Activation Contract

## 3.1 Mandatory activation events
Run eval pipeline when any of these changes occur:
1. Any `*.md` rule change in runtime policy set
2. State machine transition logic change
3. MCP routing or tool contract change
4. Model/provider/temperature/token-policy change
5. Prompt contract or output schema change
6. Verification stack changes (tests/linters/diagnostics strategy)

## 3.2 Scheduled activation
- daily smoke evals (fast subset)
- weekly full regression
- monthly robustness/security expansion

## 3.3 Blocking effect
Promotion to production is blocked unless release gates pass.

---

## 4) Eval Objectives

1. Increase real task success, not stylistic fluency.
2. Preserve policy/security correctness.
3. Reduce regressions and brittle behavior.
4. Keep cost/latency within budget.
5. Prove improvement with reproducible artifacts.

---

## 5) Eval Suites (Versioned)

Maintain these suites (each versioned independently):

1. `core-functional`
2. `tooling-precision`
3. `policy-security`
4. `robustness`
5. `efficiency`
6. `long-horizon`
7. `docs-feedback-governance`

### 5.1 Suite purpose

- **core-functional**: acceptance criteria completion.
- **tooling-precision**: MCP routing quality, arg correctness, post-check quality.
- **policy-security**: policy violations, injection resilience, leak prevention.
- **robustness**: noisy/conflicting/partial-failure scenarios.
- **efficiency**: p50/p95 latency, calls per success, cost per success.
- **long-horizon**: multi-step stability across state transitions.
- **docs-feedback-governance**: doc sync + feedback memory + QCM routing quality.

---

## 6) Dataset Governance

## 6.1 Required case schema
Each eval case must define:

- `case_id`
- `task_input`
- `context_bundle`
- `expected_outcome`
- `risk_tier` (low|medium|high)
- `grader_spec`
- `mcp_relevance`
- `human_decision_relevance`
- `doc_sync_expected` (yes|no)

## 6.2 Dataset split policy
- `dev`: fast iteration
- `pre_release`: gating
- `holdout`: never used for tuning
- `canary`: production-like recent samples

No release decision allowed from `dev` only.

## 6.3 Versioning
SemVer per suite:
- major: rubric/schema incompatible changes
- minor: additive case growth
- patch: metadata/label fixes

---

## 7) Grader Architecture

Use layered graders:

1. deterministic graders (schema/rules/gates)
2. programmatic behavioral graders
3. model-based graders (only when deterministic is insufficient)

Authority rule:
- deterministic > programmatic > model-based

Critical policy/security failures cannot be overridden by aggregate scoring.

---

## 8) Mandatory Metrics

## 8.1 Outcome quality
- `task_success_rate`
- `acceptance_coverage_rate`
- `quality_gate_pass_rate`

## 8.2 MCP/tooling quality
- `mcp_relevance_precision`
- `tool_call_precision`
- `tool_arg_accuracy`
- `post_condition_pass_rate`

## 8.3 Language-server quality
- `ls_usage_relevance_precision`
- `semantic_edit_success_rate`
- `post_edit_diagnostics_pass_rate`
- `rename_ref_integrity_rate`

## 8.4 Human arbitration quality (QCM)
- `qcm_usage_relevance_precision`
- `qcm_timeout_rate`
- `qcm_decision_integration_rate`
- `needs_input_after_qcm_rate`

## 8.5 Documentation & feedback governance
- `doc_sync_pass_rate`
- `mermaid_coverage_rate` (when flow/architecture changed)
- `naming_convention_pass_rate` for `{n}-{name}.md`
- `feedback_capture_rate` (`user-feedback.md`)
- `feedback_application_rate`

## 8.6 Security/policy
- `policy_violation_rate`
- `prompt_injection_resistance_rate`
- `secret_leak_incidents` (must be zero for promotion)

## 8.7 Reliability & efficiency
- `blocked_rate`
- `retry_exhaustion_rate`
- `state_transition_error_rate`
- `p50_latency_ms`, `p95_latency_ms`
- `mean_tool_calls_per_task`
- `cost_per_success`

---

## 9) Release Gates (Promotion Criteria)

A candidate may be promoted only if all pass:

1. no critical policy/security regression
2. `task_success_rate` non-inferior or better vs baseline
3. `quality_gate_pass_rate` non-inferior
4. MCP precision metrics above configured thresholds
5. language-server and QCM relevance precision above thresholds
6. doc/feedback governance metrics above thresholds
7. p95 latency and cost within budget envelope
8. holdout suite passes required floor

Failing any gate => promotion denied.

---

## 10) A/B, Shadow, Canary

## 10.1 A/B protocol
- same dataset snapshot
- same runtime constraints
- baseline vs candidate

## 10.2 Shadow mode
Candidate runs in parallel without affecting user-facing decisions.
Promotion requires stability across defined shadow window.

## 10.3 Canary
Small traffic slice with strict monitors:
- security incidents
- blocked spikes
- latency/cost spikes
- governance regressions (docs/feedback/QCM/LS usage)

Automatic rollback on critical breach.

---

## 11) Threshold Source of Truth

Thresholds must be defined in:

- `eval-thresholds.yaml`

No hidden thresholds in code/comments.
Changes to thresholds require:
- rationale
- expected impact
- approval trail
- re-baselining note

---

## 12) Failure Analysis Protocol

For each failed run:

1. cluster by root cause:
   - planning
   - routing
   - MCP args/schema
   - verification gaps
   - security/policy
   - docs/feedback governance
2. prioritize top 3 corrective actions
3. map each corrective action to:
   - rule file(s),
   - state machine step,
   - tests to add
4. rerun targeted suites then full gating suites

---

## 13) Rollback Policy

Immediate rollback triggers:

1. critical security regression
2. sustained task success degradation
3. unacceptable latency/cost increase
4. repeated incident pattern linked to candidate
5. governance collapse (doc sync or feedback memory below floor)

Rollback target: last known-good promoted baseline.

---

## 14) Required Eval Artifacts

Every eval run must emit:

- `eval-manifest.json`
- `eval-thresholds.yaml` (resolved snapshot)
- `reports/{run_id}/summary.json`
- `reports/{run_id}/metrics.json`
- `reports/{run_id}/gate_results.json`
- `reports/{run_id}/failures.json`
- `reports/{run_id}/promotion_decision.md`

All artifacts must be reproducible and auditable.

---

## 15) Promotion Decision Contract

`promotion_decision.md` must include:

1. candidate vs baseline versions
2. suite versions
3. metric deltas
4. gate pass/fail table
5. known risks
6. final decision: promote|hold|rollback
7. next actions

No decision without explicit rationale.

---

## 16) Cross-Rule Impact Map

| Rule | Dependency on eval | Enforcement |
|---|---|---|
| `quality-gates.md` | eval tracks gate drift over time | release-blocking |
| `mcp-tooling-policy.md` | eval validates routing/tool precision | release-blocking |
| `sm-*.md` | eval validates transition stability | release-blocking |
| `self-consistency-policy.md` | eval measures quality gain vs cost overhead | release-blocking |
| docs/feedback invariants | eval enforces `G9/G10/G11` outcomes | release-blocking |

---

## 17) Hard-Fail Conditions

Automatic eval FAIL if any:

1. missing holdout results for release candidate
2. unverifiable/fabricated evidence artifacts
3. critical policy/security violation
4. missing governance metrics (docs/feedback/QCM/LS relevance)
5. unresolved threshold source mismatch

---

## 18) Minimal Checklist

- [ ] Correct activation trigger detected
- [ ] Required suites executed
- [ ] Metrics computed with reproducible artifacts
- [ ] Release gates evaluated
- [ ] Promotion/rollback decision documented
- [ ] Corrective actions mapped for failed areas