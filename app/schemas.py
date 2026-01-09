from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class ReviewCreate(BaseModel):
    order_id: int
    user_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None

class ReviewOut(BaseModel):
    id: str
    order_id: int
    user_id: str
    partner_id: str
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class PartnerRatingOut(BaseModel):
    partner_id: str
    avg_rating: float
    count: int
