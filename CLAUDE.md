# CLAUDE.md

## Project overview

Spendly is being rebuilt from a personal Flask + SQLite expense tracker
into a **multi-company corporate accounting platform** with an AI
advisor: double-entry ledger, reports and ratios, spend management,
controls and audit, and AI recommendations.

- Target architecture: `docs/ARCHITECTURE.md` (read it before any
  design work)
- Phases and specs: `docs/ROADMAP.md`
- The old Flask app is frozen at git tag **`spendly-v1`**
- Domain explainers: `workflows/` and `learnings/` (local only, never
  committed)

Guiding rule: **code calculates, AI explains, a human decides.**

---

## Current state (transition)

Phase 0 is in progress. Until spec `p0-11-retire-legacy-flask` lands:

- The **legacy Flask app** (`app.py`, `database/`, `templates/`,
  `static/`, `tests/`, `requirements.txt`, root `venv/`) still exists.
  **Don't add features to it**; touch it only to keep it running.
- The `.claude` hooks run from the root `venv/`. **Never remove or
  break `venv/` before `p0-02-claude-tooling` lands**: the guard hook
  fails closed and blocks every tool call.
- `.claude/agents/*` and the `/test-feature`, `/code-review-feature`,
  `/create-spec` and seed commands still describe Flask/SQLite. They
  are updated in `p0-02`. Until then, give them the new stack's
  context explicitly in the prompt.

---

## Stack

| Layer | Tech |
|---|---|
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async), Alembic |
| Web | React 18, TypeScript, Vite, React Router, TanStack Query, Tailwind + shadcn/ui, Recharts, react-hook-form + zod |
| DB | PostgreSQL 16 + pgvector, row-level security per company |
| Cache / jobs | Redis 7, arq |
| Events | Kafka (Redpanda locally) via a transactional outbox |
| Identity | Keycloak (OIDC); per-company roles live in Postgres |
| Files | MinIO (S3 API) |
| Observability | OpenTelemetry → Prometheus, Tempo, Loki, Grafana |
| AI | Claude API (tool use, vision), pgvector for policy search |
| Tests | pytest + testcontainers, Vitest + Testing Library, Playwright |
| Dev env | Docker Compose via `Makefile` |

Adding a dependency is fine when a spec needs it. Add it to the right
manifest (`apps/api/pyproject.toml`, `apps/web/package.json`) in the
same change and mention it in the PR.

---

## Where things belong

```
apps/api/spendly/modules/<module>/
  router.py      HTTP only: parse, call service, shape response
  service.py     business rules, transactions, permission checks
  repository.py  all SQL for the module, nothing else
  models.py      SQLAlchemy tables
  schemas.py     Pydantic request/response models
  events.py      event payloads the module emits
apps/api/migrations/      Alembic only; never hand-edit the DB
apps/web/src/features/<feature>/   pages, hooks, components for one feature
apps/web/src/api/         generated OpenAPI client (never hand-edit)
services/<name>/          Kafka consumers and workers
packages/events/          JSON Schemas for every event (source of truth)
infra/                    compose, keycloak realm, grafana, k8s
```

---

## Non-negotiable domain rules

- **Money is exact:** `NUMERIC(18,2)` in Postgres, `Decimal` in Python,
  strings in JSON, never JS `number` maths for totals. **No floats,
  ever.**
- **Double entry:** every journal entry has ≥ 2 lines and Σ debit =
  Σ credit, enforced by a DB trigger as well as in the service.
- **Posted entries are immutable.** Corrections are reversal entries.
  Never write UPDATE/DELETE paths for posted ledger rows.
- **Closed periods are locked** (DB trigger).
- **Every company-owned row has `company_id`.** Every repository query
  filters by it, *and* RLS is on. Never bypass RLS in request code.
- **Ledger writes go through `apps/api` only.** Consumers never write
  journal entries; they build projections, alerts and audit rows.
- **Publish events via the outbox**, in the same transaction as the
  write. Never call Kafka directly from a request handler.
