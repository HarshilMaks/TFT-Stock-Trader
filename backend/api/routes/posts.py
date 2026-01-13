from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text
from backend.models.reddit import RedditPost
from backend.database.config import get_db
from backend.api.schemas.posts import PostListResponse, PostByTickerResponse, TrendingResponse

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("/", response_model=PostListResponse)
async def get_posts(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
) -> PostListResponse:
    """Get paginated Reddit posts"""
    result = await db.execute(
        select(RedditPost)
        .order_by(desc(RedditPost.score))
        .offset(skip)
        .limit(limit)
    )
    
    posts = result.scalars().all()
    
    return PostListResponse(  # type: ignore
        count=len(posts),
        posts=[
            {
                "id": post.id,
                "title": post.title,
                "tickers": post.tickers or [],
                "sentiment_score": post.sentiment_score or 0.0,  # type: ignore
                "score": post.score or 0,
                "url": post.url,
                "created_at": post.created_at
            }
            for post in posts
        ]
    )
    
@router.get("/ticker/{ticker}", response_model=PostByTickerResponse)
async def get_posts_by_ticker(
    ticker: str, 
    db: AsyncSession = Depends(get_db), 
    limit: int = Query(20, ge=1, le=100)
) -> PostByTickerResponse:
    
    """Get posts mentioning specific ticker"""
    result = await db.execute(
        select(RedditPost)
        .where(RedditPost.tickers.contains([ticker.upper()]))
        .order_by(desc(RedditPost.score))
        .limit(limit)
    )
    
    posts = result.scalars().all()
    
    return PostByTickerResponse(
        ticker=ticker.upper(),
        count=len(posts),
        posts=[
            {
                "title": post.title,
                "sentiment_score": post.sentiment_score or 0.0,  # type: ignore
                "score": post.score or 0,
                "url": post.url
            }
            for post in posts
        ]
    )
    
@router.get("/trending", response_model=TrendingResponse)
async def get_trending_tickers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50)
) -> TrendingResponse:
    """Get most mentioned tickers"""
    query = text("""
        SELECT ticker, COUNT(*) as mentions
        FROM reddit_posts, unnest(tickers) as ticker
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {"limit": limit})
    
    trending = [{"ticker": row[0], "mentions": row[1]} for row in result]
    return TrendingResponse(trending=trending)  # type: ignore
    