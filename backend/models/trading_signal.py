from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from backend.database.config import Base
import enum


class SignalType(enum.Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradingSignal(Base):
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String(10), nullable=False, index=True)
    
    # Signal
    signal = Column(SQLEnum(SignalType), nullable=False)
    confidence = Column(Float, nullable=False)  # 0-1 probability
    
    # Price levels
    entry_price = Column(Float, nullable=False)
    target_price = Column(Float, nullable=True)  # +5-10% profit target
    stop_loss = Column(Float, nullable=True)     # -5% loss limit
    
    # Risk metrics
    risk_reward_ratio = Column(Float, nullable=True)  # Target gain / Stop loss
    position_size_pct = Column(Float, nullable=True)  # % of portfolio
    
    # Features that generated signal
    rsi_value = Column(Float, nullable=True)
    macd_value = Column(Float, nullable=True)
    sentiment_score = Column(Float, nullable=True)
    sentiment_trend = Column(Float, nullable=True)
    
    # Status tracking
    is_active = Column(Integer, default=1)  # 1=active, 0=closed
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(50), nullable=True)  # 'target', 'stop_loss', 'signal_flip'
    
    # Timestamps
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # Signal valid until
    closed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<TradingSignal {self.signal.value} {self.ticker} @${self.entry_price} conf={self.confidence:.2f}>"
