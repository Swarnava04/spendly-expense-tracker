import re
from datetime import date

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

VALID_FORM = {
    "amount": "50.0",
    "category": "Food",
    "date": "2026-03-20",
    "description": "Lunch",
}


def _form(**overrides):
    data = dict(VALID_FORM)
    for key, value in overrides.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return data


def _all_expenses():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT user_id, amount, category, date, description FROM expenses ORDER BY id"
        ).fetchall()
    finally:
        conn.close()


def _expenses_for(user_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT user_id, amount, category, date, description FROM expenses "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
    finally:
        conn.close()


def _option_tags(html):
    return re.findall(r"<option\b[^>]*>.*?</option>", html, flags=re.S | re.I)


def _shows_error(clean_html, error_html):
    # The spec does not fix the error wording, so look for any rendered text line
    # that the clean form lacks, ignoring lines that only differ by retained values.
    clean_lines = {line.strip() for line in clean_html.splitlines()}
    new_lines = [
        line.strip()
        for line in error_html.splitlines()
        if line.strip()
        and line.strip() not in clean_lines
        and "value=" not in line
        and "selected" not in line
        and "<option" not in line
    ]
    return bool(new_lines)


@pytest.fixture
def logged_in(make_user, login):
    user_id = make_user()
    login()
    return user_id


# --- insert_expense helper -------------------------------------------------


def test_insert_expense_creates_row(app, make_user):
    user_id = make_user()

    new_id = db.insert_expense(user_id, 50.0, "Food", "2026-03-20", "Lunch")

    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT user_id, amount, category, date, description FROM expenses WHERE id = ?",
            (new_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert row["user_id"] == user_id
    assert row["amount"] == 50.0
    assert row["category"] == "Food"
    assert row["date"] == "2026-03-20"
    assert row["description"] == "Lunch"


def test_insert_expense_stores_null_description(app, make_user):
    user_id = make_user()

    db.insert_expense(user_id, 12.5, "Other", "2026-03-20", None)

    rows = _expenses_for(user_id)
    assert len(rows) == 1
    assert rows[0]["description"] is None


def test_insert_expense_returns_distinct_ids(app, make_user):
    user_id = make_user()

    first = db.insert_expense(user_id, 1.0, "Food", "2026-01-15", None)
    second = db.insert_expense(user_id, 2.0, "Food", "2026-01-15", None)

    assert isinstance(first, int)
    assert isinstance(second, int)
    assert first != second


def test_categories_constant_matches_spec(app):
    assert db.CATEGORIES == EXPECTED_CATEGORIES


# --- auth guards -----------------------------------------------------------


def test_guest_get_redirects_to_login(client):
    response = client.get("/expenses/add")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_guest_post_redirects_to_login_and_inserts_nothing(client):
    response = client.post("/expenses/add", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert _all_expenses() == []


@pytest.mark.parametrize("method", ["get", "post"])
def test_stale_session_is_cleared_and_redirected(client, method):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999

    response = getattr(client, method)("/expenses/add", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
    assert _all_expenses() == []


# --- GET form --------------------------------------------------------------


def test_get_renders_form(client, logged_in):
    response = client.get("/expenses/add")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert re.search(r"<form\b[^>]*method=\"post\"", html, flags=re.I)
    assert re.search(r"<form\b[^>]*action=\"/expenses/add\"", html, flags=re.I)
    assert "Save Expense" in html


@pytest.mark.parametrize("field", ["amount", "category", "date", "description"])
def test_get_form_has_field(client, logged_in, field):
    html = client.get("/expenses/add").get_data(as_text=True)

    assert f'name="{field}"' in html


def test_amount_input_attributes(client, logged_in):
    html = client.get("/expenses/add").get_data(as_text=True)

    tag = re.search(r"<input\b[^>]*name=\"amount\"[^>]*>", html, flags=re.S)
    assert tag
    assert 'type="number"' in tag.group(0)
    assert 'step="0.01"' in tag.group(0)
    assert 'min="0.01"' in tag.group(0)
    assert "required" in tag.group(0)


def test_date_input_is_date_type_defaulting_to_today(client, logged_in):
    html = client.get("/expenses/add").get_data(as_text=True)

    tag = re.search(r"<input\b[^>]*name=\"date\"[^>]*>", html, flags=re.S)
    assert tag
    assert 'type="date"' in tag.group(0)
    assert "required" in tag.group(0)
    assert f'value="{date.today().isoformat()}"' in tag.group(0)


def test_category_dropdown_has_exactly_the_seven_categories(client, logged_in):
    html = client.get("/expenses/add").get_data(as_text=True)

    select = re.search(r"<select\b[^>]*name=\"category\"[^>]*>(.*?)</select>", html, flags=re.S)
    assert select
    options = _option_tags(select.group(1))
    labels = [re.sub(r"<[^>]+>", "", opt).strip() for opt in options]
    real_labels = [label for label in labels if label in EXPECTED_CATEGORIES]
    assert real_labels == EXPECTED_CATEGORIES
    for opt, label in zip(options, labels):
        if label not in EXPECTED_CATEGORIES:
            # Only an empty placeholder option is acceptable besides the seven
            assert 'value=""' in opt, f"unexpected category option: {opt}"


def test_cancel_link_points_to_profile(client, logged_in):
    html = client.get("/expenses/add").get_data(as_text=True)

    assert 'href="/profile"' in html


def test_form_does_not_expose_user_id_field(client, logged_in):
    html = client.get("/expenses/add").get_data(as_text=True)

    assert 'name="user_id"' not in html


# --- POST success ----------------------------------------------------------


def test_valid_post_redirects_to_profile_and_inserts_row(client, logged_in):
    response = client.post("/expenses/add", data=_form())

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["amount"] == 50.0
    assert rows[0]["category"] == "Food"
    assert rows[0]["date"] == "2026-03-20"
    assert rows[0]["description"] == "Lunch"


def test_valid_post_flashes_success(client, logged_in):
    client.post("/expenses/add", data=_form())

    with client.session_transaction() as sess:
        flashes = sess.get("_flashes", [])
    assert ("success", "Expense added.") in flashes


def test_new_expense_appears_on_profile(client, logged_in):
    response = client.post(
        "/expenses/add",
        data=_form(description="Unique dosa lunch"),
        follow_redirects=True,
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.request.path == "/profile"
    assert "Expense added." in html
    assert "Unique dosa lunch" in html
    assert "₹50.00" in html


def test_expense_is_saved_for_session_user_not_form_user_id(client, make_user, login):
    other = make_user(name="Other", email="other@example.com")
    me = make_user(name="Me", email="me@example.com")
    login(email="me@example.com")

    client.post("/expenses/add", data=_form(user_id=str(other)))

    assert len(_expenses_for(me)) == 1
    assert _expenses_for(other) == []


def test_amount_is_rounded_to_two_decimals(client, logged_in):
    client.post("/expenses/add", data=_form(amount="12.3456"))

    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["amount"] == 12.35


@pytest.mark.parametrize("category", EXPECTED_CATEGORIES)
def test_every_category_is_accepted(client, logged_in, category):
    response = client.post("/expenses/add", data=_form(category=category))

    assert response.status_code == 302
    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["category"] == category


@pytest.mark.parametrize("description", [None, "", "   "])
def test_blank_description_saves_null(client, logged_in, description):
    response = client.post("/expenses/add", data=_form(description=description))

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")
    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["description"] is None


def test_description_is_stripped(client, logged_in):
    client.post("/expenses/add", data=_form(description="  Coffee  "))

    rows = _expenses_for(logged_in)
    assert rows[0]["description"] == "Coffee"


def test_description_of_exactly_200_chars_is_accepted(client, logged_in):
    response = client.post("/expenses/add", data=_form(description="x" * 200))

    assert response.status_code == 302
    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["description"] == "x" * 200


def test_sql_injection_in_description_is_stored_literally(client, logged_in):
    payload = "'); DROP TABLE expenses; --"

    response = client.post("/expenses/add", data=_form(description=payload))

    assert response.status_code == 302
    rows = _expenses_for(logged_in)
    assert len(rows) == 1
    assert rows[0]["description"] == payload


def test_smallest_valid_amount_is_accepted(client, logged_in):
    response = client.post("/expenses/add", data=_form(amount="0.01"))

    assert response.status_code == 302
    assert _expenses_for(logged_in)[0]["amount"] == 0.01


# --- POST validation errors ------------------------------------------------


@pytest.mark.parametrize(
    "amount",
    [None, "", "0", "0.00", "-5", "abc", "inf", "-inf", "nan", "Infinity"],
)
def test_invalid_amount_rerenders_form_with_error(client, logged_in, amount):
    clean_html = client.get("/expenses/add").get_data(as_text=True)

    response = client.post("/expenses/add", data=_form(amount=amount))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Save Expense" in html
    assert _shows_error(clean_html, html)
    assert _all_expenses() == []


@pytest.mark.parametrize(
    "category",
    [None, "", "Groceries", "food", "FOOD", "Food'; DROP TABLE expenses; --"],
)
def test_invalid_category_rerenders_form_with_error(client, logged_in, category):
    clean_html = client.get("/expenses/add").get_data(as_text=True)

    response = client.post("/expenses/add", data=_form(category=category))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Save Expense" in html
    assert _shows_error(clean_html, html)
    assert _all_expenses() == []


@pytest.mark.parametrize(
    "date_value",
    [None, "", "not-a-date", "2026-13-01", "2026-02-30", "20-03-2026", "2026/03/20"],
)
def test_invalid_date_rerenders_form_with_error(client, logged_in, date_value):
    clean_html = client.get("/expenses/add").get_data(as_text=True)

    response = client.post("/expenses/add", data=_form(date=date_value))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Save Expense" in html
    assert _shows_error(clean_html, html)
    assert _all_expenses() == []


def test_description_over_200_chars_rerenders_form_with_error(client, logged_in):
    clean_html = client.get("/expenses/add").get_data(as_text=True)

    response = client.post("/expenses/add", data=_form(description="x" * 201))
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Save Expense" in html
    assert _shows_error(clean_html, html)
    assert _all_expenses() == []


def test_error_does_not_flash_success(client, logged_in):
    response = client.post("/expenses/add", data=_form(amount="0"))

    assert "Expense added." not in response.get_data(as_text=True)


# --- value retention after errors ------------------------------------------


@pytest.mark.parametrize("amount", ["0", "-5", "abc", "inf"])
def test_bad_amount_keeps_other_values(client, logged_in, amount):
    data = _form(
        amount=amount,
        category="Transport",
        date="2026-03-21",
        description="Retained note",
    )

    html = client.post("/expenses/add", data=data).get_data(as_text=True)

    assert 'value="2026-03-21"' in html
    assert "Retained note" in html
    transport = [opt for opt in _option_tags(html) if "Transport" in opt]
    assert transport and "selected" in transport[0]


@pytest.mark.parametrize("amount", ["-5", "abc"])
def test_bad_amount_value_is_retained(client, logged_in, amount):
    html = client.post("/expenses/add", data=_form(amount=amount)).get_data(as_text=True)

    tag = re.search(r"<input\b[^>]*name=\"amount\"[^>]*>", html, flags=re.S)
    assert tag
    assert f'value="{amount}"' in tag.group(0)


def test_long_description_keeps_amount_and_category(client, logged_in):
    data = _form(amount="12.34", category="Health", description="y" * 201)

    html = client.post("/expenses/add", data=data).get_data(as_text=True)

    tag = re.search(r"<input\b[^>]*name=\"amount\"[^>]*>", html, flags=re.S)
    assert tag and 'value="12.34"' in tag.group(0)
    health = [opt for opt in _option_tags(html) if "Health" in opt]
    assert health and "selected" in health[0]


def test_invalid_date_keeps_amount_and_description(client, logged_in):
    data = _form(amount="77.70", date="not-a-date", description="Keep me")

    html = client.post("/expenses/add", data=data).get_data(as_text=True)

    tag = re.search(r"<input\b[^>]*name=\"amount\"[^>]*>", html, flags=re.S)
    assert tag and 'value="77.70"' in tag.group(0)
    assert "Keep me" in html


# --- navigation links ------------------------------------------------------


def test_profile_has_add_expense_button(client, logged_in):
    html = client.get("/profile").get_data(as_text=True)

    # one link from the navbar, one from the profile page button
    assert html.count('href="/expenses/add"') >= 2
    assert "Add Expense" in html


def test_navbar_shows_add_expense_when_logged_in(client, logged_in):
    html = client.get("/terms").get_data(as_text=True)

    assert 'href="/expenses/add"' in html
    assert "Add Expense" in html


def test_navbar_hides_add_expense_when_logged_out(client):
    for path in ("/terms", "/login"):
        html = client.get(path).get_data(as_text=True)
        assert 'href="/expenses/add"' not in html, path
        assert "Add Expense" not in html, path
