import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from mt5_signal_generator import MT5SignalGenerator

load_dotenv()

class SignalDispatcher:
    """Manages trading signal generation and distribution"""
    
    def __init__(self, bot, signals_channel_id):
        self.bot = bot
        self.signals_channel_id = signals_channel_id
        self.logger = logging.getLogger('SignalDispatcher')
        
        # Initialize MT5 signal generator
        self.signal_generator = MT5SignalGenerator(
            mt5_username=os.getenv("MT5_USERNAME"),
            mt5_password=os.getenv("MT5_PASSWORD"),
            mt5_server=os.getenv("MT5_SERVER")
        )
        
        # Track last signal time to control frequency
        self.last_signal_time = datetime.now() - timedelta(hours=12)  # Start ready to send
        self.min_signal_interval_hours = 4  # Minimum hours between signals
    
    async def check_and_send_signal(self):
        """Check if it's time to send a signal and do so if appropriate"""
        now = datetime.now()
        hours_since_last = (now - self.last_signal_time).total_seconds() / 3600
        
        # Check if enough time has passed since last signal
        if hours_since_last < self.min_signal_interval_hours:
            self.logger.info(f"Skipping signal check - only {hours_since_last:.2f} hours since last signal")
            return
            
        # Market hours check (optional)
        # Avoid sending signals during major market closures
        current_hour = now.hour
        current_weekday = now.weekday()
        
        # Skip weekends (Saturday and most of Sunday)
        if current_weekday == 5 or (current_weekday == 6 and current_hour < 21):
            self.logger.info("Skipping signal check - weekend market closure")
            return
            
        # Try to generate a signal
        signal = self.signal_generator.generate_signal()
        
        if signal:
            try:
                # Send the signal
                await self.bot.send_message(
                    chat_id=self.signals_channel_id,
                    text=signal,
                    parse_mode='HTML'
                )
                
                self.last_signal_time = now
                self.logger.info(f"Sent trading signal at {now}")
                
                # Optional: Notify admin about sent signal
                # [code to notify admin]
                
            except Exception as e:
                self.logger.error(f"Error sending trading signal: {e}")
        else:
            self.logger.info("No valid signals generated at this time")
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        self.signal_generator.cleanup()