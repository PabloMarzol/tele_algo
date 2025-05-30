
from imports import *

import sys
import os
sys.path.append(os.path.abspath(".."))
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


config = Config()
ADMIN_USER_ID = config.ADMIN_USER_ID
SIGNALS_CHANNEL_ID = config.SIGNALS_CHANNEL_ID
# ================================================================================================= #
# ================================================================================================= #

class SignalBot:
    """ Class for trading signals functionality"""
    
    def __init__(self, bot_token, signals_channel_id):
        """Initialize signal bot with dedicated token"""
        self.bot_token = bot_token
        self.signals_channel_id = signals_channel_id
        self.signal_dispatcher = None
        self.signal_system_initialized = False
        
        # Create dedicated bot instance for signals
        from telegram import Bot
        self.bot = Bot(token=bot_token)
        
        # CREATE A SIMPLE APPLICATION FOR COMMANDS
        from telegram.ext import Application, CommandHandler
        self.signal_app = Application.builder().token(bot_token).build()
        
        # REGISTER COMMANDS DIRECTLY IN THE CONSTRUCTOR
        self.setup_commands()
        
        logger.info(f"Signal Bot initialized with token ending in ...{bot_token[-8:]}")
    
    def setup_commands(self):
        """Setup commands for the signal bot"""
        self.signal_app.add_handler(CommandHandler("signalstatus", self.signal_status_command))
        self.signal_app.add_handler(CommandHandler("signalstats", self.handle_signalstats))
        self.signal_app.add_handler(CommandHandler("algostats", self.signal_stats_command))
    
    def start_polling(self):
        """Start the signal bot polling"""
        import asyncio
        asyncio.set_event_loop(asyncio.new_event_loop())  # ADD THIS LINE
        self.signal_app.run_polling()
    
    async def init_signal_system(self):
        """Initialize the signal system after bot startup"""
        # Skip if already initialized
        if self.signal_system_initialized:
            logger.info("Signal system already initialized, skipping")
            return
        
        try:
            logger.info("Starting signal system initialization...")
            
            # Import SignalDispatcher from the correct path
            from tradingSignals.signalsManager.signal_dispatcher import SignalDispatcher
            logger.info("✅ Successfully imported SignalDispatcher")
            
            # Create instance with SIGNAL BOT (not manager bot)
            self.signal_dispatcher = SignalDispatcher(self.bot, self.signals_channel_id)
            
            # Mark as initialized
            self.signal_system_initialized = True
            logger.info("✅ Signal system initialized successfully")
            
            # Notify admin via SIGNAL BOT
            for admin_id in ADMIN_USER_ID:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text="🤖 Signal system initialized successfully (Algo Bot)"
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error in init_signal_system: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            self.signal_dispatcher = None

    async def apply_trailing_stops(self):
        """Safely apply trailing stops"""
        if self.signal_dispatcher is None:
            logger.warning("Cannot apply trailing stops - signal_dispatcher is None")
            return
        
        try:
            await self.signal_dispatcher.check_and_apply_trailing_stops()
        except Exception as e:
            logger.error(f"Error in trailing stops: {e}")

    async def send_daily_stats(self):
        """Safely send daily stats"""
        if self.signal_dispatcher is None:
            logger.warning("Cannot send daily stats - signal_dispatcher is None")
            return
        
        try:
            await self.signal_dispatcher.send_daily_stats()
        except Exception as e:
            logger.error(f"Error in daily stats: {e}")

    async def check_and_send_signals(self):
        """Check for and send trading signals based on market conditions"""
        if self.signal_dispatcher:
            await self.signal_dispatcher.check_and_send_signal()
        else:
            logger.warning("Cannot check signals - signal_dispatcher is None")
            
    async def report_signal_system_status(self):
        """Log periodic status information about the signal system"""
        if not self.signal_dispatcher:
            logger.warning("⚠️ Signal system not initialized yet")
            return
        
        try:
            # Get MT5 connection status
            mt5_connected = self.signal_dispatcher.signal_generator.connected
            
            # Get time since last signal
            hours_since = (datetime.now() - self.signal_dispatcher.last_signal_time).total_seconds() / 3600
            
            logger.info("📊 SIGNAL SYSTEM STATUS 📊")
            logger.info(f"MT5 Connection: {'✅ Connected' if mt5_connected else '❌ Disconnected'}")
            logger.info(f"Hours since last signal: {hours_since:.1f}")
            logger.info(f"Signals sent today: {sum(1 for k,v in self.signal_dispatcher.signal_generator.signal_history.items() if v['timestamp'].date() == datetime.now().date())}")
            logger.info(f"Next check eligible: {'Yes' if hours_since >= self.signal_dispatcher.min_signal_interval_hours else 'No'}")
        except Exception as e:
            logger.error(f"Error generating status report: {e}")

    async def signal_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Command to check signal system status for admins"""
        if update.effective_user.id not in ADMIN_USER_ID:
            await update.message.reply_text("This command is only available to admins.")
            return
        
        if not self.signal_dispatcher:
            await update.message.reply_text("⚠️ Signal system not initialized yet.")
            return
        
        try:
            # Get MT5 connection status
            mt5_connected = self.signal_dispatcher.signal_generator.connected
            
            # Get time since last signal
            hours_since = (datetime.now() - self.signal_dispatcher.last_signal_time).total_seconds() / 3600
            
            # Count signals sent today
            today_signals = sum(1 for k,v in self.signal_dispatcher.signal_generator.signal_history.items() 
                             if v['timestamp'].date() == datetime.now().date())
            
            # Format a detailed status message
            status_msg = (
                f"📊 SIGNAL SYSTEM STATUS 📊\n\n"
                f"🤖 VFX - ALGO\n"
                f"MT5 Connection: {'✅ Connected' if mt5_connected else '❌ Disconnected'}\n"
                f"Hours since last signal: {hours_since:.1f}\n"
                f"Signals sent today: {today_signals}\n"
                f"Next check eligible: {'✅ Yes' if hours_since >= self.signal_dispatcher.min_signal_interval_hours else '❌ No'}\n\n"
            )
            
            # Add signal history
            if self.signal_dispatcher.signal_generator.signal_history:
                status_msg += "📝 RECENT SIGNALS:\n\n"
                
                # Sort by timestamp (most recent first)
                sorted_history = sorted(
                    self.signal_dispatcher.signal_generator.signal_history.items(),
                    key=lambda x: x[1]['timestamp'],
                    reverse=True
                )
                
                # Show last 5 signals
                for i, (key, data) in enumerate(sorted_history[:5]):
                    signal_time = data['timestamp'].strftime("%Y-%m-%d %H:%M")
                    status_msg += f"{i+1}. {data['symbol']} {data['direction']} at {signal_time}\n"
            
            await update.message.reply_text(status_msg)
            
        except Exception as e:
            error_msg = f"Error retrieving signal status: {e}"
            logger.error(error_msg)
            await update.message.reply_text(f"⚠️ {error_msg}")

    async def handle_signalstats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /signalstats command for admin users via signal bot."""
        message = update.message
        user_id = message.from_user.id
        
        # Check if user is admin
        if user_id not in ADMIN_USER_ID:
            await message.reply_text("❌ Access denied. Admin only command.")
            return
        
        try:
            # Send "generating stats..." message first
            status_msg = await message.reply_text("📊 Generating daily statistics...")
            
            # Check if signal dispatcher exists and is initialized
            if not self.signal_dispatcher:
                await status_msg.edit_text("⚠️ Signal dispatcher not initialized. Cannot generate stats.")
                return
                
            # Check if signal executor is initialized
            if not hasattr(self.signal_dispatcher, 'signal_executor') or not self.signal_dispatcher.signal_executor.initialized:
                await status_msg.edit_text("⚠️ Signal executor not initialized. Cannot generate stats.")
                return
            
            # Generate daily stats
            result = self.signal_dispatcher.signal_executor.generate_daily_stats()
            
            if not result["success"]:
                error_msg = f"❌ Failed to generate daily stats: {result.get('error', 'Unknown error')}"
                await status_msg.edit_text(error_msg)
                return
            
            stats = result["stats"]
            
            # Format the main stats message
            stats_msg = f"""
📊 <b>DAILY TRADING STATISTICS</b> 📊
<i>{stats['date']}</i>

<b>🤖 Bot:</b> VFX - ALGO (Signals)

<b>📈 Summary:</b>
• Signals Executed: {stats['signals_executed']}
• Positions Opened: {stats['positions_opened']}
• Positions Closed: {stats['positions_closed']}
• Active Positions: {stats['active_positions']}

<b>💰 Performance:</b>
• Wins: {stats['wins']} | Losses: {stats['losses']}
• Win Rate: {stats['win_rate']:.1f}%
• Total Profit: ${stats['total_profit']:.2f}
• Total Pips: {stats['total_pips']:.1f}
• Return: {stats['return_percentage']:.2f}%

<b>🎯 Symbols Traded:</b> {', '.join(stats['symbols_traded']) if stats['symbols_traded'] else 'None'}
"""
            
            # Add multi-account breakdown if available
            if 'account_breakdown' in stats and stats['account_breakdown']:
                stats_msg += f"\n<b>💼 Account Breakdown:</b>\n"
                for account_name, account_data in stats['account_breakdown'].items():
                    if account_data.get('success', False):
                        stats_msg += f"• <b>{account_name}:</b> ${account_data.get('profit', 0):.2f} ({account_data.get('return_pct', 0):.1f}%) - {account_data.get('wins', 0)}W/{account_data.get('losses', 0)}L\n"
                    else:
                        stats_msg += f"• <b>{account_name}:</b> ❌ {account_data.get('error', 'Error')}\n"
            
            # Add details of closed positions if any
            closed_positions = [detail for detail in stats['signal_details'] if detail.get('status') in ['WIN', 'LOSS']]
            if closed_positions:
                stats_msg += f"\n<b>🔄 Closed Positions Today:</b>\n"
                for detail in closed_positions[:10]:  # Limit to 10 to avoid message length issues
                    account_info = f" ({detail.get('account', 'N/A')})" if 'account' in detail else ""
                    stats_msg += f"• {detail['symbol']} {detail['direction']}: {detail['status']} ${detail.get('profit', 0):.2f}{account_info}\n"
                
                if len(closed_positions) > 10:
                    stats_msg += f"• ... and {len(closed_positions) - 10} more\n"
            
            # Add details of active positions if any
            active_positions = [detail for detail in stats['signal_details'] if detail.get('status') == 'ACTIVE']
            if active_positions:
                stats_msg += f"\n<b>🔴 Active Positions:</b>\n"
                for detail in active_positions[:10]:  # Limit to 10
                    account_info = f" ({detail.get('account', 'N/A')})" if 'account' in detail else ""
                    unrealized_profit = detail.get('unrealized_profit', 0)
                    unrealized_pips = detail.get('unrealized_pips', 0)
                    stats_msg += f"• {detail['symbol']} {detail['direction']}: ${unrealized_profit:.2f} ({unrealized_pips:.1f} pips){account_info}\n"
                
                if len(active_positions) > 10:
                    stats_msg += f"• ... and {len(active_positions) - 10} more\n"
            
            # Add generation timestamp
            stats_msg += f"\n⏰ <i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            
            # Update the status message with the full stats
            await status_msg.edit_text(stats_msg, parse_mode='HTML')
            
            logger.info(f"Sent daily stats to admin user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in handle_signalstats: {e}")
            error_msg = f"❌ Error generating stats: {str(e)}"
            try:
                if 'status_msg' in locals():
                    await status_msg.edit_text(error_msg)
                else:
                    await message.reply_text(error_msg)
            except:
                pass

    async def signal_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /algostats command - shows stats for each individual signal."""
        message = update.message
        user_id = message.from_user.id
        
        # Check if user is admin
        if user_id not in ADMIN_USER_ID:
            await message.reply_text("❌ Access denied. Admin only command.")
            return
        
        try:
            from tradingSignals.mt5_Fn.mt5_accountManager import MultiAccountExecutor
            # Get days parameter (default: 1 day)
            days = 1
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                    if days < 1 or days > 7:  # Limit to 7 days to keep response manageable
                        days = 1
                except ValueError:
                    days = 1
            
            # Send "generating stats..." message first
            status_msg = await message.reply_text(f"📊 Generating signal breakdown for last {days} day(s)...")
            
            # Check if signal dispatcher exists and is initialized
            if not self.signal_dispatcher:
                await status_msg.edit_text("⚠️ Signal dispatcher not initialized.")
                return
                
            if not hasattr(self.signal_dispatcher, 'signal_executor') or not self.signal_dispatcher.signal_executor.initialized:
                await status_msg.edit_text("⚠️ Signal executor not initialized.")
                return
            
            # Generate signal breakdown stats
            if isinstance(self.signal_dispatcher.signal_executor, MultiAccountExecutor):
                result = self.signal_dispatcher.signal_executor.generate_signal_breakdown_stats_multi_account(days)
            else:
                result = self.signal_dispatcher.signal_executor.generate_signal_stats(days)
            
            if not result["success"]:
                await status_msg.edit_text(f"❌ Failed to generate signal breakdown: {result.get('error', 'Unknown error')}")
                return
            
            stats = result["stats"]
            signal_breakdown = stats["signal_breakdown"]
            
            if not signal_breakdown:
                await status_msg.edit_text(f"📊 No signals found in the last {days} day(s).")
                return
            
            # Format the message
            msg = f"""📊 <b>INDIVIDUAL SIGNAL BREAKDOWN</b> 📊
