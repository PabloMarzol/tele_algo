import logging
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from mt5_signal_generator import MT5SignalGenerator

from news_fetcher import FinancialNewsFetcher
from groq_client import GroqClient
from signal_tracker import SignalTracker

load_dotenv()

class SignalDispatcher:
    """
    Manages trading signal generation, distribution, tracking, and follow-up messages.
    Implements both original signal generation and Plan_2 functionality.
    """
    
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
        
        # Initialize signal tracker for monitoring signal progress
        self.signal_tracker = SignalTracker()
        
        # Initialize news fetcher with API key from environment
        self.news_fetcher = FinancialNewsFetcher(
            api_key=os.getenv("NEWS_API_KEY")
        )
        
        # Initialize GROQ client with API key from environment
        self.groq_client = GroqClient(
            api_key=os.getenv("GROQ_API_KEY"),
            model=os.getenv("GROQ_MODEL")
        )
                
        # Track last signal time to control frequency
        self.last_signal_time = datetime.now() - timedelta(hours=12)  # Start ready to send
        self.min_signal_interval_hours = 1  # Minimum hours between signals
        self.signals_sent_today = 0
        self.signals_sent_this_hour = 0
        
        # Track last operation times for Plan_2 functionality
        self.last_signal_check_time = datetime.now() - timedelta(hours=1)
        self.last_news_time = datetime.now() - timedelta(hours=4)
        
        # Set intervals for scheduled tasks
        self.signal_check_interval_minutes = 25  # Check signals every 5 minutes
        self.news_interval_hours = 3            # Send news every 4 hours
        
        self.last_daily_reset = datetime.now().date()
        self.last_hourly_reset = datetime.now().hour

        self.logger.info("Signal dispatcher initialized with extended functionality")
    
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
        signal_text, signal_data = self.signal_generator.generate_signal()
        
        if signal_text and signal_data:
            try:
                # Send the signal
                await self.bot.send_message(
                    chat_id=self.signals_channel_id,
                    text=signal_text,
                    parse_mode='HTML'
                )
                
                # Add signal to tracker for follow-up messages
                signal_id = await self.process_new_signal(signal_data)
                
                # Update tracking values
                self.last_signal_time = now
                self.signals_sent_today += 1
                self.signals_sent_this_hour += 1
                
                self.logger.info(f"Sent trading signal at {now} - Daily: {self.signals_sent_today}/{self.signal_generator.max_signals_per_day}, Hourly: {self.signals_sent_this_hour}/{self.signal_generator.max_signals_per_hour}")
                
            except Exception as e:
                self.logger.error(f"Error sending trading signal: {e}")
        else:
            self.logger.info("No valid signals generated at this time")
    
    async def process_new_signal(self, signal_data):
        """
        Process a new trading signal for tracking.
        
        Args:
            signal_data (dict): Signal data including symbol, direction, entry, SL, TP
        
        Returns:
            str: Signal ID if successful, None otherwise
        """
        try:
            # Add signal to tracker
            signal_id = self.signal_tracker.add_signal(signal_data)
            
            if not signal_id:
                self.logger.error("Failed to add signal to tracker")
                return None
            
            self.logger.info(f"Added signal {signal_id} to tracker for follow-up messages")
            return signal_id
            
        except Exception as e:
            self.logger.error(f"Error processing new signal: {e}")
            return None
    
    async def check_and_send_signal_updates(self):
        """
        Check for signal updates and send them if needed.
        This implements Phase 2: Track signals progress toward take-profit levels.
        
        Returns:
            bool: True if updates were sent, False otherwise
        """
        try:
            now = datetime.now()
            minutes_since_last_check = (now - self.last_signal_check_time).total_seconds() / 60
            
            if minutes_since_last_check < self.signal_check_interval_minutes:
                self.logger.info(f"Skipping signal update check, only {minutes_since_last_check:.1f} minutes since last check")
                return False
            
            # Check for signals that need updates
            signals_to_update = self.signal_tracker.check_signals_for_updates(
                min_pct_change=5,  # 5% change to trigger update
                min_update_interval_minutes=self.signal_check_interval_minutes
            )
            
            if not signals_to_update:
                self.logger.info("No signals need updates")
                self.last_signal_check_time = now
                return False
            
            # Process each signal that needs an update
            updates_sent = 0
            for signal_update in signals_to_update:
                signal = signal_update["signal"]
                status = signal_update["status"]
                
                # Generate update message using GROQ
                update_message = self.groq_client.generate_signal_update(signal, status["current_price"])
                
                # Format and send the message
                formatted_message = self.format_signal_update_message(signal, status, update_message)
                await self.send_message_to_channel(formatted_message)
                
                updates_sent += 1
                self.logger.info(f"Sent update for signal {signal_update['signal_id']}")
            
            # Clean up completed signals
            self.signal_tracker.cleanup_completed_signals()
            
            # Update last check time
            self.last_signal_check_time = now
            
            self.logger.info(f"Sent {updates_sent} signal updates")
            return updates_sent > 0
            
        except Exception as e:
            self.logger.error(f"Error in check_and_send_signal_updates: {e}")
            return False
    
    def format_signal_update_message(self, signal, status, ai_message):
        """
        Format a signal update message.
        
        Args:
            signal (dict): Original signal data
            status (dict): Current status of the signal
            ai_message (str): AI-generated update message
        
        Returns:
            str: Formatted message
        """
        symbol = signal["symbol"]
        direction = signal["direction"]
        direction_emoji = "🟢" if direction == "BUY" else "🔴"
        
        # Format price movement
        price_move = status["profit_pips"]
        price_move_formatted = f"+{price_move:.4f}" if price_move >= 0 else f"{price_move:.4f}"
        price_move_emoji = "📈" if price_move >= 0 else "📉"
        
        # Format TP progress
        tp_progress = ""
        if status["pct_to_tp1"] > 0:
            tp_progress = f"Progress to TP1: {status['pct_to_tp1']:.1f}%"
        
        # Check for TP hits
        tp_status = ""
        if any(status["tps_hit"]):
            hit_tps = [i+1 for i, hit in enumerate(status["tps_hit"]) if hit]
            tp_status = f"✅ TP{', TP'.join(map(str, hit_tps))} reached!"
        
        # Check for stop loss hit
        if status["stop_hit"]:
            message = f"""<b>⚠️ SIGNAL UPDATE {direction_emoji}</b>

<b>{symbol} {direction}</b>

<b>Stop Loss Reached!</b>
{price_move_emoji} Movement: {price_move_formatted}

<i>Consider closing this position per your risk management rules.</i>

<b>Entry:</b> {signal['entry_price']}
<b>Current:</b> {status['current_price']}
<b>Stop Loss:</b> {signal['stop_loss']}
"""
            return message
        
        # Regular update message
        message = f"""<b>📊 SIGNAL UPDATE {direction_emoji}</b>

<b>{symbol} {direction}</b>

{ai_message}

{price_move_emoji} Movement: {price_move_formatted}
{tp_progress}
{tp_status}

<i>Generated at {datetime.now().strftime('%H:%M:%S')} VFX Time</i>
"""
        return message
    
    async def check_and_send_news(self):
        """
        Check if it's time to send news and send if appropriate.
        This implements Phase 1: Pull financial news from API and process with GROQ.
        
        Returns:
            bool: True if news was sent, False otherwise
        """
        try:
            now = datetime.now()
            hours_since_last_news = (now - self.last_news_time).total_seconds() / 3600
            
            if hours_since_last_news < self.news_interval_hours:
                self.logger.info(f"Skipping news check, only {hours_since_last_news:.1f} hours since last news")
                return False
            
            # Fetch news
            success = await self.fetch_and_send_news()
            
            if success:
                self.last_news_time = now
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error in check_and_send_news: {e}")
            return False
    
    async def fetch_and_send_news(self):
        """
        Fetch financial news, process with GROQ, and send to channel.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # First, get forex news
            forex_news = self.news_fetcher.get_forex_news(limit=3)
            
            # If not enough forex news, get general news
            if len(forex_news) < 3:
                general_news = self.news_fetcher.fetch_news(limit=5)
                news_items = forex_news + general_news
                news_items = news_items[:5]  # Limit to 5 items
            else:
                news_items = forex_news
            
            if not news_items:
                self.logger.warning("No news items found to send")
                return False
            
            # Save news to file for reference
            self.news_fetcher.save_recent_news()
            
            # Generate AI commentary with GROQ
            ai_commentary = self.groq_client.generate_news_commentary(news_items)
            
            # Format the message
            formatted_message = self.format_news_message(news_items, ai_commentary)
            
            # Send to channel
            await self.send_message_to_channel(formatted_message)
            
            self.logger.info(f"Sent news update with {len(news_items)} items")
            return True
            
        except Exception as e:
            self.logger.error(f"Error fetching and sending news: {e}")
            return False
    
    def format_news_message(self, news_items, ai_commentary):
        """
        Format news items and AI commentary into a message.
        
        Args:
            news_items (list): List of news item dictionaries
            ai_commentary (str): AI-generated commentary
        
        Returns:
            str: Formatted message
        """
        message = "<b>📰 MARKET NEWS ROUNDUP 📰</b>\n\n"
        
        # Add the top 2 news items
        for i, item in enumerate(news_items[:2]):
            message += f"<b>{item['title']}</b>\n"
            message += f"<i>{item['source']} - {item['published_at'][:10]}</i>\n"
            message += f"<a href='{item['url']}'>Read full story</a>\n\n"
        
        # Add AI commentary
        message += f"<b>📝 MARKET INSIGHT:</b>\n{ai_commentary}\n\n"
        
        # Add more news titles as links
        if len(news_items) > 2:
            message += "<b>MORE TOP HEADLINES:</b>\n"
            for item in news_items[2:5]:
                message += f"• <a href='{item['url']}'>{item['title']}</a>\n"
        
        message += "\n<i>Stay informed with the latest market updates from VFX Trading! 📈</i>"
        
        return message
    
    async def send_message_to_channel(self, message):
        """
        Send a message to the signals channel.
        
        Args:
            message (str): Message to send
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            await self.bot.send_message(
                chat_id=self.signals_channel_id,
                text=message,
                parse_mode='HTML',
                disable_web_page_preview=False  # Allow preview for the first link
            )
            return True
        except Exception as e:
            self.logger.error(f"Error sending message to channel: {e}")
            return False
    
    async def run_scheduler(self):
        """
        Run the scheduler for periodic checks.
        
        This method is designed to be run in a background task.
        """
        try:
            while True:
                # Check for signal updates
                await self.check_and_send_signal_updates()
                
                # Check for news (less frequently)
                await self.check_and_send_news()
                
                # Wait before next check
                await asyncio.sleep(60)  # Check every minute
                
        except asyncio.CancelledError:
            self.logger.info("Scheduler task cancelled")
        except Exception as e:
            self.logger.error(f"Error in scheduler: {e}")
    
    def cleanup(self):
        """Clean up resources when shutting down"""
        self.signal_generator.cleanup()