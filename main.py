from imports import *

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from userReg.reg_Fn import *
from local_DB.db_handlers import *  
from tradingSignals.SignalAlgo import *
from mySQL.c_functions import *



WELCOME_MSG = db.get_setting("welcome_message", config.get("messages.welcome"))
PRIVATE_WELCOME_MSG = db.get_setting("private_welcome_message", config.get("messages.private_welcome"))

# -------------------------------------- Core Handles ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced start function with direct registration support."""
    user = update.effective_user
    user_id = user.id
    
    print(f"User ID {user_id} ({user.first_name}) started the bot")
    
    # SECURITY CHECK: Prevent duplicate registrations
    if await check_existing_registration(update, context, user_id):
        return
    
    # Enhanced parameter handling for direct registration
    referral_admin = None
    source_channel = "main_channel"  # Default
    is_direct_registration = False
    
    if context.args and len(context.args) > 0:
        arg = context.args[0]
        
        # Direct registration from main channel
        if arg == "register" or arg == "signup" or arg == "join":
            is_direct_registration = True
            source_channel = "main_channel_direct"
            print(f"✅ Direct registration from main channel")
        
        # Admin referral
        elif arg.startswith("ref_"):
            try:
                referral_admin = int(arg.split("_")[1])
                source_channel = "admin_referral"
                print(f"✅ Admin referral from {referral_admin}")
            except:
                pass
        
        # Source-specific registrations
        elif arg.startswith("signals"):
            source_channel = "signals_channel"
            is_direct_registration = True
        elif arg.startswith("strategy"):
            source_channel = "strategy_channel" 
            is_direct_registration = True
    
    # Store user with source tracking
    db.add_user({
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "source_channel": source_channel,
        "is_direct_registration": is_direct_registration,
        "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Handle referral notifications
    if referral_admin:
        try:
            await context.bot.send_message(
                chat_id=referral_admin,
                text=f"✅ {user.first_name} (ID: {user_id}) connected through your referral link!"
            )
        except Exception as e:
            print(f"Error notifying admin {referral_admin}: {e}")
    
    # Get appropriate welcome message
    try:
        if source_channel == "signals_channel":
            welcome_msg = config.get("messages.signals_auto_welcome", 
                                   "Welcome to VFX Trading Signals!")
        elif is_direct_registration:
            # Special welcome for direct registrations from main channel
            welcome_msg = (
                "<b>🎉 Welcome to VFX Trading Registration! 🎉</b>\n\n"
                "Thank you for clicking our registration link! You're about to join "
                "thousands of successful traders who trust VFX Trading.\n\n"
                "<b>🚀 Quick Setup Process:</b>\n"
                "• Answer a few quick questions about your trading style\n"
                "• Get your Vortex-FX account set up (if you don't have one)\n"
                "• Verify your account and deposit minimum $100\n"
                "• Gain instant VIP access to our premium services!\n\n"
                "<b>⏱️ This takes less than 5 minutes!</b>\n\n"
                "<b>💡 Quick Tip:</b>\n\n"

                "Ready to start your trading journey? 🌟"
            )
        else:
            welcome_msg = config.get("messages.admin_auto_welcome", 
                                   "Welcome to VFX Trading!")
        
    except Exception as e:
        print(f"Error getting welcome message: {e}")
        welcome_msg = "Welcome to VFX Trading!"
    
    # Enhanced buttons for direct registration
    if is_direct_registration:
        keyboard = [
            [InlineKeyboardButton("🚀 Start Registration", callback_data="start_guided")],
            [InlineKeyboardButton("📋 What's Included?", callback_data="explain_services")],
            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🚀 Start Guided Setup", callback_data="start_guided")],
            [InlineKeyboardButton("📋 What's Included?", callback_data="explain_services")],
            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send welcome message
    await update.message.reply_text(
        welcome_msg,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Track the user
    context.bot_data.setdefault("auto_welcoming_users", {})
    context.bot_data["auto_welcoming_users"][user_id] = {
        "name": user.first_name,
        "status": "welcomed",
        "source_channel": source_channel,
        "is_direct_registration": is_direct_registration,
        "welcome_sent": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    # Set initial state
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "awaiting_guided_setup"
    
    db.update_analytics(active_users=1)
    print(f"✅ Start function completed for user {user_id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help message with all available commands."""
    # user_id = update.effective_user.id
    is_admin = await is_user_admin(update, context)
    
    # Basic commands for all users
    help_text = (
        "Here are the available commands:\n\n"
        "/start - Start the bot and begin profile creation\n"
        "/help - Show this help message\n"
        "/cancel - Cancel the current conversation\n"
    )
    
    # Add admin-specific commands if the user is an admin
    if is_admin:
        admin_help = (
            "\nAdmin Commands:\n"
            "/stats - Show bot statistics\n"
            "/users - List recent users to start a conversation with\n"
            "/endchat - End the current user conversation\n"
            "/updatemsg - Update scheduled messages\n"
            "/viewmsgs - View currently scheduled messages\n"
            "/managemsg - Manage VFX channel messaging system\n\n"
            
            "VFX Message Management:\n"
            "/managemsg view hourly - View all hourly welcome messages\n"
            "/managemsg view interval - View all interval messages\n"
            "/managemsg add hourly <set-time (9)> <Your message> - Set message for 9:00 AM\n"
            "/managemsg add interval signal_buy Your message - Add a new interval message\n"
            "/managemsg remove interval signal_buy - Remove an interval message\n"
            "/managemsg reset - Reset interval message rotation\n\n"
            
            "Admin Features:\n"
            "- Forward a message from a user to start a conversation with them\n"
            "- Any regular message you send will be forwarded to the current user in conversation\n"
            "- The VFX messaging system sends welcome messages hourly and rotates through\n"
            "  different promotional messages every 20 minutes\n"
        )
        help_text += admin_help
    
    await update.message.reply_text(help_text)
    
    # Update user activity
    db.update_user_activity(update.effective_user.id)
    
    # Update analytics
    db.update_analytics(commands_used=1)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Provide statistics about the bot usage to admins."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Get stats from database
    total_users = db.users_df.height
    verified_users = db.users_df.filter(pl.col("is_verified") == True).height
    active_users_7d = db.get_active_users(days=7)
    active_users_30d = db.get_active_users(days=30)
    
    # Format stats message
    stats_msg = (
        f"📊 Bot Statistics 📊\n\n"
        f"Total Users: {total_users}\n"
        f"Verified Users: {verified_users}\n"
        f"Active Users (7 days): {active_users_7d}\n"
        f"Active Users (30 days): {active_users_30d}\n"
        f"Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await update.message.reply_text(stats_msg)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text("Information collection cancelled.")
    
    # Clean up conversation data if exists
    if "user_info" in context.user_data:
        del context.user_data["user_info"]
    
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the admin."""
    # Log the error
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Send error message to admin
    error_message = f"⚠️ Bot Error ⚠️\n\n{context.error}\n\nUpdate: {update}"
    if len(error_message) > 4000:  # Telegram message length limit
        error_message = error_message[:4000] + "..."
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID, 
            text=error_message
        )
    except Exception as e:
        logger.error(f"Failed to send error message to admin: {e}")
    
    # Diagnostic information
    if update and update.effective_chat:
        try:
            chat_type = update.effective_chat.type
            chat_id = update.effective_chat.id
            logger.info(f"Error occurred in {chat_type} chat {chat_id}")
        except:
            pass
    
    if update and update.message:
        try:
            message_text = update.message.text
            logger.info(f"Message that caused error: {message_text}")
        except:
            pass
    
    if context.user_data:
        try:
            logger.info(f"User data: {context.user_data}")
        except:
            pass

async def debug_vip_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to check VIP status in local database."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /debugvip <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        user_info = db.get_user(user_id)
        
        if not user_info:
            await update.message.reply_text(f"User {user_id} not found in local database.")
            return
        
        # Show all VIP-related fields
        debug_msg = f"<b>🔍 VIP Status Debug for User {user_id}</b>\n\n"
        debug_msg += f"<b>Basic Info:</b>\n"
        debug_msg += f"• Name: {user_info.get('first_name', 'Unknown')}\n"
        debug_msg += f"• Verified: {user_info.get('is_verified', False)}\n"
        debug_msg += f"• Trading Account: {user_info.get('trading_account', 'None')}\n\n"
        
        debug_msg += f"<b>VIP Fields:</b>\n"
        debug_msg += f"• vip_access_granted: {user_info.get('vip_access_granted', 'Not Set')}\n"
        debug_msg += f"• vip_eligible: {user_info.get('vip_eligible', 'Not Set')}\n"
        debug_msg += f"• vip_services: {user_info.get('vip_services', 'Not Set')}\n"
        debug_msg += f"• vip_services_list: {user_info.get('vip_services_list', 'Not Set')}\n"
        debug_msg += f"• vip_granted_date: {user_info.get('vip_granted_date', 'Not Set')}\n"
        debug_msg += f"• vip_request_status: {user_info.get('vip_request_status', 'Not Set')}\n\n"
        
        debug_msg += f"<b>Balance Info:</b>\n"
        debug_msg += f"• account_balance: {user_info.get('account_balance', 0)}\n"
        debug_msg += f"• funding_status: {user_info.get('funding_status', 'Not Set')}\n"
        
        # Get real-time balance for comparison
        if user_info.get('trading_account'):
            try:
                mysql_db = get_mysql_connection()
                if mysql_db and mysql_db.is_connected():
                    account_info = mysql_db.verify_account_exists(user_info.get('trading_account'))
                    if account_info['exists']:
                        real_time_balance = float(account_info.get('balance', 0))
                        debug_msg += f"• real_time_balance: {real_time_balance}\n"
            except Exception as e:
                debug_msg += f"• real_time_balance: Error - {e}\n"
        
        await update.message.reply_text(debug_msg, parse_mode='HTML')
        
    except ValueError:
        await update.message.reply_text("Invalid user ID format.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


# -------------------------------------- User Management System ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def explain_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explain VIP services to new users."""
    query = update.callback_query
    await query.answer()
    
    services_explanation = (
        "<b>🌟 VFX Trading VIP Services Explained 🌟</b>\n\n"
        
        "<b>🔔 VIP Signals Service:</b>\n"
        "• Live trading alerts sent directly to your phone\n"
        "• Entry points, stop losses, and take profit levels\n"
        "• Real-time market updates and trend analysis\n"
        "• Perfect for busy traders who want expert guidance\n\n"
        
        "<b>🤖 VIP Automated Strategy:</b>\n"
        "• Fully automated trading on your account\n"
        "• Our algorithms trade for you 24/7\n"
        "• No manual work required - set and forget\n"
        "• Professional risk management built-in\n"
        "• Perfect for passive income generation\n\n"
        
        "<b>💰 Investment Required:</b>\n"
        "• Minimum deposit: $100 (to start with VIP access)\n"
        "• Recommended: $500+ for optimal results\n"
        "• No monthly fees - one-time verification\n\n"
        
        "<b>🎯 Which One Is Right for You?</b>\n"
        "• <b>Choose Signals</b> if you want to learn and trade manually\n"
        "• <b>Choose Automated</b> if you want passive income\n"
        "• <b>Choose Both</b> for maximum profit potential!\n\n"
        
        "<b>Ready to get started?</b> 🚀"
    )
    
    keyboard = [
        [InlineKeyboardButton("🚀 Start Registration Now", callback_data="start_guided")],
        [InlineKeyboardButton("💬 Ask Questions First", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        services_explanation,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

def generate_registration_link(bot_username: str) -> str:
    """Generate direct registration link for main channel."""
    return f"https://t.me/{bot_username}?start=register"

async def my_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's account dashboard - main entry point with real-time data."""
    user_id = update.effective_user.id
    
    # Get user info
    user_info = db.get_user(user_id)
    if not user_info:
        await update.message.reply_text(
            "🔐 <b>Account Not Found</b>\n\n"
            "It looks like you haven't registered yet! Use /start to begin registration.",
            parse_mode='HTML'
        )
        return
    
    # Show loading message for balance fetch
    loading_msg = await update.message.reply_text(
        "📊 <b>Loading Your Dashboard...</b>\n\n"
        "Fetching real-time account data... ⏳",
        parse_mode='HTML'
    )
    
    # Small delay to show loading 
    await asyncio.sleep(1)
    
    # Delete loading message and show dashboard
    await loading_msg.delete()
    
    await show_account_dashboard(update, context, user_info, is_command=True)

async def show_account_dashboard(update, context, user_info, is_command=False):
    """Display user's account dashboard with real-time balance from MySQL."""
    user_id = user_info.get('user_id')
    first_name = user_info.get('first_name', 'User')
    
    # Get account status
    trading_account = user_info.get('trading_account', 'Not provided')
    is_verified = user_info.get('is_verified', False)
    risk_profile = user_info.get('risk_profile_text', 'Not set')
    deposit_amount = user_info.get('deposit_amount', 'Not set')
    
    # VIP STATUS FROM LOCAL DB (FIXED)
    vip_access_granted = user_info.get('vip_access_granted', False)
    vip_services_list = user_info.get('vip_services_list', '')
    vip_granted_date = user_info.get('vip_granted_date', '')
    
    # Real-time balance
    real_time_balance = 0.0
    balance_source = "cached"
    
    if trading_account and trading_account != "Not provided":
        try:
            mysql_db = get_mysql_connection()
            if mysql_db and mysql_db.is_connected():
                account_info = mysql_db.verify_account_exists(trading_account)
                if account_info['exists']:
                    real_time_balance = float(account_info.get('balance', 0))
                    balance_source = "real-time MySQL"
                    
                    # Update local DB with fresh balance
                    db.add_user({
                        "user_id": user_id,
                        "account_balance": real_time_balance,
                        "last_balance_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        except Exception as e:
            print(f"Error fetching balance: {e}")
            real_time_balance = user_info.get('account_balance', 0) or 0.0
            balance_source = "cached"
    
    # Status indicators
    verification_status = "✅ Verified" if is_verified else "⚠️ Pending"
    vip_status = "🌟 Active" if vip_access_granted else "🔒 Not Active"
    
    # Balance status
    if real_time_balance >= 100:
        balance_emoji = "💰"
        balance_status = "✅ VIP Qualified"
    elif real_time_balance > 0:
        balance_emoji = "💳"
        balance_status = f"⚠️ ${100 - real_time_balance:,.0f} more for VIP"
    else:
        balance_emoji = "💸"
        balance_status = "❌ Funding Required"
    
    # Build dashboard with VIP info
    dashboard = (
        f"<b>👤 Your VFX Trading Account</b>\n\n"
        f"<b>🎯 Welcome back, {first_name}!</b>\n\n"
        
        f"<b>📊 Account Overview:</b>\n"
        f"• Trading Account: <code>{trading_account}</code>\n"
        f"• Verification: {verification_status}\n"
        f"• Current Balance: {balance_emoji} <b>${real_time_balance:,.2f}</b>\n"
        f"• Balance Status: {balance_status}\n"
        f"• VIP Access: {vip_status}\n"
    )
    
    # Add VIP services info if granted
    if vip_access_granted and vip_services_list:
        dashboard += f"• Active Services: {vip_services_list}\n"
        if vip_granted_date:
            dashboard += f"• VIP Since: {vip_granted_date[:10]}\n"
    
    
    dashboard += (
        f"<b>🎯 Your Profile:</b>\n"
        f"• Risk Level: {risk_profile}\n"
        f"• Target Deposit: ${deposit_amount}\n"
        f"• Member Since: {user_info.get('join_date', 'Unknown')}\n\n"
    )
    
    # Status-specific messaging
    if vip_access_granted:
        dashboard += (
            f"<b>🎉 VIP Services Active!</b>\n"
            f"• All premium features unlocked 🌟\n"
            f"• Professional trading support available 👨‍💼\n"
            f"• Priority customer service 📞\n\n"
        )
    elif not is_verified:
        dashboard += (
            f"<b>⚠️ Next Steps:</b>\n"
            f"• Complete account verification\n"
            f"• Deposit minimum $100\n"
            f"• Gain VIP access to premium services\n\n"
        )
    elif real_time_balance < 100:
        needed = 100 - real_time_balance
        dashboard += (
            f"<b>💳 Almost There!</b>\n"
            f"• Deposit ${needed:,.0f} more for VIP access\n"
            f"• Access premium trading signals\n"
            f"• Get automated trading strategies\n\n"
        )
    
    dashboard += (
        f"<b>💡 Pro Tip:</b>\n"
        f"• Use <b>/myaccount</b> anytime to return here\n"
        f"• Click 'Refresh Balance' for latest data\n"
        f"• Your VIP status updates automatically! 🚀\n\n"
    )
    
    # Buttons based on VIP status
    keyboard = []
    
    keyboard.append([
        InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile_menu"),
        InlineKeyboardButton("🔄 Refresh Balance", callback_data="check_balance_now")
    ])
    
    if vip_access_granted:
        keyboard.append([
            InlineKeyboardButton("🌟 My VIP Services", callback_data="my_vip_services"),
            InlineKeyboardButton("📊 Request Additional Service", callback_data="request_vip_both_services")
        ])
    else:
        if is_verified and real_time_balance >= 100:
            keyboard.append([
                InlineKeyboardButton("🚀 Request VIP Access", callback_data="request_vip_both_services")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🚀 Complete Setup", callback_data="complete_setup")
            ])
    
    keyboard.append([
        InlineKeyboardButton("❓ Need Help?", callback_data="help_menu"),
        InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_command:
        await update.message.reply_text(dashboard, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(dashboard, parse_mode='HTML', reply_markup=reply_markup)

async def edit_profile_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show profile editing options - FIXED VERSION."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = db.get_user(user_id)
    
    if not user_info:
        await query.edit_message_text("❌ User profile not found.")
        return
    
    menu_text = (
        "<b>✏️ Edit Your Profile</b>\n\n"
        "<b>Current Information:</b>\n"
        f"• Risk Level: {user_info.get('risk_profile_text', 'Not set')}\n"
        f"• Target Deposit: ${user_info.get('deposit_amount', 'Not set')}\n"
        f"• Trading Interest: {user_info.get('trading_interest', 'Not specified')}\n\n"
        
        "<b>What would you like to update?</b>\n\n"
        "<i>Note: Account number and personal details cannot be changed for security reasons.</i>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🎯 Risk Level", callback_data="edit_risk_level"),
            InlineKeyboardButton("💰 Target Deposit", callback_data="edit_deposit_amount")
        ],
        [
            InlineKeyboardButton("📈 Trading Interest", callback_data="edit_trading_interest")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_dashboard"),
            InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(menu_text, parse_mode='HTML', reply_markup=reply_markup)

async def edit_risk_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow user to update their risk level."""
    query = update.callback_query
    await query.answer()
    
    risk_text = (
        "<b>🎯 Update Your Risk Level</b>\n\n"
        "<b>Choose your preferred trading style:</b>\n\n"
        
        "<b>🛡️ Conservative (Low Risk):</b>\n"
        "• Safer trades with smaller profits\n"
        "• Lower chance of losses\n"
        "• Perfect for beginners\n\n"
        
        "<b>⚖️ Balanced (Medium Risk):</b>\n"
        "• Good balance of safety and profit\n"
        "• Moderate risk, moderate reward\n"
        "• Most popular choice\n\n"
        
        "<b>🚀 Aggressive (High Risk):</b>\n"
        "• Higher profit potential\n"
        "• Bigger risks involved\n"
        "• For experienced traders\n\n"
        
        "<b>What's your preference?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🛡️ Conservative", callback_data="update_risk_low"),
            InlineKeyboardButton("⚖️ Balanced", callback_data="update_risk_medium"),
            InlineKeyboardButton("🚀 Aggressive", callback_data="update_risk_high")
        ],
        [InlineKeyboardButton("🔙 Back to Edit Menu", callback_data="edit_profile_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(risk_text, parse_mode='HTML', reply_markup=reply_markup)

async def update_risk_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process risk level update."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Extract risk level
    if "low" in callback_data:
        risk_level = "conservative"
        risk_value = 2
        emoji = "🛡️"
    elif "medium" in callback_data:
        risk_level = "balanced"
        risk_value = 5
        emoji = "⚖️"
    elif "high" in callback_data:
        risk_level = "aggressive"
        risk_value = 8
        emoji = "🚀"
    
    # Update database
    db.add_user({
        "user_id": user_id,
        "risk_profile_text": risk_level,
        "risk_appetite": risk_value,
        "profile_updated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await query.edit_message_text(
        f"<b>✅ Risk Level Updated!</b>\n\n"
        f"Your new risk level: {emoji} <b>{risk_level.capitalize()}</b>\n\n"
        f"This change will be applied to all future trading activities.\n\n"
        f"<i>Returning to your dashboard...</i>",
        parse_mode='HTML'
    )
    
    # Auto-return to dashboard after 2 seconds
    import asyncio
    await asyncio.sleep(2)
    
    user_info = db.get_user(user_id)
    await show_account_dashboard(update, context, user_info)

async def my_vip_services_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's VIP services status."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = db.get_user(user_id)
    
    real_time_balance = 0.0
    if user_info and user_info.get("trading_account"):
        try:
            mysql_db = get_mysql_connection()
            if mysql_db and mysql_db.is_connected():
                account_info = mysql_db.verify_account_exists(user_info.get("trading_account"))
                if account_info['exists']:
                    real_time_balance = float(account_info.get('balance', 0))
        except Exception as e:
            print(f"Error getting real-time balance for VIP services: {e}")
            real_time_balance = user_info.get('account_balance', 0) or 0
    
    # Check VIP access status from multiple fields
    vip_access_granted = user_info.get('vip_access_granted', False)
    vip_eligible = user_info.get('vip_eligible', False)
    is_verified = user_info.get('is_verified', False)
    vip_services = user_info.get('vip_services', '')
    vip_services_list = user_info.get('vip_services_list', '')
    
    # Determine overall VIP status
    has_vip_access = vip_access_granted or (vip_eligible and is_verified and real_time_balance >= 100)
    
    services_text = (
        f"<b>🌟 Your VIP Services Status</b>\n\n"
        
        f"<b>📊 Account Summary:</b>\n"
        f"• Account Verified: {'✅ Yes' if is_verified else '❌ No'}\n"
        f"• Current Balance: ${real_time_balance:,.2f}\n"
        f"• VIP Eligible: {'✅ Yes' if vip_eligible else '❌ No'}\n"
        f"• VIP Access Granted: {'✅ Yes' if vip_access_granted else '❌ No'}\n\n"
        
        f"<b>🔔 VIP Signals:</b>\n"
        f"Status: {'✅ Active' if has_vip_access else '🔒 Not Active'}\n"
        f"• Live trading alerts\n"
        f"• Entry/exit points\n"
        f"• Professional analysis\n\n"
        
        f"<b>🤖 VIP Automated Strategy:</b>\n"
        f"Status: {'✅ Active' if has_vip_access else '🔒 Not Active'}\n"
        f"• Fully automated trading\n"
        f"• 24/7 market monitoring\n"
        f"• Professional risk management\n\n"
        
        f"<b>💰 Access Requirements:</b>\n"
        f"• Minimum Balance: $100 ({'✅ Met' if real_time_balance >= 100 else '❌ Not Met'})\n"
        f"• Account Verified: {'✅ Yes' if is_verified else '❌ No'}\n\n"
    )
    
    if has_vip_access:
        services_text += f"<b>🎉 All services are active and ready!</b>\n\n"
        if vip_services_list:
            services_text += f"<b>Active Services:</b> {vip_services_list}\n"
    else:
        if not is_verified:
            services_text += "<b>⚠️ Complete account verification first.</b>"
        elif real_time_balance < 100:
            needed = 100 - real_time_balance
            services_text += f"<b>⚠️ Deposit ${needed:,.0f} more to activate VIP services.</b>"
        else:
            services_text += "<b>⚠️ VIP access pending - contact support.</b>"
    
    keyboard = []
    
    if has_vip_access:
        keyboard.append([
            InlineKeyboardButton("📊 Request Additional Service", callback_data="request_vip_both_services")
        ])
    else:
        if is_verified and real_time_balance >= 100:
            keyboard.append([
                InlineKeyboardButton("🚀 Request VIP Access", callback_data="request_vip_both_services")
            ])
        elif real_time_balance < 100:
            keyboard.append([
                InlineKeyboardButton("💳 Add Funds", callback_data="choose_deposit_amount")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🚀 Complete Setup", callback_data="complete_setup")
            ])
    
    keyboard.extend([
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="back_to_dashboard"),
            InlineKeyboardButton("💬 Get Help", callback_data="speak_advisor")
        ]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(services_text, parse_mode='HTML', reply_markup=reply_markup)

async def back_to_dashboard_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return user to their dashboard with fresh balance data."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = db.get_user(user_id)
    
    if user_info:
        # Show loading state
        await query.edit_message_text(
            "📊 <b>Refreshing Dashboard...</b>\n\n"
            "Fetching latest account data... ⏳",
            parse_mode='HTML'
        )
        
        # Small delay for UX
        await asyncio.sleep(1)
        
        await show_account_dashboard(update, context, user_info)
    else:
        await query.edit_message_text("❌ Unable to load dashboard. Please try /myaccount")

async def help_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive help menu."""
    query = update.callback_query
    await query.answer()
    
    help_text = (
        "<b>❓ VFX Trading Help Center</b>\n\n"
        
        "<b>🏠 Your Control Center:</b>\n"
        "<b>/myaccount</b> - Your personal dashboard 📊\n"
        "• View your complete profile\n"
        "• Edit your settings anytime\n"
        "• Check account status\n"
        "• Track VIP services\n"
        "• Contact support directly\n\n"
        
        "<b>🔧 Quick Actions:</b>\n"
        "• Refresh your balance anytime\n"
        "• Update your risk profile\n"
        "• Change deposit targets\n"
        "• Request VIP services\n\n"
        
        "<b>💰 About VIP Services:</b>\n"
        "• <b>Signals:</b> Get trading alerts on your phone 📱\n"
        "• <b>Automated:</b> Let our bots trade for you 🤖\n"
        "• Minimum $100 deposit required\n"
        "• No monthly fees - one-time verification\n\n"
        
        "<b>🔐 Account Security:</b>\n"
        "• Your account number cannot be changed\n"
        "• Contact support for sensitive changes\n"
        "• Always verify emails/messages from us\n\n"
        
        "<b>📞 Need Personal Help?</b>\n"
        "Our support team is available 24/7!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 Open My Dashboard", callback_data="back_to_dashboard")],
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
        [InlineKeyboardButton("📋 Explain Services", callback_data="explain_services")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_text, parse_mode='HTML', reply_markup=reply_markup)

async def edit_deposit_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow user to update their target deposit amount."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = db.get_user(user_id)
    current_amount = user_info.get('deposit_amount', 0) if user_info else 0
    
    deposit_text = (
        "<b>💰 Update Your Target Deposit</b>\n\n"
        f"<b>Current Target:</b> ${current_amount}\n\n"
        
        "<b>💡 Choose your preferred deposit amount:</b>\n\n"
        
        "<b>💳 Starter Package ($100-$500):</b>\n"
        "• Good for learning and testing\n"
        "• Access to all VIP features\n"
        "• Lower risk, steady growth\n\n"
        
        "<b>💰 Growth Package ($500-$2,000):</b>\n"
        "• Better profit potential\n"
        "• More trading opportunities\n"
        "• Recommended for most users\n\n"
        
        "<b>💎 Premium Package ($2,000+):</b>\n"
        "• Maximum profit potential\n"
        "• Priority support\n"
        "• Advanced strategies available\n\n"
        
        "<b>What's your target?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("💳 $100", callback_data="update_deposit_100"),
            InlineKeyboardButton("💳 $250", callback_data="update_deposit_250"),
            InlineKeyboardButton("💳 $500", callback_data="update_deposit_500")
        ],
        [
            InlineKeyboardButton("💰 $1,000", callback_data="update_deposit_1000"),
            InlineKeyboardButton("💰 $2,000", callback_data="update_deposit_2000"),
            InlineKeyboardButton("💎 $5,000", callback_data="update_deposit_5000")
        ],
        [
            InlineKeyboardButton("✏️ Custom Amount", callback_data="custom_deposit_edit"),
            InlineKeyboardButton("🔙 Back", callback_data="edit_profile_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(deposit_text, parse_mode='HTML', reply_markup=reply_markup)

async def edit_trading_interest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow user to update their trading interest."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_info = db.get_user(user_id)
    current_interest = user_info.get('trading_interest', 'Not specified') if user_info else 'Not specified'
    
    interest_text = (
        "<b>📈 Update Your Trading Interest</b>\n\n"
        f"<b>Current Selection:</b> {current_interest}\n\n"
        
        "<b>🔔 VIP Signals Service:</b>\n"
        "• Live trading alerts sent to your phone 📱\n"
        "• Entry points, stop losses, take profits\n"
        "• 75%+ win rate with expert analysis\n"
        "• Perfect for active traders who want guidance\n\n"
        
        "<b>🤖 VIP Automated Strategy:</b>\n"
        "• Fully automated trading on your account\n"
        "• Our algorithms trade for you 24/7\n"
        "• No manual work required - set and forget\n"
        "• Perfect for passive income generation\n\n"
        
        "<b>✨ Both Services (Recommended):</b>\n"
        "• Get the best of both worlds\n"
        "• Learn from signals while earning passively\n"
        "• Maximum profit potential\n"
        "• Most popular choice among our users\n\n"
        
        "<b>What interests you most?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🔔 VIP Signals", callback_data="update_interest_signals"),
            InlineKeyboardButton("🤖 Automated Strategy", callback_data="update_interest_strategy")
        ],
        [
            InlineKeyboardButton("✨ Both Services", callback_data="update_interest_all")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="edit_profile_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(interest_text, parse_mode='HTML', reply_markup=reply_markup)

async def update_deposit_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process deposit amount update."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Extract amount from callback data
    amount_str = callback_data.split("_")[-1]
    try:
        amount = int(amount_str)
    except ValueError:
        amount = 100
    
    # Update database
    db.add_user({
        "user_id": user_id,
        "deposit_amount": amount,
        "profile_updated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Determine package type for display
    if amount <= 500:
        package = "💳 Starter Package"
        benefits = "Access to all VIP features with steady growth potential"
    elif amount <= 2000:
        package = "💰 Growth Package"
        benefits = "Enhanced profit potential with more trading opportunities"
    else:
        package = "💎 Premium Package"
        benefits = "Maximum profit potential with priority support"
    
    await query.edit_message_text(
        f"<b>✅ Target Deposit Updated!</b>\n\n"
        f"<b>New Target:</b> ${amount:,}\n"
        f"<b>Package:</b> {package}\n"
        f"<b>Benefits:</b> {benefits}\n\n"
        f"<i>💡 You can access your dashboard anytime with /myaccount</i>\n\n"
        f"<i>Returning to your dashboard...</i>",
        parse_mode='HTML'
    )
    
    # Auto-return to dashboard after 2 seconds
    import asyncio
    await asyncio.sleep(2)
    
    user_info = db.get_user(user_id)
    await show_account_dashboard(update, context, user_info)

async def update_trading_interest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process trading interest update."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    callback_data = query.data
    
    # Extract interest from callback data
    if "signals" in callback_data:
        interest = "signals"
        display_name = "🔔 VIP Signals"
        description = "You'll receive live trading alerts and professional analysis"
    elif "strategy" in callback_data:
        interest = "strategy"
        display_name = "🤖 Automated Strategy"
        description = "Our algorithms will trade automatically on your account"
    elif "all" in callback_data:
        interest = "all"
        display_name = "✨ Both Services"
        description = "You'll get signals AND automated trading for maximum results"
    
    # Update database
    db.add_user({
        "user_id": user_id,
        "trading_interest": interest,
        "profile_updated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await query.edit_message_text(
        f"<b>✅ Trading Interest Updated!</b>\n\n"
        f"<b>Your Choice:</b> {display_name}\n"
        f"<b>What This Means:</b> {description}\n\n"
        f"<i>💡 Tip: You can always view your full profile with /myaccount</i>\n\n"
        f"<i>Returning to your dashboard...</i>",
        parse_mode='HTML'
    )
    
    # Auto-return to dashboard after 2 seconds
    import asyncio
    await asyncio.sleep(2)
    
    user_info = db.get_user(user_id)
    await show_account_dashboard(update, context, user_info)

async def custom_deposit_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle custom deposit amount entry."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "<b>✏️ Enter Custom Deposit Amount</b>\n\n"
        "Please type your desired deposit amount:\n\n"
        "<b>💡 Examples:</b>\n"
        "• Type: 750\n"
        "• Type: 1500\n"
        "• Type: 3000\n\n"
        "<b>📝 Just type the number (minimum $100):</b>",
        parse_mode='HTML'
    )
    
    # Set state for custom deposit editing
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "editing_custom_deposit"



# -------------------------------------- Admin Management Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

async def list_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List recent users for the admin to contact."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Get recent users
    recent_users = db.users_df.sort("last_active", descending=True).head(10)
    
    if recent_users.height == 0:
        await update.message.reply_text("No users found in the database.")
        return
    
    # Format the user list with buttons
    message = "Recent users:\n\n"
    keyboard = []
    
    for i in range(recent_users.height):
        user_id = recent_users["user_id"][i]
        username = recent_users["username"][i] if recent_users["username"][i] else "No username"
        first_name = recent_users["first_name"][i] if recent_users["first_name"][i] else "Unknown"
        last_active = recent_users["last_active"][i]
        
        message += f"{i+1}. {first_name} (@{username}) - Last active: {last_active}\n"
        keyboard.append([InlineKeyboardButton(f"Message {first_name}", callback_data=f"start_conv_{user_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup)

async def end_user_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End the current user conversation."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if "current_user_conv" in context.user_data:
        user_id = context.user_data["current_user_conv"]
        del context.user_data["current_user_conv"]
        
        await update.message.reply_text(f"Conversation with user {user_id} ended.")
    else:
        await update.message.reply_text("You're not currently in a conversation with any user.")

async def handle_admin_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages forwarded by the admin from users - FIXED VERSION."""
    # Debug output
    print(f"Received message in chat {update.effective_chat.id} from user {update.effective_user.id}")
    
    # Check if this is the admin's chat
    if update.effective_user.id not in ADMIN_USER_ID:
        print("Not from admin, skipping admin forward handler")
        return
    
    # CRITICAL FIX: Check if this is a forwarded message FIRST
    is_forwarded = False
    original_sender_id = None
    original_sender_name = "Unknown User"
    forwarded_from_channel = None
    
    # Method 1: Check for forward_origin 
    if hasattr(update.message, 'forward_origin'):
        print("Message has forward_origin property")
        is_forwarded = True
        
        if hasattr(update.message.forward_origin, 'sender_user') and update.message.forward_origin.sender_user:
            original_sender_id = update.message.forward_origin.sender_user.id
            original_sender_name = update.message.forward_origin.sender_user.first_name
            print(f"Sender from forward_origin: {original_sender_id} ({original_sender_name})")
        elif hasattr(update.message.forward_origin, 'sender_user_name'):
            original_sender_name = update.message.forward_origin.sender_user_name
            print(f"Hidden sender from forward_origin: {original_sender_name}")
    
    # Method 2: Check for forward_from (older Telegram API)
    elif hasattr(update.message, 'forward_from') and update.message.forward_from:
        print("Message has forward_from property")
        is_forwarded = True
        original_sender_id = update.message.forward_from.id
        original_sender_name = update.message.forward_from.first_name
        print(f"Sender from forward_from: {original_sender_id} ({original_sender_name})")
    
    # Method 3: Check for forward_sender_name (for privacy-enabled users)
    elif hasattr(update.message, 'forward_sender_name') and update.message.forward_sender_name:
        print("Message has forward_sender_name property")
        is_forwarded = True
        original_sender_name = update.message.forward_sender_name
        print(f"Hidden sender from forward_sender_name: {original_sender_name}")
    
    # IF THIS IS A FORWARDED MESSAGE - Handle the forwarded message workflow
    if is_forwarded:
        print(f"Processing forwarded message from {original_sender_name}")
        
        message_text = update.message.text if update.message.text else ""
        
        # Try to determine source channel
        if hasattr(update.message, 'forward_from_chat') and update.message.forward_from_chat:
            forward_chat_id = str(update.message.forward_from_chat.id)
            if forward_chat_id == MAIN_CHANNEL_ID:
                forwarded_from_channel = "main_channel"
                print(f"Message identified as forwarded from main channel")
            elif forward_chat_id == SIGNALS_CHANNEL_ID:
                forwarded_from_channel = "signals_channel"
                print(f"Message identified as forwarded from signals channel")
        else:
            # Try to infer source from content
            if any(keyword in message_text.lower() for keyword in ["signal", "trade", "buy", "sell", "entry", "exit", "tp", "sl"]):
                forwarded_from_channel = "signals_channel"
                print(f"Message content suggests it's from signals channel")
            else:
                forwarded_from_channel = "main_channel"
                print(f"Defaulting to main channel as source")
        
        # Handle user with visible info
        if original_sender_id:
            print(f"Processing forwarded message from user with ID: {original_sender_id}")
            
            # Store original sender ID for future communication with source channel info
            user_data = {
                "user_id": original_sender_id,
                "first_name": original_sender_name,
                "last_name": "",
                "username": "",
                "source_channel": forwarded_from_channel,
                "first_contact_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            db.add_user(user_data)
            
            # AUTOMATICALLY SEND WELCOME MESSAGE TO USER
            try:
                # Get the appropriate welcome message based on source channel
                if forwarded_from_channel == "signals_channel":
                    welcome_msg = db.get_setting("signals_auto_welcome", 
                                               config.get("messages.signals_auto_welcome", 
                                                        db.get_setting("admin_auto_welcome", 
                                                                     "Welcome to VFX Trading Signals!")))
                else:
                    welcome_msg = db.get_setting("admin_auto_welcome", 
                                               config.get("messages.admin_auto_welcome", 
                                                        "Welcome to VFX Trading!"))
                
                # Create buttons for welcome message
                keyboard = [
                    [InlineKeyboardButton("🚀 Start Guided Setup", callback_data="start_guided")],
                    [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                try:
                    # Send the welcome message directly to the user
                    await context.bot.send_message(
                        chat_id=original_sender_id,
                        text=welcome_msg,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    
                    # Mark this user as having received the auto-welcome
                    db.add_user({
                        "user_id": original_sender_id,
                        "auto_welcomed": True,
                        "auto_welcome_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    # Notify admin that automated welcome was sent
                    source_text = "signals channel" if forwarded_from_channel == "signals_channel" else "main channel"
                    await update.message.reply_text(
                        f"✅ Automated welcome message sent to {original_sender_name} (ID: {original_sender_id}).\n\n"
                        f"User identified as coming from the {source_text}.\n\n"
                        f"The message includes questions about their risk profile, capital, and account number.\n\n"
                        f"Their responses will be tracked in the database."
                    )
                    
                except Exception as e:
                    print(f"Error sending automated welcome: {e}")
                    
                    # Check if it's a privacy restriction error
                    if "Forbidden: bot can't initiate conversation with a user" in str(e):
                        # Create "start bot" deep link
                        bot_username = await context.bot.get_me()
                        bot_username = bot_username.username
                        start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
                        
                        # Create keyboard with copy buttons
                        keyboard = [
                            [InlineKeyboardButton("🔗 Generate Welcome Link", callback_data=f"gen_welcome_{original_sender_id}")],
                            [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{original_sender_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            f"⚠️ Cannot message {original_sender_name} directly due to Telegram privacy settings.\n\n"
                            f"This means the user has not started a conversation with the bot yet.\n\n"
                            f"<b>💡 You can still try to connect manually:</b>\n"
                            f"Click 'Generate Welcome Link' to create a personalized message for this user.\n\n"
                            f"<b>Alternative:</b> Ask the user to click this link first:\n"
                            f"`{start_link}`",
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    else:
                        # Other error
                        await update.message.reply_text(
                            f"⚠️ Failed to send automated welcome to {original_sender_name}: {e}\n\n"
                            f"Would you like to start a conversation manually?"
                        )
                
                # Store this user in admin's active conversations with source info
                context.bot_data.setdefault("auto_welcoming_users", {})
                context.bot_data["auto_welcoming_users"][original_sender_id] = {
                    "name": original_sender_name,
                    "status": "awaiting_response",
                    "welcome_sent": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source_channel": forwarded_from_channel
                }
                
            except Exception as e:
                print(f"Error sending automated welcome: {e}")
                await update.message.reply_text(
                    f"⚠️ Failed to send automated welcome to {original_sender_name}: {e}\n\n"
                    f"Would you like to start a conversation manually?"
                )
            
            # Ask admin if they want to start conversation (keep this as a backup)
            keyboard = [
                [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{original_sender_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📨 Message forwarded from {original_sender_name} (ID: {original_sender_id}).\n"
                f"Automated welcome message has been sent.\n\n"
                f"<b>💡 To start direct conversation:</b>\n"
                f"Click 'View User Profile' → 'Start Conversation'",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        else:
            # Handle privacy-protected users (no sender ID available)
            print(f"Privacy-protected user detected: {original_sender_name}")
            
            # Create buttons for privacy-protected user handling
            keyboard = [
                [InlineKeyboardButton("🔗 Generate Welcome Link", callback_data=f"gen_welcome_privacy")],
                [InlineKeyboardButton("📋 View Instructions", callback_data=f"show_privacy_instructions")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"⚠️ <b>Privacy-Protected User: {original_sender_name}</b>\n\n"
                f"This user has privacy settings enabled, so I cannot message them directly.\n\n"
                f"<b>Source:</b> {forwarded_from_channel.replace('_', ' ').title()}\n"
                f"<b>Message:</b> \"{message_text[:100]}...\"\n\n"
                f"Choose an option to help them connect:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            # Store the user info for the welcome link generation
            context.user_data["privacy_user_name"] = original_sender_name
            context.user_data["privacy_user_source"] = forwarded_from_channel
        
        # IMPORTANT: Return here to prevent further processing
        return
    
    # IF THIS IS NOT A FORWARDED MESSAGE - Check if admin is in active conversation
    if "current_user_conv" in context.user_data:
        user_id = context.user_data["current_user_conv"]
        print(f"Admin is in conversation with user {user_id}, forwarding message")
        
        # Try to get user info for better error handling
        user_info = db.get_user(user_id)
        user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
        
        # Forward the admin's reply to that user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=update.message.text,  # Send the raw message without "Admin:" prefix
                parse_mode="HTML"
            )
            await update.message.reply_text(
                f"✅ <b>Message delivered to {user_name}</b>\n\n"
                f"📱 Your message: \"{update.message.text[:50]}...\"\n"
                f"👤 Sent to: {user_name} (ID: {user_id})",
                parse_mode='HTML'
            )
            print(f"Successfully forwarded message to user {user_id}")
            return
            
        except Exception as e:
            print(f"Error sending message to user {user_id}: {e}")
            
            # Enhanced error handling based on error type
            if "Forbidden: bot can't initiate conversation with a user" in str(e):
                # User hasn't started the bot yet
                bot_info = await context.bot.get_me()
                bot_username = bot_info.username
                start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
                
                # Check if user has username for direct messaging
                username = user_info.get('username') if user_info else None
                
                keyboard = [
                    [InlineKeyboardButton("🔗 Generate Connection Link", callback_data=f"gen_connect_link_{user_id}")],
                    [InlineKeyboardButton("📞 Get User Contact Info", callback_data=f"get_contact_info_{user_id}")],
                    [InlineKeyboardButton("❌ End This Conversation", callback_data=f"end_conv_{user_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                error_message = (
                    f"🚫 <b>Cannot Deliver Message to {user_name}</b>\n\n"
                    f"<b>📱 Your message:</b> \"{update.message.text[:100]}...\"\n\n"
                    f"<b>⚠️ Issue:</b> {user_name} hasn't started a conversation with the bot yet.\n\n"
                    f"<b>💡 Solutions:</b>\n\n"
                )
                
                if username:
                    error_message += (
                        f"<b>🎯 Best Option:</b> Message @{username} directly\n"
                        f"• Click their username to open chat\n"
                        f"• Send your message directly\n"
                        f"• Much faster than using the bot\n\n"
                        f"<b>🔗 Alternative:</b> Send them a bot connection link\n"
                        f"• Click 'Generate Connection Link' below\n"
                        f"• Copy and paste the message to @{username}\n\n"
                    )
                else:
                    error_message += (
                        f"<b>🔗 Send Connection Link:</b>\n"
                        f"• Click 'Generate Connection Link' below\n"
                        f"• Copy the generated message\n"
                        f"• Find {user_name} in your chats and paste it\n\n"
                    )
                
                error_message += f"<b>⚙️ Quick Connect Link:</b>\n`{start_link}`"
                
                await update.message.reply_text(
                    error_message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                
            elif "Forbidden: user is deactivated" in str(e):
                await update.message.reply_text(
                    f"🚫 <b>User Account Deactivated</b>\n\n"
                    f"👤 {user_name} (ID: {user_id})\n"
                    f"⚠️ This user's Telegram account has been deactivated.\n\n"
                    f"🔄 Use /endchat to end this conversation.",
                    parse_mode='HTML'
                )
                
            elif "Forbidden: bot was blocked by the user" in str(e):
                await update.message.reply_text(
                    f"🚫 <b>Bot Blocked by User</b>\n\n"
                    f"👤 {user_name} (ID: {user_id})\n"
                    f"⚠️ This user has blocked the bot.\n\n"
                    f"💡 You'll need to contact them through other means.\n"
                    f"🔄 Use /endchat to end this conversation.",
                    parse_mode='HTML'
                )
                
            else:
                # Generic error
                await update.message.reply_text(
                    f"❌ <b>Delivery Failed</b>\n\n"
                    f"👤 {user_name} (ID: {user_id})\n"
                    f"⚠️ Error: {str(e)[:100]}\n\n"
                    f"🔄 Use /endchat to end this conversation.",
                    parse_mode='HTML'
                )
            return
    
    # If it's NOT a forwarded message AND admin is not in active conversation
    print("This is a regular message from admin, but no active conversation")
    await update.message.reply_text(
        "💬 <b>No Active Conversation</b>\n\n"
        "You're not currently in a conversation with any user.\n\n"
        "<b>To start a conversation:</b>\n"
        "• Forward a message from a user, OR\n"
        "• Use /users to see recent users and click 'Message User'\n\n"
        "<b>💡 Tip:</b> When you start a conversation, any regular message you send will be forwarded to that user.",
        parse_mode='HTML'
    )

async def start_user_conversation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """FIXED: Show clickable username to admin for direct conversation."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("start_conv_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Admin starting conversation with user ID: {user_id}")
            
            # Store the current conversation user for admin
            context.user_data["current_user_conv"] = user_id
            
            # Get user info from multiple sources
            user_info = db.get_user(user_id)
            if not user_info:
                # Try to get from auto_welcoming_users if not in main DB
                auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
                if user_id in auto_welcoming_users:
                    user_name = auto_welcoming_users[user_id].get("name", "User")
                    username = None  # Auto-welcoming users don't have username
                else:
                    user_name = "User"
                    username = None
            else:
                user_name = user_info.get("first_name", "User")
                username = user_info.get("username")
            
            # Try to get user info directly from Telegram if we don't have username
            telegram_username = None
            try:
                # Get user info from Telegram
                chat_member = await context.bot.get_chat_member(user_id, user_id)
                if chat_member.user.username:
                    telegram_username = chat_member.user.username
            except:
                pass
            
            # Use the best available username
            final_username = username or telegram_username
            
            # Try to send a direct message to the user FIRST
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"<b>👋 Hello {user_name}!</b>\n\n"
                        f"One of our advisors is now available to help you.\n\n"
                        f"<b>💬 You can now chat directly with our team!</b>\n"
                        f"Feel free to ask any questions about your account or our services. ✅"
                    ),
                    parse_mode='HTML'
                )
                
                # SUCCESS - Show admin the clickable username or user info
                if final_username:
                    admin_message = (
                        f"<b>✅ Connected Successfully!</b>\n\n"
                        f"<b>👤 User:</b> {user_name} (@{final_username})\n"
                        f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
                        f"<b>💬 Status:</b> Direct conversation started\n"
                        f"<b>🕒 Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"<b>🎯 Click on @{final_username} above to start chatting!</b>\n\n"
                        f"<b>Alternative:</b> Any message you send to me will be forwarded to them.\n\n"
                        f"Use /endchat to end this conversation when finished."
                    )
                else:
                    admin_message = (
                        f"<b>✅ Connected Successfully!</b>\n\n"
                        f"<b>👤 User:</b> {user_name}\n"
                        f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
                        f"<b>💬 Status:</b> Direct conversation started\n"
                        f"<b>🕒 Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"<b>⚠️ Note:</b> User has no public username\n"
                        f"<b>🎯 Any message you send to me will be forwarded to {user_name}</b>\n\n"
                        f"Use /endchat to end this conversation when finished."
                    )
                
                await query.edit_message_text(
                    admin_message,
                    parse_mode='HTML'
                )
                
                print(f"Successfully connected admin to user {user_id}")
                
            except Exception as e:
                print(f"Error sending message to user: {e}")
                
                # Check if it's the "can't initiate conversation" error
                if "can't initiate conversation with a user" in str(e):
                    # User hasn't started bot yet - provide link and username if available
                    bot_info = await context.bot.get_me()
                    bot_username = bot_info.username
                    start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
                    
                    if final_username:
                        error_message = (
                            f"<b>⚠️ Cannot Message User Directly</b>\n\n"
                            f"<b>👤 User:</b> {user_name} (@{final_username})\n"
                            f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
                            f"<b>Issue:</b> User hasn't started the bot yet\n\n"
                            f"<b>✅ Two Options:</b>\n\n"
                            f"<b>1. Direct Message:</b> Click @{final_username} above\n\n"
                            f"<b>2. Bot Connection:</b> Send them this link:\n"
                            f"<code>{start_link}</code>\n\n"
                            f"<b>🎯 Direct messaging is usually faster!</b>"
                        )
                    else:
                        error_message = (
                            f"<b>⚠️ Cannot Message User Directly</b>\n\n"
                            f"<b>👤 User:</b> {user_name}\n"
                            f"<b>🆔 User ID:</b> <code>{user_id}</code>\n"
                            f"<b>Issue:</b> User hasn't started the bot yet\n\n"
                            f"<b>✅ Solution:</b> Send them this link:\n"
                            f"<code>{start_link}</code>\n\n"
                            f"<b>📋 Instructions for user:</b>\n"
                            f"1. Click the link above\n"
                            f"2. Press START in the bot\n"
                            f"3. You'll be connected automatically"
                        )
                    
                    await query.edit_message_text(
                        error_message,
                        parse_mode='HTML'
                    )
                else:
                    # Other error
                    await query.edit_message_text(
                        f"<b>⚠️ Connection Issue</b>\n\n"
                        f"<b>User:</b> {user_name}\n"
                        f"<b>Error:</b> {str(e)[:100]}\n\n"
                        f"<b>💡 Try contacting them through the group/channel</b>",
                        parse_mode='HTML'
                    )
                
        except Exception as e:
            print(f"Error processing start conversation callback: {e}")
            await query.edit_message_text(
                f"<b>⚠️ Error Processing Request</b>\n\n{str(e)[:200]}",
                parse_mode='HTML'
            )

async def handle_referral(context, user, ref_code):
    """Handle referral codes separately to avoid message leakage."""
    try:
        # Extract the referring admin's ID
        referring_admin_id = int(ref_code.split("_")[1])
        print(f"User {user.id} was referred by admin {referring_admin_id}")
        
        # Store this connection in the database or context
        context.bot_data.setdefault("admin_user_connections", {})
        context.bot_data["admin_user_connections"][user.id] = referring_admin_id
        
        # Notify ONLY the admin
        try:
            await context.bot.send_message(
                chat_id=referring_admin_id,
                text=f"✅ {user.first_name} (ID: {user.id}) has connected with the bot through your link! You can now communicate with them."
            )
            print(f"Sent connection notification to admin {referring_admin_id}")
        except Exception as e:
            print(f"Failed to send admin notification: {e}")
    except Exception as e:
        print(f"Error processing referral: {e}")

async def generate_connection_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a connection link for users who haven't started the bot."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[3])  # gen_connect_link_{user_id}
    
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
    
    # Create connection link
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    start_link = f"https://t.me/{bot_username}?start=ref_{query.from_user.id}"
    
    # Generate connection message
    connection_message = (
        f"Hi {user_name}! 👋\n\n"
        f"I received your message and I'm ready to help you with VFX Trading!\n\n"
        f"To continue our conversation through our secure system, please click this link:\n\n"
        f"👉 {start_link}\n\n"
        f"This will connect you to our automated assistant where we can discuss your trading needs in detail.\n\n"
        f"Looking forward to helping you! 🚀"
    )
    
    await query.edit_message_text(
        f"🔗 <b>Connection Link Generated for {user_name}</b>\n\n"
        f"📋 <b>Send this message to the user:</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{connection_message}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 After they click the link and start the bot, you'll be able to message them directly through this system.",
        parse_mode='HTML'
    )

async def get_contact_info_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show contact information for the user."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[3])  # get_contact_info_{user_id}
    
    user_info = db.get_user(user_id)
    
    if user_info:
        contact_info = (
            f"👤 <b>Contact Information</b>\n\n"
            f"<b>Name:</b> {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"<b>Username:</b> @{user_info.get('username', 'Not available')}\n"
            f"<b>User ID:</b> <code>{user_id}</code>\n"
            f"<b>Source:</b> {user_info.get('source_channel', 'Unknown')}\n"
            f"<b>First Contact:</b> {user_info.get('first_contact_date', 'Unknown')}\n\n"
        )
        
        if user_info.get('username'):
            contact_info += f"💡 <b>Best option:</b> Message @{user_info.get('username')} directly"
        else:
            contact_info += f"⚠️ No public username available. Use the connection link method."
    else:
        contact_info = f"❌ No contact information available for user {user_id}"
    
    await query.edit_message_text(contact_info, parse_mode='HTML')

async def end_conversation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """End the current conversation."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[2])  # end_conv_{user_id}
    
    # End the conversation
    if "current_user_conv" in context.user_data:
        del context.user_data["current_user_conv"]
    
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
    
    await query.edit_message_text(
        f"✅ <b>Conversation Ended</b>\n\n"
        f"Conversation with {user_name} (ID: {user_id}) has been ended.\n\n"
        f"💡 You can start a new conversation by forwarding a message from another user or using /users.",
        parse_mode='HTML'
    )

async def admin_dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Main admin dashboard - central hub for all admin functions."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Get quick stats
    total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
    verified_users = db.users_df.filter(pl.col("is_verified") == True).height if total_users > 0 else 0
    vip_users = db.users_df.filter(pl.col("vip_access_granted") == True).height if total_users > 0 else 0
    active_users_7d = db.get_active_users(days=7)
    
    dashboard_message = (
        f"🎛️ <b>VFX Trading Admin Dashboard</b>\n\n"
        f"<b>📊 Quick Stats:</b>\n"
        f"• Total Users: {total_users:,}\n"
        f"• Verified: {verified_users:,}\n"
        f"• VIP Members: {vip_users:,}\n"
        f"• Active (7d): {active_users_7d:,}\n\n"
        f"<b>🚀 What would you like to do?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👥 Manage Users", callback_data="admin_users_menu"),
            InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats_menu")
        ],
        [
            InlineKeyboardButton("🌟 VIP Management", callback_data="admin_vip_menu"),
            InlineKeyboardButton("🔄 Copier Management", callback_data="admin_copier_menu")
        ],
        [
            InlineKeyboardButton("🔍 Search Users", callback_data="admin_search_menu"),
            InlineKeyboardButton("⚙️ System Settings", callback_data="admin_settings_menu")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(dashboard_message, parse_mode='HTML', reply_markup=reply_markup)

async def enhanced_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced user management with filters and bulk actions."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Show user browser with filter options
    await show_user_browser(update, context, filter_type="recent")

async def show_user_browser(update, context, filter_type="recent", page=0, is_callback=False):
    """Display paginated user browser with filters and actions."""
    users_per_page = 5
    
    # Apply filters
    if filter_type == "recent":
        filtered_users = db.users_df.sort("last_active", descending=True).head(50)
        title = "📅 Recent Users"
    elif filter_type == "verified":
        filtered_users = db.users_df.filter(pl.col("is_verified") == True).sort("last_active", descending=True)
        title = "✅ Verified Users"
    elif filter_type == "vip":
        filtered_users = db.users_df.filter(pl.col("vip_access_granted") == True).sort("vip_granted_date", descending=True)
        title = "🌟 VIP Users"
    elif filter_type == "unverified":
        filtered_users = db.users_df.filter(pl.col("is_verified") == False).sort("join_date", descending=True)
        title = "⏳ Unverified Users"
    elif filter_type == "high_balance":
        filtered_users = db.users_df.filter(pl.col("account_balance") >= 100).sort("account_balance", descending=True)
        title = "💰 High Balance Users"
    else:
        filtered_users = db.users_df.sort("last_active", descending=True)
        title = "👥 All Users"
    
    total_filtered = filtered_users.height if hasattr(filtered_users, 'height') else 0
    
    if total_filtered == 0:
        message = f"{title}\n\n❌ No users found matching this filter."
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Filters", callback_data="admin_users_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_callback:
            await update.callback_query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        else:
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        return
    
    # Pagination
    start_idx = page * users_per_page
    end_idx = min(start_idx + users_per_page, total_filtered)
    page_users = filtered_users.slice(start_idx, users_per_page)
    
    # Build message
    message = f"{title} ({total_filtered:,} total)\n\n"
    message += f"<b>Page {page + 1} of {(total_filtered - 1) // users_per_page + 1}</b>\n\n"
    
    # User list with quick info
    for i in range(page_users.height):
        user_id = page_users["user_id"][i]
        first_name = page_users["first_name"][i] or "Unknown"
        last_name = page_users["last_name"][i] or ""
        username = page_users["username"][i] or "None"
        is_verified = page_users["is_verified"][i] if page_users["is_verified"][i] is not None else False
        vip_access = page_users["vip_access_granted"][i] if page_users["vip_access_granted"][i] is not None else False
        balance = page_users["account_balance"][i] if page_users["account_balance"][i] is not None else 0
        
        # Status indicators
        verify_emoji = "✅" if is_verified else "⏳"
        vip_emoji = "🌟" if vip_access else "🔒"
        balance_emoji = "💰" if balance >= 100 else "💳" if balance > 0 else "💸"
        
        message += f"{i + 1}. <b>{first_name} {last_name}</b> {verify_emoji}{vip_emoji}{balance_emoji}\n"
        message += f"   @{username} • ID: {user_id}\n"
        if balance > 0:
            message += f"   Balance: ${balance:,.2f}\n"
        message += "\n"
    
    # Build keyboard
    keyboard = []
    
    # User action buttons (one row per user)
    for i in range(page_users.height):
        user_id = page_users["user_id"][i]
        first_name = page_users["first_name"][i] or "User"
        keyboard.append([
            InlineKeyboardButton(f"👤 {first_name}", callback_data=f"admin_user_profile_{user_id}"),
            InlineKeyboardButton("💬", callback_data=f"admin_start_conv_{user_id}"),
            InlineKeyboardButton("🔗", callback_data=f"admin_gen_link_{user_id}"),
            InlineKeyboardButton("🌟", callback_data=f"admin_quick_vip_{user_id}")
        ])
    
    # Pagination controls
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"admin_users_page_{filter_type}_{page-1}"))
    if end_idx < total_filtered:
        nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin_users_page_{filter_type}_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    # Filter and action buttons
    keyboard.extend([
        [
            InlineKeyboardButton("🔍 Change Filter", callback_data="admin_users_menu"),
            InlineKeyboardButton("🔄 Refresh", callback_data=f"admin_users_refresh_{filter_type}_{page}")
        ],
        [
            InlineKeyboardButton("📊 Bulk Actions", callback_data=f"admin_bulk_menu_{filter_type}"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if is_callback:
        await update.callback_query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)

async def admin_user_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show comprehensive user profile with all available actions."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[3])  # admin_user_profile_{user_id}
    
    await show_comprehensive_user_profile(query, context, user_id)

async def show_comprehensive_user_profile(query, context, user_id):
    """Display a comprehensive user profile with all admin actions."""
    user_info = db.get_user(user_id)
    
    if not user_info:
        await query.edit_message_text(
            f"❌ <b>User Not Found</b>\n\nUser ID {user_id} not found in database.",
            parse_mode='HTML'
        )
        return
    
    # Get real-time balance if possible
    real_time_balance = user_info.get('account_balance', 0) or 0
    trading_account = user_info.get('trading_account')
    
    if trading_account:
        try:
            mysql_db = get_mysql_connection()
            if mysql_db and mysql_db.is_connected():
                account_info = mysql_db.verify_account_exists(trading_account)
                if account_info['exists']:
                    real_time_balance = float(account_info.get('balance', 0))
        except Exception as e:
            print(f"Error getting real-time balance: {e}")
    
    # Build comprehensive profile
    first_name = user_info.get('first_name', 'Unknown')
    last_name = user_info.get('last_name', '')
    username = user_info.get('username', 'None')
    is_verified = user_info.get('is_verified', False)
    vip_access = user_info.get('vip_access_granted', False)
    risk_appetite = user_info.get('risk_appetite', 0)
    deposit_amount = user_info.get('deposit_amount', 0)
    trading_interest = user_info.get('trading_interest', 'Not specified')
    source_channel = user_info.get('source_channel', 'Unknown')
    join_date = user_info.get('join_date', 'Unknown')
    last_active = user_info.get('last_active', 'Unknown')
    
    # Status indicators and recommendations
    verify_status = "✅ Verified" if is_verified else "⏳ Pending"
    vip_status = "🌟 Active" if vip_access else "🔒 Not Active"
    balance_status = f"💰 ${real_time_balance:,.2f}"
    
    # Smart recommendations
    recommendations = []
    if not is_verified and trading_account:
        recommendations.append("⚡ Account verification needed")
    if is_verified and real_time_balance >= 100 and not vip_access:
        recommendations.append("🎯 Ready for VIP access")
    if real_time_balance > 0 and not trading_account:
        recommendations.append("🔗 Connect trading account")
    if vip_access and real_time_balance >= 500:
        recommendations.append("🚀 Consider copier team")
    
    profile_message = (
        f"👤 <b>User Profile: {first_name} {last_name}</b>\n\n"
        f"<b>📋 Basic Info:</b>\n"
        f"• Username: @{username}\n"
        f"• User ID: <code>{user_id}</code>\n"
        f"• Source: {source_channel.replace('_', ' ').title()}\n"
        f"• Joined: {join_date[:10] if join_date != 'Unknown' else 'Unknown'}\n"
        f"• Last Active: {last_active[:10] if last_active != 'Unknown' else 'Unknown'}\n\n"
        
        f"<b>📊 Account Status:</b>\n"
        f"• Verification: {verify_status}\n"
        f"• VIP Access: {vip_status}\n"
        f"• Balance: {balance_status}\n"
        f"• Trading Account: {trading_account or 'Not provided'}\n\n"
        
        f"<b>🎯 Profile Data:</b>\n"
        f"• Risk Level: {risk_appetite}/10\n"
        f"• Target Deposit: ${deposit_amount:,}\n"
        f"• Interest: {trading_interest}\n\n"
    )
    
    if recommendations:
        profile_message += f"<b>💡 Recommendations:</b>\n"
        for rec in recommendations:
            profile_message += f"• {rec}\n"
        profile_message += "\n"
    
    profile_message += f"<b>🔧 What would you like to do?</b>"
    
    # Build comprehensive action keyboard
    keyboard = []
    
    # Communication actions
    keyboard.append([
        InlineKeyboardButton("💬 Start Chat", callback_data=f"admin_start_conv_{user_id}"),
        InlineKeyboardButton("🔗 Send Link", callback_data=f"admin_gen_link_{user_id}")
    ])
    
    # Account management
    if not is_verified and trading_account:
        keyboard.append([
            InlineKeyboardButton("✅ Verify Account", callback_data=f"admin_verify_{user_id}"),
            InlineKeyboardButton("🔄 Check Balance", callback_data=f"admin_check_balance_{user_id}")
        ])
    elif is_verified:
        keyboard.append([
            InlineKeyboardButton("🔄 Refresh Balance", callback_data=f"admin_check_balance_{user_id}"),
            InlineKeyboardButton("📊 Account Details", callback_data=f"admin_account_details_{user_id}")
        ])
    
    # VIP management
    if real_time_balance >= 100 and not vip_access:
        keyboard.append([
            InlineKeyboardButton("🌟 Grant VIP Signals", callback_data=f"admin_grant_vip_signals_{user_id}"),
            InlineKeyboardButton("🤖 Grant VIP Strategy", callback_data=f"admin_grant_vip_strategy_{user_id}")
        ])
        keyboard.append([
            InlineKeyboardButton("✨ Grant Both VIP Services", callback_data=f"admin_grant_vip_all_{user_id}")
        ])
    elif vip_access:
        keyboard.append([
            InlineKeyboardButton("🌟 Manage VIP", callback_data=f"admin_manage_vip_{user_id}"),
            InlineKeyboardButton("🔄 Forward to Copier", callback_data=f"admin_forward_copier_{user_id}")
        ])
    
    # Profile management
    keyboard.append([
        InlineKeyboardButton("✏️ Edit Profile", callback_data=f"admin_edit_profile_{user_id}"),
        InlineKeyboardButton("🔄 Reset User", callback_data=f"admin_reset_user_{user_id}")
    ])
    
    # Navigation
    keyboard.append([
        InlineKeyboardButton("🔙 Back to Users", callback_data="admin_users_menu"),
        InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(profile_message, parse_mode='HTML', reply_markup=reply_markup)

async def admin_dashboard_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all admin dashboard callbacks."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "refresh_dashboard":
        await refresh_admin_dashboard(query, context)
        
    elif callback_data == "admin_users_menu":
        await show_users_filter_menu(query, context)
        
    elif callback_data == "admin_stats_menu":
        await show_admin_stats(query, context)
        
    elif callback_data == "admin_vip_menu":
        await show_vip_management_menu(query, context)
        
    elif callback_data == "admin_copier_menu":
        await show_copier_management_menu(query, context)
        
    elif callback_data == "admin_search_menu":
        await show_search_menu(query, context)
        
    elif callback_data == "admin_settings_menu":
        await show_settings_menu(query, context)
        
    elif callback_data.startswith("admin_users_page_"):
        parts = callback_data.split("_")
        filter_type = parts[3]
        page = int(parts[4])
        await show_user_browser(query, context, filter_type, page, is_callback=True)
        
    elif callback_data.startswith("admin_users_refresh_"):
        parts = callback_data.split("_")
        filter_type = parts[3]
        page = int(parts[4])
        await show_user_browser(query, context, filter_type, page, is_callback=True)
        
    elif callback_data.startswith("admin_start_conv_"):
        user_id = int(callback_data.split("_")[3])
        await admin_start_conversation(query, context, user_id)
        
    elif callback_data.startswith("admin_gen_link_"):
        user_id = int(callback_data.split("_")[3])
        await admin_generate_link(query, context, user_id)
        
    elif callback_data.startswith("admin_quick_vip_"):
        user_id = int(callback_data.split("_")[3])
        await admin_quick_vip_menu(query, context, user_id)

    # Handle other admin callbacks that might not be covered above
    else:
        print(f"Unhandled admin callback: {callback_data}")
        await query.edit_message_text(
            f"⚠️ <b>Function Under Development</b>\n\n"
            f"This feature is being implemented.\n"
            f"Please use the dashboard for available functions.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Back to Dashboard", callback_data="refresh_dashboard")]
            ])
        )


# -------------------------------------- VIP and Copier Team Management ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def add_to_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback for adding user to VIP channels."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received add to VIP callback: {query.data}")
    callback_data = query.data
    
    # Parse callback data to extract channel type and user ID
    # Format: add_vip_TYPE_USERID
    parts = callback_data.split('_')
    if len(parts) >= 4:
        channel_type = parts[2]
        user_id = parts[3]
        
        print(f"Adding user {user_id} to VIP {channel_type}")
        
        # Map channel types to IDs
        channel_mapping = {
            "signals": (SIGNALS_CHANNEL_ID, SIGNALS_GROUP_ID, "Signals"),
            "strategy": (STRATEGY_CHANNEL_ID, STRATEGY_GROUP_ID, "Strategy"),
            "propcapital": (PROP_CHANNEL_ID, PROP_GROUP_ID, "Prop Capital"),
        }
        
        if channel_type in channel_mapping:
            channel_id, group_id, channel_name = channel_mapping[channel_type]
            
            try:
                # Create invite links
                channel_invite = await context.bot.create_chat_invite_link(
                    chat_id=channel_id,
                    member_limit=1,
                    name=f"Invite for user {user_id}"
                )
                
                group_invite = await context.bot.create_chat_invite_link(
                    chat_id=group_id,
                    member_limit=1,
                    name=f"Invite for user {user_id}"
                )
                
                # Get user info
                user_info = db.get_user(user_id)
                user_name = user_info.get('first_name', 'User') if user_info else 'User'
                
                # Update database to track VIP channel assignment
                current_vip = user_info.get('vip_channels', '') if user_info else ''
                new_vip = f"{current_vip},{channel_type}".strip(',')
                
                db.add_user({
                    "user_id": user_id,
                    "vip_channels": new_vip,
                    "vip_added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Format response
                response = (
                    f"✅ VIP {channel_name} Access for {user_name} (ID: {user_id}):\n\n"
                    f"Channel: {channel_invite.invite_link}\n"
                    f"These are one-time use links. Please send to the user."
                )
                
                # Update the original message
                await query.edit_message_text(
                    text=response,
                    reply_markup=None  # Remove buttons after action
                )
                
                # Also try to notify the user
                try:
                    user_notification = (
                        f"🎉 Congratulations! You've been added to our VIP {channel_name} channel!\n\n"
                        f"Please use these exclusive invite links to join:\n\n"
                        f"Channel: {channel_invite.invite_link}\n"
                        f"These links will expire after one use, so please click them as soon as possible."
                    )
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_notification
                    )
                    print(f"Successfully sent VIP channel notification to user {user_id}")
                except Exception as e:
                    print(f"Failed to send notification to user {user_id}: {e}")
                    # Add a note to the admin message
                    await context.bot.send_message(
                        chat_id=update.effective_user.id,
                        text=f"Note: Unable to message user directly. Please manually send them the invite links."
                    )
                
            except Exception as e:
                await query.edit_message_text(
                    text=f"⚠️ Error adding user to VIP {channel_name}: {e}",
                    reply_markup=None
                )
        else:
            await query.edit_message_text(
                text=f"⚠️ Invalid channel type: {channel_type}",
                reply_markup=None
            )
    else:
        await query.edit_message_text(
            text="⚠️ Invalid callback data format",
            reply_markup=None
        )

async def forward_to_copier_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle callback for forwarding user to copier team."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received forward to copier callback: {query.data}")
    callback_data = query.data
    
    # Parse callback data to extract user ID
    # Format: forward_copier_USERID
    parts = callback_data.split('_')
    if len(parts) >= 3:
        user_id = parts[2]
        
        print(f"Forwarding user {user_id} to copier team")
        
        try:
            # Get user info
            user_info = db.get_user(user_id)
            
            if not user_info:
                await query.edit_message_text(
                    text=f"⚠️ User {user_id} not found in database",
                    reply_markup=None
                )
                return
            
            # Check if user has trading account
            trading_account = user_info.get("trading_account")
            if not trading_account:
                await query.edit_message_text(
                    text=f"⚠️ User {user_id} does not have a trading account registered",
                    reply_markup=None
                )
                return
            
            # Get user details
            user_name = user_info.get('first_name', 'Unknown')
            last_name = user_info.get('last_name', '')
            username = user_info.get('username', 'None')
            risk_appetite = user_info.get('risk_appetite', 'Not specified')
            deposit_amount = user_info.get('deposit_amount', 'Not specified')
            vip_channels = user_info.get('vip_channels', 'None')
            is_verified = user_info.get('is_verified', False)
            
            # Format copier team message with more details
            copier_message = (
                f"<b>🔄 NEW ACCOUNT FOR COPIER SYSTEM 🔄</b>\n\n"
                f"<b>📋 USER DETAILS:</b>\n"
                f"• Name: {user_name} {last_name}\n"
                f"• Username: @{username}\n"
                f"• User ID: {user_id}\n"
                f"• Trading Account: {trading_account} {'✅' if is_verified else '⚠️'}\n\n"
                f"<b>📊 TRADING PROFILE:</b>\n"
                f"• Risk Level: {risk_appetite}/10\n"
                f"• Deposit Amount: ${deposit_amount}\n"
                f"• VIP Services: {vip_channels}\n"
                f"• Account Status: {'Verified' if is_verified else 'Pending Verification'}\n\n"
                f"<b>⏰ Date Added:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"<b>👉 ACTION REQUIRED:</b> Please add this account to the copier system and configure the appropriate risk parameters."
            )
            
            # Create action buttons for the copier team
            copier_keyboard = [
                [
                    InlineKeyboardButton("✅ Account Added", callback_data=f"copier_added_{user_id}"),
                    InlineKeyboardButton("❌ Account Rejected", callback_data=f"copier_rejected_{user_id}")
                ],
                [InlineKeyboardButton("📞 Contact User", callback_data=f"contact_user_{user_id}")],
                [InlineKeyboardButton("📝 View Full Profile", callback_data=f"view_profile_{user_id}")]
            ]
            copier_reply_markup = InlineKeyboardMarkup(copier_keyboard)
            
            # Send message to support group (copier team)
            try:
                copier_team_message = await context.bot.send_message(
                    chat_id=SUPPORT_GROUP_ID,
                    text=copier_message,
                    parse_mode='HTML',
                    reply_markup=copier_reply_markup
                )
                
                print(f"Successfully sent copier team message to support group {SUPPORT_GROUP_ID}")
                
                # Update database to mark as forwarded to copier team
                db.add_user({
                    "user_id": user_id,
                    "copier_forwarded": True,
                    "copier_forwarded_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "copier_message_id": copier_team_message.message_id
                })
                
                # Update the original admin message to confirm it was sent
                await query.edit_message_text(
                    text=f"<b>✅ Account Successfully Forwarded to Copier Team</b>\n\n"
                        f"<b>User:</b> {user_name} {last_name}\n"
                        f"<b>Account:</b> {trading_account}\n"
                        f"<b>Risk Level:</b> {risk_appetite}/10\n"
                        f"<b>Deposit:</b> ${deposit_amount}\n\n"
                        f"<b>📤 Message sent to Support Group</b>\n"
                        f"<b>🕒 Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"The copier team will be able to take action on this account using the buttons provided.",
                    parse_mode='HTML',
                    reply_markup=None
                )
                
            except Exception as e:
                print(f"Error sending message to support group: {e}")
                await query.edit_message_text(
                    text=f"<b>⚠️ Error sending to copier team:</b> {e}\n\n"
                        f"Please manually forward this information:\n\n{copier_message}",
                    parse_mode='HTML',
                    reply_markup=None
                )
                return
            
            # Also notify the user
            try:
                user_notification = (
                    f"<b>📊 Your trading account has been forwarded to our copier team!</b>\n\n"
                    f"<b>Account:</b> {trading_account}\n"
                    f"<b>Risk Level:</b> {risk_appetite}/10\n"
                    f"<b>Deposit Amount:</b> ${deposit_amount}\n\n"
                    f"Our copier team will review your account and set up the optimal trading parameters based on your risk profile. "
                    f"You'll receive confirmation once your account is connected to our automated trading system.\n\n"
                    f"<b>Expected Setup Time:</b> 24 hours\n"
                    f"<b>Next Steps:</b> Our team will contact you with setup details and login credentials for your copier dashboard."
                )
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_notification,
                    parse_mode='HTML'
                )
                print(f"Successfully sent notification to user {user_id}")
            except Exception as e:
                print(f"Failed to send notification to user {user_id}: {e}")
                
        except Exception as e:
            print(f"Error in forward_to_copier_callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error forwarding to copier team: {e}",
                reply_markup=None
            )
    else:
        await query.edit_message_text(
            text="⚠️ Invalid callback data format",
            reply_markup=None
        )

async def copier_team_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle copier team action buttons (added, rejected, contact)."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    print(f"Received copier team action: {callback_data}")
    
    # Parse callback data
    parts = callback_data.split('_')
    if len(parts) >= 3:
        action = parts[1]  # added, rejected, contact
        user_id = parts[2]
        
        try:
            # Get user info
            user_info = db.get_user(user_id)
            if not user_info:
                await query.edit_message_text(
                    text="⚠️ User not found in database",
                    reply_markup=None
                )
                return
            
            user_name = user_info.get('first_name', 'Unknown')
            trading_account = user_info.get('trading_account', 'N/A')
            
            if action == "added":
                # Mark user as added to copier system
                db.add_user({
                    "user_id": user_id,
                    "copier_status": "active",
                    "copier_activated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Update the message to show it's been handled
                await query.edit_message_text(
                    text=f"<b>✅ ACCOUNT ADDED TO COPIER SYSTEM</b>\n\n"
                        f"<b>User:</b> {user_name}\n"
                        f"<b>Account:</b> {trading_account}\n"
                        f"<b>Status:</b> Active in copier system\n"
                        f"<b>Added by:</b> {query.from_user.first_name}\n"
                        f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"✅ User has been notified of successful setup.",
                    parse_mode='HTML',
                    reply_markup=None
                )
                
                # Notify the user
                try:
                    user_success_message = (
                        f"<b>🎉 Congratulations! Your account has been successfully added to our copier system! ✅</b>\n\n"
                        f"<b>📊 Account:</b> {trading_account}\n"
                        f"<b>🟢 Status:</b> Active\n"
                        f"<b>📅 Setup Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"🤖 Your account is now automatically copying our professional trading signals! "
                        f"📱 Monitor your performance through your Vortex-FX MT5 platform.\n\n"
                        f"<b>📝 Important Notes:</b>\n"
                        f"• ⚡ Trades execute automatically based on your risk settings\n"
                        f"• 📈 Monitor performance 24/7 through MT5\n"
                        f"• 👥 Our team monitors all accounts during market hours\n"
                        f"• 🔑 Keep your master password as default for optimal system performance\n\n"
                        f"<b>⚠️ Master Password Notice:</b>\n"
                        f"🔐 Your master password enables our copier system to execute trades efficiently. "
                        f"Changing it will automatically deactivate copy trading on your account.\n\n"
                        f"🚀 Welcome to our automated trading system! Let's grow your portfolio together! 💰"
                    )
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_success_message,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    print(f"Error notifying user of copier activation: {e}")
                    
            elif action == "rejected":
                # Mark user as rejected
                db.add_user({
                    "user_id": user_id,
                    "copier_status": "rejected",
                    "copier_rejected_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Create follow-up buttons for admin
                rejection_keyboard = [
                    [InlineKeyboardButton("📞 Contact User to Resolve", callback_data=f"contact_user_{user_id}")],
                    [InlineKeyboardButton("🔄 Retry Setup", callback_data=f"forward_copier_{user_id}")]
                ]
                rejection_reply_markup = InlineKeyboardMarkup(rejection_keyboard)
                
                await query.edit_message_text(
                    text=f"<b>❌ ACCOUNT REJECTED FROM COPIER SYSTEM</b>\n\n"
                        f"<b>User:</b> {user_name}\n"
                        f"<b>Account:</b> {trading_account}\n"
                        f"<b>Status:</b> Rejected\n"
                        f"<b>Rejected by:</b> {query.from_user.first_name}\n"
                        f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"⚠️ Please contact the user to resolve any issues.",
                    parse_mode='HTML',
                    reply_markup=rejection_reply_markup
                )
                
            elif action == "contact":
                # Provide contact options
                contact_keyboard = [
                    [InlineKeyboardButton("💬 Start Direct Chat", callback_data=f"start_conv_{user_id}")],
                    [InlineKeyboardButton("📋 View Full Profile", callback_data=f"view_profile_{user_id}")]
                ]
                contact_reply_markup = InlineKeyboardMarkup(contact_keyboard)
                
                await query.edit_message_text(
                    text=f"<b>📞 CONTACT USER: {user_name}</b>\n\n"
                        f"<b>User ID:</b> {user_id}\n"
                        f"<b>Account:</b> {trading_account}\n"
                        f"<b>Username:</b> @{user_info.get('username', 'None')}\n\n"
                        f"Choose how you'd like to contact this user:",
                    parse_mode='HTML',
                    reply_markup=contact_reply_markup
                )
                
        except Exception as e:
            print(f"Error handling copier team action: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error processing action: {e}",
                reply_markup=None
            )
    else:
        await query.edit_message_text(
            text="⚠️ Invalid action format",
            reply_markup=None
        )

async def handle_vip_confirmation_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle VIP access confirmation callbacks."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("confirm_vip_"):
        # Parse: confirm_vip_{service_type}_{user_id}
        parts = callback_data.split("_")
        service_type = parts[2]  # signals, strategy, or all
        user_id = int(parts[3])
        
        try:
            # First update local database VIP status
            await update_local_db_vip_status(user_id, service_type, query.from_user.id)
            
            # Then grant access and send links
            await grant_vip_access_to_user(query, context, user_id, service_type)
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ <b>Error Granting VIP Access</b>\n\n"
                f"Error: {str(e)[:200]}\n\n"
                f"Please try again or contact technical support.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"admin_grant_vip_{service_type}_{user_id}")],
                    [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
                ])
            )

async def admin_check_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-triggered balance check for a user."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[3])  # admin_check_balance_{user_id}
    
    user_info = db.get_user(user_id)
    if not user_info:
        await query.edit_message_text("❌ User not found.")
        return
    
    user_name = user_info.get("first_name", "User")
    trading_account = user_info.get("trading_account")
    
    if not trading_account:
        await query.edit_message_text(
            f"⚠️ <b>No Trading Account</b>\n\n"
            f"User {user_name} (ID: {user_id}) has no trading account registered.",
            parse_mode='HTML'
        )
        return
    
    # Show loading message
    loading_msg = await query.edit_message_text(
        f"🔍 <b>Checking Balance for {user_name}</b>\n\n"
        f"Fetching real-time data from account {trading_account}...",
        parse_mode='HTML'
    )
    
    try:
        # Get fresh balance from MySQL
        mysql_db = get_mysql_connection()
        if mysql_db and mysql_db.is_connected():
            account_info = mysql_db.verify_account_exists(trading_account)
            if account_info['exists']:
                current_balance = float(account_info.get('balance', 0))
                account_name = account_info.get('name', 'Unknown')
                
                # Update local database
                db.add_user({
                    "user_id": user_id,
                    "account_balance": current_balance,
                    "last_balance_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Show results
                balance_message = (
                    f"💰 <b>Balance Check Results</b>\n\n"
                    f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
                    f"<b>📊 Account:</b> {trading_account}\n"
                    f"<b>🏷️ Holder:</b> {account_name}\n"
                    f"<b>💵 Balance:</b> ${current_balance:,.2f}\n"
                    f"<b>🕒 Checked:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
                )
                
                if current_balance >= 100:
                    balance_message += f"<b>✅ Eligible for VIP access!</b>"
                    keyboard = [
                        [InlineKeyboardButton("🌟 Grant VIP Access", callback_data=f"admin_quick_vip_{user_id}")],
                        [InlineKeyboardButton("👤 View Profile", callback_data=f"admin_user_profile_{user_id}")],
                        [InlineKeyboardButton("🔄 Check Again", callback_data=f"admin_check_balance_{user_id}")]
                    ]
                else:
                    needed = 100 - current_balance
                    balance_message += f"<b>⚠️ ${needed:,.2f} more needed for VIP</b>"
                    keyboard = [
                        [InlineKeyboardButton("💬 Contact User", callback_data=f"admin_start_conv_{user_id}")],
                        [InlineKeyboardButton("👤 View Profile", callback_data=f"admin_user_profile_{user_id}")],
                        [InlineKeyboardButton("🔄 Check Again", callback_data=f"admin_check_balance_{user_id}")]
                    ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await loading_msg.edit_text(balance_message, parse_mode='HTML', reply_markup=reply_markup)
                
            else:
                await loading_msg.edit_text(
                    f"❌ <b>Account Not Found</b>\n\n"
                    f"Account {trading_account} not found in trading system.",
                    parse_mode='HTML'
                )
        else:
            await loading_msg.edit_text(
                f"⚠️ <b>Connection Error</b>\n\n"
                f"Unable to connect to trading system.",
                parse_mode='HTML'
            )
            
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ <b>Balance Check Failed</b>\n\n"
            f"Error: {str(e)[:200]}",
            parse_mode='HTML'
        )

async def admin_verify_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-triggered user verification."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[2])  # admin_verify_{user_id}
    
    user_info = db.get_user(user_id)
    if not user_info:
        await query.edit_message_text("❌ User not found.")
        return
    
    user_name = user_info.get("first_name", "User")
    trading_account = user_info.get("trading_account")
    
    if not trading_account:
        await query.edit_message_text(
            f"⚠️ <b>No Trading Account</b>\n\n"
            f"User {user_name} (ID: {user_id}) has no trading account to verify.",
            parse_mode='HTML'
        )
        return
    
    # Mark as verified and update database
    db.add_user({
        "user_id": user_id,
        "is_verified": True,
        "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "verified_by_admin": query.from_user.id
    })
    
    # Notify user
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ <b>Account Verified!</b>\n\n"
                f"Your VortexFX account {trading_account} has been verified by our team.\n\n"
                f"You can now access VIP services by ensuring your account has a minimum balance of $100.\n\n"
                f"Use <b>/myaccount</b> to check your status!"
            ),
            parse_mode='HTML'
        )
    except Exception as e:
        print(f"Error notifying user {user_id} of verification: {e}")
    
    # Update admin
    await query.edit_message_text(
        f"✅ <b>User Verified Successfully</b>\n\n"
        f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
        f"<b>📊 Account:</b> {trading_account}\n"
        f"<b>✅ Status:</b> Verified\n"
        f"<b>🕒 Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"User has been notified of verification.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Check Balance", callback_data=f"admin_check_balance_{user_id}")],
            [InlineKeyboardButton("👤 View Profile", callback_data=f"admin_user_profile_{user_id}")],
            [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
        ])
    )

async def admin_account_details_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show detailed account information for admin."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = int(callback_data.split("_")[3])  # admin_account_details_{user_id}
    
    user_info = db.get_user(user_id)
    if not user_info:
        await query.edit_message_text("❌ User not found.")
        return
    
    user_name = user_info.get("first_name", "User")
    trading_account = user_info.get("trading_account", "Not provided")
    
    # Get comprehensive account details
    account_details = (
        f"📋 <b>Account Details: {user_name}</b>\n\n"
        f"<b>👤 User Information:</b>\n"
        f"• User ID: {user_id}\n"
        f"• Name: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
        f"• Username: @{user_info.get('username', 'None')}\n"
        f"• Source: {user_info.get('source_channel', 'Unknown').replace('_', ' ').title()}\n\n"
        
        f"<b>📊 Trading Account:</b>\n"
        f"• Account Number: {trading_account}\n"
        f"• Account Holder: {user_info.get('account_owner', 'Unknown')}\n"
        f"• Balance: ${user_info.get('account_balance', 0):,.2f}\n"
        f"• Status: {user_info.get('account_status', 'Unknown')}\n\n"
        
        f"<b>✅ Verification:</b>\n"
        f"• Verified: {'Yes' if user_info.get('is_verified') else 'No'}\n"
        f"• Verification Date: {user_info.get('verification_date', 'Not set')}\n\n"
        
        f"<b>🌟 VIP Status:</b>\n"
        f"• VIP Access: {'Yes' if user_info.get('vip_access_granted') else 'No'}\n"
        f"• VIP Services: {user_info.get('vip_services_list', 'None')}\n"
        f"• VIP Since: {user_info.get('vip_granted_date', 'Not applicable')}\n\n"
        
        f"<b>📈 Trading Profile:</b>\n"
        f"• Risk Level: {user_info.get('risk_appetite', 'Not set')}/10\n"
        f"• Target Deposit: ${user_info.get('deposit_amount', 0):,}\n"
        f"• Trading Interest: {user_info.get('trading_interest', 'Not specified')}\n\n"
        
        f"<b>📅 Activity:</b>\n"
        f"• Joined: {user_info.get('join_date', 'Unknown')}\n"
        f"• Last Active: {user_info.get('last_active', 'Unknown')}\n"
        f"• Last Balance Update: {user_info.get('last_balance_update', 'Never')}"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🔄 Refresh Balance", callback_data=f"admin_check_balance_{user_id}"),
            InlineKeyboardButton("✏️ Edit Profile", callback_data=f"admin_edit_profile_{user_id}")
        ],
        [
            InlineKeyboardButton("💬 Start Conversation", callback_data=f"admin_start_conv_{user_id}"),
            InlineKeyboardButton("🌟 Manage VIP", callback_data=f"admin_manage_vip_{user_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Profile", callback_data=f"admin_user_profile_{user_id}"),
            InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(account_details, parse_mode='HTML', reply_markup=reply_markup)



# -------------------------------------- Utility Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome new members to the group/channel."""
    for new_user in update.message.new_chat_members:
        # Add user to database
        db.add_user({
            "user_id": new_user.id,
            "username": new_user.username,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name
        })
        
        # Add to group members
        db.add_to_group(new_user.id)
        
        # Send welcome message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome {new_user.first_name} to our trading community! {WELCOME_MSG}"
        )
        
        # Initiate authentication process
        await start_authentication(update, context, new_user.id)
        
        # Update analytics
        db.update_analytics(new_users=1)

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """HTML styled private message handler."""
    user = update.effective_user
    user_id = user.id
    
    # Check if this is a direct message to the bot
    if update.effective_chat.type == "private":
        # SECURITY CHECK: Prevent duplicate registrations
        if await check_existing_registration(update, context, user_id):
            return ConversationHandler.END
        # Update user activity
        db.update_user_activity(user.id)
        
        # HTML styled welcome message
        await update.message.reply_text(
            f"<b>🎉 Welcome to VFX Trading!</b>\n\n"
            f"Hi <b>{user.first_name}</b>! Let's get your account set up quickly and efficiently! ⚡\n\n"
            f"<b>📊 First Question:</b>\n"
            f"What's your risk appetite from <b>1-10</b>? 🎯\n\n"
            f"<b>💡 Tip:</b> 1 = Very Conservative, 10 = High Risk",
            parse_mode='HTML'
        )
        return RISK_APPETITE
    
    # For group messages, just update user activity
    db.update_user_activity(user.id)
    db.update_analytics(messages_sent=1)
    
    return ConversationHandler.END

async def log_all_chats(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log information about all chats the bot is a member of."""
    print("\n[CHAT ID DEBUG] Listing all chats the bot can access:")
    
    try:
        # Get the bot's information
        bot_info = await context.bot.get_me()
        print(f"Bot username: @{bot_info.username}")
        
        # For all updates, extract unique chat IDs
        with open("all_chat_ids.log", "w") as f:
            f.write(f"=== Bot Chat IDs as of {datetime.now()} ===\n\n")
            
            # Log information about the chats we already know
            f.write("Known chats:\n")
            f.write(f"GROUP_ID: {STRATEGY_GROUP_ID}\n")
            f.write(f"CHANNEL_ID: {MAIN_CHANNEL_ID}\n\n")
            
            f.write("=== Attempting to get information about channels ===\n")
            
            # Try to get chat information for channels we know about
            try:
                # Get info about the known channel
                channel_chat = await context.bot.get_chat(MAIN_CHANNEL_ID)
                f.write(f"Channel: {channel_chat.title} (ID: {channel_chat.id})\n")
                print(f"[CHAT ID DEBUG] Channel: {channel_chat.title} (ID: {channel_chat.id})")
            except Exception as e:
                f.write(f"Error getting known channel info: {e}\n")
                
            # Try to get chat information for groups we know about
            try:
                # Get info about the known group
                group_chat = await context.bot.get_chat(STRATEGY_GROUP_ID)
                f.write(f"Group: {group_chat.title} (ID: {group_chat.id})\n")
                print(f"[CHAT ID DEBUG] Group: {group_chat.title} (ID: {group_chat.id})")
            except Exception as e:
                f.write(f"Error getting known group info: {e}\n")
                
    except Exception as e:
        print(f"[CHAT ID DEBUG] Error listing chats: {e}")
        with open("all_chat_ids.log", "a") as f:
            f.write(f"Error listing chats: {e}\n")

async def silent_update_logger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Silently log any update to the terminal and file without responding."""
    # Skip if this is a command or we've already processed it
    if not update or not update.effective_chat:
        return
        
    chat_id = update.effective_chat.id
    chat_type = update.effective_chat.type
    chat_title = update.effective_chat.title if hasattr(update.effective_chat, 'title') else "Direct message"
    
    print(f"[SILENT LOGGER] New activity in: {chat_title}")
    print(f"[SILENT LOGGER] Chat ID: {chat_id}, type: {chat_type}")
    
    with open("silent_chat_ids.log", "a") as f:
        f.write(f"{datetime.now()}: {chat_title} - {chat_id} ({chat_type})\n")

async def refresh_admin_dashboard(query, context):
    """Refresh the main admin dashboard."""
    # Get fresh stats
    total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
    verified_users = db.users_df.filter(pl.col("is_verified") == True).height if total_users > 0 else 0
    vip_users = db.users_df.filter(pl.col("vip_access_granted") == True).height if total_users > 0 else 0
    active_users_7d = db.get_active_users(days=7)
    
    dashboard_message = (
        f"🎛️ <b>VFX Trading Admin Dashboard</b>\n\n"
        f"<b>📊 Quick Stats (Updated):</b>\n"
        f"• Total Users: {total_users:,}\n"
        f"• Verified: {verified_users:,}\n"
        f"• VIP Members: {vip_users:,}\n"
        f"• Active (7d): {active_users_7d:,}\n\n"
        f"<b>🚀 What would you like to do?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👥 Manage Users", callback_data="admin_users_menu"),
            InlineKeyboardButton("📊 View Statistics", callback_data="admin_stats_menu")
        ],
        [
            InlineKeyboardButton("🌟 VIP Management", callback_data="admin_vip_menu"),
            InlineKeyboardButton("🔄 Copier Management", callback_data="admin_copier_menu")
        ],
        [
            InlineKeyboardButton("🔍 Search Users", callback_data="admin_search_menu"),
            InlineKeyboardButton("⚙️ System Settings", callback_data="admin_settings_menu")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(dashboard_message, parse_mode='HTML', reply_markup=reply_markup)

async def show_users_filter_menu(query, context):
    """Show user filter options."""
    filter_message = (
        f"👥 <b>User Management</b>\n\n"
        f"<b>🔍 Choose how to view users:</b>\n\n"
        f"📅 <b>Recent:</b> Recently active users\n"
        f"✅ <b>Verified:</b> Users with verified accounts\n"
        f"🌟 <b>VIP:</b> Users with VIP access\n"
        f"⏳ <b>Unverified:</b> Users needing verification\n"
        f"💰 <b>High Balance:</b> Users with $100+ balance\n"
        f"👥 <b>All Users:</b> Complete user list"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("📅 Recent Users", callback_data="admin_users_page_recent_0"),
            InlineKeyboardButton("✅ Verified", callback_data="admin_users_page_verified_0")
        ],
        [
            InlineKeyboardButton("🌟 VIP Users", callback_data="admin_users_page_vip_0"),
            InlineKeyboardButton("⏳ Unverified", callback_data="admin_users_page_unverified_0")
        ],
        [
            InlineKeyboardButton("💰 High Balance", callback_data="admin_users_page_high_balance_0"),
            InlineKeyboardButton("👥 All Users", callback_data="admin_users_page_all_0")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(filter_message, parse_mode='HTML', reply_markup=reply_markup)

async def admin_start_conversation(query, context, user_id):
    """Start a conversation with a user (enhanced version)."""
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
    
    # Store the current conversation user for admin
    context.user_data["current_user_conv"] = user_id
    
    try:
        # Try to send a connection message to the user
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"<b>👋 Hello {user_name}!</b>\n\n"
                f"One of our VFX Trading advisors is now available to help you.\n\n"
                f"<b>💬 You can now chat directly with our team!</b>\n"
                f"Feel free to ask any questions about your account or our services. ✅"
            ),
            parse_mode='HTML'
        )
        
        await query.edit_message_text(
            f"✅ <b>Conversation Started!</b>\n\n"
            f"<b>👤 Connected to:</b> {user_name} (ID: {user_id})\n"
            f"<b>💬 Status:</b> Direct conversation active\n"
            f"<b>🕒 Started:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
            f"<b>📱 Any message you send to the bot will now be forwarded to {user_name}</b>\n\n"
            f"Use /endchat to end this conversation when finished.",
            parse_mode='HTML'
        )
        
    except Exception as e:
        if "Forbidden: bot can't initiate conversation with a user" in str(e):
            await query.edit_message_text(
                f"🚫 <b>Cannot Connect Directly</b>\n\n"
                f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
                f"<b>⚠️ Issue:</b> User hasn't started the bot yet\n\n"
                f"<b>💡 Solution:</b> Use 'Send Link' to connect with them first",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Generate Link", callback_data=f"admin_gen_link_{user_id}")],
                    [InlineKeyboardButton("🔙 Back to Profile", callback_data=f"admin_user_profile_{user_id}")]
                ])
            )
        else:
            await query.edit_message_text(
                f"❌ <b>Connection Failed</b>\n\n"
                f"Error: {str(e)[:100]}",
                parse_mode='HTML'
            )

async def admin_generate_link(query, context, user_id):
    """Generate connection link for user (enhanced version)."""
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
    username = user_info.get('username') if user_info else None
    
    # Create connection link
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    start_link = f"https://t.me/{bot_username}?start=ref_{query.from_user.id}"
    
    # Generate personalized message
    connection_message = (
        f"Hi {user_name}! 👋\n\n"
        f"I'm reaching out from VFX Trading to help you with your account setup.\n\n"
        f"To continue our conversation securely through our system, please click this link:\n\n"
        f"👉 <a href='{start_link}'>Connect with VFX - REGISTRATION</a>\n\n"
        f"This will connect you to our automated assistant where we can discuss:\n"
        f"• Your trading goals and preferences\n"
        f"• Account verification and funding\n"
        f"• VIP service access\n\n"
        f"Looking forward to helping you succeed! 🚀"
    )
    
    instructions = (
        f"🔗 <b>Connection Link Generated for {user_name}</b>\n\n"
        f"📋 <b>Send this message to the user:</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{connection_message}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    if username:
        instructions += f"💡 <b>Best option:</b> Message @{username} directly with the text above"
    else:
        instructions += f"💡 <b>Copy the message above and send it to {user_name} in your chats"
    
    await query.edit_message_text(
        instructions,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back to Profile", callback_data=f"admin_user_profile_{user_id}")],
            [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
        ])
    )

async def admin_quick_vip_menu(query, context, user_id):
    """Show quick VIP grant options."""
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else f'User {user_id}'
    balance = user_info.get('account_balance', 0) or 0
    
    if balance < 100:
        await query.edit_message_text(
            f"⚠️ <b>Insufficient Balance</b>\n\n"
            f"<b>User:</b> {user_name}\n"
            f"<b>Balance:</b> ${balance:,.2f}\n"
            f"<b>Required:</b> $100.00\n\n"
            f"User needs more funding for VIP access.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Profile", callback_data=f"admin_user_profile_{user_id}")]
            ])
        )
        return
    
    quick_vip_message = (
        f"🌟 <b>Quick VIP Grant for {user_name}</b>\n\n"
        f"<b>💰 Balance:</b> ${balance:,.2f} ✅\n"
        f"<b>✅ Eligible for VIP access</b>\n\n"
        f"<b>Which service would you like to grant?</b>"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🔔 VIP Signals Only", callback_data=f"admin_grant_vip_signals_{user_id}"),
            InlineKeyboardButton("🤖 VIP Strategy Only", callback_data=f"admin_grant_vip_strategy_{user_id}")
        ],
        [
            InlineKeyboardButton("✨ Both VIP Services", callback_data=f"admin_grant_vip_all_{user_id}")
        ],
        [
            InlineKeyboardButton("🔙 Back to Profile", callback_data=f"admin_user_profile_{user_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

async def show_admin_stats(query, context):
    """Show comprehensive statistics dashboard."""
    try:
        # Get comprehensive stats
        total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
        verified_users = db.users_df.filter(pl.col("is_verified") == True).height if total_users > 0 else 0
        vip_users = db.users_df.filter(pl.col("vip_access_granted") == True).height if total_users > 0 else 0
        unverified_users = total_users - verified_users
        
        # Activity stats
        active_users_1d = db.get_active_users(days=1)
        active_users_7d = db.get_active_users(days=7)
        active_users_30d = db.get_active_users(days=30)
        
        # Balance stats
        high_balance_users = 0
        total_balance = 0
        avg_balance = 0
        
        if total_users > 0:
            try:
                # Get users with balance >= $100
                high_balance_users = db.users_df.filter(pl.col("account_balance") >= 100).height
                
                # Calculate total and average balance
                balance_data = db.users_df.select(pl.col("account_balance")).fill_null(0)
                if balance_data.height > 0:
                    total_balance = balance_data.sum().item()
                    avg_balance = total_balance / total_users
                    
            except Exception as e:
                print(f"Error calculating balance stats: {e}")
        
        # Source channel breakdown
        source_stats = {}
        try:
            if total_users > 0:
                sources = db.users_df.group_by("source_channel").count()
                for i in range(sources.height):
                    channel = sources["source_channel"][i] or "Unknown"
                    count = sources["count"][i]
                    source_stats[channel] = count
        except Exception as e:
            print(f"Error calculating source stats: {e}")
        
        # Format stats message
        stats_message = (
            f"📊 <b>VFX Trading Statistics Dashboard</b>\n\n"
            
            f"<b>👥 User Overview:</b>\n"
            f"• Total Users: {total_users:,}\n"
            f"• ✅ Verified: {verified_users:,} ({(verified_users/total_users*100):.1f}%)\n"
            f"• ⏳ Unverified: {unverified_users:,} ({(unverified_users/total_users*100):.1f}%)\n"
            f"• 🌟 VIP Members: {vip_users:,} ({(vip_users/total_users*100):.1f}%)\n\n"
            
            f"<b>📈 Activity Metrics:</b>\n"
            f"• Active Today: {active_users_1d:,}\n"
            f"• Active (7 days): {active_users_7d:,}\n"
            f"• Active (30 days): {active_users_30d:,}\n\n"
            
            f"<b>💰 Financial Overview:</b>\n"
            f"• High Balance ($100+): {high_balance_users:,}\n"
            f"• Total Balance: ${total_balance:,.2f}\n"
            f"• Average Balance: ${avg_balance:,.2f}\n\n"
        )
        
        if source_stats:
            stats_message += f"<b>📍 User Sources:</b>\n"
            for source, count in sorted(source_stats.items(), key=lambda x: x[1], reverse=True):
                percentage = (count/total_users*100) if total_users > 0 else 0
                source_display = source.replace('_', ' ').title()
                stats_message += f"• {source_display}: {count:,} ({percentage:.1f}%)\n"
            stats_message += "\n"
        
        stats_message += f"<b>🕒 Last Updated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        keyboard = [
            [
                InlineKeyboardButton("📊 Detailed Reports", callback_data="admin_detailed_reports"),
                InlineKeyboardButton("📈 Growth Metrics", callback_data="admin_growth_metrics")
            ],
            [
                InlineKeyboardButton("💰 Financial Analysis", callback_data="admin_financial_analysis"),
                InlineKeyboardButton("📍 Source Analysis", callback_data="admin_source_analysis")
            ],
            [
                InlineKeyboardButton("🔄 Refresh Stats", callback_data="admin_stats_menu"),
                InlineKeyboardButton("📋 Export Data", callback_data="admin_export_data")
            ],
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(stats_message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error Loading Statistics</b>\n\n"
            f"Error: {str(e)[:200]}\n\n"
            f"Please try again or contact technical support.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="admin_stats_menu")],
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
            ])
        )

async def show_vip_management_menu(query, context):
    """Show VIP management options."""
    try:
        # Get VIP stats
        total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
        vip_users = db.users_df.filter(pl.col("vip_access_granted") == True).height if total_users > 0 else 0
        vip_eligible = db.users_df.filter(pl.col("account_balance") >= 100).height if total_users > 0 else 0
        pending_requests = 0
        
        try:
            pending_requests = db.users_df.filter(pl.col("vip_request_status") == "pending").height
        except:
            pass
        
        # VIP service breakdown
        signals_users = 0
        strategy_users = 0
        both_services = 0
        
        try:
            if vip_users > 0:
                vip_data = db.users_df.filter(pl.col("vip_access_granted") == True)
                for i in range(vip_data.height):
                    services = vip_data["vip_services"][i] or ""
                    if services == "signals":
                        signals_users += 1
                    elif services == "strategy":
                        strategy_users += 1
                    elif services == "all":
                        both_services += 1
        except Exception as e:
            print(f"Error calculating VIP service breakdown: {e}")
        
        vip_message = (
            f"🌟 <b>VIP Management Dashboard</b>\n\n"
            
            f"<b>📊 VIP Overview:</b>\n"
            f"• Total VIP Members: {vip_users:,}\n"
            f"• VIP Eligible (Balance $100+): {vip_eligible:,}\n"
            f"• Pending Requests: {pending_requests:,}\n"
            f"• VIP Conversion Rate: {(vip_users/total_users*100):.1f}%\n\n"
            
            f"<b>🎯 Service Breakdown:</b>\n"
            f"• 🔔 Signals Only: {signals_users:,}\n"
            f"• 🤖 Strategy Only: {strategy_users:,}\n"
            f"• ✨ Both Services: {both_services:,}\n\n"
            
            f"<b>🚀 What would you like to do?</b>"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 View VIP Users", callback_data="admin_users_page_vip_0"),
                InlineKeyboardButton("⏳ Pending Requests", callback_data="admin_vip_pending")
            ],
            [
                InlineKeyboardButton("💰 VIP Eligible Users", callback_data="admin_users_page_high_balance_0"),
                InlineKeyboardButton("🎯 Grant VIP Access", callback_data="admin_vip_grant_menu")
            ],
            [
                InlineKeyboardButton("📊 VIP Analytics", callback_data="admin_vip_analytics"),
                InlineKeyboardButton("⚙️ VIP Settings", callback_data="admin_vip_settings")
            ],
            [
                InlineKeyboardButton("🔄 Bulk VIP Actions", callback_data="admin_vip_bulk"),
                InlineKeyboardButton("📧 VIP Messaging", callback_data="admin_vip_messaging")
            ],
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(vip_message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error Loading VIP Management</b>\n\n"
            f"Error: {str(e)[:200]}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="admin_vip_menu")],
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
            ])
        )

async def show_copier_management_menu(query, context):
    """Show copier team management options."""
    try:
        # Get copier stats
        total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
        copier_forwarded = 0
        copier_active = 0
        copier_rejected = 0
        
        try:
            copier_forwarded = db.users_df.filter(pl.col("copier_forwarded") == True).height
            copier_active = db.users_df.filter(pl.col("copier_status") == "active").height
            copier_rejected = db.users_df.filter(pl.col("copier_status") == "rejected").height
        except:
            pass
        
        # Get recent copier activity
        recent_forwards = 0
        try:
            from datetime import datetime, timedelta
            recent_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            recent_forwards = db.users_df.filter(
                (pl.col("copier_forwarded_date") >= recent_date) & 
                (pl.col("copier_forwarded") == True)
            ).height
        except:
            pass
        
        copier_message = (
            f"🔄 <b>Copier Team Management</b>\n\n"
            
            f"<b>📊 Copier Overview:</b>\n"
            f"• Total Forwarded: {copier_forwarded:,}\n"
            f"• Active in System: {copier_active:,}\n"
            f"• Rejected: {copier_rejected:,}\n"
            f"• Recent Forwards (7d): {recent_forwards:,}\n\n"
            
            f"<b>📈 Success Rate:</b>\n"
        )
        
        if copier_forwarded > 0:
            success_rate = (copier_active / copier_forwarded) * 100
            copier_message += f"• Acceptance Rate: {success_rate:.1f}%\n"
        else:
            copier_message += f"• Acceptance Rate: N/A\n"
        
        copier_message += (
            f"\n<b>🎯 Management Options:</b>\n"
            f"• Forward eligible users to copier team\n"
            f"• Monitor copier system performance\n"
            f"• Manage user account integration\n"
            f"• Handle copier team communications"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("👥 View Copier Users", callback_data="admin_copier_users"),
                InlineKeyboardButton("⏳ Pending Reviews", callback_data="admin_copier_pending")
            ],
            [
                InlineKeyboardButton("🎯 Forward to Copier", callback_data="admin_copier_forward_menu"),
                InlineKeyboardButton("📊 Copier Analytics", callback_data="admin_copier_analytics")
            ],
            [
                InlineKeyboardButton("✅ Active Accounts", callback_data="admin_copier_active"),
                InlineKeyboardButton("❌ Rejected Accounts", callback_data="admin_copier_rejected")
            ],
            [
                InlineKeyboardButton("⚙️ Copier Settings", callback_data="admin_copier_settings"),
                InlineKeyboardButton("💬 Team Messages", callback_data="admin_copier_messages")
            ],
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(copier_message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error Loading Copier Management</b>\n\n"
            f"Error: {str(e)[:200]}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="admin_copier_menu")],
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
            ])
        )

async def show_search_menu(query, context):
    """Show search and filter options."""
    search_message = (
        f"🔍 <b>Search & Filter Users</b>\n\n"
        
        f"<b>🎯 Quick Searches:</b>\n"
        f"• Search by user ID or username\n"
        f"• Find users by account number\n"
        f"• Filter by balance range\n"
        f"• Search by registration date\n\n"
        
        f"<b>📊 Advanced Filters:</b>\n"
        f"• Combine multiple criteria\n"
        f"• Export search results\n"
        f"• Save common searches\n"
        f"• Bulk actions on results\n\n"
        
        f"<b>💡 Search Tips:</b>\n"
        f"• Use partial matches for names\n"
        f"• Date ranges for time-based filters\n"
        f"• Balance ranges for financial analysis"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("🆔 Search by User ID", callback_data="admin_search_user_id"),
            InlineKeyboardButton("👤 Search by Name", callback_data="admin_search_name")
        ],
        [
            InlineKeyboardButton("📊 Search by Account", callback_data="admin_search_account"),
            InlineKeyboardButton("💰 Search by Balance", callback_data="admin_search_balance")
        ],
        [
            InlineKeyboardButton("📅 Search by Date", callback_data="admin_search_date"),
            InlineKeyboardButton("🌟 Search VIP Status", callback_data="admin_search_vip")
        ],
        [
            InlineKeyboardButton("🔧 Advanced Search", callback_data="admin_search_advanced"),
            InlineKeyboardButton("📋 Recent Searches", callback_data="admin_search_recent")
        ],
        [
            InlineKeyboardButton("💾 Saved Searches", callback_data="admin_search_saved"),
            InlineKeyboardButton("📊 Quick Stats", callback_data="admin_search_stats")
        ],
        [
            InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(search_message, parse_mode='HTML', reply_markup=reply_markup)

async def show_settings_menu(query, context):
    """Show system settings and configuration options."""
    try:
        # Get current system status
        total_users = db.users_df.height if hasattr(db.users_df, 'height') else 0
        
        # Check MySQL connection
        mysql_status = "🟢 Connected"
        try:
            mysql_db = get_mysql_connection()
            if not mysql_db.is_connected():
                mysql_status = "🔴 Disconnected"
        except:
            mysql_status = "🔴 Error"
        
        # Get scheduled job status (simplified check)
        job_status = "🟢 Active"
        try:
            # You can add more sophisticated job checking here
            job_status = "🟢 Active"
        except:
            job_status = "🔴 Inactive"
        
        settings_message = (
            f"⚙️ <b>System Settings & Configuration</b>\n\n"
            
            f"<b>🔧 System Status:</b>\n"
            f"• Database: {mysql_status}\n"
            f"• Scheduled Jobs: {job_status}\n"
            f"• Total Users: {total_users:,}\n"
            f"• Bot Uptime: Active ✅\n\n"
            
            f"<b>📋 Configuration Options:</b>\n"
            f"• Message scheduling settings\n"
            f"• VIP access parameters\n"
            f"• Channel management\n"
            f"• Admin permissions\n"
            f"• Database maintenance\n\n"
            
            f"<b>🛠️ Available Tools:</b>\n"
            f"• Backup and restore data\n"
            f"• Update system messages\n"
            f"• Monitor performance\n"
            f"• Export/import settings"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("📧 Message Settings", callback_data="admin_settings_messages"),
                InlineKeyboardButton("🌟 VIP Settings", callback_data="admin_settings_vip")
            ],
            [
                InlineKeyboardButton("📺 Channel Settings", callback_data="admin_settings_channels"),
                InlineKeyboardButton("👥 Admin Settings", callback_data="admin_settings_admins")
            ],
            [
                InlineKeyboardButton("🗄️ Database Tools", callback_data="admin_settings_database"),
                InlineKeyboardButton("📊 Performance Monitor", callback_data="admin_settings_performance")
            ],
            [
                InlineKeyboardButton("💾 Backup & Export", callback_data="admin_settings_backup"),
                InlineKeyboardButton("🔄 System Maintenance", callback_data="admin_settings_maintenance")
            ],
            [
                InlineKeyboardButton("📋 View Logs", callback_data="admin_settings_logs"),
                InlineKeyboardButton("⚙️ Advanced Config", callback_data="admin_settings_advanced")
            ],
            [
                InlineKeyboardButton("🔙 Back to Dashboard", callback_data="refresh_dashboard")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(settings_message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error Loading Settings</b>\n\n"
            f"Error: {str(e)[:200]}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Retry", callback_data="admin_settings_menu")],
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
            ])
        )

async def handle_all_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enhanced handler for all admin dashboard callbacks."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Main dashboard callbacks
    if callback_data == "refresh_dashboard":
        await refresh_admin_dashboard(query, context)
        
    elif callback_data == "admin_users_menu":
        await show_users_filter_menu(query, context)
        
    elif callback_data == "admin_stats_menu":
        await show_admin_stats(query, context)
        
    elif callback_data == "admin_vip_menu":
        await show_vip_management_menu(query, context)
        
    elif callback_data == "admin_copier_menu":
        await show_copier_management_menu(query, context)
        
    elif callback_data == "admin_search_menu":
        await show_search_menu(query, context)
        
    elif callback_data == "admin_settings_menu":
        await show_settings_menu(query, context)
    
    # User management callbacks
    elif callback_data.startswith("admin_users_page_"):
        parts = callback_data.split("_")
        filter_type = parts[3]
        page = int(parts[4])
        await show_user_browser(query, context, filter_type, page, is_callback=True)
        
    elif callback_data.startswith("admin_users_refresh_"):
        parts = callback_data.split("_")
        filter_type = parts[3]
        page = int(parts[4])
        await show_user_browser(query, context, filter_type, page, is_callback=True)
        
    elif callback_data.startswith("admin_user_profile_"):
        user_id = int(callback_data.split("_")[3])
        await show_comprehensive_user_profile(query, context, user_id)
    
    # VIP management callbacks
    elif callback_data.startswith("admin_grant_vip_signals_"):
        user_id = int(callback_data.split("_")[4])
        await grant_vip_access_enhanced(query, context, user_id, "signals")
        
    elif callback_data.startswith("admin_grant_vip_strategy_"):
        user_id = int(callback_data.split("_")[4])
        await grant_vip_access_enhanced(query, context, user_id, "strategy")
        
    elif callback_data.startswith("admin_grant_vip_all_"):
        user_id = int(callback_data.split("_")[4])
        await grant_vip_access_enhanced(query, context, user_id, "all")
    
    # Communication callbacks
    elif callback_data.startswith("admin_start_conv_"):
        user_id = int(callback_data.split("_")[3])
        await admin_start_conversation(query, context, user_id)
        
    elif callback_data.startswith("admin_gen_link_"):
        user_id = int(callback_data.split("_")[3])
        await admin_generate_link(query, context, user_id)
        
    elif callback_data.startswith("admin_quick_vip_"):
        user_id = int(callback_data.split("_")[3])
        await admin_quick_vip_menu(query, context, user_id)
    
    # Placeholder callbacks for not-yet-implemented features
    elif callback_data in [
        "admin_detailed_reports", "admin_growth_metrics", "admin_financial_analysis",
        "admin_source_analysis", "admin_export_data", "admin_vip_pending",
        "admin_vip_grant_menu", "admin_vip_analytics", "admin_vip_settings",
        "admin_vip_bulk", "admin_vip_messaging", "admin_copier_users",
        "admin_copier_pending", "admin_copier_forward_menu", "admin_copier_analytics",
        "admin_copier_active", "admin_copier_rejected", "admin_copier_settings",
        "admin_copier_messages", "admin_search_user_id", "admin_search_name",
        "admin_search_account", "admin_search_balance", "admin_search_date",
        "admin_search_vip", "admin_search_advanced", "admin_search_recent",
        "admin_search_saved", "admin_search_stats", "admin_settings_messages",
        "admin_settings_vip", "admin_settings_channels", "admin_settings_admins",
        "admin_settings_database", "admin_settings_performance", "admin_settings_backup",
        "admin_settings_maintenance", "admin_settings_logs", "admin_settings_advanced"
    ]:
        await query.edit_message_text(
            f"⚙️ <b>Feature Under Development</b>\n\n"
            f"This feature is currently being implemented.\n"
            f"Please check back in a future update!\n\n"
            f"<b>Available now:</b>\n"
            f"• User management ✅\n"
            f"• VIP access granting ✅\n"
            f"• Basic statistics ✅\n"
            f"• User conversations ✅",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")]
            ])
        )
    
    # Unknown callback
    else:
        print(f"Unhandled admin callback: {callback_data}")
        await query.edit_message_text(
            f"⚠️ <b>Unknown Action</b>\n\n"
            f"This action is not recognized.\n"
            f"Please try using the dashboard menu.",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Dashboard", callback_data="refresh_dashboard")]
            ])
        )

async def grant_vip_access_enhanced(query, context, user_id, service_type):
    """Enhanced VIP access granting with comprehensive error handling."""
    try:
        user_info = db.get_user(user_id)
        if not user_info:
            await query.edit_message_text(
                f"❌ <b>User Not Found</b>\n\nUser ID {user_id} not found in database.",
                parse_mode='HTML'
            )
            return
        
        user_name = user_info.get("first_name", "User")
        account_number = user_info.get("trading_account", "Unknown")
        
        # Check balance eligibility
        account_balance = user_info.get("account_balance", 0) or 0
        if account_balance < 100:
            await query.edit_message_text(
                f"⚠️ <b>Insufficient Balance</b>\n\n"
                f"<b>User:</b> {user_name} (ID: {user_id})\n"
                f"<b>Balance:</b> ${account_balance:,.2f}\n"
                f"<b>Required:</b> $100.00\n\n"
                f"User needs more funding for VIP access.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contact User", callback_data=f"admin_start_conv_{user_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"admin_user_profile_{user_id}")]
                ])
            )
            return
        
        # Show confirmation
        service_names = {
            "signals": "VIP Signals",
            "strategy": "VIP Strategy", 
            "all": "All VIP Services (Signals + Strategy + Prop Capital)"
        }
        
        service_name = service_names.get(service_type, service_type)
        
        confirmation_message = (
            f"✅ <b>Confirm VIP Access Grant</b>\n\n"
            f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
            f"<b>📊 Account:</b> {account_number}\n"
            f"<b>💰 Balance:</b> ${account_balance:,.2f} ✅\n"
            f"<b>🎯 Service:</b> {service_name}\n\n"
            f"<b>This will:</b>\n"
            f"• Generate exclusive invite links\n"
            f"• Send them directly to the user\n"
            f"• Update their VIP status in database\n"
            f"• Grant immediate access to channels\n\n"
            f"<b>Proceed with granting access?</b>"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Grant Access Now", callback_data=f"confirm_vip_{service_type}_{user_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"admin_user_profile_{user_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(confirmation_message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        await query.edit_message_text(
            f"❌ <b>Error Processing Request</b>\n\n"
            f"Error: {str(e)[:200]}",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="refresh_dashboard")]
            ])
        )



