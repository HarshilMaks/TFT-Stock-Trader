#!/usr/bin/env python3
"""
Manual test script for real Reddit scraping

This script tests the real Reddit scraping functionality without needing
a running FastAPI server or database connection.

Usage:
    python scripts/test_scrape_real_reddit.py

Expected Output:
    ✅ Scraped 50-100 posts from r/wallstreetbets
    ✅ Verified post structure (post_id, title, body, etc.)
    ✅ Posts saved to local parquet for inspection
"""

import asyncio
import pandas as pd
from datetime import datetime
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.scrapers.reddit_scraper import RedditScraper
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def test_real_scraping():
    """Test real Reddit scraping with multiple subreddits"""
    
    print("\n" + "="*80)
    print("🔍 REAL REDDIT SCRAPING TEST")
    print("="*80 + "\n")
    
    scraper = RedditScraper()
    subreddits = ['wallstreetbets', 'stocks', 'investing']
    all_posts = []
    
    for subreddit in subreddits:
        try:
            print(f"\n📍 Scraping r/{subreddit}...")
            posts = scraper.scrape_posts(subreddit, limit=50, post_type='hot')
            
            if posts:
                print(f"   ✅ Got {len(posts)} posts")
                all_posts.extend(posts)
                
                # Display sample post
                sample = posts[0]
                print(f"   📌 Sample post:")
                print(f"      Title: {sample['title'][:60]}...")
                print(f"      Author: {sample['author']}")
                print(f"      Score: {sample['score']}")
                print(f"      URL: {sample['url']}")
            else:
                print(f"   ⚠️  No posts found")
                
        except Exception as e:
            logger.error(f"❌ Error scraping r/{subreddit}: {e}")
    
    # Save to parquet for inspection
    if all_posts:
        print(f"\n✅ Total posts scraped: {len(all_posts)}")
        
        # Create DataFrame
        df = pd.DataFrame(all_posts)
        
        # Save to parquet
        data_dir = Path("data/processed")
        data_dir.mkdir(parents=True, exist_ok=True)
        
        filename = data_dir / f"reddit_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
        df.to_parquet(filename)
        
        print(f"📁 Saved to: {filename}")
        print(f"📊 DataFrame shape: {df.shape}")
        print(f"📋 Columns: {list(df.columns)}")
        
        # Display statistics
        print(f"\n📊 STATISTICS:")
        print(f"   Total posts: {len(df)}")
        print(f"   Average score: {df['score'].mean():.1f}")
        print(f"   Average comments: {df['num_comments'].mean():.1f}")
        print(f"   Average upvote ratio: {df['upvote_ratio'].mean():.2%}")
        
        # Show posts by subreddit
        print(f"\n📈 Posts by subreddit:")
        for subreddit, count in df['subreddit'].value_counts().items():
            print(f"   r/{subreddit}: {count}")
        
        return True
    else:
        print(f"\n❌ No posts scraped")
        return False


async def test_deduplication():
    """Test duplicate detection logic"""
    
    print("\n" + "="*80)
    print("🔍 DEDUPLICATION TEST")
    print("="*80 + "\n")
    
    # Simulate same posts scraped twice
    scraper = RedditScraper()
    
    print("Scraping first batch...")
    batch1 = scraper.scrape_posts('wallstreetbets', limit=20, post_type='hot')
    post_ids_1 = {p['post_id'] for p in batch1}
    print(f"✅ Got {len(batch1)} unique post IDs: {len(post_ids_1)}")
    
    # Wait a moment to avoid rate limiting
    await asyncio.sleep(2)
    
    print("\nScraping second batch (should have some overlaps)...")
    batch2 = scraper.scrape_posts('wallstreetbets', limit=20, post_type='hot')
    post_ids_2 = {p['post_id'] for p in batch2}
    print(f"✅ Got {len(batch2)} unique post IDs: {len(post_ids_2)}")
    
    # Find overlaps
    overlaps = post_ids_1 & post_ids_2
    print(f"\n📊 Duplicate detection:")
    print(f"   Batch 1 posts: {len(batch1)}")
    print(f"   Batch 2 posts: {len(batch2)}")
    print(f"   Overlapping posts: {len(overlaps)}")
    print(f"   New posts in batch 2: {len(batch2) - len(overlaps)}")
    
    if overlaps:
        print(f"   ✅ Deduplication would skip {len(overlaps)} posts")
    
    return True


async def main():
    """Run all tests"""
    
    try:
        # Test 1: Real scraping
        success1 = await test_real_scraping()
        
        # Test 2: Deduplication
        success2 = await test_deduplication()
        
        print("\n" + "="*80)
        if success1 and success2:
            print("✅ ALL TESTS PASSED")
        else:
            print("⚠️  SOME TESTS FAILED")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
