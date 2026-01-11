import datetime

class _FakeOrder:
    def __init__(self, user_id: str, partner_id=None, has_partner_field: bool = True):
        self.user_id = user_id
        self.partner_id = partner_id
        self._has_partner_field = has_partner_field

    def HasField(self, name: str) -> bool:
        if name == "partner_id":
            return self._has_partner_field and self.partner_id is not None
        return hasattr(self, name)


class _FakeResp:
    def __init__(self, order):
        self.order = order

    def HasField(self, name: str) -> bool:
        return name == "order" and self.order is not None


def test_create_review_success(client, monkeypatch):
    import app.main as main_mod

    def _fake_get_order_by_id(order_id: int, tenant_id=None):
        return _FakeResp(_FakeOrder(user_id="user-1", partner_id="partner-1", has_partner_field=True))

    monkeypatch.setattr(main_mod, "get_order_by_id", _fake_get_order_by_id)

    r = client.post(
        "/reviews",
        json={"order_id": 1, "user_id": "user-1", "rating": 5, "comment": "ok"},
    )
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


def test_create_review_grpc_failure_returns_502(client, monkeypatch):
    import app.main as main_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("grpc down")

    monkeypatch.setattr(main_mod, "get_order_by_id", _boom)

    r = client.post("/reviews", json={"order_id": 2, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 502
    assert "Order service unavailable" in r.json()["detail"]


def test_create_review_order_not_found_404(client, monkeypatch):
    import app.main as main_mod

    class _NoOrder:
        def HasField(self, name: str) -> bool:
            return False

    monkeypatch.setattr(main_mod, "get_order_by_id", lambda order_id, tenant_id=None: _NoOrder())

    r = client.post("/reviews", json={"order_id": 3, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 404
    assert r.json()["detail"] == "Order not found"


def test_create_review_wrong_owner_403(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="someone-else", partner_id="partner-1")),
    )

    r = client.post("/reviews", json={"order_id": 4, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 403
    assert r.json()["detail"] == "Order does not belong to user"


def test_create_review_missing_partner_id_400(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="", has_partner_field=True)),
    )

    r = client.post("/reviews", json={"order_id": 5, "user_id": "user-1", "rating": 5, "comment": None})
    assert r.status_code == 400
    assert r.json()["detail"] == "Order has no partner_id set"


def test_create_review_duplicate_order_409(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="partner-1")),
    )

    payload = {"order_id": 6, "user_id": "user-1", "rating": 5, "comment": None}

    r1 = client.post("/reviews", json=payload)
    assert r1.status_code == 201, r1.text

    r2 = client.post("/reviews", json=payload)
    assert r2.status_code == 409
    assert r2.json()["detail"] == "Order already reviewed"


def test_create_review_invalid_rating_422(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="partner-1")),
    )

    r = client.post("/reviews", json={"order_id": 7, "user_id": "user-1", "rating": 6, "comment": None})
    assert r.status_code == 422


def test_list_partner_reviews_sorted_desc(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="partner-x")),
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


def test_get_partner_rating(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="p1")),
    )

    # No reviews -> 0s
    r0 = client.get("/partners/p1/rating")
    assert r0.status_code == 200
    assert r0.json() == {"partner_id": "p1", "avg_rating": 0.0, "count": 0}

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
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="p1")),
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


def test_tenant_isolation(client, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(
        main_mod,
        "get_order_by_id",
        lambda order_id, tenant_id=None: _FakeResp(_FakeOrder(user_id="user-1", partner_id="partner-a")),
    )

    payload = {"order_id": 999, "user_id": "user-1", "rating": 5, "comment": None}

    r_a = client.post("/reviews", json=payload, headers={"X-Tenant-Id": "tenant_a"})
    r_b = client.post("/reviews", json=payload, headers={"X-Tenant-Id": "tenant_b"})

    assert r_a.status_code == 201, r_a.text
    assert r_b.status_code == 201, r_b.text
