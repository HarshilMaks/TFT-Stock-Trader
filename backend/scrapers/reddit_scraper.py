import praw  # type: ignore
import os
from datetime import datetime
from typing import Any, Literal
from dotenv import load_dotenv

load_dotenv()

PostType = Literal['hot', 'new', 'rising', 'top']


class RedditScraper:
    """
    Handles fetching posts from Reddit using PRAW.
    Supports multiple post types: hot, new, rising, top
    """
    
    def __init__(self):
        """Initialize Reddit API client"""
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
    
    def scrape_posts(
        self, 
        subreddit_name: str, 
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day'
    ) -> list[dict[str, Any]]:
        """
        Fetch posts from a subreddit.
        
        Args:
            subreddit_name: Name without 'r/' prefix (e.g., 'wallstreetbets')
            limit: Number of posts to fetch (max 100 per request)
            post_type: Type of posts to fetch ('hot', 'new', 'rising', 'top')
            time_filter: For 'top' posts only ('hour', 'day', 'week', 'month', 'year', 'all')
        
        Returns:
            List of post dictionaries with standardized fields
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        posts: list[dict[str, Any]] = []
        
        # Select the appropriate post listing based on type
        if post_type == 'hot':
            listing = subreddit.hot(limit=limit)
        elif post_type == 'new':
            listing = subreddit.new(limit=limit)
        elif post_type == 'rising':
            listing = subreddit.rising(limit=limit)
        elif post_type == 'top':
            listing = subreddit.top(time_filter=time_filter, limit=limit)
        else:
            raise ValueError(f"Invalid post_type: {post_type}. Must be 'hot', 'new', 'rising', or 'top'")
        
        for post in listing:
            # Skip stickied posts (moderator announcements)
            if post.stickied:
                continue
            
            posts.append({
                'post_id': post.id,
                'subreddit': subreddit_name,
                'title': post.title,
                'body': post.selftext if post.selftext else '',
                'author': str(post.author) if post.author else '[deleted]',
                'score': post.score,
                'num_comments': post.num_comments,
                'created_at': datetime.fromtimestamp(post.created_utc),
                'url': f"https://reddit.com{post.permalink}"
            })
        
        return posts

