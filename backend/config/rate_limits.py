"""
Rate Limiting Configuration Module

Purpose: Centralized rate limit definitions for all API endpoints.
This allows different limits based on endpoint cost and usage patterns.

Pattern: Cost-based rate limiting
- GET (read-only): Higher limits (cheaper, no side effects)
- POST (write): Lower limits (expensive, side effects)
- Task triggers: Very low (triggers background jobs)
- Scraping: Extremely low (hits external APIs)
"""

from dataclasses import dataclass
from typing import Dict

@dataclass
class RateLimitConfig:
    """
    Dataclass for rate limit rules.
    
    Attributes:
        requests (int): Number of requests allowed
        period (str): Time period ('minute', 'hour', 'day')
        description (str): Human-readable description
    
    Example:
        RateLimitConfig(
            requests=100,
            period="minute",
            description="Get paginated posts"
        )
        → Results in: "100/minute" limit
    """
    requests: int
    period: str
    description: str


# Define rate limits by endpoint category
# Format: Key → RateLimitConfig(requests, period, description)
#
# Philosophy:
# 1. Read endpoints (GET): Higher limits (cheap queries, mostly cached)
# 2. Write endpoints (POST/PUT): Lower limits (DB writes, side effects)
# 3. Task triggers: Very low (expensive - calls external APIs)
# 4. Aggregations: Medium (GROUP BY, JOINs are expensive)

RATE_LIMITS: Dict[str, RateLimitConfig] = {
    # ═══════════════════════════════════════════════════════════════════════════
    # 📝 POSTS ENDPOINTS (Reddit data - read-heavy, mostly paginated)
    # ═══════════════════════════════════════════════════════════════════════════
    
    "posts:list": RateLimitConfig(
        requests=100,
        period="minute",
        description="List Reddit posts with pagination - Simple SELECT + ORDER BY"
    ),
    
    "posts:ticker": RateLimitConfig(
        requests=100,
        period="minute",
        description="Get posts by ticker - ARRAY filtering, indexed query"
    ),
    
    "posts:trending": RateLimitConfig(
        requests=50,
        period="minute",
        description="Get trending tickers - GROUP BY + unnest() aggregation (expensive)"
    ),
    
    "posts:sentiment": RateLimitConfig(
        requests=50,
        period="minute",
        description="Aggregate sentiment - AVG, COUNT, SUM calculations"
    ),
    
    "posts:scrape": RateLimitConfig(
        requests=5,
        period="hour",
        description="Manual Reddit scraping - calls external Reddit API (expensive, use sparingly)"
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 💹 STOCKS ENDPOINTS (Market data - read-heavy, heavily cached)
    # ═══════════════════════════════════════════════════════════════════════════
    
    "stocks:prices": RateLimitConfig(
        requests=100,
        period="minute",
        description="Historical stock prices - SELECT with date range filter"
    ),
    
    "stocks:latest": RateLimitConfig(
        requests=200,
        period="minute",
        description="Latest price - Cached (5min TTL), very cheap"
    ),
    
    "stocks:signals": RateLimitConfig(
        requests=100,
        period="minute",
        description="Momentum signals - Cached (5min TTL), calculations done once"
    ),
    
    "stocks:health": RateLimitConfig(
        requests=30,
        period="minute",
        description="Stock health check - COUNT(*) on large table, expensive"
    ),
    
    "stocks:fetch": RateLimitConfig(
        requests=20,
        period="minute",
        description="Manually fetch stock data - Calls yfinance API, external dependency"
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ⚙️  TASK ROUTES (Background jobs - VERY EXPENSIVE!)
    # ═══════════════════════════════════════════════════════════════════════════
    # 
    # These trigger Celery jobs which:
    # - Make external API calls (Reddit, yfinance)
    # - May lock tables
    # - Run in background workers
    # - Have high latency/resource usage
    
    "tasks:fetch_trending": RateLimitConfig(
        requests=5,
        period="hour",
        description="Trigger trending stock fetch - Calls Reddit + yfinance APIs"
    ),
    
    "tasks:fetch_single": RateLimitConfig(
        requests=10,
        period="hour",
        description="Trigger single stock fetch - External API call"
    ),
    
    "tasks:cleanup": RateLimitConfig(
        requests=2,
        period="day",
        description="Trigger data cleanup - DELETE operations, locks tables"
    ),
    
    "tasks:status": RateLimitConfig(
        requests=50,
        period="minute",
        description="Check task status - Read-only, cheap (AsyncResult lookup)"
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 💾 CACHE MANAGEMENT ENDPOINTS
    # ═══════════════════════════════════════════════════════════════════════════
    
    "cache:stats": RateLimitConfig(
        requests=100,
        period="minute",
        description="Cache statistics - O(1) Redis operation, very cheap"
    ),
    
    "cache:invalidate": RateLimitConfig(
        requests=20,
        period="minute",
        description="Invalidate cache - Delete pattern from Redis"
    ),
    
    # ═══════════════════════════════════════════════════════════════════════════
    # 🔐 DEFAULT FALLBACK (Unspecified endpoints)
    # ═══════════════════════════════════════════════════════════════════════════
    
    "default:read": RateLimitConfig(
        requests=100,
        period="minute",
        description="Default read limit for unspecified GET endpoints"
    ),
    
    "default:write": RateLimitConfig(
        requests=30,
        period="minute",
        description="Default write limit for unspecified POST endpoints"
    ),
}


def get_rate_limit(key: str) -> str:
    """
    Get rate limit string in format "requests/period"
    
    This is what slowapi decorator uses: @limiter.limit("100/minute")
    
    Args:
        key (str): Limit key from RATE_LIMITS dict
                  Examples: "posts:list", "stocks:latest", "tasks:fetch_trending"
    
    Returns:
        str: Format "requests/period" (e.g., "100/minute")
    
    Raises:
        None - Falls back to default:read if key not found
    
    Examples:
        >>> get_rate_limit("posts:list")
        "100/minute"
        
        >>> get_rate_limit("tasks:cleanup")
        "2/day"
        
        >>> get_rate_limit("unknown:endpoint")  # Fallback
        "100/minute"
    """
    # Check if key exists in config
    if key not in RATE_LIMITS:
        # Fallback to safe default (conservative limit)
        config = RATE_LIMITS["default:read"]
        print(f"⚠️  Unknown rate limit key '{key}', using default:read")
    else:
        config = RATE_LIMITS[key]
    
    # Construct limit string
    return f"{config.requests}/{config.period}"


def get_period_seconds(period: str) -> int:
    """
    Convert period string to seconds.
    
    This is needed for Redis TTL operations where we set key expiration.
    
    Args:
        period (str): One of "minute", "hour", "day"
    
    Returns:
        int: Number of seconds
    
    Examples:
        >>> get_period_seconds("minute")
        60
        
        >>> get_period_seconds("hour")
        3600
        
        >>> get_period_seconds("day")
        86400
    """
    period_map = {
        "minute": 60,
        "hour": 3600,
        "day": 86400,
    }
    return period_map.get(period, 60)  # Default to minute if unknown
