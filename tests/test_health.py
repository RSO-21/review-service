from fastapi.testclient import TestClient


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["db"] == "ok"


def test_health_db_failure_returns_503(app_and_engine):
    app, _ = app_and_engine
    from app.main import get_db_with_schema

    def _bad_db():
        class Bad:
            def execute(self, *args, **kwargs):
                raise Exception("db down")
        yield Bad()

    app.dependency_overrides[get_db_with_schema] = _bad_db
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 503
    assert "Database unavailable" in r.json()["detail"]

    app.dependency_overrides.clear()
