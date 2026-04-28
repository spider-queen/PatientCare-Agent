# Codex Skill Selection Guide

This document is a practical index for using the `agent-skills` repository with Codex when working in other project directories.

It combines the lifecycle-based grouping from the repository README with a more practical "which skill should I load now?" view.

## How to Use This Guide

When you switch to another codebase, do not load every skill at once. Keep a small default set loaded, then add 1 to 2 task-specific skills as needed.

Recommended baseline:

- `spec-driven-development`
- `test-driven-development`
- `code-review-and-quality`

Helpful optional baseline:

- `using-agent-skills`
- `incremental-implementation`
- `git-workflow-and-versioning`

Example prompt for Codex:

```text
Please work in `D:\Projects\my-app`.
Before making changes, read these skills:
- `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md`

For this task, also load:
- `E:\LLM\Projects\agent-skills\agent-skills\skills\debugging-and-error-recovery\SKILL.md`
```

## Basic Skills

These are the best "always reach for these first" skills for day-to-day coding work.

| Skill | Why it is basic | Best for | Path |
|---|---|---|---|
| `spec-driven-development` | Defines scope, constraints, and acceptance criteria before code | New features, significant changes, ambiguous requests | `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md` |
| `test-driven-development` | Forces proof through tests instead of intuition | Bug fixes, behavior changes, core logic | `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md` |
| `code-review-and-quality` | Adds a structured quality gate before considering work done | Pre-merge review, self-review, regression checks | `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md` |
| `incremental-implementation` | Encourages small, safe, verifiable slices | Multi-file changes, iterative delivery | `E:\LLM\Projects\agent-skills\agent-skills\skills\incremental-implementation\SKILL.md` |
| `using-agent-skills` | Helps map a task to the right skill set | Session startup, uncertain task selection | `E:\LLM\Projects\agent-skills\agent-skills\skills\using-agent-skills\SKILL.md` |
| `git-workflow-and-versioning` | Keeps changes atomic and easier to review or roll back | Any real code change | `E:\LLM\Projects\agent-skills\agent-skills\skills\git-workflow-and-versioning\SKILL.md` |

Suggested default sets:

- Minimal: `spec-driven-development` + `test-driven-development` + `code-review-and-quality`
- Balanced: Minimal + `incremental-implementation`
- Engineering-heavy: Balanced + `git-workflow-and-versioning`

## Skill Categories

### 1. Define: Clarify What to Build

Use these when the request is still vague, incomplete, or too large to code safely.

| Skill | Use when | Path |
|---|---|---|
| `idea-refine` | You have a rough concept and need to turn it into a clearer proposal | `E:\LLM\Projects\agent-skills\agent-skills\skills\idea-refine\SKILL.md` |
| `spec-driven-development` | You need a concrete spec, scope, constraints, and acceptance criteria before coding | `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md` |

### 2. Plan: Break Work into Executable Tasks

Use this when the feature is understood but still needs an implementation plan.

| Skill | Use when | Path |
|---|---|---|
| `planning-and-task-breakdown` | You want small, verifiable tasks with dependency order and acceptance criteria | `E:\LLM\Projects\agent-skills\agent-skills\skills\planning-and-task-breakdown\SKILL.md` |

### 3. Build: Implement the Change

These are the main execution skills for writing code.

| Skill | Use when | Path |
|---|---|---|
| `incremental-implementation` | The change spans multiple files or should be delivered in safe slices | `E:\LLM\Projects\agent-skills\agent-skills\skills\incremental-implementation\SKILL.md` |
| `test-driven-development` | You are changing logic, fixing bugs, or adding behavior that needs proof | `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md` |
| `context-engineering` | You need better context packaging, rules loading, or agent guidance | `E:\LLM\Projects\agent-skills\agent-skills\skills\context-engineering\SKILL.md` |
| `source-driven-development` | Framework or library decisions should be grounded in official docs | `E:\LLM\Projects\agent-skills\agent-skills\skills\source-driven-development\SKILL.md` |
| `frontend-ui-engineering` | The task involves components, design systems, state, responsiveness, or accessibility | `E:\LLM\Projects\agent-skills\agent-skills\skills\frontend-ui-engineering\SKILL.md` |
| `api-and-interface-design` | You are defining APIs, contracts, module boundaries, or public interfaces | `E:\LLM\Projects\agent-skills\agent-skills\skills\api-and-interface-design\SKILL.md` |

### 4. Verify: Prove It Works

Use these when behavior needs to be validated in the browser or when something is failing.

| Skill | Use when | Path |
|---|---|---|
| `browser-testing-with-devtools` | You need runtime browser inspection, DOM checks, console errors, or network tracing | `E:\LLM\Projects\agent-skills\agent-skills\skills\browser-testing-with-devtools\SKILL.md` |
| `debugging-and-error-recovery` | Tests fail, builds break, or production behavior is unexpected | `E:\LLM\Projects\agent-skills\agent-skills\skills\debugging-and-error-recovery\SKILL.md` |

### 5. Review: Improve Quality Before Merge

Use these to reduce hidden risk after the code works.

| Skill | Use when | Path |
|---|---|---|
| `code-review-and-quality` | You want a structured review before merging | `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md` |
| `code-simplification` | The code works, but it is harder to understand than it should be | `E:\LLM\Projects\agent-skills\agent-skills\skills\code-simplification\SKILL.md` |
| `security-and-hardening` | The task touches input handling, auth, data storage, or external systems | `E:\LLM\Projects\agent-skills\agent-skills\skills\security-and-hardening\SKILL.md` |
| `performance-optimization` | There are performance goals or suspected regressions | `E:\LLM\Projects\agent-skills\agent-skills\skills\performance-optimization\SKILL.md` |

