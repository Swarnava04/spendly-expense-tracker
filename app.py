import calendar
import math
import sqlite3
from datetime import date, datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_user,
    delete_expense_for_user,
    get_category_totals,
    get_expense_for_user,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    insert_expense,
    seed_db,
    update_expense_for_user,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-change-me"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Auth helpers                                                        #
# ------------------------------------------------------------------ #

def get_current_user():
    """Return the logged-in user's row, or None (clearing a stale session)."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
    return user


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")
    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not all([name, email, password, confirm_password]):
        flash("All fields are required.", "error")
        return render_template("register.html")
    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("register.html")
    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("Email already registered.", "error")
        return render_template("register.html")

    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_user_by_email(email) if email and password else None

    if user is None or not check_password_hash(user["password_hash"], password):
        flash("Invalid email or password.", "error")
        return render_template("login.html")

    session.clear()
    session["user_id"] = int(user["id"])
    return redirect(url_for("landing"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Profile view-model builders                                         #
# ------------------------------------------------------------------ #

def build_user(user_row):
    words = user_row["name"].split()
    initials = (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()
    member_since = datetime.strptime(
        user_row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %Y")
    return {
        "name": user_row["name"],
        "email": user_row["email"],
        "initials": initials,
        "member_since": member_since,
    }


# --- Summary stats (subagent 2) ------------------------------------ #

def build_stats(user_id, date_from=None, date_to=None):
    """Return {"total_spent": float, "transaction_count": int}."""
    summary = get_expense_summary(user_id, date_from=date_from, date_to=date_to)
    return {
        "total_spent": float(summary["total_spent"]),
        "transaction_count": int(summary["transaction_count"]),
    }


# --- Category breakdown (subagent 3) ------------------------------- #

def build_categories(user_id, total_spent, date_from=None, date_to=None):
    """Return [{"name", "amount", "pct"}, ...] sorted by amount desc."""
    return [
        {
            "name": row["category"],
            "amount": float(row["total"]),
            "pct": round(row["total"] / total_spent * 100, 1) if total_spent else 0,
        }
        for row in get_category_totals(
            user_id, date_from=date_from, date_to=date_to
        )
    ]


# --- Transaction history (subagent 1) ------------------------------ #

def build_transactions(user_id, date_from=None, date_to=None):
    """Return the 10 most recent expenses as dicts for the table."""
    return [
        {
            "id": row["id"],
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in get_recent_expenses(
            user_id, date_from=date_from, date_to=date_to
        )
    ]


# --- Date range filter --------------------------------------------- #

def _parse_iso_date(value):
    """Return a date for a YYYY-MM-DD string, or None if empty/invalid."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_date_filter(args):
    """Return (date_from, date_to, error) as ISO strings or None.

    The filter only applies when both dates are valid; a reversed
    range falls back to no filter with an error message.
    """
    start = _parse_iso_date(args.get("date_from", ""))
    end = _parse_iso_date(args.get("date_to", ""))
    if start is None or end is None:
        return None, None, None
    if start > end:
        return None, None, "Start date must be before end date."
    return start.isoformat(), end.isoformat(), None


def _shift_months(d, months):
    """Shift a date by whole months, clamping the day to the month's end."""
    index = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(d.day, last_day))


def build_presets(today):
    """Return the quick-select date ranges for the filter bar."""
    month_end = today.replace(
        day=calendar.monthrange(today.year, today.month)[1]
    )
    return [
        {
            "key": "month",
            "label": "This Month",
            "date_from": today.replace(day=1).isoformat(),
            "date_to": month_end.isoformat(),
        },
        {
            "key": "3m",
            "label": "Last 3 Months",
            "date_from": _shift_months(today, -3).isoformat(),
            "date_to": today.isoformat(),
        },
        {
            "key": "6m",
            "label": "Last 6 Months",
            "date_from": _shift_months(today, -6).isoformat(),
            "date_to": today.isoformat(),
        },
        {"key": "all", "label": "All Time", "date_from": None, "date_to": None},
    ]


