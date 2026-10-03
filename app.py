import sqlite3
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_totals,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-change-me"

with app.app_context():
    init_db()
    seed_db()


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

def build_stats(user_id):
    """Return {"total_spent": float, "transaction_count": int}."""
    summary = get_expense_summary(user_id)
    return {
        "total_spent": float(summary["total_spent"]),
        "transaction_count": int(summary["transaction_count"]),
    }


# --- Category breakdown (subagent 3) ------------------------------- #

def build_categories(user_id, total_spent):
    """Return [{"name", "amount", "pct"}, ...] sorted by amount desc."""
    return [
        {
            "name": row["category"],
            "amount": float(row["total"]),
            "pct": round(row["total"] / total_spent * 100, 1) if total_spent else 0,
        }
        for row in get_category_totals(user_id)
    ]


# --- Transaction history (subagent 1) ------------------------------ #

def build_transactions(user_id):
    """Return the 10 most recent expenses as dicts for the table."""
    return [
        {
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": float(row["amount"]),
        }
        for row in get_recent_expenses(user_id)
    ]


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    user_row = get_user_by_id(user_id)
    if user_row is None:
        session.clear()
        return redirect(url_for("login"))

    user = build_user(user_row)
    stats = build_stats(user_id)
    categories = build_categories(user_id, stats["total_spent"])
    stats["top_category"] = categories[0]["name"] if categories else "—"
    transactions = build_transactions(user_id)

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        categories=categories,
        transactions=transactions,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
