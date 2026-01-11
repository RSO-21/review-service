import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
import sys
import types

def _stub_orders_grpc_modules():
    """
    Tests monkeypatch app.main.get_order_by_id anyway, so we just need imports
    to succeed when app.grpc.orders_client imports generated proto modules.
    """

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
            raise RuntimeError("Stub called in tests. You should monkeypatch get_order_by_id.")

    orders_pb2_grpc.OrdersServiceStub = OrdersServiceStub

    sys.modules.setdefault("orders_pb2_grpc", orders_pb2_grpc)
    sys.modules.setdefault("app.grpc.orders_pb2_grpc", orders_pb2_grpc)


@pytest.fixture(autouse=True)
def _clean_db(app_and_engine):
    _, engine = app_and_engine
    schemas = ["public", "tenant_a", "tenant_b"]

    with engine.begin() as conn:
        for schema in schemas:
            conn.execute(text(f"SET search_path TO {schema}"))
            conn.execute(text("TRUNCATE TABLE reviews RESTART IDENTITY CASCADE"))


def _ensure_env():
    required = ["PGHOST", "PGUSER", "PGPASSWORD", "PGDATABASE"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise RuntimeError(
            f"Missing env vars for tests: {missing}. "
            "Set them locally or in GitHub Actions env."
        )
    os.environ.setdefault("PGPORT", "5432")


@pytest.fixture(scope="session")
def app_and_engine():
    _ensure_env()
    _stub_orders_grpc_modules()

    from app.main import app
    from app.database import engine
    from app.models import Base

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
