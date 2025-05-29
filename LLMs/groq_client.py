import os
import logging
import asyncio
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import Groq with error handling
try:
    from groq import AsyncGroq
    groq_available = True
except ImportError:
    groq_available = False
    logging.error("groq package not installed. Install with: pip install groq")

class GroqClient:
    """
    Client for interacting with Groq LLM API to generate trading insights
    """
    
    def __init__(self, api_key=None, model=None):
        """Initialize Groq client"""
        # Set up logging
        self.logger = logging.getLogger('GroqClient')
        
        # Get credentials
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")
        
        # Check if Groq is available
        if not groq_available:
            self.logger.error("Groq Python package not available")
            self.client = None
            self.initialized = False
            return
        
        # Validate API key
        if not self.api_key:
            self.logger.error("No Groq API key provided")
            self.client = None
            self.initialized = False
            return
        
        # Initialize client
        try:
            self.client = AsyncGroq(api_key=self.api_key)
            self.initialized = True
            self.logger.info(f"Groq client initialized with model: {self.model}")
        except Exception as e:
            self.logger.error(f"Failed to initialize Groq client: {e}")
            self.client = None
            self.initialized = False
    
    async def generate_signal_followup(self, signal_info):
        """Generate a follow-up message explaining a trading signal"""
        if not self.client:
            self.logger.error("Cannot generate follow-up - Groq client not initialized")
            return None
        
        try:
            # Extract signal details
            symbol = signal_info.get("symbol", "unknown")
            direction = signal_info.get("direction", "unknown")
            entry_low = signal_info.get("entry_range_low", "unknown")
            entry_high = signal_info.get("entry_range_high", "unknown")
            stop_low = signal_info.get("stop_range_low", "unknown")
            stop_high = signal_info.get("stop_range_high", "unknown")
            tp1 = signal_info.get("take_profit", "unknown")
            tp2 = signal_info.get("take_profit2", "unknown")
            tp3 = signal_info.get("take_profit3", "unknown")
            
            # Create prompt for Groq
            prompt = f"""You are an expert Quantitative Trader with over 20 Years of experience. A trading signal was just sent with the following details:

Symbol: {symbol}
Direction: {direction}
Entry Zone: {entry_low} - {entry_high}
Stop Loss Range: {stop_low} - {stop_high}
Take Profit 1: {tp1}
Take Profit 2: {tp2}
Take Profit 3: {tp3}

Generate a brief (80-120 words), professional follow-up explanation that:
1. Provides context on market conditions supporting this trade
2. Explains the technical or fundamental rationale behind the signal (Avoid using retail trader terms, stick to quantitative Researcher terms, and highly technical language)
3. Highlights key levels to watch beyond the provided targets
4. Uses confident but not overly promotional tone
5. DO NOT mention know technical indicators (e.g. RSI, MACD, EMA, Fibonacci, Support/Resistence etc..) Mention High level quantitative tools and formulas instead
The message should sound natural, like it was written by a human trading expert. But at the same time keep it casual (remember that's telegram trading channel meant to impress retails traders)
"""
            
            # Call Groq API
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert trading analyst who provides insightful follow-up explanations to trading signals."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7
            )
            
            # Extract response
            follow_up = completion.choices[0].message.content
            
            self.logger.info(f"Generated follow-up for {symbol} {direction} signal")
            return follow_up
            
        except Exception as e:
            self.logger.error(f"Error generating signal follow-up: {e}")
            return None