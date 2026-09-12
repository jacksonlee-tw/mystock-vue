# Project Guidelines

Project overview, architecture, hard rules, and build/test commands are documented in [CLAUDE.md](../CLAUDE.md) at the repo root — read it before making changes; it is the authoritative context for this repo.

## Skills

This repo has engineering workflow skills under `.agents/skills/`. Before starting non-trivial work, check whether one applies and follow it — they encode processes that prevent common mistakes (skipped verification, scope creep, wrong assumptions).

Start with [using-agent-skills](../.agents/skills/using-agent-skills/SKILL.md) — the meta-skill that maps a task to the right skill(s) and defines core operating behaviors (surface assumptions, verify don't assume, scope discipline) that apply regardless of which skill is active.

Quick reference — load a skill's `SKILL.md` when its trigger applies:

| Skill | Use when |
|---|---|
| `interview-me` | Ask is underspecified; need to extract real intent before planning |
| `idea-refine` | Idea is vague; need to stress-test or expand options before committing |
| `spec-driven-development` | Starting a new feature/change with no spec yet |
| `constraint-driven-development` | No written quality bar (coverage, perf, a11y) for the project |
| `planning-and-task-breakdown` | Spec exists; need to break it into ordered tasks |
| `incremental-implementation` | Implementing any multi-file change; deliver in thin, verifiable slices |
| `context-engineering` | Session context needs setup/pruning, or output quality is degrading |
| `source-driven-development` | Need to verify an approach against official framework/library docs first |
| `doubt-driven-development` | High-stakes, unfamiliar, or irreversible change; needs adversarial review |
| `frontend-ui-engineering` | Building/modifying Vue components, pages, layouts, accessibility |
| `api-and-interface-design` | Designing FastAPI endpoints or module/type contracts |
| `test-driven-development` | Implementing logic, fixing a bug, or changing behavior |
| `browser-testing-with-devtools` | Verifying browser/UI behavior with real runtime data |
| `debugging-and-error-recovery` | Something broke; need systematic root-cause debugging |
| `code-review-and-quality` | Reviewing a change before it merges |
| `code-simplification` | Working code has grown unnecessarily complex |
| `security-and-hardening` | Handling user input, auth, secrets, or third-party integrations |
| `performance-optimization` | Suspected perf regression or need to fix N+1/slow queries |
| `git-workflow-and-versioning` | Committing, branching, opening a PR, cutting a release |
| `ci-cd-and-automation` | Setting up or changing build/deploy pipelines |
| `deprecation-and-migration` | Removing/replacing old systems or migrating a schema |
| `documentation-and-adrs` | Recording an architecture decision or documenting a public API change |
| `observability-and-instrumentation` | Adding logs/metrics/traces/alerts for a production feature |
| `shipping-and-launch` | Preparing a production deploy or rollout |

Only one skill file loads at a time when relevant — don't preemptively read all of them.
