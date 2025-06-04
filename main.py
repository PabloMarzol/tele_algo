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
                "After registration, you can always check your status and edit your profile using:\n\n"
                "<b>/myaccount</b> - Your personal dashboard 📊\n\n"
                "Let's get started! 🚀\n\n",
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
    
    # Small delay to show loading (optional)
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
    """Handle messages forwarded by the admin from users."""
    # Debug output
    print(f"Received message in chat {update.effective_chat.id} from user {update.effective_user.id}")
    
    # Check if this is the admin's chat
    if update.effective_user.id not in ADMIN_USER_ID:
        print("Not from admin, skipping admin forward handler")
        return
    
    # Check for forwarded message
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
    
    
    message_text = update.message.text if update.message.text else ""
    # Try to determine source channel
    if hasattr(update.message, 'forward_from_chat') and update.message.forward_from_chat:
        # If we have direct information about the source chat
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
            # Message likely related to trading signals
            forwarded_from_channel = "signals_channel"
            print(f"Message content suggests it's from signals channel")
        else:
            # Default to main channel if can't determine
            forwarded_from_channel = "main_channel"
            print(f"Defaulting to main channel as source")
    # If it's a forwarded message
    if is_forwarded:
        print(f"This is a forwarded message from {original_sender_name}")
        
        # Handle user with visible info
        if original_sender_id:
            # Store original sender ID for future communication with source channel info
            user_data = {
                "user_id": original_sender_id,
                "first_name": original_sender_name,
                "last_name": "" if not hasattr(update.message.forward_origin.sender_user, 'last_name') else update.message.forward_origin.sender_user.last_name,
                "username": "" if not hasattr(update.message.forward_origin.sender_user, 'username') else update.message.forward_origin.sender_user.username,
                "source_channel": forwarded_from_channel,  # Set source channel
                "first_contact_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            db.add_user(user_data)
            
            # AUTOMATICALLY SEND WELCOME MESSAGE TO USER - CUSTOMIZE BASED ON SOURCE CHANNEL
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
                
                # Send the welcome message directly to the user
                # Create buttons for welcome message
                keyboard = [
                    [InlineKeyboardButton("🚀 Start Guided Setup", callback_data="start_guided")],
                    # [
                    #     InlineKeyboardButton("Low Risk", callback_data="risk_low"),
                    #     InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
                    #     InlineKeyboardButton("High Risk", callback_data="risk_high")
                    # ],
                    [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                # Format same text with HTML
                formatted_msg = welcome_msg  # Keep original message text

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
                        # Create "start bot" deep link - this is a special link format that opens the bot when clicked
                        bot_username = await context.bot.get_me()
                        bot_username = bot_username.username
                        start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
                        
                        # Create keyboard with copy buttons
                        keyboard = [
                            [InlineKeyboardButton("Generate Welcome Link", callback_data=f"gen_welcome_{original_sender_id}")],
                            [InlineKeyboardButton("View User Profile", callback_data=f"view_profile_{original_sender_id}")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            f"⚠️ Cannot message {original_sender_name} directly due to Telegram privacy settings.\n\n"
                            f"This means the user has not started a conversation with the bot yet.\n\n"
                            f"Option 1: You can ask the user to click this link first:\n"
                            f"{start_link}\n\n"
                            f"Option 2: Click 'Generate Welcome Link' to create a personalized message for this user.",
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
                [InlineKeyboardButton("View User Profile", callback_data=f"view_profile_{original_sender_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"Message forwarded from {original_sender_name} (ID: {original_sender_id}).\n"
                f"Automated welcome message has been sent.",
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
    
    # If it's just a regular message from the admin
    else:
        print("This is a regular message from admin")
        # Check if admin is currently in a conversation with a user
        if "current_user_conv" in context.user_data:
            user_id = context.user_data["current_user_conv"]
            print(f"Admin is in conversation with user {user_id}")
            
            # Forward the admin's reply to that user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"Admin: {update.message.text}",
                    parse_mode="HTML"
                )
                await update.message.reply_text(f"Message sent to user {user_id}")
            except Exception as e:
                print(f"Error sending message to user: {e}")
                await update.message.reply_text(f"Failed to send message: {e}")
        else:
            print("Admin is not in a conversation with any user")
            # Admin is not in a conversation with anyone
            await update.message.reply_text(
                "You're not currently in a conversation with any user. "
                "Forward a message from a user to start a conversation."
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
                    f"Group: {group_invite.invite_link}\n\n"
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
                        f"Group: {group_invite.invite_link}\n\n"
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
    # Manager bot commands (no signal commands)
    manager_application.add_handler(CommandHandler("users", list_users_command))
    manager_application.add_handler(CommandHandler("endchat", end_user_conversation))
    manager_application.add_handler(CommandHandler("startform", start_form_command))
    manager_application.add_handler(CommandHandler("addtovip", add_to_vip_command))
    manager_application.add_handler(CommandHandler("forwardmt5", forward_mt5_command))
    manager_application.add_handler(CommandHandler("testaccount", test_account_command))
    manager_application.add_handler(CommandHandler("debugdb", debug_db_command))
    manager_application.add_handler(CommandHandler("resetuser", reset_user_registration_command))
    manager_application.add_handler(CommandHandler("debugvip", debug_vip_status_command))

    
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