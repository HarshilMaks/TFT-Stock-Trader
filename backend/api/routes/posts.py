from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, text, func
from backend.models.reddit import RedditPost
from backend.database.config import get_db
from backend.api.schemas.posts import PostListResponse, PostByTickerResponse, TrendingResponse, TickerSentiment
from backend.api.middleware.rate_limit import check_rate_limit
from backend.config.rate_limits import RATE_LIMITS, get_period_seconds
from backend.scrapers.reddit_scraper import RedditScraper
from backend.utils.logger import get_logger
from pydantic import BaseModel

logger = get_logger(__name__)

# Response model for scrape endpoint
class ScrapeResponse(BaseModel):
    subreddit: str
    fetched: int
    saved: int
    skipped: int
    message: str

router = APIRouter(prefix="/posts", tags=["posts"])


# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMIT DEPENDENCY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
#
# Each endpoint has a corresponding rate limit function.
# These encapsulate the rate limit configuration for that endpoint.
# Usage: add async def limit_X(req: Request) and then use Depends(limit_X)
#
# Why separate functions?
# 1. Cleaner code (doesn't clutter endpoint function signature)
# 2. Reusable (same limit function can be used by multiple endpoints if needed)
# 3. Configurable (change limits in one place, update function, done)


async def rate_limit_posts_list(request: Request):
    """
    Rate limit: GET /posts/ endpoint
    
    Limit: 100 requests per minute per IP address
    
    Rationale:
    - This is a simple paginated SELECT query
    - Relatively cheap (indexed sort by score, offset/limit)
    - Common operation users will call frequently
    - No side effects, safe to have higher limits
    
    Endpoint cost: 🟢 LOW (cacheable reads)
    """
    config = RATE_LIMITS["posts:list"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:list",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_ticker(request: Request):
    """
    Rate limit: GET /posts/ticker/{ticker} endpoint
    
    Limit: 100 requests per minute per IP address
    
    Rationale:
    - ARRAY containment filter (WHERE tickers[] CONTAINS 'AAPL')
    - Uses GIN index on tickers column for fast lookups
    - Same cost as list endpoint
    
    Endpoint cost: 🟢 LOW (indexed array filter)
    """
    config = RATE_LIMITS["posts:ticker"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:ticker",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_trending(request: Request):
    """
    Rate limit: GET /posts/trending endpoint
    
    Limit: 50 requests per minute per IP address
    
    Rationale:
    - GROUP BY aggregation: scans entire table, groups by ticker
    - unnest() ARRAY operation: expensive (expands arrays into rows)
    - COUNT(*) for each group: additional computation
    - More expensive than simple list query → lower limit
    
    This is a heavier query, not something you call many times per minute.
    
    Endpoint cost: 🟡 MEDIUM (GROUP BY + aggregation)
    
    Query example:
        SELECT ticker, COUNT(*) as mentions
        FROM reddit_posts, unnest(tickers) as ticker
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT 10
    
    Cost: O(n) where n = total rows in reddit_posts
    """
    config = RATE_LIMITS["posts:trending"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:trending",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_sentiment(request: Request):
    """
    Rate limit: GET /posts/sentiment/{ticker} endpoint
    
    Limit: 50 requests per minute per IP address
    
    Rationale:
    - Multiple aggregate functions: AVG(), COUNT(), SUM()
    - Scans table for matching ticker
    - Three calculations per row
    - Similar cost to trending endpoint
    
    Endpoint cost: 🟡 MEDIUM (aggregations)
    
    Query example:
        SELECT AVG(sentiment_score), COUNT(*), SUM(score)
        FROM reddit_posts
        WHERE tickers[] CONTAINS 'AAPL'
    """
    config = RATE_LIMITS["posts:sentiment"]
    period_seconds = get_period_seconds(config.period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:sentiment",
        limit=config.requests,
        period_seconds=period_seconds
    )


async def rate_limit_posts_scrape(request: Request):
    """
    Rate limit: POST /posts/scrape/{subreddit} endpoint
    
    Limit: 5 requests per hour per IP address
    
    Rationale:
    - This is an expensive API call to Reddit
    - Rate limited by Reddit (60 requests per minute max)
    - Each scrape call fetches 100+ posts
    - Should NOT be called frequently by one user
    - Reserved for manual testing / admin only
    
    Endpoint cost: 🔴 HIGH (external API call, network I/O)
    """
    config = RATE_LIMITS.get("posts:scrape")
    if not config:
        # Fallback if config not found
        config_requests = 5
        config_period = "hour"
    else:
        config_requests = config.requests
        config_period = config.period
    
    period_seconds = get_period_seconds(config_period)
    
    return await check_rate_limit(
        request=request,
        endpoint_key="posts:scrape",
        limit=config_requests,
        period_seconds=period_seconds
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS WITH RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/scrape/{subreddit}", response_model=ScrapeResponse)
async def scrape_subreddit(
    subreddit: str,
    limit: int = Query(100, ge=10, le=500),
    db: AsyncSession = Depends(get_db),
    _rate_limit = Depends(rate_limit_posts_scrape)
) -> ScrapeResponse:
    """
    Manually trigger Reddit scraping for a specific subreddit.
    
    **IMPORTANT**: This endpoint calls the real Reddit API.
    - Rate limited: 5 times per hour per IP address
    - Each call fetches up to {limit} posts from subreddit
    - Posts with duplicates will be skipped
    
    Usage:
        POST /api/posts/scrape/wallstreetbets?limit=100
    
    Response:
        {
            "subreddit": "wallstreetbets",
            "fetched": 100,
            "saved": 85,
            "skipped": 15,
            "message": "Successfully scraped r/wallstreetbets"
        }
    
    Args:
        subreddit: Name of subreddit (without 'r/' prefix)
        limit: Number of posts to fetch (10-500, default 100)
    
    Returns:
        ScrapeResponse with count of fetched, saved, and skipped posts
    
    Raises:
        HTTPException 429: Rate limit exceeded
        HTTPException 500: Reddit API error or database error
    """
    try:
        logger.info(f"🔄 Starting scrape for r/{subreddit} (limit={limit})")
        
        # Step 1: Scrape from Reddit
        scraper = RedditScraper()
        posts = scraper.scrape_posts(subreddit, limit=limit)
        
        if not posts:
            return ScrapeResponse(
                subreddit=subreddit,
                fetched=0,
                saved=0,
                skipped=0,
                message=f"No posts found in r/{subreddit}"
            )
        
        logger.info(f"✅ Fetched {len(posts)} posts from r/{subreddit}")
        
        # Step 2: Check for duplicates and save to database
        saved_count = 0
        skipped_count = 0
        
        for post_data in posts:
            try:
                # Check if post already exists
                existing = await db.execute(
                    select(RedditPost).where(RedditPost.post_id == post_data['post_id'])
                )
                
                if existing.scalar_one_or_none():
                    skipped_count += 1
                    logger.debug(f"⏭️  Skipped duplicate post: {post_data['post_id']}")
                    continue
                
                # Create new post record
                reddit_post = RedditPost(
                    post_id=post_data['post_id'],
                    subreddit=post_data['subreddit'],
                    title=post_data['title'],
                    body=post_data['body'],
                    author=post_data['author'],
                    score=post_data['score'],
                    num_comments=post_data['num_comments'],
                    upvote_ratio=post_data['upvote_ratio'],
                    created_at=post_data['created_at'],
                    url=post_data['url'],
                    is_self=post_data['is_self'],
                    link_flair_text=post_data['link_flair_text'],
                    tickers=[],  # Will be extracted by sentiment service
                    sentiment_score=None  # Will be calculated by sentiment service
                )
                
                db.add(reddit_post)
                saved_count += 1
                logger.debug(f"✏️  Added post: {post_data['post_id']}")
                
            except Exception as e:
                logger.error(f"❌ Error saving post {post_data.get('post_id')}: {e}")
                continue
        
        # Step 3: Commit all saves
        await db.commit()
        logger.info(f"✅ Saved {saved_count} posts to database")
        
        return ScrapeResponse(
            subreddit=subreddit,
            fetched=len(posts),
            saved=saved_count,
            skipped=skipped_count,
            message=f"Successfully scraped r/{subreddit}: {saved_count} new posts saved"
        )
        
    except Exception as e:
        logger.error(f"❌ Error scraping r/{subreddit}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape r/{subreddit}: {str(e)}")


@router.get("/", response_model=PostListResponse)
async def get_posts(
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _rate_limit = Depends(rate_limit_posts_list)  # ← Rate limit check happens here
) -> PostListResponse:
    """
    Get paginated Reddit posts
    
    Rate limited: 100 requests per minute per IP
    
    How rate limiting works:
    1. FastAPI calls Depends(rate_limit_posts_list)
    2. rate_limit_posts_list(request) is invoked
    3. check_rate_limit() is awaited:
       - Extracts client IP from request
       - Gets Redis client from app.state
       - Increments "ratelimit:posts:list:{ip}" counter in Redis
       - If counter > 100: raises HTTPException(429)
       - If counter <= 100: returns rate limit info
    4. If no exception: endpoint logic runs normally
    5. If exception: FastAPI returns JSON error response
    
    The _rate_limit parameter:
    - Name starts with _ to indicate it's internal (not user-provided)
    - We don't use it in the function (just ensure it's checked)
    - FastAPI still calls Depends() and waits for result
    - If 429 is raised, endpoint code never runs
    """
    
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
    limit: int = Query(20, ge=1, le=100),
    _rate_limit = Depends(rate_limit_posts_ticker)  # ← Rate limit check
) -> PostByTickerResponse:
    """
    Get posts mentioning specific ticker
    
    Rate limited: 100 requests per minute per IP
    """
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
                "sentiment_score": post.sentiment_score or 0.0,
                "score": post.score or 0,
                "url": post.url
            }
            for post in posts
        ]
    )
    

