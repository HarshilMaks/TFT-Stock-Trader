import asyncio
from backend.database.config import async_session
from backend.services.reddit_service import RedditService


async def test():
    service = RedditService()
    
    print("🚀 Starting Reddit scraper test...")
    
    async with async_session() as db:
        stats = await service.scrape_and_save(db, 'wallstreetbets', limit=50)
        
        print("\n✅ Scraping complete!")
        print(f"📊 Stats:")
        print(f"   - Fetched: {stats['total_fetched']} posts")
        print(f"   - Saved: {stats['saved']} posts with tickers")
        print(f"   - Skipped: {stats['skipped']} posts (duplicates or no tickers)")
        print(f"   - Failed: {stats['failed']} posts")


if __name__ == "__main__":
    asyncio.run(test())
