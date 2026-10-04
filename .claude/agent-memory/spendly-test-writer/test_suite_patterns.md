---
name: test-suite-patterns
description: Spendly test-suite conventions, fixture names, file-to-feature map and heuristics used when specs leave error wording unspecified
metadata:
  type: project
---

- conftest fixtures: `app`, `client`, `make_user(name,email,password)`, `login(email,password)`, `add_expense(user_id, amount, category, date, description=None)` (direct-insert factory, returns nothing — use `db.insert_expense(...)` when you need the id; don't shadow it; use a local `logged_in` fixture instead).
- Files: test_profile.py (profile backend), test_date_filter_profile.py (step 6 filter), test_add_expense.py (step 7, /expenses/add + insert_expense), test_delete_expense.py (step 9, /expenses/<id>/delete + get_expense_for_user/delete_expense_for_user).
- Stale-session pattern: `client.session_transaction()` set user_id=9999, expect 302 to /login and user_id removed.
- Flash check without following redirect: read `sess["_flashes"]` -> list of (category, message).
- Flashes are rendered per-page (profile/login/register/add_expense templates), not in base.html.
- Specs often say "contains an error message" without wording: test_add_expense.py uses a `_shows_error(clean_html, error_html)` diff heuristic (new text lines vs a clean GET, ignoring value=/option lines).
- Stub routes (e.g. /expenses/<id>/edit) have no spec'd body text; test only 200 + no `<form`.
- Profile strings to rely on: "No transactions yet.", "No spending yet.", "₹0.00", "—" placeholder; transaction count has no spec'd HTML format, so verify it via `get_expense_summary`.

**Why:** speeds up writing new feature test files consistently.
**How to apply:** reuse these patterns for step 8 (edit expense) and later steps.
