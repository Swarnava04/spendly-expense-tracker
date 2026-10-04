# Spec: Add Expense

## Overview
Step 7 lets a logged-in user submit a new expense through a dedicated form page
at `/expenses/add`. The route already exists as a GET placeholder; this step
upgrades it to a full GET + POST handler, inserts validated data into the
`expenses` table, and redirects back to the profile page on success. A reusable
`insert_expense` query helper is added to `database/db.py`. An "Add Expense"
button is added to `profile.html` and an "Add Expense" navbar link to
`base.html` so users can navigate to the form.

## Depends on
- Step 1: Database setup (`expenses` table exists with all required columns)
- Step 3: Login / Logout (`session["user_id"]` is set and checked)
- Step 4 / 5: Profile page exists and is the natural redirect target after saving

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert the new expense — logged-in only

Guests (no `user_id` in session) are redirected to `/login` for both methods.
A stale session (the `user_id` no longer exists in `users`) is cleared with
`session.clear()` and redirected to `/login`, matching `/profile`.

## Database changes
No database changes. The `expenses` table already has all required columns:
`id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create**: `templates/add_expense.html`
  - Extends `base.html`
  - Form with `method="POST"` and `action="{{ url_for('add_expense') }}"`
  - Fields:
    - `amount` — number input, step="0.01", min="0.01", required
    - `category` — `<select>` built by looping over the `categories` list
      passed from the route (`CATEGORIES` from `database/db.py`: Food,
      Transport, Bills, Health, Entertainment, Shopping, Other) — not
      hardcoded in the template
    - `date` — `<input type="date">`, required, defaults to today's date
    - `description` — text input, optional, max 200 chars
  - Submit button ("Save Expense") and a cancel link to `url_for('profile')`
  - Display flash/error message when validation fails, re-populating previous values
- **Modify**: `templates/profile.html`
  - Add an "Add Expense" button/link to `url_for('add_expense')` (e.g., near the transaction table heading)
- **Modify**: `templates/base.html`
  - Add an "Add Expense" navbar link to `url_for('add_expense')`, visible
    only when `session.user_id` is set

## Files to change
- `app.py` — replace the GET-only placeholder at `/expenses/add` with a GET+POST handler:
  - Import `insert_expense` and `CATEGORIES` from `database.db`
  - GET: render `add_expense.html` with `categories=CATEGORIES` (redirect to login if not authenticated or session is stale)
  - POST: read form fields, validate, call `insert_expense`, redirect to `url_for("profile")`
  - Keep validation in a small helper (e.g. `parse_expense_form(form)` returning `(values, error)`) so the route stays single-responsibility
- `database/db.py` — add `insert_expense(user_id, amount, category, date, description)`; returns the new row id
- `templates/profile.html` — add "Add Expense" button
- `templates/base.html` — add logged-in-only "Add Expense" navbar link
- `static/css/profile.css` — style for the "Add Expense" button
- `CLAUDE.md` — mark `GET, POST /expenses/add` as implemented and list `insert_expense()` under `database/db.py`

## Files to create
- `templates/add_expense.html` — the add-expense form template
- `static/css/add_expense.css` — page-specific form styles (linked from `add_expense.html`)

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- DB logic lives in `database/db.py` only — never inline in the route
- Every internal link and form action uses `url_for()` — never a hardcoded path
- `user_id` comes from `session` only — never from a form field
- Parameterised queries only — never string-format values into SQL
- Foreign keys PRAGMA must be enabled on every connection (already done in `get_db()`)
- Unauthenticated access to both GET and POST `/expenses/add` must redirect to `/login`
- A stale session must be cleared and redirected to `/login`; nothing is inserted
- Validation rules for POST:
  - `amount`: required, must be a finite number greater than 0 (parse with `float()`; catch `ValueError`; reject `inf`/`nan` with `math.isfinite`); round to 2 decimal places before storing
  - `category`: required, must be in `CATEGORIES` exactly (reject anything else)
  - `date`: required, must be a valid `YYYY-MM-DD` date (parse with `datetime.strptime`)
  - `description`: optional; strip whitespace; store `None` if blank; reject if longer than 200 characters (checked server-side, not just via `maxlength`)
  - On any validation error, re-render the form with the error message and the previously submitted values pre-filled
- After successful insert, flash "Expense added." (category `success`) and redirect to `url_for("profile")` — do NOT render the form again
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₹ — never £ or $

## Tests to write
File: `tests/test_add_expense.py`

### Unit tests
| Function | Input | Expected output |
|---|---|---|
| `insert_expense` | valid `user_id`, `amount=50.0`, `category="Food"`, `date="2026-03-20"`, `description="Lunch"` | row inserted; querying the DB returns the new row |
| `insert_expense` | `description=None` | row inserted with `description` stored as `NULL` |

### Route tests
`GET /expenses/add` — unauthenticated:
- Redirects to `/login` (302)

`GET /expenses/add` — authenticated:
- Returns 200
- Response body contains the category `<select>` with all 7 options
- Response body contains `<form` with `method` POST

`POST /expenses/add` — unauthenticated:
- Redirects to `/login` (302)

`POST /expenses/add` — authenticated, valid data (`amount=50.0`, `category=Food`, `date=2026-03-20`, `description=Lunch`):
- Redirects to `/profile` (302)
- New expense row exists in the database for the test user

`POST /expenses/add` — authenticated, missing amount:
- Returns 200 (re-renders form)
- Response body contains an error message

`POST /expenses/add` — authenticated, amount = 0:
- Returns 200 (re-renders form)
- Response body contains an error message

`POST /expenses/add` — authenticated, non-numeric amount:
- Returns 200 (re-renders form)
- Response body contains an error message

`POST /expenses/add` — authenticated, invalid category (not in fixed list):
- Returns 200 (re-renders form)
- Response body contains an error message

`POST /expenses/add` — authenticated, invalid date string:
- Returns 200 (re-renders form)
- Response body contains an error message

`POST /expenses/add` — authenticated, amount = `inf`:
- Returns 200 (re-renders form)
- Response body contains an error message
- No row inserted

`POST /expenses/add` — authenticated, description of 201 characters:
- Returns 200 (re-renders form)
- Response body contains an error message
- No row inserted

`GET` and `POST /expenses/add` — stale session (`user_id` not in `users`):
- Redirects to `/login` (302)
- Session no longer contains `user_id`
- No row inserted

`POST /expenses/add` — authenticated, no description (optional field):
- Redirects to `/profile` (302)
- Row inserted with `description = NULL`

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` with a stale session clears it and redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount, category, date, and description fields
- [ ] The category dropdown contains exactly: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- [ ] Submitting a valid expense redirects to `/profile` and the new expense appears in the transaction list
- [ ] Submitting with a missing, zero, negative, non-numeric or `inf` amount re-renders the form with an error and previously entered values retained
- [ ] Submitting with an invalid category re-renders the form with an error
- [ ] Submitting with an invalid date re-renders the form with an error
- [ ] Submitting without a description saves the expense with no description (no error)
- [ ] Submitting a description over 200 characters re-renders the form with an error
- [ ] The "Add Expense" button on the profile page navigates to `/expenses/add`
- [ ] Navbar shows "Add Expense" link when logged in, and hides it when logged out
- [ ] No template contains a hardcoded internal URL — all use `url_for()`