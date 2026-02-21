"""
Example: Using the backtest engine with trained models.

This shows complete workflow:
1. Load trained models from MLflow
2. Generate historical predictions
3. Run backtest
4. Compare models
5. Generate report

Usage:
    from backend.ml.backtesting.example_backtest import run_example
    run_example()
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from backend.ml.backtesting.backtest_engine import BacktestEngine, BacktestConfig
from backend.ml.tracking.mlflow_logger import MLflowLogger

logger = logging.getLogger(__name__)


def load_historical_data(
    ticker: str,
    start_date: datetime,
    end_date: datetime
) -> tuple:
    """
    Load historical price data and features.
    
    In production, this would query your database.
    For example, we'll generate sample data.
    """
    dates = pd.date_range(start_date, end_date, freq='D')
    
    prices = []
    features = []
    
    for i, date in enumerate(dates):
        # Sample price (with trend)
        price = 100 + i * 0.3 + np.random.normal(0, 1)
        
        prices.append({
            'date': date,
            'ticker': ticker,
            'close_price': price,
            'volume': 1000000 + np.random.randint(-100000, 100000)
        })
        
        features.append({
            'date': date,
            'ticker': ticker,
            'rsi': 50 + np.random.normal(0, 10),
            'macd': np.random.normal(0, 1),
            'volume_ma': 1000000,
            'price_ma_20': price - 5 + np.random.normal(0, 2)
        })
    
    return pd.DataFrame(prices), pd.DataFrame(features)


def generate_predictions_from_model(
    model,
    features: pd.DataFrame,
    model_name: str = "xgboost"
) -> pd.DataFrame:
    """
    Generate predictions from trained model.
    
    In production, this would load actual trained models.
    """
    predictions = []
    
    for _, row in features.iterrows():
        # In production: model.predict([features])
        # For demo: simple rule-based
        if row['rsi'] < 30:
            signal = 1  # Oversold - buy
            confidence = 0.8
        elif row['rsi'] > 70:
            signal = -1  # Overbought - sell
            confidence = 0.8
        else:
            signal = 0  # Hold
            confidence = 0.5
        
        predictions.append({
            'date': row['date'],
            'ticker': row['ticker'],
            'signal': signal,
            'confidence': confidence,
            'model': model_name
        })
    
    return pd.DataFrame(predictions)


def run_backtest_single_model(
    predictions: pd.DataFrame,
    prices: pd.DataFrame,
    model_name: str,
    initial_capital: float = 100000
) -> dict:
    """
    Run backtest for single model.
    
    Args:
        predictions: Model predictions DataFrame
        prices: Historical prices DataFrame
        model_name: Name of the model
        initial_capital: Starting capital
    
    Returns:
        Dict with backtest results
    """
    config = BacktestConfig(initial_capital=initial_capital)
    engine = BacktestEngine(config)
    
    logger.info(f"Running backtest: {model_name}")
    results = engine.run(
        predictions=predictions,
        prices=prices,
        model_name=model_name
    )
    
    engine.print_report()
    
    return {
        'model_name': model_name,
        'engine': engine,
        'results': results
    }


def compare_multiple_models(
    models_data: list,
    prices: pd.DataFrame
) -> pd.DataFrame:
    """
    Compare performance of multiple models.
    
    Args:
        models_data: List of (model_name, predictions) tuples
        prices: Historical prices DataFrame
    
    Returns:
        Comparison DataFrame
    """
    comparison_rows = []
    
    for model_name, predictions in models_data:
        backtest = run_backtest_single_model(
            predictions=predictions,
            prices=prices,
            model_name=model_name
        )
        
        summary = backtest['results']['summary']
        
        comparison_rows.append({
            'Model': model_name,
            'Total Return': summary.get('total_return', 0),
            'Annual Return': summary.get('annual_return', 0),
            'Sharpe Ratio': summary.get('sharpe_ratio', 0),
            'Max Drawdown': summary.get('max_drawdown', 0),
            'Win Rate': summary.get('win_rate', 0),
            'Num Trades': summary.get('num_trades', 0),
            'Profit Factor': summary.get('profit_factor', 0)
        })
    
    comparison_df = pd.DataFrame(comparison_rows)
    comparison_df = comparison_df.sort_values('Sharpe Ratio', ascending=False)
    
    return comparison_df


def generate_backtest_report(
    backtest: dict,
    output_dir: str = "results/backtests"
) -> str:
    """
    Generate comprehensive backtest report.
    
    Args:
        backtest: Backtest results dict
        output_dir: Directory to save report
    
    Returns:
        Path to report file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    model_name = backtest['model_name']
    results = backtest['results']
    engine = backtest['engine']
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_path / f"{model_name}_backtest_{timestamp}.txt"
    
    with open(report_path, 'w') as f:
        f.write("="*70 + "\n")
        f.write(f"BACKTEST REPORT\n")
        f.write(f"Model: {model_name}\n")
        f.write(f"Date: {datetime.now().isoformat()}\n")
        f.write("="*70 + "\n\n")
        
        # Summary metrics
        f.write("PERFORMANCE METRICS\n")
        f.write("-"*70 + "\n")
        summary = results['summary']
        f.write(f"Initial Capital:        ${100000:,.0f}\n")
        f.write(f"Final Capital:          ${summary.get('final_capital', 0):,.0f}\n")
        f.write(f"Total Return:           {summary.get('total_return', 0):.2%}\n")
        f.write(f"Annual Return:          {summary.get('annual_return', 0):.2%}\n")
        f.write(f"Volatility:             {summary.get('volatility', 0):.2%}\n")
        f.write(f"Sharpe Ratio:           {summary.get('sharpe_ratio', 0):.2f}\n")
        f.write(f"Sortino Ratio:          {summary.get('sortino_ratio', 0):.2f}\n")
        f.write(f"Calmar Ratio:           {summary.get('calmar_ratio', 0):.2f}\n")
        f.write(f"Max Drawdown:           {summary.get('max_drawdown', 0):.2%}\n\n")
        
        # Trade metrics
        f.write("TRADE METRICS\n")
        f.write("-"*70 + "\n")
        f.write(f"Number of Trades:       {summary.get('num_trades', 0)}\n")
        f.write(f"Winning Trades:         {summary.get('num_winning_trades', 0)}\n")
        f.write(f"Losing Trades:          {summary.get('num_losing_trades', 0)}\n")
        f.write(f"Win Rate:               {summary.get('win_rate', 0):.2%}\n")
        f.write(f"Profit Factor:          {summary.get('profit_factor', 0):.2f}\n")
        f.write(f"Avg Win:                ${summary.get('avg_win', 0):,.2f}\n")
        f.write(f"Avg Loss:               ${summary.get('avg_loss', 0):,.2f}\n")
        f.write(f"Win/Loss Ratio:         {summary.get('win_loss_ratio', 0):.2f}\n\n")
        
        # Baseline comparison
        f.write("BASELINE COMPARISON (BUY & HOLD)\n")
        f.write("-"*70 + "\n")
        baseline = results['baseline_comparison']
        f.write(f"Return:                 {baseline.get('total_return', 0):.2%}\n")
        f.write(f"Sharpe Ratio:           {baseline.get('sharpe_ratio', 0):.2f}\n")
        f.write(f"Max Drawdown:           {baseline.get('max_drawdown', 0):.2%}\n")
        f.write(f"Strategy Outperformance: {(summary.get('total_return', 0) - baseline.get('total_return', 0)):.2%}\n\n")
        
        # Recent trades
        f.write("RECENT TRADES (Last 10)\n")
        f.write("-"*70 + "\n")
        trades = results['trades']
        for trade in trades[-10:]:
            f.write(f"{trade['entry_date']} → {trade['exit_date']}: "
                   f"{trade['ticker']} {trade['signal']:+.0f} "
                   f"P&L: ${trade['pnl']:,.2f} ({trade['pnl_pct']:.2%})\n")
    
    logger.info(f"Report saved to {report_path}")
    return str(report_path)


