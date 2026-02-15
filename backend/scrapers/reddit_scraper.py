import praw  # type: ignore
import os
from datetime import datetime
from typing import Any, Literal, Optional
from dotenv import load_dotenv
from backend.utils.logger import get_logger
from backend.utils.retry import retry_with_backoff, REDDIT_CONFIG

load_dotenv()

PostType = Literal['hot', 'new', 'rising', 'top']
logger = get_logger(__name__)


class RedditScraper:
    """
    Enhanced Reddit scraper using PRAW.
    
    Features:
    - Multiple post types: hot, new, rising, top
    - Comment scraping with nested replies
    - Complete metadata: upvote_ratio, is_self, link_flair_text
    - Graceful error handling for deleted/removed content
    """
    
    def __init__(self):
        """Initialize Reddit API client"""
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
    
    @retry_with_backoff(config=REDDIT_CONFIG)
    def scrape_posts(
        self, 
        subreddit_name: str, 
        limit: int = 100,
        post_type: PostType = 'hot',
        time_filter: str = 'day'
    ) -> list[dict[str, Any]]:
        """
        Fetch posts from a subreddit with complete metadata.
        
        Args:
            subreddit_name: Name without 'r/' prefix (e.g., 'wallstreetbets')
            limit: Number of posts to fetch (max 100 per request)
            post_type: Type of posts to fetch ('hot', 'new', 'rising', 'top')
            time_filter: For 'top' posts only ('hour', 'day', 'week', 'month', 'year', 'all')
        
        Returns:
            List of post dictionaries with complete fields:
            - Basic: post_id, subreddit, title, body, author, url
            - Engagement: score, num_comments, upvote_ratio
            - Metadata: created_at, is_self, link_flair_text
        
        Raises:
            ValueError: If post_type is invalid
        """
        try:
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
                
                try:
                    posts.append({
                        # Identifiers
                        'post_id': post.id,
                        'subreddit': subreddit_name,
                        
                        # Content
                        'title': post.title,
                        'body': post.selftext if post.selftext else '',
                        'author': str(post.author) if post.author else '[deleted]',
                        
                        # Engagement metrics
                        'score': post.score,
                        'num_comments': post.num_comments,
                        'upvote_ratio': post.upvote_ratio,  # NEW: Percentage upvoted (0.0-1.0)
                        
                        # Metadata
                        'created_at': datetime.fromtimestamp(post.created_utc),
                        'url': f"https://reddit.com{post.permalink}",
                        'is_self': post.is_self,  # NEW: True if text post, False if link
                        'link_flair_text': post.link_flair_text or '',  # NEW: Post flair tag
                    })
                except Exception as e:
                    # Handle deleted/removed posts gracefully
                    logger.warning(f"Skipping post {post.id} due to error: {e}")
                    continue
            
            logger.info(f"Scraped {len(posts)} posts from r/{subreddit_name} ({post_type})")
            return posts
            
        except Exception as e:
            logger.error(f"Failed to scrape r/{subreddit_name}: {e}")
            return []
    
    @retry_with_backoff(config=REDDIT_CONFIG)
    def get_post_comments(
        self, 
        post_id: str, 
        limit: int = 50,
        sort: str = 'top',
        include_replies: bool = True
    ) -> list[dict[str, Any]]:
        """
        Fetch comments from a specific post for deeper sentiment analysis.
        
        Args:
            post_id: Reddit post ID (e.g., '1a2b3c')
            limit: Number of top-level comments to fetch
            sort: Comment sort order ('top', 'best', 'new', 'controversial', 'old', 'qa')
            include_replies: Whether to include nested replies (up to 2 levels deep)
        
        Returns:
            List of comment dictionaries with:
            - comment_id, post_id, body, author
            - score, created_at, is_submitter
            - parent_comment_id (for replies)
            - depth (0=top-level, 1=reply, 2=nested reply)
        
        Use Case:
            For high-engagement posts (>100 comments), scrape comments to:
            - Get broader sentiment beyond just the post
            - Identify controversial opinions (low score + many replies)
            - Track sentiment shifts over time (early vs late comments)
        """
        try:
            submission = self.reddit.submission(id=post_id)
            
            # Sort comments
            if sort == 'top':
                submission.comment_sort = 'top'
            elif sort == 'best':
                submission.comment_sort = 'best'
            elif sort == 'new':
                submission.comment_sort = 'new'
            elif sort == 'controversial':
                submission.comment_sort = 'controversial'
            elif sort == 'old':
                submission.comment_sort = 'old'
            elif sort == 'qa':
                submission.comment_sort = 'qa'
            
            # Fetch comments (replaces "MoreComments" objects with actual comments)
            submission.comments.replace_more(limit=0)
            comments: list[dict[str, Any]] = []
            
            # Process top-level comments
            for comment in submission.comments[:limit]:
                try:
                    comment_data = self._parse_comment(comment, post_id, depth=0)
                    if comment_data:
                        comments.append(comment_data)
                    
                    # Include replies if requested
                    if include_replies and hasattr(comment, 'replies'):
                        # Level 1 replies (direct replies to top-level comment)
                        for reply in comment.replies[:5]:  # Limit to 5 replies per comment
                            try:
                                reply_data = self._parse_comment(
                                    reply, 
                                    post_id, 
                                    depth=1, 
                                    parent_id=comment.id
                                )
                                if reply_data:
                                    comments.append(reply_data)
                                
                                # Level 2 replies (nested discussions)
                                if hasattr(reply, 'replies'):
                                    for nested_reply in reply.replies[:3]:  # Limit nested
                                        try:
                                            nested_data = self._parse_comment(
                                                nested_reply,
                                                post_id,
                                                depth=2,
                                                parent_id=reply.id
                                            )
                                            if nested_data:
                                                comments.append(nested_data)
                                        except Exception as e:
                                            logger.warning(f"Skipping nested reply: {e}")
                                            continue
                            except Exception as e:
                                logger.warning(f"Skipping reply: {e}")
                                continue
                
                except Exception as e:
                    logger.warning(f"Skipping comment due to error: {e}")
                    continue
            
            logger.info(f"Scraped {len(comments)} comments from post {post_id}")
            return comments
            
        except Exception as e:
            logger.error(f"Failed to scrape comments for post {post_id}: {e}")
            return []
    
    def _parse_comment(
        self, 
        comment: Any, 
        post_id: str, 
        depth: int = 0,
        parent_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """
        Parse a PRAW comment object into a standardized dictionary.
        
        Args:
            comment: PRAW Comment object
            post_id: Parent post ID
            depth: Nesting level (0=top, 1=reply, 2=nested)
            parent_id: Comment ID this is replying to (None for top-level)
        
        Returns:
            Comment dictionary or None if parsing fails
        """
        try:
            # Skip deleted/removed comments
            if not hasattr(comment, 'body') or comment.body in ['[deleted]', '[removed]']:
                return None
            
            return {
                'comment_id': comment.id,
                'post_id': post_id,
                'body': comment.body,
                'author': str(comment.author) if comment.author else '[deleted]',
                'score': comment.score,
                'created_at': datetime.fromtimestamp(comment.created_utc),
                'is_submitter': comment.is_submitter,  # True if comment author = post author
                'depth': depth,
                'parent_comment_id': parent_id,
            }
        except Exception as e:
            logger.warning(f"Failed to parse comment: {e}")
            return None

