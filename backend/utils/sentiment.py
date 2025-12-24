from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


class SentimentAnalyzer:
    """
    Analyze sentiment of Reddit posts using VADER (Valence Aware Dictionary and sEntiment Reasoner).
    
    VADER is specifically attuned to sentiments expressed in social media and works well for:
    - Stock market language (bullish, bearish, moon, crash, etc.)
    - Emojis and slang
    - Intensity modifiers (VERY good, really bad)
    
    Returns compound score: -1 (negative) to +1 (positive)
    """
    
    def __init__(self):
        self.analyzer = SentimentIntensityAnalyzer()
        
        # Add custom lexicon for stock market terms
        self.analyzer.lexicon.update({
            'moon': 4.0,
            'mooning': 4.0,
            'rocket': 3.5,
            'bullish': 3.0,
            'bull': 2.5,
            'calls': 2.0,
            'long': 1.5,
            'buy': 1.5,
            'buying': 1.5,
            'green': 1.5,
            'gains': 2.5,
            'tendies': 3.0,
            'profit': 2.0,
            'winner': 2.5,
            'squeeze': 3.0,
            'shorts': -2.0,
            'short': -1.5,
            'bearish': -3.0,
            'bear': -2.5,
            'puts': -2.0,
            'sell': -1.5,
            'selling': -1.5,
            'red': -1.5,
            'loss': -2.5,
            'losses': -2.5,
            'crash': -3.5,
            'dump': -3.0,
            'rug': -3.5,
            'rekt': -4.0,
            'bagholding': -3.0,
            'bagholder': -3.0,
            'fomo': -1.0,
            'dip': -0.5,  # Slightly negative but often means "buying opportunity"
            'yolo': 2.0,  # Risk-taking but positive sentiment
            'diamond': 3.0,
            'hands': 2.0,
            'hold': 1.5,
            'hodl': 2.0,
        })
    
    def analyze(self, text: str) -> float:
        """
        Analyze sentiment of text and return compound score.
        
        Args:
            text: Post title + body text
            
        Returns:
            float: Compound sentiment score from -1 to +1
                   -1: Most negative
                    0: Neutral
                   +1: Most positive
        """
        if not text or not text.strip():
            return 0.0
        
        scores = self.analyzer.polarity_scores(text)
        return scores['compound']
    
    def classify(self, score: float) -> str:
        """
        Classify sentiment score into categories.
        
        Args:
            score: Compound sentiment score
            
        Returns:
            str: 'positive', 'negative', or 'neutral'
        """
        if score >= 0.05:
            return 'positive'
        elif score <= -0.05:
            return 'negative'
        else:
            return 'neutral'


# Singleton instance
_sentiment_analyzer = None

def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create singleton sentiment analyzer instance"""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


def analyze_sentiment(text: str) -> float:
    """Convenience function to analyze text sentiment"""
    analyzer = get_sentiment_analyzer()
    return analyzer.analyze(text)
