from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text, func
from backend.models.reddit import RedditPost
from backend.database.config import get_db
from backend.api.schemas.posts import PostListResponse, PostByTickerResponse, TrendingResponse, TickerSentiment

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("/", response_model=PostListResponse)
async def get_posts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),  # Changed from skip
    page_size: int = Query(20, ge=1, le=100)  # Changed from limit
) -> PostListResponse:
    """Get paginated Reddit posts"""
    
    # Calculate offset
    skip = (page - 1) * page_size
    
    # Get total count
    count_result = await db.execute(select(func.count(RedditPost.id)))
    total = count_result.scalar() or 0
    
    # Get posts
    result = await db.execute(
        select(RedditPost)
        .order_by(desc(RedditPost.score))
        .offset(skip)
        .limit(page_size)
    )
    
    posts = result.scalars().all()
    
    return PostListResponse(
        total=total,
        page=page,
        page_size=page_size,
        posts=[
            {
                "id": post.id,
                "title": post.title,
                "tickers": post.tickers or [],
                "sentiment_score": post.sentiment_score or 0.0,
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


@router.get("/sentiment/{ticker}", response_model=TickerSentiment)
async def get_ticker_sentiment(
    ticker: str,
    db: AsyncSession = Depends(get_db)
) -> TickerSentiment:  # Changed return type
    """Get aggregated sentiment for a specific ticker"""
    result = await db.execute(
        select(
            func.avg(RedditPost.sentiment_score).label('avg_sentiment'),
            func.count(RedditPost.id).label('post_count'),
            func.sum(RedditPost.score).label('total_engagement')
        ).where(RedditPost.tickers.contains([ticker.upper()]))
    )
    
    row = result.first()
    
    if not row or row.post_count == 0:
        return TickerSentiment(
            ticker=ticker.upper(),
            sentiment="No data",
            avg_score=0.0,
            post_count=0,
            total_engagement=0
        )
    
    avg_sentiment = float(row.avg_sentiment) if row.avg_sentiment else 0.0
    
    # Determine sentiment label
    if avg_sentiment >= 0.05:
        label = "bullish"
    elif avg_sentiment <= -0.05:
        label = "bearish"
    else:
        label = "neutral"
    
    return TickerSentiment(
        ticker=ticker.upper(),
        sentiment=label,
        avg_score=round(avg_sentiment, 3),
        post_count=row.post_count,
        total_engagement=row.total_engagement or 0
    )
    