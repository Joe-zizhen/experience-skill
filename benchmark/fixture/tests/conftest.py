import os
import tempfile

_tmpdir = tempfile.mkdtemp(prefix="benchfix-")
os.environ["DB_PATH"] = os.path.join(_tmpdir, "test.db")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FIRST_SUPERUSER"] = "admin@example.com"
os.environ["FIRST_SUPERUSER_PASSWORD"] = "admin12345"

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture(scope="session")
def client():
    conn = db.connect()
    db.init_db(conn)
    conn.close()
    return TestClient(app)


@pytest.fixture(scope="session")
def admin_headers(client):
    r = client.post(
        "/login/access-token",
        data={"username": "admin@example.com", "password": "admin12345"},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def bearer(token):
    return {"Authorization": "Bearer " + token}


def login(client, email, password):
    r = client.post("/login/access-token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def member_headers(client, admin_headers):
    r = client.post(
        "/users/",
        json={"email": "member@example.com", "password": "member123", "full_name": "Member"},
        headers=admin_headers,
    )
    assert r.status_code == 201, r.text
    return bearer(login(client, "member@example.com", "member123"))
