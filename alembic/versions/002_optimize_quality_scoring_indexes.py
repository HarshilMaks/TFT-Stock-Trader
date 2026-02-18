"""Optimize quality scoring with performance indexes.

Revision ID: 002_optimize_quality_scoring
Revises: 6aeb58d1fa26
Create Date: 2026-02-18 11:00:00.000000

This migration:
1. Adds is_quality column (derived from quality_score >= 50)
2. Creates indexes for quality-based queries
3. Creates composite index (is_quality, created_at) for filtered feeds

Performance improvements:
- Quality range queries: WHERE quality_score > 50
- Quality-filtered feeds: WHERE is_quality=true ORDER BY created_at DESC
- Time-based queries: WHERE created_at > timestamp
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002_optimize_quality_scoring'
down_revision: Union[str, Sequence[str], None] = '6aeb58d1fa26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quality optimization columns and indexes."""
    # Add is_quality boolean column (True if quality_score >= 50)
    op.add_column(
        'reddit_posts',
        sa.Column('is_quality', sa.Boolean(), nullable=False, server_default='false')
    )
    
    # Create index on quality_score for range queries
    op.create_index(
        'ix_reddit_posts_quality_score',
        'reddit_posts',
        ['quality_score']
    )
    
    # Create composite index for quality filtering + sorting
    # This supports: SELECT * FROM reddit_posts 
    #               WHERE is_quality=true 
    #               ORDER BY created_at DESC LIMIT 10
    op.create_index(
        'ix_reddit_posts_quality_created',
        'reddit_posts',
        ['is_quality', 'created_at'],
        postgresql_where=sa.text('is_quality = true')
    )
    
    # Create index on created_at if it doesn't exist
    op.create_index(
        'ix_reddit_posts_created_at',
        'reddit_posts',
        ['created_at']
    )


def downgrade() -> None:
    """Remove quality optimization columns and indexes."""
    # Drop indexes
    op.drop_index('ix_reddit_posts_quality_created', table_name='reddit_posts')
    op.drop_index('ix_reddit_posts_quality_score', table_name='reddit_posts')
    op.drop_index('ix_reddit_posts_created_at', table_name='reddit_posts')
    
    # Drop column
    op.drop_column('reddit_posts', 'is_quality')