# -------------------------------------- Admin Command Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def start_form_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the registration form during an ongoing conversation."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if "current_user_conv" in context.user_data:
        user_id = context.user_data["current_user_conv"]
        user_info = db.get_user(user_id)
        user_name = user_info.get("first_name", "User") if user_info else "User"
        
        try:
            # Send the registration form questions
            await context.bot.send_message(
                chat_id=user_id,
                text=f"{PRIVATE_WELCOME_MSG}\n\nFirst, what's your risk appetite from 1-10?"
            )
            
            await update.message.reply_text(
                f"✅ Registration form sent to {user_name} (ID: {user_id}).\n"
                f"The user's responses will now be collected for the registration process."
            )
        except Exception as e:
            await update.message.reply_text(f"Error sending registration form: {e}")
    else:
        await update.message.reply_text(
            "You're not currently in a conversation with any user. "
            "Forward a message from a user to start a conversation first."
        )

async def add_to_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to add a user to VIP channels."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Check for arguments
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "Usage: /addtovip <user_id> <channel_type>\n"
            "Channel types: signals, strategy, propcapital, all"
        )
        return
    
    try:
        user_id = args[0]
        channel_type = args[1].lower()
        
        # Validate user ID
        user_info = db.get_user(user_id)
        if not user_info:
            await update.message.reply_text(f"User ID {user_id} not found in database.")
            return
        
        # Map channel type to channel IDs
        channel_mapping = {
            "signals": (SIGNALS_CHANNEL_ID, SIGNALS_GROUP_ID),
            "strategy": (STRATEGY_CHANNEL_ID, STRATEGY_GROUP_ID),
            "propcapital": (PROP_CHANNEL_ID, PROP_GROUP_ID),
        }
        
        channels_to_add = []
        if channel_type == "all":
            for channel_pair in channel_mapping.values():
                channels_to_add.append(channel_pair)
        elif channel_type in channel_mapping:
            channels_to_add.append(channel_mapping[channel_type])
        else:
            await update.message.reply_text(f"Invalid channel type. Use signals, strategy, propcapital, or all.")
            return
        
        # Generate invite links for each channel/group
        success_messages = []
        for channel_id, group_id in channels_to_add:
            try:
                # Create chat invite link with member limit=1 (one-time use)
                channel_invite = await context.bot.create_chat_invite_link(
                    chat_id=channel_id,
                    member_limit=1,
                    name=f"Invite for user {user_id}"
                )
                
                group_invite = await context.bot.create_chat_invite_link(
                    chat_id=group_id,
                    member_limit=1,
                    name=f"Invite for user {user_id}"
                )
                
                # Get channel/group names
                channel_chat = await context.bot.get_chat(channel_id)
                group_chat = await context.bot.get_chat(group_id)
                
                success_messages.append(
                    f"✅ Invite links for {channel_chat.title}:\n"
                    f"Channel: {channel_invite.invite_link}\n"
                    f"Group: {group_invite.invite_link}\n"
                )
            except Exception as e:
                await update.message.reply_text(f"Error creating invite for {channel_id}: {e}")
        
        # Format response with all invite links
        if success_messages:
            response = f"🔗 VIP Access for {user_info['first_name']} (ID: {user_id}):\n\n"
            response += "\n".join(success_messages)
            response += "\nPlease send these links to the user."
            
            await update.message.reply_text(response)
            
            # Also record this in the database
            db.add_user({
                "user_id": user_id,
                "vip_channels": channel_type,
                "vip_added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            await update.message.reply_text("Failed to create any invite links.")
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def forward_mt5_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to forward MT5 account details to the copier team."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Check for arguments
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /forwardmt5 <user_id>"
        )
        return
    
    try:
        user_id = args[0]
        
        # Validate user ID
        user_info = db.get_user(user_id)
        if not user_info:
            await update.message.reply_text(f"User ID {user_id} not found in database.")
            return
        
        # Check if user has trading account
        trading_account = user_info.get("trading_account")
        if not trading_account:
            await update.message.reply_text(f"User {user_id} does not have a trading account registered.")
            return
        
        # Get risk appetite and deposit amount
        risk_appetite = user_info.get("risk_appetite", "Not specified")
        deposit_amount = user_info.get("deposit_amount", "Not specified")
        
        # Format message for copier team
        copier_message = (
            f"🔄 New Trading Account for Copier System 🔄\n\n"
            f"User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"Trading Account: {trading_account}\n"
            f"Risk Level: {risk_appetite}/10\n"
            f"Deposit Amount: ${deposit_amount}\n"
            f"Date Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"👉 Please add this account to the copier system."
        )
        
        # Here you would forward to your copier team's chat or group
        # For now, we'll just send it back to the admin
        await update.message.reply_text(
            f"✅ Trading account forwarded to copier team:\n\n{copier_message}\n\n"
            f"(In production, this would be sent to your copier team's chat)"
        )
        
        # Record this in the database
        db.add_user({
            "user_id": user_id,
            "copier_forwarded": True,
            "copier_forwarded_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def test_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test command to directly check account validation."""
    user_id = update.effective_user.id
    
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /testaccount <account_number>")
        return
    
    account_number = context.args[0]
    
    await update.message.reply_text(f"Testing account number: {account_number}")
    
    # Test validation
    is_valid = auth.validate_account_format(account_number)
    await update.message.reply_text(f"Format validation result: {is_valid}")
    
    # Test verification
    try:
        verification_result = auth.verify_account(account_number, user_id)
        await update.message.reply_text(f"Verification result: {verification_result}")
    except Exception as e:
        await update.message.reply_text(f"Verification error: {e}")
    
    await update.message.reply_text("Test completed.")

async def debug_db_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check database status and user entries."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # List all users in database
    try:
        all_users = db.users_df
        user_count = all_users.height if hasattr(all_users, 'height') else "Unknown"
        
        # Check specific user if ID provided
        if context.args and len(context.args) > 0:
            user_id = int(context.args[0])
            user_info = db.get_user(user_id)
            
            if user_info:
                await update.message.reply_text(
                    f"✅ User ID {user_id} found in database:\n\n{user_info}"
                )
            else:
                # Try alternate methods to find user
                await update.message.reply_text(
                    f"⚠️ User ID {user_id} not found with db.get_user\n\n"
                    f"Checking raw dataframe..."
                )
                
                # Try direct dataframe filter
                try:
                    user_rows = all_users.filter(pl.col("user_id") == user_id)
                    if user_rows.height > 0:
                        await update.message.reply_text(
                            f"Found user in raw dataframe:\n\n{user_rows.row(0)}"
                        )
                    else:
                        await update.message.reply_text(
                            f"User {user_id} not found in raw dataframe"
                        )
                except Exception as e:
                    await update.message.reply_text(f"Error filtering dataframe: {e}")
        else:
            # Show database stats
            await update.message.reply_text(
                f"📊 Database Status 📊\n\n"
                f"Total users: {user_count}\n"
                f"Column count: {len(all_users.columns) if hasattr(all_users, 'columns') else 'Unknown'}\n\n"
                f"Use /debugdb <user_id> to check a specific user"
            )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Database check failed: {e}")

async def reset_user_registration_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to reset a user's registration status."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /resetuser <user_id>")
        return
    
    try:
        user_id = int(context.args[0])
        
        # Reset user's registration status
        db.add_user({
            "user_id": user_id,
            "is_verified": False,
            "registration_confirmed": False,
            "vip_access_granted": False,
            "trading_account": None,
            "reset_by_admin": True,
            "reset_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        await update.message.reply_text(
            f"✅ User {user_id} registration status has been reset. They can now register again."
        )
        
    except ValueError:
        await update.message.reply_text("Invalid user ID format.")
    except Exception as e:
        await update.message.reply_text(f"Error resetting user: {e}")



# -------------------------------------- VFX Messages ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def send_hourly_welcome(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send hour-specific market session messages to the group and channel."""
    current_hour = datetime.now().hour
    current_weekday = datetime.now().weekday()
    
    # Only send messages at market opening hours on weekdays (0-4 are Monday-Friday)
    if current_hour not in [0, 8, 13] or current_weekday > 4:  # Skip weekends (5=Saturday, 6=Sunday)
        return  # Exit if not a market opening hour or if it's weekend
    
    # Get the appropriate session message
    if current_hour == 0:
        message = vfx_scheduler.get_welcome_message(0)  # Tokyo session
        session_name = "Tokyo"
    elif current_hour == 8:
        message = vfx_scheduler.get_welcome_message(8)  # London session
        session_name = "London"
    elif current_hour == 13:
        message = vfx_scheduler.get_welcome_message(13)  # NY session
        session_name = "New York"    

    
    # Send to channel
    try:
        await context.bot.send_message(
            chat_id=MAIN_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Sent {session_name} session message at {datetime.now()} (Weekday: {current_weekday})")
    except Exception as e:
        logger.error(f"Failed to send {session_name} session message: {e}")
    
    # Update analytics
    try:
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to update analytics: {e}")

async def send_giveaway_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send giveaway messages at specific hours."""
    # Get the current hour to determine which message to send
    current_hour = datetime.now().hour
    current_weekday = datetime.now().weekday()
    
    # Skip weekends if needed
    if current_weekday > 4:  # Skip weekends (5=Saturday, 6=Sunday)
        logger.info(f"Skipping giveaway message on weekend (Weekday: {current_weekday})")
        return
    
    # Determine which message to send based on the hour
    if current_hour == 15:
        message = vfx_scheduler.get_welcome_message(15)
        message_type = "Daily Giveaway Announcement"
    elif current_hour == 16:
        message = vfx_scheduler.get_welcome_message(16)
        message_type = "Giveaway Countdown"
    elif current_hour == 17:
        message = vfx_scheduler.get_welcome_message(17)
        message_type = "Giveaway Winner Announcement"
    else:
        logger.error(f"Unexpected hour for giveaway message: {current_hour}")
        return
    
    # Log before sending
    logger.info(f"Preparing to send {message_type} at {datetime.now()}")
    
    # Send to channel
    try:
        await context.bot.send_message(
            chat_id=MAIN_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'
        )
        logger.info(f"Successfully sent {message_type} at {datetime.now()}")
    except Exception as e:
        logger.error(f"Failed to send {message_type}: {e}")
    
    # Update analytics
    try:
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to update analytics: {e}")

async def send_interval_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the next interval message to the channel."""
    # Get the next interval message
    message = vfx_scheduler.get_next_interval_message()
    
    try:
        # Send to channel with HTML parsing enabled
        await context.bot.send_message(
            chat_id=MAIN_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'  # Enable HTML formatting
        )
        logger.info(f"Sent interval message at {datetime.now()}")
    except Exception as e:
        logger.error(f"Failed to send interval message: {e}")
    
    # Update analytics
    try:
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to update analytics: {e}")

async def send_strategy_interval_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the next interval message to the strategy channel."""
    # Get the next interval message from the strategy scheduler
    try:
        message = strategyChannel_scheduler.get_next_interval_message()
        
        print(f"Retrieved strategy interval message: {message[:50]}...")
        
        # Send to strategy channel with HTML parsing enabled
        await context.bot.send_message(
            chat_id=STRATEGY_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'  # Enable HTML formatting
        )
        logger.info(f"Sent strategy interval message to channel {STRATEGY_CHANNEL_ID} at {datetime.now()}")
        
        # Update analytics
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to send strategy interval message: {e}")
        print(f"Error in send_strategy_interval_message: {e}")

async def send_prop_interval_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the next interval message to the strategy channel."""
    # Get the next interval message from the strategy scheduler
    try:
        message = propChannel_scheduler.get_next_interval_message()
        
        print(f"Retrieved strategy interval message: {message[:50]}...")
        
        # Send to strategy channel with HTML parsing enabled
        await context.bot.send_message(
            chat_id=PROP_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'  # Enable HTML formatting
        )
        logger.info(f"Sent strategy interval message to channel {PROP_CHANNEL_ID} at {datetime.now()}")
        
        # Update analytics
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to send strategy interval message: {e}")
        print(f"Error in send_strategy_interval_message: {e}")

async def send_signals_interval_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the next interval message to the strategy channel."""
    # Get the next interval message from the strategy scheduler
    try:
        message = signalsChannel_scheduler.get_next_interval_message()
        
        print(f"Retrieved strategy interval message: {message[:50]}...")
        
        # Send to strategy channel with HTML parsing enabled
        await context.bot.send_message(
            chat_id=SIGNALS_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'  # Enable HTML formatting
        )
        logger.info(f"Sent strategy interval message to channel {SIGNALS_CHANNEL_ID} at {datetime.now()}")
        
        # Update analytics
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to send strategy interval message: {e}")
        print(f"Error in send_strategy_interval_message: {e}")

async def send_ed_interval_message(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the next interval message to the strategy channel."""
    # Get the next interval message from the strategy scheduler
    try:
        message = educationChannel_scheduler.get_next_interval_message()
        
        print(f"Retrieved strategy interval message: {message[:50]}...")
        
        # Send to strategy channel with HTML parsing enabled
        await context.bot.send_message(
            chat_id=ED_CHANNEL_ID, 
            text=message,
            parse_mode='HTML'  # Enable HTML formatting
        )
        logger.info(f"Sent strategy interval message to channel {ED_CHANNEL_ID} at {datetime.now()}")
        
        # Update analytics
        db.update_analytics(messages_sent=1)
    except Exception as e:
        logger.error(f"Failed to send strategy interval message: {e}")
        print(f"Error in send_strategy_interval_message: {e}")

async def manage_messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to manage scheduled messages."""
    if not await is_user_admin(update, context):
        await update.message.reply_text("This command is only available to admins.")
        return
    
    # Check arguments
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "Usage: /managemsg <action> [arguments]\n\n"
            "Actions:\n"
            "- view hourly/interval/all: View messages\n"
            "- add hourly <hour> <message>: Add hourly message\n"
            "- add interval <name> <message>: Add interval message\n"
            "- remove hourly/interval <key>: Remove message\n"
            "- reset: Reset interval rotation\n"
        )
        return
    
    action = args[0].lower()
    
    if action == "view":
        # View messages
        if len(args) < 2:
            await update.message.reply_text("Please specify what to view: hourly, interval, or all")
            return
        
        view_type = args[1].lower()
        
        if view_type == "hourly":
            hourly_msgs = vfx_scheduler.get_all_messages("hourly")
            if hourly_msgs:
                message = "Hourly Welcome Messages:\n\n"
                for hour, msg in sorted(hourly_msgs.items()):
                    message += f"{hour}: {msg[:50]}...\n\n"
                
                # Split into multiple messages if too long
                if len(message) > 4000:
                    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(message)
            else:
                await update.message.reply_text("No hourly messages configured.")
        
        elif view_type == "interval":
            interval_msgs = vfx_scheduler.get_all_messages("interval")
            if interval_msgs:
                message = "Interval Messages:\n\n"
                for msg in interval_msgs:
                    message += f"{msg['name']}: {msg['message'][:50]}...\n\n"
                
                # Split into multiple messages if too long
                if len(message) > 4000:
                    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(message)
            else:
                await update.message.reply_text("No interval messages configured.")
        
        elif view_type == "all":
            all_msgs = vfx_scheduler.get_all_messages()
            await update.message.reply_text("All message types available. Use 'view hourly' or 'view interval' to see specific messages.")
        
        else:
            await update.message.reply_text("Invalid view type. Use hourly, interval, or all.")
    
    elif action == "add":
        # Add message
        if len(args) < 3:
            await update.message.reply_text("Insufficient arguments for add command.")
            return
        
        msg_type = args[1].lower()
        
        if msg_type == "hourly":
            try:
                hour = int(args[2])
                message = " ".join(args[3:])
                
                if vfx_scheduler.add_message("hourly", hour, message):
                    await update.message.reply_text(f"Added hourly message for {hour}:00")
                else:
                    await update.message.reply_text("Failed to add hourly message.")
            except ValueError:
                await update.message.reply_text("Hour must be a number between 0 and 23")
        
        elif msg_type == "interval":
            if len(args) < 4:
                await update.message.reply_text("Insufficient arguments for add interval command.")
                return
            
            name = args[2]
            message = " ".join(args[3:])
            
            if vfx_scheduler.add_message("interval", name, message):
                await update.message.reply_text(f"Added interval message '{name}'")
            else:
                await update.message.reply_text("Failed to add interval message.")
        
        else:
            await update.message.reply_text("Invalid message type. Use hourly or interval.")
    
    elif action == "remove":
        # Remove message
        if len(args) < 3:
            await update.message.reply_text("Insufficient arguments for remove command.")
            return
        
        msg_type = args[1].lower()
        key = args[2]
        
        if msg_type == "hourly":
            if vfx_scheduler.remove_message("hourly", key):
                await update.message.reply_text(f"Removed hourly message for {key}")
            else:
                await update.message.reply_text("Failed to remove hourly message.")
        
        elif msg_type == "interval":
            if vfx_scheduler.remove_message("interval", key):
                await update.message.reply_text(f"Removed interval message '{key}'")
            else:
                await update.message.reply_text("Failed to remove interval message.")
        
        else:
            await update.message.reply_text("Invalid message type. Use hourly or interval.")
    
    elif action == "reset":
        # Reset interval rotation
        vfx_scheduler.reset_interval_rotation()
        await update.message.reply_text("Reset interval message rotation.")
    
    else:
        await update.message.reply_text("Invalid action. Use view, add, remove, or reset.")


# -------------------------------------- DMs Handlers ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def send_instructions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Send Instructions' button callback for hidden users."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received instruction callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("instr_"):
        try:
            session_id = callback_data[6:]  # Remove 'instr_' prefix
            print(f"Sending instructions for session: {session_id}")
            
            # Get hidden user info
            if "hidden_users" in context.bot_data and session_id in context.bot_data["hidden_users"]:
                user_name = context.bot_data["hidden_users"][session_id]["name"]
                
                # Add new option to directly initiate the registration
                keyboard = [
                    [InlineKeyboardButton("Initialize Registration", callback_data=f"init_reg_{session_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text=f"Options for {user_name}:\n\n"
                         f"1. Click 'Initialize Registration' to have the bot send registration questions directly to this user.\n\n"
                         f"Or copy and paste these simple instructions to the user:\n\n"
                         f"To set up your trading profile, please send a message directly to our bot @YourBotUsername",
                    reply_markup=reply_markup
                )
                
                print(f"Instructions options provided for {user_name}")
            else:
                await query.edit_message_text(
                    text="⚠️ User session information not found. Please try forwarding a new message."
                )
        except Exception as e:
            print(f"Error processing instruction callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error generating instructions: {e}"
            )

async def initialize_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Initialize Registration' button callback."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received initialize registration callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("init_reg_"):
        try:
            session_id = callback_data[9:]  # Remove 'init_reg_' prefix
            print(f"Initializing registration for session: {session_id}")
            
            # Get hidden user info
            if "hidden_users" in context.bot_data and session_id in context.bot_data["hidden_users"]:
                user_name = context.bot_data["hidden_users"][session_id]["name"]
                # Get the original message content
                original_message = context.bot_data["hidden_users"][session_id]["last_message"]
                
                # This is where we'd normally need the user's chat ID to message them directly
                # Since this is a hidden user, we can't get their chat ID directly
                
                await query.edit_message_text(
                    text=f"✅ Registration initiated for {user_name}\n\n"
                         f"Since this user has privacy settings enabled, you need to:\n\n"
                         f"1. Open their chat\n"
                         f"2. Copy and paste this message:\n\n"
                         f"{PRIVATE_WELCOME_MSG}\n\n"
                         f"First, what's your risk appetite from 1-10?\n\n"
                         f"(Unfortunately, due to Telegram's privacy settings, the bot can't message them first)"
                )
                
            else:
                await query.edit_message_text(
                    text="⚠️ User session information not found. Please try forwarding a new message."
                )
        except Exception as e:
            print(f"Error processing initialize registration callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error initializing registration: {e}"
            )

async def send_registration_form_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Send Registration Form' button callback."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received send form callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("send_form_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Sending registration form to user ID: {user_id}")
            
            # Store the current conversation user
            context.user_data["current_user_conv"] = user_id
            
            # Get user info
            user_info = db.get_user(user_id)
            user_name = user_info.get("first_name", "User") if user_info else "User"
            
            # Send welcome message to user with the registration questions
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"{PRIVATE_WELCOME_MSG}\n\nFirst, what's your risk appetite from 1-10?"
                )
                
                # Confirm to admin
                await query.edit_message_text(
                    text=f"✅ Registration form sent to {user_name} (ID: {user_id}).\n\n"
                    f"The risk appetite question has been sent to the user.\n\n"
                    f"Any regular messages you send to me now will be forwarded to {user_name}.\n"
                    f"Use /endchat to end this conversation when finished."
                )
                
                print(f"Successfully sent registration form to user {user_id}")
            except Exception as e:
                print(f"Error sending message to user: {e}")
                await query.edit_message_text(
                    text=f"⚠️ Failed to send registration form to user: {e}"
                )
        except Exception as e:
            print(f"Error processing callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error processing request: {e}"
            )

async def start_casual_conversation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Start Casual Conversation' button callback."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received start casual conversation callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("start_casual_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Starting casual conversation with user ID: {user_id}")
            
            # Store the current conversation user
            context.user_data["current_user_conv"] = user_id
            
            # Get user info
            user_info = db.get_user(user_id)
            user_name = user_info.get("first_name", "User") if user_info else "User"
            
            # Send a friendly greeting to user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Hello {user_name}! Thanks for reaching out. One of our trading specialists will be assisting you today. How can we help you with your trading journey?"
                )
                
                # Confirm to admin
                await query.edit_message_text(
                    text=f"✅ Started casual conversation with {user_name} (ID: {user_id}).\n\n"
                    f"A friendly greeting has been sent to the user.\n\n"
                    f"Any regular messages you send to me now will be forwarded to {user_name}.\n"
                    f"Use /endchat to end this conversation when finished.\n\n"
                    f"If you want to switch to the registration form later, use /startform"
                )
                
                print(f"Successfully started casual conversation with user {user_id}")
            except Exception as e:
                print(f"Error sending message to user: {e}")
                await query.edit_message_text(
                    text=f"⚠️ Failed to start casual conversation with user: {e}"
                )
        except Exception as e:
            print(f"Error processing callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error processing request: {e}"
            )

async def copy_template_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the template copy button callbacks."""
    query = update.callback_query
    await query.answer(text="Message template copied to clipboard!", show_alert=False)
    
    callback_data = query.data
    
    if callback_data.startswith("copy_reg_"):
        user_id = int(callback_data.split("_")[2])
        template = context.user_data.get("reg_template", "Template not found")
        
        await query.edit_message_text(
            text=f"✅ Registration template ready to paste:\n\n{template}\n\n"
                 f"After the user clicks the link and connects with the bot, "
                 f"you'll be notified and can communicate with them through the bot."
        )
    
    elif callback_data.startswith("copy_casual_"):
        user_id = int(callback_data.split("_")[2])
        template = context.user_data.get("casual_template", "Template not found")
        
        await query.edit_message_text(
            text=f"✅ Casual template ready to paste:\n\n{template}\n\n"
                 f"After the user clicks the link and connects with the bot, "
                 f"you'll be notified and can communicate with them through the bot."
        )








# -------------------------------------- MAIN ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
def main() -> None:
    """Start both manager and signal bots from same main function."""
    print("Starting VFX Trading Bot System...")
    print("📋 Manager Bot: User registration, admin tools, scheduled messages")
    print("🤖 Signal Bot: Trading signals, MT5 connections, signal analysis")
    print(f"Admin ID is set to {ADMIN_USER_ID}")
    
    mysql_db = get_mysql_connection()
    if mysql_db.is_connected():
        print("✅ MySQL database ready for real-time account verification")
    else:
        print("⚠️ MySQL connection failed - will use CSV fallback")
    
    # ===== CREATE BOTH BOTS =====
    # Manager bot 
    manager_application = Application.builder().token(BOT_MANAGER_TOKEN).build()
    
    # Signal bot 
    signal_bot = SignalBot(BOT_ALGO_TOKEN, SIGNALS_CHANNEL_ID)
    
    # Custom filter for forwarded messages
    forwarded_filter = ForwardedMessageFilter()
    
    # ===== MANAGER BOT HANDLERS (All existing handlers) =====
    manager_application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_USER_ID) & ~filters.COMMAND,
        handle_admin_forward,
        block=True
    ))

    manager_application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_USER_ID) & filters.TEXT & ~forwarded_filter & ~filters.COMMAND,
        handle_admin_forward,
        block=True
    ))
    
    # All callback handlers (VIP, copier, profile, etc.)
    manager_application.add_handler(CallbackQueryHandler(add_to_vip_callback, pattern=r"^add_vip_"))
    manager_application.add_handler(CallbackQueryHandler(forward_to_copier_callback, pattern=r"^forward_copier_"))
    manager_application.add_handler(CallbackQueryHandler(copier_team_action_callback, pattern=r"^copier_(added|rejected)_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(copier_team_action_callback, pattern=r"^contact_user_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(start_user_conversation_callback, pattern=r"^start_conv_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(view_profile_callback, pattern=r"^view_profile_"))
    manager_application.add_handler(CallbackQueryHandler(generate_welcome_link_callback, pattern=r"^gen_welcome_"))
    manager_application.add_handler(CallbackQueryHandler(handle_grant_vip_access_callbacks, pattern=r"^grant_vip_(signals|strategy|all)_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(check_my_status_callback, pattern=r"^check_my_status$"))
    manager_application.add_handler(CallbackQueryHandler(handle_privacy_welcome_link, pattern=r"^gen_welcome_privacy$"))
    manager_application.add_handler(CallbackQueryHandler(show_privacy_instructions, pattern=r"^show_privacy_instructions$"))
    manager_application.add_handler(CallbackQueryHandler(explain_services_callback, pattern=r"^explain_services$"))
    manager_application.add_handler(CallbackQueryHandler(generate_connection_link_callback, pattern=r"^gen_connect_link_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(get_contact_info_callback, pattern=r"^get_contact_info_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(end_conversation_callback, pattern=r"^end_conv_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(handle_vip_confirmation_callbacks, pattern=r"^confirm_vip_"))

    # Admin balance check callbacks
    manager_application.add_handler(CallbackQueryHandler(
        admin_check_balance_callback, 
        pattern=r"^admin_check_balance_\d+$"
    ))

    # Admin verification callbacks
    manager_application.add_handler(CallbackQueryHandler(
        admin_verify_user_callback, 
        pattern=r"^admin_verify_\d+$"
    ))

    # Admin account details callbacks
    manager_application.add_handler(CallbackQueryHandler(
        admin_account_details_callback, 
        pattern=r"^admin_account_details_\d+$"
    ))
    
    
    # User Management System #
    manager_application.add_handler(CommandHandler("myaccount", my_account_command))
    manager_application.add_handler(CallbackQueryHandler(edit_profile_menu_callback, pattern=r"^edit_profile_menu$"))
    manager_application.add_handler(CallbackQueryHandler(edit_risk_level_callback, pattern=r"^edit_risk_level$"))
    manager_application.add_handler(CallbackQueryHandler(update_risk_level_callback, pattern=r"^update_risk_(low|medium|high)$"))
    manager_application.add_handler(CallbackQueryHandler(my_vip_services_callback, pattern=r"^my_vip_services$"))
    manager_application.add_handler(CallbackQueryHandler(back_to_dashboard_callback, pattern=r"^back_to_dashboard$"))
    manager_application.add_handler(CallbackQueryHandler(help_menu_callback, pattern=r"^help_menu$"))
    
    manager_application.add_handler(CallbackQueryHandler(need_new_account_callback, pattern=r"^need_new_account$"))
    manager_application.add_handler(CallbackQueryHandler(account_created_callback, pattern=r"^account_created$"))
    manager_application.add_handler(CallbackQueryHandler(retry_account_number_callback, pattern=r"^retry_account_number$"))
    manager_application.add_handler(CallbackQueryHandler(wait_and_retry_callback, pattern=r"^wait_and_retry$"))
    
    manager_application.add_handler(CallbackQueryHandler(edit_deposit_amount_callback, pattern=r"^edit_deposit_amount$"))
    manager_application.add_handler(CallbackQueryHandler(edit_trading_interest_callback, pattern=r"^edit_trading_interest$"))
    manager_application.add_handler(CallbackQueryHandler(update_deposit_amount_callback, pattern=r"^update_deposit_\d+$"))
    manager_application.add_handler(CallbackQueryHandler(update_trading_interest_callback, pattern=r"^update_interest_(signals|strategy|all)$"))
    manager_application.add_handler(CallbackQueryHandler(custom_deposit_edit_callback, pattern=r"^custom_deposit_edit$"))
    
    # Account verification choice handlers
    manager_application.add_handler(CallbackQueryHandler(have_account_callback, pattern=r"^have_account$"))
    manager_application.add_handler(CallbackQueryHandler(explain_vortexfx_callback, pattern=r"^explain_vortexfx$"))
    manager_application.add_handler(CallbackQueryHandler(help_find_account_callback, pattern=r"^help_find_account$"))
    
    # Account creation flow handlers  
    manager_application.add_handler(CallbackQueryHandler(creation_help_callback, pattern=r"^creation_help$"))
    manager_application.add_handler(CallbackQueryHandler(waiting_for_email_callback, pattern=r"^waiting_for_email$"))
    manager_application.add_handler(CallbackQueryHandler(try_later_callback, pattern=r"^try_later$"))
    manager_application.add_handler(CallbackQueryHandler(complete_setup_callback, pattern=r"^complete_setup$"))
    manager_application.add_handler(CallbackQueryHandler(back_to_services_callback, pattern=r"^back_to_services$"))
    
    manager_application.add_handler(CallbackQueryHandler(
        handle_all_admin_callbacks, 
        pattern=r"^(admin_|refresh_dashboard)"
    ))
    
    # manager_application.add_handler(CallbackQueryHandler(
    #     admin_grant_vip_signals_callback, 
    #     pattern=r"^admin_grant_vip_signals_\d+$"
    # ))
    # manager_application.add_handler(CallbackQueryHandler(
    #     admin_grant_vip_strategy_callback, 
    #     pattern=r"^admin_grant_vip_strategy_\d+$"
    # ))
    # manager_application.add_handler(CallbackQueryHandler(
    #     admin_grant_vip_all_callback, 
    #     pattern=r"^admin_grant_vip_all_\d+$"
    # ))
    
    # User registration flow
    manager_application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_auto_welcome_response,
        block=False  
    ))

    manager_application.add_handler(CallbackQueryHandler(
        handle_auto_welcome_response,
        pattern=r"^(risk_|interest_|deposit_exact_|choose_deposit_amount|custom_amount|request_vip_|restart_process|speak_advisor|check_balance_now|start_guided).*$"
    ))

    # Manual entry conversation
    manual_entry_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(manual_entry_callback, pattern=r"^manual_")],
        states={
            RISK_APPETITE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, risk_appetite_manual)],
            DEPOSIT_AMOUNT_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_manual)],
            TRADING_ACCOUNT_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, trading_account_manual)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="manual_entry_conversation",
    )
    manager_application.add_handler(manual_entry_handler)
    
    # ===== ADMIN COMMANDS =====
    # Manager bot commands
    manager_application.add_handler(CommandHandler("users", list_users_command))
    manager_application.add_handler(CommandHandler("endchat", end_user_conversation))
    manager_application.add_handler(CommandHandler("startform", start_form_command))
    manager_application.add_handler(CommandHandler("addtovip", add_to_vip_command))
    manager_application.add_handler(CommandHandler("forwardmt5", forward_mt5_command))
    manager_application.add_handler(CommandHandler("testaccount", test_account_command))
    manager_application.add_handler(CommandHandler("debugdb", debug_db_command))
    manager_application.add_handler(CommandHandler("resetuser", reset_user_registration_command))
    manager_application.add_handler(CommandHandler("debugvip", debug_vip_status_command))
    manager_application.add_handler(CommandHandler("admin_panel", admin_dashboard_command))
    manager_application.add_handler(CommandHandler("admin", admin_dashboard_command))
    manager_application.add_handler(CommandHandler("manage_users", enhanced_users_command))
    
    # MySQL commands
    manager_application.add_handler(CommandHandler("testmysql", test_mysql_command))
    manager_application.add_handler(CommandHandler("searchaccount", search_account_command))
    manager_application.add_handler(CommandHandler("checktable", check_table_command))
    manager_application.add_handler(CommandHandler("debugreg", debug_registrations_command))
    manager_application.add_handler(CommandHandler("checkmyaccounts", check_my_accounts_command))
    manager_application.add_handler(CommandHandler("quickbalance", quick_balance_command))
    manager_application.add_handler(CommandHandler("simpleregcheck", simple_reg_check_command))
    manager_application.add_handler(CommandHandler("testrecent", test_recent_fix_command))
    manager_application.add_handler(CommandHandler("testtimestamp", test_timestamp_approach))
    manager_application.add_handler(CommandHandler("recentbylogin", recent_accounts_by_login_command))
    manager_application.add_handler(CommandHandler("recentbytime", recent_accounts_timestamp_command))
    manager_application.add_handler(CommandHandler("newest", newest_accounts_simple_command))
    manager_application.add_handler(CommandHandler("debugzero", debug_zero_dates_command))
    manager_application.add_handler(CommandHandler("checkmysqlmode", check_mysql_mode_command))
    manager_application.add_handler(CommandHandler("findthreshold", find_recent_login_threshold_command))
    manager_application.add_handler(CommandHandler("checkperms", check_user_permissions_command))
    manager_application.add_handler(CommandHandler("diagnoseaccess", diagnose_account_access_command))
    manager_application.add_handler(CommandHandler("testsafe", test_safe_login_query_command))  
    manager_application.add_handler(CommandHandler("decodetimestamp", decode_mt5_timestamp_command))
    manager_application.add_handler(CommandHandler("recentaccounts", recent_accounts_final_command)) 
    manager_application.add_handler(CommandHandler("currenttable", compare_current_table_command))
    manager_application.add_handler(CommandHandler("showtables", show_all_tables_command))
    manager_application.add_handler(CommandHandler("searchusertables", search_user_tables_command))
    manager_application.add_handler(CommandHandler("showdatabases", show_all_databases_command))
    manager_application.add_handler(CommandHandler("check_table", check_table_for_high_accounts_command))
    manager_application.add_handler(CommandHandler("checkaccounts", check_mt5_accounts_table_command))
    manager_application.add_handler(CommandHandler("compareusers", compare_users_vs_accounts_command))
    manager_application.add_handler(CommandHandler("sampleaccounts", check_accounts_table_sample_command))
    
        
    
    manager_application.add_handler(MessageHandler(filters.ALL, silent_update_logger), group=999)
    
    

    # Auth conversation
    auth_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(auth_callback, pattern=r"^auth_\d+$")],
        states={
            CAPTCHA_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha_response)],
            TRADING_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_account_verification)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=False,
        name="auth_conversation",
    )
    manager_application.add_handler(auth_conv_handler)

    # Basic commands
    manager_application.add_handler(CommandHandler("start", start))
    manager_application.add_handler(CommandHandler("help", help_command))
    manager_application.add_handler(CommandHandler("stats", stats_command))
    manager_application.add_handler(CommandHandler("managemsg", manage_messages_command))
    manager_application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Error handler
    manager_application.add_error_handler(error_handler)
    
    # ===== SCHEDULED JOBS =====
    job_queue = manager_application.job_queue
    
    # ===== MANAGER BOT JOBS (Non-signal jobs) =====
    job_queue.run_daily(send_daily_signup_report, time=time(hour=0, minute=0))
    job_queue.run_daily(send_daily_response_report, time=time(hour=23, minute=0))
    job_queue.run_once(log_all_chats, 5)
    
    # Market session messages, giveaways, channel messages (all existing)
    now = datetime.now()
    
    # Market session messages
    tokyo_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if tokyo_time <= now:
        tokyo_time += timedelta(days=1)
    seconds_until_tokyo = (tokyo_time - now).total_seconds()
    
    london_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if london_time <= now:
        london_time += timedelta(days=1)
    seconds_until_london = (london_time - now).total_seconds()
    
    ny_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
    if ny_time <= now:
        ny_time += timedelta(days=1)
    seconds_until_ny = (ny_time - now).total_seconds()
    
    job_queue.run_once(send_hourly_welcome, seconds_until_tokyo)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=0, minute=0))
    job_queue.run_once(send_hourly_welcome, seconds_until_london)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=8, minute=0))
    job_queue.run_once(send_hourly_welcome, seconds_until_ny)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=13, minute=0))

    # Giveaway messages
    job_queue.run_daily(send_giveaway_message, time=time(hour=15, minute=0))
    job_queue.run_daily(send_giveaway_message, time=time(hour=16, minute=0))
    job_queue.run_daily(send_giveaway_message, time=time(hour=17, minute=0))
    
    # Channel interval messages (all existing)
    minutes_now = now.minute
    minutes_until_next_interval = 21 - (minutes_now % 21)
    if minutes_until_next_interval == 0:
        minutes_until_next_interval = 21
    
    next_interval = now + timedelta(minutes=minutes_until_next_interval)
    next_interval = next_interval.replace(second=0, microsecond=0)
    seconds_until_next_interval = (next_interval - now).total_seconds()
    
    job_queue.run_repeating(
        send_interval_message, 
        interval=timedelta(minutes=21), 
        first=seconds_until_next_interval
    )
    
    
    """---------------------------------
         Strategy Channel Messages
    ------------------------------------"""
     # Schedule strategy channel messages - every 45 minutes (different frequency)
    minutes_until_strategy = 30 - (minutes_now % 30)
    if minutes_until_strategy == 0:
        minutes_until_strategy = 30
    
    next_strategy = now + timedelta(minutes=minutes_until_strategy)
    next_strategy = next_strategy.replace(second=0, microsecond=0)
    seconds_until_strategy = (next_strategy - now).total_seconds()
    
    job_queue.run_repeating(
        send_strategy_interval_message,
        interval=timedelta(minutes=30),
        first=seconds_until_strategy
    )
    
    """---------------------------------
         Prop-Capital Channel Messages
    ------------------------------------"""
    minutes_until_propMessage = 35 - (minutes_now % 35)
    if minutes_until_propMessage == 0:
        minutes_until_propMessage = 35
    
    next_strategy = now + timedelta(minutes=minutes_until_propMessage)
    next_strategy = next_strategy.replace(second=0, microsecond=0)
    seconds_until_strategy = (next_strategy - now).total_seconds()
    
    job_queue.run_repeating(
        send_prop_interval_message,
        interval=timedelta(minutes=35),
        first=seconds_until_strategy
    )
    
    """---------------------------------
         Signals Channel Messages
    ------------------------------------"""
    minutes_until_signals = 36 - (minutes_now % 36)
    if minutes_until_signals == 0:
        minutes_until_signals = 36
    
    next_strategy = now + timedelta(minutes=minutes_until_signals)
    next_strategy = next_strategy.replace(second=0, microsecond=0)
    seconds_until_strategy = (next_strategy - now).total_seconds()
    
    job_queue.run_repeating(
        send_signals_interval_message,
        interval=timedelta(minutes=36),
        first=seconds_until_strategy
    )
    
    """---------------------------------
         Education Channel Messages
    ------------------------------------"""
    minutes_until_educationMessages = 40 - (minutes_now % 40)
    if minutes_until_educationMessages == 0:
        minutes_until_educationMessages = 40
    
    next_strategy = now + timedelta(minutes=minutes_until_educationMessages)
    next_strategy = next_strategy.replace(second=0, microsecond=0)
    seconds_until_strategy = (next_strategy - now).total_seconds()
    
    job_queue.run_repeating(
        send_ed_interval_message,
        interval=timedelta(minutes=40),
        first=seconds_until_strategy
    )
    
    
    """---------------------------------
         Signal Jobs
    ------------------------------------"""
    
    job_queue.run_once(lambda context: signal_bot.init_signal_system(), 10)
    
    # Signal checks every 5 minutes
    job_queue.run_repeating(
        lambda context: signal_bot.check_and_send_signals(),
        interval=300,
        first=60
    )
    
    # Signal status reports every 6 hours
    job_queue.run_repeating(
        lambda context: signal_bot.report_signal_system_status(),
        interval=21600,
        first=600
    )
    
    # Trailing stops every 2 minutes
    job_queue.run_repeating(
        lambda context: signal_bot.apply_trailing_stops(),  # This already exists!
        interval=120,
        first=60
    )

    # Daily stats at 22:00
    job_queue.run_daily(
        lambda context: signal_bot.send_daily_stats(),
        time=time(hour=22, minute=0)
    )
    
    # ===== LOGGING =====
    logger.info("📋 Manager Bot scheduled jobs:")
    logger.info(f"- Hourly welcome messages")
    logger.info(f"- Channel interval messages") 
    logger.info(f"- Giveaway messages")
    logger.info(f"- Daily reports")
    
    logger.info("🤖 Signal Bot scheduled jobs:")
    logger.info(f"- Signal checks every 5 minutes")
    logger.info(f"- Trailing stops every 2 minutes")
    logger.info(f"- Status reports every 6 hours")
    logger.info(f"- Daily stats at 22:00")
    
    print("✅ Both bots configured and ready!")
    print("📋 Manager Bot handles: Registration, Admin, VIP, Channels")
    print("🤖 Signal Bot handles: Signals, MT5, Trading, Statistics")
    
    # ===== RUN MANAGER BOT  ===== #
    import threading
    
    # Start signal bot in background thread 
    threading.Thread(target=signal_bot.start_polling, daemon=True).start()
    
    # Start manager bot in main thread
    manager_application.run_polling(allowed_updates=Update.ALL_TYPES)


# Main running name # 
if __name__ == "__main__":
    main()