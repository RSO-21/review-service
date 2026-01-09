import os
import grpc
from . import orders_pb2, orders_pb2_grpc

ORDERS_GRPC_HOST = os.getenv("ORDERS_GRPC_HOST", "order-service")
ORDERS_GRPC_PORT = int(os.getenv("ORDERS_GRPC_PORT", "50051"))

def get_order_by_id(order_id: int, tenant_id: str | None = None, timeout_s: float = 2.0):
    target = f"{ORDERS_GRPC_HOST}:{ORDERS_GRPC_PORT}"

    with grpc.insecure_channel(target) as channel:
        stub = orders_pb2_grpc.OrdersServiceStub(channel)

        metadata = []
        if tenant_id:
            metadata.append(("x-tenant-id", tenant_id))

        return stub.GetOrderById(
            orders_pb2.GetOrderByIdRequest(order_id=order_id),
            timeout=timeout_s,
            metadata=metadata,
        )
