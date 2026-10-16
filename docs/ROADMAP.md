# Spendly — Roadmap

Six phases. **Each phase ends in a complete, demoable system**: it runs
with `make up`, its tests are green in CI, and it has a scripted demo.
Each spec goes through the usual pipeline:
`/create-spec` → implement → `/test-feature` → `/code-review-feature` →
`/ship-feature`, plus a `learnings/` explainer.

Spec names: `p<phase>-<nn>-<slug>`, e.g. `p0-03-docker-compose-infra`.
Tests for a spec go in the matching app, e.g.
`apps/api/tests/test_docker_compose_infra.py`.

Architecture: see `docs/ARCHITECTURE.md`.

---

## Phase 0 — Platform foundations

**Demo:** `make up` → sign in through Keycloak → create a company → invite
a teammate as `accountant` → they accept and see the company; a second
company's data is invisible to them. Grafana shows the request traces.

| Spec | Delivers | Done when |
|---|---|---|
| `p0-01-monorepo-skeleton` | `apps/`, `services/`, `packages/`, `infra/`, `docs/` layout next to the legacy app; `Makefile` with self-documenting `help`; `.gitattributes` (`* text=auto eol=lf`, `*.cmd`/`*.ps1` CRLF); `.editorconfig`; root README. **Windows make shim** in `scripts/windows/`: `make.cmd` (cmd/PowerShell) and `make` (Git Bash) forwarding to `wsl make "$@"`, plus `install-make-shim.ps1` that copies them to `%USERPROFILE%\bin` and adds it to the user PATH (idempotent, no admin) | Tree matches ARCHITECTURE §3; `make help` works from an Ubuntu terminal **and** from PowerShell / Git Bash in the repo folder |
| `p0-02-claude-tooling` | New CLAUDE.md conventions in force; hooks rewritten (guard protects `.env*`, Postgres volumes, `docker compose down -v`, `DROP DATABASE`, `alembic downgrade base`; formatter runs ruff / prettier); agents and commands updated for pytest + Vitest + Playwright. **Protected files are applied by the user** | `/test-feature` and `/code-review-feature` work on a p0 spec; guard still fails closed |
| `p0-03-docker-compose-infra` | Compose: Postgres 16 + pgvector, Redis, Redpanda + Console, MinIO, Keycloak (own DB), OTel Collector, Prometheus, Tempo, Loki, Grafana; healthchecks; named volumes; `.env.example` | `make up` → all healthy; `make down` keeps data; `make nuke` asks first |
| `p0-04-api-skeleton` | FastAPI app factory, pydantic-settings config, `/health` and `/ready` (checks DB, Redis, Kafka), JSON logging, error model (RFC 7807), async SQLAlchemy, Alembic baseline, OTel, testcontainers fixtures | `pytest` runs against real containers; `/ready` fails if Postgres is down |
| `p0-05-web-skeleton` | Vite + React + TS, router, TanStack Query, Tailwind + shadcn/ui, app shell (sidebar, company switcher placeholder), OpenAPI client generation, Vitest, ESLint, Prettier | `make web` serves the shell; generated client compiles |
| `p0-06-keycloak-auth` | Realm `spendly` exported as code; web login via OIDC + PKCE; API JWT validation (JWKS cache in Redis); `users` table upserted on first login; logout | Unauthenticated API calls → 401; a logged-in user sees their name |
| `p0-07-companies-and-memberships` | `companies`, `memberships`, `invitations`; create company (GSTIN/PAN optional, fiscal year starts April); roles; `require(permission)`; company switcher; invite + accept flow | Owner can invite; non-members get 404 for another company |
| `p0-08-row-level-security` | Non-owner DB role for the API; RLS policies; `SET LOCAL app.company_id` per request; tests proving cross-company reads return nothing even with a missing `WHERE` | RLS isolation test suite green |
| `p0-09-ci-pipeline` | GitHub Actions: ruff, mypy, eslint, tsc, pytest (service containers), Vitest, Playwright smoke, Docker image builds; PR template | PRs show all checks; main requires green |
| `p0-10-observability` | Trace propagation web → API → DB; provisioned Grafana dashboards (RED metrics, DB pool, Redis); log ↔ trace links | One login shows a single end-to-end trace |
| `p0-11-retire-legacy-flask` | Remove Flask app, Jinja templates, old tests, `railway.json`, root `requirements.txt`; archive `.claude/specs/01–09` under `docs/archive/v1-specs/` | Repo has only the new stack; `spendly-v1` tag still checks out the old app |

**Ordering note:** `p0-02` must land before anything removes the root
`venv/`. Today's guard hook runs from that venv and **blocks every tool
call** if it's missing.

---

## Phase 1 — Ledger core

**Demo:** post Priya's Bakery (`workflows/03`); the general ledger shows
every account's running balance; reversing an entry leaves a full trail.

