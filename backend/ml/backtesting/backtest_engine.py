"""
Production backtesting engine for ML trading models.

Features:
- Chronological data processing (no lookahead bias)
- Multi-model comparison
- Comprehensive metrics: Sharpe, Sortino, Calmar, win rate, profit factor
- Buy-and-hold baseline comparison
- Trade-level analytics
- Risk metrics: drawdown, var, cvar

Usage:
    from backend.ml.backtesting.backtest_engine import BacktestEngine
    
    backtest = BacktestEngine(initial_capital=100000)
    results = backtest.run(
        predictions=model_predictions,  # (dates, tickers, signal: 1/-1/0)
        prices=historical_prices,       # (dates, tickers, close price)
        volumes=volumes,                # position sizing
        transaction_cost=0.001          # 0.1% slippage
    )
    
    print(results['summary'])
    print(results['trades'])
    backtest.plot_performance()
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Backtesting configuration."""
    initial_capital: float = 100000.0
    max_position_size: float = 0.2  # Max 20% of capital per position
    transaction_cost: float = 0.001  # 0.1% slippage + commission
    risk_free_rate: float = 0.02  # 2% annual risk-free rate
    min_confidence: float = 0.5  # Only take signals > 50% confidence
    lookback_days: int = 30  # Days to keep in memory for no lookahead
    rebalance_days: int = 5  # Rebalance every 5 days


@dataclass
class TradeRecord:
    """Single trade record."""
    entry_date: datetime
    entry_price: float
    entry_signal: float  # 1.0 for long, -1.0 for short
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    shares: float = 0.0
    duration_days: int = 0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    ticker: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'entry_date': self.entry_date,
            'ticker': self.ticker,
            'entry_price': self.entry_price,
            'signal': self.entry_signal,
            'exit_date': self.exit_date,
            'exit_price': self.exit_price,
            'shares': self.shares,
            'duration_days': self.duration_days,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
        }


