import os
import sqlite3
from datetime import date

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "expense_tracker.db",
)

CATEGORIES = [
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# --- Add expense --------------------------------------------------- #

def insert_expense(user_id, amount, category, date, description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# --- Delete expense ------------------------------------------------ #

def get_expense_for_user(expense_id, user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses "
            "WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def delete_expense_for_user(expense_id, user_id):
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# --- Edit expense -------------------------------------------------- #

def update_expense_for_user(expense_id, user_id, amount, category, date, description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# --- Date range filter --------------------------------------------- #

def _date_range_params(date_from, date_to):
    """Bind values for `(? IS NULL OR date BETWEEN ? AND ?)`.

    The range only applies when both bounds are given.
    """
    if not date_from or not date_to:
        return (None, None, None)
    return (date_from, date_from, date_to)


# --- Summary stats (subagent 2) ------------------------------------ #

def get_expense_summary(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total_spent, "
            "COUNT(*) AS transaction_count "
            "FROM expenses WHERE user_id = ? "
            "AND (? IS NULL OR date BETWEEN ? AND ?)",
            (user_id, *_date_range_params(date_from, date_to)),
        ).fetchone()
    finally:
        conn.close()


# --- Category breakdown (subagent 3) ------------------------------- #

def get_category_totals(user_id, date_from=None, date_to=None):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses "
            "WHERE user_id = ? AND (? IS NULL OR date BETWEEN ? AND ?) "
            "GROUP BY category "
            "ORDER BY total DESC, category ASC",
            (user_id, *_date_range_params(date_from, date_to)),
        ).fetchall()
    finally:
        conn.close()


# --- Transaction history (subagent 1) ------------------------------ #

def get_recent_expenses(user_id, limit=10, date_from=None, date_to=None):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, date, description, category, amount FROM expenses "
            "WHERE user_id = ? AND (? IS NULL OR date BETWEEN ? AND ?) "
            "ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *_date_range_params(date_from, date_to), limit),
        ).fetchall()
    finally:
        conn.close()


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                date TEXT NOT NULL,
                description TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing > 0:
            return

        password_hash = generate_password_hash("demo123")
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", password_hash),
        )
        user_id = cursor.lastrowid

        year = date.today().year
        month = date.today().month

        expenses = [
            ("Food", 45.50, 2, "Groceries at supermarket"),
            ("Transport", 20.00, 4, "Bus pass top-up"),
            ("Bills", 89.99, 5, "Electricity bill"),
            ("Health", 32.00, 8, "Pharmacy - vitamins"),
            ("Entertainment", 15.00, 10, "Movie tickets"),
            ("Shopping", 60.75, 14, "New shoes"),
            ("Other", 10.00, 18, "Miscellaneous purchase"),
            ("Food", 25.30, 22, "Lunch with friends"),
        ]

        rows = [
            (user_id, amount, category, f"{year:04d}-{month:02d}-{day:02d}", description)
            for category, amount, day, description in expenses
        ]

        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
