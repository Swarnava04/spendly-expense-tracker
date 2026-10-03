import database.db as db


def test_guest_is_redirected_to_login(client):
    response = client.get("/profile")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_profile_shows_logged_in_users_details(client, make_user, login):
    make_user(name="Asha Rao", email="asha@example.com")
    login(email="asha@example.com")

    html = client.get("/profile").get_data(as_text=True)

    assert "Asha Rao" in html
    assert "asha@example.com" in html
    assert ">AR<" in html
    assert "Member since" in html
    assert "Demo User" not in html


def test_single_word_name_gives_one_initial(client, make_user, login):
    make_user(name="Madonna")
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert ">M<" in html


def test_new_user_sees_empty_state(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert "₹0.00" in html
    assert "No spending yet." in html
    assert "No transactions yet." in html
    assert "—" in html  # top category placeholder


def test_summary_stats_and_categories(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 100.00, "Food", "2026-09-01", "Lunch")
    add_expense(user_id, 50.50, "Food", "2026-09-02", "Snacks")
    add_expense(user_id, 300.00, "Bills", "2026-09-03", "Internet")
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert "₹450.50" in html          # total spent
    assert "₹300.00" in html          # Bills total
    assert "₹150.50" in html          # Food total
    assert html.index("Bills") < html.index("Food")  # sorted by amount desc
    assert "width: 66.6%" in html     # 300 / 450.50
    assert "width: 33.4%" in html     # 150.50 / 450.50


def test_summary_helpers_return_correct_values(make_user, add_expense, app):
    user_id = make_user()
    add_expense(user_id, 10.0, "Food", "2026-09-01")
    add_expense(user_id, 20.0, "Transport", "2026-09-02")
    add_expense(user_id, 5.0, "Food", "2026-09-03")

    summary = db.get_expense_summary(user_id)
    assert summary["total_spent"] == 35.0
    assert summary["transaction_count"] == 3

    totals = [(row["category"], row["total"]) for row in db.get_category_totals(user_id)]
    assert totals == [("Transport", 20.0), ("Food", 15.0)]


def test_transactions_limited_to_ten_newest_first(client, make_user, login, add_expense):
    user_id = make_user()
    for day in range(1, 13):
        add_expense(user_id, day, "Other", f"2026-09-{day:02d}", f"Item {day:02d}")
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert "Item 12" in html
    assert "Item 01" not in html and "Item 02" not in html
    assert html.index("Item 12") < html.index("Item 03")
    # totals still cover all 12 expenses
    assert "₹78.00" in html


def test_missing_description_renders_dash(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 42.0, "Health", "2026-09-05", None)
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert "None" not in html
    assert "—" in html


def test_users_do_not_see_each_others_expenses(client, make_user, login, add_expense):
    alice = make_user(name="Alice", email="alice@example.com")
    bob = make_user(name="Bob", email="bob@example.com")
    add_expense(alice, 999.0, "Shopping", "2026-09-01", "Alice secret purchase")
    add_expense(bob, 10.0, "Food", "2026-09-01", "Bob sandwich")
    login(email="bob@example.com")

    html = client.get("/profile").get_data(as_text=True)

    assert "Bob sandwich" in html
    assert "Alice secret purchase" not in html
    assert "₹999.00" not in html


def test_stale_session_is_cleared_and_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999

    response = client.get("/profile")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
