FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /workspace/app/grpc && \
    test -f /workspace/app/grpc/__init__.py || touch /workspace/app/grpc/__init__.py

RUN python -m grpc_tools.protoc \
  -I/workspace/protos \
  --python_out=/workspace/app/grpc \
  --grpc_python_out=/workspace/app/grpc \
  /workspace/protos/orders.proto

RUN find /workspace/app/grpc -name '*_pb2_grpc.py' -exec sed -i 's/^import \(.*_pb2\) as \(.*\)$/from . import \1 as \2/' {} \;

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/workspace"]
