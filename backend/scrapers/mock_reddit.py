from datetime import datetime, timedelta
import random
from typing import Literal

PostType = Literal['hot', 'new', 'rising', 'top']


class MockRedditScraper:
    """Generates fake Reddit posts for testing"""
    
    SAMPLE_TITLES = [
        "AAPL earnings beat expectations! 🚀",
        "Is TSLA overvalued at current price?",
        "GME short squeeze incoming? DD inside",
        "Why I'm bullish on NVDA for 2026",
        "MSFT Azure growth is insane",
        "Thoughts on $SPY calls this week?",
        "AMC apes still holding strong 💎🙌",
        "META Reality Labs losing billions",
        "Should I buy AMZN before holidays?",
        "PLTR government contracts secured"
    ]
    
    def scrape_posts(
        self, 
        subreddit_name: str, 
        limit: int = 100, 
        post_type: PostType = 'hot',
        time_filter: str = 'day'
    ):
        """
        Mock scraper that generates fake posts.
        Args match real RedditScraper for compatibility.
        """
        posts = []
        base_time = datetime.now()
        
        for i in range(limit):
            posts.append({
                'post_id': f'mock_{i}_{random.randint(1000, 9999)}',
                'subreddit': subreddit_name,
                'title': random.choice(self.SAMPLE_TITLES),
                'body': f'This is mock post content {i}. Analysis suggests bullish sentiment.',
                'author': f'user_{random.randint(1, 100)}',
                'score': random.randint(10, 5000),
                'num_comments': random.randint(5, 500),
                'created_at': base_time - timedelta(hours=random.randint(1, 72)),
                'url': f'https://reddit.com/r/{subreddit_name}/mock_{i}'
            })
        
        return posts
