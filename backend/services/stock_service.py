from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.models.stock import StockPrice
from backend.scrapers.stock_scraper import StockScraper
from backend.utils.logger import logger
from datetime import datetime
from typing import List, Dict


class StockService:
    """Service layer for stock price data management"""
    
    def __init__(self):
        self.scraper = StockScraper()
    
    async def fetch_and_save_stock_data(
        self, 
        ticker: str, 
        db: AsyncSession,
        period: str = "3mo"
    ) -> Dict:
        """
        Fetch stock data and save to database.
        
        Args:
            ticker: Stock symbol
            db: Database session
            period: Historical period to fetch
            
        Returns:
            Dictionary with stats: {'ticker', 'saved', 'skipped', 'errors'}
        """
        logger.info(f"Fetching stock data for {ticker}")
        
        # Fetch from Yahoo Finance
        prices = await self.scraper.fetch_historical(ticker, period=period)
        
        if not prices:
            logger.warning(f"No data fetched for {ticker}")
            return {"ticker": ticker, "saved": 0, "skipped": 0, "errors": 1}
        
        saved_count = 0
        skipped_count = 0
        
        for price_data in prices:
            try:
                # Check if record already exists
                existing = await db.execute(
                    select(StockPrice).where(
                        StockPrice.ticker == price_data['ticker'],
                        StockPrice.date == price_data['date']
                    )
                )
                if existing.scalar_one_or_none():
                    skipped_count += 1
                    continue
                
                # Create new stock price record
                stock_price = StockPrice(**price_data)
                db.add(stock_price)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving {ticker} record: {e}")
                continue
        
        # Commit all records
        try:
            await db.commit()
            logger.info(f"{ticker}: Saved {saved_count}, Skipped {skipped_count}")
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to commit {ticker} data: {e}")
            return {"ticker": ticker, "saved": 0, "skipped": 0, "errors": 1}
        
        return {
            "ticker": ticker,
            "saved": saved_count,
            "skipped": skipped_count,
            "errors": 0
        }
    
    async def fetch_and_save_multiple(
        self,
        tickers: List[str],
        db: AsyncSession,
        period: str = "3mo"
    ) -> Dict[str, Dict]:
        """
        Fetch and save data for multiple tickers in parallel.
        
        Args:
            tickers: List of stock symbols
            db: Database session
            period: Historical period
            
        Returns:
            Dictionary mapping ticker to stats
        """
        results = {}
        
        for ticker in tickers:
            result = await self.fetch_and_save_stock_data(ticker, db, period)
            results[ticker] = result
        
        return results
    
    async def get_latest_price(
        self,
        ticker: str,
        db: AsyncSession
    ) -> float | None:
        """Get most recent price from database"""
        result = await db.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker.upper())
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        return latest.close if latest else None
    
    async def get_momentum_signals(
        self,
        ticker: str,
        db: AsyncSession
    ) -> Dict | None:
        """
        Get latest momentum indicators for a ticker.
        
        Returns:
            Dictionary with RSI, MACD, SMA crossover status, etc.
        """
        result = await db.execute(
            select(StockPrice)
            .where(StockPrice.ticker == ticker.upper())
            .order_by(StockPrice.date.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()
        
        if not latest:
            return None
        
        # Calculate momentum signals
        sma_crossover = None
        if latest.sma_50 and latest.sma_200:
            sma_crossover = "bullish" if latest.sma_50 > latest.sma_200 else "bearish"
        
        return {
            "ticker": ticker.upper(),
            "date": latest.date,
            "close": latest.close,
            "rsi": latest.rsi,
            "macd": latest.macd,
            "macd_signal": latest.macd_signal,
            "macd_crossover": latest.macd > latest.macd_signal if (latest.macd and latest.macd_signal) else None,
            "sma_50": latest.sma_50,
            "sma_200": latest.sma_200,
            "sma_crossover": sma_crossover,
            "volume_ratio": latest.volume_ratio,
            "bb_position": self._calculate_bb_position(latest)
        }
    
    def _calculate_bb_position(self, stock_price: StockPrice) -> str | None:
        """Calculate where price is relative to Bollinger Bands"""
        if not (stock_price.bb_upper and stock_price.bb_lower):
            return None
        
        close = stock_price.close
        
        if close > stock_price.bb_upper:
            return "above_upper"
        elif close < stock_price.bb_lower:
            return "below_lower"
        else:
            return "inside_bands"
