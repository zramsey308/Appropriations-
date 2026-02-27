import json
import re
import logging
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.news_article import NewsArticle

logger = logging.getLogger(__name__)

# TX-11 specific keywords for relevance scoring
TX11_KEYWORDS = [
    "pfluger", "tx-11", "tx 11", "texas 11", "district 11",
    "midland", "odessa", "san angelo", "permian basin",
    "ector county", "tom green county", "midland county",
    "concho valley", "big spring", "pecos", "fort stockton",
]

APPROPRIATIONS_KEYWORDS = [
    "appropriations", "funding", "cpf", "community project",
    "earmark", "federal funding", "fy2027", "fy 2027", "fy27",
    "budget", "spending bill", "omnibus", "minibus",
    "subcommittee", "markup", "allocation",
    "energy and water", "defense", "agriculture",
    "commerce justice science", "homeland security",
    "interior", "labor hhs", "military construction",
    "transportation hud", "financial services",
]

POLICY_KEYWORDS = [
    "water infrastructure", "oil and gas", "energy",
    "border security", "military", "veterans",
    "agriculture", "ranching", "drought",
    "air force", "goodfellow", "dyess",
]

ENDORSEMENT_KEYWORDS = [
    "endorse", "endorsement", "endorsed", "endorses",
    "backs", "backing", "supported by", "supports",
    "throws support", "rallies behind",
]


def compute_relevance_score(article: NewsArticle) -> tuple[float, list[str]]:
    """Score an article 0-10 for relevance to TX-11 appropriations work."""
    score = 0.0
    flags = []
    text = f"{article.title} {article.summary or ''}".lower()

    # District match (strongest signal)
    if article.district and article.district.upper() == "TX-11":
        score += 4.0
        flags.append("TX-11 district match")
    elif article.district and article.district.upper().startswith("TX-"):
        score += 1.5
        flags.append(f"Texas district ({article.district})")

    # TX-11 keyword matches
    tx11_hits = [kw for kw in TX11_KEYWORDS if kw in text]
    if tx11_hits:
        score += min(3.0, len(tx11_hits) * 1.0)
        flags.append(f"TX-11 keywords: {', '.join(tx11_hits[:3])}")

    # Appropriations keywords
    approp_hits = [kw for kw in APPROPRIATIONS_KEYWORDS if kw in text]
    if approp_hits:
        score += min(2.0, len(approp_hits) * 0.5)
        flags.append(f"Appropriations: {', '.join(approp_hits[:3])}")

    # Policy keywords
    policy_hits = [kw for kw in POLICY_KEYWORDS if kw in text]
    if policy_hits:
        score += min(1.5, len(policy_hits) * 0.5)
        flags.append(f"Policy: {', '.join(policy_hits[:3])}")

    # Endorsement boost
    endorsement_hits = [kw for kw in ENDORSEMENT_KEYWORDS if kw in text]
    if endorsement_hits:
        score += 1.0
        flags.append("Endorsement content")

    # Category boosts
    if article.category == "appropriations":
        score += 2.0
        flags.append("Appropriations category")
    elif article.category == "policy":
        score += 0.5
    elif article.category == "endorsement":
        score += 0.5

    # Recency boost (articles from last 7 days get a boost)
    if article.published_at:
        days_old = (datetime.utcnow() - article.published_at).days
        if days_old <= 1:
            score += 1.0
            flags.append("Breaking (today)")
        elif days_old <= 3:
            score += 0.5
            flags.append("Recent (3 days)")
        elif days_old <= 7:
            score += 0.25

    return min(10.0, round(score, 1)), flags


