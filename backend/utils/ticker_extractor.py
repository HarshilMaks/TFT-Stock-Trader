import re

# Comprehensive list of popular tickers across all categories
KNOWN_TICKERS = {
    # FAANG + Tech Giants
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'NVDA', 'AMD', 'INTC', 'TSLA',
    'NFLX', 'ADBE', 'CRM', 'ORCL', 'CSCO', 'AVGO', 'QCOM', 'TXN', 'MU', 'AMAT',
    'LRCX', 'KLAC', 'SNPS', 'CDNS', 'MCHP', 'MRVL', 'ADI', 'NXPI', 'ASML',
    
    # Meme Stocks
    'GME', 'AMC', 'BB', 'BBBY', 'NOK', 'PLTR', 'WISH', 'CLOV', 'SOFI', 'HOOD',
    'COIN', 'DKNG', 'SPCE', 'OPEN', 'FUBO', 'SKLZ', 'ROOT', 'GOEV',
    
    # Major ETFs
    'SPY', 'QQQ', 'IWM', 'DIA', 'VOO', 'VTI', 'ARKK', 'ARKG', 'ARKF', 'ARKW',
    'XLF', 'XLE', 'XLK', 'XLV', 'XLI', 'XLP', 'XLY', 'XLB', 'XLU', 'XLRE',
    'SMH', 'SOXX', 'VGT', 'GLD', 'SLV', 'USO', 'TLT', 'HYG', 'SQQQ', 'TQQQ',
    
    # Finance & Banking
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW', 'AXP', 'USB',
    'PNC', 'TFC', 'COF', 'BK', 'STT', 'V', 'MA', 'PYPL', 'SQ', 'FIS',
    
    # EV & Auto
    'F', 'GM', 'TM', 'HMC', 'RIVN', 'LCID', 'NIO', 'XPEV', 'LI', 'PLUG',
    
    # Energy & Oil
    'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'PXD', 'OXY', 'HAL', 'MPC', 'PSX',
    
    # Healthcare & Pharma
    'JNJ', 'UNH', 'PFE', 'ABBV', 'TMO', 'ABT', 'DHR', 'MRK', 'LLY', 'BMY',
    'AMGN', 'GILD', 'CVS', 'CI', 'ISRG', 'MDT', 'SYK', 'BSX', 'ZTS', 'REGN',
    'MRNA', 'BNTX', 'VRTX', 'BIIB', 'ILMN',
    
    # Retail & Consumer
    'WMT', 'COST', 'TGT', 'HD', 'LOW', 'NKE', 'SBUX', 'MCD', 'CMG', 'DPZ',
    'YUM', 'BKNG', 'MAR', 'HLT', 'DIS', 'CMCSA', 'T', 'VZ', 'TMUS',
    
    # Consumer Goods
    'PG', 'KO', 'PEP', 'PM', 'MO', 'CL', 'EL', 'MDLZ', 'MNST', 'KHC',
    'GIS', 'K', 'HSY', 'CLX', 'CHD',
    
    # Industrial & Aerospace
    'BA', 'CAT', 'DE', 'GE', 'HON', 'UPS', 'FDX', 'RTX', 'LMT', 'NOC',
    'GD', 'LHX', 'TXT', 'ETN', 'EMR', 'ROK', 'PH', 'ITW',
    
    # Chinese Stocks
    'BABA', 'JD', 'PDD', 'BIDU', 'TME', 'BILI', 'IQ', 'NTES', 'WB', 'DIDI',
    
    # SPACs & Recent IPOs
    'RBLX', 'ABNB', 'DASH', 'SNOW', 'PLTR', 'U', 'CPNG', 'GRAB', 'RIVN',
    
    # Semiconductors
    'TSM', 'AVGO', 'QCOM', 'TXN', 'INTC', 'MU', 'AMAT', 'LRCX', 'KLAC',
    
    # Communication & Social
    'SNAP', 'PINS', 'TWTR', 'SPOT', 'MTCH', 'ZM', 'DOCU', 'TEAM', 'WDAY',
    
    # Cloud & Software
    'CRM', 'ADBE', 'NOW', 'PANW', 'CRWD', 'ZS', 'DDOG', 'NET', 'OKTA', 'SPLK',
    'TWLO', 'SNOW', 'MRVL', 'FTNT', 'ABNB', 'UBER', 'LYFT',
    
    # Real Estate
    'AMT', 'PLD', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'AVB',
    
    # Crypto-Related
    'MSTR', 'COIN', 'SQ', 'RIOT', 'MARA', 'CLSK', 'HUT', 'BITF',
    
    # Leveraged ETFs
    'UPRO', 'SPXL', 'TQQQ', 'SQQQ', 'SPXS', 'UDOW', 'SDOW', 'TNA', 'TZA',
    'UVXY', 'VXX', 'VIXY',
}


def extract_tickers(text: str) -> list[str]:
    """
    Extract stock tickers from text using regex patterns.
    
    Handles:
    - Cashtags: $AAPL
    - All caps words: TSLA (2-5 letters)
    
    Filters:
    - Only returns known tickers (prevents false positives like "YOLO", "LOL")
    - De-duplicates
    - Expands to 250+ tickers covering major markets
    """
    # Pattern 1: Cashtags like $AAPL
    # Pattern 2: All caps words (2-5 letters) not preceded/followed by letters
    pattern = r'\$([A-Z]{1,5})\b|(?<!\w)([A-Z]{2,5})(?!\w)'
    
    matches = re.findall(pattern, text.upper())
    
    tickers = set()
    for match in matches:
        ticker = match[0] or match[1]  # match[0] for $AAPL, match[1] for AAPL
        if ticker in KNOWN_TICKERS:
            tickers.add(ticker)
    
    return sorted(list(tickers))  # Return sorted for consistency
