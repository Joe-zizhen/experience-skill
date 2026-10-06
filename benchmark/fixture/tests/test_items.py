def test_item_crud_and_ownership(client, admin_headers, member_headers):
    r = client.post("/items/", json={"title": "admin item"}, headers=admin_headers)
    assert r.status_code == 201
    admin_item = r.json()

    r = client.post("/items/", json={"title": "member item", "description": "d"}, headers=member_headers)
    assert r.status_code == 201
    member_item = r.json()

    mine = client.get("/items/", headers=member_headers).json()
    assert [i["title"] for i in mine] == ["member item"]

    r = client.get("/items/%d" % admin_item["id"], headers=member_headers)
    assert r.status_code == 403

    r = client.get("/items/%d" % admin_item["id"], headers=admin_headers)
    assert r.status_code == 200

    r = client.delete("/items/%d" % member_item["id"], headers=member_headers)
    assert r.status_code == 204
    assert client.get("/items/%d" % member_item["id"], headers=member_headers).status_code == 404


def test_empty_title_rejected(client, member_headers):
    r = client.post("/items/", json={"title": "  "}, headers=member_headers)
    assert r.status_code == 422


def test_missing_item_404(client, admin_headers):
    assert client.get("/items/99999", headers=admin_headers).status_code == 404


def test_items_require_auth(client):
    assert client.get("/items/").status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