<i>{stats['date_range']}</i>

<b>🤖 Bot:</b> VFX - ALGO (Signals)

<b>📈 Overview:</b>
• Total Signals: {stats['total_signals_executed']}
• Total Profit: ${stats['total_profit_all_signals']:.2f}
"""
            
            if 'accounts_analyzed' in stats:
                msg += f"• Accounts: {stats['accounts_analyzed']}\n"
            
            msg += "\n<b>🎯 Individual Signal Performance:</b>\n"
            
            # Sort signals by profit
            sorted_signals = sorted(
                signal_breakdown.items(),
                key=lambda x: x[1]['total_profit'],
                reverse=True
            )
            
            for i, (signal_key, signal_stats) in enumerate(sorted_signals):
                if i >= 10:  # Limit to top 10 signals to avoid message length issues
                    msg += f"\n... and {len(sorted_signals) - 10} more signals"
                    break
                
                profit_emoji = "💰" if signal_stats['total_profit'] > 0 else "📉" if signal_stats['total_profit'] < 0 else "➖"
                direction_emoji = "🔼" if signal_stats['direction'] == "BUY" else "🔻"
                
                msg += f"\n{profit_emoji} <b>{signal_stats['symbol']} {direction_emoji} ({signal_stats['strategy']})</b>\n"
                msg += f"  • ID: {signal_stats['signal_id']}\n"
                msg += f"  • Orders: {signal_stats['orders_placed']} | Closed: {signal_stats['total_trades']} | Active: {signal_stats['active_positions']}\n"
                
                if signal_stats['total_trades'] > 0:
                    msg += f"  • W/L: {signal_stats['wins']}/{signal_stats['losses']} ({signal_stats['win_rate']:.1f}%)\n"
                    msg += f"  • P&L: ${signal_stats['total_profit']:.2f} (${signal_stats['avg_profit_per_trade']:.2f}/trade)\n"
                    msg += f"  • Pips: {signal_stats['total_pips']:.1f} ({signal_stats['avg_pips_per_trade']:.1f}/trade)\n"
                else:
                    msg += f"  • Unrealized P&L: ${signal_stats['total_profit']:.2f}\n"
                    msg += f"  • Unrealized Pips: {signal_stats['total_pips']:.1f}\n"
                
                msg += f"  • Executed: {signal_stats['execution_time']}\n"
            
            msg += f"\n⏰ <i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            
            # Update the status message with the breakdown
            await status_msg.edit_text(msg, parse_mode='HTML')
            
            logger.info(f"Sent signal breakdown to admin user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in signal_stats_command: {e}")
            error_msg = f"❌ Error generating signal breakdown: {str(e)}"
            try:
                if 'status_msg' in locals():
                    await status_msg.edit_text(error_msg)
                else:
                    await message.reply_text(error_msg)
            except:
                pass






