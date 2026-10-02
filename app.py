import sqlite3

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

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


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # Placeholder data for the design step — replaced by DB queries later
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "initials": "DU",
        "member_since": "January 2026",
    }
    transactions = [
        {"date": "2026-09-28", "description": "Grocery run", "category": "Food", "amount": 1850.00},
        {"date": "2026-09-26", "description": "Electricity bill", "category": "Bills", "amount": 2400.00},
        {"date": "2026-09-24", "description": "Metro card top-up", "category": "Transport", "amount": 500.00},
        {"date": "2026-09-22", "description": "Pharmacy", "category": "Health", "amount": 720.50},
        {"date": "2026-09-20", "description": "Movie tickets", "category": "Entertainment", "amount": 600.00},
        {"date": "2026-09-18", "description": "New headphones", "category": "Shopping", "amount": 2999.00},
        {"date": "2026-09-15", "description": "Dinner out", "category": "Food", "amount": 1250.00},
        {"date": "2026-09-12", "description": "Gift wrapping", "category": "Other", "amount": 150.00},
    ]

    totals = {}
    for txn in transactions:
        totals[txn["category"]] = totals.get(txn["category"], 0) + txn["amount"]
    total_spent = sum(totals.values())
    categories = [
        {
            "name": name,
            "amount": amount,
            "pct": round(amount / total_spent * 100, 1) if total_spent else 0,
        }
        for name, amount in sorted(totals.items(), key=lambda kv: kv[1], reverse=True)
    ]
    stats = {
        "total_spent": total_spent,
        "transaction_count": len(transactions),
        "top_category": categories[0]["name"] if categories else "—",
    }

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
