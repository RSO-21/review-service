import os
import sys
import types
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

def _ensure_env():
    required = ["PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing env vars for tests: {missing}. "
            "Set them locally or in GitHub Actions env."
        )
    os.environ.setdefault("PGPORT", "5432")


def _stub_orders_grpc_modules():
    orders_pb2 = types.ModuleType("orders_pb2")

    class GetOrderByIdRequest:
        def __init__(self, order_id: int):
            self.order_id = order_id

    orders_pb2.GetOrderByIdRequest = GetOrderByIdRequest
    sys.modules.setdefault("orders_pb2", orders_pb2)
    sys.modules.setdefault("app.grpc.orders_pb2", orders_pb2)

    orders_pb2_grpc = types.ModuleType("orders_pb2_grpc")

    class OrdersServiceStub:
        def __init__(self, channel):
            self._channel = channel

        def GetOrderById(self, request, metadata=None):
            raise RuntimeError("Stub called. Tests must monkeypatch app.main.get_order_by_id.")

    orders_pb2_grpc.OrdersServiceStub = OrdersServiceStub
    sys.modules.setdefault("orders_pb2_grpc", orders_pb2_grpc)
    sys.modules.setdefault("app.grpc.orders_pb2_grpc", orders_pb2_grpc)


@pytest.fixture(scope="session")
def app_and_engine():
    _ensure_env()
    _stub_orders_grpc_modules()

    import importlib
    main_mod = importlib.import_module("app.main")

    app = main_mod.app

    app.include_router(main_mod.router)

    from app.database import engine
    from app.models import Base
    from sqlalchemy import text

    schemas = ["public", "tenant_a", "tenant_b"]

    with engine.begin() as conn:
        for schema in schemas:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.execute(text(f"SET search_path TO {schema}"))
            Base.metadata.create_all(bind=conn)

    return app, engine



@pytest.fixture()
def client(app_and_engine):
    app, _ = app_and_engine
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clean_db(app_and_engine):
    _, engine = app_and_engine
    schemas = ["public", "tenant_a", "tenant_b"]

    with engine.begin() as conn:
        for schema in schemas:
            conn.execute(text(f"SET search_path TO {schema}"))
            conn.execute(text("TRUNCATE TABLE reviews RESTART IDENTITY CASCADE"))


class FakeOrder:
    def __init__(self, user_id: str, partner_id=None, has_partner_field: bool = True):
        self.user_id = user_id
        self.partner_id = partner_id
        self._has_partner_field = has_partner_field

    def HasField(self, name: str) -> bool:
        if name == "partner_id":
            return self._has_partner_field and self.partner_id is not None
        return hasattr(self, name)


class FakeResp:
    def __init__(self, order):
        self.order = order

    def HasField(self, name: str) -> bool:
        return name == "order" and self.order is not None


@pytest.fixture()
def mock_order_ok(monkeypatch):
    import app.main as main_mod

    def _fake_get_order_by_id(order_id: int, tenant_id=None):
        return FakeResp(FakeOrder(user_id="user-1", partner_id="partner-1", has_partner_field=True))

    monkeypatch.setattr(main_mod, "get_order_by_id", _fake_get_order_by_id)
    return _fake_get_order_by_id
