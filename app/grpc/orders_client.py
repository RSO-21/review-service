import os
import grpc
from app.grpc import orders_pb2, orders_pb2_grpc

ORDERS_GRPC_HOST = os.getenv("ORDERS_GRPC_HOST", "order-service")
ORDERS_GRPC_PORT = int(os.getenv("ORDERS_GRPC_PORT", "50051"))

def get_order_by_id(order_id: int, tenant_id: str | None = None):
    target = f"{ORDERS_GRPC_HOST}:{ORDERS_GRPC_PORT}"
    metadata = [("x-tenant-id", (tenant_id or "public"))]

    with grpc.insecure_channel(target) as channel:
        stub = orders_pb2_grpc.OrdersServiceStub(channel)

        return stub.GetOrderById(
            orders_pb2.GetOrderByIdRequest(order_id=order_id),
            metadata=metadata,
        )
