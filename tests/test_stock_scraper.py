"""
Test script for stock scraper with momentum indicators

Usage:
    uv run python test_stock_scraper.py
"""

import asyncio
from backend.database.config import AsyncSessionLocal
from backend.services.stock_service import StockService


async def test_stock_scraper():
    """Test fetching stock data with swing trading indicators"""
    
    print("=" * 60)
    print("Testing Stock Scraper with Momentum Indicators")
    print("=" * 60)
    
    # Test tickers
    test_tickers = ["AAPL", "TSLA", "MSFT"]
    
    service = StockService()
    
    async with AsyncSessionLocal() as db:
        print(f"\n📊 Fetching data for: {', '.join(test_tickers)}")
        print("⏳ This will take ~30 seconds (3 months of data + indicators)...\n")
        
        # Fetch and save for each ticker
        for ticker in test_tickers:
            result = await service.fetch_and_save_stock_data(
                ticker=ticker,
                db=db,
                period="3mo"  # 3 months for SMA_200
            )
            
            print(f"\n✅ {result['ticker']}")
            print(f"   Saved: {result['saved']} records")
            print(f"   Skipped: {result['skipped']} (already in DB)")
            print(f"   Errors: {result['errors']}")
            
            # Get momentum signals
            signals = await service.get_momentum_signals(ticker, db)
            
            if signals:
                print(f"\n   📈 Latest Momentum Indicators:")
                print(f"      Date: {signals['date'].date()}")
                print(f"      Close: ${signals['close']:.2f}")
                print(f"      RSI: {signals['rsi']:.2f}" if signals['rsi'] else "      RSI: N/A")
                print(f"      MACD: {signals['macd']:.2f}" if signals['macd'] else "      MACD: N/A")
                print(f"      MACD Crossover: {'Bullish' if signals['macd_crossover'] else 'Bearish'}" if signals['macd_crossover'] is not None else "      MACD Crossover: N/A")
                print(f"      SMA 50: ${signals['sma_50']:.2f}" if signals['sma_50'] else "      SMA 50: N/A")
                print(f"      SMA 200: ${signals['sma_200']:.2f}" if signals['sma_200'] else "      SMA 200: N/A")
                print(f"      SMA Trend: {signals['sma_crossover']}" if signals['sma_crossover'] else "      SMA Trend: N/A")
                print(f"      Volume Ratio: {signals['volume_ratio']:.2f}x" if signals['volume_ratio'] else "      Volume Ratio: N/A")
                print(f"      BB Position: {signals['bb_position']}" if signals['bb_position'] else "      BB Position: N/A")
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)
    print("\n💡 Next Steps:")
    print("   1. Check your database - stock_prices table should have data")
    print("   2. All momentum indicators (RSI, MACD, SMA, BB) are calculated")
    print("   3. Ready for Week 3: Feature engineering + ML training")


if __name__ == "__main__":
    asyncio.run(test_stock_scraper())
