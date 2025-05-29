from imports import *
from main import is_user_admin
# =============================== Signal Functions ============================= #
# ============================================================ #

signal_dispatcher = None
signal_system_initialized = False

async def init_signal_system(context: ContextTypes.DEFAULT_TYPE):
    """Initialize the signal system after bot startup - DEBUG VERSION"""
    global signal_dispatcher, signal_system_initialized
    
    # Skip if already initialized
    if signal_system_initialized:
        logger.info("Signal system already initialized, skipping")
        return
    
    try:
        logger.info("Starting signal system initialization...")
        
        # Debug: Check what we're importing
        logger.info("Attempting to import SignalDispatcher class...")
        
        # Try different import approaches
        try:
            # Method 1: Direct class import
            from signalsManager.signal_dispatcher import SignalDispatcher
            logger.info(f"✅ Successfully imported SignalDispatcher: {SignalDispatcher}")
            logger.info(f"SignalDispatcher type: {type(SignalDispatcher)}")
            
        except ImportError as ie:
            logger.error(f"❌ Import error: {ie}")
            # Method 2: Module import then access class
            try:
                import signalsManager.signal_dispatcher as sd_module
                logger.info(f"Module imported: {sd_module}")
                SignalDispatcher = sd_module.SignalDispatcher
                logger.info(f"Class from module: {SignalDispatcher}")
            except Exception as e2:
                logger.error(f"❌ Module import failed: {e2}")
                return
        
        # Debug: Check if SIGNALS_CHANNEL_ID exists
        if 'SIGNALS_CHANNEL_ID' not in globals():
            logger.error("❌ SIGNALS_CHANNEL_ID not defined in globals")
            # Try to define it with a placeholder
            global SIGNALS_CHANNEL_ID
            SIGNALS_CHANNEL_ID = -1001234567890  # Replace with your actual channel ID
            logger.info(f"Set SIGNALS_CHANNEL_ID to: {SIGNALS_CHANNEL_ID}")
        else:
            logger.info(f"✅ SIGNALS_CHANNEL_ID found: {SIGNALS_CHANNEL_ID}")
        
        # Debug: Check context.bot
        logger.info(f"Context bot type: {type(context.bot)}")
        logger.info(f"Context bot: {context.bot}")
        
        # Now try to create the instance
        logger.info("Creating SignalDispatcher instance...")
        signal_dispatcher = SignalDispatcher(context.bot, SIGNALS_CHANNEL_ID)
        
        # Mark as initialized
        signal_system_initialized = True
        logger.info("✅ Signal system initialized successfully")
        
        # Notify admin
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text="🤖 Signal system initialized successfully"
                )
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
        
    except Exception as e:
        logger.error(f"❌ Error in init_signal_system: {e}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        signal_dispatcher = None
        
        # Notify admin of failure
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"❌ Signal system initialization failed: {e}"
                )
            except Exception as notify_error:
                logger.error(f"Failed to notify admin of init failure: {notify_error}")

# Safe wrapper functions for scheduled jobs
async def apply_trailing_stops():
    """Safely apply trailing stops"""
    global signal_dispatcher
    if signal_dispatcher is None:
        logger.warning("Cannot apply trailing stops - signal_dispatcher is None")
        return
    
    try:
        await signal_dispatcher.check_and_apply_trailing_stops()
    except Exception as e:
        logger.error(f"Error in trailing stops: {e}")

async def send_daily_stats():
    """Safely send daily stats"""
    global signal_dispatcher
    if signal_dispatcher is None:
        logger.warning("Cannot send daily stats - signal_dispatcher is None")
        return
    
    try:
        await signal_dispatcher.send_daily_stats()
    except Exception as e:
        logger.error(f"Error in daily stats: {e}")