### 6. Ship: Prepare for Delivery

Use these when changes affect versioning, CI/CD, migration, rollout, or release confidence.

| Skill | Use when | Path |
|---|---|---|
| `git-workflow-and-versioning` | You want smaller commits, clean history, and safer change management | `E:\LLM\Projects\agent-skills\agent-skills\skills\git-workflow-and-versioning\SKILL.md` |
| `ci-cd-and-automation` | You are setting up or modifying pipelines, checks, or automation | `E:\LLM\Projects\agent-skills\agent-skills\skills\ci-cd-and-automation\SKILL.md` |
| `deprecation-and-migration` | You are retiring old code, migrating users, or changing compatibility paths | `E:\LLM\Projects\agent-skills\agent-skills\skills\deprecation-and-migration\SKILL.md` |
| `documentation-and-adrs` | You need to capture architecture decisions, API notes, or implementation rationale | `E:\LLM\Projects\agent-skills\agent-skills\skills\documentation-and-adrs\SKILL.md` |
| `shipping-and-launch` | You need launch checklists, rollout planning, rollback readiness, and monitoring | `E:\LLM\Projects\agent-skills\agent-skills\skills\shipping-and-launch\SKILL.md` |

## Practical Selection by Task Type

Use this section when you do not want to think in lifecycle phases.

| Task type | Recommended skills |
|---|---|
| New feature | `spec-driven-development` + `planning-and-task-breakdown` + `incremental-implementation` + `test-driven-development` |
| Bug fix | `debugging-and-error-recovery` + `test-driven-development` + `code-review-and-quality` |
| Refactor | `code-simplification` + `incremental-implementation` + `code-review-and-quality` |
| Frontend UI work | `frontend-ui-engineering` + `test-driven-development` + `browser-testing-with-devtools` |
| API or SDK design | `api-and-interface-design` + `spec-driven-development` + `code-review-and-quality` |
| Unknown library or framework work | `source-driven-development` + `test-driven-development` |
| Security-sensitive change | `security-and-hardening` + `code-review-and-quality` + `test-driven-development` |
| Performance tuning | `performance-optimization` + `browser-testing-with-devtools` or targeted tests |
| CI/CD changes | `ci-cd-and-automation` + `git-workflow-and-versioning` |
| Deprecation or migration | `deprecation-and-migration` + `documentation-and-adrs` + `shipping-and-launch` |

## Suggested Loading Strategy for Codex

### Option A: Minimal Default

Load these at the start of most sessions:

- `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md`

### Option B: Default for Real Project Work

Use this when you expect multi-file changes:

- `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\incremental-implementation\SKILL.md`

### Option C: Default for Ongoing Team Repos

Use this for longer-running engineering work:

- `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\incremental-implementation\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\git-workflow-and-versioning\SKILL.md`

## Optional Supporting Files

These are not skills, but they are useful companions.

### Specialist agents

| File | Purpose | Path |
|---|---|---|
| `code-reviewer` | Staff-level review perspective | `E:\LLM\Projects\agent-skills\agent-skills\agents\code-reviewer.md` |
| `test-engineer` | Test strategy and coverage review | `E:\LLM\Projects\agent-skills\agent-skills\agents\test-engineer.md` |
| `security-auditor` | Threat modeling and vulnerability review | `E:\LLM\Projects\agent-skills\agent-skills\agents\security-auditor.md` |

### Reference checklists

| File | Use with | Path |
|---|---|---|
| `testing-patterns.md` | `test-driven-development` | `E:\LLM\Projects\agent-skills\agent-skills\references\testing-patterns.md` |
| `security-checklist.md` | `security-and-hardening` | `E:\LLM\Projects\agent-skills\agent-skills\references\security-checklist.md` |
| `performance-checklist.md` | `performance-optimization` | `E:\LLM\Projects\agent-skills\agent-skills\references\performance-checklist.md` |
| `accessibility-checklist.md` | `frontend-ui-engineering` | `E:\LLM\Projects\agent-skills\agent-skills\references\accessibility-checklist.md` |

## Recommended Workflow When Switching to Another Project

1. Tell Codex the target project directory.
2. Ask Codex to read the baseline skills first.
3. Add 1 to 2 scenario-specific skills for the current task.
4. If the task is large, ask Codex to produce a spec and task breakdown before coding.
5. Before finishing, ask Codex to run a review using `code-review-and-quality`.

Example:

```text
Please work in `D:\Projects\service-a`.
Before coding, read:
- `E:\LLM\Projects\agent-skills\agent-skills\skills\spec-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\test-driven-development\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\code-review-and-quality\SKILL.md`

This is an API change, so also read:
- `E:\LLM\Projects\agent-skills\agent-skills\skills\api-and-interface-design\SKILL.md`
- `E:\LLM\Projects\agent-skills\agent-skills\skills\incremental-implementation\SKILL.md`
```

## Final Notes

- The README's lifecycle grouping is the best top-level mental model.
- For everyday use with Codex, the most effective approach is a small default set plus targeted additions.
- If you are unsure which skill to load, start with `using-agent-skills`, then add the baseline set, then pick the task-specific skill.
