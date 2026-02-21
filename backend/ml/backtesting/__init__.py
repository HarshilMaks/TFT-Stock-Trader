"""
Backtesting module for ML trading models.

Provides:
- Historical signal generation with no lookahead bias
- Trade simulation and P&L calculation
- Performance metrics (Sharpe, drawdown, win rate)
- Baseline comparison (buy-and-hold)
"""

from .backtest_engine import BacktestEngine

__all__ = ["BacktestEngine"]