def build_filters(date_from, date_to, today):
    """Return the filter bar state: active range, active preset, presets."""
    presets = build_presets(today)
    if date_from is None:
        active = "all"
    else:
        active = next(
            (
                p["key"]
                for p in presets
                if (p["date_from"], p["date_to"]) == (date_from, date_to)
            ),
            "custom",
        )
    return {
        "date_from": date_from or "",
        "date_to": date_to or "",
        "active": active,
        "presets": presets,
    }


@app.route("/profile")
def profile():
    user_row = get_current_user()
    if user_row is None:
        return redirect(url_for("login"))
    user_id = session["user_id"]

    date_from, date_to, error = parse_date_filter(request.args)
    if error:
        flash(error, "error")

    user = build_user(user_row)
    stats = build_stats(user_id, date_from, date_to)
    categories = build_categories(
        user_id, stats["total_spent"], date_from, date_to
    )
    stats["top_category"] = categories[0]["name"] if categories else "—"
    transactions = build_transactions(user_id, date_from, date_to)
    filters = build_filters(date_from, date_to, date.today())

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        categories=categories,
        transactions=transactions,
        filters=filters,
    )


# ------------------------------------------------------------------ #
# Add expense                                                         #
# ------------------------------------------------------------------ #

DESCRIPTION_MAX_LENGTH = 200


def parse_expense_form(form):
    """Return (values, error) for a submitted add-expense form.

    `values` holds the cleaned amount, category, date and description;
    `error` is the first failing check's message, or None.
    """
    try:
        amount = float(form.get("amount", ""))
    except ValueError:
        amount = None
    if amount is None or not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be a positive number."

    category = form.get("category", "")
    if category not in CATEGORIES:
        return None, "Please choose a valid category."

    expense_date = _parse_iso_date(form.get("date", ""))
    if expense_date is None:
        return None, "Please enter a valid date."

    description = form.get("description", "").strip()
    if len(description) > DESCRIPTION_MAX_LENGTH:
        return None, "Description must be 200 characters or fewer."

    return {
        "amount": round(amount, 2),
        "category": category,
        "date": expense_date.isoformat(),
        "description": description or None,
    }, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if get_current_user() is None:
        return redirect(url_for("login"))
    user_id = session["user_id"]

    if request.method == "GET":
        form = {"date": date.today().isoformat()}
        return render_template(
            "add_expense.html", categories=CATEGORIES, form=form
        )

    values, error = parse_expense_form(request.form)
    if error:
        flash(error, "error")
        return render_template(
            "add_expense.html", categories=CATEGORIES, form=request.form
        )

    insert_expense(user_id, **values)
    flash("Expense added.", "success")
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Delete expense                                                      #
# ------------------------------------------------------------------ #

@app.route("/expenses/<int:id>/delete", methods=["GET", "POST"])
def delete_expense(id):
    if get_current_user() is None:
        return redirect(url_for("login"))
    user_id = session["user_id"]

    expense = get_expense_for_user(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template("delete_expense.html", expense=expense)

    if delete_expense_for_user(id, user_id) == 0:
        abort(404)
    flash("Expense deleted.", "success")
    return redirect(url_for("profile"))


# ------------------------------------------------------------------ #
# Edit expense                                                        #
# ------------------------------------------------------------------ #

@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if get_current_user() is None:
        return redirect(url_for("login"))
    user_id = session["user_id"]

    expense = get_expense_for_user(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        form = {
            "amount": "%.2f" % expense["amount"],
            "category": expense["category"],
            "date": expense["date"],
            "description": expense["description"] or "",
        }
        return render_template(
            "edit_expense.html", categories=CATEGORIES, form=form, expense_id=id
        )

    values, error = parse_expense_form(request.form)
    if error:
        flash(error, "error")
        return render_template(
            "edit_expense.html",
            categories=CATEGORIES,
            form=request.form,
            expense_id=id,
        )

    if update_expense_for_user(id, user_id, **values) == 0:
        abort(404)
    flash("Expense updated.", "success")
    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
