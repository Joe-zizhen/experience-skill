def test_admin_creates_user(client, admin_headers):
    r = client.post(
        "/users/",
        json={"email": "alice@example.com", "password": "alice1234", "full_name": "Alice"},
        headers=admin_headers,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "alice@example.com"
    assert body["is_superuser"] is False
    assert "hashed_password" not in body


def test_duplicate_email_conflict(client, admin_headers):
    r = client.post(
        "/users/",
        json={"email": "alice@example.com", "password": "alice1234"},
        headers=admin_headers,
    )
    assert r.status_code == 409


def test_short_password_rejected(client, admin_headers):
    r = client.post(
        "/users/",
        json={"email": "bob@example.com", "password": "short"},
        headers=admin_headers,
    )
    assert r.status_code == 422


def test_member_cannot_list_users(client, member_headers):
    assert client.get("/users/", headers=member_headers).status_code == 403


def test_member_cannot_create_user(client, member_headers):
    r = client.post(
        "/users/",
        json={"email": "carol@example.com", "password": "carol1234"},
        headers=member_headers,
    )
    assert r.status_code == 403


def test_update_me(client, member_headers):
    r = client.patch("/users/me", json={"full_name": "Renamed"}, headers=member_headers)
    assert r.status_code == 200
    assert r.json()["full_name"] == "Renamed"
