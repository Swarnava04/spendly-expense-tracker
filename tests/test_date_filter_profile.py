import calendar
from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

import database.db as db

FLASH_MSG = "Start date must be before end date."
PRESETS = ["This Month", "Last 3 Months", "Last 6 Months", "All Time"]


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []
        self.inputs = []
        self._open = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self._open.append({"attrs": attrs, "text": ""})
        elif tag == "input":
            self.inputs.append(attrs)

    def handle_data(self, data):
        for anchor in self._open:
            anchor["text"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._open:
            anchor = self._open.pop()
            anchor["text"] = " ".join(anchor["text"].split())
            self.anchors.append(anchor)


def _parse(html):
    parser = _PageParser()
    parser.feed(html)
    return parser


def _preset_anchors(html):
    anchors = _parse(html).anchors
    found = {}
    for label in PRESETS:
        matches = [a for a in anchors if a["text"] == label]
        assert len(matches) == 1, f"expected one '{label}' link, found {len(matches)}"
        found[label] = matches[0]["attrs"]
    return found


def _href_parts(attrs):
    parts = urlsplit(attrs.get("href", ""))
    return parts.path, parse_qs(parts.query, keep_blank_values=True)


def _highlight_signature(attrs):
    classes = frozenset((attrs.get("class") or "").split())
    return classes, attrs.get("aria-current")


def _highlighted_presets(html):
    signatures = {label: _highlight_signature(a) for label, a in _preset_anchors(html).items()}
    distinct = [
        label for label, sig in signatures.items()
        if list(signatures.values()).count(sig) == 1
    ]
    return distinct, signatures


def _date_input_value(html, name):
    matches = [i for i in _parse(html).inputs if i.get("name") == name]
    assert len(matches) == 1, f"expected one input named {name}"
    assert matches[0].get("type") == "date"
    return matches[0].get("value") or ""


def _months_ago(today, n):
    month_index = today.year * 12 + (today.month - 1) - n
    year, month = divmod(month_index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _this_month_range(today):
    first = today.replace(day=1)
    last = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return first, last


@pytest.fixture
def user_with_spread(make_user, add_expense):
    user_id = make_user()
    add_expense(user_id, 40.00, "Shopping", "2025-12-31", "Before range")
    add_expense(user_id, 100.00, "Food", "2026-01-10", "Start boundary")
    add_expense(user_id, 200.00, "Bills", "2026-01-20", "Mid range")
    add_expense(user_id, 0.00, "Food", "2026-01-31", "End boundary")
    add_expense(user_id, 50.00, "Travel", "2026-02-01", "After range")
    return user_id


# --- Auth ---------------------------------------------------------------


def test_guest_with_filter_params_is_redirected_to_login(client):
    response = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_stale_session_with_filter_params_is_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999

    response = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# --- Unfiltered view ----------------------------------------------------


def test_no_params_shows_all_expenses(client, user_with_spread, login):
    login()

    response = client.get("/profile")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹390.00" in html
    for desc in ["Before range", "Start boundary", "Mid range", "End boundary", "After range"]:
        assert desc in html, desc
    assert FLASH_MSG not in html


def test_no_params_category_breakdown_covers_all_expenses(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 100.00, "Food", "2025-03-01")
    add_expense(user_id, 200.00, "Bills", "2026-06-01")
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert "₹300.00" in html
    assert "width: 66.7%" in html
    assert "width: 33.3%" in html


# --- Custom range -------------------------------------------------------


def test_custom_range_filters_total(client, user_with_spread, login):
    login()

    response = client.get("/profile?date_from=2026-01-10&date_to=2026-01-31")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹300.00" in html
    assert "₹390.00" not in html


def test_custom_range_filters_transactions_table(client, user_with_spread, login):
    login()

    html = client.get("/profile?date_from=2026-01-10&date_to=2026-01-31").get_data(as_text=True)

    assert "Start boundary" in html
    assert "Mid range" in html
    assert "End boundary" in html
    assert "Before range" not in html
    assert "After range" not in html


def test_custom_range_filters_category_breakdown(client, user_with_spread, login):
    login()

    html = client.get("/profile?date_from=2026-01-10&date_to=2026-01-31").get_data(as_text=True)

    assert "Shopping" not in html
    assert "Travel" not in html
    assert "₹40.00" not in html
    assert "₹50.00" not in html
    assert "width: 66.7%" in html  # Bills 200 / filtered total 300
    assert "width: 33.3%" in html  # Food 100 / filtered total 300
    assert html.index("Bills") < html.index("Food")


def test_custom_range_boundaries_are_inclusive(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 1.00, "Other", "2026-03-09", "Day before")
    add_expense(user_id, 2.00, "Other", "2026-03-10", "First day")
    add_expense(user_id, 4.00, "Other", "2026-03-20", "Last day")
    add_expense(user_id, 8.00, "Other", "2026-03-21", "Day after")
    login()

    html = client.get("/profile?date_from=2026-03-10&date_to=2026-03-20").get_data(as_text=True)

    assert "First day" in html
    assert "Last day" in html
    assert "Day before" not in html
    assert "Day after" not in html
    assert "₹6.00" in html


def test_single_day_range(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 11.00, "Food", "2026-04-14", "Prior evening item")
    add_expense(user_id, 22.00, "Food", "2026-04-15", "Target lunch")
    add_expense(user_id, 33.00, "Food", "2026-04-15", "Target dinner")
    add_expense(user_id, 44.00, "Food", "2026-04-16", "Following morning item")
    login()

    response = client.get("/profile?date_from=2026-04-15&date_to=2026-04-15")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Target lunch" in html
    assert "Target dinner" in html
    assert "Prior evening item" not in html
    assert "Following morning item" not in html
    assert "₹55.00" in html
    assert FLASH_MSG not in html


def test_empty_range_shows_zero_state(client, user_with_spread, login):
    login()

    response = client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹0.00" in html
    assert "No spending yet." in html
    assert "No transactions yet." in html
    for desc in ["Before range", "Start boundary", "Mid range", "End boundary", "After range"]:
        assert desc not in html, desc


def test_filter_applies_to_custom_range_beyond_ten_transactions(client, make_user, login, add_expense):
    user_id = make_user()
    for day in range(1, 13):
        add_expense(user_id, day, "Other", f"2026-05-{day:02d}", f"Item {day:02d}")
    add_expense(user_id, 500.00, "Other", "2026-06-01", "June item")
    login()

    html = client.get("/profile?date_from=2026-05-01&date_to=2026-05-31").get_data(as_text=True)

    assert "June item" not in html
    assert "Item 12" in html
    assert "Item 01" not in html and "Item 02" not in html
    assert html.index("Item 12") < html.index("Item 03")
    assert "₹78.00" in html


def test_users_do_not_see_each_others_expenses_under_filter(client, make_user, login, add_expense):
    alice = make_user(name="Alice", email="alice@example.com")
    bob = make_user(name="Bob", email="bob@example.com")
    add_expense(alice, 999.00, "Shopping", "2026-01-15", "Alice secret purchase")
    add_expense(bob, 10.00, "Food", "2026-01-15", "Bob sandwich")
    login(email="bob@example.com")

    html = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").get_data(as_text=True)

    assert "Bob sandwich" in html
    assert "Alice secret purchase" not in html
    assert "₹999.00" not in html


# --- Fallbacks ----------------------------------------------------------


@pytest.mark.parametrize("query", [
    "date_from=2026-01-10",
    "date_to=2026-01-31",
    "date_from=2026-01-10&date_to=",
    "date_from=&date_to=2026-01-31",
    "date_from=&date_to=",
])
def test_single_bound_shows_unfiltered_view_without_error(client, user_with_spread, login, query):
    login()

    response = client.get(f"/profile?{query}")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "₹390.00" in html
    assert "Before range" in html
    assert "After range" in html
    assert FLASH_MSG not in html


@pytest.mark.parametrize("bad", [
    "not-a-date",
    "2026-13-01",
    "2026-02-30",
    "2026/01/10",
    "10-01-2026",
    "2026-01-10' OR '1'='1",
])
def test_malformed_date_falls_back_silently(client, user_with_spread, login, bad):
    login()

    for query in [
        {"date_from": bad, "date_to": "2026-01-31"},
        {"date_from": "2026-01-10", "date_to": bad},
    ]:
        response = client.get("/profile", query_string=query)
        html = response.get_data(as_text=True)

        assert response.status_code == 200, query
        assert "₹390.00" in html, query
        assert "Before range" in html, query
        assert "After range" in html, query
        assert FLASH_MSG not in html, query


def test_malformed_date_is_not_echoed_into_inputs(client, user_with_spread, login):
    login()

    html = client.get(
        "/profile", query_string={"date_from": "not-a-date", "date_to": "2026-01-31"}
    ).get_data(as_text=True)

    assert "not-a-date" not in html


def test_reversed_range_flashes_error_and_shows_unfiltered(client, user_with_spread, login):
    login()

    response = client.get(
        "/profile?date_from=2026-01-31&date_to=2026-01-10", follow_redirects=True
    )
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert FLASH_MSG in html
    assert "₹390.00" in html
    assert "Before range" in html
    assert "After range" in html


def test_reversed_range_flash_uses_error_category(client, user_with_spread, login):
    login()

    with client:
        client.get("/profile?date_from=2026-01-31&date_to=2026-01-10")
        with client.session_transaction() as sess:
            pending = sess.get("_flashes", [])

    # the message is either consumed by the same render or still pending;
    # if pending, it must carry the "error" category
    for category, message in pending:
        if message == FLASH_MSG:
            assert category == "error"


# --- Presets ------------------------------------------------------------


def test_preset_links_are_rendered(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile").get_data(as_text=True)

    anchors = _preset_anchors(html)
    for label in PRESETS:
        path, _ = _href_parts(anchors[label])
        assert path == "/profile", label


def test_this_month_preset_link_covers_current_calendar_month(client, make_user, login):
    make_user()
    login()
    first, last = _this_month_range(date.today())

    html = client.get("/profile").get_data(as_text=True)

    path, query = _href_parts(_preset_anchors(html)["This Month"])
    assert path == "/profile"
    assert query == {"date_from": [first.isoformat()], "date_to": [last.isoformat()]}


@pytest.mark.parametrize("label,months", [("Last 3 Months", 3), ("Last 6 Months", 6)])
def test_last_n_months_preset_link(client, make_user, login, label, months):
    make_user()
    login()
    today = date.today()

    html = client.get("/profile").get_data(as_text=True)

    path, query = _href_parts(_preset_anchors(html)[label])
    assert path == "/profile"
    assert query == {
        "date_from": [_months_ago(today, months).isoformat()],
        "date_to": [today.isoformat()],
    }


def test_all_time_preset_link_has_no_query_params(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").get_data(as_text=True)

    href = _preset_anchors(html)["All Time"].get("href", "")
    assert urlsplit(href).path == "/profile"
    assert urlsplit(href).query == ""
    assert "?" not in href


def test_this_month_preset_filters_to_current_month(client, make_user, login, add_expense):
    user_id = make_user()
    first, last = _this_month_range(date.today())
    add_expense(user_id, 1.00, "Food", (first - timedelta(days=1)).isoformat(), "Last month item")
    add_expense(user_id, 2.00, "Food", first.isoformat(), "First of month item")
    add_expense(user_id, 4.00, "Food", last.isoformat(), "End of month item")
    add_expense(user_id, 8.00, "Food", (last + timedelta(days=1)).isoformat(), "Next month item")
    login()

    html = client.get(f"/profile?date_from={first}&date_to={last}").get_data(as_text=True)

    assert "First of month item" in html
    assert "End of month item" in html
    assert "Last month item" not in html
    assert "Next month item" not in html
    assert "₹6.00" in html


@pytest.mark.parametrize("months", [3, 6])
def test_last_n_months_preset_filters_window(client, make_user, login, add_expense, months):
    user_id = make_user()
    today = date.today()
    start = _months_ago(today, months)
    add_expense(user_id, 1.00, "Food", (start - timedelta(days=1)).isoformat(), "Too old item")
    add_expense(user_id, 2.00, "Food", start.isoformat(), "Window start item")
    add_expense(user_id, 4.00, "Food", today.isoformat(), "Today item")
    add_expense(user_id, 8.00, "Food", (today + timedelta(days=1)).isoformat(), "Tomorrow item")
    login()

    html = client.get(f"/profile?date_from={start}&date_to={today}").get_data(as_text=True)

    assert "Window start item" in html
    assert "Today item" in html
    assert "Too old item" not in html
    assert "Tomorrow item" not in html
    assert "₹6.00" in html


def test_following_this_month_link_filters_view(client, make_user, login, add_expense):
    user_id = make_user()
    first, _ = _this_month_range(date.today())
    add_expense(user_id, 7.00, "Food", first.isoformat(), "Current month item")
    add_expense(user_id, 9.00, "Food", (first - timedelta(days=1)).isoformat(), "Previous month item")
    login()
    href = _preset_anchors(client.get("/profile").get_data(as_text=True))["This Month"]["href"]

    html = client.get(href).get_data(as_text=True)

    assert "Current month item" in html
    assert "Previous month item" not in html


def test_following_all_time_link_shows_everything(client, user_with_spread, login):
    login()
    filtered = client.get("/profile?date_from=2026-01-10&date_to=2026-01-31").get_data(as_text=True)
    href = _preset_anchors(filtered)["All Time"]["href"]

    html = client.get(href).get_data(as_text=True)

    assert "₹390.00" in html
    assert "Before range" in html
    assert "After range" in html


# --- Active state -------------------------------------------------------


def test_this_month_preset_is_highlighted_when_active(client, make_user, login):
    make_user()
    login()
    first, last = _this_month_range(date.today())

    html = client.get(f"/profile?date_from={first}&date_to={last}").get_data(as_text=True)

    highlighted, _ = _highlighted_presets(html)
    assert highlighted == ["This Month"]


@pytest.mark.parametrize("label,months", [("Last 3 Months", 3), ("Last 6 Months", 6)])
def test_last_n_months_preset_is_highlighted_when_active(client, make_user, login, label, months):
    make_user()
    login()
    today = date.today()
    start = _months_ago(today, months)

    html = client.get(f"/profile?date_from={start}&date_to={today}").get_data(as_text=True)

    highlighted, _ = _highlighted_presets(html)
    assert highlighted == [label]


def test_all_time_preset_is_highlighted_without_filter(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile").get_data(as_text=True)

    highlighted, _ = _highlighted_presets(html)
    assert highlighted == ["All Time"]


def test_no_preset_highlighted_for_custom_range(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile?date_from=2020-02-03&date_to=2020-02-17").get_data(as_text=True)

    _, signatures = _highlighted_presets(html)
    assert len(set(signatures.values())) == 1


def test_date_inputs_prefilled_with_active_range(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile?date_from=2026-01-10&date_to=2026-01-31").get_data(as_text=True)

    assert _date_input_value(html, "date_from") == "2026-01-10"
    assert _date_input_value(html, "date_to") == "2026-01-31"


def test_date_inputs_empty_without_filter(client, make_user, login):
    make_user()
    login()

    html = client.get("/profile").get_data(as_text=True)

    assert _date_input_value(html, "date_from") == ""
    assert _date_input_value(html, "date_to") == ""


def test_rupee_symbol_shown_under_filter(client, make_user, login, add_expense):
    user_id = make_user()
    add_expense(user_id, 12.34, "Food", "2026-01-15", "Coffee")
    login()

    html = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31").get_data(as_text=True)

    assert "₹12.34" in html


# --- DB helpers ---------------------------------------------------------


def test_summary_helper_filters_by_range(app, user_with_spread):
    summary = db.get_expense_summary(user_with_spread, date_from="2026-01-10", date_to="2026-01-31")

    assert summary["total_spent"] == 300.0
    assert summary["transaction_count"] == 3


def test_summary_helper_unfiltered_without_dates(app, user_with_spread):
    summary = db.get_expense_summary(user_with_spread)

    assert summary["total_spent"] == 390.0
    assert summary["transaction_count"] == 5


def test_summary_helper_empty_range(app, user_with_spread):
    summary = db.get_expense_summary(user_with_spread, date_from="2030-01-01", date_to="2030-12-31")

    assert summary["total_spent"] == 0
    assert summary["transaction_count"] == 0


def test_summary_helper_single_day(app, user_with_spread):
    summary = db.get_expense_summary(user_with_spread, date_from="2026-01-20", date_to="2026-01-20")

    assert summary["total_spent"] == 200.0
    assert summary["transaction_count"] == 1


def test_category_totals_helper_filters_by_range(app, user_with_spread):
    rows = db.get_category_totals(user_with_spread, date_from="2026-01-10", date_to="2026-01-31")

    totals = [(row["category"], row["total"]) for row in rows]
    assert totals == [("Bills", 200.0), ("Food", 100.0)]


def test_category_totals_helper_unfiltered_without_dates(app, user_with_spread):
    rows = db.get_category_totals(user_with_spread)

    totals = [(row["category"], row["total"]) for row in rows]
    assert totals == [("Bills", 200.0), ("Food", 100.0), ("Travel", 50.0), ("Shopping", 40.0)]


def test_category_totals_helper_empty_range(app, user_with_spread):
    rows = db.get_category_totals(user_with_spread, date_from="2030-01-01", date_to="2030-12-31")

    assert list(rows) == []


def test_recent_expenses_helper_filters_by_range(app, user_with_spread):
    rows = db.get_recent_expenses(user_with_spread, date_from="2026-01-10", date_to="2026-01-31")

    assert [row["date"] for row in rows] == ["2026-01-31", "2026-01-20", "2026-01-10"]


def test_recent_expenses_helper_respects_limit_within_range(app, make_user, add_expense):
    user_id = make_user()
    for day in range(1, 13):
        add_expense(user_id, day, "Other", f"2026-05-{day:02d}")
    add_expense(user_id, 99.0, "Other", "2026-06-01")

    rows = db.get_recent_expenses(user_id, limit=5, date_from="2026-05-01", date_to="2026-05-31")

    assert [row["date"] for row in rows] == [f"2026-05-{d:02d}" for d in range(12, 7, -1)]


def test_recent_expenses_helper_default_limit_within_range(app, make_user, add_expense):
    user_id = make_user()
    for day in range(1, 13):
        add_expense(user_id, day, "Other", f"2026-05-{day:02d}")

    rows = db.get_recent_expenses(user_id, date_from="2026-05-01", date_to="2026-05-31")

    assert len(rows) == 10
    assert rows[0]["date"] == "2026-05-12"


def test_recent_expenses_helper_unfiltered_without_dates(app, user_with_spread):
    rows = db.get_recent_expenses(user_with_spread)

    assert [row["date"] for row in rows] == [
        "2026-02-01", "2026-01-31", "2026-01-20", "2026-01-10", "2025-12-31",
    ]


def test_recent_expenses_helper_positional_limit_still_works(app, user_with_spread):
    rows = db.get_recent_expenses(user_with_spread, 2)

    assert [row["date"] for row in rows] == ["2026-02-01", "2026-01-31"]


def test_recent_expenses_helper_empty_range(app, user_with_spread):
    rows = db.get_recent_expenses(user_with_spread, date_from="2030-01-01", date_to="2030-12-31")

    assert list(rows) == []


def test_helpers_isolate_users_under_filter(app, make_user, add_expense):
    alice = make_user(name="Alice", email="alice@example.com")
    bob = make_user(name="Bob", email="bob@example.com")
    add_expense(alice, 999.0, "Shopping", "2026-01-15")
    add_expense(bob, 10.0, "Food", "2026-01-15")

    summary = db.get_expense_summary(bob, date_from="2026-01-01", date_to="2026-01-31")
    totals = [(r["category"], r["total"]) for r in db.get_category_totals(bob, date_from="2026-01-01", date_to="2026-01-31")]
    recent = db.get_recent_expenses(bob, date_from="2026-01-01", date_to="2026-01-31")

    assert summary["total_spent"] == 10.0
    assert summary["transaction_count"] == 1
    assert totals == [("Food", 10.0)]
    assert len(recent) == 1


def test_helpers_treat_sql_in_dates_as_data(app, user_with_spread):
    injected = "2026-01-10' OR '1'='1"

    summary = db.get_expense_summary(user_with_spread, date_from=injected, date_to="2026-01-31")

    assert summary["transaction_count"] != 5