- **Consumers are idempotent** (dedupe on `event_id`).
- **AI is read-only.** Advisor tools only read; AI output is a
  recommendation a human accepts or rejects. Log every AI call.
- **India-first:** fiscal year April–March, Schedule III layout, GST and
  TDS as their own accounts (never part of income or expense).

---

## Code style

- Python: ruff (lint + format), mypy strict on `apps/api`, snake_case,
  type hints everywhere, async I/O
- TypeScript: strict mode, ESLint + Prettier, function components and
  hooks, server state via TanStack Query only
- SQL: SQLAlchemy expressions or bound parameters only. Never build SQL
  with f-strings or concatenation
- HTTP errors: raise typed exceptions mapped to RFC 7807 problem
  responses; no bare string error bodies
- Config: only from environment via `config.py`; no secrets in code;
  every variable documented in `.env.example`

---

## Commands

```bash
make up          # start the full stack (Docker Compose)
make down        # stop, keep data
make migrate     # alembic upgrade head
make api         # run API with reload
make web         # run Vite dev server
make test        # all tests
make test-api    # pytest (apps/api) — uses testcontainers
make test-web    # vitest
make e2e         # playwright
make lint        # ruff, mypy, eslint, tsc
```

These targets are created in `p0-01`–`p0-05`. Until then, the legacy
app runs with `python app.py` (port 5001) and `pytest`.

---

## Subagent policy

- Always use a built-in Explore subagent for codebase exploration
  before implementing a new feature
- When asked to plan, delegate codebase research to a subagent before
  presenting the plan
- Always use a built-in Plan subagent in plan mode

### Post-implementation pipeline

After implementing a spec, run these in order. `<spec-name>` is the
spec filename without `.md`, e.g. `p0-04-api-skeleton`.

1. **`/test-feature <spec-name>`**
   - `spendly-test-writer` writes tests **from the spec in
     `.claude/specs/<spec-name>.md`, never from the implementation**.
     Tests go in the app the spec targets (`apps/api/tests/`,
     `apps/web/src/**/*.test.tsx`, `e2e/`).
   - `spendly-test-runner` runs those tests only and diagnoses failures.
   - The command never fixes code. If tests fail, fix the
     implementation (or flag the spec to the user) and re-run.
2. **`/code-review-feature <spec-name>`**, once tests pass
   - `spendly-security-reviewer` and `spendly-quality-reviewer` run in
     parallel on the branch's changes.
   - The command merges both into one report and asks before changing
     anything. Never edit files until the user approves.
3. **Write the `learnings/` explainer** for the spec (never committed).

### Subagent rules

- Agent definitions live in `.claude/agents/`; commands in
  `.claude/commands/`
- Prefer the commands over invoking agents one by one. Direct order:
  test-writer → test-runner → both reviewers in parallel
- Never invoke `spendly-test-runner` before the test file exists
- A failing spec-based test means the implementation (or the spec) is
  wrong. Never weaken assertions to make it pass
- Reviewer findings are educational; the user decides what to fix
- Relay each subagent's report to the user; they can't see subagent
  output directly

---

## Warnings and things to avoid

- **Never use floats for money**, anywhere (Python, SQL, TypeScript)
- **Never mutate posted ledger rows**, not even in migrations or seeds
- **Never disable RLS** or connect the API as the table owner
- **Tests never touch the dev database.** Integration tests use
  testcontainers; unit tests use no DB
- **Never commit secrets.** `.env` is local only; `.env.example` is the
  documented template. Treat `.env` as protected
- **Never run `docker compose down -v`, `DROP DATABASE` or
  `alembic downgrade base`** without the user asking explicitly. They
  destroy local data
- **Don't hand-edit generated code** (`apps/web/src/api/`, Alembic
  revisions after they're merged)
- **Don't implement a later spec's work early.** Follow
  `docs/ROADMAP.md`; when in doubt, ask
- `learnings/` and `workflows/` are in `.git/info/exclude`. Never commit
  them and never add them to `.gitignore`
