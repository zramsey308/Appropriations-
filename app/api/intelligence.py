import json
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app.services.intelligence_service import IntelligenceService

router = APIRouter()


class ArticleCreate(BaseModel):
    title: str
    source: str
    url: Optional[str] = None
    summary: Optional[str] = None
    district: Optional[str] = None
    category: str = "campaign"
    sentiment: str = "neutral"
    mentioned_members: Optional[str] = None
    mentioned_orgs: Optional[str] = None
    published_at: Optional[datetime] = None


class ArticleBulkCreate(BaseModel):
    articles: list[ArticleCreate]


def _serialize_article(a):
    return {
        "id": a.id,
        "title": a.title,
        "source": a.source,
        "url": a.url,
        "summary": a.summary,
        "district": a.district,
        "category": a.category,
        "sentiment": a.sentiment,
        "is_endorsement": a.is_endorsement,
        "relevance_score": a.relevance_score,
        "relevance_flags": json.loads(a.relevance_flags) if a.relevance_flags else [],
        "mentioned_members": a.mentioned_members,
        "mentioned_orgs": a.mentioned_orgs,
        "published_at": a.published_at.isoformat() if a.published_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


@router.get("/summary")
def get_intelligence_summary(db: Session = Depends(get_db)):
    service = IntelligenceService(db)
    return service.get_summary()


@router.get("/articles")
def list_articles(
    district: Optional[str] = None,
    category: Optional[str] = None,
    sentiment: Optional[str] = None,
    min_relevance: Optional[float] = None,
    endorsements_only: bool = False,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
):
    service = IntelligenceService(db)
    items, total = service.list_articles(
        district=district,
        category=category,
        sentiment=sentiment,
        min_relevance=min_relevance,
        endorsements_only=endorsements_only,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [_serialize_article(a) for a in items],
        "total": total,
    }


@router.post("/articles")
def create_article(data: ArticleCreate, db: Session = Depends(get_db)):
    service = IntelligenceService(db)
    article = service.create_article(data.model_dump())
    return _serialize_article(article)


@router.post("/articles/bulk")
def create_articles_bulk(data: ArticleBulkCreate, db: Session = Depends(get_db)):
    service = IntelligenceService(db)
    results = []
    for a in data.articles:
        article = service.create_article(a.model_dump())
        results.append(_serialize_article(article))
    return {"created": len(results), "articles": results}


@router.post("/rescore")
def rescore_all(db: Session = Depends(get_db)):
    service = IntelligenceService(db)
    count = service.rescore_all()
    return {"rescored": count}


@router.delete("/articles/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db)):
    service = IntelligenceService(db)
    if not service.delete_article(article_id):
        raise HTTPException(status_code=404, detail="Article not found")
    return {"deleted": True}
