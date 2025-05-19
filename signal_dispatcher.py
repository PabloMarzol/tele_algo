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
from mt5_accountManager import MultiAccountExecutor

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
            username = os.getenv("MT5_USERNAME"),
            password = os.getenv("MT5_PASSWORD"),
            server = os.getenv("MT5_SERVER")
        )
        # Initialize the signal executor
        # self.signal_executor = MT5SignalExecutor(
        #     username = os.getenv("MT5_USERNAME"),
        #     password = os.getenv("MT5_PASSWORD"),
        #     server = os.getenv("MT5_SERVER"),
        #     risk_percent = 0.7  # risk % per trade
        # )
        
        self.signal_executor = MultiAccountExecutor()
        
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
                        
                        if execution_result["success"]:
                            accounts_executed = execution_result["accounts_executed"]
                            total_accounts = execution_result["total_accounts"]
                            self.logger.info(f"Signal {signal_id} executed on {accounts_executed}/{total_accounts} accounts")
                            
                            # Format account details for the admin notification
                            account_details = ""
                            for account_name, result in execution_result["details"].items():
                                if result["success"]:
                                    orders_placed = result.get("order_count", 0)
                                    total_lots = result.get("total_lot_size", 0)
                                    account_details += f"• {account_name}: ✅ {orders_placed} orders, {total_lots:.2f} lots\n"
                                else:
                                    error = result.get("error", "Unknown error")
                                    account_details += f"• {account_name}: ❌ Error: {error}\n"
                            
                            # Send execution notification to admin only
                            admin_msg = f"""
                    🤖 <b>SIGNAL AUTO-EXECUTED</b> 🤖

                    Symbol: {signal_info['symbol']} {signal_info['direction']}
                    Executed on {accounts_executed}/{total_accounts} accounts

                    <b>Account Details:</b>
                    {account_details}

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
                            self.logger.error(f"Failed to execute signal {signal_id} on any account: {execution_result['error']}")
                            
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
            
            # Extract strategy type - look for strategy names in the message
            strategy_mappings = {
                "MA_CROSS SIGNAL": "MA_CROSS",
                "Moving Average Crossover": "MA_CROSS",
                "RSI_REV SIGNAL": "RSI_REV",
                "RSI Reversal": "RSI_REV",
                "SUP_RES SIGNAL": "SUP_RES",
                "Support & Resistance": "SUP_RES",
                "VOL_HAWKES SIGNAL": "VOL_HAWKES",
                "Volatility Breakout (Hawkes)": "VOL_HAWKES"
            }
            
            # Find strategy in message
            for strategy_text, strategy_code in strategy_mappings.items():
                if strategy_text in signal_message:
                    signal_info["strategy"] = strategy_code
                    break
                    
            # Default strategy if not found
            if "strategy" not in signal_info:
                signal_info["strategy"] = "VFX-LIMIT"
            
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
            
            # Extract Hawkes-specific data if present
            hawkes_vol_match = re.search(r"Current Volatility:\s*(\d+\.\d+)", signal_message)
            if hawkes_vol_match:
                signal_info["hawkes_vol"] = float(hawkes_vol_match.group(1))
                
            q05_match = re.search(r"Lower Threshold:\s*(\d+\.\d+)", signal_message)
            if q05_match:
                signal_info["q05"] = float(q05_match.group(1))
                
            q95_match = re.search(r"Upper Threshold:\s*(\d+\.\d+)", signal_message)
            if q95_match:
                signal_info["q95"] = float(q95_match.group(1))
            
            # Add timeframe (not in the message, but we can set defaults)
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
    
    async def check_and_apply_trailing_stops(self):
        """
        Check active positions and apply trailing stops where appropriate.
        """
        try:
            # Skip if signal executor is not initialized
            if not hasattr(self, 'signal_executor') or not self.signal_executor.initialized:
                self.logger.warning("Signal executor not initialized, skipping trailing stop check")
                return
            
            # Apply trailing stops to all active positions
            # Handle both single-account and multi-account executors
            if isinstance(self.signal_executor, MultiAccountExecutor):
                # Multi-account execution
                result = self.signal_executor.apply_trailing_stop()
                
                if result["success"]:
                    accounts_updated = result["accounts_updated"]
                    total_accounts = result["total_accounts"]
                    
                    if accounts_updated > 0:
                        self.logger.info(f"Updated trailing stops on {accounts_updated}/{total_accounts} accounts")
                        
                        # Format account details for the admin notification
                        account_details = ""
                        positions_updated = 0
                        
                        for account_name, account_result in result["details"].items():
                            if account_result["success"]:
                                account_positions_updated = account_result.get("positions_updated", 0)
                                positions_updated += account_positions_updated
                                
                                if account_positions_updated > 0:
                                    account_details += f"\n<b>{account_name}:</b>\n"
                                    
                                    # Add details for each updated position
                                    for detail in account_result.get("details", []):
                                        if detail.get("updated", False):
                                            account_details += f"• {detail['symbol']} {detail['direction']}: SL {detail['old_sl']:.5f} → {detail['new_sl']:.5f} (Profit: {detail['profit_pips']:.1f} pips)\n"
                        
                        if positions_updated > 0:
                            admin_msg = f"""
    🔄 <b>TRAILING STOPS UPDATED</b> 🔄

    Updated positions on {accounts_updated}/{total_accounts} accounts.
    Total positions updated: {positions_updated}

    {account_details}
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
                                    self.logger.error(f"Failed to send trailing stop notification to admin {admin_id}: {e}")
                    else:
                        self.logger.info(f"No trailing stops updated on any account.")
                else:
                    self.logger.error(f"Error applying trailing stops: {result.get('error', 'Unknown error')}")
                    
            else:
                # Single-account execution (original implementation)
                result = self.signal_executor.apply_trailing_stop()
                
                if result["success"]:
                    if result["positions_updated"] > 0:
                        self.logger.info(f"Updated trailing stops for {result['positions_updated']} out of {result['positions_checked']} positions")
                        
                        # Notify admin of trailing stop updates
                        update_details = "\n".join([
                            f"• {detail['symbol']} {detail['direction']}: SL {detail['old_sl']:.5f} → {detail['new_sl']:.5f} (Profit: {detail['profit_pips']:.1f} pips)"
                            for detail in result["details"] if detail.get("updated", False)
                        ])
                        
                        admin_msg = f"""
    🔄 <b>TRAILING STOPS UPDATED</b> 🔄

    Updated {result["positions_updated"]} out of {result["positions_checked"]} positions:

    {update_details}
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
                                self.logger.error(f"Failed to send trailing stop notification to admin {admin_id}: {e}")
                    else:
                        self.logger.info(f"No trailing stops updated. Checked {result['positions_checked']} positions.")
                else:
                    self.logger.error(f"Error applying trailing stops: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            self.logger.error(f"Error in check_and_apply_trailing_stops: {e}")
            
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
    
    async def send_daily_stats(self):
        """
        Send daily statistics to admin.
        """
        try:
            # Skip if signal executor is not initialized
            if not hasattr(self, 'signal_executor') or not self.signal_executor.initialized:
                self.logger.warning("Signal executor not initialized, skipping daily stats")
                return
            
            # Generate daily stats
            result = self.signal_executor.generate_daily_stats()
            
            if not result["success"]:
                self.logger.error(f"Failed to generate daily stats: {result.get('error', 'Unknown error')}")
                return
            
            stats = result["stats"]
            
            # Format the stats message
            stats_msg = f"""
    📊 <b>DAILY TRADING STATISTICS</b> 📊
    <i>{stats['date']}</i>

    <b>Summary:</b>
    - Signals Executed: {stats['signals_executed']}
    - Positions Opened: {stats['positions_opened']}
    - Positions Closed: {stats['positions_closed']}
    - Active Positions: {stats['active_positions']}

    <b>Performance:</b>
    - Wins: {stats['wins']}
    - Losses: {stats['losses']}
    - Win Rate: {stats['win_rate']:.1f}%
    - Total Profit: ${stats['total_profit']:.2f}
    - Total Pips: {stats['total_pips']:.1f}
    - Return: {stats['return_percentage']:.2f}%

    <b>Symbols Traded:</b> {', '.join(stats['symbols_traded'])}
    """
            
            # Add details of closed positions
            closed_positions = [detail for detail in stats['signal_details'] if detail['status'] in ['WIN', 'LOSS']]
            if closed_positions:
                closed_details = "\n".join([
                    f"• {detail['symbol']} {detail['direction']}: {detail['status']} (${detail['profit']:.2f})"
                    for detail in closed_positions
                ])
                stats_msg += f"\n\n<b>Closed Positions:</b>\n{closed_details}"
            
            # Add details of active positions
            active_positions = [detail for detail in stats['signal_details'] if detail['status'] == 'ACTIVE']
            if active_positions:
                active_details = "\n".join([
                    f"• {detail['symbol']} {detail['direction']}: ${detail['unrealized_profit']:.2f} ({detail['unrealized_pips']:.1f} pips)"
                    for detail in active_positions
                ])
                stats_msg += f"\n\n<b>Active Positions:</b>\n{active_details}"
            
            # Send to admin
            for admin_id in ADMIN_USER_ID:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=stats_msg,
                        parse_mode='HTML'
                    )
                    self.logger.info(f"Sent daily stats to admin {admin_id}")
                except Exception as e:
                    self.logger.error(f"Failed to send daily stats to admin {admin_id}: {e}")
            
        except Exception as e:
            self.logger.error(f"Error in send_daily_stats: {e}")
        
    def cleanup(self):
        """Clean up resources when shutting down"""
        self.signal_generator.cleanup()