# Define the scheduled function
async def check_and_send_signals(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for and send trading signals based on market conditions"""
    global signal_dispatcher
    if signal_dispatcher:
        await signal_dispatcher.check_and_send_signal()
    else:
        logger.warning("Cannot check signals - signal_dispatcher is None")
        
async def report_signal_system_status(context: ContextTypes.DEFAULT_TYPE):
    """Log periodic status information about the signal system"""
    global signal_dispatcher
    
    if not signal_dispatcher:
        logger.warning("⚠️ Signal system not initialized yet")
        return
    
    try:
        # Get MT5 connection status
        mt5_connected = signal_dispatcher.signal_generator.connected
        
        # Get time since last signal
        hours_since = (datetime.now() - signal_dispatcher.last_signal_time).total_seconds() / 3600
        
        logger.info("📊 SIGNAL SYSTEM STATUS 📊")
        logger.info(f"MT5 Connection: {'✅ Connected' if mt5_connected else '❌ Disconnected'}")
        logger.info(f"Hours since last signal: {hours_since:.1f}")
        logger.info(f"Signals sent today: {sum(1 for k,v in signal_dispatcher.signal_generator.signal_history.items() if v['timestamp'].date() == datetime.now().date())}")
        logger.info(f"Next check eligible: {'Yes' if hours_since >= signal_dispatcher.min_signal_interval_hours else 'No'}")
    except Exception as e:
        logger.error(f"Error generating status report: {e}")

async def signal_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command to check signal system status for admins"""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    global signal_dispatcher
    
    if not signal_dispatcher:
        await update.message.reply_text("⚠️ Signal system not initialized yet.")
        return
    
    try:
        # Get MT5 connection status
        mt5_connected = signal_dispatcher.signal_generator.connected
        
        # Get time since last signal
        hours_since = (datetime.now() - signal_dispatcher.last_signal_time).total_seconds() / 3600
        
        # Count signals sent today
        today_signals = sum(1 for k,v in signal_dispatcher.signal_generator.signal_history.items() 
                         if v['timestamp'].date() == datetime.now().date())
        
        # Format a detailed status message
        status_msg = (
            f"📊 SIGNAL SYSTEM STATUS 📊\n\n"
            f"MT5 Connection: {'✅ Connected' if mt5_connected else '❌ Disconnected'}\n"
            f"Hours since last signal: {hours_since:.1f}\n"
            f"Signals sent today: {today_signals}\n"
            f"Next check eligible: {'✅ Yes' if hours_since >= signal_dispatcher.min_signal_interval_hours else '❌ No'}\n\n"
        )
        
        # Add signal history
        if signal_dispatcher.signal_generator.signal_history:
            status_msg += "📝 RECENT SIGNALS:\n\n"
            
            # Sort by timestamp (most recent first)
            sorted_history = sorted(
                signal_dispatcher.signal_generator.signal_history.items(),
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

async def check_and_send_signal_updates(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for signal updates and send follow-up messages"""
    global signal_dispatcher
    if signal_dispatcher:
        await signal_dispatcher.send_signal_updates()
    else:
        logger.warning("Cannot send signal updates - signal_dispatcher is None")

async def handle_signalstats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /signalstats command for admin users.
    Shows daily trading statistics on demand.
    """
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
        if 'signal_dispatcher' not in globals() or signal_dispatcher is None:
            await status_msg.edit_text("⚠️ Signal dispatcher not initialized. Cannot generate stats.")
            return
            
        # Check if signal executor is initialized
        if not hasattr(signal_dispatcher, 'signal_executor') or not signal_dispatcher.signal_executor.initialized:
            await status_msg.edit_text("⚠️ Signal executor not initialized. Cannot generate stats.")
            return
        
        # Generate daily stats
        result = signal_dispatcher.signal_executor.generate_daily_stats()
        
        if not result["success"]:
            error_msg = f"❌ Failed to generate daily stats: {result.get('error', 'Unknown error')}"
            await status_msg.edit_text(error_msg)
            return
        
        stats = result["stats"]
        
        # Format the main stats message
        stats_msg = f"""
📊 <b>DAILY TRADING STATISTICS</b> 📊
<i>{stats['date']}</i>

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

async def signal_stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /signalbreakdown command - shows stats for each individual signal.
    """
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
        if 'signal_dispatcher' not in globals() or signal_dispatcher is None:
            await status_msg.edit_text("⚠️ Signal dispatcher not initialized.")
            return
            
        if not hasattr(signal_dispatcher, 'signal_executor') or not signal_dispatcher.signal_executor.initialized:
            await status_msg.edit_text("⚠️ Signal executor not initialized.")
            return
        
        # Generate signal breakdown stats
        if isinstance(signal_dispatcher.signal_executor, MultiAccountExecutor):
            result = signal_dispatcher.signal_executor.generate_signal_breakdown_stats_multi_account(days)
        else:
            result = signal_dispatcher.signal_executor.generate_signal_stats(days)
        
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
        logger.error(f"Error in handle_signalbreakdown: {e}")
        error_msg = f"❌ Error generating signal breakdown: {str(e)}"
        try:
            if 'status_msg' in locals():
                await status_msg.edit_text(error_msg)
            else:
                await message.reply_text(error_msg)
        except:
            pass
