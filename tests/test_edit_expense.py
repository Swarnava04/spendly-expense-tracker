import re

import pytest

import database.db as db

EXPECTED_CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]

FIXED_CREATED_AT = "2020-01-01 00:00:00"

AMOUNT_ERROR = "Amount must be a positive number."
CATEGORY_ERROR = "Please choose a valid category."
DATE_ERROR = "Please enter a valid date."
DESCRIPTION_ERROR = "Description must be 200 characters or fewer."

VALID_EDIT = {
    "amount": "250.00",
    "category": "Shopping",
    "date": "2026-02-20",
    "description": "Fancy jacket",
}


def _form(**overrides):
    data = dict(VALID_EDIT)
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def _expense_row(expense_id):
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT user_id, amount, category, date, description, created_at "
            "FROM expenses WHERE id = ?",
            (expense_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _set_created_at(expense_id, value=FIXED_CREATED_AT):
    conn = db.get_db()
    try:
        conn.execute("UPDATE expenses SET created_at = ? WHERE id = ?", (value, expense_id))
        conn.commit()
    finally:
        conn.close()


def _flashes(client):
    with client.session_transaction() as sess:
        return list(sess.get("_flashes", []))


def _input_tag(html, name):
    match = re.search(rf"<input\b[^>]*name=\"{name}\"[^>]*>", html, flags=re.S | re.I)
    return match.group(0) if match else None


def _option_tags(html):
    return re.findall(r"<option\b[^>]*>.*?</option>", html, flags=re.S | re.I)


def _category_select(html):
    match = re.search(
        r"<select\b[^>]*name=\"category\"[^>]*>(.*?)</select>", html, flags=re.S | re.I
    )
    return match.group(1) if match else None


def _selected_labels(html):
    select = _category_select(html)
    assert select is not None
    return [
        re.sub(r"<[^>]+>", "", opt).strip()
        for opt in _option_tags(select)
        if re.search(r"\bselected\b", opt, flags=re.I)
    ]


@pytest.fixture
def logged_in(make_user, login):
    user_id = make_user()
    login()
    return user_id


@pytest.fixture
def other_user(make_user):
    return make_user(name="Other Person", email="other@example.com")


@pytest.fixture
def own_expense(logged_in):
    expense_id = db.insert_expense(logged_in, 42.5, "Food", "2026-01-15", "Lunch")
    _set_created_at(expense_id)
    return expense_id


# --- update_expense_for_user helper ----------------------------------------


def test_update_expense_for_user_returns_one_and_updates_row(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    updated = db.update_expense_for_user(
        expense_id, user_id, 99.99, "Bills", "2026-02-01", "Electricity"
    )

    assert updated == 1
    row = _expense_row(expense_id)
    assert row["amount"] == 99.99
    assert row["category"] == "Bills"
    assert row["date"] == "2026-02-01"
    assert row["description"] == "Electricity"


def test_update_expense_for_user_stores_null_description(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    db.update_expense_for_user(expense_id, user_id, 42.5, "Food", "2026-01-15", None)

    assert _expense_row(expense_id)["description"] is None


def test_update_expense_for_user_returns_zero_for_missing_id(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")

    updated = db.update_expense_for_user(9999, user_id, 1.0, "Other", "2026-02-01", "X")

    assert updated == 0
    assert _expense_row(expense_id)["amount"] == 42.5


def test_update_expense_for_user_enforces_ownership(app, make_user, other_user):
    user_id = make_user()
    expense_id = db.insert_expense(other_user, 10.0, "Bills", "2026-01-15", "Rent")
    before = _expense_row(expense_id)

    updated = db.update_expense_for_user(
        expense_id, user_id, 1.0, "Other", "2026-02-01", "Hijacked"
    )

    assert updated == 0
    assert _expense_row(expense_id) == before


def test_update_expense_for_user_keeps_user_id_and_created_at(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    _set_created_at(expense_id)

    db.update_expense_for_user(expense_id, user_id, 5.0, "Health", "2026-02-01", "Pills")

    row = _expense_row(expense_id)
    assert row["user_id"] == user_id
    assert row["created_at"] == FIXED_CREATED_AT


def test_update_expense_for_user_leaves_other_rows(app, make_user, other_user):
    user_id = make_user()
    keep_id = db.insert_expense(user_id, 1.0, "Food", "2026-01-14", "Keep")
    edit_id = db.insert_expense(user_id, 2.0, "Food", "2026-01-15", "Edit me")
    theirs_id = db.insert_expense(other_user, 3.0, "Food", "2026-01-15", "Theirs")
    keep_before = _expense_row(keep_id)
    theirs_before = _expense_row(theirs_id)

    db.update_expense_for_user(edit_id, user_id, 9.0, "Other", "2026-02-01", "Edited")

    assert _expense_row(keep_id) == keep_before
    assert _expense_row(theirs_id) == theirs_before


def test_update_expense_for_user_stores_sql_literally(app, make_user):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    payload = "'); DROP TABLE expenses; --"

    db.update_expense_for_user(expense_id, user_id, 42.5, "Food", "2026-01-15", payload)

    assert _expense_row(expense_id)["description"] == payload


# --- auth guards -----------------------------------------------------------


@pytest.mark.parametrize("method", ["get", "post"])
def test_guest_is_redirected_to_login(client, make_user, method):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    before = _expense_row(expense_id)

    response = getattr(client, method)(f"/expenses/{expense_id}/edit", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert _expense_row(expense_id) == before


@pytest.mark.parametrize("method", ["get", "post"])
def test_stale_session_is_cleared_and_nothing_changed(client, make_user, method):
    user_id = make_user()
    expense_id = db.insert_expense(user_id, 42.5, "Food", "2026-01-15", "Lunch")
    before = _expense_row(expense_id)
    with client.session_transaction() as sess:
        sess["user_id"] = 9999

    response = getattr(client, method)(f"/expenses/{expense_id}/edit", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert _expense_row(expense_id) == before


# --- GET pre-filled form ---------------------------------------------------


def test_get_renders_edit_form(client, own_expense):
    response = client.get(f"/expenses/{own_expense}/edit")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Edit expense" in html
    assert "Save Changes" in html


def test_get_form_posts_to_edit_url(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    forms = re.findall(r"<form\b[^>]*>", html, flags=re.I)
    matching = [
        tag
        for tag in forms
        if re.search(r'method="post"', tag, flags=re.I)
        and f'action="/expenses/{own_expense}/edit"' in tag
    ]
    assert matching


def test_get_prefills_amount_to_two_decimals(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    tag = _input_tag(html, "amount")
    assert tag
    assert 'value="42.50"' in tag


def test_get_prefills_date(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    tag = _input_tag(html, "date")
    assert tag
    assert 'value="2026-01-15"' in tag


def test_get_prefills_description(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    tag = _input_tag(html, "description")
    assert tag
    assert 'value="Lunch"' in tag


@pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
def test_get_selects_stored_category(client, logged_in, category):
    expense_id = db.insert_expense(logged_in, 10.0, category, "2026-01-15", "Thing")

    html = client.get(f"/expenses/{expense_id}/edit").get_data(as_text=True)

    assert _selected_labels(html) == [category]


def test_get_shows_blank_description_for_null(client, logged_in):
    expense_id = db.insert_expense(logged_in, 7.0, "Health", "2026-01-15", None)

    html = client.get(f"/expenses/{expense_id}/edit").get_data(as_text=True)

    tag = _input_tag(html, "description")
    assert tag
    assert "None" not in tag
    value = re.search(r'value="([^"]*)"', tag)
    assert value is None or value.group(1) == ""
    assert "None" not in html


def test_category_dropdown_has_exactly_the_seven_categories(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    select = _category_select(html)
    assert select is not None
    options = _option_tags(select)
    labels = [re.sub(r"<[^>]+>", "", opt).strip() for opt in options]
    assert [label for label in labels if label in EXPECTED_CATEGORIES] == EXPECTED_CATEGORIES
    for opt, label in zip(options, labels):
        if label not in EXPECTED_CATEGORIES:
            assert 'value=""' in opt, f"unexpected category option: {opt}"


def test_amount_input_attributes(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    tag = _input_tag(html, "amount")
    assert tag
    assert 'type="number"' in tag
    assert 'step="0.01"' in tag
    assert 'min="0.01"' in tag
    assert "required" in tag


def test_date_and_description_input_attributes(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    date_tag = _input_tag(html, "date")
    description_tag = _input_tag(html, "description")
    assert 'type="date"' in date_tag
    assert "required" in date_tag
    assert 'maxlength="200"' in description_tag


def test_cancel_link_points_to_profile(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    assert re.search(r'<a\b[^>]*href="/profile"[^>]*>\s*Cancel\s*</a>', html, flags=re.I)


def test_edit_page_links_add_expense_stylesheet(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    assert "css/add_expense.css" in html


def test_form_does_not_expose_user_id_field(client, own_expense):
    html = client.get(f"/expenses/{own_expense}/edit").get_data(as_text=True)

    assert 'name="user_id"' not in html


def test_get_does_not_modify_expense(client, own_expense):
    before = _expense_row(own_expense)

    client.get(f"/expenses/{own_expense}/edit")

    assert _expense_row(own_expense) == before


# --- POST success ----------------------------------------------------------


def test_valid_post_updates_all_fields_and_redirects(client, own_expense):
    response = client.post(f"/expenses/{own_expense}/edit", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    row = _expense_row(own_expense)
    assert row["amount"] == 250.0
    assert row["category"] == "Shopping"
    assert row["date"] == "2026-02-20"
    assert row["description"] == "Fancy jacket"


def test_valid_post_flashes_success(client, own_expense):
    client.post(f"/expenses/{own_expense}/edit", data=_form())

    assert ("success", "Expense updated.") in _flashes(client)


def test_success_flash_is_shown_on_profile(client, own_expense):
    response = client.post(f"/expenses/{own_expense}/edit", data=_form(), follow_redirects=True)

    assert response.status_code == 200
    assert response.request.path == "/profile"
    assert "Expense updated." in response.get_data(as_text=True)


def test_edit_keeps_user_id_and_created_at(client, logged_in, own_expense):
    client.post(f"/expenses/{own_expense}/edit", data=_form())

    row = _expense_row(own_expense)
    assert row["user_id"] == logged_in
    assert row["created_at"] == FIXED_CREATED_AT


@pytest.mark.parametrize("description", [None, "", "   "])
def test_clearing_description_stores_null(client, own_expense, description):
    response = client.post(
        f"/expenses/{own_expense}/edit", data=_form(description=description)
    )

    assert response.status_code == 302
    assert _expense_row(own_expense)["description"] is None


def test_description_is_stripped(client, own_expense):
    client.post(f"/expenses/{own_expense}/edit", data=_form(description="  Coffee  "))

    assert _expense_row(own_expense)["description"] == "Coffee"


def test_amount_is_rounded_to_two_decimals(client, own_expense):
    client.post(f"/expenses/{own_expense}/edit", data=_form(amount="12.3456"))

    assert _expense_row(own_expense)["amount"] == 12.35


def test_description_of_exactly_200_chars_is_accepted(client, own_expense):
    response = client.post(f"/expenses/{own_expense}/edit", data=_form(description="x" * 200))

    assert response.status_code == 302
    assert _expense_row(own_expense)["description"] == "x" * 200


def test_saving_unchanged_values_succeeds(client, own_expense):
    data = {"amount": "42.50", "category": "Food", "date": "2026-01-15", "description": "Lunch"}

    response = client.post(f"/expenses/{own_expense}/edit", data=data)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    row = _expense_row(own_expense)
    assert row["amount"] == 42.5
    assert row["description"] == "Lunch"


def test_edit_leaves_other_expenses_untouched(client, logged_in, other_user, own_expense):
    keep_id = db.insert_expense(logged_in, 10.0, "Bills", "2026-01-14", "Internet")
    theirs_id = db.insert_expense(other_user, 30.0, "Food", "2026-01-15", "Their dinner")
    keep_before = _expense_row(keep_id)
    theirs_before = _expense_row(theirs_id)

    client.post(f"/expenses/{own_expense}/edit", data=_form())

    assert _expense_row(keep_id) == keep_before
    assert _expense_row(theirs_id) == theirs_before


def test_profile_reflects_edit(client, logged_in):
    db.insert_expense(logged_in, 50.0, "Food", "2026-01-14", "Snacks")
    edit_id = db.insert_expense(logged_in, 100.0, "Food", "2026-01-15", "Groceries run")
    before = client.get("/profile").get_data(as_text=True)
    assert "Groceries run" in before
    assert "₹150.00" in before

    client.post(f"/expenses/{edit_id}/edit", data=_form())
    html = client.get("/profile").get_data(as_text=True)

    assert "Fancy jacket" in html
    assert "Groceries run" not in html
    assert "Snacks" in html
    assert "₹300.00" in html
    assert "₹250.00" in html
    assert "₹150.00" not in html
    assert "₹100.00" not in html
    assert "Shopping" in html


def test_summary_helpers_reflect_edit(client, logged_in):
    db.insert_expense(logged_in, 50.0, "Food", "2026-01-14", "Snacks")
    edit_id = db.insert_expense(logged_in, 100.0, "Food", "2026-01-15", "Groceries run")

    client.post(f"/expenses/{edit_id}/edit", data=_form())

    summary = db.get_expense_summary(logged_in)
    assert summary["total_spent"] == 300.0
    assert summary["transaction_count"] == 2
    totals = {row["category"]: row["total"] for row in db.get_category_totals(logged_in)}
    assert totals == {"Food": 50.0, "Shopping": 250.0}


# --- POST validation errors ------------------------------------------------


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"amount": None}, AMOUNT_ERROR),
        ({"amount": ""}, AMOUNT_ERROR),
        ({"amount": "0"}, AMOUNT_ERROR),
        ({"amount": "0.00"}, AMOUNT_ERROR),
        ({"amount": "-5"}, AMOUNT_ERROR),
        ({"amount": "abc"}, AMOUNT_ERROR),
        ({"amount": "inf"}, AMOUNT_ERROR),
        ({"amount": "-inf"}, AMOUNT_ERROR),
        ({"amount": "Infinity"}, AMOUNT_ERROR),
        ({"amount": "nan"}, AMOUNT_ERROR),
        ({"category": None}, CATEGORY_ERROR),
        ({"category": ""}, CATEGORY_ERROR),
        ({"category": "Groceries"}, CATEGORY_ERROR),
        ({"category": "food"}, CATEGORY_ERROR),
        ({"date": None}, DATE_ERROR),
        ({"date": ""}, DATE_ERROR),
        ({"date": "not-a-date"}, DATE_ERROR),
        ({"date": "2026-02-30"}, DATE_ERROR),
        ({"date": "2026/03/20"}, DATE_ERROR),
        ({"description": "x" * 201}, DESCRIPTION_ERROR),
    ],
)
def test_invalid_post_rerenders_with_error_and_changes_nothing(
    client, own_expense, overrides, message
):
    before = _expense_row(own_expense)

    response = client.post(f"/expenses/{own_expense}/edit", data=_form(**overrides))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Save Changes" in html
    assert message in html
    assert "Expense updated." not in html
    assert _expense_row(own_expense) == before


def test_only_first_failing_check_is_shown(client, own_expense):
    data = _form(amount="-5", category="Groceries", date="not-a-date", description="x" * 201)

    html = client.post(f"/expenses/{own_expense}/edit", data=data).get_data(as_text=True)

    assert AMOUNT_ERROR in html
    assert CATEGORY_ERROR not in html
    assert DATE_ERROR not in html
    assert DESCRIPTION_ERROR not in html


def test_invalid_post_does_not_flash_success(client, own_expense):
    client.post(f"/expenses/{own_expense}/edit", data=_form(amount="0"))

    assert ("success", "Expense updated.") not in _flashes(client)


# --- value retention after errors ------------------------------------------


@pytest.mark.parametrize("amount", ["0", "-5", "abc", "inf"])
def test_bad_amount_keeps_submitted_values(client, own_expense, amount):
    data = _form(amount=amount, category="Transport", date="2026-03-21", description="Retained note")

    html = client.post(f"/expenses/{own_expense}/edit", data=data).get_data(as_text=True)

    assert f'value="{amount}"' in _input_tag(html, "amount")
    assert 'value="2026-03-21"' in _input_tag(html, "date")
    assert 'value="Retained note"' in _input_tag(html, "description")
    assert _selected_labels(html) == ["Transport"]


def test_bad_category_keeps_submitted_values(client, own_expense):
    data = _form(amount="77.70", category="Groceries", date="2026-03-21", description="Retained note")

    html = client.post(f"/expenses/{own_expense}/edit", data=data).get_data(as_text=True)

    assert 'value="77.70"' in _input_tag(html, "amount")
    assert 'value="2026-03-21"' in _input_tag(html, "date")
    assert 'value="Retained note"' in _input_tag(html, "description")
    assert "Food" not in _selected_labels(html)


def test_bad_date_keeps_submitted_values(client, own_expense):
    data = _form(amount="77.70", category="Health", date="not-a-date", description="Retained note")

    html = client.post(f"/expenses/{own_expense}/edit", data=data).get_data(as_text=True)

    assert 'value="77.70"' in _input_tag(html, "amount")
    assert 'value="Retained note"' in _input_tag(html, "description")
    assert _selected_labels(html) == ["Health"]


def test_long_description_keeps_submitted_values(client, own_expense):
    long_text = "y" * 201
    data = _form(amount="12.34", category="Health", date="2026-03-21", description=long_text)

    html = client.post(f"/expenses/{own_expense}/edit", data=data).get_data(as_text=True)

    assert 'value="12.34"' in _input_tag(html, "amount")
    assert 'value="2026-03-21"' in _input_tag(html, "date")
    assert long_text in html
    assert _selected_labels(html) == ["Health"]


def test_invalid_post_form_still_posts_to_edit_url(client, own_expense):
    html = client.post(
        f"/expenses/{own_expense}/edit", data=_form(amount="0")
    ).get_data(as_text=True)

    assert re.search(
        rf'<form\b[^>]*action="/expenses/{own_expense}/edit"', html, flags=re.I
    )


# --- ownership and missing ids ---------------------------------------------


def test_get_other_users_expense_returns_404(client, logged_in, other_user):
    expense_id = db.insert_expense(other_user, 999.0, "Shopping", "2026-01-15", "Secret purchase")

    response = client.get(f"/expenses/{expense_id}/edit")

    assert response.status_code == 404
    assert "Secret purchase" not in response.get_data(as_text=True)


@pytest.mark.parametrize(
    "data",
    [
        VALID_EDIT,
        {**VALID_EDIT, "amount": "-5"},
        {**VALID_EDIT, "category": "Groceries"},
        {},
    ],
)
def test_post_other_users_expense_returns_404_and_changes_nothing(
    client, logged_in, other_user, data
):
    expense_id = db.insert_expense(other_user, 999.0, "Shopping", "2026-01-15", "Secret purchase")
    before = _expense_row(expense_id)

    response = client.post(f"/expenses/{expense_id}/edit", data=data)

    assert response.status_code == 404
    assert "Secret purchase" not in response.get_data(as_text=True)
    assert _expense_row(expense_id) == before


@pytest.mark.parametrize("method", ["get", "post"])
def test_nonexistent_id_returns_404(client, own_expense, method):
    before = _expense_row(own_expense)

    response = getattr(client, method)("/expenses/9999/edit", data=_form())

    assert response.status_code == 404
    assert _expense_row(own_expense) == before


@pytest.mark.parametrize("method", ["get", "post"])
def test_missing_and_foreign_404s_look_the_same(client, logged_in, other_user, method):
    foreign_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")

    foreign = getattr(client, method)(f"/expenses/{foreign_id}/edit", data=_form())
    missing = getattr(client, method)("/expenses/9999/edit", data=_form())

    assert foreign.status_code == missing.status_code == 404
    assert foreign.get_data(as_text=True) == missing.get_data(as_text=True)


def test_non_integer_id_returns_404(client, logged_in):
    response = client.get("/expenses/abc/edit")

    assert response.status_code == 404


def test_edit_after_delete_returns_404(client, own_expense):
    db.delete_expense_for_user(own_expense, _expense_row(own_expense)["user_id"])

    get_response = client.get(f"/expenses/{own_expense}/edit")
    post_response = client.post(f"/expenses/{own_expense}/edit", data=_form())

    assert get_response.status_code == 404
    assert post_response.status_code == 404


def test_forged_user_id_cannot_move_own_expense(client, logged_in, other_user, own_expense):
    response = client.post(
        f"/expenses/{own_expense}/edit", data=_form(user_id=str(other_user))
    )

    assert response.status_code == 302
    row = _expense_row(own_expense)
    assert row["user_id"] == logged_in
    assert row["description"] == "Fancy jacket"


def test_forged_user_id_cannot_edit_other_users_expense(client, logged_in, other_user):
    expense_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")
    before = _expense_row(expense_id)

    response = client.post(
        f"/expenses/{expense_id}/edit", data=_form(user_id=str(other_user))
    )

    assert response.status_code == 404
    assert _expense_row(expense_id) == before


# --- profile Edit links ----------------------------------------------------


def test_profile_rows_have_edit_links(client, logged_in):
    ids = [
        db.insert_expense(logged_in, 10.0, "Food", "2026-01-13", "First"),
        db.insert_expense(logged_in, 20.0, "Bills", "2026-01-14", "Second"),
        db.insert_expense(logged_in, 30.0, "Other", "2026-01-15", "Third"),
    ]

    html = client.get("/profile").get_data(as_text=True)

    for expense_id in ids:
        assert re.search(
            rf'<a\b[^>]*href="/expenses/{expense_id}/edit"[^>]*>\s*Edit\s*</a>', html
        ), expense_id


def test_profile_edit_link_comes_before_delete_link(client, logged_in):
    ids = [
        db.insert_expense(logged_in, 10.0, "Food", "2026-01-13", "First"),
        db.insert_expense(logged_in, 20.0, "Bills", "2026-01-14", "Second"),
    ]

    html = client.get("/profile").get_data(as_text=True)

    for expense_id in ids:
        edit_pos = html.find(f'href="/expenses/{expense_id}/edit"')
        delete_pos = html.find(f'href="/expenses/{expense_id}/delete"')
        assert edit_pos != -1 and delete_pos != -1, expense_id
        assert edit_pos < delete_pos, expense_id


def test_profile_has_no_edit_links_for_other_users(client, logged_in, other_user):
    db.insert_expense(logged_in, 10.0, "Food", "2026-01-15", "Mine")
    theirs_id = db.insert_expense(other_user, 5.0, "Food", "2026-01-15", "Theirs")

    html = client.get("/profile").get_data(as_text=True)

    assert f"/expenses/{theirs_id}/edit" not in html


def test_edit_link_opens_prefilled_form(client, logged_in):
    expense_id = db.insert_expense(logged_in, 64.0, "Entertainment", "2026-01-15", "Cinema")
    profile = client.get("/profile").get_data(as_text=True)
    assert f'href="/expenses/{expense_id}/edit"' in profile

    html = client.get(f"/expenses/{expense_id}/edit").get_data(as_text=True)

    assert 'value="64.00"' in _input_tag(html, "amount")
    assert 'value="Cinema"' in _input_tag(html, "description")
    assert _selected_labels(html) == ["Entertainment"]
