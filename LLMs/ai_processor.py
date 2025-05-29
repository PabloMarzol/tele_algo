import requests
import json
import logging
import os
from datetime import datetime

class AIProcessor:
    """Class to interact with AI APIs for text processing."""
    
    def __init__(self, api_key=None, api_url=None, model="meta-llama/llama-4-maverick-17b-128e-instruct"):
        """Initialize the AI processor with API credentials."""
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.api_url = api_url or "https://api.groq.com/openai/v1/chat/completions"
        self.model = model
        self.logger = logging.getLogger('AIProcessor')
    
    def process_news(self, news_items):
        """Process news items and generate commentary."""
        if not news_items:
            return "No news to process."
        
        try:
            # Prepare the prompt with the news data
            news_text = "\n\n".join([
                f"Title: {item['title']}\nSource: {item['source']}\nSummary: {item['summary'][:200]}..."
                for item in news_items[:3]  # Limit to 3 news items to keep prompt size reasonable
            ])
            
            prompt = f"""
            Below are recent financial news headlines:
            
            {news_text}
            
            As a financial analyst, provide a brief market commentary based on these news. Include:
            1. Key insights
            2. Potential market impact
            3. What traders should watch out for
            
            Keep it concise and professional, suitable for a trading channel.
            """
            
            # Prepare API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional financial analyst providing insights for traders."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300
            }
            
            # Make API request
            self.logger.info(f"Sending request to AI API for news processing")
            response = requests.post(self.api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            commentary = result["choices"][0]["message"]["content"].strip()
            
            return commentary
            
        except Exception as e:
            self.logger.error(f"Error processing news with AI: {e}")
            return "Unable to generate market commentary at this time."
    
    def enhance_signal(self, signal_data):
        """Enhance a trading signal with AI commentary."""
        try:
            # Extract relevant information from the signal
            symbol = signal_data.get("symbol", "Unknown")
            direction = signal_data.get("direction", "Unknown")
            entry_price = signal_data.get("entry_price", "Unknown")
            stop_loss = signal_data.get("stop_loss", "Unknown")
            take_profit = signal_data.get("take_profit", "Unknown")
            timestamp = signal_data.get("timestamp", datetime.now())
            
            # Prepare the prompt
            prompt = f"""
            I have a trading signal with the following details:
            
            Symbol: {symbol}
            Direction: {direction}
            Entry Price: {entry_price}
            Stop Loss: {stop_loss}
            Take Profit: {take_profit}
            Time: {timestamp}
            
            As an experienced trader, provide a brief professional analysis of this signal. Include:
            1. Key technical or fundamental factors supporting this direction
            2. Risk management considerations for this specific trade
            3. Key levels to watch beyond the specified take profit
            
            Keep it concise (3-4 sentences total), technical but accessible, and professional.
            """
            
            # Prepare API request
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an expert trader providing analysis for VIP clients."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 250
            }
            
            # Make API request
            self.logger.info(f"Sending request to AI API for signal enhancement: {symbol} {direction}")
            response = requests.post(self.api_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            
            # Parse response
            result = response.json()
            analysis = result["choices"][0]["message"]["content"].strip()
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Error enhancing signal with AI: {e}")
            return "Signal analysis unavailable at this time."


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    processor = AIProcessor(api_key="YOUR_API_KEY_HERE")
    
    # Test signal enhancement
    test_signal = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": "1.0750",
        "stop_loss": "1.0720",
        "take_profit": "1.0800"
    }
    
    analysis = processor.enhance_signal(test_signal)
    print("Signal Analysis:")
    print(analysis)