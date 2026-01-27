from sqlalchemy import Column, Integer, BigInteger, String, Float, DateTime, Index, UniqueConstraint
from sqlalchemy.sql import func
from backend.database.config import Base


class StockPrice(Base):
    __tablename__ = "stock_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False)
    
    # OHLCV data
    open_price = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    adjusted_close = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    
    # Technical Indicators - Momentum
    rsi = Column(Float, nullable=True)
    macd = Column(Float, nullable=True)
    macd_signal = Column(Float, nullable=True)
    bb_upper = Column(Float, nullable=True)
    bb_lower = Column(Float, nullable=True)
    
    # Moving Averages - Swing Trading
    sma_50 = Column(Float, nullable=True)
    sma_200 = Column(Float, nullable=True)
    
    # Volume Indicators
    volume_ratio = Column(Float, nullable=True)  # Current volume / 20-day avg
    
    # Timestamps
    date = Column(DateTime(timezone=True), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Constraints
    __table_args__ = (
        UniqueConstraint('ticker', 'date', name='unique_ticker_date'),
        Index('idx_ticker_date', 'ticker', 'date'),
    )
    
    def __repr__(self):
        return f"<StockPrice {self.ticker} {self.date.date()} ${self.close}>"