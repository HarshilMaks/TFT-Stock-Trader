from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class PostResponse(BaseModel):
    id: int
    title: str
    tickers: list[str]
    sentiment_score: float = Field(..., ge=-1.0, le=1.0, description="Sentiment score from -1 to 1")
    score: int
    url: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class PostListResponse(BaseModel):
    total: int  # Total posts in DB (not just this page)
    page: int
    page_size: int
    posts: list[PostResponse]


class PostByTickerResponse(BaseModel):
    ticker: str
    count: int
    posts: list[dict]


class TickerSentiment(BaseModel):
    ticker: str
    sentiment: str  # bullish/bearish/neutral/No data
    avg_score: float = Field(..., ge=-1.0, le=1.0)
    post_count: int = Field(..., ge=0)
    total_engagement: int = Field(..., ge=0)

class TrendingTicker(BaseModel):
    ticker: str
    mentions: int

class TrendingResponse(BaseModel):
    trending: list[TrendingTicker]

class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None