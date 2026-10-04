# CLAUDE.md

## Project overview

Spendly is a lightweight personal expense tracker built with Flask and SQLite.

---

## Architecture
```
spendly/
├── app.py              # All routes — single file, no blueprints;
│                       #   get_current_user() is the shared logged-in guard
├── database/
│   └── db.py           # SQLite helpers: get_db(), init_db(), seed_db(),
│                       #   create_user(), get_user_by_email(), get_user_by_id(),
│                       #   get_expense_summary(), get_category_totals(), get_recent_expenses(),
│                       #   insert_expense(), get_expense_for_user(), delete_expense_for_user(),
│                       #   update_expense_for_user()
├── templates/
│   ├── base.html       # Shared layout — all templates must extend this
│   └── *.html          # One template per page
├── static/
│   ├── css/
│   │   ├── style.css       # Global styles
│   │   ├── profile.css     # Profile-page-only styles
│   │   ├── add_expense.css # Add-expense-page-only styles
│   │   └── delete_expense.css # Delete-confirmation-page-only styles
│   └── js/
│       └── main.js         # Vanilla JS only
├── tests/
│   ├── conftest.py     # Fixtures — temp SQLite DB per test, never the real one
│   └── test_*.py       # One test file per feature
└── requirements.txt
```

**Where things belong:**
- New routes → `app.py` only, no blueprints
- DB logic → `database/db.py` only, never inline in routes
- New pages → new `.html` file extending `base.html`
- Page-specific styles → new `.css` file, not inline `<style>` tags

---

## Code style

- Python: PEP 8, snake_case for all variables and functions
- Templates: Jinja2 with `url_for()` for every internal link — never hardcode URLs
- Route functions: one responsibility only — fetch data, render template, done
- DB queries: always use parameterized queries (`?` placeholders) — never f-strings in SQL
- Error handling: use `abort()` for HTTP errors, not bare `return "error string"`

---

## Tech constraints

- **Flask only** — no FastAPI, no Django, no other web frameworks
- **SQLite only** — no PostgreSQL, no SQLAlchemy ORM, no external DB
- **Vanilla JS only** — no React, no jQuery, no npm packages
- **No new pip packages** — work within `requirements.txt` as-is unless explicitly told otherwise
- Python 3.10+ assumed — f-strings and `match` statements are fine

---

## Subagent Policy
- Always use a builtin explore subagent for codebase exploration 
  before implementing any new feature
- When asked to plan, delegate codebase research 
  to a subagent before presenting the plan
- always use a builtin plan subagent in plan mode

### Post-implementation pipeline

After implementing any feature, run these two commands 
in order. `<spec-name>` is the spec's filename without 
`.md`, e.g. `05-profile-backend`.

1. **`/test-feature <spec-name>`** — testing
   - `spendly-test-writer` writes tests from 
     `.claude/specs/<spec-name>.md`, never from the 
     implementation, into `tests/test_<feature>.py` 
     (step number dropped, underscores: 
     `05-profile-backend` → `tests/test_profile_backend.py`). 
     It only writes tests; it does not run them.
   - Then `spendly-test-runner` runs that file only and 
     diagnoses failures. This is the subagent that 
     verifies test results after any implementation.
   - The command never fixes code. If tests fail, fix 
     the implementation (or flag the spec to the user) 
     and re-run `/test-feature` until it's green.
2. **`/code-review-feature <spec-name>`** — review, once 
   tests pass
   - `spendly-security-reviewer` and 
     `spendly-quality-reviewer` run in parallel on the 
     branch's changes (committed, uncommitted and 
     untracked).
   - The command merges both into one report with an 
     action plan and verdict, then asks before changing 
     anything. Never edit files until the user approves.

### Subagent rules
- Agent definitions live in `.claude/agents/`; the 
  commands that orchestrate them live in 
  `.claude/commands/`
- Prefer the commands over invoking the agents one by 
  one. If invoking directly, keep the same order: 
  test-writer → test-runner → both reviewers in 
  parallel (one message, two Agent calls)
- Never invoke `spendly-test-runner` before the test 
  file exists
- A failing spec-based test means the implementation 
  (or the spec) is wrong — never weaken a test's 
  assertions to make it pass
- Reviewer findings are educational: the verdict is a 
  recommendation, and the user decides what to fix
- Relay each subagent's report to the user; they can't 
  see subagent output directly

---

## Commands
```bash
# Setup
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run dev server (port 5001)
python app.py

# Run all tests
pytest

# Run a specific test file
pytest tests/test_foo.py

# Run a specific test by name
pytest -k "test_name"

# Run tests with output visible
pytest -s
```

---

## Implemented vs stub routes

| Route | Status |
|---|---|
| `GET /` | Implemented — renders `landing.html` |
| `GET, POST /register` | Implemented — renders `register.html`; POST creates user, redirects to `/login` |
| `GET, POST /login` | Implemented — renders `login.html`; POST checks credentials, sets `session["user_id"]`, redirects to `/` |
| `GET /logout` | Implemented — clears session, redirects to `/` |
| `GET /profile` | Implemented — renders `profile.html` with the logged-in user's real stats, category breakdown and 10 most recent expenses; optional `?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD` filter (inclusive, applied only when both are valid) with presets This Month / Last 3 Months / Last 6 Months / All Time; a reversed range flashes an error and shows all time; redirects guests (and stale sessions) to `/login` |
| `GET, POST /expenses/add` | Implemented — renders `add_expense.html`; POST validates amount/category/date/description, inserts via `insert_expense()`, flashes "Expense added." and redirects to `/profile`; invalid input re-renders the form (200) with values kept; redirects guests (and stale sessions) to `/login` |
| `GET, POST /expenses/<id>/edit` | Implemented — GET renders `edit_expense.html` pre-filled with the stored values; POST re-validates via `parse_expense_form()`, updates via `update_expense_for_user()`, flashes "Expense updated." and redirects to `/profile`; invalid input re-renders the form (200) with values kept and the expense unchanged; missing or another user's expense → 404 (checked before validation); redirects guests (and stale sessions) to `/login` |
| `GET, POST /expenses/<id>/delete` | Implemented — GET renders `delete_expense.html` confirmation (never deletes); POST deletes via `delete_expense_for_user()`, flashes "Expense deleted." and redirects to `/profile`; missing or another user's expense → 404; redirects guests (and stale sessions) to `/login` |

**Do not implement a stub route unless the active task explicitly targets that step.**

---

## Warnings and things to avoid

- **Never use raw string returns for stub routes** once a step is implemented — always render a template
- **Never hardcode URLs** in templates — always use `url_for()`
- **Never put DB logic in route functions** — it belongs in `database/db.py`
- **Never install new packages** mid-feature without flagging it — keep `requirements.txt` in sync
- **Never use JS frameworks** — the frontend is intentionally vanilla
- **Only use DB helpers that already exist in `database/db.py`** — do not assume helpers for later steps (e.g. add/edit/delete expense) exist until the step that implements them
- **Tests must never touch `expense_tracker.db`** — use the fixtures in `tests/conftest.py`, which point `DB_PATH` at a temp file
- **FK enforcement is manual** — SQLite foreign keys are off by default; `get_db()` must run `PRAGMA foreign_keys = ON` on every connection
- The app runs on **port 5001**, not the Flask default 5000 — don't change this