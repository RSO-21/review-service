from fastapi import FastAPI, Depends, HTTPException, Header, Query, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Optional, List

from prometheus_fastapi_instrumentator import Instrumentator

from app.database import get_db_session, engine
from app.models import Base, Review
from app.schemas import ReviewCreate, ReviewOut, PartnerRatingOut
from app.grpc.orders_client import get_order_by_id

app = FastAPI(title="Review Microservice")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

router = APIRouter()

Instrumentator().instrument(app).expose(app)
app.include_router(router, prefix="/reviews")

def get_tenant_id(x_tenant_id: Optional[str] = Header(None)) -> str:
    return x_tenant_id or "public"

def get_db_with_schema(tenant_id: str = Depends(get_tenant_id)):
    with get_db_session(schema=tenant_id) as db:
        yield db

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    payload: ReviewCreate,
    tenant_id: str = Depends(get_tenant_id),
    db: Session = Depends(get_db_with_schema),
):
    try:
        resp = get_order_by_id(order_id=payload.order_id, tenant_id=tenant_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Order service unavailable: {e}")

    if not resp or not resp.HasField("order"):
        raise HTTPException(status_code=404, detail="Order not found")

    order = resp.order

    if order.user_id != payload.user_id:
        raise HTTPException(status_code=403, detail="Order does not belong to user")

    if not order.HasField("partner_id") or not order.partner_id:
        raise HTTPException(status_code=400, detail="Order has no partner_id set")

    existing = db.execute(
        select(Review).where(Review.order_id == payload.order_id)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Order already reviewed")

    review = Review(
        id=Review.new_id(),
        order_id=payload.order_id,
        user_id=payload.user_id,
        partner_id=order.partner_id,
        rating=payload.rating,
        comment=payload.comment,
    )

    db.add(review)
    db.commit()
    db.refresh(review)
    return review

@app.get("/partners/{partner_id}/reviews", response_model=List[ReviewOut])
def list_partner_reviews(partner_id: str, db: Session = Depends(get_db_with_schema)):
    reviews = db.execute(
        select(Review).where(Review.partner_id == partner_id).order_by(Review.created_at.desc())
    ).scalars().all()
    return reviews

@app.get("/partners/ratings")
def get_partners_ratings(
    partner_ids: str = Query(...),
    db: Session = Depends(get_db_with_schema),
):
    partner_ids_list = [pid.strip() for pid in partner_ids.split(",") if pid.strip()]

    rows = db.execute(
        select(
            Review.partner_id,
            func.avg(Review.rating),
            func.count(Review.id),
        )
        .where(Review.partner_id.in_(partner_ids_list))
        .group_by(Review.partner_id)
    ).all()

    result = {
        partner_id: PartnerRatingOut(
            partner_id=partner_id,
            avg_rating=float(avg) if avg is not None else 0.0,
            count=int(count),
        )
        for partner_id, avg, count in rows
    }

    for pid in partner_ids_list:
        if pid not in result:
            result[pid] = PartnerRatingOut(
                partner_id=pid,
                avg_rating=0.0,
                count=0,
            )

    return result

@app.get("/partners/{partner_id}/rating", response_model=PartnerRatingOut)
def get_partner_rating(partner_id: str, db: Session = Depends(get_db_with_schema)):
    row = db.execute(
        select(func.avg(Review.rating), func.count(Review.id)).where(Review.partner_id == partner_id)
    ).one()
    avg_rating = float(row[0]) if row[0] is not None else 0.0
    count = int(row[1]) if row[1] is not None else 0

    return PartnerRatingOut(partner_id=partner_id, avg_rating=avg_rating, count=count)

@app.get("/health", tags=["health"])
def health(db: Session = Depends(get_db_with_schema)):
    try:
        db.execute(select(1))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}",
        )
    return {"status": "ok", "db": "ok"}
