import requests
import json
import logging
import os
from datetime import datetime

class GroqClient:
    """Client for interacting with GROQ's API to generate text using Llama models."""
    
    def __init__(self, api_key=None, model=None):
        """
        Initialize the GROQ client with API key and model.
        
        Args:
            api_key (str): GROQ API key
            model (str): Model to use, e.g. "meta-llama/llama-4-maverick-17b-128e-instruct"
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.logger = logging.getLogger('GroqClient')
        
        if not self.api_key:
            self.logger.warning("No GROQ API key provided. Set GROQ_API_KEY environment variable or pass as parameter.")
    
    def generate_signal_update(self, signal_data, current_price):
        """
        Generate a signal update message based on current price and signal data.
        
        Args:
            signal_data (dict): Original signal data with entry, stop loss, take profits
            current_price (float): Current price of the asset
        
        Returns:
            str: Generated message about signal progress
        """
        try:
            # Extract relevant information from the signal
            symbol = signal_data.get("symbol", "Unknown")
            direction = signal_data.get("direction", "BUY")
            entry_price = signal_data.get("entry_price", 0.0)
            stop_loss = signal_data.get("stop_loss", 0.0)
            
            # Extract take-profit targets
            take_profits = []
            for i in range(1, 4):  # Look for TP1, TP2, TP3
                tp_key = f"take_profit{i}" if i > 1 else "take_profit"
                if tp_key in signal_data:
                    take_profits.append(signal_data[tp_key])
            
            # If no multiple TPs found, use the single take profit
            if not take_profits and "take_profit" in signal_data:
                take_profits = [signal_data["take_profit"]]
            
            # Convert to float for calculations
            entry_price = float(entry_price) if isinstance(entry_price, str) else entry_price
            stop_loss = float(stop_loss) if isinstance(stop_loss, str) else stop_loss
            take_profits = [float(tp) if isinstance(tp, str) else tp for tp in take_profits]
            
            # Calculate price movements and percentages to target
            if direction == "BUY":
                # For buy signals
                entry_to_current = current_price - entry_price
                current_to_tp1 = take_profits[0] - current_price if take_profits else 0
                entry_to_tp1 = take_profits[0] - entry_price if take_profits else 0
                
                # Calculate percentage to TP1
                pct_to_tp1 = (entry_to_current / entry_to_tp1) * 100 if entry_to_tp1 != 0 else 0
                
                # Check if in profit or loss
                in_profit = current_price > entry_price
                risk_reward_current = abs(entry_to_current / (entry_price - stop_loss)) if stop_loss != entry_price else 0
                
            else:  # SELL signal
                # For sell signals
                entry_to_current = entry_price - current_price
                current_to_tp1 = current_price - take_profits[0] if take_profits else 0
                entry_to_tp1 = entry_price - take_profits[0] if take_profits else 0
                
                # Calculate percentage to TP1
                pct_to_tp1 = (entry_to_current / entry_to_tp1) * 100 if entry_to_tp1 != 0 else 0
                
                # Check if in profit or loss
                in_profit = current_price < entry_price
                risk_reward_current = abs(entry_to_current / (stop_loss - entry_price)) if stop_loss != entry_price else 0
            
            # Prepare context information for the model
            status = {
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "current_price": current_price,
                "stop_loss": stop_loss,
                "take_profits": take_profits,
                "in_profit": in_profit,
                "profit_pips": entry_to_current,
                "pct_to_tp1": pct_to_tp1,
                "risk_reward_current": risk_reward_current
            }
            
            # Create prompt based on signal status
            prompt = self._create_update_prompt(status)
            
            # Generate text using GROQ API
            return self._generate_text(prompt)
            
        except Exception as e:
            self.logger.error(f"Error generating signal update: {e}")
            return "Unable to generate signal update at this time."
    
    def generate_news_commentary(self, news_items):
        """
        Generate commentary on financial news.
        
        Args:
            news_items (list): List of news item dictionaries
        
        Returns:
            str: Generated commentary
        """
        try:
            if not news_items:
                return "No news to analyze at this time."
            
            # Prepare news summaries for the prompt
            news_text = "\n\n".join([
                f"Title: {item['title']}\nSource: {item['source']}\nSummary: {item['summary'][:200]}..."
                for item in news_items[:3]  # Limit to 3 news items to keep prompt size reasonable
            ])
            
            # Create prompt
            prompt = f"""
            Below are recent financial news headlines:
            
            {news_text}
            
            As a financial analyst, provide a brief market commentary based on these news. Include:
            1. Key insights
            2. Potential market impact
            3. What traders should watch out for
            
            Keep it concise (max 100 words) and professional, suitable for a trading channel.
            """
            
            # Generate text using GROQ API
            return self._generate_text(prompt)
            
        except Exception as e:
            self.logger.error(f"Error generating news commentary: {e}")
            return "Unable to generate market commentary at this time."
    
    def _create_update_prompt(self, status):
        """
        Create a prompt for generating a signal update based on status.
        
        Args:
            status (dict): Signal status information
        
        Returns:
            str: Prompt for the model
        """
        symbol = status["symbol"]
        direction = status["direction"]
        in_profit = status["in_profit"]
        pct_to_tp1 = status["pct_to_tp1"]
        rr_current = status["risk_reward_current"]
        
        # Base template
        prompt = f"""
        You are a professional trading analyst with more than 20 years of experience working at top firms providing an update on a signal.
        
        SIGNAL DETAILS:
        - Symbol: {symbol}
        - Direction: {direction}
        - Entry Price: {status['entry_price']}
        - Current Price: {status['current_price']}
        - Stop Loss: {status['stop_loss']}
        - Take Profit Targets: {status['take_profits']}
        - Currently {'in profit' if in_profit else 'in loss'} 
        - Movement: {abs(status['profit_pips']):.4f} points {'toward target' if in_profit else 'away from entry'}
        - Progress to TP1: {pct_to_tp1:.1f}%
        - Current Risk/Reward: {rr_current:.2f}
        
        TASK:
        Generate a BRIEF (max 7 sentences) signal update for traders following this trade.
        """
        
        # Add specific instructions based on signal status
        if not in_profit:
            prompt += """
            Since the trade is not yet in profit, include:
            - A note about patience
            - Reminder about the trade's potential
            - Suggestion about watching key levels
            - Suggestions about risk managment techniques
            """
        elif 0 < pct_to_tp1 < 30:
            prompt += """
            Since the trade is in profit but still far from TP1, include:
            - Encouragement about the positive movement
            - Reminder to follow the plan
            - Suggestion about potential market drivers to watch
            - Suggestions about risk managment techniques
            """
        elif 30 <= pct_to_tp1 < 70:
            prompt += """
            Since the trade is approaching TP1, include:
            - Note about the solid progress
            - Specific risk management advice like considering moving stop loss to breakeven
            - Brief technical observation about momentum
            """
        elif 70 <= pct_to_tp1 < 95:
            prompt += """
            Since the trade is very close to TP1, include:
            - Alert that TP1 is nearly reached
            - Specific advice about partial profit taking
            - Suggestion about moving stop loss to protect gains
            """
        elif pct_to_tp1 >= 95:
            prompt += """
            Since TP1 has been reached or is imminent, include:
            - Congratulations on reaching the first target
            - Very specific instructions on how to manage the remainder of the position
            - Brief technical outlook for the continued move
            """
        
        prompt += """
        IMPORTANT FORMATTING:
        - Keep it very short and professional (70-120 words maximum)
        - Use appropriate emojis for market movements
        - Include a specific, actionable risk management tip
        - Do NOT mention that you're an AI or mention this prompt
        - Don't use hashtags or overly promotional language
        """
        
        return prompt
    
    def _generate_text(self, prompt):
        """
        Generate text using GROQ API.
        
        Args:
            prompt (str): Prompt for the model
        
        Returns:
            str: Generated text
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a professional trading analyst providing concise, valuable information for traders."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 300,
                "top_p": 1
            }
            
            self.logger.info(f"Sending request to GROQ API: {self.api_url}")
            response = requests.post(self.api_url, headers=headers, json=data)
            
            if response.status_code != 200:
                self.logger.error(f"Error from GROQ API: {response.status_code} - {response.text}")
                return "Error generating text. Please try again later."
            
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"].strip()
            else:
                self.logger.error(f"Unexpected response format: {result}")
                return "Error: Unexpected response format from GROQ API."
            
        except Exception as e:
            self.logger.error(f"Error in GROQ API request: {e}")
            return "Error generating text. Please try again later."


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with environment variables
    client = GroqClient()
    
    # Test signal update
    test_signal = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.0750,
        "stop_loss": 1.0720,
        "take_profit": 1.0820,
        "take_profit2": 1.0850,
        "take_profit3": 1.0900
    }
    
    # Test with price approaching TP1
    current_price = 1.0800  # 71% to TP1
    update = client.generate_signal_update(test_signal, current_price)
    print("\nSignal Update (approaching TP1):")
    print(update)