from tests.conftest import FakeOrder, FakeResp


def test_create_review_success(client, mock_order_ok):
    payload = {"order_id": 1, "user_id": "user-1", "rating": 5, "comment": "ok"}
    r = client.post("/reviews", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["order_id"] == 1
    assert body["user_id"] == "user-1"
    assert body["partner_id"] == "partner-1"
    assert body["rating"] == 5
    assert body["comment"] == "ok"
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


def test_create_review_invalid_rating_422(client, mock_order_ok):
    r = client.post("/reviews", json={"order_id": 2, "user_id": "user-1", "rating": 6, "comment": None})
    assert r.status_code == 422


def test_create_review_grpc_failure_returns_502(client, monkeypatch):
    import app.main as main_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("grpc down")

    monkeypatch.setattr(main_mod, "get_order_by_id", _boom)

    r = client.post("/reviews", json={"order_id": 3, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 502
    assert "Order service unavailable" in r.json()["detail"]


def test_create_review_order_not_found_404(client, monkeypatch):
    import app.main as main_mod

    class _NoOrder:
        def HasField(self, name: str) -> bool:
            return False

    monkeypatch.setattr(main_mod, "get_order_by_id", lambda order_id, tenant_id=None: _NoOrder())

    r = client.post("/reviews", json={"order_id": 4, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 404
    assert r.json()["detail"] == "Order not found"


def test_create_review_missing_partner_id_400(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: FakeResp(FakeOrder(user_id="user-1", partner_id="", has_partner_field=True)),
    )

    r = client.post("/reviews", json={"order_id": 6, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 400
    assert r.json()["detail"] == "Order has no partner_id set"


def test_create_review_missing_partner_field_400(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: FakeResp(FakeOrder(user_id="user-1", partner_id=None, has_partner_field=False)),
    )

    r = client.post("/reviews", json={"order_id": 7, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 400
    assert r.json()["detail"] == "Order has no partner_id set"


def test_create_review_duplicate_order_409(client, mock_order_ok):
    payload = {"order_id": 8, "user_id": "user-1", "rating": 5, "comment": None}
    r1 = client.post("/reviews", json=payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/reviews", json=payload)
    assert r2.status_code == 409
    assert r2.json()["detail"] == "Order already reviewed"


def test_list_partner_reviews_sorted_desc(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: FakeResp(FakeOrder(user_id="user-1", partner_id="partner-x")),
    )

    r1 = client.post("/reviews", json={"order_id": 10, "user_id": "user-1", "rating": 2, "comment": "a"})
    assert r1.status_code == 201
    r2 = client.post("/reviews", json={"order_id": 11, "user_id": "user-1", "rating": 4, "comment": "b"})
    assert r2.status_code == 201

    r = client.get("/partners/partner-x/reviews")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 2
    assert body[0]["order_id"] == 11
    assert body[1]["order_id"] == 10


def test_get_partner_rating_zero_when_none(client):
    r = client.get("/partners/p0/rating")
    assert r.status_code == 200
    assert r.json() == {"partner_id": "p0", "avg_rating": 0.0, "count": 0}


def test_get_partner_rating_avg_and_count(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: FakeResp(FakeOrder(user_id="user-1", partner_id="p1")),
    )

    client.post("/reviews", json={"order_id": 20, "user_id": "user-1", "rating": 2, "comment": None})
    client.post("/reviews", json={"order_id": 21, "user_id": "user-1", "rating": 4, "comment": None})

    r = client.get("/partners/p1/rating")
    assert r.status_code == 200
    body = r.json()
    assert body["partner_id"] == "p1"
    assert body["count"] == 2
    assert abs(body["avg_rating"] - 3.0) < 1e-9


def test_get_partners_ratings_bulk_includes_missing(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: FakeResp(FakeOrder(user_id="user-1", partner_id="p1")),
    )

    client.post("/reviews", json={"order_id": 30, "user_id": "user-1", "rating": 5, "comment": None})

    r = client.get("/partners/ratings", params={"partner_ids": "p1,p2"})
    assert r.status_code == 200
    body = r.json()

    assert "p1" in body and "p2" in body
    assert body["p1"]["count"] == 1
    assert body["p1"]["avg_rating"] == 5.0
    assert body["p2"]["count"] == 0
    assert body["p2"]["avg_rating"] == 0.0


def test_tenant_isolation_same_order_id_ok_in_different_tenants(app_and_engine, monkeypatch):

    from fastapi.testclient import TestClient
    import app.main as main_mod

    app, _ = app_and_engine
    client = TestClient(app)

    def _fake_get_order_by_id(order_id: int, tenant_id=None):
        return FakeResp(FakeOrder(user_id="user-1", partner_id=f"partner-{tenant_id or 'public'}"))

    monkeypatch.setattr(main_mod, "get_order_by_id", _fake_get_order_by_id)

    payload = {"order_id": 999, "user_id": "user-1", "rating": 5, "comment": None}

    r_a = client.post("/reviews", json=payload, headers={"x-tenant-id": "tenant_a"})
    r_b = client.post("/reviews", json=payload, headers={"x-tenant-id": "tenant_b"})

    assert r_a.status_code == 201, r_a.text
    assert r_b.status_code == 201, r_b.text
