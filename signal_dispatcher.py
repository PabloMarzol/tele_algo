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
        self.min_signal_interval_hours = 1  # Minimum hours between signals
        self.signals_sent_today = 0
        self.signals_sent_this_hour = 0
        self.last_daily_reset = datetime.now().date()
        self.last_hourly_reset = datetime.now().hour
    
    
    async def check_and_send_signal(self):
        """Check if it's time to send a signal and do so if appropriate"""
        now = datetime.now()
        
        # Reset daily counter if needed
        if now.date() != self.last_daily_reset:
            self.signals_sent_today = 0
            self.last_daily_reset = now.date()
        
        # Reset hourly counter if needed
        if now.hour != self.last_hourly_reset:
            self.signals_sent_this_hour = 0
            self.last_hourly_reset = now.hour
        
        # Check frequency controls
        minutes_since_last = (now - self.last_signal_time).total_seconds() / 60
        if minutes_since_last < self.signal_generator.min_minutes_between_signals:
            self.logger.info(f"Signal spacing control: Only {minutes_since_last:.1f} minutes since last signal (min: {self.signal_generator.min_minutes_between_signals})")
            return
            
        if self.signals_sent_today >= self.signal_generator.max_signals_per_day:
            self.logger.info(f"Daily limit reached: {self.signals_sent_today} signals sent today (max: {self.signal_generator.max_signals_per_day})")
            return
            
        if self.signals_sent_this_hour >= self.signal_generator.max_signals_per_hour:
            self.logger.info(f"Hourly limit reached: {self.signals_sent_this_hour} signals sent this hour (max: {self.signal_generator.max_signals_per_hour})")
            return
            
        # Market hours check (optional)
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
                
                # Update tracking values
                self.last_signal_time = now
                self.signals_sent_today += 1
                self.signals_sent_this_hour += 1
                
                self.logger.info(f"Sent trading signal at {now} - Daily: {self.signals_sent_today}/{self.signal_generator.max_signals_per_day}, Hourly: {self.signals_sent_this_hour}/{self.signal_generator.max_signals_per_hour}")
                
            except Exception as e:
                self.logger.error(f"Error sending trading signal: {e}")
        else:
            self.logger.info("No valid signals generated at this time")
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        self.signal_generator.cleanup()