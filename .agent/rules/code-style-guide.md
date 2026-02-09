---
trigger: always_on
description: activation_mode: semi_enforced, trigger:   - on_code_create   - on_code_edit   - on_refactor   - on_test_write
---

---
trigger:
  - on_code_create
  - on_code_edit
  - on_refactor
  - on_test_write
activation_mode: semi_enforced
lifecycle_hooks:
  - planning
  - act
  - verify
owner: Agent Runtime
version: 2.0.0
last_updated: 2026-02-08
---

# code-style-guide.md

## 1) Purpose

Define a consistent, high-signal coding style across languages and repositories to maximize:

1. readability,
2. maintainability,
3. correctness,
4. reviewability,
5. safe refactoring velocity.

This guide standardizes **how code is written**, while execution safety and completion criteria remain governed by higher-priority policies.

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
8. `tech-stack-guide.md`
9. `code-style-guide.md` (this file)
10. `work-style-guide.md`
11. `context-policy.md`

If conflict exists with higher-priority files, this guide yields.

---

## 3) Activation Contract

### 3.1 Mode
`semi_enforced`

### 3.2 Escalation to blocking (for the current change)
Escalate style enforcement to **blocking** when:

- changes target critical modules (auth, security, billing, deployment paths),
- refactor touches shared/public APIs,
- high-risk tasks where clarity directly impacts correctness,
- code ownership conventions require strict compliance.

---

## 4) Core Style Principles

1. **Clarity over cleverness**
   - Prefer straightforward implementations over dense “smart” constructs.
2. **Consistency over personal preference**
   - Match existing project conventions unless explicitly migrating.
3. **Small, explainable units**
   - Keep functions/modules focused and composable.
4. **Semantic naming**
   - Names should expose intent, not implementation accidents.
5. **Stable interfaces**
   - Minimize unnecessary API churn.
6. **Diff friendliness**
   - Write code that is easy to review and bisect.

---

## 5) Naming Conventions (General)

Apply project convention first; if absent, use:

- Types/classes/components: `PascalCase`
- Functions/methods: `snake_case` or `camelCase` (project standard only, never mixed in same scope)
- Variables/fields: `snake_case` (or repo standard)
- Constants: `UPPER_SNAKE_CASE`
- Files:
  - code files: project convention
  - policy/docs artifacts: `"{n}-{name}.md"` (mandatory)

Naming rules:

1. avoid ambiguous abbreviations,
2. avoid context-free names (`data`, `tmp`, `obj`),
3. prefer domain terms from product/spec,
4. boolean names should read as predicates (`is_enabled`, `has_access`).

---

## 6) Structure and Modularity

1. One module/file should have one clear responsibility.
2. Limit function size and branching complexity.
3. Split “orchestrator” logic from pure business logic.
4. Isolate side effects (IO/network/fs) from pure transforms when possible.
5. Prefer explicit boundaries (interfaces/types/contracts) for replaceable components.

---

## 7) Error Handling and Failure Semantics

1. Never swallow errors silently.
2. Preserve actionable context in errors (what failed, where, why).
3. Use typed/domain errors when available.
4. Distinguish:
   - recoverable errors (retry/fallback path),
   - terminal errors (bubble up with clear reason).
5. Avoid broad catch blocks without narrowing/annotation.

---

## 8) Comments and Documentation in Code

Use comments for **why**, not obvious **what**.

Required inline documentation for:

- non-trivial invariants,
- subtle edge-case handling,
- security-sensitive logic,
- algorithmic trade-off decisions.

Avoid stale comments:
- update/remove comments when behavior changes.
- comments that no longer match code are treated as defects.

---

## 9) Testing Style Requirements

For changed behavior:

1. add or update targeted tests,
2. include at least one edge-case path when risk is medium/high,
3. keep tests deterministic and isolated,
4. prefer explicit assertions over snapshot-only dependence,
5. avoid brittle tests tied to irrelevant formatting/order unless required.

Test names should describe behavior, not implementation detail.

---

## 10) Formatting and Linting Policy

1. Use project-standard formatter and linter.
2. Avoid manual style bikeshedding when formatter can decide.
3. Do not introduce formatting drift across untouched files.
4. Keep imports/includes ordered by project convention.
5. Resolve lints intentionally; do not blanket-disable rules without reason.

Any lint/format suppression must include a concise rationale.

---

## 11) Type and Contract Discipline

1. Prefer explicit types at public boundaries.
2. Validate inputs at boundaries (API, tool input, file parse).
3. Encode invariants in types/contracts where possible.
4. Avoid “stringly-typed” control flows for domain-critical logic.
5. Minimize nullable/optional ambiguity with clear handling paths.

---

## 12) Refactoring Safety Rules

When refactoring:

1. establish baseline behavior (tests/diagnostics),
2. make incremental changes,
3. use semantic tooling when available:
   - `language-server` (`definition`, `references`, `rename_symbol`, `diagnostics`, `edit_file`),
4. verify after each meaningful batch,
5. avoid mixed refactor + feature changes unless justified.

No large blind text replacement for symbol-safe operations when language-server is available.

---

## 13) Performance and Complexity Hygiene

1. Do not optimize blindly; optimize based on signal.
2. Remove accidental quadratic patterns in hot paths.
3. Prefer readability until profiling demonstrates bottlenecks.
4. Document intentional complexity/performance trade-offs.
5. Keep allocations/IO patterns explicit in sensitive paths.

---

## 14) Security-Aware Coding Style

1. Treat external inputs as untrusted.
2. Keep sanitization/validation close to boundaries.
3. Avoid leaking sensitive data in logs/errors.
4. Do not hardcode credentials/secrets.
5. Make risky operations explicit and auditable.

Security policy remains authoritative; this section reinforces coding-level hygiene.

---

## 15) Language-Specific Overlays

Each repo may define overlays (e.g., `code-style-python.md`, `code-style-ts.md`, `code-style-rust.md`) for language details.
Overlays must not contradict higher-priority rules.

If no overlay exists, default to this guide + project conventions.

---

## 16) Pull Request / Change Readability Contract

Every non-trivial code change should be reviewable with:

- clear intent summary,
- bounded diff scope,
- rationale for design choices,
- verification evidence,
- risk notes (if any).

Large multi-purpose diffs are discouraged.

---

## 17) Output Contract for Style Compliance

For significant code changes, include:

- `style_compliance`: pass|partial|fail
- `exceptions`: list (with rationale)
- `lint_format_status`
- `naming_consistency_status`
- `refactor_safety_notes` (if refactor)
- `follow_up_actions` (if partial/fail)

---

## 18) Anti-Patterns

1. Clever but opaque one-liners in critical logic.
2. Mixing naming conventions in same module.
3. Massive files with unrelated responsibilities.
4. Silent error handling.
5. Blanket linter suppression.
6. Refactor-by-search-replace where semantic tooling is available.
7. Tests that pass but do not validate intended behavior.

---

## 19) Minimal Checklist

- [ ] Naming is consistent and meaningful
- [ ] Modules/functions have clear responsibilities
- [ ] Error handling is explicit and actionable
- [ ] Comments explain non-obvious decisions
- [ ] Tests cover changed behavior and key edges
- [ ] Formatter/linter compliance confirmed
- [ ] Public boundaries have clear type/contracts
- [ ] Semantic-safe refactor workflow used when relevant