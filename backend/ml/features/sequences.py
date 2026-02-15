"""
Temporal Sequence Builder for ML Models

Converts feature snapshots into sliding window sequences for:
- XGBoost/LightGBM: 1D feature vectors per 30-day window
- TFT (Temporal Fusion Transformer): 3D sequences (batch, time, features)
- LSTM/GRU: 3D sequences for temporal modeling

Output: numpy arrays with shape validation
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.feature_snapshot import FeatureSnapshot
from backend.database.config import AsyncSessionLocal

logger = logging.getLogger(__name__)


class SequenceBuilder:
    """
    Build temporal sequences from feature snapshots.
    
    Workflow:
      1. Query feature snapshots for ticker + date range
      2. Sort chronologically
      3. Create sliding windows of configurable size
      4. Stack features into 3D array (n_sequences, window_size, n_features)
    """
    
    # Standard features to include in sequences
    DEFAULT_FEATURES = [
        "rsi", "macd", "macd_signal", "macd_histogram",
        "bb_upper", "bb_lower", "bb_width",
        "sma_50", "sma_200", "sma_50_200_ratio", "sma_crossover",
        "sentiment_score", "sentiment_count", "sentiment_std", "sentiment_trend",
        "volume", "volume_ratio", "volume_trend",
        "close_price", "high", "low",
        "price_range", "rsi_extreme",
        "close_to_bb_mid"
    ]
    
    def __init__(
        self,
        window_size: int = 30,
        step_size: int = 1,
        fill_missing: bool = True,
    ):
        """
        Initialize sequence builder.
        
        Args:
            window_size: Days per sequence (default: 30 for monthly)
            step_size: Days between sequence starts (1 = overlapping, 30 = non-overlapping)
            fill_missing: Whether to forward-fill missing values
        """
        self.window_size = window_size
        self.step_size = step_size
        self.fill_missing = fill_missing
    
    async def build_sequences(
        self,
        ticker: str,
        start_date: datetime,
        end_date: datetime,
        session: Optional[AsyncSession] = None,
        features: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[datetime], Dict[str, Any]]:
        """
        Build temporal sequences for a ticker.
        
        Args:
            ticker: Stock ticker symbol
            start_date: Date range start
            end_date: Date range end
            session: Database session
            features: List of feature names to include (default: all standard features)
            
        Returns:
            Tuple of:
              - sequences: Array of shape (n_sequences, window_size, n_features)
              - dates: List of start dates for each sequence
              - metadata: Dict with shape info, missing data %, etc.
        """
        if session is None:
            session = AsyncSessionLocal()
        
        if features is None:
            features = self.DEFAULT_FEATURES
        
        try:
            # Fetch all snapshots for ticker in date range
            snapshots_df = await self._fetch_snapshots(
                session, ticker, start_date, end_date
            )
            
            if snapshots_df.empty:
                logger.warning(f"No snapshots found for {ticker} between {start_date} and {end_date}")
                return np.array([]), [], {"error": "No data"}
            
            # Create sliding windows
            sequences = []
            sequence_dates = []
            
            # Generate window start dates
            current_date = snapshots_df['reference_date'].min()
            end_window_date = snapshots_df['reference_date'].max() - timedelta(days=self.window_size-1)
            
            while current_date <= end_window_date:
                window_end = current_date + timedelta(days=self.window_size-1)
                
                # Extract window data
                window_data = snapshots_df[
                    (snapshots_df['reference_date'] >= current_date) &
                    (snapshots_df['reference_date'] <= window_end)
                ].copy()
                
                if len(window_data) == self.window_size:
                    # We have a complete window
                    sequence = self._create_sequence(window_data, features)
                    if sequence is not None:
                        sequences.append(sequence)
                        sequence_dates.append(current_date)
                elif self.fill_missing and len(window_data) > self.window_size // 2:
                    # Partial window - try to fill missing dates
                    window_data = self._fill_missing_dates(
                        window_data, current_date, window_end
                    )
                    if len(window_data) == self.window_size:
                        sequence = self._create_sequence(window_data, features)
                        if sequence is not None:
                            sequences.append(sequence)
                            sequence_dates.append(current_date)
                
                current_date += timedelta(days=self.step_size)
            
            if not sequences:
                logger.warning(f"Could not build any complete sequences for {ticker}")
                return np.array([]), [], {"error": "No complete sequences"}
            
            # Stack sequences
            sequences_array = np.array(sequences)
            
            # Validate shape
            expected_shape = (len(sequences), self.window_size, len(features))
            if sequences_array.shape != expected_shape:
                logger.warning(
                    f"Unexpected shape: {sequences_array.shape} vs {expected_shape}"
                )
            
            metadata = {
                "shape": sequences_array.shape,
                "n_sequences": len(sequences),
                "window_size": self.window_size,
                "n_features": len(features),
                "feature_names": features,
                "date_range": (snapshots_df['reference_date'].min(), snapshots_df['reference_date'].max()),
                "ticker": ticker,
                "missing_pct": round(100 * snapshots_df['features_json'].isna().sum() / len(snapshots_df), 2)
            }
            
            return sequences_array, sequence_dates, metadata
            
        except Exception as e:
            logger.error(f"Error building sequences for {ticker}: {e}")
            raise
    
    async def _fetch_snapshots(
        self,
        session: AsyncSession,
        ticker: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fetch and convert snapshots to DataFrame."""
        stmt = select(FeatureSnapshot).where(
            and_(
                FeatureSnapshot.ticker == ticker,
                FeatureSnapshot.reference_date >= start_date,
                FeatureSnapshot.reference_date <= end_date,
                FeatureSnapshot.data_quality != "error"
            )
        ).order_by(FeatureSnapshot.reference_date)
        
        result = await session.execute(stmt)
        snapshots = result.scalars().all()
        
        if not snapshots:
            return pd.DataFrame()
        
        # Convert to DataFrame
        data = []
        for snap in snapshots:
            features = snap.features if isinstance(snap.features_json, dict) else {}
            row = {
                "reference_date": snap.reference_date,
                "ticker": snap.ticker,
                "features_json": snap.features_json,
                **features  # Flatten features into row
            }
            data.append(row)
        
        df = pd.DataFrame(data)
        return df
    
    def _create_sequence(
        self,
        window_data: pd.DataFrame,
        features: List[str]
    ) -> Optional[np.ndarray]:
        """
        Create a single sequence from window data.
        
        Returns:
            Array of shape (window_size, n_features) or None if invalid
        """
        try:
            # Extract feature columns
            feature_cols = [f for f in features if f in window_data.columns]
            
            if not feature_cols:
                logger.warning(f"No features found in window data")
                return None
            
            # Create array (window_size, n_features)
            sequence = window_data[feature_cols].values.astype(np.float32)
            
            # Handle missing values
            if np.isnan(sequence).any():
                if self.fill_missing:
                    sequence = self._forward_fill_nans(sequence)
                else:
                    return None  # Skip window with missing values
            
            if sequence.shape != (self.window_size, len(feature_cols)):
                return None
            
            return sequence
            
        except Exception as e:
            logger.warning(f"Error creating sequence: {e}")
            return None
    
    def _fill_missing_dates(
        self,
        window_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """Fill missing dates with forward-filled features."""
        # Create complete date range
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # Reindex and forward fill
        window_data = window_data.set_index('reference_date')
        window_data = window_data.reindex(date_range, method='ffill')
        window_data['reference_date'] = window_data.index
        window_data = window_data.reset_index(drop=True)
        
        return window_data
    
    @staticmethod
    def _forward_fill_nans(arr: np.ndarray) -> np.ndarray:
        """Forward fill NaN values in array."""
        for i in range(1, arr.shape[0]):
            mask = np.isnan(arr[i])
            arr[i][mask] = arr[i-1][mask]
        return arr


async def build_multi_ticker_sequences(
    tickers: List[str],
    start_date: datetime,
    end_date: datetime,
    window_size: int = 30,
    session: Optional[AsyncSession] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Build sequences for multiple tickers.
    
    Returns:
        Dict mapping ticker -> {sequences, dates, metadata}
    """
    builder = SequenceBuilder(window_size=window_size)
    results = {}
    
    for ticker in tickers:
        try:
            sequences, dates, metadata = await builder.build_sequences(
                ticker, start_date, end_date, session
            )
            results[ticker] = {
                "sequences": sequences,
                "dates": dates,
                "metadata": metadata
            }
        except Exception as e:
            logger.error(f"Failed to build sequences for {ticker}: {e}")
            results[ticker] = {"error": str(e)}
    
    return results


if __name__ == "__main__":
    import asyncio
    
    async def main():
        builder = SequenceBuilder(window_size=30)
        
        # Example usage
        sequences, dates, metadata = await builder.build_sequences(
            ticker="AAPL",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 12, 31)
        )
        
        print(f"✅ Built {metadata['n_sequences']} sequences")
        print(f"   Shape: {metadata['shape']}")
        print(f"   Features: {len(metadata['feature_names'])}")
        print(f"   Missing data: {metadata['missing_pct']}%")
    
    asyncio.run(main())
