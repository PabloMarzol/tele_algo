import os
import logging
from datetime import datetime
import requests
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SignalFollowUpGenerator:
    """Generates follow-up messages for active trading signals using Groq API."""
    
    def __init__(self, signal_tracker=None):
        """
        Initialize the follow-up message generator.
        
        Args:
            signal_tracker: Instance of SignalTracker to use for signal status
        """
        self.logger = logging.getLogger('SignalFollowUpGenerator')
        self.signal_tracker = signal_tracker
        
        # Get Groq API credentials from environment variables
        self.api_key = os.getenv("GROQ_API_KEY")
        self.model = os.getenv("GROQ_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")
        self.models = [
            "meta-llama/llama-4-maverick-17b-128e-instruct",  # Primary model
            "compound-beta",
            "deepseek-r1-distill-llama-70b",
            "qwen-qwq-32b",
            "gemma2-9b-it"
        ]
        # Current model index (start with primary model)
        self.current_model_index = 0
        
        # Model cooldown tracking
        self.model_cooldowns = {model: None for model in self.models}
        
        
        if not self.api_key:
            self.logger.error("GROQ_API_KEY not found in environment variables")
            raise ValueError("GROQ_API_KEY not found")
            
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Message templates for different scenarios
        self.message_templates = {
            "take_profit_hit": "Signal update for {symbol} {direction}: Take Profit {tp_num} HIT! Price reached {tp_price}. {additional_info}",
            "stop_loss_hit": "Signal update for {symbol} {direction}: Stop Loss triggered at {sl_price}. {additional_info}",
            "progress_update": "Signal update for {symbol} {direction}: Currently at {progress}% toward TP1. {additional_info}",
            "major_milestone": "Signal update for {symbol} {direction}: {milestone} milestone reached! Now {progress}% toward TP1. {additional_info}"
        }
        
        self.logger.info("SignalFollowUpGenerator initialized successfully")
    
    def generate_message(self, signal_data, status):
        """
        Generate a follow-up message for a signal based on its current status.
        
        Args:
            signal_data (dict): The original signal data
            status (dict): Current status of the signal
            
        Returns:
            str: Generated follow-up message
        """
        try:
            # Extract basic info
            symbol = signal_data.get("symbol", "Unknown")
            direction = signal_data.get("direction", "Unknown")
            
            # Determine message type based on status
            message_type = "progress_update"  # Default message type
            
            # Check if stop loss hit
            if status.get("stop_hit", False):
                message_type = "stop_loss_hit"
                
            # Check if any take profits hit
            elif any(status.get("tps_hit", [])):
                message_type = "take_profit_hit"
                
            # Check for major milestones (25%, 50%, 75%, 90%)
            elif status.get("pct_to_tp1", 0) >= 25:
                message_type = "major_milestone"
            
            # Create context for Groq
            context = self.create_message_context(signal_data, status, message_type)
            
            # Generate message using Groq
            follow_up_message = self.query_groq(context)
            
            # If Groq fails, use a template fallback
            if not follow_up_message:
                follow_up_message = self.generate_fallback_message(signal_data, status, message_type)
                
            return follow_up_message
            
        except Exception as e:
            self.logger.error(f"Error generating follow-up message: {e}")
            return f"Signal update for {symbol} {direction}: Check your trading platform for the latest status."
    
    def create_message_context(self, signal_data, status, message_type):
        """
        Create context information for Groq to generate a follow-up message.
        
        Args:
            signal_data (dict): The original signal data
            status (dict): Current status of the signal
            message_type (str): Type of message to generate
            
        Returns:
            dict: Context for Groq message generation
        """
        # Extract signal information
        symbol = signal_data.get("symbol", "Unknown")
        direction = signal_data.get("direction", "Unknown")
        entry_price = signal_data.get("entry_price", 0)
        current_price = status.get("current_price", 0)
        
        # Format take profit values
        take_profits = []
        for i in range(1, 4):
            tp_key = f"take_profit{i}" if i > 1 else "take_profit"
            if tp_key in signal_data:
                take_profits.append(signal_data[tp_key])
        
        # Get profit/loss information
        in_profit = status.get("in_profit", False)
        profit_pips = status.get("profit_pips", 0)
        progress = status.get("pct_to_tp1", 0)
        
        # Determine which take profit was hit (if any)
        tp_hit = None
        tp_hit_price = None
        for i, hit in enumerate(status.get("tps_hit", [])):
            if hit:
                tp_hit = i + 1
                tp_hit_price = take_profits[i] if i < len(take_profits) else None
                break
        
        # Determine milestone if applicable
        milestone = None
        if progress >= 90:
            milestone = "90%"
        elif progress >= 75:
            milestone = "75%"
        elif progress >= 50:
            milestone = "50%"
        elif progress >= 25:
            milestone = "25%"
            
        # Create context with all relevant information
        context = {
            "message_type": message_type,
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "current_price": current_price,
            "take_profits": take_profits,
            "stop_loss": signal_data.get("stop_loss", 0),
            "in_profit": in_profit,
            "profit_pips": profit_pips,
            "progress": progress,
            "tp_hit": tp_hit,
            "tp_hit_price": tp_hit_price,
            "milestone": milestone,
            "stop_hit": status.get("stop_hit", False),
        }
        
        return context
        
    def query_groq(self, context):
        """
        Generate a message using Groq API.
        
        Args:
            context (dict): Context for message generation
            
        Returns:
            str: Generated message or None if failed
        """
        now = datetime.now()
        message = None
        
        # Try each model in sequence until success or all models fail
        for model_index in range(len(self.models)):
            # Calculate the actual model index to use (rotate through models)
            idx = (self.current_model_index + model_index) % len(self.models)
            model = self.models[idx]
            
            # Check if this model is on cooldown
            cooldown_until = self.model_cooldowns[model]
            if cooldown_until and now < cooldown_until:
                seconds_remaining = (cooldown_until - now).total_seconds()
                self.logger.info(f"Model {model} is on cooldown for {seconds_remaining:.1f}s, trying next model")
                continue
            
            try:
                # Create the prompt for Groq
                symbol = context.get("symbol", "Unknown")
                direction = context.get("direction", "Unknown")
                message_type = context.get("message_type", "progress_update")
                
                # Customize the prompt based on the message type
                base_prompt = f"""
        You are an expert Quantitative Trader/Researcher with over 20 years of experience. Generate a professional, visually appealing follow-up message for a trading signal in a VIP Telegram channel.

        Signal Details:
        - Symbol: {symbol}
        - Direction: {direction}
        - Entry Price: {context.get('entry_price')}
        - Current Price: {context.get('current_price')}
        - Take Profit Targets: {context.get('take_profits')}
        - Stop Loss: {context.get('stop_loss')}
        - Current Progress to TP1: {context.get('progress'):.1f}%
        - Currently in Profit: {context.get('in_profit')}
        - Profit/Loss Pips: {context.get('profit_pips'):.1f}

        Additional Context:
        """

                # Add specific context based on message type
                if message_type == "take_profit_hit":
                    base_prompt += f"""
        - Take Profit {context.get('tp_hit')} has been hit!
        - Price reached {context.get('tp_hit_price')}
        - Create an enthusiastic message celebrating this win
        - Include advice about managing the remaining position (moving stop loss, trailing, etc.)
        """
                elif message_type == "stop_loss_hit":
                    base_prompt += f"""
        - Stop Loss has been triggered at {context.get('stop_loss')}
        - Create a professional and reassuring message
        - Mention that risk management is key to long-term success
        - Encourage them to look forward to the next setup
        """
                elif message_type == "major_milestone":
                    base_prompt += f"""
        - Signal has reached a significant milestone: {context.get('milestone')} toward TP1
        - Create an encouraging message highlighting this progress
        - Include a brief technical observation about the current price action
        - Remind about proper position management
        """
                else:  # progress_update
                    base_prompt += f"""
        - Regular progress update for this signal
        - Currently at {context.get('progress'):.1f}% toward TP1
        - Create a balanced, informative update
        - Include a brief market observation relevant to this trade
        """

                base_prompt += """
        TELEGRAM FORMATTING GUIDELINES:
        - Create a visually structured message with clear sections
        - Use line breaks to separate sections
        - Start with a prominent header with emojis (e.g., "📊 SIGNAL UPDATE: EURUSD BUY 📈")
        - Use <b>bold text</b> for important information and section headers
        - Use emojis to start each major point or section (not just decorative, but meaningful)
        - Include a clear status section showing current price, progress percentage, and profit/loss
        - End with a motivational note or clear next steps

        STRUCTURE YOUR MESSAGE LIKE THIS:
        📊 <b>SIGNAL UPDATE: [SYMBOL] [DIRECTION]</b> 📈

        ⏱ <b>Status:</b> [Current status in 1-2 sentences]

        💰 <b>Performance:</b>
        - Entry: [entry price]
        - Current: [current price]
        - Profit/Loss: [amount] pips
        - Progress to TP1: [percentage]%

        🔍 <b>Market Insight:</b>
        [Brief technical observation]

        🚀 <b>Next Steps:</b>
        [What traders should do now]

        [Encouraging closing note]

        Make the message conversational but professional. Use the exact structure above, maintaining the 
        emojis and formatting shown. The message should feel exclusive and valuable to VIP traders.
        """

                # Prepare the API request
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a professional quantitative trader/researcher with over 20 years of experience and 2 PhDs in Quantitative Finance and Machine Learning."},
                        {"role": "user", "content": base_prompt}
                    ],
                    "temperature": 0.7,
                    "max_tokens": 300
                }
                
                  # Call the Groq API
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    message = result["choices"][0]["message"]["content"].strip()
                    self.logger.info(f"Successfully generated follow-up message using Groq for {symbol} {direction}")
                    return message
                else:
                    self.logger.error(f"Error from Groq API: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"Error querying Groq API: {e}")
                return None
            
    def generate_fallback_message(self, signal_data, status, message_type):
        """
        Generate a fallback message using templates when Groq is unavailable.
        
        Args:
            signal_data (dict): The original signal data
            status (dict): Current status of the signal
            message_type (str): Type of message to generate
            
        Returns:
            str: Fallback message
        """
        symbol = signal_data.get("symbol", "Unknown")
        direction = signal_data.get("direction", "Unknown")
        
        additional_info = ""
        if status.get("in_profit", False):
            additional_info = f"Position is currently in profit by {status.get('profit_pips', 0):.1f} pips."
        else:
            additional_info = f"Position is currently down by {abs(status.get('profit_pips', 0)):.1f} pips."
            
        if message_type == "take_profit_hit":
            tp_num = 0
            for i, hit in enumerate(status.get("tps_hit", [])):
                if hit:
                    tp_num = i + 1
                    break
                    
            tp_price = None
            tp_key = f"take_profit{tp_num}" if tp_num > 1 else "take_profit"
            if tp_key in signal_data:
                tp_price = signal_data[tp_key]
                
            message = self.message_templates["take_profit_hit"].format(
                symbol=symbol,
                direction=direction,
                tp_num=tp_num,
                tp_price=tp_price,
                additional_info=additional_info
            )
            
        elif message_type == "stop_loss_hit":
            message = self.message_templates["stop_loss_hit"].format(
                symbol=symbol,
                direction=direction,
                sl_price=signal_data.get("stop_loss", 0),
                additional_info=additional_info
            )
            
        elif message_type == "major_milestone":
            milestone = None
            if status.get("pct_to_tp1", 0) >= 90:
                milestone = "90%"
            elif status.get("pct_to_tp1", 0) >= 75:
                milestone = "75%"
            elif status.get("pct_to_tp1", 0) >= 50:
                milestone = "50%"
            elif status.get("pct_to_tp1", 0) >= 25:
                milestone = "25%"
                
            message = self.message_templates["major_milestone"].format(
                symbol=symbol,
                direction=direction,
                milestone=milestone,
                progress=status.get("pct_to_tp1", 0),
                additional_info=additional_info
            )
            
        else:  # progress_update
            message = self.message_templates["progress_update"].format(
                symbol=symbol,
                direction=direction,
                progress=status.get("pct_to_tp1", 0),
                additional_info=additional_info
            )
            
        return f"📊 SIGNAL UPDATE: {message}"
    
    def process_signals_for_updates(self, min_pct_change=5, min_update_interval_minutes=15):
        """
        Process all active signals and generate follow-up messages for those that need updates.
        
        Args:
            min_pct_change (float): Minimum percentage change to trigger update
            min_update_interval_minutes (int): Minimum minutes between updates
            
        Returns:
            list: Signal updates with generated messages
        """
        if not self.signal_tracker:
            self.logger.error("No signal tracker provided")
            return []
            
        try:
            # Get signals that need updates - use the check_signals_for_updates method from signal_tracker
            signals_to_update = self.signal_tracker.check_signals_for_updates(
                min_pct_change=min_pct_change,
                min_update_interval_minutes=min_update_interval_minutes
            )
            
            results = []
            for signal_update in signals_to_update:
                try:
                    signal_id = signal_update["signal_id"]
                    signal_data = signal_update["signal"]
                    status = signal_update["status"]
                    
                    # Generate follow-up message
                    message = self.generate_message(signal_data, status)
                    
                    results.append({
                        "signal_id": signal_id,
                        "signal": signal_data,
                        "status": status,
                        "message": message,
                        "timestamp": datetime.now()
                    })
                    
                except Exception as e:
                    self.logger.error(f"Error processing signal update: {e}")
            
            self.logger.info(f"Generated {len(results)} follow-up messages")
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing signals for updates: {e}")
            return []