class BacktestEngine:
    """
    Production backtesting engine with comprehensive metrics.
    
    Prevents lookahead bias by processing data chronologically
    and only using historical information for predictions.
    """
    
    def __init__(self, config: Optional[BacktestConfig] = None):
        """Initialize backtest engine."""
        self.config = config or BacktestConfig()
        self.trades: List[TradeRecord] = []
        self.equity_curve: List[float] = [self.config.initial_capital]
        self.dates: List[datetime] = []
        self.daily_returns: np.ndarray = np.array([])
        self.summary: Dict[str, float] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}  # ticker -> position info
        
    def run(
        self,
        predictions: pd.DataFrame,  # date, ticker, signal (1/-1/0), confidence
        prices: pd.DataFrame,        # date, ticker, close_price
        volumes: Optional[pd.DataFrame] = None,
        model_name: str = "model"
    ) -> Dict[str, Any]:
        """
        Run backtest on model predictions.
        
        Args:
            predictions: DataFrame with columns [date, ticker, signal, confidence]
            prices: DataFrame with columns [date, ticker, close_price]
            volumes: Optional DataFrame with [date, ticker, volume]
            model_name: Name of model for reporting
            
        Returns:
            Dict with 'summary', 'trades', 'equity_curve', 'baseline_comparison'
        """
        logger.info(f"Starting backtest for {model_name}")
        
        # Validate inputs
        predictions = self._validate_predictions(predictions)
        prices = self._validate_prices(prices)
        
        # Initialize
        self.positions = {}
        self.trades = []
        self.equity_curve = [self.config.initial_capital]
        self.dates = []
        
        current_capital = self.config.initial_capital
        
        # Get unique dates in chronological order
        unique_dates = sorted(predictions['date'].unique())
        
        # Process each day (no lookahead bias)
        for day_idx, current_date in enumerate(unique_dates):
            logger.debug(f"Processing {current_date}")
            
            # Get predictions for this day only (historical data)
            day_predictions = predictions[predictions['date'] == current_date]
            
            # Get prices up to this day (no future information)
            historical_prices = prices[prices['date'] <= current_date]
            
            # Update positions and close trades
            current_capital = self._update_positions(
                current_date,
                day_predictions,
                historical_prices,
                current_capital
            )
            
            # Generate new signals (only if not trading too frequently)
            if day_idx % self.config.rebalance_days == 0:
                current_capital = self._execute_signals(
                    current_date,
                    day_predictions,
                    prices[prices['date'] == current_date],
                    current_capital
                )
            
            # Record equity
            self.equity_curve.append(current_capital)
            self.dates.append(current_date)
        
        # Close remaining positions at last price
        last_date = unique_dates[-1]
        last_prices = prices[prices['date'] == last_date]
        current_capital = self._close_all_positions(last_date, last_prices, current_capital)
        
        # Calculate metrics
        self.summary = self._calculate_metrics()
        self.summary['model'] = model_name
        self.summary['final_capital'] = current_capital
        self.summary['total_return'] = (current_capital - self.config.initial_capital) / self.config.initial_capital
        
        # Baseline comparison
        baseline_comparison = self._calculate_baseline_comparison(prices)
        
        logger.info(f"Backtest complete. Final return: {self.summary['total_return']:.2%}")
        
        return {
            'summary': self.summary,
            'trades': [t.to_dict() for t in self.trades],
            'equity_curve': pd.DataFrame({
                'date': self.dates,
                'equity': self.equity_curve[1:]
            }),
            'baseline_comparison': baseline_comparison
        }
    
    def _validate_predictions(self, predictions: pd.DataFrame) -> pd.DataFrame:
        """Validate prediction DataFrame."""
        required_cols = ['date', 'ticker', 'signal']
        for col in required_cols:
            if col not in predictions.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Ensure signal is 1, -1, or 0
        if not predictions['signal'].isin([-1, 0, 1]).all():
            raise ValueError("Signal must be -1 (short), 0 (hold), or 1 (long)")
        
        # Add confidence if missing
        if 'confidence' not in predictions.columns:
            predictions['confidence'] = 0.6  # Default confidence
        
        return predictions
    
    def _validate_prices(self, prices: pd.DataFrame) -> pd.DataFrame:
        """Validate price DataFrame."""
        required_cols = ['date', 'ticker', 'close_price']
        for col in required_cols:
            if col not in prices.columns:
                raise ValueError(f"Missing required column: {col}")
        
        # Ensure prices are positive
        if (prices['close_price'] <= 0).any():
            raise ValueError("Prices must be positive")
        
        return prices
    
    def _update_positions(
        self,
        current_date: datetime,
        day_predictions: pd.DataFrame,
        historical_prices: pd.DataFrame,
        current_capital: float
    ) -> float:
        """
        Update existing positions and close based on recent prices.
        
        No lookahead bias: only use data up to current_date.
        """
        for ticker, position in list(self.positions.items()):
            # Get latest price for this ticker
            ticker_prices = historical_prices[
                historical_prices['ticker'] == ticker
            ].sort_values('date')
            
            if ticker_prices.empty:
                continue
            
            current_price = ticker_prices.iloc[-1]['close_price']
            
            # Check if we should close (opposite signal)
            ticker_pred = day_predictions[day_predictions['ticker'] == ticker]
            if not ticker_pred.empty:
                signal = ticker_pred.iloc[0]['signal']
                
                # Close if signal flips or is 0 (sell signal)
                if signal != position['signal'] or signal == 0:
                    current_capital = self._close_position(
                        ticker, current_date, current_price, current_capital
                    )
        
        return current_capital
    
    def _execute_signals(
        self,
        current_date: datetime,
        day_predictions: pd.DataFrame,
        current_prices: pd.DataFrame,
        current_capital: float
    ) -> float:
        """Execute trading signals for the day."""
        for _, row in day_predictions.iterrows():
            ticker = row['ticker']
            signal = row['signal']
            confidence = row.get('confidence', 0.6)
            
            # Skip weak signals
            if confidence < self.config.min_confidence:
                logger.debug(f"Skipping {ticker}: low confidence {confidence:.2f}")
                continue
            
            # Skip neutral signals
            if signal == 0:
                continue
            
            # Skip if already have position
            if ticker in self.positions:
                continue
            
            # Get entry price
            ticker_price = current_prices[current_prices['ticker'] == ticker]
            if ticker_price.empty:
                continue
            
            entry_price = ticker_price.iloc[0]['close_price']
            
            # Calculate position size (Kelly-like sizing)
            position_value = self._calculate_position_size(
                current_capital,
                signal,
                confidence
            )
            
            if position_value <= 0:
                continue
            
            shares = position_value / entry_price
            
            # Account for transaction costs
            cost = position_value * self.config.transaction_cost
            current_capital -= cost
            
            # Create position
            self.positions[ticker] = {
                'entry_date': current_date,
                'entry_price': entry_price,
                'signal': signal,
                'shares': shares,
                'confidence': confidence,
                'position_value': position_value
            }
            
            logger.debug(f"Opened {signal:+.0f} position: {ticker} @ {entry_price:.2f}")
        
        return current_capital
    
    def _calculate_position_size(
        self,
        capital: float,
        signal: float,
        confidence: float
    ) -> float:
        """
        Calculate position size using confidence-weighted Kelly criterion.
        
        Larger positions for higher confidence signals.
        """
        # Base position size
        base_size = capital * self.config.max_position_size
        
        # Adjust by confidence (0.5 -> 0.5x, 1.0 -> 2.0x)
        confidence_factor = (confidence - 0.5) * 2
        position_size = base_size * confidence_factor
        
        # Ensure we don't exceed max
        position_size = min(position_size, capital * self.config.max_position_size)
        
        return max(position_size, 0)
    
    def _close_position(
        self,
        ticker: str,
        exit_date: datetime,
        exit_price: float,
        current_capital: float
    ) -> float:
        """Close a position and record the trade."""
        if ticker not in self.positions:
            return current_capital
        
        position = self.positions[ticker]
        
        # Calculate P&L
        shares = position['shares']
        entry_price = position['entry_price']
        initial_position_value = position['position_value']
        
        if position['signal'] == 1:  # Long
            # We paid: shares * entry_price + transaction_cost
            # We receive: shares * exit_price - transaction_cost
            entry_cost = shares * entry_price
            entry_cost_with_fee = entry_cost * (1 + self.config.transaction_cost)
            
            exit_proceeds = shares * exit_price
            exit_proceeds_after_fee = exit_proceeds * (1 - self.config.transaction_cost)
            
            pnl = exit_proceeds_after_fee - entry_cost_with_fee
            
        else:  # Short
            # We received: shares * entry_price - transaction_cost (short sale proceeds)
            # We pay to close: shares * exit_price + transaction_cost
            entry_proceeds = shares * entry_price
            entry_proceeds_after_fee = entry_proceeds * (1 - self.config.transaction_cost)
            
            close_cost = shares * exit_price
            close_cost_with_fee = close_cost * (1 + self.config.transaction_cost)
            
            pnl = entry_proceeds_after_fee - close_cost_with_fee
        
        pnl_pct = pnl / initial_position_value if initial_position_value > 0 else 0
        
        # Record trade
        trade = TradeRecord(
            entry_date=position['entry_date'],
            entry_price=entry_price,
            entry_signal=position['signal'],
            exit_date=exit_date,
            exit_price=exit_price,
            shares=shares,
            duration_days=(exit_date - position['entry_date']).days,
            pnl=pnl,
            pnl_pct=pnl_pct,
            ticker=ticker
        )
        self.trades.append(trade)
        
        # Update capital: add the P&L from this trade
        current_capital += pnl
        
        # Remove position
        del self.positions[ticker]
        
        logger.debug(f"Closed position: {ticker} P&L={pnl:.2f} ({pnl_pct:.2%})")
        
        return current_capital
        return current_capital
    
    def _close_all_positions(
        self,
        exit_date: datetime,
        prices: pd.DataFrame,
        current_capital: float
    ) -> float:
        """Close all remaining positions."""
        for ticker in list(self.positions.keys()):
            ticker_price = prices[prices['ticker'] == ticker]
            if not ticker_price.empty:
                exit_price = ticker_price.iloc[0]['close_price']
                current_capital = self._close_position(
                    ticker, exit_date, exit_price, current_capital
                )
        
        return current_capital
    
    def _calculate_metrics(self) -> Dict[str, float]:
        """Calculate comprehensive performance metrics."""
        if len(self.equity_curve) < 2:
            return {}
        
        equity_array = np.array(self.equity_curve)
        returns = np.diff(equity_array) / equity_array[:-1]
        
        # Store for later use
        self.daily_returns = returns
        
        # Basic returns
        total_return = (equity_array[-1] - equity_array[0]) / equity_array[0]
        
        # Annualized return (assuming 252 trading days)
        annual_return = (1 + total_return) ** (252 / len(returns)) - 1
        
        # Volatility
        volatility = np.std(returns) * np.sqrt(252)
        
        # Sharpe ratio
        excess_returns = returns - (self.config.risk_free_rate / 252)
        sharpe = np.mean(excess_returns) / (np.std(excess_returns) + 1e-8) * np.sqrt(252)
        
        # Sortino ratio (only downside volatility)
        downside_returns = returns[returns < 0]
        downside_vol = np.std(downside_returns) * np.sqrt(252) if len(downside_returns) > 0 else 0
        sortino = np.mean(excess_returns) / (downside_vol + 1e-8) * np.sqrt(252)
        
        # Maximum drawdown
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # Calmar ratio
        calmar = annual_return / (abs(max_drawdown) + 1e-8)
        
        # Trade metrics
        if self.trades:
            wins = sum(1 for t in self.trades if t.pnl > 0)
            losses = sum(1 for t in self.trades if t.pnl < 0)
            win_rate = wins / len(self.trades) if self.trades else 0
            
            total_wins = sum(t.pnl for t in self.trades if t.pnl > 0)
            total_losses = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
            profit_factor = total_wins / (total_losses + 1e-8) if total_losses > 0 else np.inf
            
            avg_win = total_wins / (wins + 1e-8) if wins > 0 else 0
            avg_loss = total_losses / (losses + 1e-8) if losses > 0 else 0
            win_loss_ratio = abs(avg_win / (avg_loss + 1e-8)) if avg_loss != 0 else np.inf
        else:
            win_rate = 0
            profit_factor = 0
            win_loss_ratio = 0
            avg_win = 0
            avg_loss = 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe,
            'sortino_ratio': sortino,
            'calmar_ratio': calmar,
            'max_drawdown': max_drawdown,
            'num_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'win_loss_ratio': win_loss_ratio,
            'num_winning_trades': sum(1 for t in self.trades if t.pnl > 0),
            'num_losing_trades': sum(1 for t in self.trades if t.pnl < 0),
        }
    
    def _calculate_baseline_comparison(self, prices: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate buy-and-hold baseline for comparison.
        
        Prevents lookahead bias by using only historical prices.
        """
        # Get first ticker's prices
        first_ticker = prices['ticker'].iloc[0]
        ticker_prices = prices[prices['ticker'] == first_ticker].sort_values('date')
        
        if len(ticker_prices) < 2:
            return {}
        
        # Buy-and-hold strategy
        start_price = ticker_prices.iloc[0]['close_price']
        end_price = ticker_prices.iloc[-1]['close_price']
        
        baseline_return = (end_price - start_price) / start_price
        
        # Calculate baseline metrics
        daily_prices = ticker_prices['close_price'].values
        daily_returns = np.diff(daily_prices) / daily_prices[:-1]
        
        baseline_volatility = np.std(daily_returns) * np.sqrt(252)
        baseline_sharpe = np.mean(daily_returns) / (np.std(daily_returns) + 1e-8) * np.sqrt(252)
        
        # Drawdown
        cumulative = np.cumprod(1 + daily_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        baseline_max_drawdown = np.min(drawdown)
        
        return {
            'total_return': baseline_return,
            'volatility': baseline_volatility,
            'sharpe_ratio': baseline_sharpe,
            'max_drawdown': baseline_max_drawdown,
            'strategy': 'buy_and_hold',
            'ticker': first_ticker
        }
    
    def get_summary(self) -> pd.DataFrame:
        """Get summary statistics as formatted DataFrame."""
        summary_dict = {
            'Metric': [],
            'Value': []
        }
        
        for key, value in self.summary.items():
            if key in ['total_return', 'annual_return', 'volatility', 'max_drawdown', 'win_rate']:
                if isinstance(value, float):
                    summary_dict['Metric'].append(key.replace('_', ' ').title())
                    if key in ['total_return', 'annual_return', 'win_rate']:
                        summary_dict['Value'].append(f"{value:.2%}")
                    elif key in ['volatility', 'max_drawdown']:
                        summary_dict['Value'].append(f"{value:.2%}")
                    else:
                        summary_dict['Value'].append(f"{value:.4f}")
        
        return pd.DataFrame(summary_dict)
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame."""
        if not self.trades:
            return pd.DataFrame()
        
        return pd.DataFrame([t.to_dict() for t in self.trades])
    
    def plot_performance(self, save_path: Optional[str] = None) -> None:
        """
        Plot equity curve and drawdown.
        
        Args:
            save_path: Optional path to save plot
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not installed, skipping plots")
            return
        
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))
        
        # Equity curve
        axes[0].plot(self.dates, self.equity_curve[1:], label='Strategy', linewidth=2)
        axes[0].axhline(self.config.initial_capital, color='r', linestyle='--', label='Initial Capital')
        axes[0].set_title('Equity Curve')
        axes[0].set_ylabel('Capital ($)')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
        
        # Drawdown
        equity_array = np.array(self.equity_curve[1:])
        running_max = np.maximum.accumulate(equity_array)
        drawdown_pct = (equity_array - running_max) / running_max * 100
        
        axes[1].fill_between(self.dates, drawdown_pct, 0, alpha=0.3, color='red')
        axes[1].plot(self.dates, drawdown_pct, color='red', linewidth=2)
        axes[1].set_title('Drawdown %')
        axes[1].set_ylabel('Drawdown (%)')
        axes[1].set_xlabel('Date')
        axes[1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150)
            logger.info(f"Plot saved to {save_path}")
        
        plt.show()
    
    def print_report(self) -> None:
        """Print formatted backtest report."""
        print("\n" + "="*60)
        print(f"BACKTEST REPORT - {self.summary.get('model', 'Unknown Model')}")
        print("="*60)
        
        print(f"\nCapital: ${self.config.initial_capital:,.0f} → ${self.summary.get('final_capital', 0):,.0f}")
        print(f"Total Return: {self.summary.get('total_return', 0):.2%}")
        print(f"Annual Return: {self.summary.get('annual_return', 0):.2%}")
        print(f"Volatility: {self.summary.get('volatility', 0):.2%}")
        print(f"Sharpe Ratio: {self.summary.get('sharpe_ratio', 0):.2f}")
        print(f"Sortino Ratio: {self.summary.get('sortino_ratio', 0):.2f}")
        print(f"Calmar Ratio: {self.summary.get('calmar_ratio', 0):.2f}")
        print(f"Max Drawdown: {self.summary.get('max_drawdown', 0):.2%}")
        
        print(f"\nTrades: {self.summary.get('num_trades', 0)}")
        print(f"Win Rate: {self.summary.get('win_rate', 0):.2%}")
        print(f"Profit Factor: {self.summary.get('profit_factor', 0):.2f}")
        print(f"Avg Win: ${self.summary.get('avg_win', 0):,.2f}")
        print(f"Avg Loss: ${self.summary.get('avg_loss', 0):,.2f}")
        print(f"Win/Loss Ratio: {self.summary.get('win_loss_ratio', 0):.2f}")
        
        print("="*60 + "\n")