def run_example(
    tickers: list = None,
    start_date: datetime = None,
    end_date: datetime = None
):
    """
    Run complete backtesting example.
    
    Args:
        tickers: List of tickers to backtest
        start_date: Start date for historical data
        end_date: End date for historical data
    """
    if tickers is None:
        tickers = ['AAPL']
    
    if start_date is None:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
    
    print("\n" + "="*70)
    print("BACKTESTING EXAMPLE")
    print("="*70 + "\n")
    
    # 1. Load historical data
    print("1. Loading historical data...")
    all_prices = []
    all_features = []
    
    for ticker in tickers:
        prices, features = load_historical_data(ticker, start_date, end_date)
        all_prices.append(prices)
        all_features.append(features)
    
    prices_df = pd.concat(all_prices, ignore_index=True)
    features_df = pd.concat(all_features, ignore_index=True)
    print(f"   Loaded {len(prices_df)} price records")
    
    # 2. Generate predictions from different models
    print("\n2. Generating predictions from models...")
    models = [
        ('XGBoost', generate_predictions_from_model(None, features_df, 'xgboost')),
        ('LightGBM', generate_predictions_from_model(None, features_df, 'lightgbm')),
        ('TFT', generate_predictions_from_model(None, features_df, 'tft'))
    ]
    print(f"   Generated predictions for {len(models)} models")
    
    # 3. Run backtests
    print("\n3. Running backtests...")
    backtests = []
    for model_name, predictions in models:
        backtest = run_backtest_single_model(
            predictions=predictions,
            prices=prices_df,
            model_name=model_name
        )
        backtests.append(backtest)
    
    # 4. Compare models
    print("\n4. Comparing models...")
    comparison = compare_multiple_models(models, prices_df)
    print("\nMODEL COMPARISON:")
    print(comparison.to_string(index=False))
    
    # 5. Generate reports
    print("\n5. Generating reports...")
    for backtest in backtests:
        report_path = generate_backtest_report(backtest)
        print(f"   Report: {report_path}")
    
    # 6. Plot best model
    print("\n6. Plotting performance...")
    best_backtest = backtests[0]
    best_backtest['engine'].plot_performance(
        f"results/backtests/best_model_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )
    
    print("\n" + "="*70)
    print("EXAMPLE COMPLETE")
    print("="*70 + "\n")


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    run_example()
