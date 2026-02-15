"""
Unit Tests for Risk Manager Service

Tests all validation rules in isolation and combination.
Run with: pytest tests/unit/test_risk_manager.py -v
"""

import pytest
from backend.services.risk_manager import (
    RiskManager,
    SignalValidationRequest,
    PortfolioState,
    RejectionReason
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures (Test Setup)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def risk_manager():
    """Fresh risk manager instance for each test"""
    return RiskManager()


@pytest.fixture
def healthy_portfolio():
    """Healthy portfolio state (good to trade)"""
    return PortfolioState(
        portfolio_value=20000,           # $20k account (allows 2% = $400 risk)
        current_positions=2,             # 2 of 5 max
        portfolio_drawdown_pct=5.0,      # 5% drawdown (well below 15% limit)
        open_position_values=[2000, 1600]
    )


@pytest.fixture
def valid_buy_signal():
    """Valid BUY signal that should pass all checks"""
    return SignalValidationRequest(
        ticker="AAPL",
        signal_type="BUY",
        confidence=0.80,  # 80% confidence (well above 70% min)
        entry_price=100.0,
        target_price=110.0,  # +10% target (reward: 10)
        stop_loss=95.0,      # -5% stop loss (risk: 5, ratio 2:1 ✓)
        rsi_value=30.0,      # Oversold
        sentiment_score=0.5  # Bullish
    )


@pytest.fixture
def valid_sell_signal():
    """Valid SELL signal that should pass all checks"""
    return SignalValidationRequest(
        ticker="MSFT",
        signal_type="SELL",
        confidence=0.75,
        entry_price=300.0,
        target_price=279.0,  # -7% target
        stop_loss=315.0,     # +5% stop loss
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 1: Confidence Filter
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfidenceFilter:
    """Test Rule 1: Confidence >= 70%"""
    
    def test_signal_passes_at_exactly_70_percent(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Edge case: exactly 70% should pass"""
        valid_buy_signal.confidence = 0.70
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        # Should pass confidence check (may fail position sizing or other rules)
        assert result.rejection_reason != RejectionReason.CONFIDENCE_TOO_LOW
    
    def test_signal_fails_below_70_percent(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Signal with 69% confidence should fail"""
        valid_buy_signal.confidence = 0.69
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.CONFIDENCE_TOO_LOW
        assert "70%" in result.rejection_message.lower()
    
    def test_signal_passes_above_70_percent(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Signal with 95% confidence should pass confidence gate"""
        valid_buy_signal.confidence = 0.95
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        # May fail other checks, but not confidence
        assert result.rejection_reason != RejectionReason.CONFIDENCE_TOO_LOW


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 2: Price Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestPriceValidation:
    """Test Rule 2: Valid price levels (entry between stop and target)"""
    
    def test_buy_signal_valid_prices(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """BUY signal: stop < entry < target should be valid"""
        valid_buy_signal.signal_type = "BUY"
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.target_price = 107.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        # May not pass overall, but price validation should pass
        assert result.rejection_reason != RejectionReason.INVALID_PRICE_LEVELS
    
    def test_buy_signal_invalid_prices_entry_above_target(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """BUY signal: entry > target is invalid"""
        valid_buy_signal.signal_type = "BUY"
        valid_buy_signal.entry_price = 110.0
        valid_buy_signal.target_price = 107.0  # Entry above target!
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.INVALID_PRICE_LEVELS
    
    def test_buy_signal_invalid_prices_entry_below_stop(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """BUY signal: entry < stop_loss is invalid"""
        valid_buy_signal.signal_type = "BUY"
        valid_buy_signal.stop_loss = 105.0  # Stop above entry!
        valid_buy_signal.entry_price = 100.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.INVALID_PRICE_LEVELS
    
    def test_sell_signal_valid_prices(self, risk_manager, valid_sell_signal, healthy_portfolio):
        """SELL signal: target < entry < stop_loss should be valid"""
        valid_sell_signal.signal_type = "SELL"
        valid_sell_signal.target_price = 279.0
        valid_sell_signal.entry_price = 300.0
        valid_sell_signal.stop_loss = 315.0
        
        result = risk_manager.validate(valid_sell_signal, healthy_portfolio)
        # May not pass overall, but price validation should pass
        assert result.rejection_reason != RejectionReason.INVALID_PRICE_LEVELS
    
    def test_sell_signal_invalid_prices(self, risk_manager, valid_sell_signal, healthy_portfolio):
        """SELL signal: entry < target is invalid"""
        valid_sell_signal.signal_type = "SELL"
        valid_sell_signal.target_price = 310.0  # Target above entry!
        valid_sell_signal.entry_price = 300.0
        
        result = risk_manager.validate(valid_sell_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.INVALID_PRICE_LEVELS


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 3: Risk/Reward Ratio
# ═══════════════════════════════════════════════════════════════════════════════


class TestRiskRewardRatio:
    """Test Rule 3: Risk/reward >= 1:2"""
    
    def test_2_to_1_ratio_passes(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Exactly 2:1 ratio should pass"""
        # Entry 100, stop 95 (-5 risk), target 110 (+10 reward) = 2:1
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.target_price = 110.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert result.rejection_reason != RejectionReason.RISK_REWARD_UNFAVORABLE
    
    def test_3_to_1_ratio_passes(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Better ratio (3:1) should pass"""
        # Entry 100, stop 95 (-5 risk), target 115 (+15 reward) = 3:1
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.target_price = 115.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert result.rejection_reason != RejectionReason.RISK_REWARD_UNFAVORABLE
    
    def test_1to1_ratio_fails(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """1:1 ratio (unfavorable) should fail"""
        # Entry 100, stop 95 (-5 risk), target 105 (+5 reward) = 1:1
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.target_price = 105.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert result.rejection_reason == RejectionReason.RISK_REWARD_UNFAVORABLE
    
    def test_1point5_to_1_ratio_fails(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Below 2:1 ratio should fail"""
        # Entry 100, stop 95 (-5 risk), target 107.5 (+7.5 reward) = 1.5:1
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.target_price = 107.5
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert result.rejection_reason == RejectionReason.RISK_REWARD_UNFAVORABLE


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 4: Position Sizing
# ═══════════════════════════════════════════════════════════════════════════════


class TestPositionSizing:
    """Test Rule 4: Position sizing (max 2% risk, max 20% size)"""
    
    def test_position_size_calculation(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Test that position size is calculated correctly"""
        # Portfolio: $10k, Entry: $100, Stop: $95 (risk $5)
        # Max risk: 2% = $200
        # Shares: $200 / $5 = 40 shares = $4000 (40% of portfolio)
        # Capped at 20% = $2000
        
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 95.0
        valid_buy_signal.target_price = 107.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        # Position size should be capped at 20%
        assert result.position_size_pct <= 0.20
        # Risk should be at most 2%
        assert result.risk_dollars <= healthy_portfolio.portfolio_value * 0.02 * 1.01  # Allow 1% tolerance
    
    def test_position_size_respects_20_percent_cap(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Position shouldn't exceed 20% of portfolio even with small stop loss"""
        # Portfolio: $10k, Entry: $100, Stop: $99 (only $1 risk)
        # Max risk: 2% = $200, but shares = $200/$1 = 200 = $20k (200%!)
        # Should be capped at 20% = $2000
        
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 99.0  # Very tight stop (1% risk)
        valid_buy_signal.target_price = 102.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        assert result.position_size_pct <= 0.20
        assert result.position_size_dollars <= healthy_portfolio.portfolio_value * 0.20


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 5: Portfolio Constraints
# ═══════════════════════════════════════════════════════════════════════════════


class TestPortfolioConstraints:
    """Test Rule 5: Portfolio constraints (max 5 positions, max 15% drawdown)"""
    
    def test_max_positions_constraint(self, risk_manager, valid_buy_signal):
        """Signal should fail when portfolio already has 5 positions"""
        portfolio_at_limit = PortfolioState(
            portfolio_value=10000,
            current_positions=5,  # Already at max!
            portfolio_drawdown_pct=5.0
        )
        
        result = risk_manager.validate(valid_buy_signal, portfolio_at_limit)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.MAX_POSITIONS_EXCEEDED
    
    def test_max_positions_just_under_limit(self, risk_manager, valid_buy_signal):
        """Signal should pass with 4 positions (under 5 limit)"""
        portfolio_nearly_full = PortfolioState(
            portfolio_value=10000,
            current_positions=4,  # Just under limit
            portfolio_drawdown_pct=5.0
        )
        
        result = risk_manager.validate(valid_buy_signal, portfolio_nearly_full)
        # May fail other checks, but not position count
        assert result.rejection_reason != RejectionReason.MAX_POSITIONS_EXCEEDED
    
    def test_drawdown_constraint_exceeded(self, risk_manager, valid_buy_signal):
        """Signal should fail when portfolio drawdown exceeds 15%"""
        high_drawdown_portfolio = PortfolioState(
            portfolio_value=10000,
            current_positions=2,
            portfolio_drawdown_pct=16.0  # 16% > 15% limit
        )
        
        result = risk_manager.validate(valid_buy_signal, high_drawdown_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.PORTFOLIO_IN_DRAWDOWN
    
    def test_drawdown_constraint_just_under_limit(self, risk_manager, valid_buy_signal):
        """Signal should pass with 14.9% drawdown"""
        moderate_drawdown = PortfolioState(
            portfolio_value=10000,
            current_positions=2,
            portfolio_drawdown_pct=14.9  # Just under 15% limit
        )
        
        result = risk_manager.validate(valid_buy_signal, moderate_drawdown)
        # May fail other checks, but not drawdown
        assert result.rejection_reason != RejectionReason.PORTFOLIO_IN_DRAWDOWN


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 6: Integration Tests (Multiple Rules)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Test combinations of rules together"""
    
    def test_valid_signal_passes_all_checks(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """A well-formed signal should pass all checks"""
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert result.passed, f"Signal failed: {result.rejection_message}"
    
    def test_signal_fails_on_first_violation(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Signal should fail immediately on first rule violation (confidence)"""
        # Set confidence below threshold
        valid_buy_signal.confidence = 0.50
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        # Should fail on confidence, not later checks
        assert result.rejection_reason == RejectionReason.CONFIDENCE_TOO_LOW
    
    def test_multiple_violations_report_first(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """With multiple violations, only first is reported"""
        # Violate both confidence and price levels
        valid_buy_signal.confidence = 0.30  # Too low
        valid_buy_signal.entry_price = 110.0  # Entry > target (also invalid)
        valid_buy_signal.target_price = 105.0
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        # Should report first violation (confidence)
        assert result.rejection_reason == RejectionReason.CONFIDENCE_TOO_LOW
    
    def test_statistics_tracking(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Risk manager should track validation statistics"""
        stats_before = risk_manager.get_stats()
        assert stats_before['total_validations'] == 0
        
        # Run a validation
        risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        stats_after = risk_manager.get_stats()
        assert stats_after['total_validations'] == 1
        assert stats_after['accepted_signals'] == 1
        assert stats_after['rejected_signals'] == 0
    
    def test_reset_statistics(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Statistics should reset properly"""
        # Run several validations
        for _ in range(3):
            risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        stats = risk_manager.get_stats()
        assert stats['total_validations'] == 3
        
        # Reset
        risk_manager.reset_stats()
        
        reset_stats = risk_manager.get_stats()
        assert reset_stats['total_validations'] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 7: Edge Cases & Error Handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test unusual or boundary conditions"""
    
    def test_missing_required_fields(self, risk_manager, healthy_portfolio):
        """Signal with missing fields should fail"""
        incomplete_signal = SignalValidationRequest(
            ticker="AAPL",
            signal_type="BUY",
            confidence=0.80,
            entry_price=100.0,
            target_price=None,  # Missing!
            stop_loss=95.0
        )
        
        result = risk_manager.validate(incomplete_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.MISSING_REQUIRED_FIELDS
    
    def test_invalid_confidence_value(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Confidence > 1.0 should be rejected"""
        valid_buy_signal.confidence = 1.5  # Invalid!
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.MISSING_REQUIRED_FIELDS
    
    def test_negative_prices_rejected(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Negative prices should be rejected"""
        valid_buy_signal.entry_price = -100.0  # Invalid!
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed
        assert result.rejection_reason == RejectionReason.MISSING_REQUIRED_FIELDS
    
    def test_zero_risk_distance(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Entry == stop_loss (zero risk) should fail price validation"""
        valid_buy_signal.entry_price = 100.0
        valid_buy_signal.stop_loss = 100.0  # Same as entry!
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        assert not result.passed


# ═══════════════════════════════════════════════════════════════════════════════
# Test Suite 8: Validation Notes
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidationNotes:
    """Test that validation notes are informative"""
    
    def test_passed_signal_has_positive_notes(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Passing signal should have positive notes"""
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        if result.passed:
            assert len(result.validation_notes) > 0
            # All notes should contain checkmarks and rule names
            for note in result.validation_notes:
                assert '✅' in note or '✔' in note
    
    def test_failed_signal_has_rejection_message(self, risk_manager, valid_buy_signal, healthy_portfolio):
        """Failed signal should explain why"""
        valid_buy_signal.confidence = 0.50  # Too low
        
        result = risk_manager.validate(valid_buy_signal, healthy_portfolio)
        
        assert not result.passed
        assert result.rejection_message is not None
        assert len(result.rejection_message) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
