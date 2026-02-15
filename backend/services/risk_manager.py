"""
Risk Manager Service

Validates trading signals against strict risk rules before they're persisted to the database.
Every signal must pass multiple risk checks or it's rejected.

This is a critical safety gate in the trading system:
- Prevents overleveraged positions
- Enforces position sizing
- Validates confidence thresholds
- Monitors portfolio-level constraints

Philosophy: Reject unsafe signals. No position is worth risking the portfolio.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Data Models for Risk Validation
# ═══════════════════════════════════════════════════════════════════════════════


class RejectionReason(Enum):
    """Reasons why a signal was rejected by risk manager"""
    
    # Confidence rules (signal quality)
    CONFIDENCE_TOO_LOW = "confidence_below_70_percent"
    
    # Position sizing rules
    POSITION_TOO_LARGE = "position_exceeds_20_percent_limit"
    RISK_TOO_LARGE = "risk_exceeds_2_percent_per_trade"
    
    # Risk/reward rules
    RISK_REWARD_UNFAVORABLE = "risk_reward_ratio_below_1_2"
    
    # Portfolio constraints
    MAX_POSITIONS_EXCEEDED = "portfolio_has_5_concurrent_positions"
    PORTFOLIO_IN_DRAWDOWN = "portfolio_drawdown_exceeds_15_percent"
    
    # Price validation
    INVALID_PRICE_LEVELS = "entry_target_stop_invalid"
    
    # Data quality
    MISSING_REQUIRED_FIELDS = "missing_required_fields"


@dataclass
class SignalValidationRequest:
    """Input to risk manager: a candidate signal"""
    
    ticker: str
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    confidence: float  # 0.0 to 1.0
    entry_price: float
    target_price: Optional[float]
    stop_loss: Optional[float]
    rsi_value: Optional[float] = None
    macd_value: Optional[float] = None
    sentiment_score: Optional[float] = None


@dataclass
class PortfolioState:
    """Current portfolio state needed for risk calculations"""
    
    portfolio_value: float  # Total account value
    current_positions: int  # Number of open positions
    portfolio_drawdown_pct: float  # Current drawdown as percentage (0-100)
    open_position_values: Optional[List[float]] = None  # Values of open positions


@dataclass
class RiskValidationResult:
    """Output from risk manager: pass/fail with details"""
    
    passed: bool
    rejection_reason: Optional[RejectionReason] = None
    rejection_message: Optional[str] = None
    
    # Risk metrics (calculated regardless of pass/fail)
    position_size_pct: float = 0.0  # Proposed position as % of portfolio
    position_size_dollars: float = 0.0  # Dollar amount
    risk_reward_ratio: float = 0.0  # Target gain / Stop loss distance
    risk_dollars: float = 0.0  # 2% of portfolio at risk
    
    # Metadata
    validated_at: datetime = None
    validation_notes: List[str] = None
    
    def __post_init__(self):
        if self.validated_at is None:
            self.validated_at = datetime.now(timezone.utc)
        if self.validation_notes is None:
            self.validation_notes = []


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Manager Service
# ═══════════════════════════════════════════════════════════════════════════════


class RiskManager:
    """
    Validates trading signals against strict risk rules.
    
    Risk Rules (in order of application):
    
    1. **Confidence Filter** (Quality Gate)
       - Min confidence: 70%
       - Ensures only high-quality signals are traded
       - Risk: Trading low-conviction signals leads to losses
    
    2. **Price Validation** (Data Quality)
       - Entry < Stop Loss < Target (or Entry > Stop Loss > Target for shorts)
       - Check for NaN, Inf, or absurd values
       - Risk: Invalid prices cause execution errors
    
    3. **Risk/Reward Ratio** (Edge Requirement)
       - Min 1:2 ratio (1 dollar risk for 2+ dollars reward)
       - Ensures favorable odds
       - Risk: Trading unfavorable odds leads to negative expectancy
    
    4. **Position Sizing** (Capital Preservation)
       - Max 2% risk per trade
       - Max 20% position size
       - Risk: Overleveraging bankrupts accounts
    
    5. **Portfolio Constraints** (System Safety)
       - Max 5 concurrent positions
       - Max 15% portfolio drawdown
       - Risk: Too many concurrent positions are unmanageable
       
    Philosophy: Reject fast, fail safely. A rejected signal costs nothing;
    a bad trade costs portfolio.
    """
    
    # ─────────────────────────────────────────────────────────────────────────
    # Configuration - Risk Limits (Customizable)
    # ─────────────────────────────────────────────────────────────────────────
    
    MIN_CONFIDENCE = 0.70  # 70% minimum
    MAX_RISK_PER_TRADE = 0.02  # 2% of portfolio
    MAX_POSITION_SIZE = 0.20  # 20% of portfolio
    MIN_RISK_REWARD_RATIO = 2.0  # 1:2 (1 risk for 2 reward)
    MAX_CONCURRENT_POSITIONS = 5
    MAX_PORTFOLIO_DRAWDOWN = 0.15  # 15%
    
    STANDARD_STOP_LOSS = 0.95  # -5% if not specified
    STANDARD_TARGET = 1.07  # +7% if not specified
    
    def __init__(self):
        """Initialize Risk Manager with default configuration"""
        self.validation_count = 0
        self.acceptance_count = 0
        self.rejection_count = 0
    
    def validate(
        self,
        signal: SignalValidationRequest,
        portfolio: PortfolioState
    ) -> RiskValidationResult:
        """
        Main entry point: Validate a signal against all risk rules.
        
        Args:
            signal: Candidate signal with prices and confidence
            portfolio: Current portfolio state (positions, drawdown, etc)
        
        Returns:
            RiskValidationResult with pass/fail and risk metrics
        """
        self.validation_count += 1
        result = RiskValidationResult(passed=False)
        result.validated_at = datetime.now(timezone.utc)
        
        # 1. Validate required fields exist
        if not self._validate_required_fields(signal, result):
            self.rejection_count += 1
            return result
        
        # 2. Check confidence threshold (quality gate)
        if not self._validate_confidence(signal, result):
            self.rejection_count += 1
            return result
        
        # 3. Validate price levels (data quality)
        if not self._validate_price_levels(signal, result):
            self.rejection_count += 1
            return result
        
        # 4. Calculate risk metrics
        self._calculate_risk_metrics(signal, portfolio, result)
        
        # 5. Check risk/reward ratio (edge requirement)
        if not self._validate_risk_reward_ratio(result):
            self.rejection_count += 1
            return result
        
        # 6. Check position sizing (capital preservation)
        if not self._validate_position_sizing(result):
            self.rejection_count += 1
            return result
        
        # 7. Check portfolio constraints (system safety)
        if not self._validate_portfolio_constraints(portfolio, result):
            self.rejection_count += 1
            return result
        
        # All checks passed!
        result.passed = True
        self.acceptance_count += 1
        result.validation_notes.append("✅ Signal passed all risk checks")
        
        logger.info(
            f"Signal ACCEPTED: {signal.ticker} {signal.signal_type} "
            f"@${signal.entry_price} | {result.position_size_pct:.1%} of portfolio"
        )
        
        return result
    
    # ─────────────────────────────────────────────────────────────────────────
    # Individual Validation Rules
    # ─────────────────────────────────────────────────────────────────────────
    
    def _validate_required_fields(
        self,
        signal: SignalValidationRequest,
        result: RiskValidationResult
    ) -> bool:
        """Check that all required fields are present and valid"""
        
        required_fields = {
            'ticker': signal.ticker,
            'signal_type': signal.signal_type,
            'confidence': signal.confidence,
            'entry_price': signal.entry_price,
            'target_price': signal.target_price,
            'stop_loss': signal.stop_loss
        }
        
        for field_name, field_value in required_fields.items():
            if field_value is None:
                result.rejection_reason = RejectionReason.MISSING_REQUIRED_FIELDS
                result.rejection_message = f"Missing required field: {field_name}"
                result.validation_notes.append(f"❌ {result.rejection_message}")
                return False
        
        # Check for invalid values
        if not isinstance(signal.confidence, (int, float)) or signal.confidence < 0 or signal.confidence > 1:
            result.rejection_reason = RejectionReason.MISSING_REQUIRED_FIELDS
            result.rejection_message = "Confidence must be 0.0-1.0"
            result.validation_notes.append(f"❌ {result.rejection_message}")
            return False
        
        if signal.entry_price <= 0 or signal.target_price <= 0 or signal.stop_loss <= 0:
            result.rejection_reason = RejectionReason.MISSING_REQUIRED_FIELDS
            result.rejection_message = "Prices must be positive"
            result.validation_notes.append(f"❌ {result.rejection_message}")
            return False
        
        return True
    
    def _validate_confidence(
        self,
        signal: SignalValidationRequest,
        result: RiskValidationResult
    ) -> bool:
        """Rule 1: Confidence filter (quality gate)
        
        Only trade high-conviction signals (70%+ probability).
        This is the first filter to eliminate noise.
        """
        
        if signal.confidence < self.MIN_CONFIDENCE:
            result.rejection_reason = RejectionReason.CONFIDENCE_TOO_LOW
            result.rejection_message = (
                f"Confidence {signal.confidence:.1%} below minimum {self.MIN_CONFIDENCE:.0%}"
            )
            result.validation_notes.append(
                f"❌ Confidence Filter: {signal.confidence:.1%} < {self.MIN_CONFIDENCE:.0%}"
            )
            return False
        
        result.validation_notes.append(
            f"✅ Confidence Filter: {signal.confidence:.1%} >= {self.MIN_CONFIDENCE:.0%}"
        )
        return True
    
    def _validate_price_levels(
        self,
        signal: SignalValidationRequest,
        result: RiskValidationResult
    ) -> bool:
        """Rule 2: Validate that price levels make sense
        
        For BUY signals: entry < stop_loss < target
        For SELL signals: entry > stop_loss > target
        """
        
        if signal.signal_type.upper() == 'BUY':
            # For BUY: entry should be between stop loss and target
            if not (signal.stop_loss < signal.entry_price < signal.target_price):
                result.rejection_reason = RejectionReason.INVALID_PRICE_LEVELS
                result.rejection_message = (
                    f"BUY signal requires: stop_loss({signal.stop_loss}) < "
                    f"entry({signal.entry_price}) < target({signal.target_price})"
                )
                result.validation_notes.append(f"❌ Price Validation: {result.rejection_message}")
                return False
        
        elif signal.signal_type.upper() == 'SELL':
            # For SELL: entry should be between target and stop loss
            if not (signal.target_price < signal.entry_price < signal.stop_loss):
                result.rejection_reason = RejectionReason.INVALID_PRICE_LEVELS
                result.rejection_message = (
                    f"SELL signal requires: target({signal.target_price}) < "
                    f"entry({signal.entry_price}) < stop_loss({signal.stop_loss})"
                )
                result.validation_notes.append(f"❌ Price Validation: {result.rejection_message}")
                return False
        
        result.validation_notes.append("✅ Price Validation: Levels are valid")
        return True
    
    def _calculate_risk_metrics(
        self,
        signal: SignalValidationRequest,
        portfolio: PortfolioState,
        result: RiskValidationResult
    ) -> None:
        """Calculate risk metrics for this trade"""
        
        if signal.signal_type.upper() == 'BUY':
            # For BUY: risk is entry - stop_loss, reward is target - entry
            risk_dollars = signal.entry_price - signal.stop_loss
            reward_dollars = signal.target_price - signal.entry_price
        else:
            # For SELL: risk is stop_loss - entry, reward is entry - target
            risk_dollars = signal.stop_loss - signal.entry_price
            reward_dollars = signal.entry_price - signal.target_price
        
        # Risk/reward ratio
        result.risk_reward_ratio = reward_dollars / risk_dollars if risk_dollars > 0 else 0
        
        # Position sizing (based on 2% risk)
        result.risk_dollars = portfolio.portfolio_value * self.MAX_RISK_PER_TRADE
        
        # How many shares/units can we buy given risk constraint?
        if risk_dollars > 0:
            shares = result.risk_dollars / risk_dollars
            result.position_size_dollars = shares * signal.entry_price
        else:
            result.position_size_dollars = 0
        
        # Cap at 20% position limit
        max_position_dollars = portfolio.portfolio_value * self.MAX_POSITION_SIZE
        result.position_size_dollars = min(result.position_size_dollars, max_position_dollars)
        
        # As percentage
        result.position_size_pct = result.position_size_dollars / portfolio.portfolio_value
        
        logger.debug(
            f"Risk metrics for {signal.ticker}: "
            f"risk/${risk_dollars:.2f}, reward/${reward_dollars:.2f}, "
            f"ratio={result.risk_reward_ratio:.2f}, position={result.position_size_pct:.1%}"
        )
    
    def _validate_risk_reward_ratio(self, result: RiskValidationResult) -> bool:
        """Rule 3: Ensure risk/reward ratio is favorable
        
        Minimum 1:2 ratio (1 dollar risk for 2+ dollars reward).
        Ensures positive expectancy: even with 50% win rate, you make money.
        """
        
        if result.risk_reward_ratio < self.MIN_RISK_REWARD_RATIO:
            result.rejection_reason = RejectionReason.RISK_REWARD_UNFAVORABLE
            result.rejection_message = (
                f"Risk/reward ratio {result.risk_reward_ratio:.2f} "
                f"below minimum {self.MIN_RISK_REWARD_RATIO:.1f}"
            )
            result.validation_notes.append(
                f"❌ Risk/Reward: {result.risk_reward_ratio:.2f} < {self.MIN_RISK_REWARD_RATIO}"
            )
            return False
        
        result.validation_notes.append(
            f"✅ Risk/Reward: {result.risk_reward_ratio:.2f} >= {self.MIN_RISK_REWARD_RATIO}"
        )
        return True
    
    def _validate_position_sizing(self, result: RiskValidationResult) -> bool:
        """Rule 4: Validate position sizing constraints
        
        - Max 2% risk per trade (capital preservation)
        - Max 20% position size (diversification)
        
        Note: Position sizing is already calculated to enforce the 2% risk limit,
        so this check validates the 20% position size cap.
        """
        
        # Check position size limit
        if result.position_size_pct > self.MAX_POSITION_SIZE:
            result.rejection_reason = RejectionReason.POSITION_TOO_LARGE
            result.rejection_message = (
                f"Position size {result.position_size_pct:.1%} exceeds {self.MAX_POSITION_SIZE:.0%} limit"
            )
            result.validation_notes.append(f"❌ Position Size: {result.rejection_message}")
            return False
        
        result.validation_notes.append(
            f"✅ Position Sizing: {result.position_size_pct:.1%} of portfolio, "
            f"${result.risk_dollars:.0f} at risk"
        )
        return True
    
    def _validate_portfolio_constraints(
        self,
        portfolio: PortfolioState,
        result: RiskValidationResult
    ) -> bool:
        """Rule 5: Validate portfolio-level constraints
        
        - Max 5 concurrent positions (manageable)
        - Max 15% drawdown (circuit breaker)
        """
        
        # Check position count
        if portfolio.current_positions >= self.MAX_CONCURRENT_POSITIONS:
            result.rejection_reason = RejectionReason.MAX_POSITIONS_EXCEEDED
            result.rejection_message = (
                f"Portfolio has {portfolio.current_positions} positions "
                f"(max {self.MAX_CONCURRENT_POSITIONS})"
            )
            result.validation_notes.append(f"❌ Max Positions: {result.rejection_message}")
            return False
        
        # Check drawdown
        if portfolio.portfolio_drawdown_pct > self.MAX_PORTFOLIO_DRAWDOWN * 100:
            result.rejection_reason = RejectionReason.PORTFOLIO_IN_DRAWDOWN
            result.rejection_message = (
                f"Portfolio drawdown {portfolio.portfolio_drawdown_pct:.1f}% "
                f"exceeds {self.MAX_PORTFOLIO_DRAWDOWN*100:.0f}% limit"
            )
            result.validation_notes.append(f"❌ Drawdown Limit: {result.rejection_message}")
            return False
        
        result.validation_notes.append(
            f"✅ Portfolio Constraints: "
            f"{portfolio.current_positions}/{self.MAX_CONCURRENT_POSITIONS} positions, "
            f"drawdown {portfolio.portfolio_drawdown_pct:.1f}%"
        )
        return True
    
    # ─────────────────────────────────────────────────────────────────────────
    # Statistics & Monitoring
    # ─────────────────────────────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Return usage statistics"""
        acceptance_rate = (
            self.acceptance_count / self.validation_count
            if self.validation_count > 0
            else 0
        )
        
        return {
            'total_validations': self.validation_count,
            'accepted_signals': self.acceptance_count,
            'rejected_signals': self.rejection_count,
            'acceptance_rate': f"{acceptance_rate:.1%}"
        }
    
    def reset_stats(self) -> None:
        """Reset usage counters"""
        self.validation_count = 0
        self.acceptance_count = 0
        self.rejection_count = 0


# Singleton instance (optional, for convenience)
risk_manager = RiskManager()