@router.get("/trending", response_model=TrendingResponse)
async def get_trending_tickers(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(10, ge=1, le=50),
    _rate_limit = Depends(rate_limit_posts_trending)  # ← Rate limit check
) -> TrendingResponse:
    """
    Get most mentioned tickers (aggregation - more expensive)
    
    Rate limited: 50 requests per minute per IP (lower than simple reads)
    
    This endpoint uses GROUP BY which requires scanning entire reddit_posts table.
    The GROUP BY + unnest() is more expensive than simple filtered reads.
    Therefore: 50/min instead of 100/min
    """
    query = text("""
        SELECT ticker, COUNT(*) as mentions
        FROM reddit_posts, unnest(tickers) as ticker
        GROUP BY ticker
        ORDER BY mentions DESC
        LIMIT :limit
    """)
    result = await db.execute(query, {"limit": limit})
    
    trending = [{"ticker": row[0], "mentions": row[1]} for row in result]
    return TrendingResponse(trending=trending)


@router.get("/sentiment/{ticker}", response_model=TickerSentiment)
async def get_ticker_sentiment(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    _rate_limit = Depends(rate_limit_posts_sentiment)  # ← Rate limit check
) -> TickerSentiment:
    """
    Get aggregated sentiment for a specific ticker
    
    Rate limited: 50 requests per minute per IP
    
    This endpoint performs multiple aggregations (AVG, COUNT, SUM).
    More expensive than simple reads, so lower limit.
    """
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
