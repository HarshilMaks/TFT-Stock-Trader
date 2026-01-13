from pydantic import BaseModel
from datetime import datetime


class PostResponse(BaseModel):
    id: int
    title: str
    tickers: list[str]
    sentiment_score: float
    score: int
    url: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    count: int
    posts: list[PostResponse]


class PostByTickerResponse(BaseModel):
    ticker: str
    count: int
    posts: list[dict]  # Simplified posts


class TrendingTicker(BaseModel):
    ticker: str
    mentions: int


class TrendingResponse(BaseModel):
    trending: list[TrendingTicker]
