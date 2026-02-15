import yfinance as yf
import pandas as pd
import pandas_ta as ta
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from backend.utils.logger import logger
from backend.utils.retry import retry_with_backoff, YFINANCE_CONFIG, should_retry


class StockScraper:
    """Fetches stock prices and calculates momentum indicators for swing trading"""
    
    def __init__(self):
        self._session = None
    
    async def fetch_historical(
        self, 
        ticker: str, 
        period: str = "3mo",  # Need 200 days for SMA_200
        calculate_indicators: bool = True
    ) -> List[Dict]:
        """Fetch historical data with technical indicators for swing trading"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self._fetch_sync, 
            ticker, period, calculate_indicators
        )
    
    @retry_with_backoff(config=YFINANCE_CONFIG)
    def _fetch_sync(self, ticker: str, period: str, calc_indicators: bool) -> List[Dict]:
        """Synchronous fetching (runs in thread pool)"""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period)
            
            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                return []
            
            # Calculate technical indicators for momentum trading
            if calc_indicators:
                # Momentum Oscillators
                df['RSI'] = ta.rsi(df['Close'], length=14)
                
                # MACD (trend strength)
                macd = ta.macd(df['Close'], fast=12, slow=26, signal=9)
                if macd is not None:
                    df['MACD'] = macd['MACD_12_26_9']
                    df['MACD_Signal'] = macd['MACDs_12_26_9']
                
                # Bollinger Bands (volatility breakouts)
                bbands = ta.bbands(df['Close'], length=20, std=2)
                if bbands is not None:
                    df['BB_Upper'] = bbands['BBU_20_2.0']
                    df['BB_Lower'] = bbands['BBL_20_2.0']
                
                # Moving Averages (swing trading key levels)
                df['SMA_50'] = ta.sma(df['Close'], length=50)
                df['SMA_200'] = ta.sma(df['Close'], length=200)
                
                # Volume Analysis
                df['Volume_Avg_20'] = df['Volume'].rolling(window=20).mean()
                df['Volume_Ratio'] = df['Volume'] / df['Volume_Avg_20']
            
            # Convert to list of dicts
            prices = []
            for date, row in df.iterrows():
                price_data = {
                    'ticker': ticker.upper(),
                    'date': date.to_pydatetime(),
                    'open_price': float(row['Open']),  # Fixed field name
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'adjusted_close': float(row['Close']),  # Added
                    'volume': int(row['Volume']),
                }
                
                # Add indicators if calculated
                if calc_indicators:
                    price_data.update({
                        'rsi': float(row['RSI']) if pd.notna(row['RSI']) else None,
                        'macd': float(row['MACD']) if pd.notna(row.get('MACD')) else None,
                        'macd_signal': float(row['MACD_Signal']) if pd.notna(row.get('MACD_Signal')) else None,
                        'bb_upper': float(row['BB_Upper']) if pd.notna(row.get('BB_Upper')) else None,
                        'bb_lower': float(row['BB_Lower']) if pd.notna(row.get('BB_Lower')) else None,
                        'sma_50': float(row['SMA_50']) if pd.notna(row['SMA_50']) else None,
                        'sma_200': float(row['SMA_200']) if pd.notna(row['SMA_200']) else None,
                        'volume_ratio': float(row['Volume_Ratio']) if pd.notna(row['Volume_Ratio']) else None,
                    })
                
                prices.append(price_data)
            
            logger.info(f"Fetched {len(prices)} price records for {ticker}")
            return prices
            
        except Exception as e:
            # Re-raise transient errors so the retry decorator can handle them
            if should_retry(e):
                raise  # Let the decorator retry
            # For permanent errors (404, 401, etc.), log and return empty list
            logger.error(f"Error fetching {ticker}: {e}", exc_info=True)
            return []
    
    async def fetch_multiple(
        self, 
        tickers: List[str], 
        period: str = "3mo"
    ) -> Dict[str, List[Dict]]:
        """
        Fetch data for multiple tickers in parallel.
        
        Args:
            tickers: List of stock symbols
            period: Time period for each ticker
            
        Returns:
            Dictionary mapping ticker to price data list
        """
        tasks = [self.fetch_historical(t, period) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        output = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch {ticker}: {result}")
                output[ticker] = []
            else:
                output[ticker] = result
        
        return output
    
    async def fetch_current_price(self, ticker: str) -> Optional[float]:
        """Get current market price"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_price_sync, ticker)
    
    @retry_with_backoff(config=YFINANCE_CONFIG)
    def _get_price_sync(self, ticker: str) -> Optional[float]:
        """Synchronous price fetching"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Try multiple price fields
            price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or
                info.get('previousClose')
            )
            
            return float(price) if price else None
            
        except Exception as e:
            # Re-raise transient errors so the retry decorator can handle them
            if should_retry(e):
                raise  # Let the decorator retry
            # For permanent errors, log and return None
            logger.error(f"Failed to get price for {ticker}: {e}")
            return None