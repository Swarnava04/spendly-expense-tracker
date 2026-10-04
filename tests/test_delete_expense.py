import re

import pytest

import database.db as db


def _expense_exists(expense_id):
    conn = db.get_db()
    try:
        row = conn.execute("SELECT id FROM expenses WHERE id = ?", (expense_id,)).fetchone()
    finally:
        conn.close()
    return row is not None


def _expense_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT user_id, amount, category, date, description FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
    finally:
        conn.close()


def _expense_count():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _flashes(client):
    with client.session_transaction() as sess:
        return list(sess.get("_flashes", []))


def _forms(html):
    return re.findall(r"<form\b[^>]*>", html, flags=re.I)


@pytest.fixture
def logged_in(make_user, login):
    user_id = make_user()
    login()
    return user_id


@pytest.fixture
def other_user(make_user):
    return make_user(name="Other Person", email="other@example.com")


# --- get_expense_for_user helper -------------------------------------------


def test_get_expense_for_user_returns_row(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    row = db.get_expense_for_user(expense_id, user_id)

    assert row is not None
    assert row["id"] == expense_id
    assert row["amount"] == 42.5
    assert row["category"] == "Food"
    assert row["date"] == "2026-01-15"
    assert row["description"] == "Lunch"


def test_get_expense_for_user_returns_none_for_missing_id(app, make_user):
    user_id = make_user()

    assert db.get_expense_for_user(9999, user_id) is None


def test_get_expense_for_user_returns_none_for_other_users_expense(app, make_user, other_user):
    user_id = make_user()
    expense_id = db.insert_expense(other_user, 10.0, "Bills", "2026-01-15", "Rent")

    assert db.get_expense_for_user(expense_id, user_id) is None


def test_get_expense_for_user_returns_null_description(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 5.0, "Other", "2026-01-15", None)

    row = db.get_expense_for_user(expense_id, user_id)

    assert row["description"] is None


# --- delete_expense_for_user helper ----------------------------------------


def test_delete_expense_for_user_returns_one_and_removes_row(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    deleted = db.delete_expense_for_user(expense_id, user_id)

    assert deleted == 1
    assert not _expense_exists(expense_id)


def test_delete_expense_for_user_returns_zero_for_missing_id(app, make_user):
    user_id = make_user()
    db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    deleted = db.delete_expense_for_user(9999, user_id)

    assert deleted == 0
    assert _expense_count() == 1


def test_delete_expense_for_user_enforces_ownership(app, make_user, other_user):
    user_id = make_user()
    expense_id = db.insert_expense(other_user, 10.0, "Bills", "2026-01-15", "Rent")

    deleted = db.delete_expense_for_user(expense_id, user_id)

    assert deleted == 0
    assert _expense_exists(expense_id)


def test_delete_expense_for_user_second_call_returns_zero(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    db.delete_expense_for_user(expense_id, user_id)

    assert db.delete_expense_for_user(expense_id, user_id) == 0


def test_delete_expense_for_user_leaves_other_rows(app, make_user):
    user_id = make_user()
    keep_id = db.insert_expense(user_id, 1.0, "Food", "2026-01-14", "Keep")
    drop_id = db.insert_expense(user_id, 2.0, "Food", "2026-01-15", "Drop")

    db.delete_expense_for_user(drop_id, user_id)

    assert _expense_exists(keep_id)
    assert not _expense_exists(drop_id)


def test_get_current_user_helper_exists():
    import app as app_module

    assert callable(app_module.get_current_user)


# --- auth guards ------------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_guest_is_redirected_to_login(client, make_user, method):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert _expense_exists(expense_id)


@pytest.mark.parametrize("method", ["get", "post"])
def test_stale_session_is_cleared_and_nothing_deleted(client, make_user, method):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    with client.session_transaction() as sess:
        sess["user_id"] = 9999

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert _expense_count() == 1


# --- confirmation page (GET) -----------------------------------------------


def test_confirmation_page_shows_expense_details(client, logged_in):
    expense_id = db.insert_expense(logged_in, 1234.5, "Transport", "2026-01-15", "Taxi to airport")

    response = client.get(f"/expenses/{expense_id}/delete")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "2026-01-15" in html
    assert "Taxi to airport" in html
    assert "Transport" in html
    assert "₹1234.50" in html
    assert "Delete Expense" in html


def test_confirmation_page_shows_dash_for_missing_description(client, logged_in):
    expense_id = db.insert_expense(logged_in, 7.0, "Health", "2026-01-15", None)

    html = client.get(f"/expenses/{expense_id}/delete").get_data(as_text=True)

    assert "—" in html
    assert "None" not in html


def test_confirmation_page_form_posts_to_delete_url(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    html = client.get(f"/expenses/{expense_id}/delete").get_data(as_text=True)

    matching = [
        tag
        for tag in _forms(html)
        if re.search(r'method="post"', tag, flags=re.I)
        and f'action="/expenses/{expense_id}/delete"' in tag
    ]
    assert matching
    assert re.search(r'type="submit"', html, flags=re.I)


def test_confirmation_page_has_cancel_link_to_profile(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    html = client.get(f"/expenses/{expense_id}/delete").get_data(as_text=True)

    assert re.search(r'<a\b[^>]*href="/profile"[^>]*>\s*Cancel\s*</a>', html, flags=re.I)


def test_confirmation_page_links_its_stylesheet(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    html = client.get(f"/expenses/{expense_id}/delete").get_data(as_text=True)

    assert "css/delete_expense.css" in html


def test_get_does_not_delete(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    client.get(f"/expenses/{expense_id}/delete")
    client.get(f"/expenses/{expense_id}/delete")

    assert _expense_exists(expense_id)


# --- deletion (POST) -------------------------------------------------------


def test_post_deletes_flashes_and_redirects(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    response = client.post(f"/expenses/{expense_id}/delete")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    assert not _expense_exists(expense_id)
    assert ("success", "Expense deleted.") in _flashes(client)


def test_post_flash_is_shown_on_profile(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    response = client.post(f"/expenses/{expense_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert "Expense deleted." in response.get_data(as_text=True)


def test_post_twice_second_returns_404(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    first = client.post(f"/expenses/{expense_id}/delete")
    second = client.post(f"/expenses/{expense_id}/delete")

    assert first.status_code == 302
    assert first.headers["Location"].endswith("/profile")
    assert second.status_code == 404


def test_get_after_delete_returns_404(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")
    client.post(f"/expenses/{expense_id}/delete")

    response = client.get(f"/expenses/{expense_id}/delete")

    assert response.status_code == 404


def test_delete_leaves_other_expenses_untouched(client, logged_in, other_user):
    keep_id = db.insert_expense(logged_in, 10.0, "Bills", "2026-01-14", "Internet")
    drop_id = db.insert_expense(logged_in, 20.0, "Food", "2026-01-15", "Dinner")
    theirs_id = db.insert_expense(other_user, 30.0, "Food", "2026-01-15", "Their dinner")

    client.post(f"/expenses/{drop_id}/delete")

    assert not _expense_exists(drop_id)
    keep = _expense_row(keep_id)
    assert keep["user_id"] == logged_in
    assert keep["amount"] == 10.0
    assert keep["category"] == "Bills"
    assert keep["date"] == "2026-01-14"
    assert keep["description"] == "Internet"
    assert _expense_exists(theirs_id)


def test_profile_reflects_deletion(client, logged_in):
    db.insert_expense(logged_in, 100.0, "Food", "2026-01-14", "Groceries run")
    drop_id = db.insert_expense(logged_in, 250.0, "Shopping", "2026-01-15", "Fancy jacket")

    before = client.get("/profile").get_data(as_text=True)
    assert "Fancy jacket" in before
    assert "₹350.00" in before

    client.post(f"/expenses/{drop_id}/delete")
    html = client.get("/profile").get_data(as_text=True)

    assert "Fancy jacket" not in html
    assert "Groceries run" in html
    assert "₹350.00" not in html
    assert "₹250.00" not in html
    assert "₹100.00" in html


def test_summary_helpers_reflect_deletion(client, logged_in):
    db.insert_expense(logged_in, 100.0, "Food", "2026-01-14", "Groceries run")
    drop_id = db.insert_expense(logged_in, 250.0, "Shopping", "2026-01-15", "Fancy jacket")

    client.post(f"/expenses/{drop_id}/delete")

    summary = db.get_expense_summary(logged_in)
    assert summary["total_spent"] == 100.0
    assert summary["transaction_count"] == 1
    totals = [(row["category"], row["total"]) for row in db.get_category_totals(logged_in)]
    assert totals == [("Food", 100.0)]


def test_deleting_only_expense_shows_empty_state(client, logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    client.post(f"/expenses/{expense_id}/delete")
    html = client.get("/profile").get_data(as_text=True)

    assert "No transactions yet." in html
    assert "No spending yet." in html
    assert "₹0.00" in html


# --- ownership and missing ids ---------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_other_users_expense_returns_404(client, logged_in, other_user, method):
    expense_id = db.insert_expense(other_user, 999.0, "Shopping", "2026-01-15", "Secret purchase")

    response = getattr(client, method)(f"/expenses/{expense_id}/delete")

    assert response.status_code == 404
    assert "Secret purchase" not in response.get_data(as_text=True)
    row = _expense_row(expense_id)
    assert row is not None
    assert row["user_id"] == other_user


@pytest.mark.parametrize("method", ["get", "post"])
def test_nonexistent_id_returns_404(client, logged_in, method):
    db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")

    response = getattr(client, method)("/expenses/9999/delete")

    assert response.status_code == 404
    assert _expense_count() == 1


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_and_foreign_404s_look_the_same(client, logged_in, other_user, method):
    foreign_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")

    foreign = getattr(client, method)(f"/expenses/{foreign_id}/delete")
    missing = getattr(client, method)("/expenses/9999/delete")

    assert foreign.status_code == missing.status_code == 404
    assert foreign.get_data(as_text=True) == missing.get_data(as_text=True)


def test_non_integer_id_returns_404(client, logged_in):
    response = client.get("/expenses/abc/delete")

    assert response.status_code == 404


def test_post_ignores_user_id_in_form(client, logged_in, other_user):
    expense_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")

    response = client.post(f"/expenses/{expense_id}/delete", data={"user_id": str(other_user)})

    assert response.status_code == 404
    assert _expense_exists(expense_id)


# --- profile Delete links --------------------------------------------------


def test_profile_rows_have_delete_links(client, logged_in):
    ids = [
        db.insert_expense(logged_in, 10.0, "Food", "2026-01-13", "First"),
        db.insert_expense(logged_in, 20.0, "Bills", "2026-01-14", "Second"),
        db.insert_expense(logged_in, 30.0, "Other", "2026-01-15", "Third"),
    ]

    html = client.get("/profile").get_data(as_text=True)

    for expense_id in ids:
        assert f'href="/expenses/{expense_id}/delete"' in html, expense_id
    assert re.search(r"<a\b[^>]*>\s*Delete\s*</a>", html)


def test_profile_has_no_delete_links_for_other_users(client, logged_in, other_user):
    theirs_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")

    html = client.get("/profile").get_data(as_text=True)

    assert f"/expenses/{theirs_id}/delete" not in html
