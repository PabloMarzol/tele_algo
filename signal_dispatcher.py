import asyncio
import logging
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from mt5_signal_generator import MT5SignalGenerator

from news_fetcher import FinancialNewsFetcher  
from groq_client import GroqClient
from signal_tracker import SignalTracker
from signal_follow import SignalFollowUpGenerator
from mt5_signal_executor import MT5SignalExecutor

load_dotenv()
ADMIN_USER_ID = [7823596188, 7396303047]

class SignalDispatcher:
    """Manages trading signal generation and distribution"""
    
    def __init__(self, bot, signals_channel_id):
        self.bot = bot
        self.signals_channel_id = signals_channel_id
        self.logger = logging.getLogger('SignalDispatcher')
        
        # Initialize MT5 signal generator
        self.signal_generator = MT5SignalGenerator(
            username=os.getenv("MT5_USERNAME"),
            password=os.getenv("MT5_PASSWORD"),
            server=os.getenv("MT5_SERVER")
        )
        # Initialize the signal executor
        self.signal_executor = MT5SignalExecutor(
            username=os.getenv("MT5_USERNAME"),
            password=os.getenv("MT5_PASSWORD"),
            server=os.getenv("MT5_SERVER"),
            risk_percent=1.0  # 1% risk per trade
        )
        self.auto_execute = False
        # self.signal_tracker = self.signal_generator.signal_history 

        
        # Track last signal time to control frequency
        self.last_signal_time = datetime.now() - timedelta(hours=12)  # Start ready to send
        self.min_signal_interval_hours = 1  # Minimum hours between signals
        self.signals_sent_today = 0
        self.signals_sent_this_hour = 0
        self.last_daily_reset = datetime.now().date()
        self.last_hourly_reset = datetime.now().hour

        news_api_key = os.getenv("NEWS_API_KEY")
        if news_api_key:
            self.news_fetcher = FinancialNewsFetcher(api_key=news_api_key)
            self.logger.info("News fetcher initialized")
        else:
            self.news_fetcher = None
            self.logger.warning("News fetcher not initialized - no API key provided")
        
        # Initialize Groq client if API key is provided
        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            self.groq_client = GroqClient(api_key=groq_api_key)
            self.logger.info("Groq client initialized")
        else:
            self.groq_client = None
            self.logger.warning("Groq client not initialized - no API key provided")
        
        # Initialize signal tracker
        self.signal_tracker = SignalTracker()
        self.signal_tracker.register_update_callback(self.handle_signal_updates)
        self.logger.info("Signal tracker initialized with callback")
        
        # Initialize follow-up generator
        self.follow_up_generator = SignalFollowUpGenerator(signal_tracker=self.signal_tracker)

    
    async def handle_signal_updates(self, signals_to_update):
        """Handle updates for signals that have crossed important thresholds"""
        try:
            update_count = 0
            for signal_update in signals_to_update:
                try:
                    signal_id = signal_update["signal_id"]
                    signal_data = signal_update["signal"]
                    status = signal_update["status"]
                    
                    # Generate follow-up message
                    message = await self.follow_up_generator.query_groq(
                        self.follow_up_generator.create_message_context(
                            signal_data, status, self._determine_message_type(status)
                        )
                    )
                    
                    # If Groq fails, use fallback
                    if not message:
                        message = self.follow_up_generator.generate_fallback_message(
                            signal_data, status, self._determine_message_type(status)
                        )
                    
                    # Send to channel
                    await self.bot.send_message(
                        chat_id=self.signals_channel_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    
                    update_count += 1
                    self.logger.info(f"Sent follow-up message for signal {signal_id}")
                    
                    # Add a small delay between messages to prevent flooding
                    if len(signals_to_update) > 1:
                        await asyncio.sleep(1)
                    
                except Exception as e:
                    self.logger.error(f"Error handling signal update: {e}")
            
            if update_count > 0:
                self.logger.info(f"Processed {update_count} signal updates")
                
            return update_count
            
        except Exception as e:
            self.logger.error(f"Error handling signal updates: {e}")
            return 0
    
    def _determine_message_type(self, status):
        """Determine the message type based on signal status."""
        if status.get("stop_hit", False):
            return "stop_loss_hit"
        
        if any(status.get("tps_hit", [])):
            return "take_profit_hit"
        
        if status.get("pct_to_tp1", 0) >= 90:
            return "major_milestone"
        elif status.get("pct_to_tp1", 0) >= 75:
            return "major_milestone"
        elif status.get("pct_to_tp1", 0) >= 50:
            return "major_milestone"
        elif status.get("pct_to_tp1", 0) >= 25:
            return "major_milestone"
        
        return "progress_update"
    
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
                # Extract signal info from formatted message
                signal_info = self.extract_signal_info(signal)
                
                # Send the signal message to the channel
                await self.bot.send_message(
                    chat_id=self.signals_channel_id,
                    text=signal,
                    parse_mode='HTML'
                )
                
                # Update tracking values
                self.last_signal_time = now
                self.signals_sent_today += 1
                self.signals_sent_this_hour += 1
                
                # Add to signal tracker and get the signal_id
                if signal_info:
                    signal_id = self.signal_tracker.add_signal(signal_info)
                    
                    # Add signal_id to the signal_info dict for the executor
                    signal_info['signal_id'] = signal_id
                    
                    # Execute the signal automatically
                    try:
                        execution_result = self.signal_executor.execute_signal(signal_info)
                        
                        # Log the execution result
                        if execution_result["success"]:
                            self.logger.info(f"Signal {signal_id} executed successfully: {execution_result['order_count']} orders placed")
                            
                            # Format order details for the admin notification
                            order_details = "\n".join([
                                f"• Order {i+1}: ID {order['order_id']}, Entry {order['entry_price']:.2f}, SL {order['stop_loss']:.2f}, Lot {order['lot_size']:.2f}"
                                for i, order in enumerate(execution_result['orders'])
                            ])
                            
                            # Send execution notification to admin only
                            admin_msg = f"""
                        🤖 <b>VFX_Algo Trading Signal</b> 🤖

                        Symbol: {signal_info['symbol']} {signal_info['direction']}
                        Placed {execution_result['order_count']} limit orders across the entry range.

                        <b>Order Details:</b>
                        {order_details}

                        <b>Take Profit Levels:</b>
                        - TP1: {execution_result['take_profits'][0] if execution_result['take_profits'] else 'N/A'}
                        {f"• TP2: {execution_result['take_profits'][1]}" if len(execution_result['take_profits']) > 1 else ""}
                        {f"• TP3: {execution_result['take_profits'][2]}" if len(execution_result['take_profits']) > 2 else ""}

                        Total Position Size: {execution_result.get('total_lot_size', 0):.2f} lots
                        Signal ID: {signal_id}
                        """
                            # Send to admin only
                            for admin_id in ADMIN_USER_ID:
                                try:
                                    await self.bot.send_message(
                                        chat_id=admin_id,
                                        text=admin_msg,
                                        parse_mode='HTML'
                                    )
                                except Exception as e:
                                    self.logger.error(f"Failed to send execution notification to admin {admin_id}: {e}")
                        else:
                            error_msg = f"Failed to execute signal {signal_id}: {execution_result['error']}"
                            self.logger.error(error_msg)
                            
                            # Notify admin of execution failure
                            for admin_id in ADMIN_USER_ID:
                                try:
                                    await self.bot.send_message(
                                        chat_id=admin_id,
                                        text=f"⚠️ EXECUTION FAILED: {signal_info['symbol']} {signal_info['direction']}\n\nError: {execution_result['error']}",
                                        parse_mode='HTML'
                                    )
                                except Exception as e:
                                    self.logger.error(f"Failed to send execution error to admin {admin_id}: {e}")
                                    
                    except Exception as e:
                        self.logger.error(f"Error during signal execution: {e}")
                        
                        # Notify admin of execution exception
                        for admin_id in ADMIN_USER_ID:
                            try:
                                await self.bot.send_message(
                                    chat_id=admin_id,
                                    text=f"⚠️ EXECUTION ERROR: {signal_info['symbol']} {signal_info['direction']}\n\nException: {str(e)}",
                                    parse_mode='HTML'
                                )
                            except Exception as notify_error:
                                self.logger.error(f"Failed to send execution exception to admin {admin_id}: {notify_error}")
                    
                    # Schedule follow-up message
                    asyncio.create_task(self.send_signal_followup(signal_info))
                
                self.logger.info(f"Sent trading signal at {now} - Daily: {self.signals_sent_today}/{self.signal_generator.max_signals_per_day}, Hourly: {self.signals_sent_this_hour}/{self.signal_generator.max_signals_per_hour}")
                
            except Exception as e:
                self.logger.error(f"Error sending trading signal: {e}")
        else:
            self.logger.info("No valid signals generated at this time")
        
        updated_count = await self.signal_tracker.monitor_active_signals()
        if updated_count > 0:
            self.logger.info(f"Processed updates for {updated_count} signals")

    def extract_signal_info(self, signal_message):
        """Extract structured signal information from a formatted signal message string"""
        try:
            # Initialize empty signal info dictionary
            signal_info = {}
            
            # Extract direction (BUY/SELL)
            if "BUY LIMIT ORDERS" in signal_message:
                signal_info["direction"] = "BUY"
            elif "SELL LIMIT ORDERS" in signal_message:
                signal_info["direction"] = "SELL"
            else:
                self.logger.error("Could not determine signal direction")
                return None
                
            # Extract symbol by checking for common display names
            symbol_mappings = {
                "GOLD (XAU/USD)": "XAUUSD",
                "NASDAQ (NAS100)": "NAS100",
                "EUR/USD": "EURUSD",
                "GBP/USD": "GBPUSD",
                "AUD/USD": "AUDUSD",
                "USD/CAD": "USDCAD",
                "CAC 40 (FRA40)": "FRA40",
                "FTSE 100 (UK100)": "UK100",
                "DOW JONES (US30)": "US30",
                "S&P 500 (US500)": "US500"
            }
            
            # Check for each symbol in the message
            for display_name, symbol in symbol_mappings.items():
                if display_name in signal_message:
                    signal_info["symbol"] = symbol
                    break
            
            # If no symbol found using display names, try direct symbol names
            if "symbol" not in signal_info:
                for symbol in ["XAUUSD", "NAS100", "EURUSD", "GBPUSD", "AUDUSD", "USDCAD", "FRA40", "UK100", "US30", "US500"]:
                    if symbol in signal_message:
                        signal_info["symbol"] = symbol
                        break
            
            if "symbol" not in signal_info:
                self.logger.error("Could not determine symbol from signal message")
                return None
            
            # Extract price levels using regex
            import re
            
            # Look for entry zone
            entry_zone_match = re.search(r"Entry Zone:.+?(\d+\.?\d*)\s*[-—]\s*(\d+\.?\d*)", signal_message)
            if entry_zone_match:
                signal_info["entry_range_low"] = float(entry_zone_match.group(1))
                signal_info["entry_range_high"] = float(entry_zone_match.group(2))
                # Also set an entry price as the midpoint for convenience
                signal_info["entry_price"] = (signal_info["entry_range_low"] + signal_info["entry_range_high"]) / 2
            
            # Look for stop loss range
            sl_range_match = re.search(r"Stop Loss Range:.+?(\d+\.?\d*)\s*[-—]\s*(\d+\.?\d*)", signal_message)
            if sl_range_match:
                signal_info["stop_range_low"] = float(sl_range_match.group(1))
                signal_info["stop_range_high"] = float(sl_range_match.group(2))
                # Also set a stop loss as the midpoint for convenience
                signal_info["stop_loss"] = (signal_info["stop_range_low"] + signal_info["stop_range_high"]) / 2
            
            # Look for take profit levels
            tp1_match = re.search(r"TP1:\s*(\d+\.?\d*)", signal_message)
            if tp1_match:
                signal_info["take_profit"] = float(tp1_match.group(1))
            
            tp2_match = re.search(r"TP2:\s*(\d+\.?\d*)", signal_message)
            if tp2_match:
                signal_info["take_profit2"] = float(tp2_match.group(1))
            
            tp3_match = re.search(r"TP3:\s*(\d+\.?\d*)", signal_message)
            if tp3_match:
                signal_info["take_profit3"] = float(tp3_match.group(1))
            
            # Add strategy and timeframe (not in the message, but we can set defaults)
            signal_info["strategy"] = "VFX-LIMIT"
            signal_info["timeframe"] = "M15"  # Default timeframe
            
            # Add timestamp
            signal_info["timestamp"] = datetime.now()
            
            # Check if we have minimum required information
            if "symbol" in signal_info and "direction" in signal_info:
                return signal_info
            else:
                self.logger.error("Extracted signal info missing required fields")
                return None
        
        except Exception as e:
            self.logger.error(f"Error extracting signal info: {e}")
            return None
    
    async def send_signal_followup(self, signal_info):
        """Send a follow-up message with analysis after a signal"""
        if not hasattr(self, 'groq_client') or self.groq_client is None:
            self.logger.info("No Groq client available - skipping follow-up")
            return
        
        try:
            # Wait a bit to make it seem natural
            await asyncio.sleep(90)  # 1.5 minutes
            
            # Generate follow-up text using Groq
            followup = await self.groq_client.generate_signal_followup(signal_info)
            
            if not followup:
                self.logger.error("Failed to generate signal follow-up")
                return
            
            # Get symbol display name
            symbol_display = {
                "XAUUSD": "🟡 GOLD (XAU/USD)",
                "NAS100": "💻 NASDAQ (NAS100)",
                "EURUSD": "💱 EUR/USD",
                "GBPUSD": "💱 GBP/USD",
                "AUDUSD": "💱 AUD/USD",
                "USDCAD": "💱 USD/CAD",
                "FRA40": "🇫🇷 CAC 40 (FRA40)",
                "UK100": "🇬🇧 FTSE 100 (UK100)",
                "US30": "🇺🇸 DOW JONES (US30)",
                "US500": "🇺🇸 S&P 500 (US500)"
            }
            
            display_name = symbol_display.get(signal_info['symbol'], f"💱 {signal_info['symbol']}")
            
            # Format the message with enhanced styling
            message = f"""
    🔮 <b>VFX SIGNAL ANALYSIS</b> 🔮

    <b>Asset:</b> {display_name}
    <b>Direction:</b> {'🔼 BUY' if signal_info['direction'] == 'BUY' else '🔻 SELL'}

    📊 <b>MARKET ANALYSIS</b> 📊

    {followup}

    🧠 <b>KEY TAKEAWAYS</b> 🧠

    - Watch price/volume difference at entry range
    - Manage risk with partial take-profits
    - Stay disciplined with your stop loss

    ⏰ <i>Analysis time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>

    🚫 <i>For informational purposes only. Not financial advice.</i>
    """
            
            # Send to channel
            await self.bot.send_message(
                chat_id=self.signals_channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info(f"Sent follow-up analysis for {signal_info['symbol']} {signal_info['direction']}")
        
        except Exception as e:
            self.logger.error(f"Error sending signal follow-up: {e}")
    
    async def send_signal_updates(self):
        """Check for signal updates and send follow-up messages."""
        try:
            # Add debugging to identify the issue
            self.logger.info(f"Bot type: {type(self.bot)}")
            self.logger.info(f"Channel ID: {self.signals_channel_id}")
            
            # Process signals for updates
            signal_updates = self.follow_up_generator.process_signals_for_updates()
            
            for update in signal_updates:
                signal_id = update["signal_id"]
                message = update["message"]
                
                # More debugging
                self.logger.info(f"Attempting to send message for signal {signal_id}")
                
                # Try sending message with error catching
                try:
                    await self.bot.send_message(
                        chat_id=self.signals_channel_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    self.logger.info(f"Successfully sent follow-up message for signal {signal_id}")
                except Exception as e:
                    self.logger.error(f"Error sending specific message: {e}")
                
            return len(signal_updates)
            
        except Exception as e:
            self.logger.error(f"Error sending signal updates: {e}")
            return 0
        
    def cleanup(self):
        """Clean up resources when shutting down"""
        self.signal_generator.cleanup()