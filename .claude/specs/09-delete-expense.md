# Spec: Delete Expense

## Overview
Step 9 replaces the `/expenses/<id>/delete` stub so a logged-in user can
permanently remove one of their own expenses. Each row in the profile page's
"Recent transactions" table gets a "Delete" link that opens a confirmation
page showing the expense's details; confirming submits a POST that deletes the
row and redirects back to `/profile` with a success message. The GET request
never deletes anything — deletion only happens on POST, so a prefetched link,
crawler or accidental click cannot remove data. Ownership is enforced in SQL:
an expense that does not exist or belongs to another user returns 404 and is
left untouched. This step does not depend on Step 8 (edit expense), which is
still a stub.

## Depends on
- Step 1: Database setup (`expenses` table)
- Step 3: Login / Logout (`session["user_id"]`)
- Step 5: Profile backend (`get_recent_expenses` already selects `id`;
  `build_transactions` feeds the transactions table)
- Step 7: Add expense (the stale-session guard pattern this step reuses)

## Routes
- `GET /expenses/<int:id>/delete` — render a confirmation page for the
  expense with this id, if it belongs to the logged-in user — logged-in
- `POST /expenses/<int:id>/delete` — delete the expense if it belongs to
  the logged-in user, flash "Expense deleted." (category `success`) and
  redirect to `/profile` — logged-in

For both methods:
- Guests (no `user_id` in session) are redirected to `/login`
- A stale session (`user_id` no longer in `users`) is cleared with
  `session.clear()` and redirected to `/login`
- An expense id that does not exist, or that belongs to another user,
  returns `abort(404)` — the response must not reveal which of the two
  cases applied, and nothing is deleted

## Database changes
No database changes.

New helpers in `database/db.py`:
- `get_expense_for_user(expense_id, user_id)` — returns the row
  (`id, amount, category, date, description`) or `None`, using
  `WHERE id = ? AND user_id = ?`
- `delete_expense_for_user(expense_id, user_id)` — runs
  `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, and
  returns the number of rows deleted (`cursor.rowcount`, 0 or 1)

## Templates
- **Create:** `templates/delete_expense.html`
  - Extends `base.html`; links `static/css/delete_expense.css` via
    `{% block head %}`
  - Shows the expense's date, description (or "—" if none), category and
    amount formatted as `₹{{ "%.2f"|format(amount) }}`
  - Warning text that the action cannot be undone
  - A form with `method="post"` and
    `action="{{ url_for('delete_expense', id=expense.id) }}"` containing a
    "Delete Expense" submit button
  - A "Cancel" link to `url_for('profile')`
- **Modify:** `templates/profile.html`
  - Add a fifth column to the Recent transactions table (empty or
    visually-hidden "Actions" header) with a "Delete" link per row to
    `url_for('delete_expense', id=t.id)`

## Files to change
- `app.py`
  - Import `get_expense_for_user` and `delete_expense_for_user` from
    `database.db`
  - Add a `get_current_user()` helper that returns the logged-in user's row
    or `None`, clearing a stale session; use it in the new route (and
    optionally refactor `profile()` and `add_expense()` to use it, with no
    behaviour change)
  - `build_transactions()` — include `"id": row["id"]` in each dict
  - Replace the `/expenses/<int:id>/delete` stub with a `GET, POST` route
- `database/db.py` — add `get_expense_for_user()` and
  `delete_expense_for_user()`
- `templates/profile.html` — Delete link column
- `static/css/profile.css` — style for the Delete link (danger colour via
  CSS variable)
- `CLAUDE.md` — mark `GET, POST /expenses/<id>/delete` as implemented and
  list the two new helpers under `database/db.py`

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — `?` placeholders, never f-strings in SQL
- Passwords hashed with werkzeug (no auth changes in this step)
- Use CSS variables — never hardcode hex values (use `--danger` /
  `--danger-light` for destructive styling)
- All templates extend `base.html`
- No inline `<style>` tags or `style=` attributes
- DB logic lives in `database/db.py` only — never inline in the route
- Every internal link and form action uses `url_for()`
- `user_id` comes from `session` only — never from the URL or a form field
- Ownership is enforced in the SQL `WHERE` clause (`id = ? AND user_id = ?`)
  for both the lookup and the delete — never fetch by id alone and compare
  afterwards in Python
- GET must never delete; only POST deletes
- Use `abort(404)` for missing / not-owned expenses — never a raw string
  return
- Do not implement the edit stub (`/expenses/<id>/edit`) in this step

## Definition of done
- [ ] `GET /expenses/<id>/delete` while logged out redirects to `/login`
- [ ] `POST /expenses/<id>/delete` while logged out redirects to `/login`
  and the expense still exists
- [ ] Both methods with a stale session clear it, redirect to `/login`, and
  delete nothing
- [ ] `GET /expenses/<id>/delete` for the user's own expense returns 200 and
  shows its date, description, category and ₹ amount, a "Delete Expense"
  button and a Cancel link to `/profile`
- [ ] `GET` on the confirmation page does not delete the expense
- [ ] `POST /expenses/<id>/delete` for the user's own expense removes the
  row, flashes "Expense deleted." and redirects to `/profile`
- [ ] After deletion the expense no longer appears in Recent transactions,
  and total spent, transaction count and category breakdown reflect the
  removal
- [ ] `GET` and `POST` for another user's expense return 404 and the other
  user's expense still exists
- [ ] `GET` and `POST` for a non-existent id return 404
- [ ] `POST` twice for the same expense: first redirects to `/profile`,
  second returns 404
- [ ] Deleting one expense leaves the user's other expenses untouched
- [ ] Each row in the profile Recent transactions table has a "Delete" link
  to that expense's `/expenses/<id>/delete` page
- [ ] `/expenses/<id>/edit` is still the Step 8 stub
