from .conftest import bearer


def test_login_ok(client):
    r = client.post(
        "/login/access-token",
        data={"username": "admin@example.com", "password": "admin12345"},
    )
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_login_wrong_password(client):
    r = client.post(
        "/login/access-token",
        data={"username": "admin@example.com", "password": "wrong"},
    )
    assert r.status_code == 400


def test_me_requires_auth(client):
    assert client.get("/users/me").status_code == 401


def test_me_with_token(client, admin_headers):
    r = client.get("/users/me", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@example.com"
    assert "hashed_password" not in r.json()


def test_bad_token_rejected(client):
    assert client.get("/users/me", headers=bearer("not-a-token")).status_code == 401
