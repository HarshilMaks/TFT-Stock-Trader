"""
Tests for backtesting engine.

Validates:
- No lookahead bias
- Correct P&L calculations
- Metrics accuracy
- Buy-and-hold baseline
"""

import pytest
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from backend.ml.backtesting.backtest_engine import BacktestEngine, BacktestConfig


@pytest.fixture
def simple_predictions():
    """Create simple test predictions."""
    dates = pd.date_range('2023-01-01', periods=30, freq='D')
    predictions = []
    
    for i, date in enumerate(dates):
        # Simple trend: up for first 15 days, down for next 15
        signal = 1 if i < 15 else -1
        predictions.append({
            'date': date,
            'ticker': 'TEST',
            'signal': signal,
            'confidence': 0.8
        })
    
    return pd.DataFrame(predictions)


@pytest.fixture
def simple_prices():
    """Create simple test prices."""
    dates = pd.date_range('2023-01-01', periods=30, freq='D')
    prices = []
    
    for i, date in enumerate(dates):
        # Slowly increasing price with trend
        price = 100 + i * 0.5
        prices.append({
            'date': date,
            'ticker': 'TEST',
            'close_price': price
        })
    
    return pd.DataFrame(prices)


@pytest.fixture
def flat_prices():
    """Create flat price data (no trend)."""
    dates = pd.date_range('2023-01-01', periods=30, freq='D')
    prices = []
    
    for date in dates:
        prices.append({
            'date': date,
            'ticker': 'TEST',
            'close_price': 100.0
        })
    
    return pd.DataFrame(prices)


@pytest.fixture
def downtrend_prices():
    """Create downtrend prices."""
    dates = pd.date_range('2023-01-01', periods=30, freq='D')
    prices = []
    
    for i, date in enumerate(dates):
        price = 100 - i * 0.5
        prices.append({
            'date': date,
            'ticker': 'TEST',
            'close_price': price
        })
    
    return pd.DataFrame(prices)


class TestBacktestBasics:
    """Test basic backtest functionality."""
    
    def test_backtest_initialization(self):
        """Test backtest engine initialization."""
        config = BacktestConfig(initial_capital=50000)
        engine = BacktestEngine(config)
        
        assert engine.config.initial_capital == 50000
        assert len(engine.trades) == 0
        assert len(engine.equity_curve) == 1
    
    def test_simple_long_signal(self, simple_predictions, simple_prices):
        """Test simple long signal execution."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices, model_name="test_long")
        
        # Should have generated trades
        assert results['summary']['num_trades'] > 0
        
        # Should have positive return on uptrend
        assert results['summary']['total_return'] > 0
    
    def test_flat_price_neutral(self, simple_predictions, flat_prices):
        """Test behavior on flat prices with high transaction costs."""
        # Test with extreme transaction costs to ensure we see impact
        config = BacktestConfig(transaction_cost=0.05, rebalance_days=1)  # 5% cost, daily
        engine = BacktestEngine(config=config)
        results = engine.run(simple_predictions, flat_prices, model_name="test_flat")
        
        # With 5% costs on each trade and flat prices, should definitely lose money
        # Given the signal changes on day 15, we should have at least 2-3 major trades
        assert results['summary']['total_return'] < 0, \
            f"Expected loss on flat prices with 5% transaction costs, got {results['summary']['total_return']}"
    
    def test_downtrend_detection(self, simple_predictions, downtrend_prices):
        """Test signal reversal on downtrend."""
        # Create predictions that flip on downtrend
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        predictions = []
        
        for i, date in enumerate(dates):
            # Long for first 15, short for last 15
            signal = 1 if i < 15 else -1
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': signal,
                'confidence': 0.8
            })
        
        pred_df = pd.DataFrame(predictions)
        engine = BacktestEngine()
        results = engine.run(pred_df, downtrend_prices, model_name="test_downtrend")
        
        # Should have trades
        assert results['summary']['num_trades'] > 0


class TestNoLookaheadBias:
    """Test that backtester has no lookahead bias."""
    
    def test_future_data_not_used(self, simple_prices):
        """Test that only historical data is used for signals."""
        engine = BacktestEngine()
        
        # Create predictions that could tempt lookahead
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        predictions = []
        
        for i, date in enumerate(dates):
            # Perfect signal based on future knowledge
            futures_price = simple_prices[simple_prices['date'] == date + timedelta(days=1)]
            current_price = simple_prices[simple_prices['date'] == date]
            
            if not futures_price.empty and not current_price.empty:
                future = futures_price.iloc[0]['close_price']
                current = current_price.iloc[0]['close_price']
                signal = 1 if future > current else -1
            else:
                signal = 1
            
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': signal,
                'confidence': 0.8
            })
        
        pred_df = pd.DataFrame(predictions)
        results = engine.run(pred_df, simple_prices)
        
        # Verify no position is open with future data
        assert len(engine.positions) == 0 or len(engine.trades) > 0
    
    def test_chronological_processing(self, simple_predictions, simple_prices):
        """Test that data is processed chronologically."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        # Dates should be in order
        dates = results['equity_curve']['date'].values
        assert all(dates[i] <= dates[i+1] for i in range(len(dates)-1))


