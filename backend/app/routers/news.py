from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NewsArticle

router = APIRouter(prefix="/api/news", tags=["news"])


class ArticleOut(BaseModel):
    id: int
    category: str
    title: str
    url: Optional[str]
    source: Optional[str]
    published_at: Optional[datetime]
    description: Optional[str]
    ai_summary: Optional[str]

    model_config = {"from_attributes": True}


@router.get("/{category}", response_model=List[ArticleOut])
def get_news(category: str, limit: int = 10, db: Session = Depends(get_db)):
    return (
        db.query(NewsArticle)
        .filter(NewsArticle.category == category)
        .order_by(NewsArticle.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )
