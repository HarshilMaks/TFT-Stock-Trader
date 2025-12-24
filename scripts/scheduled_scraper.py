#!/usr/bin/env python3
"""
Automated Reddit Scraper with Scheduling
Runs continuously and scrapes Reddit at configured intervals
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.database.config import AsyncSessionLocal
from backend.services.reddit_service import RedditService
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ScheduledRedditScraper:
    """
    Automated scraper that runs on a schedule
    """
    
    def __init__(self):
        self.service = RedditService()
        self.scheduler = AsyncIOScheduler()
        
    async def scrape_job(self, post_type: str = 'hot'):
        """
        Single scrape job - fetches and saves posts
        """
        try:
            logger.info(f"Starting scheduled scrape ({post_type} posts)...")
            
            async with AsyncSessionLocal() as db:
                stats = await self.service.scrape_and_save(
                    db=db,
                    post_type=post_type,  # type: ignore
                    limit=100
                )
                
                logger.info(
                    f"Scrape completed: {stats['saved']} saved, "
                    f"{stats['skipped']} skipped, {stats['failed']} failed"
                )
                
                # Log per-subreddit stats
                for subreddit, sub_stats in stats['by_subreddit'].items():  # type: ignore
                    logger.info(f"  r/{subreddit}: {sub_stats}")
                    
        except Exception as e:
            logger.error(f"Scrape job failed: {e}", exc_info=True)
    
    def setup_schedule(self):
        """
        Configure scraping schedules
        
        Schedule:
        - Hot posts: Every 2 hours
        - New posts: Every 30 minutes
        - Rising posts: Every hour
        - Top daily: Once per day at 11 PM
        """
        # Hot posts - every 2 hours
        self.scheduler.add_job(
            self.scrape_job,
            trigger=CronTrigger(minute=0, hour='*/2'),  # Every 2 hours
            args=['hot'],
            id='scrape_hot',
            name='Scrape hot posts',
            replace_existing=True
        )
        
        # New posts - every 30 minutes
        self.scheduler.add_job(
            self.scrape_job,
            trigger=CronTrigger(minute='*/30'),  # Every 30 min
            args=['new'],
            id='scrape_new',
            name='Scrape new posts',
            replace_existing=True
        )
        
        # Rising posts - every hour
        self.scheduler.add_job(
            self.scrape_job,
            trigger=CronTrigger(minute=0),  # Every hour
            args=['rising'],
            id='scrape_rising',
            name='Scrape rising posts',
            replace_existing=True
        )
        
        # Top daily - once per day at 11 PM
        self.scheduler.add_job(
            self.scrape_job,
            trigger=CronTrigger(hour=23, minute=0),  # 11 PM daily
            args=['top'],
            id='scrape_top',
            name='Scrape top daily posts',
            replace_existing=True
        )
        
        logger.info("Scraping schedule configured:")
        logger.info("  - Hot posts: Every 2 hours")
        logger.info("  - New posts: Every 30 minutes")
        logger.info("  - Rising posts: Every hour")
        logger.info("  - Top daily: 11 PM daily")
    
    async def run_once(self):
        """Run scraper once immediately (for testing)"""
        logger.info("Running single scrape...")
        await self.scrape_job('hot')
        logger.info("Single scrape completed")
    
    async def start(self):
        """Start the scheduler"""
        self.setup_schedule()
        self.scheduler.start()
        logger.info("Scheduler started. Press Ctrl+C to stop.")
        
        # Run initial scrape immediately
        await self.scrape_job('hot')
        
        # Keep running
        try:
            while True:
                await asyncio.sleep(3600)  # Sleep for 1 hour
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown()


async def main():
    """Main entry point"""
    scraper = ScheduledRedditScraper()
    
    # Check command line args
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        # Run once for testing
        await scraper.run_once()
    else:
        # Run continuously with scheduler
        await scraper.start()


if __name__ == '__main__':
    asyncio.run(main())
