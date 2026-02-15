"""
Retry and Backoff Utilities

Provides decorators and utilities for resilient API calls with exponential backoff.
Handles rate limits, temporary failures, and network issues gracefully.
"""

import asyncio
import time
import functools
from typing import Callable, Any, TypeVar, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_retries: int = 5,
        base_delay: float = 1.0,  # Start at 1 second
        max_delay: float = 60.0,  # Cap at 1 minute
        exponential_base: float = 2.0,  # 1, 2, 4, 8, 16, 32... seconds
        jitter: bool = True,  # Add randomness to prevent thundering herd
    ):
        """
        Args:
            max_retries: Maximum number of retries (not including initial attempt)
            base_delay: Initial delay in seconds (grows exponentially)
            max_delay: Maximum delay cap (prevents unbounded growth)
            exponential_base: Base for exponential growth (2 = doubling)
            jitter: Add random factor to delay to prevent synchronized retries
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
    
    def get_delay(self, retry_count: int) -> float:
        """Calculate delay for a given retry count
        
        Examples (base_delay=1, exponential_base=2):
            retry 0: 1s
            retry 1: 2s
            retry 2: 4s
            retry 3: 8s
            retry 4: 16s
            retry 5: 32s (if max_delay >= 32)
        """
        # Exponential: base_delay * (exponential_base ^ retry_count)
        raw_delay = self.base_delay * (self.exponential_base ** retry_count)
        
        # Cap at maximum
        delay = min(raw_delay, self.max_delay)
        
        # Add jitter (±10% randomness)
        if self.jitter:
            jitter_factor = 1.0 + (hash(str(time.time())) % 20 - 10) / 100  # ±10%
            delay = delay * jitter_factor
        
        return delay


def should_retry(exception: Exception) -> bool:
    """Determine if an exception should trigger a retry
    
    Returns True for transient errors:
    - Network timeouts
    - Rate limit errors (429)
    - Temporary server errors (5xx)
    - Connection errors
    
    Returns False for permanent errors:
    - Authentication failures (4xx)
    - Invalid input (400)
    - Not found (404)
    """
    
    # Check exception type
    if isinstance(exception, (asyncio.TimeoutError, TimeoutError)):
        return True
    
    if isinstance(exception, ConnectionError):
        return True
    
    # Check for PRAW rate limit (Reddit)
    if hasattr(exception, 'response'):
        status_code = getattr(exception.response, 'status_code', None)
        if status_code == 429:  # Too Many Requests
            logger.warning(f"Rate limited (429), will retry")
            return True
    
    # Check for HTTP/network error attributes
    if hasattr(exception, 'status_code'):
        status_code = exception.status_code
        # Retry on 429, 502, 503, 504
        if status_code in (429, 502, 503, 504):
            logger.warning(f"Transient error {status_code}, will retry")
            return True
        # Don't retry on client errors (400, 401, 403, 404)
        if 400 <= status_code < 500:
            logger.error(f"Client error {status_code}, won't retry")
            return False
    
    # Retry on generic Exception if network-related
    error_msg = str(exception).lower()
    
    # Check for HTTP status codes in error message (e.g., "HTTP 429: Too Many Requests")
    if 'http 429' in error_msg or ('429' in error_msg and 'too many' in error_msg):
        logger.warning("Rate limited (429), will retry")
        return True
    
    if any(status_str in error_msg for status_str in ['http 500', 'http 502', 'http 503', 'http 504', '500', '502', '503', '504']):
        logger.warning(f"Transient server error in message, will retry")
        return True
    
    network_keywords = ['timeout', 'connection', 'refused', 'reset', 'temporarily']
    if any(keyword in error_msg for keyword in network_keywords):
        return True
    
    return False


def retry_with_backoff(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None
) -> Callable[[F], F]:
    """
    Decorator for retrying functions with exponential backoff.
    
    Usage:
        @retry_with_backoff()
        def fetch_data():
            # Will retry up to 5 times with exponential backoff
            pass
        
        @retry_with_backoff(config=RetryConfig(max_retries=3, base_delay=0.5))
        def quick_fetch():
            # Will retry up to 3 times, starting with 0.5 second delays
            pass
    
    Args:
        config: RetryConfig instance (uses defaults if None)
        on_retry: Optional callback for logging/monitoring retries
    
    Returns:
        Decorated function that retries on transient failures
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            # Initial attempt + retries
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if not should_retry(e):
                        logger.error(f"Non-transient error in {func.__name__}: {e}")
                        raise
                    
                    # Check if we've exhausted retries
                    if attempt >= config.max_retries:
                        logger.error(f"Max retries ({config.max_retries}) exhausted for {func.__name__}")
                        raise
                    
                    # Calculate delay and log
                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    # Call callback if provided
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # Should not reach here, but just in case
            raise last_exception or RuntimeError(f"Unexpected error in {func.__name__}")
        
        return wrapper  # type: ignore
    
    return decorator


def retry_with_backoff_async(
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable] = None
) -> Callable[[F], F]:
    """
    Async version of retry_with_backoff decorator.
    
    Usage:
        @retry_with_backoff_async()
        async def fetch_data():
            # Will retry with exponential backoff (async)
            pass
    
    Args:
        config: RetryConfig instance (uses defaults if None)
        on_retry: Optional callback for logging/monitoring retries
    
    Returns:
        Decorated async function that retries on transient failures
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            # Initial attempt + retries
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if not should_retry(e):
                        logger.error(f"Non-transient error in {func.__name__}: {e}")
                        raise
                    
                    # Check if we've exhausted retries
                    if attempt >= config.max_retries:
                        logger.error(f"Max retries ({config.max_retries}) exhausted for {func.__name__}")
                        raise
                    
                    # Calculate delay and log
                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    # Call callback if provided
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    # Wait before retry (async)
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            raise last_exception or RuntimeError(f"Unexpected error in {func.__name__}")
        
        return wrapper  # type: ignore
    
    return decorator


class RateLimiter:
    """
    Simple rate limiter to avoid overwhelming APIs.
    
    Tracks requests and enforces minimum delay between calls.
    Useful for Reddit (60 req/min) and yfinance (general best practices).
    
    Usage:
        limiter = RateLimiter(requests_per_minute=20)
        
        @limiter.rate_limit
        def fetch_data():
            pass
    """
    
    def __init__(self, requests_per_minute: int = 60):
        """
        Args:
            requests_per_minute: Max requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.min_delay = 60.0 / requests_per_minute  # Delay between requests
        self.last_request_time = None
    
    def wait_if_needed(self) -> None:
        """Wait if necessary to respect rate limit"""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return
        
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def wait_if_needed_async(self) -> None:
        """Async version of wait_if_needed"""
        if self.last_request_time is None:
            self.last_request_time = time.time()
            return
        
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            wait_time = self.min_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()


# Preset configs for common scenarios
REDDIT_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=2.0,  # Reddit rate limits, start with 2 seconds
    max_delay=120.0,  # Cap at 2 minutes
)

YFINANCE_CONFIG = RetryConfig(
    max_retries=3,
    base_delay=1.0,
    max_delay=30.0,
)

GENERIC_CONFIG = RetryConfig(
    max_retries=5,
    base_delay=1.0,
    max_delay=60.0,
)