class IntelligenceService:
    def __init__(self, db: Session):
        self.db = db

    def create_article(self, data: dict) -> NewsArticle:
        article = NewsArticle(**data)
        # Auto-detect endorsement
        text = f"{article.title} {article.summary or ''}".lower()
        if any(kw in text for kw in ENDORSEMENT_KEYWORDS):
            article.is_endorsement = True
        if article.category == "endorsement":
            article.is_endorsement = True
        # Compute relevance
        score, flags = compute_relevance_score(article)
        article.relevance_score = score
        article.relevance_flags = json.dumps(flags)
        self.db.add(article)
        self.db.commit()
        self.db.refresh(article)
        return article

    def list_articles(
        self,
        district: Optional[str] = None,
        category: Optional[str] = None,
        sentiment: Optional[str] = None,
        min_relevance: Optional[float] = None,
        endorsements_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[NewsArticle], int]:
        query = self.db.query(NewsArticle)
        if district:
            query = query.filter(NewsArticle.district == district.upper())
        if category:
            query = query.filter(NewsArticle.category == category)
        if sentiment:
            query = query.filter(NewsArticle.sentiment == sentiment)
        if min_relevance is not None:
            query = query.filter(NewsArticle.relevance_score >= min_relevance)
        if endorsements_only:
            query = query.filter(NewsArticle.is_endorsement == True)
        total = query.count()
        items = query.order_by(desc(NewsArticle.relevance_score), desc(NewsArticle.published_at)).offset(skip).limit(limit).all()
        return items, total

    def get_summary(self) -> dict:
        total = self.db.query(NewsArticle).count()
        high_relevance = self.db.query(NewsArticle).filter(NewsArticle.relevance_score >= 5.0).count()
        endorsement_count = self.db.query(NewsArticle).filter(NewsArticle.is_endorsement == True).count()

        # Sentiment breakdown
        sentiment_counts = {}
        for sent, count in self.db.query(NewsArticle.sentiment, func.count(NewsArticle.id)).group_by(NewsArticle.sentiment).all():
            sentiment_counts[sent] = count

        # Category breakdown
        category_counts = {}
        for cat, count in self.db.query(NewsArticle.category, func.count(NewsArticle.id)).group_by(NewsArticle.category).all():
            category_counts[cat] = count

        # District breakdown
        district_counts = {}
        for dist, count in self.db.query(NewsArticle.district, func.count(NewsArticle.id)).group_by(NewsArticle.district).all():
            if dist:
                district_counts[dist] = count

        # Average relevance
        avg_relevance = self.db.query(func.avg(NewsArticle.relevance_score)).scalar() or 0

        # Recent endorsements (last 30 days)
        cutoff = datetime.utcnow() - timedelta(days=30)
        recent_endorsements = (
            self.db.query(NewsArticle)
            .filter(NewsArticle.is_endorsement == True)
            .filter(NewsArticle.published_at >= cutoff)
            .order_by(desc(NewsArticle.published_at))
            .limit(10)
            .all()
        )

        return {
            "total_articles": total,
            "high_relevance_count": high_relevance,
            "endorsement_count": endorsement_count,
            "avg_relevance": round(float(avg_relevance), 1),
            "by_sentiment": sentiment_counts,
            "by_category": category_counts,
            "by_district": district_counts,
            "recent_endorsements": [
                {
                    "id": e.id,
                    "title": e.title,
                    "source": e.source,
                    "district": e.district,
                    "relevance_score": e.relevance_score,
                    "published_at": e.published_at.isoformat() if e.published_at else None,
                    "mentioned_members": e.mentioned_members,
                }
                for e in recent_endorsements
            ],
        }

    def rescore_all(self) -> int:
        """Recompute relevance scores for all articles."""
        articles = self.db.query(NewsArticle).all()
        for article in articles:
            score, flags = compute_relevance_score(article)
            article.relevance_score = score
            article.relevance_flags = json.dumps(flags)
        self.db.commit()
        return len(articles)

    def delete_article(self, article_id: int) -> bool:
        article = self.db.query(NewsArticle).filter(NewsArticle.id == article_id).first()
        if not article:
            return False
        self.db.delete(article)
        self.db.commit()
        return True
