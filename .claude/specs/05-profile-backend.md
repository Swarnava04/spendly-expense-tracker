# Spec: Profile Backend

## Overview
Step 04 delivered the profile page design, but `GET /profile` still renders hardcoded "Demo User" placeholder data for every logged-in user. This step wires the page to the real database: the route loads the logged-in user from `session["user_id"]`, and their summary stats, category breakdown and recent transactions are all computed from the `expenses` table through new helper functions in `database/db.py`. The aggregation logic that currently lives inline in the route moves into the database layer, so the route goes back to its single responsibility of fetching data and rendering the template. This step also handles a stale session — a `user_id` that no longer exists in the database — and adds the project's first automated tests. Those tests run against a temporary database so later steps (7–9: add/edit/delete expense) can build on a verified foundation.

## Depends on
- Step 01 — Database Setup (`users` and `expenses` tables, `get_db()`)
- Step 02 — Registration (users can be created)
- Step 03 — Login and Logout (`session["user_id"]` is set on login and cleared on logout)
- Step 04 — Profile Page Design (`templates/profile.html`, `static/css/profile.css`, login guard)

## Routes
No new routes. The existing route changes:
- `GET /profile` — render the profile page with the logged-in user's real data from the database. Redirect guests to `/login`. If `session["user_id"]` refers to a user that no longer exists, clear the session and redirect to `/login`. — logged-in

## Database changes
No database changes. The existing `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) columns cover everything the page needs.

New helper functions in `database/db.py`. All of them open a connection with `get_db()`, use parameterised queries and close the connection in `finally`:
- `get_user_by_id(user_id)` — returns a Row with `id, name, email, created_at`, or `None`
- `get_expense_summary(user_id)` — returns `total_spent` (`COALESCE(SUM(amount), 0)`) and `transaction_count` (`COUNT(*)`) over all of the user's expenses
- `get_category_totals(user_id)` — returns rows of `category, total` using `GROUP BY category ORDER BY total DESC`
- `get_recent_expenses(user_id, limit=10)` — returns rows of `id, date, description, category, amount` using `ORDER BY date DESC, id DESC LIMIT ?`

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - When an expense has no description (`NULL`), show a muted "—" instead of "None".
  - Rename the transactions heading to make clear it shows the latest 10 (e.g. "Recent transactions").
  - The existing empty states ("No spending yet." / "No transactions yet.") must render correctly for a user with zero expenses.

## Files to change
- `app.py` — rewrite `profile()`:
  - guard against guests
  - load the user with `get_user_by_id`, and clear the session and redirect if the user is not found
  - call the three expense helpers
  - build the `user`, `stats`, `categories` and `transactions` context and render `profile.html`
  - remove the placeholder dicts and the inline totals loop
  - remove the unused `get_db` import
- `database/db.py` — add `get_user_by_id`, `get_expense_summary`, `get_category_totals`, `get_recent_expenses`
- `templates/profile.html` — show "—" for a missing description (see Templates)
- `CLAUDE.md` — make these updates:
  - mark `GET /profile` as Implemented (real data)
  - remove the stale "`database/db.py` is currently empty" warning
  - list the new helpers in the architecture section
  - add `tests/` to the architecture tree

## Files to create
- `tests/__init__.py` — empty, makes `tests` a package
- `tests/conftest.py` — pytest fixtures:
  - `app`: patches `database.db.DB_PATH` to a `tmp_path` SQLite file and calls `init_db()` (does **not** call `seed_db()`), then sets `TESTING=True`
  - `client`: the Flask test client
  - a helper that creates a user and logs them in
- `tests/test_profile.py` — tests covering the Definition of done (guest redirect, real user data, isolation between two users, empty state, stale session, aggregation correctness)

## New dependencies
No new dependencies. `pytest` and `pytest-flask` are already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — `?` placeholders, never f-strings or string concatenation in SQL
- Passwords hashed with werkzeug (no password handling changes in this step; test users are created with `create_user`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py` — the route must not call `get_db()` or run SQL directly
- Every query that touches `expenses` must filter by `user_id = ?`, so a user can never see another user's data
- Do the aggregation (SUM, COUNT, GROUP BY) in SQL, not in Python loops
- Compute in the route only what is purely presentational:
  - initials: first letter of the first and last word of `name`, uppercased; a single-word name gives one letter
  - "Member since" formatted as `Month YYYY` from `created_at`
  - each category's `pct` share of `total_spent`, rounded to 1 decimal place and `0` when the total is 0
  - `top_category` is the first category from `get_category_totals`, or "—" when there are none
- Totals and transaction count cover **all** of the user's expenses. Only the transactions table is limited to the 10 most recent.
- Currency stays ₹ with two decimal places
- Do not implement the Step 7/8/9 expense stubs
- Do not change login/logout behaviour or the post-login redirect
- Tests must never read or write the real `expense_tracker.db`

## Definition of done
- [ ] Visiting `/profile` while logged out redirects to `/login`
- [ ] Logging in as `demo@spendly.com` / `demo123` shows "Demo User", the demo email, correct initials ("DU") and a "Member since" month/year taken from `created_at`
- [ ] Registering a new user, logging in and visiting `/profile` shows **that user's** name and email, not "Demo User"
- [ ] A brand-new user with no expenses sees Total spent ₹0.00, 0 transactions, Top category "—", and both empty-state messages
- [ ] For a user with expenses (e.g. after `/seed-expense`), Total spent and Transactions match `SELECT SUM(amount), COUNT(*) FROM expenses WHERE user_id = ?`
- [ ] The category breakdown is sorted by amount (highest first), and the bar widths add up to roughly 100%
- [ ] The transactions table shows at most 10 rows, newest date first
- [ ] One user's expenses never appear on another user's profile
- [ ] An expense with no description shows "—" rather than "None"
- [ ] Deleting the logged-in user's row from the DB (or recreating the DB) and then visiting `/profile` redirects to `/login` without a crash
- [ ] `grep -n "Demo User" app.py` returns nothing, and `app.py` contains no SQL
- [ ] `pytest` runs and all tests in `tests/test_profile.py` pass, and running them leaves `expense_tracker.db` unmodified
