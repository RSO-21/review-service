# Review Service ⭐

The **Review Service** is a microservice responsible for handling **user reviews and ratings of completed orders**.
It enables users to rate their orders (1–5 stars) and provides aggregated ratings for partners (restaurants).

This service is designed as a **loosely coupled component** in the FriFood microservice architecture and communicates with the **Order Service** via **gRPC** for validation.

---

## Responsibilities

* Create a review for an order (one review per order)
* List all reviews for a partner
* Compute and return the average rating for a partner
* Validate order ownership using the Order Service (gRPC)

---

## API Endpoints (REST)

### Create a review

```
POST /reviews
```

**Body**

```json
{
  "order_id": 123,
  "user_id": "uuid-string",
  "rating": 5,
  "comment": "Fast delivery and great food!"
}
```

Rules:

* Rating must be between **1 and 5**
* Each order can be reviewed **only once**
* The order must belong to the given user

---

### List partner reviews

```
GET /partners/{partner_id}/reviews
```

Returns all reviews for a partner, sorted by creation date.

---

### Get partner rating

```
GET /partners/{partner_id}/rating
```

**Response**

```json
{
  "partner_id": "uuid-string",
  "avg_rating": 4.6,
  "count": 18
}
```

---

### Health check

```
GET /health
```

---

## Architecture & Integration

* **Database:** PostgreSQL (schema-based multi-tenancy)
* **Validation:** gRPC call to Order Service (`GetOrderById`)
* **Communication:**
  * REST for client/API Gateway
  * gRPC for inter-service validation
* **Observability:** Prometheus metrics (`/metrics`)

---

## Running Locally (Docker Compose)

```bash
docker compose up review-service
```

Service will be available at:

```
http://localhost:8007
```