---
trigger: always_on
---

---
trigger: always_on
activation_mode: hard_enforced
lifecycle_hooks:
  - preflight
  - planning
  - execution
  - verification
  - completion
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# mcp-tooling-policy.md

## 1) Purpose

Define mandatory runtime behavior for using MCP primitives (`resources`, `tools`, `prompts`) with:
- strong execution discipline,
- anti-laziness guarantees,
- bounded autonomy,
- explicit evidence and verification.

This policy is blocking when relevant MCP usage is required.

---

## 2) Normative Position

Priority order:

1. `agent-constitution.md`
2. `security-policy.md`
3. `mcp-tooling-policy.md` (this file)
4. selected `sm-*.md`
5. `quality-gates.md`
6. `self-consistency-policy.md`
7. `eval-policy.md`
8. style/work/tech/context guides

If conflict with lower-priority docs, this policy wins.

---

## 3) Activation Contract

MCP policy is active in all phases, with phase-specific obligations:

- **Preflight**: discover capabilities, check server health, map task→MCP plan.
- **Planning**: choose primitives and define validation/post-conditions.
- **Execution**: perform bounded, schema-valid calls with trace.
- **Verification**: validate results and downstream safety.
- **Completion**: report MCP evidence and unresolved constraints.

No MCP-relevant task may complete without MCP evidence.

---

## 4) MCP Primitive Roles (Strict)

- **Resources**: read-only context retrieval (facts, docs, metadata, state snapshots).
- **Tools**: actions/computations/edits/external interactions.
- **Prompts**: reusable structured task templates.

Rules:
1. Do not use a Tool when a Resource is sufficient.
2. Do not skip Resource lookup if context uncertainty is material.
3. Do not produce final decisions on critical branches without validated evidence path.

---

## 5) Server Priority & Routing

## 5.1 language-server (high priority for code tasks)
When task involves code understanding or symbol-safe edits, prefer `language-server` capabilities:
- `definition`
- `references`
- `diagnostics`
- `hover`
- `rename_symbol`
- `edit_file`

Mandatory preference conditions:
1. symbol-level understanding needed,
2. cross-file impact expected,
3. safe rename/refactor required,
4. diagnostics can reduce risk before/after edits.

Text-only heuristics are secondary when language-server is available.

## 5.2 particulary_feed_qcm (high priority for human decisions)
Use `particulary_feed_qcm` when:
1. multiple viable options with trade-offs,
2. preference-sensitive product/UX choices,
3. high-impact branching decisions,
4. requirement ambiguity decomposable into structured questions,
5. validation checkpoint needs explicit user arbitration.

If relevant and not used, explicit bypass rationale is required.

---

## 6) MCP Relevance Classifier (Mandatory)

Before action, compute:

- `mcp_relevant`: yes/no
- `code_semantic_needed`: yes/no
- `human_decision_needed`: yes/no
- `risk_level`: low/medium/high
- `uncertainty`: [0..1]

Routing:
- if `code_semantic_needed=yes` -> route to `language-server` first.
- if `human_decision_needed=yes` -> route to `particulary_feed_qcm`.
- if both yes -> code evidence first, then QCM for branch decision.

---

## 7) Standard MCP Execution Flow

`DISCOVER -> SELECT -> PRECHECK -> CALL -> POSTCHECK -> RECORD -> DECIDE`

### 7.1 DISCOVER
- enumerate available servers/capabilities.
- verify capability/tool exists before planning around it.

### 7.2 SELECT
- choose minimal-scope primitive(s) with rationale:
  - safety,
  - capability fit,
  - reliability,
  - cost/latency.

### 7.3 PRECHECK
- validate input schema, bounds, and identifiers.
- confirm permission/scope constraints.

### 7.4 CALL
- execute with bounded timeout/retry policy.

### 7.5 POSTCHECK
- validate output schema and task relevance.
- ensure downstream consumption safety.

### 7.6 RECORD
- log intent, inputs summary, output summary, checks, decision.