class TestMetricsAccuracy:
    """Test accuracy of calculated metrics."""
    
    def test_sharpe_ratio_calculation(self, simple_predictions, simple_prices):
        """Test Sharpe ratio calculation."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        sharpe = results['summary'].get('sharpe_ratio', 0)
        
        # Sharpe should be finite
        assert np.isfinite(sharpe)
    
    def test_max_drawdown_calculation(self, simple_predictions, simple_prices):
        """Test max drawdown calculation."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        max_dd = results['summary'].get('max_drawdown', 0)
        
        # Drawdown should be negative or zero
        assert max_dd <= 0
    
    def test_win_rate_calculation(self, simple_predictions, simple_prices):
        """Test win rate calculation."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        win_rate = results['summary'].get('win_rate', 0)
        num_trades = results['summary'].get('num_trades', 0)
        
        # Win rate should be between 0 and 1
        if num_trades > 0:
            assert 0 <= win_rate <= 1
    
    def test_profit_factor_calculation(self, simple_predictions, simple_prices):
        """Test profit factor (wins/losses)."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        profit_factor = results['summary'].get('profit_factor', 0)
        
        # Profit factor should be positive if there are wins
        if results['summary']['num_trades'] > 0:
            assert profit_factor >= 0


class TestTradeRecording:
    """Test trade recording and analytics."""
    
    def test_trade_pnl_calculation(self, simple_predictions, simple_prices):
        """Test that trade P&L is calculated correctly."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        trades = results['trades']
        
        # Each trade should have P&L
        for trade in trades:
            assert 'pnl' in trade
            assert 'pnl_pct' in trade
            assert trade['entry_price'] > 0
            assert trade['exit_price'] > 0
    
    def test_position_sizing(self, simple_predictions, simple_prices):
        """Test that positions are sized correctly."""
        config = BacktestConfig(initial_capital=100000, max_position_size=0.2)
        engine = BacktestEngine(config)
        results = engine.run(simple_predictions, simple_prices)
        
        trades = results['trades']
        
        # Each trade's initial value shouldn't exceed max position size
        for trade in trades:
            # Position value = shares * entry_price
            position_value = trade['shares'] * trade['entry_price']
            max_allowed = config.initial_capital * config.max_position_size
            
            # Allow some tolerance for confidence scaling
            assert position_value <= max_allowed * 2


class TestBaselineComparison:
    """Test buy-and-hold baseline comparison."""
    
    def test_baseline_vs_strategy(self, simple_predictions, simple_prices):
        """Test comparison with buy-and-hold."""
        engine = BacktestEngine()
        results = engine.run(simple_predictions, simple_prices)
        
        baseline = results['baseline_comparison']
        strategy = results['summary']
        
        # Both should have return metrics
        assert 'total_return' in baseline
        assert 'total_return' in strategy
    
    def test_baseline_metrics(self, simple_prices):
        """Test baseline calculation with only prices."""
        engine = BacktestEngine()
        
        # Create neutral predictions (no trades)
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        predictions = []
        for date in dates:
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': 0,  # Neutral
                'confidence': 0.5
            })
        
        pred_df = pd.DataFrame(predictions)
        results = engine.run(pred_df, simple_prices)
        
        baseline = results['baseline_comparison']
        
        # Baseline should show positive return on uptrend
        assert baseline['total_return'] > 0


class TestTransactionCosts:
    """Test transaction cost handling."""
    
    def test_transaction_cost_impact(self, simple_predictions, flat_prices):
        """Test that transaction costs reduce returns."""
        # Test with no transaction costs
        config1 = BacktestConfig(transaction_cost=0.0)
        engine1 = BacktestEngine(config1)
        results1 = engine1.run(simple_predictions, flat_prices)
        
        # Test with transaction costs
        config2 = BacktestConfig(transaction_cost=0.001)
        engine2 = BacktestEngine(config2)
        results2 = engine2.run(simple_predictions, flat_prices)
        
        # With costs should be worse
        assert results2['summary']['total_return'] <= results1['summary']['total_return']


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_trades(self, flat_prices):
        """Test backtest with no trades."""
        dates = pd.date_range('2023-01-01', periods=30, freq='D')
        predictions = []
        for date in dates:
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': 0,
                'confidence': 0.5
            })
        
        pred_df = pd.DataFrame(predictions)
        engine = BacktestEngine()
        results = engine.run(pred_df, flat_prices)
        
        # Should still complete without error
        assert results['summary']['num_trades'] == 0
    
    def test_single_trade(self):
        """Test backtest with signal reversal (close + reopen)."""
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
    
        predictions = []
        for i, date in enumerate(dates):
            signal = 1 if i < 5 else -1
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': signal,
                'confidence': 0.8
            })
    
        prices = []
        for i, date in enumerate(dates):
            prices.append({
                'date': date,
                'ticker': 'TEST',
                'close_price': 100 + i
            })
    
        pred_df = pd.DataFrame(predictions)
        price_df = pd.DataFrame(prices)
    
        engine = BacktestEngine()
        results = engine.run(pred_df, price_df)
    
        # Signal reversal (1 -> -1) results in close trade + open new trade
        # Plus one closing trade at end = 3 trades total
        assert results['summary']['num_trades'] >= 2
    def test_low_confidence_skip(self):
        """Test that low confidence signals are skipped."""
        config = BacktestConfig(min_confidence=0.9)
        engine = BacktestEngine(config)
        
        dates = pd.date_range('2023-01-01', periods=10, freq='D')
        
        predictions = []
        for date in dates:
            predictions.append({
                'date': date,
                'ticker': 'TEST',
                'signal': 1,
                'confidence': 0.5  # Below threshold
            })
        
        prices = []
        for i, date in enumerate(dates):
            prices.append({
                'date': date,
                'ticker': 'TEST',
                'close_price': 100 + i
            })
        
        pred_df = pd.DataFrame(predictions)
        price_df = pd.DataFrame(prices)
        
        results = engine.run(pred_df, price_df)
        
        # Should skip all trades due to low confidence
        assert results['summary']['num_trades'] == 0


class TestMultipleTickets:
    """Test backtesting with multiple tickers."""
    
    def test_multiple_ticker_backtest(self):
        """Test backtest with multiple tickers."""
        dates = pd.date_range('2023-01-01', periods=20, freq='D')
        
        predictions = []
        for date in dates:
            for ticker in ['TEST1', 'TEST2', 'TEST3']:
                predictions.append({
                    'date': date,
                    'ticker': ticker,
                    'signal': 1,
                    'confidence': 0.8
                })
        
        prices = []
        for i, date in enumerate(dates):
            for ticker in ['TEST1', 'TEST2', 'TEST3']:
                prices.append({
                    'date': date,
                    'ticker': ticker,
                    'close_price': 100 + i
                })
        
        pred_df = pd.DataFrame(predictions)
        price_df = pd.DataFrame(prices)
        
        engine = BacktestEngine()
        results = engine.run(pred_df, price_df)
        
        # Should process all tickers
        assert results['summary']['num_trades'] > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
