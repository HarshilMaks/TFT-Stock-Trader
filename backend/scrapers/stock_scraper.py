import yfinance as yf
import pandas_ta as ta
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from backend.utils.logger import get_logger

class StockFetcher:
    """Fetches stock prices from Yahoo Finance"""
    
    async def fetch_historical(
        self,
        ticker: str,
        period: str = "1mon"
        calculate_indicators: bool = True
    ) -> List[Dict]