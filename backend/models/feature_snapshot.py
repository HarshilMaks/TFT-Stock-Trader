"""
Feature Snapshot ORM Model

Stores engineered features for each ticker + timestamp combination.
Used for reproducibility, backtesting, and model training.

Schema:
  - snapshot_id: Unique ID for the feature engineering run
  - ticker: Stock ticker symbol
  - reference_date: Date features were computed for
  - features_json: All computed features as JSON
  - created_at: When this record was created
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json

from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from backend.database.config import Base


class FeatureSnapshot(Base):
    """
    Persisted feature snapshot for ML training and backtesting.
    
    Each row represents features for one ticker at one point in time.
    Multiple rows share same snapshot_id if computed together.
    """
    
    __tablename__ = "feature_snapshots"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Identifying fields
    snapshot_id = Column(String(36), nullable=False, index=True)  # UUID
    ticker = Column(String(10), nullable=False, index=True)
    reference_date = Column(DateTime, nullable=False, index=True)
    
    # Feature data (stored as JSON for flexibility)
    features_json = Column(JSON, nullable=False)
    
    # Metadata
    data_quality = Column(String(50), default="complete")  # complete/incomplete/error
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Composite uniqueness: one row per (snapshot_id, ticker)
    __table_args__ = (
        UniqueConstraint('snapshot_id', 'ticker', name='uq_snapshot_ticker'),
        Index('idx_reference_date_ticker', 'reference_date', 'ticker'),
        Index('idx_snapshot_id', 'snapshot_id'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<FeatureSnapshot(snapshot_id={self.snapshot_id}, "
            f"ticker={self.ticker}, ref_date={self.reference_date.date()})>"
        )
    
    @property
    def features(self) -> Dict[str, Any]:
        """Get features as dict."""
        if isinstance(self.features_json, str):
            return json.loads(self.features_json)
        return self.features_json
    
    @features.setter
    def features(self, value: Dict[str, Any]) -> None:
        """Set features, storing as JSON."""
        self.features_json = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "snapshot_id": self.snapshot_id,
            "ticker": self.ticker,
            "reference_date": self.reference_date.isoformat(),
            "features": self.features,
            "data_quality": self.data_quality,
            "created_at": self.created_at.isoformat(),
        }