| Spec | Delivers |
|---|---|
| `p1-01-chart-of-accounts` | `accounts` (code, name, type, `term` current/non_current, `schedule_iii_line`, `is_quick`, `is_control`, active); India starter template applied on company creation; CRUD + deactivate |
| `p1-02-fiscal-periods` | Fiscal years (April–March) and monthly periods; open/closed status |
| `p1-03-journal-entries` | `journal_entries` + `journal_lines`; draft → posted; DB triggers for balance, immutability, closed period; multi-line entry grid in React |
| `p1-04-reversals` | Reverse a posted entry (new entry, linked); UI "reverse" action |
| `p1-05-outbox-and-kafka` | Outbox table, relay service, event envelope + JSON Schemas, `ledger.entry.posted|reversed` |
| `p1-06-balance-projection` | Projector consumer → `account_balances`; idempotency; rebuild command |
| `p1-07-general-ledger` | Account ledger view with running balance and sign flip (`workflows/02`) |
| `p1-08-audit-log-consumer` | Audit consumer writing every event; audit viewer (read-only) |
| `p1-09-golden-bakery` | Golden test: bakery entries → exact balances |

## Phase 2 — Reports and analysis

**Demo:** NimbusSoft (`workflows/05`) posted from opening balances →
trial balance, P&L, Schedule III balance sheet, cash-flow and ratios
match the workflow documents exactly.

| Spec | Delivers |
|---|---|
| `p2-01-opening-balances` | Opening balance entry for a company migrating in |
| `p2-02-trial-balance` | As-of trial balance; must balance or the report refuses |
| `p2-03-profit-and-loss` | Date-range P&L with presets (this month, last 3/6 months, FY to date) |
| `p2-04-balance-sheet` | Schedule III balance sheet on any date; current-year profit and retained earnings roll-forward; A = L + E check |
| `p2-05-cash-flow` | Indirect method (`workflows/05` §8) |
| `p2-06-ratios-dashboard` | `workflows/06` ratios, two-date trend, n/a on divide-by-zero, Recharts |
| `p2-07-report-cache` | Redis cache + event-driven invalidation |
| `p2-08-exports` | PDF and Excel exports via worker, stored in MinIO |
| `p2-09-golden-nimbussoft` | Golden tests for studio and NimbusSoft |
| `p2-10-deploy-target` | Decide and implement the first hosted environment |

## Phase 3 — Spend management

**Demo:** Rahul's taxi claim (`workflows/04`) goes submit → approve → pay;
Ananya's advance (`workflows/05`) settles with the ₹6,000 top-up; each
step posts its journal automatically.

| Spec | Delivers |
|---|---|
| `p3-01-departments-cost-centres` | Dimensions on journal lines |
| `p3-02-expense-policy` | Categories → accounts, limits, receipt rules |
| `p3-03-receipts-upload` | MinIO upload, pre-signed URLs, virus/MIME checks |
| `p3-04-receipt-extraction` | Claude vision → draft fields; employee confirms |
| `p3-05-expense-claims` | Claim lifecycle; posting on approval and on payment |
| `p3-06-approval-workflows` | Amount-based multi-level approval; no self-approval |
| `p3-07-employee-advances` | Advance → settle → top-up / refund |
| `p3-08-corporate-cards` | Card statement import and matching |
| `p3-09-vendor-bills-ap` | Bills with GST input credit, TDS; payments |
| `p3-10-customer-invoices-ar` | Invoices with output GST; receipts with TDS receivable |
| `p3-11-notifications` | Email + websocket notifier |

## Phase 4 — Controls, close and audit

**Demo:** close June with the checklist; posting into June is refused;
a planted duplicate claim and a budget overrun are flagged automatically.

| Spec | Delivers |
|---|---|
| `p4-01-budgets` | Budgets by account × department × month; budget vs actual |
| `p4-02-adjusting-entries` | Depreciation schedules, prepaid amortisation, accruals |
| `p4-03-period-close` | Close checklist, Redis lock, period lock, reopen with reason |
| `p4-04-gst-tds-summaries` | GST set-off and TDS payable summaries per period |
| `p4-05-tamper-evident-audit` | Hash-chained audit log + verifier |
| `p4-06-segregation-of-duties` | SoD rules and auditor role |
| `p4-07-deviation-rules` | Detector: budget overrun, duplicates, split claims, weekend / round amounts |
| `p4-08-statistical-anomalies` | Z-scores per category/vendor, Benford's law |
| `p4-09-alerts-inbox` | Alerts UI with acknowledge / resolve |

## Phase 5 — AI advisor

**Demo:** "Why did cash fall in June?" → an answer built only from tool
results, citing figures, with recommendations an accountant accepts or
rejects.

| Spec | Delivers |
|---|---|
| `p5-01-advisor-tools` | Read-only tool layer over report services |
| `p5-02-policy-rag` | Policy documents → chunks → pgvector search |
| `p5-03-deviation-explainer` | Explains each Phase 4 alert in plain language |
| `p5-04-month-end-commentary` | Generated management commentary for a closed period |
| `p5-05-recommendations` | Recommendation records, accept/reject, follow-up tracking |
| `p5-06-ask-your-books` | Chat over the company's books (read-only) |
| `p5-07-ai-audit-and-limits` | Prompt/response/tool-call log, cost tracking, per-company budgets |
| `p5-08-advisor-evals` | Eval suite: numbers must match tool outputs; refusal on missing data |
