from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean

from app.db import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id = Column(Integer, primary_key=True, index=True)

    # Core fields
    title = Column(String(1000), nullable=False)
    source = Column(String(255), nullable=False)
    url = Column(String(2000), nullable=True)
    summary = Column(Text, nullable=True)

    # Classification
    district = Column(String(20), nullable=True, index=True)      # e.g. "TX-11", "TX-19"
    category = Column(String(50), nullable=False, index=True)      # campaign, endorsement, policy, scandal, polling, fundraising, appropriations
    sentiment = Column(String(20), nullable=False, default="neutral")  # positive, negative, neutral, mixed
    is_endorsement = Column(Boolean, default=False, index=True)

    # Relevance scoring
    relevance_score = Column(Float, default=0.0, index=True)       # 0-10 computed score
    relevance_flags = Column(Text, nullable=True)                   # JSON list of matched keywords/reasons

    # Entities mentioned
    mentioned_members = Column(Text, nullable=True)                 # comma-separated names
    mentioned_orgs = Column(Text, nullable=True)                    # comma-separated org names

    # Timestamps
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
