# Spec: Edit Expense

## Overview
Step 8 replaces the last remaining stub, `/expenses/<id>/edit`, so a
logged-in user can correct one of their own expenses. Each row in the
profile page's "Recent transactions" table gets an "Edit" link (next to the
existing "Delete" link from Step 9) that opens a form pre-filled with the
expense's current amount, category, date and description. Submitting the
form re-validates every field with the same rules as Add Expense (Step 7),
updates the row, flashes "Expense updated." and redirects to `/profile`.
Invalid input re-renders the form with an error and the submitted values.
Ownership is enforced in SQL exactly as in Step 9: an expense that does not
exist or belongs to another user returns 404 and is never modified. Step 8
is implemented after Step 9, so it reuses the helpers that step introduced
(`get_current_user()`, `get_expense_for_user()`).

## Depends on
- Step 1: Database setup (`expenses` table, `CATEGORIES`)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Profile backend (`build_transactions()` rows feed the table)
- Step 7: Add expense (`parse_expense_form()` validation, `add_expense.html`
  form layout and `add_expense.css` styles)
- Step 9: Delete expense (`get_current_user()`, `get_expense_for_user()`,
  `id` in `build_transactions()` rows, the profile table's actions column)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in
- `POST /expenses/<int:id>/edit` — validate the form; on success update the
  expense, flash "Expense updated." (category `success`) and redirect to
  `/profile`; on validation failure re-render the form (HTTP 200) with an
  error flash and the submitted values — logged-in

For both methods:
- Guests (no `user_id` in session) are redirected to `/login`
- A stale session (`user_id` no longer in `users`) is cleared and
  redirected to `/login` (via `get_current_user()`)
- An expense id that does not exist, or that belongs to another user,
  returns `abort(404)` — identical response for both cases, nothing updated
- The ownership check runs before validation, so a POST with invalid data
  for someone else's expense still returns 404 (not a re-rendered form)

## Database changes
No database changes.

New helper in `database/db.py`:
- `update_expense_for_user(expense_id, user_id, amount, category, date, description)`
  — runs `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
  WHERE id = ? AND user_id = ?`, commits, and returns the number of rows
  updated (`cursor.rowcount`, 0 or 1). `created_at` and `user_id` are never
  changed.

Reuse the existing `get_expense_for_user(expense_id, user_id)` for the
lookup — do not add a second lookup helper.

## Templates
- **Create:** `templates/edit_expense.html`
  - Extends `base.html`; links the existing `static/css/add_expense.css`
    via `{% block head %}` (same form styles — no new CSS file)
  - Same layout and fields as `add_expense.html`: `amount` (number,
    step 0.01, min 0.01, required), `category` (`<select>` built from the
    `categories` list passed by the route), `date` (`type="date"`, required),
    `description` (text, maxlength 200, optional)
  - Header text "Edit expense"; submit button "Save Changes"
  - Form `method="post"`,
    `action="{{ url_for('edit_expense', id=expense_id) }}"`
  - Cancel link to `url_for('profile')`
  - Flash-message block (same pattern as `add_expense.html`)
  - On GET, fields show the stored values (amount formatted to 2 decimals,
    blank description when it is `NULL` — never the text "None"); after a
    validation error, fields show the submitted values
- **Modify:** `templates/profile.html`
  - In each Recent transactions row's actions cell, add an "Edit" link to
    `url_for('edit_expense', id=t.id)` before the existing "Delete" link.
    The link text must be exactly "Edit" (no description/category/amount
    in text or attributes — existing tests assert absence/order of those)

## Files to change
- `app.py`
  - Import `update_expense_for_user` from `database.db`
  - Replace the `/expenses/<int:id>/edit` stub with a `GET, POST` route in
    its own "Edit expense" section; remove the now-empty "Placeholder
    routes" section header
  - Reuse `get_current_user()`, `get_expense_for_user()` and
    `parse_expense_form()` — do not duplicate validation logic
- `database/db.py` — add `update_expense_for_user()`
- `templates/profile.html` — "Edit" link per row
- `static/css/profile.css` — style for the Edit link (and spacing between
  Edit and Delete), CSS variables only
- `tests/test_delete_expense.py` — `test_edit_route_is_still_a_stub`
  encoded Step 9's "edit is still a stub" requirement, which this step
  intentionally supersedes; remove that one test (it is replaced by the
  Step 8 tests in `tests/test_edit_expense.py`). Do not change any other
  existing test
- `CLAUDE.md` — mark `GET, POST /expenses/<id>/edit` as implemented, list
  `update_expense_for_user()` under `database/db.py`, and remove the
  "Do not implement a stub route" note's reliance on remaining stubs if no
  stubs are left

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline `<style>` tags or `style=` attributes
- DB logic lives in `database/db.py` only — never inline in the route
- Every internal link and form action uses `url_for()`
- `user_id` comes from `session` only — never from the URL or a form field;
  a submitted `user_id` field is ignored
- Ownership enforced in the SQL `WHERE` clause (`id = ? AND user_id = ?`)
  for both the lookup and the update
- Validation is exactly Step 7's rules via `parse_expense_form()`:
  - amount: finite number > 0, rounded to 2 decimals —
    "Amount must be a positive number."
  - category: must be in `CATEGORIES` — "Please choose a valid category."
  - date: valid `YYYY-MM-DD` — "Please enter a valid date."
  - description: stripped; blank → `NULL`; > 200 chars —
    "Description must be 200 characters or fewer."
  - Only the first failing check is flashed (category `error`)
- An invalid submission returns 200, re-renders the form, and leaves the
  stored expense unchanged
- If the update affects 0 rows (expense deleted between lookup and
  update), return `abort(404)`
- Use `abort(404)` — never a raw string return

## Definition of done
- [ ] `GET /expenses/<id>/edit` while logged out redirects to `/login`
- [ ] `POST /expenses/<id>/edit` while logged out redirects to `/login` and
  the expense is unchanged
- [ ] Both methods with a stale session clear it, redirect to `/login`, and
  change nothing
- [ ] `GET /expenses/<id>/edit` for the user's own expense returns 200 with
  all four fields pre-filled with the stored values and the stored
  category selected
- [ ] An expense with no description shows an empty description field
  (not "None")
- [ ] The category dropdown lists exactly the 7 categories
- [ ] Submitting valid changes updates amount, category, date and
  description, flashes "Expense updated." and redirects to `/profile`
- [ ] The updated values appear in Recent transactions, and total spent and
  category breakdown reflect the change
- [ ] Clearing the description stores `NULL`
- [ ] The expense's `user_id` and `created_at` are unchanged after an edit
- [ ] Missing / zero / negative / non-numeric / `inf` amount, invalid
  category, invalid date, or a description over 200 characters each
  re-render the form with the matching error, keep the submitted values,
  and leave the stored expense unchanged
- [ ] `GET` and `POST` for another user's expense return 404 and that
  expense is unchanged
- [ ] `GET` and `POST` for a non-existent id return 404
- [ ] A forged `user_id` form field cannot move or edit another user's
  expense
- [ ] Editing one expense leaves the user's other expenses untouched
- [ ] Each row in the profile Recent transactions table has an "Edit" link
  to that expense's `/expenses/<id>/edit` page, alongside the "Delete" link
- [ ] The edit form's Cancel link goes to `/profile`
