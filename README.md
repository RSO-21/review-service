# Review Service

Review Service is a FastAPI microservice responsible for managing user reviews and partner ratings in a multi-tenant microservices system.

It allows users to submit reviews for completed orders, ensures review validity via the Orders Service, and provides aggregated rating data for partners.

## Responsibilities

* Creating reviews for orders
* Enforcing one review per order
* Validating orders and ownership by gRPC
* Aggregating partner ratings
* Tenant isolation using PostgreSQL schemas
* Health and readiness checks
* Prometheus metrics exposure

## Tech Stack

* **FastAPI**
* **SQLAlchemy 2.0**
* **PostgreSQL** (schema-per-tenant)
* **gRPC** (Orders Service)
* **Docker**
* **GitHub Actions**
* **pytest**

## Multi-Tenancy

* Tenant is selected by request header:

  ```
  X-Tenant-Id: <tenant_name>
  ```

* If tenant is not provided, it defaults to `public`

Each tenant is isolated using a separate PostgreSQL schema.

## API Endpoints

### Reviews

#### `POST /reviews`

Creates a new review for an order.

**Validation rules:**

* Order must exist (validated via Orders Service)
* Order must belong to the requesting user
* Order must contain a `partner_id`
* Only one review per order is allowed
* Rating must be between 1 and 5

**Responses:**

* **201** – Review created
* **400** – Order has no `partner_id`
* **403** – Order does not belong to user
* **404** – Order not found
* **409** – Order already reviewed
* **422** – Invalid request body
* **502** – Orders Service unavailable


### Partner Reviews

#### `GET /partners/{partner_id}/reviews`

Returns all reviews for a given partner, ordered by creation time (newest first).

### Partner Rating

#### `GET /partners/{partner_id}/rating`

Returns aggregated rating information for a partner:

* average rating
* total number of reviews

### Multiple Partner Ratings

* `GET /partners/ratings?partner_ids=p1,p2,p3`

Returns rating data for multiple partners in a single request.

* All requested partner IDs are included in the response
* Partners without reviews return `avg_rating = 0.0` and `count = 0`

### Health

* `GET /health`

Health/readiness endpoint. Verifies database connectivity.

* **200** – Service healthy
* **503** – Database unavailable

## Testing

Tests cover:

* Review creation and validation rules
* gRPC success and failure scenarios
* Duplicate review protection
* Partner rating aggregation
* Tenant isolation
* Health checks

Run tests locally:

```powershell
python -m pytest
```

## CI/CD

On push to `main`:

1. Run tests
2. Build Docker image
3. Push image to Azure Container Registry

The build is blocked if tests fail.