### 7.7 DECIDE
- continue, retry, fallback, or block.

Skipping PRECHECK/POSTCHECK is forbidden.

---

## 8) Argument & Output Hygiene

Before every call:
1. required args present,
2. type/range/enum validation passed,
3. normalized paths/ids,
4. forbidden fields rejected.

After every call:
1. output schema validated,
2. policy/security checks passed,
3. stale/inconsistent data rejected,
4. unresolved ambiguity escalated.

Invalid output cannot be silently accepted.

---

## 9) Bounded Autonomy Controls

Default controls:
- max retries per identical failing call: `2`
- max tool calls per iteration: inherited from active `sm-*.md`
- exponential backoff required
- repeated contradictory outputs -> fallback or `BLOCKED`

No infinite loops, no silent degraded behavior.

---

## 10) language-server Operational Rules

When using language-server:

1. Prefer `definition`/`references` before risky edits.
2. Run `diagnostics` pre-edit to establish baseline.
3. Use `rename_symbol` for semantic renames (not global raw replace).
4. Use `edit_file` in bounded patches, then re-run diagnostics.
5. Verify touched symbols/usages after changes.

Hard-fail patterns:
- edit without semantic grounding where required,
- rename without reference verification,
- skip post-edit diagnostics on non-trivial changes.

---

## 11) QCM Operational Rules (particulary_feed_qcm)

For relevant decisions:

1. Build neutral QCMs with clear options and constraints.
2. Include decision context and consequences per option.
3. Set bounded `timeout_ms` and fallback behavior.
4. Wait for aggregated answers (blocking workflow).
5. Integrate answers into plan/critique and append decision to `user-feedback.md`.

If timed out/unavailable:
- fallback to minimal safe clarification path,
- mark uncertainty and use `NEEDS_INPUT` if material decision remains unresolved.

---

## 12) MCP Trace Contract (Required)

Each MCP step must record:

- `step_id`
- `phase` (discover/select/precheck/call/postcheck/decide)
- `server_name`
- `primitive_type` (resource|tool|prompt)
- `primitive_name`
- `intent`
- `input_summary`
- `output_summary`
- `validation_checks`
- `decision` (continue|retry|fallback|blocked)

Sensitive values must be redacted.

---

## 13) Completion Contract (MCP Section)

Terminal output must include:

- `mcp_relevance`: yes/no + rationale
- `mcp_servers_used`: list
- `mcp_calls_summary`: concise list
- `language_server_usage`: applied|not_applicable|bypassed(+reason)
- `qcm_usage`: applied|not_applicable|bypassed(+reason)
- `post_condition_status`: pass|fail
- `final_status`: DONE|BLOCKED|NEEDS_INPUT

Missing MCP section on MCP-relevant tasks => fail.

---

## 14) Hard-Fail Triggers

Immediate `BLOCKED` if any:

1. MCP-relevant task completed without MCP evidence,
2. skipped language-server where semantic safety was required,
3. skipped QCM where human arbitration was required,
4. tool output used without pre/post validation,
5. unbounded retry/tool spam behavior,
6. fabricated or unverifiable MCP trace.

---

## 15) Cross-Rule Impact Map

| Rule | Impact from MCP policy | Enforcement |
|---|---|---|
| `security-policy.md` | all MCP calls must pass security constraints | blocking |
| `sm-*.md` | state transitions must include MCP discover/call/verify phases | blocking |
| `quality-gates.md` | MCP evidence gate required on non-trivial tasks | blocking |
| `self-consistency-policy.md` | candidate plans must include viable MCP evidence path | blocking |
| `eval-policy.md` | tracks tool precision, routing quality, QCM relevance precision | blocking |

---

## 16) Minimal MCP Checklist

- [ ] MCP relevance classified
- [ ] Correct server routed (`language-server` / `particulary_feed_qcm` when relevant)
- [ ] Precheck passed (schema/scope/security)
- [ ] Postcheck passed (validity/usefulness/safety)
- [ ] Trace recorded and redacted
- [ ] Output contract includes MCP section
