import os
import tempfile

import pytest

import database.db as db

# app.py runs init_db()/seed_db() at import time, so point the DB at a
# throwaway file *before* importing it — tests must never touch the real DB.
_import_dir = tempfile.mkdtemp()
db.DB_PATH = os.path.join(_import_dir, "import.db")

from app import app as flask_app  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(client):
    def _make_user(name="Test User", email="test@example.com", password="secret123"):
        user_id = db.create_user(name, email, password)
        return user_id

    return _make_user


@pytest.fixture
def login(client):
    def _login(email="test@example.com", password="secret123"):
        return client.post("/login", data={"email": email, "password": password})

    return _login


@pytest.fixture
def add_expense():
    def _add_expense(user_id, amount, category, date, description=None):
        conn = db.get_db()
        try:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, amount, category, date, description),
            )
            conn.commit()
        finally:
            conn.close()

    return _add_expense
