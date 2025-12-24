from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Literal
from backend.models.reddit import RedditPost
from backend.scrapers.reddit_scraper import RedditScraper, PostType
from backend.utils.ticker_extractor import extract_tickers
from backend.utils.sentiment import analyze_sentiment


class RedditService:
    """
    Service layer for Reddit data operations.
    Handles business logic: scraping → extraction → storage.
    Targets: r/wallstreetbets, r/stocks, r/options
    """
    
    # Target subreddits for stock discussion
    DEFAULT_SUBREDDITS = ['wallstreetbets', 'stocks', 'options']
    
    def __init__(self):
        self.scraper = RedditScraper()
    
    async def scrape_and_save(
        self, 
        db: AsyncSession, 
        subreddits: Optional[list[str]] = None,
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day'
    ) -> dict[str, int | dict[str, dict[str, int]]]:
        """
        Scrape Reddit posts from multiple subreddits and save to database with sentiment analysis.
        
        Args:
            db: Database session
            subreddits: List of subreddits to scrape (defaults to wallstreetbets, stocks, options)
            limit: Number of posts to fetch per subreddit
            post_type: Type of posts ('hot', 'new', 'rising', 'top')
            time_filter: For 'top' posts ('hour', 'day', 'week', 'month', 'year', 'all')
        
        Returns:
            Dictionary with stats: saved, skipped, failed, by_subreddit
        """
        if subreddits is None:
            subreddits = self.DEFAULT_SUBREDDITS
        
        total_saved = 0
        total_skipped = 0
        total_failed = 0
        total_fetched = 0
        subreddit_stats = {}
        
        for subreddit in subreddits:
            print(f"Scraping r/{subreddit} ({post_type} posts)...")
            
            posts = self.scraper.scrape_posts(subreddit, limit, post_type, time_filter)
            saved_count = 0
            skipped_count = 0
            failed_count = 0
            
            for post_data in posts:
                try:
                    # Extract tickers from title + body
                    text = f"{post_data['title']} {post_data['body']}"
                    tickers = extract_tickers(text)
                    
                    # Skip posts with no stock mentions
                    if not tickers:
                        skipped_count += 1
                        continue
                    
                    # Check if post already exists (avoid duplicates)
                    result = await db.execute(
                        select(RedditPost).where(RedditPost.post_id == post_data['post_id'])
                    )
                    if result.scalar_one_or_none():
                        skipped_count += 1
                        continue
                    
                    # Calculate sentiment score
                    sentiment_score = analyze_sentiment(text)
                    
                    # Create database record
                    db_post = RedditPost(
                        post_id=post_data['post_id'],
                        subreddit=post_data['subreddit'],
                        title=post_data['title'],
                        body=post_data['body'],
                        author=post_data['author'],
                        score=post_data['score'],
                        num_comments=post_data['num_comments'],
                        tickers=tickers,
                        sentiment_score=sentiment_score,
                        created_at=post_data['created_at'],
                        url=post_data['url']
                    )
                    
                    db.add(db_post)
                    saved_count += 1
                    
                except Exception as e:
                    print(f"Error processing post {post_data.get('post_id')}: {e}")
                    failed_count += 1
                    continue
            
            # Track stats per subreddit
            subreddit_stats[subreddit] = {
                'saved': saved_count,
                'skipped': skipped_count,
                'failed': failed_count,
                'fetched': len(posts)
            }
            
            total_saved += saved_count
            total_skipped += skipped_count
            total_failed += failed_count
            total_fetched += len(posts)
            
            print(f"r/{subreddit}: {saved_count} saved, {skipped_count} skipped, {failed_count} failed")
        
        # Commit all at once (transaction)
        await db.commit()
        
        return {
            'saved': total_saved,
            'skipped': total_skipped,
            'failed': total_failed,
            'total_fetched': total_fetched,
            'by_subreddit': subreddit_stats
        }
