import logging
import polars as pl
import asyncio
import os

from datetime import datetime, time, timedelta
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

# Import custom modules
from auth_system import TradingAccountAuth
from db_manager import TradingBotDatabase
from telegram.ext.filters import MessageFilter
from vfx_Scheduler import VFXMessageScheduler
from signal_dispatcher import SignalDispatcher
from config import Config

from mysql_manager import get_mysql_connection

# Global instance of the VFX message scheduler
config = Config()
vfx_scheduler = VFXMessageScheduler()
strategyChannel_scheduler = VFXMessageScheduler("./bot_data/strategy_messages.json")
propChannel_scheduler = VFXMessageScheduler("./bot_data/prop_messages.json")
signalsChannel_scheduler = VFXMessageScheduler("./bot_data/signals_messages.json")
educationChannel_scheduler = VFXMessageScheduler("./bot_data/ed_messages.json")

# Add this class definition before your handler functions
class ForwardedMessageFilter(MessageFilter):
    """Custom filter for forwarded messages."""
    
    def filter(self, message):
        """Returns True if the message has forward_origin attribute."""
        return hasattr(message, 'forward_origin')

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize database and auth system
db = TradingBotDatabase(data_dir="./bot_data")
auth = TradingAccountAuth(db_path="./bot_data/trading_accounts.csv")

# Define conversation states
(RISK_APPETITE, DEPOSIT_AMOUNT, TRADING_ACCOUNT, CAPTCHA_RESPONSE) = range(4)

# Configuration
BOT_TOKEN = "8113209614:AAFQ7YaIW4fZiJ6bqfOZmCScpWTB9mpd694"
ADMIN_USER_ID = [7823596188, 7396303047, 8177033621]
ADMIN_USER_ID_2 = 7396303047

MAIN_CHANNEL_ID = "-1002586937373"

SUPPORT_GROUP_ID = -1002520071214

STRATEGY_CHANNEL_ID = "-1002575685046"
STRATEGY_GROUP_ID = -1002428210575

SIGNALS_CHANNEL_ID = "-1002697690452"
SIGNALS_GROUP_ID = -1002685536346

PROP_CHANNEL_ID = "-1002675985847"
PROP_GROUP_ID = -1002673182167

ED_CHANNEL_ID = "-1002529155778"
ED_GROUP_ID: int = 0

# Get message templates from database
WELCOME_MSG = db.get_setting("welcome_message", "Welcome to our Trading Community! Please complete the authentication process.")
PRIVATE_WELCOME_MSG = db.get_setting("private_welcome_message", "Thanks for reaching out! To better serve you, please answer a few questions:")


# -------------------------------------- HELPER FUNCTIONs ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is an admin in direct chats or the current chat."""
    user_id = update.effective_user.id
    print(f"Checking admin status for user ID: {user_id}")
    print(f"Admin IDs list: {ADMIN_USER_ID}")
    
    # Always allow hardcoded admin
    if user_id in ADMIN_USER_ID:
        print(f"User {user_id} is in the hardcoded admin list")
        return True
    
    # If in direct chat, check if user is admin in the main group/channel
    if update.effective_chat.type == "private":
        try:
            # Check if user is admin in the main group
            group_member = await context.bot.get_chat_member(STRATEGY_GROUP_ID, user_id)
            if group_member.status in ['owner', 'administrator']:
                return True
                
            # Also check if user is admin in the main channel
            channel_member = await context.bot.get_chat_member(MAIN_CHANNEL_ID, user_id)
            if channel_member.status in ['owner', 'administrator']:
                return True
        except Exception as e:
            print(f"Error checking admin status in group/channel: {e}")
    
    # If in a group chat, check if user is admin in the current chat
    else:
        try:
            chat_id = update.effective_chat.id
            chat_member = await context.bot.get_chat_member(chat_id, user_id)
            return chat_member.status in ['owner', 'administrator']
        except Exception as e:
            print(f"Error checking admin status: {e}")
    
    return False

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

async def start_authentication(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Start authentication process for new users."""
    # Check if user is already verified
    user_data = db.get_user(user_id)
    if user_data and user_data["is_verified"]:
        # User is already verified
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome back! You're already verified in our system."
        )
        return
    
    # Start authentication with a button
    keyboard = [
        [InlineKeyboardButton("Complete Authentication", callback_data=f"auth_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Please complete authentication to access all features.",
        reply_markup=reply_markup
    )

async def auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle authentication button callback."""
    query = update.callback_query
    await query.answer()
    
    # Extract user_id from callback data
    callback_data = query.data
    if callback_data.startswith("auth_"):
        user_id = int(callback_data.split("_")[1])
        
        # Check if user can attempt authentication
        if not auth.can_attempt_auth(user_id):
            await query.edit_message_text(
                text="Too many failed attempts. Please try again later or contact an admin."
            )
            return ConversationHandler.END
        
        # Generate CAPTCHA
        captcha_question, captcha_answer = auth.generate_captcha()
        
        # Store the answer and user ID in user_data
        context.user_data["captcha_answer"] = captcha_answer
        context.user_data["auth_user_id"] = user_id
        
        # Store the chat_id where the auth process started
        context.user_data["auth_chat_id"] = update.effective_chat.id
        
        await query.edit_message_text(
            text=f"Authentication: {captcha_question} Reply with the number."
        )
        
        # This is crucial - we're returning a state to the conversation handler
        return CAPTCHA_RESPONSE

async def handle_captcha_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's response to CAPTCHA."""
    print(f"Received captcha response: {update.message.text}")
    print(f"User data: {context.user_data}")
    
    if "captcha_answer" in context.user_data and "auth_user_id" in context.user_data:
        try:
            user_answer = int(update.message.text.strip())
            expected_answer = context.user_data["captcha_answer"]
            user_id = context.user_data["auth_user_id"]
            
            print(f"User answer: {user_answer}, Expected: {expected_answer}")
            
            if user_answer == expected_answer:
                # Correct answer
                await update.message.reply_text("CAPTCHA solved correctly! Now please enter your trading account number for verification.")
                
                # Record successful attempt
                auth.record_attempt(user_id, True)
                
                # Keep the user_id for the trading account verification step
                context.user_data["pending_account_verify"] = user_id
                del context.user_data["captcha_answer"]
                del context.user_data["auth_user_id"]
                
                return TRADING_ACCOUNT
            else:
                # Incorrect answer
                await update.message.reply_text("Incorrect answer. Please try again.")
                
                # Record failed attempt
                auth.record_attempt(user_id, False)
                
                # Generate new CAPTCHA
                captcha_question, captcha_answer = auth.generate_captcha()
                context.user_data["captcha_answer"] = captcha_answer
                
                await update.message.reply_text(f"New authentication challenge: {captcha_question}")
                return CAPTCHA_RESPONSE
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return CAPTCHA_RESPONSE
    
    # If we get here, there's no CAPTCHA data in context
    # This usually means this is a regular message, not part of CAPTCHA verification
    print("No captcha data found in context")
    return ConversationHandler.END

async def handle_account_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle trading account verification."""
    if "pending_account_verify" in context.user_data:
        user_id = context.user_data["pending_account_verify"]
        account_number = update.message.text.strip()
        
        # Validate account format
        if not auth.validate_account_format(account_number):
            await update.message.reply_text("Invalid account format. Please enter a valid trading account number (e.g., TR12345678).")
            return TRADING_ACCOUNT
        
        # Verify the account
        if auth.verify_account(account_number, user_id):
            # Account verified successfully
            await update.message.reply_text("Trading account verified successfully! You now have full access to the group.")
            
            # Mark user as verified in database
            db.mark_user_verified(user_id)
            
            # Update user info
            db.add_user({
                "user_id": user_id,
                "enhanced_trading_account": account_number,
                "is_verified": True
            })
            
            # Clear verification data
            del context.user_data["pending_account_verify"]
            
            # End conversation
            return ConversationHandler.END
        else:
            # Account not found or already linked
            await update.message.reply_text("Account not found or already linked to another user. Please contact an admin for assistance.")
            
            # Clear verification data
            del context.user_data["pending_account_verify"]
            
            # End conversation
            return ConversationHandler.END
    else:
        # Regular message handling
        pass

async def private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle private messages to the bot and start the user info conversation."""
    user = update.effective_user
    
    # Check if this is a direct message to the bot
    if update.effective_chat.type == "private":
        # Update user activity
        db.update_user_activity(user.id)
        
        # Send welcome message and start conversation
        await update.message.reply_text(
            f"{PRIVATE_WELCOME_MSG}\n\nFirst, what's your risk appetite from 1-10?"
        )
        return RISK_APPETITE
    
    # For group messages, just update user activity
    db.update_user_activity(user.id)
    
    # Update analytics
    db.update_analytics(messages_sent=1)
    
    return ConversationHandler.END

async def risk_appetite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store risk appetite and ask for deposit amount."""
    try:
        risk = int(update.message.text)
        if 1 <= risk <= 10:
            user_id = update.effective_user.id
            
            # Store in user_data for conversation
            if "user_info" not in context.user_data:
                context.user_data["user_info"] = {}
            context.user_data["user_info"]["risk_appetite"] = risk
            
            # Update in database
            db.add_user({
                "user_id": user_id,
                "risk_appetite": risk
            })
            
            await update.message.reply_text(
                "Thanks! Now, how much do you plan to deposit? (100-10,000)"
            )
            return DEPOSIT_AMOUNT
        else:
            await update.message.reply_text("Please enter a number between 1 and 10.")
            return RISK_APPETITE
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 10.")
        return RISK_APPETITE

async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store deposit amount and ask for trading account number."""
    try:
        amount = int(update.message.text)
        if 100 <= amount <= 10000:
            user_id = update.effective_user.id
            
            # Store in user_data for conversation
            context.user_data["user_info"]["deposit_amount"] = amount
            
            # Update in database
            db.add_user({
                "user_id": user_id,
                "deposit_amount": amount
            })
            
            await update.message.reply_text(
                "Great! Finally, please enter your trading account number for verification."
            )
            return TRADING_ACCOUNT
        else:
            await update.message.reply_text("Please enter an amount between 100 and 10,000.")
            return DEPOSIT_AMOUNT
    except ValueError:
        await update.message.reply_text("Please enter a valid amount between 100 and 10,000.")
        return DEPOSIT_AMOUNT

async def send_registration_notification(context, user_id, account_number, account_verified):
    """Send detailed notification about new registration to admin team."""
    try:
        # Get user info from database
        user_info = db.get_user(user_id)
        print(f"Retrieved user info from DB for notification: {user_info}")
        
        if not user_info:
            print(f"WARNING: User {user_id} not found in database for notification")
            return
        
        # Get user's selected interests
        trading_interest = user_info.get('trading_interest', 'Not specified')
        
        # Format interest for display
        if trading_interest == 'all':
            interest_display = "All VIP Services (Signals, Strategy, Prop Capital)"
        elif trading_interest:
            interest_display = f"VIP {trading_interest.capitalize()}"
        else:
            interest_display = "Not specified"
        
        # Set verification status emoji
        verify_status = "✅ Verified" if account_verified else "⚠️ Not Verified"
        
        # Build detailed report
        report = (
            f"🔔 NEW USER REGISTRATION 🔔\n\n"
            f"User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"Username: @{user_info.get('username', 'None')}\n"
            f"User ID: {user_id}\n\n"
            f"📊 PROFILE DETAILS 📊\n"
            f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            f"Trading Interest: {interest_display}\n"
            f"Trading Account: {account_number}\n"
            f"Account Status: {verify_status}\n\n"
            f"Registered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        # Add action buttons for admin
        keyboard = []
        
        # Add VIP channel buttons based on interest
        if trading_interest == 'signals' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")])
        
        if trading_interest == 'strategy' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Strategy", callback_data=f"add_vip_strategy_{user_id}")])
        
        if trading_interest == 'propcapital' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Prop Capital", callback_data=f"add_vip_propcapital_{user_id}")])
        
        # Add button for forwarding to copier team
        keyboard.append([InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, 
                    text=report,
                    reply_markup=reply_markup
                )
                print(f"Successfully sent registration notification to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {e}")
    except Exception as e:
        print(f"Error in send_registration_notification: {e}")

async def send_account_notification(context, user_id, account_number):
    """Send notification about new account separately to avoid blocking the main flow."""
    try:
        # Get user info from database instead of context
        user_info = db.get_user(user_id)
        print(f"Retrieved user info from DB: {user_info}")
        
        if not user_info:
            print(f"WARNING: User {user_id} not found in database")
            return
        
        # Build minimal report
        report = (
            f"📊 New User Profile 📊\n"
            f"User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            f"Trading Account: {account_number}\n"
            f"User ID: {user_id}\n\n"
            f"This user needs to be added to VIP channels based on their interests."
        )
        
        # Send to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(chat_id=admin_id, text=report)
                print(f"Successfully sent notification to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {e}")
    except Exception as e:
        print(f"Error in send_account_notification: {e}")

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
                    [
                        InlineKeyboardButton("Low Risk", callback_data="risk_low"),
                        InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
                        InlineKeyboardButton("High Risk", callback_data="risk_high")
                    ],
                    [InlineKeyboardButton("Start Guided Setup", callback_data="start_guided")],
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
                f"🔄 **NEW ACCOUNT FOR COPIER SYSTEM** 🔄\n\n"
                f"📋 **USER DETAILS:**\n"
                f"• Name: {user_name} {last_name}\n"
                f"• Username: @{username}\n"
                f"• User ID: {user_id}\n"
                f"• Trading Account: {trading_account} {'✅' if is_verified else '⚠️'}\n\n"
                f"📊 **TRADING PROFILE:**\n"
                f"• Risk Level: {risk_appetite}/10\n"
                f"• Deposit Amount: ${deposit_amount}\n"
                f"• VIP Services: {vip_channels}\n"
                f"• Account Status: {'Verified' if is_verified else 'Pending Verification'}\n\n"
                f"⏰ **Date Added:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"👉 **ACTION REQUIRED:** Please add this account to the copier system and configure the appropriate risk parameters."
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
                    parse_mode='Markdown',
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
                    text=f"✅ **Account Successfully Forwarded to Copier Team**\n\n"
                         f"**User:** {user_name} {last_name}\n"
                         f"**Account:** {trading_account}\n"
                         f"**Risk Level:** {risk_appetite}/10\n"
                         f"**Deposit:** ${deposit_amount}\n\n"
                         f"📤 **Message sent to Support Group**\n"
                         f"🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                         f"The copier team will be able to take action on this account using the buttons provided.",
                    parse_mode='Markdown',
                    reply_markup=None
                )
                
            except Exception as e:
                print(f"Error sending message to support group: {e}")
                await query.edit_message_text(
                    text=f"⚠️ **Error sending to copier team:** {e}\n\n"
                         f"Please manually forward this information:\n\n{copier_message}",
                    parse_mode='Markdown',
                    reply_markup=None
                )
                return
            
            # Also notify the user
            try:
                user_notification = (
                    f"📊 **Your trading account has been forwarded to our copier team!**\n\n"
                    f"**Account:** {trading_account}\n"
                    f"**Risk Level:** {risk_appetite}/10\n"
                    f"**Deposit Amount:** ${deposit_amount}\n\n"
                    f"Our copier team will review your account and set up the optimal trading parameters based on your risk profile. "
                    f"You'll receive confirmation once your account is connected to our automated trading system.\n\n"
                    f"**Expected Setup Time:** 24 hours\n"
                    f"**Next Steps:** Our team will contact you with setup details and login credentials for your copier dashboard."
                )
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_notification,
                    parse_mode='Markdown'
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
                    text=f"✅ **ACCOUNT ADDED TO COPIER SYSTEM**\n\n"
                         f"**User:** {user_name}\n"
                         f"**Account:** {trading_account}\n"
                         f"**Status:** Active in copier system\n"
                         f"**Added by:** {query.from_user.first_name}\n"
                         f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                         f"✅ User has been notified of successful setup.",
                    parse_mode='Markdown',
                    reply_markup=None
                )
                
                # Notify the user
                try:
                    user_success_message = (
                        f"🎉 **Congratulations! Your account has been successfully added to our copier system!**\n\n"
                        f"**Account:** {trading_account}\n"
                        f"**Status:** Active\n"
                        f"**Setup Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"Your account is now automatically copying our professional trading signals. "
                        f"You can monitor your performance through your MT5 platform.\n\n"
                        f"**Important Notes:**\n"
                        f"• Trades will be executed automatically based on your risk settings\n"
                        f"• You can monitor performance 24/7 through MT5\n"
                        f"• Our team monitors all accounts during market hours\n\n"
                        f"Welcome to our automated trading system! 🚀"
                    )
                    
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=user_success_message,
                        parse_mode='Markdown'
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
                    text=f"❌ **ACCOUNT REJECTED FROM COPIER SYSTEM**\n\n"
                         f"**User:** {user_name}\n"
                         f"**Account:** {trading_account}\n"
                         f"**Status:** Rejected\n"
                         f"**Rejected by:** {query.from_user.first_name}\n"
                         f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                         f"⚠️ Please contact the user to resolve any issues.",
                    parse_mode='Markdown',
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
                    text=f"📞 **CONTACT USER: {user_name}**\n\n"
                         f"**User ID:** {user_id}\n"
                         f"**Account:** {trading_account}\n"
                         f"**Username:** @{user_info.get('username', 'None')}\n\n"
                         f"Choose how you'd like to contact this user:",
                    parse_mode='Markdown',
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

# -------------------------------------- Analytics Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def send_daily_signup_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a daily report of new sign-ups to the admin team."""
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get users who joined today
        # This assumes the join_date column is in the format "YYYY-MM-DD HH:MM:SS"
        today_users = db.users_df.filter(pl.col("join_date").str.contains(today))
        
        if today_users.height == 0:
            # No new users today
            report = f"📊 DAILY SIGNUP REPORT - {today} 📊\n\nNo new users registered today."
        else:
            # Format report
            report = f"📊 DAILY SIGNUP REPORT - {today} 📊\n\n"
            report += f"Total New Users: {today_users.height}\n\n"
            
            # Add details for each user
            report += "NEW USER DETAILS:\n\n"
            
            for i in range(min(today_users.height, 10)):  # Limit to 10 users to avoid message length issues
                user_id = today_users["user_id"][i]
                first_name = today_users["first_name"][i] if today_users["first_name"][i] else "Unknown"
                last_name = today_users["last_name"][i] if today_users["last_name"][i] else ""
                risk = today_users["risk_appetite"][i]
                deposit = today_users["deposit_amount"][i]
                account = today_users["trading_account"][i] if today_users["trading_account"][i] else "Not provided"
                verified = "✅" if today_users["is_verified"][i] else "❌"
                
                report += (
                    f"{i+1}. {first_name} {last_name} (ID: {user_id})\n"
                    f"   Risk: {risk}/10 | Deposit: ${deposit}\n"
                    f"   Account: {account} | Verified: {verified}\n\n"
                )
            
            if today_users.height > 10:
                report += f"... and {today_users.height - 10} more users"
        
        # Send report to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report
                )
                print(f"Successfully sent daily signup report to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send report to admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error generating daily signup report: {e}")

async def send_daily_response_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a daily report of user responses to the admin team."""
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get users who responded today (based on last_response_time)
        today_responders = db.users_df.filter(pl.col("last_response_time").str.contains(today))
        
        if today_responders.height == 0:
            # No responses today
            report = f"📊 DAILY USER RESPONSE REPORT - {today} 📊\n\nNo user responses recorded today."
        else:
            # Format report
            report = f"📊 DAILY USER RESPONSE REPORT - {today} 📊\n\n"
            report += f"Total User Responses: {today_responders.height}\n\n"
            
            # Add details for each user
            report += "USER RESPONSE DETAILS:\n\n"
            
            for i in range(min(today_responders.height, 10)):  # Limit to 10 users
                user_id = today_responders["user_id"][i]
                first_name = today_responders["first_name"][i] if today_responders["first_name"][i] else "Unknown"
                last_name = today_responders["last_name"][i] if today_responders["last_name"][i] else ""
                risk = today_responders["risk_appetite"][i]
                risk_text = today_responders["risk_profile_text"][i] if "risk_profile_text" in today_responders.columns and today_responders["risk_profile_text"][i] else "Not specified"
                deposit = today_responders["deposit_amount"][i]
                account = today_responders["trading_account"][i] if today_responders["trading_account"][i] else "Not provided"
                verified = "✅" if today_responders["is_verified"][i] else "❌"
                last_response = today_responders["last_response"][i] if "last_response" in today_responders.columns and today_responders["last_response"][i] else "No response"
                source_channel = today_responders["source_channel"][i] if "source_channel" in today_responders.columns and today_responders["source_channel"][i] else "Unknown"
                source_emoji = "📊" if source_channel == "signals_channel" else "📢" if source_channel == "main_channel" else "❓"
                
                report += (
                    f"{i+1}. {first_name} {last_name} (ID: {user_id}) {source_emoji}\n"
                    f"   Source: {source_channel}\n"
                    f"   Risk: {risk}/10 ({risk_text}) | Deposit: ${deposit}\n"
                    f"   Account: {account} | Verified: {verified}\n"
                    f"   Last Response: \"{last_response[:50]}...\"\n\n"
                )
            
            if today_responders.height > 10:
                report += f"... and {today_responders.height - 10} more users"
        
        # Send report to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report
                )
                print(f"Successfully sent daily response report to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send report to admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error generating daily response report: {e}")

async def show_summary(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Show summary of collected information and completion options."""
    # Get user data from database
    user_info = db.get_user(user_id)
    
    if not user_info:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Error retrieving your information. Please contact an admin for assistance."
        )
        return
    
    # Format summary
    summary = f"""<b>📋 Your Registration Summary</b>

Thank you for providing your information! Here's what we've got:

<b>Risk Profile:</b> {user_info.get('risk_profile_text', 'Not specified').capitalize()}
<b>Deposit Amount:</b> ${user_info.get('deposit_amount', 'Not specified')}
<b>Previous Experience:</b> {user_info.get('previous_experience', 'Not specified')}
<b>MT5 Account:</b> {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

<b>What's Next?</b>
Our team will review your information and set up your account for our signals service. You should receive confirmation within the next 24 hours.

If you need to make any changes or have questions, please let us know!"""

    # Add buttons for edit or confirm
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Information", callback_data="confirm_registration")],
        [InlineKeyboardButton("✏️ Edit Information", callback_data="edit_registration")],
        [InlineKeyboardButton("👨‍💼 Speak to an Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=summary,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Update conversation state
    context.user_data["response_step"] = "summary_shown"
    
    # Notify admin of completion
    for admin_id in ADMIN_USER_ID:
        try:
            admin_summary = f"""📋 <b>USER REGISTRATION COMPLETED</b>

User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}
ID: {user_id}
Source: {user_info.get('source_channel', 'Unknown')}

<b>Collected Information:</b>
- Risk Profile: {user_info.get('risk_profile_text', 'Not specified').capitalize()}
- Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}
- Previous Experience: {user_info.get('previous_experience', 'Not specified')}
- MT5 Account: {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

Registration completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

            # Add action buttons for admin
            admin_keyboard = [
                [InlineKeyboardButton("View Full Profile", callback_data=f"view_profile_{user_id}")],
                [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
                [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
            ]
            admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_summary,
                parse_mode='HTML',
                reply_markup=admin_reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def send_profile_summary_to_admins(context, user_id):
    """Send a summary of the user's profile to all admins."""
    print(f"Attempting to send profile summary for user {user_id} to admins")
    
    # Try multiple methods to get user info
    user_info = None
    error_messages = []
    
    # Method 1: Try db.get_user
    try:
        print("Attempting to retrieve user via db.get_user")
        user_info = db.get_user(user_id)
        if user_info:
            print(f"Successfully retrieved user via db.get_user: {user_info}")
    except Exception as e:
        error_msg = f"db.get_user error: {e}"
        print(error_msg)
        error_messages.append(error_msg)
    
    # Method 2: Try direct dataframe access if db.get_user failed
    if not user_info:
        try:
            print("Attempting to retrieve user via direct dataframe access")
            user_df = db.users_df.filter(pl.col("user_id") == user_id)
            if user_df.height > 0:
                print(f"Found user in dataframe, creating dict")
                user_info = {}
                for col in user_df.columns:
                    user_info[col] = user_df[col][0]
                print(f"Created user_info dict: {user_info}")
        except Exception as e:
            error_msg = f"Dataframe access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    # Method 3: Try to use auto_welcoming_users dict if available
    if not user_info:
        try:
            print("Attempting to retrieve from auto_welcoming_users")
            auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
            if user_id in auto_welcoming_users:
                print(f"User found in auto_welcoming_users")
                # Create a basic info dict
                user_info = {
                    "user_id": user_id,
                    "first_name": auto_welcoming_users[user_id].get("name", "Unknown"),
                    "source_channel": auto_welcoming_users[user_id].get("source_channel", "Unknown")
                }
                # Add any conversation state info
                user_states = context.bot_data.get("user_states", {})
                if user_id in user_states:
                    user_info["current_state"] = user_states[user_id]
        except Exception as e:
            error_msg = f"Auto_welcoming access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    if not user_info:
        # User could not be found - notify admins of the issue
        error_details = "\n".join(error_messages) if error_messages else "No detailed error information"
        
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ Could not generate summary for user {user_id}:\n\n{error_details}\n\n"
                         f"The user may need to be manually processed."
                )
                print(f"Sent error report to admin {admin_id}")
            except Exception as e:
                print(f"Error sending error report to admin {admin_id}: {e}")
        return
    
    # We have some user info - generate summary
    summary = f"""📋 <b>USER REGISTRATION COMPLETED</b>

User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}
ID: {user_id}
Source: {user_info.get('source_channel', 'Unknown')}

<b>Collected Information:</b>
- Risk Profile: {user_info.get('risk_profile_text', 'Not specified').capitalize() if user_info.get('risk_profile_text') else f"{user_info.get('risk_appetite', 0)}/10"}
- Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}
- Previous Experience: {user_info.get('previous_experience', 'Not specified').capitalize() if user_info.get('previous_experience') else 'Not specified'}
- MT5 Account: {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

Registration completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
    
    # Add action buttons for admin
    keyboard = [
        [InlineKeyboardButton("View Full Profile", callback_data=f"view_profile_{user_id}")],
        [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
        [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=summary,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            print(f"Sent profile summary to admin {admin_id}")
        except Exception as e:
            print(f"Error sending profile summary to admin {admin_id}: {e}")

# -------------------------------------- COMMANDS ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id
    
    # Debug output to console only
    print(f"User ID {user_id} ({user.first_name}) started the bot")
    
    # Handle referral parameter in a separate async function to avoid message leakage
    referral_admin = None
    if context.args and context.args[0].startswith("ref_"):
        try:
            # Extract the referring admin's ID
            referral_admin = int(context.args[0].split("_")[1])
            print(f"User {user_id} was referred by admin {referral_admin}")
            
            # Store this connection in the database
            db.add_user({
                "user_id": user_id,
                "referred_by": referral_admin,
                "referral_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # Store in bot data for quick access
            context.bot_data.setdefault("admin_user_connections", {})
            context.bot_data["admin_user_connections"][user_id] = referral_admin
            
            # Also store in auto-welcoming users
            context.bot_data.setdefault("auto_welcoming_users", {})
            context.bot_data["auto_welcoming_users"][user_id] = {
                "name": user.first_name,
                "status": "referred",
                "referred_by": referral_admin,
                "first_contact_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Notify admin of connection
            try:
                await context.bot.send_message(
                    chat_id=referral_admin,
                    text=f"✅ {user.first_name} (ID: {user_id}) has connected with the bot through your link! "
                         f"They have started the registration process."
                )
            except Exception as e:
                print(f"Error notifying admin {referral_admin}: {e}")
        except Exception as e:
            print(f"Error processing referral: {e}")
    
    # Add user to database if not exists
    db.add_user({
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "join_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "last_active": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # If this is a referred user, start with welcome message from referring admin
    if referral_admin:
        admin_info = db.get_user(referral_admin)
        admin_name = admin_info.get('first_name', 'Admin') if admin_info else 'Admin'
        
        await update.message.reply_text(
            f"Welcome {user.first_name}! You've been connected to our registration system by {admin_name}. "
            f"Let's get your account set up!"
        )
    else:
        # Standard welcome
        await update.message.reply_text(f"Hello {user.first_name}! I'm your trading assistant bot.")
    
    # Start guided setup with buttons right away
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "<b>Let's start with your profile setup!</b>\n\n"
        "What risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set initial state
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Update analytics
    db.update_analytics(active_users=1)
    
    return RISK_APPETITE

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

# -------------------------------------- MANUAL FUNCTIONS ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

async def manual_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the 'Record Info Manually' button callback for hidden users."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received manual entry callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("manual_"):
        try:
            session_id = callback_data[7:]  # Remove 'manual_' prefix
            print(f"Starting manual entry for session: {session_id}")
            
            # Store the session ID for the conversation
            context.user_data["manual_entry_session"] = session_id
            
            # Get hidden user info
            if "hidden_users" in context.bot_data and session_id in context.bot_data["hidden_users"]:
                user_name = context.bot_data["hidden_users"][session_id]["name"]
                
                await query.edit_message_text(
                    text=f"📝 Manual profile entry for {user_name}\n\n"
                         f"You'll now be asked a series of questions to fill in their profile.\n\n"
                         f"First, what is their risk appetite (1-10)?"
                )
                
                return RISK_APPETITE_MANUAL
            else:
                await query.edit_message_text(
                    text="⚠️ User session information not found. Please try forwarding a new message."
                )
                return ConversationHandler.END
        except Exception as e:
            print(f"Error processing manual entry callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error starting manual entry: {e}"
            )
            return ConversationHandler.END

async def risk_appetite_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle risk appetite input for manual entry."""
    try:
        risk = int(update.message.text)
        if 1 <= risk <= 10:
            # Store in user_data for conversation
            if "manual_entry_data" not in context.user_data:
                context.user_data["manual_entry_data"] = {}
            context.user_data["manual_entry_data"]["risk_appetite"] = risk
            
            await update.message.reply_text(
                "Thanks! Now, what is their approximate deposit amount? (100-10,000)"
            )
            return DEPOSIT_AMOUNT_MANUAL
        else:
            await update.message.reply_text("Please enter a number between 1 and 10.")
            return RISK_APPETITE_MANUAL
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 10.")
        return RISK_APPETITE_MANUAL

async def deposit_amount_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deposit amount input for manual entry."""
    try:
        amount = int(update.message.text)
        if 100 <= amount <= 10000:
            # Store in user_data for conversation
            context.user_data["manual_entry_data"]["deposit_amount"] = amount
            
            await update.message.reply_text(
                "Great! Finally, what is their trading account number? (e.g. TR12345678)"
            )
            return TRADING_ACCOUNT_MANUAL
        else:
            await update.message.reply_text("Please enter an amount between 100 and 10,000.")
            return DEPOSIT_AMOUNT_MANUAL
    except ValueError:
        await update.message.reply_text("Please enter a valid amount between 100 and 10,000.")
        return DEPOSIT_AMOUNT_MANUAL

async def trading_account_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trading account input for manual entry."""
    account_number = update.message.text.strip()
    
    # Validate account format
    if not auth.validate_account_format(account_number):
        await update.message.reply_text("Invalid account format. Please enter a valid trading account number (e.g., TR12345678).")
        return TRADING_ACCOUNT_MANUAL
    
    # Store in user_data
    context.user_data["manual_entry_data"]["trading_account"] = account_number
    
    # Get session info
    session_id = context.user_data["manual_entry_session"]
    user_name = context.bot_data["hidden_users"][session_id]["name"]
    
    # Create a virtual user entry in the database using the session ID as reference
    virtual_user_id = f"virtual_{session_id[:8]}"
    
    # Add to database with manual entry data
    user_data = {
        "user_id": virtual_user_id,
        "first_name": user_name,
        "last_name": "Hidden User",
        "username": None,
        "risk_appetite": context.user_data["manual_entry_data"]["risk_appetite"],
        "deposit_amount": context.user_data["manual_entry_data"]["deposit_amount"],
        "trading_account": account_number,
        "is_verified": True,  # Mark as verified since admin is entering data
        "notes": f"Manually entered by admin. Original name: {user_name}"
    }
    
    # Save to database
    db.add_user(user_data)
    
    # Format collected data for review
    report = (
        f"✅ Manual profile completed for {user_name}\n\n"
        f"Risk Appetite: {context.user_data['manual_entry_data']['risk_appetite']}/10\n"
        f"Deposit Amount: ${context.user_data['manual_entry_data']['deposit_amount']}\n"
        f"Trading Account: {account_number}\n"
        f"Reference ID: {virtual_user_id}\n\n"
        f"This profile has been saved and marked as verified."
    )
    
    await update.message.reply_text(report)
    
    # Clean up conversation data
    del context.user_data["manual_entry_session"]
    del context.user_data["manual_entry_data"]
    
    return ConversationHandler.END



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



# Admin command to manage scheduled messages
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

async def start_user_conversation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Start Conversation' button callback."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("start_conv_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Starting conversation with user ID: {user_id}")
            
            # Store the current conversation user
            context.user_data["current_user_conv"] = user_id
            
            # Get user info
            user_info = db.get_user(user_id)
            user_name = user_info.get("first_name", "User") if user_info else "User"
            
            # Create a deep link with user ID as parameter
            bot_username = await context.bot.get_me()
            bot_username = bot_username.username
            deep_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
            
            # Prepare copy-paste templates for admin
            registration_template = (
                f"Thank you for your message! To set up your trading profile quickly, "
                f"please click this link to chat with our bot: {deep_link}\n\n"
                f"Once you click, just send /start to begin the registration process."
            )
            
            casual_template = (
                f"Thanks for reaching out! I'd be happy to help with your questions. "
                f"For faster assistance, please connect with our trading bot: {deep_link}\n\n"
                f"Once connected, I'll be able to chat with you directly through the bot."
            )
            
            # Create keyboard with copy buttons
            keyboard = [
                [InlineKeyboardButton("Copy Registration Message", callback_data=f"copy_reg_{user_id}")],
                [InlineKeyboardButton("Copy Casual Message", callback_data=f"copy_casual_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=f"Due to Telegram's privacy restrictions, the bot can't message {user_name} first.\n\n"
                     f"Please copy and paste one of these messages to the user:\n\n"
                     f"1. Registration message:\n{registration_template}\n\n"
                     f"2. Casual message:\n{casual_template}\n\n"
                     f"These messages include a special link that will connect the user to our bot.",
                reply_markup=reply_markup
            )
            
            # Store templates for copy buttons
            context.user_data["reg_template"] = registration_template
            context.user_data["casual_template"] = casual_template
            
            print(f"Provided message templates for user {user_id}")
        except Exception as e:
            print(f"Error processing callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error processing request: {e}"
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

async def handle_auto_welcome_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle responses to the automated welcome message with enhanced verification."""
    user_id = update.effective_user.id
    message_text = update.message.text
    print(f"AUTO WELCOME RESPONSE: User ID {user_id}, Message: {message_text}")
    
    # Check if this user is in our auto_welcoming_users dict
    auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
    if user_id in auto_welcoming_users:
        user_name = auto_welcoming_users[user_id]["name"]
        
        # Get the current step from bot_data
        user_states = context.bot_data.get("user_states", {})
        current_step = user_states.get(str(user_id), None)
        if not current_step:
            current_step = user_states.get(user_id, None)  # Try with int key as well
            
        print(f"User {user_id} is at step: {current_step}")
        print(f"User states: {user_states}")
        
        # CRITICAL: State-based processing must be strictly enforced
        if current_step == "deposit_amount":
            # Processing deposit amount after risk profile selection
            import re
            amount_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', message_text)
            if amount_match:
                amount_str = amount_match.group(1).replace(',', '')
                try:
                    amount = int(float(amount_str))
                    
                    # Store deposit amount
                    db.add_user({
                        "user_id": user_id,
                        "deposit_amount": amount,
                        "last_response": message_text,
                        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    # Show experience buttons
                    keyboard = [
                        [
                            InlineKeyboardButton("Yes", callback_data="experience_yes"),
                            InlineKeyboardButton("No", callback_data="experience_no")
                        ],
                        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"<b>Deposit Amount:</b> ${amount} ✅\n\nHave you used a trading signals service before?",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    
                    # Update state to previous_experience
                    context.bot_data.setdefault("user_states", {})
                    context.bot_data["user_states"][user_id] = "previous_experience"
                    
                    # Notify admin
                    for admin_id in ADMIN_USER_ID:
                        try:
                            await context.bot.send_message(
                                chat_id=admin_id,
                                text=f"💰 User {user_name} (ID: {user_id}) indicated deposit amount: ${amount}"
                            )
                        except Exception as e:
                            print(f"Error notifying admin {admin_id}: {e}")
                except ValueError:
                    # Not a valid number
                    await update.message.reply_text(
                        "Sorry, I couldn't understand that amount. Please enter a numeric value, for example: 1000"
                    )
            else:
                # No number found
                await update.message.reply_text(
                    "Please provide a valid deposit amount. For example: 1000"
                )
            
            # Exit function after handling this state
            return
                
        elif current_step == "account_number" or current_step == "previous_experience":
            # 🔥 ENHANCED VERIFICATION STARTS HERE
            print(f"Processing as account number with enhanced verification: {message_text}")
            
            # Check if it looks like an account number
            if message_text.isdigit() and len(message_text) == 6:
                account_number = message_text
                
                # Get user's stated deposit intention from database
                user_info = db.get_user(user_id)
                stated_amount = user_info.get("deposit_amount", 0) if user_info else 0
                
                print(f"===== ENHANCED ACCOUNT VERIFICATION (AUTO WELCOME) =====")
                print(f"Account: {account_number}, User: {user_id}, Stated: ${stated_amount}")
                
                await update.message.reply_text("🔍 Verifying your account and checking balance...")
                
                # Validate account format first
                if not auth.validate_account_format(account_number):
                    await update.message.reply_text(
                        "❌ Invalid account format. Please enter a valid trading account number."
                    )
                    return
                
                # Connect to MySQL and verify account with balance
                mysql_db = get_mysql_connection()
                if not mysql_db.is_connected():
                    await update.message.reply_text(
                        "⚠️ Unable to verify account at the moment. Please try again later."
                    )
                    return
                
                try:
                    account_info = mysql_db.verify_account_exists(account_number)
                    
                    if not account_info['exists']:
                        await update.message.reply_text(
                            f"❌ Account {account_number} not found in our system.\n\n"
                            f"Please check the account number or contact support if you believe this is an error."
                        )
                        return
                    
                    # Extract account details
                    real_balance = float(account_info.get('balance', 0))
                    account_name = account_info.get('name', 'Unknown')
                    account_status = account_info.get('status', 'Unknown')
                    
                    print(f"Account found: {account_name}, Balance: ${real_balance}, Status: {account_status}")
                    
                    # Store account info in database
                    db.add_user({
                        "user_id": user_id,
                        "trading_account": account_number,
                        "account_owner": account_name,
                        "account_balance": real_balance,
                        "account_status": account_status,
                        "is_verified": True,
                        "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    # 🔥 ENHANCED DECISION LOGIC BASED ON REAL BALANCE
                    if real_balance >= stated_amount and stated_amount > 0:
                        # SCENARIO A: USER HAS SUFFICIENT FUNDS
                        success_message = (
                            f"✅ **Account Verified Successfully!** ✅\n\n"
                            f"**Account:** {account_number}\n"
                            f"**Account Holder:** {account_name}\n"
                            f"**Current Balance:** ${real_balance:,.2f} 💰\n"
                            f"**Required:** ${stated_amount:,.2f}\n\n"
                            f"🎉 **Excellent!** You have sufficient funds to access all our VIP services!\n\n"
                            f"**You now have access to:**\n"
                            f"• 🔔 Premium Trading Signals\n"
                            f"• 📈 Advanced Trading Strategies\n"
                            f"• 💰 Prop Capital Opportunities\n"
                            f"• 👨‍💼 Personal Trading Support\n\n"
                            f"Our team will set up your VIP access within the next few minutes!"
                        )
                        
                        # Create VIP access buttons
                        keyboard = [
                            [
                                InlineKeyboardButton("🔔 Access VIP Signals", callback_data="access_vip_signals"),
                                InlineKeyboardButton("📈 Access VIP Strategy", callback_data="access_vip_strategy")
                            ],
                            [
                                InlineKeyboardButton("💰 Access Prop Capital", callback_data="access_vip_propcapital"),
                                InlineKeyboardButton("👨‍💼 Speak to Advisor", callback_data="speak_advisor")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(success_message, parse_mode='Markdown', reply_markup=reply_markup)
                        
                        # Mark user as fully verified and funded
                        db.add_user({
                            "user_id": user_id,
                            "funding_status": "sufficient",
                            "vip_eligible": True,
                            "vip_access_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        # Reset state after completion
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "completed"
                        
                        # Notify admins of successful verification
                        await notify_admins_success_auto_welcome(context, user_id, account_info, stated_amount, real_balance)
                        
                    elif real_balance > 0 and stated_amount > 0:
                        # SCENARIO B: USER HAS PARTIAL FUNDS
                        difference = stated_amount - real_balance
                        percentage = (real_balance / stated_amount) * 100
                        
                        message = (
                            f"✅ **Account Successfully Verified!**\n\n"
                            f"**Account:** {account_number}\n"
                            f"**Account Holder:** {account_name}\n"
                            f"**Current Balance:** ${real_balance:,.2f}\n"
                            f"**Your Goal:** ${stated_amount:,.2f}\n"
                            f"**Remaining:** ${difference:,.2f}\n\n"
                            f"📊 **You're {percentage:.1f}% of the way there!** 🎯\n\n"
                            f"**What would you like to do?**"
                        )
                        
                        # Create action buttons
                        keyboard = [
                            [InlineKeyboardButton(f"💳 Deposit ${difference:,.0f} Now", callback_data=f"deposit_exact_{difference}")],
                            [InlineKeyboardButton(f"💰 Choose Deposit Amount", callback_data="choose_deposit_amount")],
                            [InlineKeyboardButton("🚀 Start with Current Balance", callback_data="start_with_current")],
                            [InlineKeyboardButton("⏰ I'll Deposit Later", callback_data="deposit_later")],
                            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                        
                        # Store partial funding status
                        db.add_user({
                            "user_id": user_id,
                            "funding_status": "partial",
                            "funding_percentage": percentage,
                            "remaining_amount": difference
                        })
                        
                        # Reset state 
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "awaiting_deposit_decision"
                        
                    else:
                        # SCENARIO C: USER HAS NO FUNDS OR NO STATED AMOUNT
                        target_amount = stated_amount if stated_amount > 0 else 1000  # Default if no amount stated
                        
                        message = (
                            f"✅ **Account Successfully Verified!**\n\n"
                            f"**Account:** {account_number}\n"
                            f"**Account Holder:** {account_name}\n"
                            f"**Current Balance:** ${real_balance:,.2f}\n"
                            f"**Suggested Amount:** ${target_amount:,.2f}\n\n"
                            f"🚀 **Ready to start your trading journey?**\n\n"
                            f"To access our VIP services, you'll need to fund your account.\n\n"
                            f"**Once funded, you'll get:**\n"
                            f"• 🔔 Premium Trading Signals\n"
                            f"• 📈 Advanced Strategies\n"
                            f"• 💰 Prop Capital Access\n"
                            f"• 👨‍💼 Personal Support\n\n"
                            f"**How would you like to proceed?**"
                        )
                        
                        # Create funding options
                        keyboard = [
                            [InlineKeyboardButton(f"💳 Deposit ${target_amount:,.0f} Now", callback_data=f"deposit_exact_{target_amount}")],
                            [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
                            [InlineKeyboardButton("📚 Start with Free Resources", callback_data="free_resources")],
                            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
                        
                        # Store no funding status
                        db.add_user({
                            "user_id": user_id,
                            "funding_status": "none",
                            "target_amount": target_amount
                        })
                        
                        # Reset state
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "awaiting_deposit_decision"
                    
                except Exception as e:
                    print(f"Error in enhanced verification: {e}")
                    await update.message.reply_text(
                        f"⚠️ Error verifying account: {e}\n\nPlease try again or contact support."
                    )
                    return
                    
            else:
                # Not a valid account format
                await update.message.reply_text(
                    "That doesn't look like a valid account number. Please provide a 6-digit MT5 account number."
                )
            
            # Exit function after handling this state
            return
                
        # Handle other specific conversation commands/states
        
        # If we get here, we're not in a defined state or we're handling generic text
        # First, check for known commands
        if message_text and message_text.startswith("/guided"):
            # Start guided flow with buttons for risk profile
            keyboard = [
                [
                    InlineKeyboardButton("Low Risk", callback_data="risk_low"),
                    InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
                    InlineKeyboardButton("High Risk", callback_data="risk_high")
                ],
                [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "<b>Let's get started with your profile setup!</b>\n\nWhat risk profile would you like on your account?",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            # Store current step in user data
            context.bot_data.setdefault("user_states", {})
            context.bot_data["user_states"][user_id] = "risk_profile"
            return
                
        # If we don't have a specific state yet, try to interpret the message
        # But only do this if we're not already in a structured flow
        if not current_step or current_step == "initial":
            # Check for risk profile keywords
            if any(keyword in message_text.lower() for keyword in ["low", "medium", "high", "risk"]):
                # Extract risk level (low/medium/high)
                risk_level = None
                if "low" in message_text.lower():
                    risk_level = "low"
                elif "medium" in message_text.lower():
                    risk_level = "medium" 
                elif "high" in message_text.lower():
                    risk_level = "high"
                
                if risk_level:
                    # Convert to numeric risk appetite (1-3 for low, 4-7 for medium, 8-10 for high)
                    risk_appetite = {"low": 2, "medium": 5, "high": 8}.get(risk_level, 5)
                    
                    db.add_user({
                        "user_id": user_id,
                        "risk_appetite": risk_appetite,
                        "risk_profile_text": risk_level,
                        "last_response": message_text,
                        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    
                    # Add button option for deposit amount
                    keyboard = [
                        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.message.reply_text(
                        f"<b>Risk Profile:</b> {risk_level.capitalize()} ✅\n\n"
                        f"Thank you! This will help us configure your trading strategy appropriately.\n\n"
                        f"How much capital are you planning to fund your account with?",
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                    
                    # CRITICAL: Set the next step to get deposit amount
                    context.bot_data.setdefault("user_states", {})
                    context.bot_data["user_states"][user_id] = "deposit_amount"
                    return
            
            # Check for capital/deposit amount (only if not already in a flow)
            elif any(keyword in message_text.lower() for keyword in ["$", "usd", "eur", "gbp", "deposit", "fund"]) or (message_text.strip().isdigit() and not (message_text.isdigit() and len(message_text) == 6)):
                # Avoid interpreting 6-digit numbers as amounts if they could be account numbers
                # Try to extract a number from the message
                import re
                amount_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', message_text)
                if amount_match:
                    amount_str = amount_match.group(1).replace(',', '')
                    try:
                        amount = int(float(amount_str))
                        
                        db.add_user({
                            "user_id": user_id,
                            "deposit_amount": amount,
                            "last_response": message_text,
                            "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        
                        # Show experience buttons
                        keyboard = [
                            [
                                InlineKeyboardButton("Yes", callback_data="experience_yes"),
                                InlineKeyboardButton("No", callback_data="experience_no")
                            ],
                            [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            f"<b>Deposit Amount:</b> ${amount} ✅\n\n"
                            f"Thank you! This will help us tailor the strategy to your capital.\n\n"
                            f"Have you used a trading signals service before?",
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                        
                        # CRITICAL: Set the next step for experience
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "previous_experience"
                        return
                    except ValueError:
                        # Not a valid number, store as is
                        db.add_user({
                            "user_id": user_id,
                            "notes": f"Possible deposit amount: {message_text}",
                            "last_response": message_text,
                            "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                else:
                    # No number found, store as is
                    db.add_user({
                        "user_id": user_id,
                        "notes": f"Possible deposit amount: {message_text}",
                        "last_response": message_text,
                        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        # General response - store it anyway
        db.add_user({
            "user_id": user_id,
            "notes": f"Response: {message_text}",
            "last_response": message_text,
            "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Send a generic acknowledgment with guidance if we haven't determined a specific flow
        keyboard = [
            [InlineKeyboardButton("Start Guided Setup", callback_data="start_guided")],
            [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Thank you for your response. Our team will review your information.\n\n"
            "Would you like to use our guided setup with buttons instead? This makes the process easier.",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Forward this message to the admin
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"📨 Message from {user_name} (ID: {user_id}):\n\n{message_text}"
                )
            except Exception as e:
                print(f"Error forwarding message to admin {admin_id}: {e}")

async def view_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'View User Profile' button callback."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("view_profile_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Viewing profile for user ID: {user_id}")
            
            # Get user info from database with error handling
            try:
                user_info = db.get_user(user_id)
                print(f"Retrieved user info: {user_info}")
            except Exception as e:
                print(f"Error getting user from database: {e}")
                user_info = None
                
            # If user not found in our db, check if they're in auto_welcoming_users
            if not user_info:
                print(f"User {user_id} not found in database, checking auto_welcoming_users")
                auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
                
                if user_id in auto_welcoming_users:
                    user_name = auto_welcoming_users[user_id].get("name", "Unknown User")
                    
                    # Create a basic profile with the info we have
                    profile = f"👤 USER PROFILE (Partial Info): {user_name}\n\n"
                    profile += f"User ID: {user_id}\n"
                    profile += f"Source: {auto_welcoming_users[user_id].get('source_channel', 'Unknown')}\n"
                    profile += f"WARNING: Complete profile not found in database\n\n"
                    
                    # Add action buttons
                    keyboard = [
                        [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")],
                        [InlineKeyboardButton("View Auto Welcoming Info", callback_data=f"view_welcoming_{user_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        text=profile,
                        reply_markup=reply_markup
                    )
                    return
                else:
                    await query.edit_message_text(
                        text=f"⚠️ User {user_id} not found in database or auto-welcoming lists"
                    )
                    return
            
            # Now format user profile with available info
            profile = f"👤 USER PROFILE: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n\n"
            profile += f"User ID: {user_id}\n"
            profile += f"Username: @{user_info.get('username', 'None')}\n"
            profile += f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            profile += f"Risk Profile: {user_info.get('risk_profile_text', 'Not specified')}\n"
            profile += f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            profile += f"Trading Account: {user_info.get('trading_account', 'Not provided')}\n"
            profile += f"Account Verified: {'✅ Yes' if user_info.get('is_verified') else '❌ No'}\n"
            profile += f"Join Date: {user_info.get('join_date', 'Unknown')}\n"
            profile += f"Last Active: {user_info.get('last_active', 'Unknown')}\n"
            profile += f"Last Response: {user_info.get('last_response', 'None')}\n\n"
            
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")],
                [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
                [InlineKeyboardButton("Add to VIP Strategy", callback_data=f"add_vip_strategy_{user_id}")],
                [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=profile,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            print(f"Error viewing user profile: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error viewing user profile: {e}"
            )

async def risk_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle risk profile button selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    risk_option = query.data.replace("risk_", "")
    
    # Map text options to numeric values
    risk_values = {"low": 2, "medium": 5, "high": 8}
    risk_appetite = risk_values.get(risk_option, 5)
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "risk_appetite": risk_appetite,
        "risk_profile_text": risk_option,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Ask for deposit amount next
    keyboard = [
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"<b>Risk Profile:</b> {risk_option.capitalize()} ✅\n\nHow much capital are you planning to fund your account with?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # CRITICAL: Store state in bot_data, not user_data
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "deposit_amount"
    print(f"Set state for user {user_id} to deposit_amount in bot_data")
    
    # Also notify admin of the selection
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📊 User {user_id} selected risk profile: {risk_option.capitalize()}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def restart_process_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle restart process button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Clear conversation state
    if "user_states" in context.bot_data and user_id in context.bot_data["user_states"]:
        del context.bot_data["user_states"][user_id]
    
    # Start over with risk profile buttons
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Process restarted!</b>\n\nWhat risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set state to risk_profile
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Notify admin of restart
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 User {user_id} has restarted the registration process"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def experience_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle previous experience button selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    experience = query.data.replace("experience_", "")
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "previous_experience": experience,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Ask for account number next
    keyboard = [
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"<b>Previous Experience:</b> {experience.capitalize()} ✅\n\nPlease provide your MT5 account number to continue.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # IMPORTANT: Make sure we're setting the state in bot_data
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"
    print(f"Set state for user {user_id} to account_number in bot_data")
    
    # Notify admin of the selection
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📊 User {user_id} previous experience: {experience.capitalize()}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def start_guided_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle start guided setup button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Start guided flow with buttons for risk profile
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Let's get started with your profile setup!</b>\n\nWhat risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Store current step in user data
    context.user_data["response_step"] = "risk_profile"

async def view_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle view profile summary button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    print(f"View summary requested by user ID: {user_id}")
    
    # Try multiple methods to get user info
    user_info = None
    error_messages = []
    
    # Method 1: Try db.get_user
    try:
        print("Attempting to retrieve user via db.get_user")
        user_info = db.get_user(user_id)
        if user_info:
            print(f"Successfully retrieved user via db.get_user: {user_info}")
    except Exception as e:
        error_msg = f"db.get_user error: {e}"
        print(error_msg)
        error_messages.append(error_msg)
    
    # Method 2: Try auto_welcoming_users dict
    if not user_info:
        try:
            print("Attempting to retrieve from auto_welcoming_users")
            auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
            if user_id in auto_welcoming_users:
                print(f"User found in auto_welcoming_users")
                # Create a basic info dict
                user_info = {
                    "user_id": user_id,
                    "first_name": auto_welcoming_users[user_id].get("name", "Unknown"),
                    "source_channel": auto_welcoming_users[user_id].get("source_channel", "Unknown")
                }
                
                # Check if we have risk profile and deposit amount in our state tracking
                user_states = context.bot_data.get("user_states", {})
                if user_id in user_states:
                    user_info["current_state"] = user_states[user_id]
                
                # Add trading account info if we have it
                if hasattr(auth, 'verified_users') and user_id in auth.verified_users:
                    print(f"Found user in auth.verified_users")
                    user_info["trading_account"] = auth.verified_users[user_id].get("account_number", "")
                    user_info["is_verified"] = True
                    user_info["account_owner"] = auth.verified_users[user_id].get("account_owner", "")
        except Exception as e:
            error_msg = f"Auto_welcoming access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    # Collect profile information from multiple sources if needed
    if user_info:
        # Try to get risk profile from context if not in user_info
        if ("risk_appetite" not in user_info or not user_info["risk_appetite"]) and "risk_profile" in context.user_data:
            user_info["risk_profile_text"] = context.user_data["risk_profile"]
            
        # Try to get trading account from auth system if not in user_info
        if "trading_account" not in user_info and hasattr(auth, 'verified_users'):
            if user_id in auth.verified_users:
                user_info["trading_account"] = auth.verified_users[user_id].get("account_number", "")
                user_info["is_verified"] = True
    
    if not user_info:
        # If we still don't have user_info, create a minimal one
        user_info = {
            "user_id": user_id,
            "retrieval_errors": error_messages
        }
    
    # Format summary with whatever info we have
    summary = f"""<b>📋 Your Registration Summary</b>

Thank you for providing your information! Here's what we've got:

<b>Risk Profile:</b> {user_info.get('risk_profile_text', 'Not specified').capitalize() if user_info.get('risk_profile_text') else f"{user_info.get('risk_appetite', 0)}/10"}
<b>Deposit Amount:</b> ${user_info.get('deposit_amount', 'Not specified')}
<b>Previous Experience:</b> {user_info.get('previous_experience', 'Not specified').capitalize() if user_info.get('previous_experience') else 'Not specified'}
<b>MT5 Account:</b> {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}
"""

    # Additional profile info if verified
    if user_info.get('is_verified') and user_info.get('account_owner'):
        summary += f"<b>Account Owner:</b> {user_info.get('account_owner')}\n"
    
    summary += """
<b>What's Next?</b>
Our team will review your information and set up your account for our signals service. You should receive confirmation within the next 24 hours.

If you need to make any changes or have questions, please let us know!"""

    # Add buttons for edit or confirm
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Information", callback_data="confirm_registration")],
        [InlineKeyboardButton("✏️ Edit Information", callback_data="edit_registration")],
        [InlineKeyboardButton("👨‍💼 Speak to an Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        summary,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Force send a summary to admin
    try:
        asyncio.create_task(send_profile_summary_to_admins(context, user_id))
    except Exception as e:
        print(f"Error sending profile summary to admins: {e}")

async def confirm_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation of registration."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Mark registration as confirmed in database
    db.add_user({
        "user_id": user_id,
        "registration_confirmed": True,
        "registration_confirmed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await query.edit_message_text(
        "✅ <b>Registration Confirmed!</b>\n\n"
        "Thank you for confirming your information. Our team will be in touch soon to complete your setup.\n\n"
        "If you have any questions in the meantime, feel free to ask!",
        parse_mode='HTML'
    )
    
    # Send profile summary to admins
    await send_profile_summary_to_admins(context, user_id)
    
    # Notify admin of confirmation
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ User {user_id} has confirmed their registration"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def edit_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit registration button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Provide options for what to edit
    keyboard = [
        [InlineKeyboardButton("Risk Profile", callback_data="edit_risk")],
        [InlineKeyboardButton("Deposit Amount", callback_data="edit_deposit")],
        [InlineKeyboardButton("MT5 Account", callback_data="edit_account")],
        [InlineKeyboardButton("↩️ Back to Summary", callback_data="view_summary")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Edit Registration</b>\n\nWhat information would you like to update?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def speak_advisor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle speak to advisor button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else 'User'
    
    # Notify admin that user wants to speak to an advisor
    for admin_id in ADMIN_USER_ID:
        try:
            keyboard = [
                [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 <b>ADVISOR REQUEST</b> 🔔\n\n"
                     f"User {user_name} (ID: {user_id}) has requested to speak with an advisor.\n\n"
                     f"Please respond to them as soon as possible.",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")
    
    await query.edit_message_text(
        "🔔 <b>Advisor Request Sent</b>\n\n"
        "Thank you for your request. One of our advisors will be in touch with you shortly.\n\n"
        "Please keep an eye on your messages for their response.",
        parse_mode='HTML'
    )

async def edit_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Try Another Account' button click."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Reset account number state to ask for a new one
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"
    
    await query.edit_message_text(
        "<b>Account Number</b> ⚠️\n\n"
        "Please provide a different MT5 account number:",
        parse_mode='HTML'
    )
    
    # Notify admin
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 User {user_id} is trying another account number"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def start_guided_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Start Guided Setup' button click."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Start guided flow with risk profile buttons
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Let's get started with the guided setup!</b>\n\n"
        "What risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set state to risk_profile
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Notify admin
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🚀 User {user_id} started the guided setup process"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def generate_welcome_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a welcome message with a deep link for users with privacy settings."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    if callback_data.startswith("gen_welcome_"):
        user_id = int(callback_data.split("_")[2])
        
        # Get user info if available
        auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
        user_name = auto_welcoming_users.get(user_id, {}).get("name", "there")
        
        # Create "start bot" deep link
        bot_username = await context.bot.get_me()
        bot_username = bot_username.username
        start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
        
        # Generate personalized welcome message
        welcome_template = f"""Hello {user_name}! 👋

Thank you for your interest in our VFX Trading solutions!

To get started with your account setup and access our trading services, please click the link below:

👉 {start_link}

Once you click the link:
1. You'll be connected with our automated assistant
2. Answer a few quick questions about your trading preferences
3. Verify your MT5 account number

Our team will then set up your account with the optimal parameters based on your profile.

Let me know if you have any questions!"""
        
        # Show the message with a copy button
        await query.edit_message_text(
            "✅ Here's your personalized welcome message to send to the user:\n\n"
            f"{welcome_template}\n\n"
            "Copy and paste this message to the user. After they click the link, "
            "they will be able to complete the registration process with the bot.",
            parse_mode='HTML'
        )


# -------------------------------------- MySQL Handles for Admin ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

async def test_mysql_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test MySQL database connection and functionality."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    # Test connection
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database connection failed")
        return
    
    # Test getting stats
    try:
        stats = mysql_db.get_account_stats()
        if stats:
            await update.message.reply_text(
                f"✅ <b>MySQL Connection Active</b>\n\n"
                f"📊 <b>Database Statistics:</b>\n"
                f"Total Accounts: {stats['total_accounts']:,}\n"
                f"Funded Accounts: {stats['funded_accounts']:,}\n"
                f"Active Accounts: {stats['active_accounts']:,}\n"
                f"Average Balance: ${stats['avg_balance']:,.2f}\n"
                f"Maximum Balance: ${stats['max_balance']:,.2f}\n"
                f"Total Balance: ${stats['total_balance']:,.2f}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("✅ Connected but couldn't retrieve stats")
    except Exception as e:
        await update.message.reply_text(f"❌ Error testing MySQL: {e}")

async def search_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for accounts in the MySQL database."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /searchaccount <account_number_or_name>")
        return
    
    search_term = " ".join(context.args)
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        results = mysql_db.search_accounts(search_term, limit=10)
        
        if results:
            message = f"🔍 Search Results for '{search_term}':\n\n"
            for account in results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account['email']}\n"
                message += f"<b>Balance:</b> ${account['balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Company:</b> {account['Company']}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts found for '{search_term}'")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error searching accounts: {e}")

async def recent_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recently registered accounts."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get accounts from last X days
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Try the original method first
        try:
            results = mysql_db.get_recent_registrations(days=days, limit=15)
        except Exception as e:
            print(f"Original method failed: {e}")
            # Fall back to the safer method
            results = mysql_db.get_recent_accounts(days=days, limit=15)
        
        if results:
            message = f"📅 <b>Accounts Registered in Last {days} Days:</b>\n\n"
            for account in results:
                reg_date = account.get('registration_date')
                if isinstance(reg_date, str):
                    # Parse string date
                    try:
                        from datetime import datetime
                        reg_dt = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S')
                        formatted_date = reg_dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_date = str(reg_date)
                elif reg_date:
                    # It's already a datetime object
                    formatted_date = reg_date.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_date = 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', account.get('email', 'N/A'))}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account.get('Status', 'Unknown')}\n"
                message += f"<b>Country:</b> {account.get('Country', 'Unknown')}\n"
                message += f"<b>Registered:</b> {formatted_date}\n"
                if 'days_ago' in account and account['days_ago'] is not None:
                    message += f"<b>Days Ago:</b> {account['days_ago']}\n"
                message += "\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts registered in the last {days} days")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def check_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the structure of the mt5_users table."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        structure = mysql_db.get_table_structure()
        
        if structure:
            message = "📋 MT5_USERS Table Structure:\n\n"
            for column in structure:
                message += f"Column: {column['Field']}\n"
                message += f"Type: {column['Type']}\n"
                message += f"Null: {column['Null']}\n"
                message += f"Key: {column['Key']}\n"
                message += f"Default: {column['Default']}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(message)
        else:
            await update.message.reply_text("❌ Could not retrieve table structure")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking table: {e}")

async def debug_registrations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug registration dates to see the actual data format."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get the most recent 10 accounts regardless of date
        query = """
        SELECT 
            Login as account_number,
            CONCAT(FirstName, ' ', LastName) as name,
            Registration as registration_date,
            NOW() as server_time,
            DATEDIFF(NOW(), Registration) as days_ago
        FROM mt5_users 
        ORDER BY Login DESC
        LIMIT 10
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "🔍 <b>Recent Accounts Debug Info:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                server_time = account['server_time']
                days_ago = account['days_ago']
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {reg_date}\n"
                message += f"<b>Server Time:</b> {server_time}\n"
                message += f"<b>Days Ago:</b> {days_ago}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error debugging registrations: {e}")

async def check_my_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check specific account numbers with balance and essential details (fixed datetime issues)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /checkmyaccounts <account1> <account2> ...\n\n"
            "Example: /checkmyaccounts 300666 300700 300800"
        )
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "🔍 <b>Account Details Report:</b>\n\n"
        
        for account_num in context.args:
            try:
                account_int = int(account_num)
                
                # Simplified query that avoids problematic datetime operations
                query = """
                SELECT 
                    Login,
                    CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                    FirstName,
                    LastName,
                    Email,
                    COALESCE(Balance, 0) as balance,
                    COALESCE(Credit, 0) as credit,
                    `Group` as account_group,
                    Status,
                    Country,
                    Company,
                    Registration as raw_registration,
                    LastAccess as raw_last_access,
                    Timestamp,
                    NOW() as server_time
                FROM mt5_users 
                WHERE Login = %s
                """
                
                results = mysql_db.execute_query(query, (account_int,))
                
                if results and len(results) > 0:
                    account = results[0]
                    
                    # Format balance with proper currency display
                    balance = float(account['balance']) if account['balance'] else 0.0
                    credit = float(account['credit']) if account['credit'] else 0.0
                    
                    # Color-code balance status
                    if balance > 0:
                        balance_status = "💰 Funded"
                        balance_emoji = "✅"
                    elif balance == 0:
                        balance_status = "⚪ Zero Balance"
                        balance_emoji = "⚠️"
                    else:
                        balance_status = "🔴 Negative"
                        balance_emoji = "❌"
                    
                    # Safe datetime processing
                    registration_display = "Unknown"
                    last_access_display = "Unknown"
                    account_age_display = "Unknown"
                    
                    # Process registration date safely
                    raw_reg = account.get('raw_registration')
                    if raw_reg and str(raw_reg) != '0000-00-00 00:00:00' and str(raw_reg) != 'None':
                        try:
                            if isinstance(raw_reg, str):
                                reg_date = datetime.strptime(raw_reg, '%Y-%m-%d %H:%M:%S')
                            else:
                                reg_date = raw_reg
                            registration_display = reg_date.strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Calculate age
                            age_days = (datetime.now() - reg_date).days
                            age_hours = (datetime.now() - reg_date).total_seconds() / 3600
                            account_age_display = f"{age_days} days ({int(age_hours)} hours)"
                        except:
                            registration_display = str(raw_reg)
                    
                    # Process last access safely
                    raw_access = account.get('raw_last_access')
                    if raw_access and str(raw_access) != '0000-00-00 00:00:00' and str(raw_access) != 'None':
                        try:
                            if isinstance(raw_access, str):
                                access_date = datetime.strptime(raw_access, '%Y-%m-%d %H:%M:%S')
                            else:
                                access_date = raw_access
                            last_access_display = access_date.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            last_access_display = str(raw_access)
                    
                    # Try to get creation date from timestamp if available
                    timestamp_display = "Not available"
                    if account.get('Timestamp') and account['Timestamp'] > 116444736000000000:
                        try:
                            # Convert FILETIME to readable datetime
                            timestamp_unix = (account['Timestamp'] - 116444736000000000) / 10000000
                            timestamp_date = datetime.fromtimestamp(timestamp_unix)
                            timestamp_display = timestamp_date.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            timestamp_display = f"Raw: {account['Timestamp']}"
                    
                    # Build the account info message
                    message += f"📊 <b>Account {account['Login']}</b> {balance_emoji}\n"
                    message += f"👤 <b>Name:</b> {account['name'] or 'Unknown'}\n"
                    message += f"📧 <b>Email:</b> {account['Email'] or 'Not provided'}\n"
                    message += f"🏢 <b>Company:</b> {account['Company'] or 'N/A'}\n"
                    message += f"🌍 <b>Country:</b> {account['Country'] or 'N/A'}\n\n"
                    
                    # Financial Information
                    message += f"💵 <b>FINANCIAL STATUS:</b>\n"
                    message += f"• Balance: ${balance:,.2f} ({balance_status})\n"
                    if credit != 0:
                        message += f"• Credit: ${credit:,.2f}\n"
                    message += f"• Group: {account['account_group'] or 'Default'}\n"
                    message += f"• Status: {account['Status'] or 'Unknown'}\n\n"
                    
                    # Account Timeline
                    message += f"⏰ <b>TIMELINE:</b>\n"
                    message += f"• Registration: {registration_display}\n"
                    message += f"• Last Access: {last_access_display}\n"
                    message += f"• Created (Timestamp): {timestamp_display}\n"
                    message += f"• Account Age: {account_age_display}\n"
                    message += f"• Server Time: {account['server_time']}\n"
                    
                    message += "\n" + "─" * 30 + "\n\n"
                    
                else:
                    message += f"❌ <b>Account {account_num}:</b> Not found in database\n\n"
                    
            except ValueError:
                message += f"❌ <b>Account {account_num}:</b> Invalid format (must be numeric)\n\n"
            except Exception as account_error:
                message += f"❌ <b>Account {account_num}:</b> Error - {str(account_error)[:100]}\n\n"
                print(f"Error processing account {account_num}: {account_error}")
        
        # Add summary if multiple accounts
        if len(context.args) > 1:
            try:
                # Get summary statistics using the same safe approach as quickbalance
                account_ints = [int(acc) for acc in context.args if acc.isdigit()]
                if account_ints:
                    summary_query = """
                    SELECT 
                        COUNT(*) as total_found,
                        COUNT(CASE WHEN COALESCE(Balance, 0) > 0 THEN 1 END) as funded_accounts,
                        SUM(COALESCE(Balance, 0)) as total_balance,
                        AVG(COALESCE(Balance, 0)) as avg_balance,
                        MAX(COALESCE(Balance, 0)) as max_balance,
                        MIN(COALESCE(Balance, 0)) as min_balance
                    FROM mt5_users 
                    WHERE Login IN ({})
                    """.format(','.join(['%s'] * len(account_ints)))
                    
                    summary_results = mysql_db.execute_query(summary_query, account_ints)
                    
                    if summary_results and len(summary_results) > 0:
                        summary = summary_results[0]
                        message += f"📈 <b>SUMMARY ({len(context.args)} accounts requested):</b>\n"
                        message += f"• Found in DB: {summary['total_found']}\n"
                        message += f"• Funded Accounts: {summary['funded_accounts']}\n"
                        message += f"• Total Balance: ${summary['total_balance']:,.2f}\n"
                        message += f"• Average Balance: ${summary['avg_balance']:,.2f}\n"
                        message += f"• Highest Balance: ${summary['max_balance']:,.2f}\n"
                        message += f"• Lowest Balance: ${summary['min_balance']:,.2f}\n"
                        
            except Exception as summary_error:
                print(f"Error generating summary: {summary_error}")
        
        # Split message if too long
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking accounts: {e}")
        print(f"Error in check_my_accounts_command: {e}")

async def quick_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick balance check for specific accounts (simplified output)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /quickbalance <account1> <account2> ...")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "💰 <b>Quick Balance Check:</b>\n\n"
        total_balance = 0
        found_accounts = 0
        
        for account_num in context.args:
            try:
                account_int = int(account_num)
                
                # Simple balance query
                query = """
                SELECT 
                    Login,
                    CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                    COALESCE(Balance, 0) as balance,
                    Status
                FROM mt5_users 
                WHERE Login = %s
                """
                
                results = mysql_db.execute_query(query, (account_int,))
                
                if results and len(results) > 0:
                    account = results[0]
                    balance = float(account['balance'])
                    total_balance += balance
                    found_accounts += 1
                    
                    # Status emoji
                    if balance > 0:
                        emoji = "✅"
                    elif balance == 0:
                        emoji = "⚪"
                    else:
                        emoji = "❌"
                    
                    message += f"{emoji} <b>{account['Login']}</b>: ${balance:,.2f} ({account['name'] or 'Unknown'})\n"
                else:
                    message += f"❌ <b>{account_num}:</b> Not found\n"
                    
            except ValueError:
                message += f"❌ <b>{account_num}:</b> Invalid format\n"
        
        # Add totals
        if found_accounts > 0:
            message += f"\n📊 <b>Total:</b> {found_accounts} accounts, ${total_balance:,.2f}"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking balances: {e}")

async def simple_reg_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simple check of registration dates."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Just get the registration dates without any fancy calculations
        query = """
        SELECT 
            Login,
            CONCAT(FirstName, ' ', LastName) as name,
            Registration
        FROM mt5_users 
        ORDER BY Login DESC
        LIMIT 15
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "📅 <b>Raw Registration Dates:</b>\n\n"
            for account in results:
                message += f"<b>{account['Login']}:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {account['Registration']}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def test_recent_fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test the recent accounts fix with multiple approaches."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    await update.message.reply_text("🔄 Testing different approaches to handle date issues...")
    
    # Test 1: Safe method
    try:
        safe_results = mysql_db.get_recent_accounts(days=15, limit=5)
        
        if safe_results:
            message = f"✅ <b>Safe Method Results (Last 15 Days):</b>\n\n"
            for account in safe_results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {account.get('registration_date', 'N/A')}\n"
                message += f"<b>Days Ago:</b> {account.get('days_ago', 'N/A')}\n\n"
                
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("✅ Safe method worked but found no recent results")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Safe method also failed: {e}")
        
    # Test 2: Very basic query
    try:
        basic_query = """
        SELECT 
            Login,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Registration
        FROM mt5_users 
        WHERE Login > 300000
        ORDER BY Login DESC
        LIMIT 10
        """
        
        basic_results = mysql_db.execute_query(basic_query)
        
        if basic_results:
            message = "✅ <b>Basic Query Results (Recent Logins):</b>\n\n"
            for account in basic_results:
                reg_date = account.get('Registration', 'N/A')
                if reg_date == '0000-00-00 00:00:00':
                    reg_date = 'Invalid Date'
                    
                message += f"<b>Account:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {reg_date}\n\n"
                
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Basic query returned no results")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Basic query failed: {e}")

async def debug_zero_dates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to understand the zero date issue."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check how many records have zero dates
        debug_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN Registration = '0000-00-00 00:00:00' THEN 1 END) as zero_dates,
            COUNT(CASE WHEN Registration IS NULL THEN 1 END) as null_dates,
            COUNT(CASE WHEN Registration > '1970-01-01 00:00:00' THEN 1 END) as valid_dates,
            MIN(Registration) as min_date,
            MAX(Registration) as max_date
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(debug_query)
        
        if results and len(results) > 0:
            stats = results[0]
            message = f"📊 <b>Registration Date Analysis:</b>\n\n"
            message += f"<b>Total Records:</b> {stats['total_records']:,}\n"
            message += f"<b>Zero Dates:</b> {stats['zero_dates']:,}\n"
            message += f"<b>Null Dates:</b> {stats['null_dates']:,}\n"
            message += f"<b>Valid Dates:</b> {stats['valid_dates']:,}\n"
            message += f"<b>Min Date:</b> {stats['min_date']}\n"
            message += f"<b>Max Date:</b> {stats['max_date']}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Could not retrieve date statistics")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error analyzing dates: {e}")

async def check_mysql_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check MySQL SQL mode and settings."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check SQL mode
        mode_results = mysql_db.execute_query("SELECT @@sql_mode as sql_mode")
        timezone_results = mysql_db.execute_query("SELECT @@time_zone as time_zone")
        version_results = mysql_db.execute_query("SELECT VERSION() as version")
        
        message = "⚙️ <b>MySQL Configuration:</b>\n\n"
        
        if mode_results:
            message += f"<b>SQL Mode:</b> {mode_results[0]['sql_mode']}\n\n"
        
        if timezone_results:
            message += f"<b>Time Zone:</b> {timezone_results[0]['time_zone']}\n\n"
            
        if version_results:
            message += f"<b>Version:</b> {version_results[0]['version']}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking MySQL configuration: {e}")

async def test_timestamp_approach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test using the Timestamp column instead of Registration."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Test the Timestamp column
        test_query = """
        SELECT 
            Login,
            Timestamp,
            FROM_UNIXTIME(Timestamp) as readable_timestamp,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Registration
        FROM mt5_users 
        WHERE Timestamp > 0
        ORDER BY Timestamp DESC
        LIMIT 10
        """
        
        results = mysql_db.execute_query(test_query)
        
        if results:
            message = "🕒 <b>Testing Timestamp Column:</b>\n\n"
            for account in results:
                timestamp = account['Timestamp']
                readable_time = account['readable_timestamp']
                message += f"<b>Account:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Timestamp:</b> {timestamp}\n"
                message += f"<b>Readable:</b> {readable_time}\n"
                message += f"<b>Registration:</b> {account['Registration']}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No results from timestamp test")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error testing timestamp: {e}")

async def recent_accounts_timestamp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get recent accounts using the safe Timestamp column."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Calculate Unix timestamp for X days ago
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Timestamp,
            FROM_UNIXTIME(Timestamp) as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            ROUND((UNIX_TIMESTAMP() - Timestamp) / 86400) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 0
        ORDER BY Timestamp DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(query, (cutoff_timestamp,))
        
        if results:
            message = f"📅 <b>Recent Accounts (Last {days} Days) - Using Timestamp:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                if reg_date:
                    formatted_date = reg_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(reg_date, 'strftime') else str(reg_date)
                else:
                    formatted_date = 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Created:</b> {formatted_date}\n"
                message += f"<b>Days Ago:</b> {account['days_ago']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts found in the last {days} days using Timestamp")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def recent_accounts_by_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get recent accounts using Login ID (simplest approach)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get the number of recent accounts to show
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 20
        
        # Simple query using Login ID (higher = newer)
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            CASE 
                WHEN Registration != '0000-00-00 00:00:00' THEN Registration
                ELSE 'No valid date'
            END as registration_display
        FROM mt5_users 
        WHERE Login >= 300000
        ORDER BY Login DESC
        LIMIT %s
        """
        
        results = mysql_db.execute_query(query, (limit,))
        
        if results:
            message = f"📅 <b>Most Recent {limit} Accounts (by Login ID):</b>\n\n"
            for account in results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Registration:</b> {account['registration_display']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No recent accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def find_recent_login_threshold_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find what Login ID represents 'recent' accounts."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Find Login ID ranges
        query = """
        SELECT 
            MIN(Login) as min_login,
            MAX(Login) as max_login,
            COUNT(*) as total_accounts,
            COUNT(CASE WHEN Login >= 300000 THEN 1 END) as accounts_over_300k,
            COUNT(CASE WHEN Login >= 300500 THEN 1 END) as accounts_over_300_5k,
            COUNT(CASE WHEN Login >= 300600 THEN 1 END) as accounts_over_300_6k,
            COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300_7k,
            COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300_8k
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(query)
        
        if results and len(results) > 0:
            stats = results[0]
            message = f"📊 <b>Login ID Analysis:</b>\n\n"
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login ID Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,000:</b> {stats['accounts_over_300k']:,}\n"
            message += f"<b>Accounts with Login >= 300,500:</b> {stats['accounts_over_300_5k']:,}\n"
            message += f"<b>Accounts with Login >= 300,600:</b> {stats['accounts_over_300_6k']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,700:</b> {stats['accounts_over_300_7k']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,800:</b> {stats['accounts_over_300_8k']:,}\n\n"
            
            # Suggest threshold
            if stats['accounts_over_300_6k'] > 0:
                message += "💡 <b>Suggestion:</b> Use Login >= 300600 for very recent accounts\n"
            elif stats['accounts_over_300_5k'] > 0:
                message += "💡 <b>Suggestion:</b> Use Login >= 300500 for recent accounts\n"
            else:
                message += "💡 <b>Suggestion:</b> Use Login >= 300000 for recent accounts\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Could not retrieve Login ID statistics")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error analyzing Login IDs: {e}")

async def diagnose_account_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Diagnose what accounts we can actually see."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Test 1: Check if we can see specific account you mentioned
        specific_accounts = [300790, 300800, 300666, 300665]
        
        message = "🔍 <b>Account Access Diagnostic:</b>\n\n"
        
        for account_id in specific_accounts:
            try:
                query = "SELECT Login, FirstName, LastName FROM mt5_users WHERE Login = %s"
                result = mysql_db.execute_query(query, (account_id,))
                
                if result:
                    message += f"<b>Account {account_id}:</b> ✅ Found - {result[0]['FirstName']} {result[0]['LastName']}\n"
                else:
                    message += f"<b>Account {account_id}:</b> ❌ Not found\n"
            except Exception as e:
                message += f"<b>Account {account_id}:</b> Error - {str(e)[:50]}\n"
        
        # Test 2: Check highest Login IDs we can actually see
        try:
            query = "SELECT Login FROM mt5_users ORDER BY Login DESC LIMIT 10"
            results = mysql_db.execute_query(query)
            
            if results:
                message += f"\n<b>🔝 Highest Login IDs visible:</b>\n"
                for result in results:
                    message += f"  {result['Login']}\n"
            else:
                message += f"\n<b>Highest Login IDs:</b> None found\n"
        except Exception as e:
            message += f"\n<b>Highest Login IDs:</b> Error - {e}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Diagnostic error: {e}")

async def test_safe_login_query_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test a completely safe query that avoids datetime columns."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Ultra-safe query that completely avoids datetime columns
        safe_query = """
        SELECT 
            Login,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group`,
            Status,
            Country
        FROM mt5_users 
        WHERE Login >= 300000
        ORDER BY Login DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(safe_query)
        
        if results:
            message = f"✅ <b>Safe Query Results (No Datetime Columns):</b>\n\n"
            for account in results:
                message += f"<b>Login:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Status:</b> {account['Status']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No results from safe query")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Safe query also failed: {e}")

async def decode_mt5_timestamp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Try to decode the MT5 timestamp format."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get some timestamps to analyze
        query = """
        SELECT 
            Login,
            Timestamp,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
        FROM mt5_users 
        WHERE Timestamp > 0
        ORDER BY Login DESC
        LIMIT 5
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "🕒 <b>MT5 Timestamp Analysis:</b>\n\n"
            
            for account in results:
                timestamp = account['Timestamp']
                
                # Try different timestamp interpretations
                try:
                    # Method 1: Treat as Windows FILETIME (100-nanosecond intervals since 1601-01-01)
                    # Convert to Unix timestamp: (filetime - 116444736000000000) / 10000000
                    unix_timestamp = (timestamp - 116444736000000000) / 10000000
                    if unix_timestamp > 0:
                        from datetime import datetime
                        converted_date = datetime.fromtimestamp(unix_timestamp)
                        filetime_result = converted_date.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        filetime_result = "Invalid"
                except:
                    filetime_result = "Error"
                
                # Method 2: Treat as microseconds since epoch
                try:
                    microsecond_timestamp = timestamp / 1000000
                    micro_date = datetime.fromtimestamp(microsecond_timestamp)
                    microsecond_result = micro_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    microsecond_result = "Error"
                
                # Method 3: Treat as milliseconds since epoch  
                try:
                    millisecond_timestamp = timestamp / 1000
                    milli_date = datetime.fromtimestamp(millisecond_timestamp)
                    millisecond_result = milli_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    millisecond_result = "Error"
                
                message += f"<b>Account {account['Login']}:</b> {account['name']}\n"
                message += f"<b>Raw Timestamp:</b> {timestamp}\n"
                message += f"<b>As FILETIME:</b> {filetime_result}\n"
                message += f"<b>As Microseconds:</b> {microsecond_result}\n"
                message += f"<b>As Milliseconds:</b> {millisecond_result}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No timestamp data found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Timestamp analysis error: {e}")

async def check_user_permissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check what permissions our database user has."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check current user and permissions
        queries = [
            ("Current User", "SELECT USER() as current_user"),
            ("Current Database", "SELECT DATABASE() as current_db"),
            ("User Grants", "SHOW GRANTS"),
            ("Table Count Check", "SELECT COUNT(*) as total_rows FROM mt5_users"),
        ]
        
        message = "🔐 <b>Database Permissions Check:</b>\n\n"
        
        for check_name, query in queries:
            try:
                results = mysql_db.execute_query(query)
                if results:
                    if check_name == "User Grants":
                        message += f"<b>{check_name}:</b>\n"
                        for grant in results:
                            grant_text = list(grant.values())[0]
                            message += f"  {grant_text}\n"
                        message += "\n"
                    else:
                        result_value = list(results[0].values())[0]
                        message += f"<b>{check_name}:</b> {result_value}\n"
                else:
                    message += f"<b>{check_name}:</b> No results\n"
            except Exception as e:
                message += f"<b>{check_name}:</b> Error - {str(e)[:100]}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Permissions check error: {e}")
        
async def recent_accounts_final_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Final working version - get recent accounts using FILETIME."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Use FILETIME timestamp for accurate recent account filtering
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_filetime = int((cutoff_date.timestamp() * 10000000) + 116444736000000000)
        
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Timestamp,
            FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            ROUND((UNIX_TIMESTAMP() * 10000000 + 116444736000000000 - Timestamp) / 864000000000) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 116444736000000000
        ORDER BY Timestamp DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(query, (cutoff_filetime,))
        
        if results:
            message = f"📅 <b>Recent Accounts (Last {days} Days) - FINAL VERSION:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                formatted_date = reg_date.strftime('%Y-%m-%d %H:%M:%S') if reg_date else 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Created:</b> {formatted_date}\n"
                message += f"<b>Days Ago:</b> {account['days_ago']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts created in the last {days} days")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def newest_accounts_simple_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ultra-simple version - just get the newest accounts by Login ID."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
        
        # Completely safe query - no datetime columns at all
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as created_date
        FROM mt5_users 
        WHERE Timestamp > 116444736000000000
        ORDER BY Login DESC
        LIMIT %s
        """
        
        results = mysql_db.execute_query(query, (limit,))
        
        if results:
            message = f"📅 <b>Newest {limit} Accounts (by Login ID):</b>\n\n"
            for account in results:
                created_date = account['created_date']
                formatted_date = created_date.strftime('%Y-%m-%d %H:%M:%S') if created_date else 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Created:</b> {formatted_date}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting newest accounts: {e}")

async def show_all_tables_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all tables in the current database."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Show all tables in current database
        tables_query = "SHOW TABLES"
        results = mysql_db.execute_query(tables_query)
        
        if results:
            message = "📋 <b>All Tables in 'metatrader5' Database:</b>\n\n"
            
            for table in results:
                table_name = list(table.values())[0]  # Get the table name
                
                # Get row count for each table
                try:
                    count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
                    count_result = mysql_db.execute_query(count_query)
                    row_count = count_result[0]['count'] if count_result else 0
                    
                    message += f"📊 <b>{table_name}</b>: {row_count:,} rows\n"
                except Exception as e:
                    message += f"📊 <b>{table_name}</b>: Error counting - {str(e)[:50]}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No tables found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error showing tables: {e}")
        
async def show_all_databases_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all databases available."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Show all databases
        databases_query = "SHOW DATABASES"
        results = mysql_db.execute_query(databases_query)
        
        if results:
            message = "🗄️ <b>All Available Databases:</b>\n\n"
            
            for db in results:
                db_name = list(db.values())[0]  # Get the database name
                
                # Check if we can access it
                try:
                    use_query = f"SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = '{db_name}'"
                    table_count_result = mysql_db.execute_query(use_query)
                    table_count = table_count_result[0]['table_count'] if table_count_result else 0
                    
                    message += f"🗂️ <b>{db_name}</b>: {table_count} tables\n"
                except Exception as e:
                    message += f"🗂️ <b>{db_name}</b>: Access error\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No databases found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error showing databases: {e}")
        
        
async def search_user_tables_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for tables that might contain user/account data."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Search for tables with user/account-related names
        search_query = """
        SELECT 
            table_schema as database_name,
            table_name,
            table_rows as estimated_rows
        FROM information_schema.tables 
        WHERE table_name LIKE '%user%' 
           OR table_name LIKE '%account%' 
           OR table_name LIKE '%mt5%'
           OR table_name LIKE '%client%'
           OR table_name LIKE '%trader%'
           OR table_name LIKE '%login%'
        ORDER BY table_schema, table_name
        """
        
        results = mysql_db.execute_query(search_query)
        
        if results:
            message = "🔍 <b>Tables That Might Contain Account Data:</b>\n\n"
            
            current_db = None
            for table in results:
                db_name = table['database_name']
                table_name = table['table_name']
                row_count = table['estimated_rows'] or 0
                
                if db_name != current_db:
                    message += f"\n📂 <b>Database: {db_name}</b>\n"
                    current_db = db_name
                
                message += f"  📊 {table_name}: ~{row_count:,} rows\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No user/account tables found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error searching tables: {e}")
        
async def check_table_for_high_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check a specific table for high account numbers."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    # Get table name from command arguments
    if not context.args:
        await update.message.reply_text(
            "Usage: /checktable <table_name>\n\n"
            "Example: /checktable mt5_users\n"
            "Use /showtables first to see available tables"
        )
        return
    
    table_name = context.args[0]
    
    try:
        # First, check if table exists and has a Login column
        describe_query = f"DESCRIBE `{table_name}`"
        table_structure = mysql_db.execute_query(describe_query)
        
        if not table_structure:
            await update.message.reply_text(f"❌ Table '{table_name}' not found")
            return
        
        # Check if Login column exists
        columns = [col['Field'] for col in table_structure]
        if 'Login' not in columns:
            await update.message.reply_text(
                f"❌ Table '{table_name}' doesn't have a 'Login' column\n\n"
                f"Available columns: {', '.join(columns)}"
            )
            return
        
        # Check for high account numbers
        high_accounts_query = f"""
        SELECT 
            MIN(Login) as min_login,
            MAX(Login) as max_login,
            COUNT(*) as total_accounts,
            COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300700,
            COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300800
        FROM `{table_name}`
        """
        
        results = mysql_db.execute_query(high_accounts_query)
        
        if results:
            stats = results[0]
            message = f"📊 <b>Account Analysis for Table '{table_name}':</b>\n\n"
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n"
            message += f"<b>Accounts >= 300,700:</b> {stats['accounts_over_300700']:,}\n"
            message += f"<b>Accounts >= 300,800:</b> {stats['accounts_over_300800']:,}\n\n"
            
            # If we found high accounts, show some examples
            if stats['max_login'] > 300700:
                sample_query = f"""
                SELECT Login, 
                       CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
                FROM `{table_name}` 
                WHERE Login >= 300700 
                ORDER BY Login DESC 
                LIMIT 5
                """
                
                sample_results = mysql_db.execute_query(sample_query)
                if sample_results:
                    message += "<b>🎯 High Account Numbers Found:</b>\n"
                    for account in sample_results:
                        message += f"  {account['Login']}: {account['name']}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No data found in table '{table_name}'")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking table '{table_name}': {e}")

async def compare_current_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show info about the current table we're using."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "📋 <b>Current Table Information:</b>\n\n"
        message += f"<b>Database:</b> metatrader5\n"
        message += f"<b>Table:</b> mt5_users\n\n"
        
        # Get basic stats
        stats_query = """
        SELECT 
            COUNT(*) as total_accounts,
            MIN(Login) as min_login,
            MAX(Login) as max_login
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(stats_query)
        if results:
            stats = results[0]
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n\n"
        
        message += "<b>This is the table that contains accounts up to 300666</b>\n"
        message += "<b>Accounts 300700+ might be in a different table</b>"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting current table info: {e}")


async def check_mt5_accounts_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the mt5_accounts table structure and content."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # First, check the structure of mt5_accounts
        structure_query = "DESCRIBE mt5_accounts"
        structure_results = mysql_db.execute_query(structure_query)
        
        if structure_results:
            message = "📋 <b>MT5_ACCOUNTS Table Structure:</b>\n\n"
            for column in structure_results[:10]:  # Show first 10 columns
                message += f"<b>{column['Field']}</b>: {column['Type']}\n"
            
            if len(structure_results) > 10:
                message += f"... and {len(structure_results) - 10} more columns\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        
        # Check if it has a Login column and get stats
        columns = [col['Field'] for col in structure_results]
        if 'Login' in columns:
            stats_query = """
            SELECT 
                COUNT(*) as total_accounts,
                MIN(Login) as min_login,
                MAX(Login) as max_login,
                COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300700,
                COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300800
            FROM mt5_accounts
            """
            
            stats_results = mysql_db.execute_query(stats_query)
            
            if stats_results:
                stats = stats_results[0]
                message = f"📊 <b>MT5_ACCOUNTS Table Analysis:</b>\n\n"
                message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
                message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n"
                message += f"<b>Accounts >= 300,700:</b> {stats['accounts_over_300700']:,}\n"
                message += f"<b>Accounts >= 300,800:</b> {stats['accounts_over_300800']:,}\n\n"
                
                # Check if this table has higher accounts
                if stats['max_login'] > 300700:
                    message += "🎯 <b>FOUND IT! This table has higher account numbers!</b>\n\n"
                    
                    # Show some examples of high accounts
                    sample_query = """
                    SELECT Login, 
                           CONCAT(COALESCE(Name, ''), ' ', COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
                    FROM mt5_accounts 
                    WHERE Login >= 300700 
                    ORDER BY Login DESC 
                    LIMIT 10
                    """
                    
                    sample_results = mysql_db.execute_query(sample_query)
                    if sample_results:
                        message += "<b>Sample High Account Numbers:</b>\n"
                        for account in sample_results:
                            message += f"  {account['Login']}: {account['name']}\n"
                else:
                    message += "❌ This table also only goes up to 300666\n"
                
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ mt5_accounts table doesn't have a Login column")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking mt5_accounts table: {e}")

async def compare_users_vs_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compare mt5_users vs mt5_accounts tables."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get structure of both tables
        users_structure = mysql_db.execute_query("DESCRIBE mt5_users")
        accounts_structure = mysql_db.execute_query("DESCRIBE mt5_accounts")
        
        message = "🔍 <b>MT5_USERS vs MT5_ACCOUNTS Comparison:</b>\n\n"
        
        # Compare column counts
        users_cols = len(users_structure) if users_structure else 0
        accounts_cols = len(accounts_structure) if accounts_structure else 0
        
        message += f"<b>MT5_USERS:</b> {users_cols} columns\n"
        message += f"<b>MT5_ACCOUNTS:</b> {accounts_cols} columns\n\n"
        
        # Check if both have Login column
        users_columns = [col['Field'] for col in users_structure] if users_structure else []
        accounts_columns = [col['Field'] for col in accounts_structure] if accounts_structure else []
        
        message += f"<b>MT5_USERS has Login column:</b> {'✅' if 'Login' in users_columns else '❌'}\n"
        message += f"<b>MT5_ACCOUNTS has Login column:</b> {'✅' if 'Login' in accounts_columns else '❌'}\n\n"
        
        # Show unique columns in each table
        if users_columns and accounts_columns:
            users_only = set(users_columns) - set(accounts_columns)
            accounts_only = set(accounts_columns) - set(users_columns)
            common = set(users_columns) & set(accounts_columns)
            
            message += f"<b>Common columns:</b> {len(common)}\n"
            message += f"<b>Only in MT5_USERS:</b> {len(users_only)}\n"
            message += f"<b>Only in MT5_ACCOUNTS:</b> {len(accounts_only)}\n\n"
            
            if accounts_only:
                message += f"<b>Unique to MT5_ACCOUNTS:</b>\n"
                for col in sorted(list(accounts_only)[:10]):  # Show first 10
                    message += f"  • {col}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error comparing tables: {e}")

async def check_accounts_table_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a sample of data from mt5_accounts table."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get structure first to see what columns are available
        structure_query = "DESCRIBE mt5_accounts"
        structure_results = mysql_db.execute_query(structure_query)
        
        if not structure_results:
            await update.message.reply_text("❌ Could not access mt5_accounts table")
            return
        
        columns = [col['Field'] for col in structure_results]
        
        # Build a safe query based on available columns
        select_columns = []
        if 'Login' in columns:
            select_columns.append('Login')
        if 'Name' in columns:
            select_columns.append('Name')
        if 'FirstName' in columns:
            select_columns.append('FirstName')
        if 'LastName' in columns:
            select_columns.append('LastName')
        if 'Balance' in columns:
            select_columns.append('COALESCE(Balance, 0) as Balance')
        if 'Group' in columns:
            select_columns.append('`Group`')
        if 'Status' in columns:
            select_columns.append('Status')
        
        if not select_columns:
            await update.message.reply_text("❌ No recognizable columns found in mt5_accounts")
            return
        
        # Get sample data
        sample_query = f"""
        SELECT {', '.join(select_columns)}
        FROM mt5_accounts 
        ORDER BY Login DESC 
        LIMIT 10
        """
        
        results = mysql_db.execute_query(sample_query)
        
        if results:
            message = "📊 <b>MT5_ACCOUNTS Sample Data (Top 10 by Login):</b>\n\n"
            
            for account in results:
                message += f"<b>Login:</b> {account.get('Login', 'N/A')}\n"
                
                # Build name from available fields
                name_parts = []
                if 'Name' in account and account['Name']:
                    name_parts.append(account['Name'])
                if 'FirstName' in account and account['FirstName']:
                    name_parts.append(account['FirstName'])
                if 'LastName' in account and account['LastName']:
                    name_parts.append(account['LastName'])
                
                name = ' '.join(name_parts) if name_parts else 'N/A'
                message += f"<b>Name:</b> {name}\n"
                
                if 'Balance' in account:
                    message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                if 'Group' in account:
                    message += f"<b>Group:</b> {account.get('Group', 'N/A')}\n"
                if 'Status' in account:
                    message += f"<b>Status:</b> {account.get('Status', 'N/A')}\n"
                
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No data found in mt5_accounts table")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting sample from mt5_accounts: {e}")


# -------------------------------------- SIGNALS HANDLERS ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

signal_dispatcher = None
signal_system_initialized = False
async def init_signal_system(context: ContextTypes.DEFAULT_TYPE):
    """Initialize the signal system after bot startup"""
    global signal_dispatcher, signal_system_initialized
    
    # Skip if already initialized
    if signal_system_initialized:
        logger.info("Signal system already initialized, skipping")
        return
    
    try:
        logger.info("Starting signal system initialization...")
        
        # Initialize signal dispatcher with the bot instance
        signal_dispatcher = SignalDispatcher(context.bot, SIGNALS_CHANNEL_ID)
        
        # Mark as initialized
        signal_system_initialized = True
        logger.info("Signal system initialized successfully")
        
    except Exception as e:
        logger.error(f"Error in init_signal_system: {e}")

# Define the scheduled function
async def check_and_send_signals(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check for and send trading signals based on market conditions"""
    global signal_dispatcher
    if signal_dispatcher:
        await signal_dispatcher.check_and_send_signal()
        
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




# -------------------------------------- MAIN ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #
(RISK_APPETITE_MANUAL, DEPOSIT_AMOUNT_MANUAL, TRADING_ACCOUNT_MANUAL) = range(100, 103)  # Using different ranges to avoid conflicts

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


(RISK_APPETITE, DEPOSIT_AMOUNT, TRADING_ACCOUNT, CAPTCHA_RESPONSE, 
 AWAITING_DEPOSIT_DECISION, PAYMENT_METHOD_SELECTION, DEPOSIT_CONFIRMATION) = range(7)

# async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Store deposit amount and ask for trading interests."""
#     try:
#         amount = int(update.message.text)
#         if 100 <= amount <= 10000:
#             user_id = update.effective_user.id
            
#             # Store in user_data for conversation
#             context.user_data["user_info"]["deposit_amount"] = amount
            
#             # Update in database
#             db.add_user({
#                 "user_id": user_id,
#                 "deposit_amount": amount
#             })
            
#             # Ask for trading interests with buttons
#             keyboard = [
#                 [InlineKeyboardButton("Trading Signals", callback_data="interest_signals")],
#                 [InlineKeyboardButton("Trading Strategy", callback_data="interest_strategy")],
#                 [InlineKeyboardButton("Prop Capital", callback_data="interest_propcapital")],
#                 [InlineKeyboardButton("All Services", callback_data="interest_all")]
#             ]
#             reply_markup = InlineKeyboardMarkup(keyboard)
            
#             await update.message.reply_text(
#                 "Great! Which of our VIP services are you interested in?",
#                 reply_markup=reply_markup
#             )
            
#             return TRADING_INTEREST
#         else:
#             await update.message.reply_text("Please enter an amount between 100 and 10,000.")
#             return DEPOSIT_AMOUNT
#     except ValueError:
#         await update.message.reply_text("Please enter a valid amount between 100 and 10,000.")
#         return DEPOSIT_AMOUNT

async def trading_interest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle selection of trading interests and route to appropriate VIP channels."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    callback_data = query.data
    interest = callback_data.replace("interest_", "")
    
    # Store the interest in user data
    if "user_info" not in context.user_data:
        context.user_data["user_info"] = {}
    context.user_data["user_info"]["trading_interest"] = interest
    
    # Update in database
    db.add_user({
        "user_id": user_id,
        "trading_interest": interest
    })
    
    # Map interests to appropriate VIP channels
    vip_channels = {
        "signals": {"name": "VIP Signals", "channel_id": SIGNALS_CHANNEL_ID, "group_id": SIGNALS_GROUP_ID},
        "strategy": {"name": "VIP Strategy", "channel_id": STRATEGY_CHANNEL_ID, "group_id": STRATEGY_GROUP_ID},
        "propcapital": {"name": "VIP Prop Capital", "channel_id": PROP_CHANNEL_ID, "group_id": PROP_GROUP_ID},
    }
    
    # Store assigned channels in user data for admin reference
    assigned_channels = []
    
    if interest == "all":
        for channel_info in vip_channels.values():
            assigned_channels.append(channel_info)
        # Update with list of all channel names
        interest_display = "All VIP Services (Signals, Strategy, Prop Capital)"
    else:
        assigned_channels.append(vip_channels[interest])
        # Get user-friendly name for display
        interest_display = f"VIP {interest.capitalize()}"
    
    # Store in user data for later reference
    context.user_data["user_info"]["assigned_channels"] = assigned_channels
    
    # Confirm selection to user with clear next steps
    await query.edit_message_text(
        f"Thanks for selecting {interest_display}! 🎯\n\n"
        f"Now, please enter your Vortex FX MT5 account number for verification."
    )
    
    return TRADING_ACCOUNT

async def enhanced_trading_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enhanced trading account verification with real-time balance checking."""
    account_number = update.message.text.strip()
    user_id = update.effective_user.id
    
    print(f"===== ENHANCED ACCOUNT VERIFICATION =====")
    print(f"Account: {account_number}, User: {user_id}")
    
    # Get user's stated deposit intention from conversation context
    user_info = context.user_data.get("user_info", {})
    stated_amount = user_info.get("deposit_amount", 0)
    
    print(f"User stated deposit intention: ${stated_amount}")
    
    await update.message.reply_text("🔍 Verifying your account and checking balance...")
    
    # Validate account format first
    if not auth.validate_account_format(account_number):
        await update.message.reply_text(
            "❌ Invalid account format. Please enter a valid trading account number."
        )
        return TRADING_ACCOUNT
    
    # Connect to MySQL and verify account
    mysql_db = get_mysql_connection()
    if not mysql_db.is_connected():
        await update.message.reply_text(
            "⚠️ Unable to verify account at the moment. Please try again later."
        )
        return TRADING_ACCOUNT
    
    # Get real account information including balance
    try:
        account_int = int(account_number)
        account_info = mysql_db.verify_account_exists(account_number)
        
        if not account_info['exists']:
            await update.message.reply_text(
                f"❌ Account {account_number} not found in our system.\n\n"
                f"Please check the account number or contact support if you believe this is an error."
            )
            return TRADING_ACCOUNT
        
        # Extract account details
        real_balance = float(account_info.get('balance', 0))
        account_name = account_info.get('name', 'Unknown')
        account_status = account_info.get('status', 'Unknown')
        
        print(f"Account found: {account_name}, Balance: ${real_balance}, Status: {account_status}")
        
        # Store account info in context for later use
        context.user_data["verified_account"] = {
            "account_number": account_number,
            "name": account_name,
            "balance": real_balance,
            "status": account_status,
            "full_info": account_info
        }
        
        # Store in database
        db.add_user({
            "user_id": user_id,
            "trading_account": account_number,
            "account_owner": account_name,
            "account_balance": real_balance,
            "account_status": account_status,
            "is_verified": True,
            "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Decision logic based on balance vs stated amount
        if real_balance >= stated_amount:
            return await handle_sufficient_funds(update, context, account_info, stated_amount, real_balance)
        elif real_balance > 0:
            return await handle_partial_funds(update, context, account_info, stated_amount, real_balance)
        else:
            return await handle_no_funds(update, context, account_info, stated_amount)
            
    except Exception as e:
        print(f"Error verifying account: {e}")
        await update.message.reply_text(
            f"⚠️ Error verifying account: {e}\n\nPlease try again or contact support."
        )
        return TRADING_ACCOUNT

async def handle_sufficient_funds(update, context, account_info, stated_amount, real_balance):
    """Handle users who already have sufficient balance."""
    print(f"User has sufficient funds: ${real_balance} >= ${stated_amount}")
    
    success_message = (
        f"✅ **Account Verified Successfully!** ✅\n\n"
        f"**Account:** {account_info['account_number']}\n"
        f"**Account Holder:** {account_info['name']}\n"
        f"**Current Balance:** ${real_balance:,.2f} 💰\n"
        f"**Required:** ${stated_amount:,.2f}\n\n"
        f"🎉 **Excellent!** You have sufficient funds to access all our VIP services!\n\n"
        f"**You now have access to:**\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 📈 Advanced Trading Strategies\n"
        f"• 💰 Prop Capital Opportunities\n"
        f"• 👨‍💼 Personal Trading Support\n"
        f"• 📞 Priority Customer Service\n\n"
        f"Our team will set up your VIP access within the next few minutes!"
    )
    
    # Create VIP access buttons
    keyboard = [
        [
            InlineKeyboardButton("🔔 Access VIP Signals", callback_data="access_vip_signals"),
            InlineKeyboardButton("📈 Access VIP Strategy", callback_data="access_vip_strategy")
        ],
        [
            InlineKeyboardButton("💰 Access Prop Capital", callback_data="access_vip_propcapital"),
            InlineKeyboardButton("👨‍💼 Speak to Advisor", callback_data="speak_advisor")
        ],
        [InlineKeyboardButton("📋 View My Profile", callback_data="view_summary")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(success_message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Mark user as fully verified and funded
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "sufficient",
        "vip_eligible": True,
        "vip_access_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Notify admins of successful verification
    await notify_admins_success(context, update.effective_user.id, account_info, stated_amount, real_balance)
    
    return ConversationHandler.END

async def handle_partial_funds(update, context, account_info, stated_amount, real_balance):
    """Handle users with some funds but less than stated amount."""
    difference = stated_amount - real_balance
    percentage = (real_balance / stated_amount) * 100
    
    print(f"User has partial funds: ${real_balance} of ${stated_amount} ({percentage:.1f}%)")
    
    message = (
        f"✅ **Account Successfully Verified!**\n\n"
        f"**Account:** {account_info['account_number']}\n"
        f"**Account Holder:** {account_info['name']}\n"
        f"**Current Balance:** ${real_balance:,.2f}\n"
        f"**Your Goal:** ${stated_amount:,.2f}\n"
        f"**Remaining:** ${difference:,.2f}\n\n"
        f"📊 **You're {percentage:.1f}% of the way there!** 🎯\n\n"
        f"**What would you like to do?**"
    )
    
    # Create action buttons
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit ${difference:,.0f} Now", callback_data=f"deposit_exact_{difference}")],
        [InlineKeyboardButton(f"💰 Choose Deposit Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("🚀 Start with Current Balance", callback_data="start_with_current")],
        [InlineKeyboardButton("⏰ I'll Deposit Later", callback_data="deposit_later")],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Store partial funding status
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "partial",
        "funding_percentage": percentage,
        "remaining_amount": difference
    })
    
    return AWAITING_DEPOSIT_DECISION

async def handle_no_funds(update, context, account_info, stated_amount):
    """Handle users with empty accounts."""
    print(f"User has no funds, needs ${stated_amount}")
    
    message = (
        f"✅ **Account Successfully Verified!**\n\n"
        f"**Account:** {account_info['account_number']}\n"
        f"**Account Holder:** {account_info['name']}\n"
        f"**Current Balance:** $0.00\n"
        f"**Target Amount:** ${stated_amount:,.2f}\n\n"
        f"🚀 **Ready to start your trading journey?**\n\n"
        f"To access our VIP services, you'll need to fund your account with ${stated_amount:,.2f}.\n\n"
        f"**Once funded, you'll get:**\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 📈 Advanced Strategies\n"
        f"• 💰 Prop Capital Access\n"
        f"• 👨‍💼 Personal Support\n\n"
        f"**How would you like to proceed?**"
    )
    
    # Create funding options
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit ${stated_amount:,.0f} Now", callback_data=f"deposit_exact_{stated_amount}")],
        [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("📚 Start with Free Resources", callback_data="free_resources")],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Store no funding status
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "none",
        "target_amount": stated_amount
    })
    
    return AWAITING_DEPOSIT_DECISION

async def handle_deposit_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deposit-related button callbacks."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = update.effective_user.id
    
    print(f"Deposit callback received: {callback_data}")
    
    if callback_data.startswith("deposit_exact_"):
        # User wants to deposit exact amount
        amount = float(callback_data.split("_")[2])
        return await initiate_deposit_process(query, context, amount)
        
    elif callback_data == "choose_deposit_amount":
        # User wants to choose different amount
        return await show_deposit_amount_options(query, context)
        
    elif callback_data == "start_with_current":
        # User wants to start with current balance
        return await start_with_current_balance(query, context)
        
    elif callback_data == "deposit_later":
        # User will deposit later
        return await handle_deposit_later(query, context)
        
    elif callback_data.startswith("access_vip_"):
        # User accessing VIP services
        service = callback_data.split("_")[2]
        return await handle_vip_access(query, context, service)
    
    return AWAITING_DEPOSIT_DECISION

async def initiate_deposit_process(query, context, amount):
    """Start the deposit process for specified amount."""
    user_id = query.from_user.id
    verified_account = context.user_data.get("verified_account", {})
    
    message = (
        f"💳 **Deposit ${amount:,.2f}**\n\n"
        f"**To Account:** {verified_account.get('account_number', 'Unknown')}\n"
        f"**Account Holder:** {verified_account.get('name', 'Unknown')}\n\n"
        f"**Choose your preferred payment method:**"
    )
    
    # Payment method buttons
    keyboard = [
        [
            InlineKeyboardButton("💳 Credit/Debit Card", callback_data=f"pay_card_{amount}"),
            InlineKeyboardButton("🏦 Bank Transfer", callback_data=f"pay_bank_{amount}")
        ],
        [
            InlineKeyboardButton("₿ Cryptocurrency", callback_data=f"pay_crypto_{amount}"),
            InlineKeyboardButton("📱 PayPal", callback_data=f"pay_paypal_{amount}")
        ],
        [
            InlineKeyboardButton("📋 Manual Deposit Instructions", callback_data=f"pay_manual_{amount}"),
            InlineKeyboardButton("🔙 Back", callback_data="back_to_options")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Store deposit attempt
    db.add_user({
        "user_id": user_id,
        "deposit_attempt_amount": amount,
        "deposit_attempt_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    return PAYMENT_METHOD_SELECTION

async def show_deposit_amount_options(query, context):
    """Show different deposit amount options."""
    
    message = (
        f"💰 **Choose Your Deposit Amount**\n\n"
        f"Select the amount you'd like to deposit to access our VIP services:"
    )
    
    # Deposit amount options
    keyboard = [
        [
            InlineKeyboardButton("$100", callback_data="deposit_exact_100"),
            InlineKeyboardButton("$300", callback_data="deposit_exact_300")
        ],
        [
            InlineKeyboardButton("$500", callback_data="deposit_exact_500"),
            InlineKeyboardButton("$1,000", callback_data="deposit_exact_1000")
        ],
        [
            InlineKeyboardButton("$2,000", callback_data="deposit_exact_2000"),
            InlineKeyboardButton("💬 Custom Amount", callback_data="custom_amount")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="back_to_options")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    return AWAITING_DEPOSIT_DECISION
# =========================================================================== #
# ======================= PAYMENT METHODS
# =========================================================================== #
async def handle_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle payment method selection."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    parts = callback_data.split('_')
    
    if len(parts) >= 3:
        payment_method = parts[1]  # card, bank, crypto, paypal, manual
        amount = float(parts[2])
        
        print(f"Payment method selected: {payment_method}, Amount: ${amount}")
        
        if payment_method == "card":
            return await handle_card_payment(query, context, amount)
        elif payment_method == "bank":
            return await handle_bank_payment(query, context, amount)
        elif payment_method == "crypto":
            return await handle_crypto_payment(query, context, amount)
        elif payment_method == "paypal":
            return await handle_paypal_payment(query, context, amount)
        elif payment_method == "manual":
            return await handle_manual_deposit(query, context, amount)
    
    return PAYMENT_METHOD_SELECTION

async def handle_card_payment(query, context, amount):
    """Handle credit/debit card payment."""
    user_id = query.from_user.id
    
    # Generate payment link (you'll need to integrate with your payment processor)
    payment_link = generate_stripe_payment_link(amount, user_id)
    
    message = (
        f"💳 **Credit/Debit Card Payment**\n\n"
        f"**Amount:** ${amount:,.2f}\n\n"
        f"Click the button below to complete your secure payment.\n\n"
        f"🔒 **Secure Payment Processing by Stripe**\n"
        f"• Your card details are never stored\n"
        f"• SSL encrypted transaction\n"
        f"• Instant deposit confirmation\n\n"
        f"After payment, funds will appear in your MT5 account within 5-10 minutes."
    )
    
    keyboard = [
        [InlineKeyboardButton(f"💳 Pay ${amount:,.0f} Securely", url=payment_link)],
        [InlineKeyboardButton("❓ Payment Help", callback_data="payment_help")],
        [InlineKeyboardButton("🔙 Choose Different Method", callback_data=f"deposit_exact_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Schedule balance check
    schedule_balance_check(context, user_id, amount, 5)  # Check in 5 minutes
    
    return DEPOSIT_CONFIRMATION

async def handle_bank_payment(query, context, amount):
    """Handle bank transfer payment."""
    user_id = query.from_user.id
    verified_account = context.user_data.get("verified_account", {})
    
    # Generate unique reference number
    reference = f"VFX-{user_id}-{int(datetime.now().timestamp())}"
    
    message = (
        f"🏦 **Bank Transfer Instructions**\n\n"
        f"**Amount:** ${amount:,.2f}\n"
        f"**Reference:** {reference}\n\n"
        f"**💰 Bank Details:**\n"
        f"Bank Name: Your Bank Name\n"
        f"Account Name: VFX Trading Ltd\n"
        f"Account Number: 1234567890\n"
        f"Routing Number: 123456789\n"
        f"SWIFT Code: ABCD1234\n\n"
        f"**📋 Important Instructions:**\n"
        f"• Use reference code: {reference}\n"
        f"• Transfer exactly ${amount:,.2f}\n"
        f"• Processing time: 1-3 business days\n"
        f"• Send confirmation screenshot after transfer\n\n"
        f"**Target Account:** {verified_account.get('account_number', 'Unknown')}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📸 Send Transfer Confirmation", callback_data=f"confirm_transfer_{reference}")],
        [InlineKeyboardButton("❓ Transfer Help", callback_data="transfer_help")],
        [InlineKeyboardButton("🔙 Choose Different Method", callback_data=f"deposit_exact_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Store transfer reference
    db.add_user({
        "user_id": user_id,
        "transfer_reference": reference,
        "transfer_amount": amount,
        "transfer_status": "pending"
    })
    
    return DEPOSIT_CONFIRMATION

async def handle_paypal_payment(query, context, amount):
    """Handle PayPal payment."""
    user_id = query.from_user.id
    verified_account = context.user_data.get("verified_account", {})
    
    # Generate PayPal payment link (you'll need to integrate with your PayPal account)
    paypal_link = generate_paypal_payment_link(amount, user_id)
    
    # Generate unique reference for tracking
    reference = f"VFX-PP-{user_id}-{int(datetime.now().timestamp())}"
    
    message = (
        f"📱 **PayPal Payment**\n\n"
        f"**Amount:** ${amount:,.2f}\n"
        f"**To Account:** {verified_account.get('account_number', 'Unknown')}\n"
        f"**Reference:** {reference}\n\n"
        f"🔒 **Secure PayPal Processing**\n"
        f"• Pay with your PayPal account or card\n"
        f"• Buyer protection included\n"
        f"• Instant payment confirmation\n"
        f"• Funds transferred within 1-2 hours\n\n"
        f"**Steps:**\n"
        f"1. Click 'Pay with PayPal' below\n"
        f"2. Complete payment on PayPal\n"
        f"3. Return here for confirmation\n"
        f"4. Funds will appear in your MT5 account\n\n"
        f"**Processing Time:** 1-2 hours maximum"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"📱 Pay ${amount:,.0f} with PayPal", url=paypal_link)],
        [InlineKeyboardButton("✅ I've Completed Payment", callback_data=f"paypal_completed_{reference}")],
        [InlineKeyboardButton("❓ PayPal Help", callback_data="paypal_help")],
        [InlineKeyboardButton("🔙 Choose Different Method", callback_data=f"deposit_exact_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Store PayPal payment attempt
    db.add_user({
        "user_id": user_id,
        "paypal_reference": reference,
        "paypal_amount": amount,
        "paypal_status": "pending",
        "paypal_initiated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Schedule balance checks for PayPal payments (faster than bank transfers)
    schedule_balance_check(context, user_id, amount, 15)  # Check in 15 minutes
    schedule_balance_check(context, user_id, amount, 60)  # Check in 1 hour
    schedule_balance_check(context, user_id, amount, 120) # Check in 2 hours
    
    return DEPOSIT_CONFIRMATION

async def handle_crypto_payment(query, context, amount):
    """Handle cryptocurrency payment."""
    user_id = query.from_user.id
    
    # Generate crypto addresses (you'll need to integrate with your crypto processor)
    btc_address = generate_btc_address(user_id)
    eth_address = generate_eth_address(user_id)
    
    message = (
        f"₿ **Cryptocurrency Payment**\n\n"
        f"**Amount:** ${amount:,.2f}\n\n"
        f"**Choose your cryptocurrency:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("₿ Bitcoin (BTC)", callback_data=f"crypto_btc_{amount}")],
        [InlineKeyboardButton("⟠ Ethereum (ETH)", callback_data=f"crypto_eth_{amount}")],
        [InlineKeyboardButton("₮ Tether (USDT)", callback_data=f"crypto_usdt_{amount}")],
        [InlineKeyboardButton("🔙 Choose Different Method", callback_data=f"deposit_exact_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    return PAYMENT_METHOD_SELECTION

async def handle_manual_deposit(query, context, amount):
    """Handle manual deposit instructions."""
    user_id = query.from_user.id
    verified_account = context.user_data.get("verified_account", {})
    
    message = (
        f"📋 **Manual Deposit Instructions**\n\n"
        f"**Amount:** ${amount:,.2f}\n"
        f"**To Account:** {verified_account.get('account_number')}\n\n"
        f"**How to deposit directly to your MT5 account:**\n\n"
        f"**Option 1: MT5 Platform**\n"
        f"1. Open your MT5 trading platform\n"
        f"2. Go to 'Deposit' or 'Fund Account'\n"
        f"3. Select your preferred payment method\n"
        f"4. Enter amount: ${amount:,.2f}\n"
        f"5. Complete the deposit process\n\n"
        f"**Option 2: Client Portal**\n"
        f"1. Log into your VortexFX's client portal\n"
        f"2. Navigate to 'Deposits' section\n"
        f"3. Choose payment method and amount\n"
        f"4. Complete the transaction\n\n"
        f"**⏰ Processing Time:** 5-30 minutes\n"
        f"**💡 Tip:** Take a screenshot of your deposit confirmation\n\n"
        f"Once completed, click 'Check Balance' to verify your deposit!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check My Balance Now", callback_data="check_balance_now")],
        [InlineKeyboardButton("📸 Upload Deposit Proof", callback_data="upload_proof")],
        [InlineKeyboardButton("❓ Need Help?", callback_data="deposit_help")],
        [InlineKeyboardButton("🔙 Other Payment Methods", callback_data=f"deposit_exact_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Schedule periodic balance checks
    schedule_balance_check(context, user_id, amount, 10)  # Check in 10 minutes
    schedule_balance_check(context, user_id, amount, 30)  # Check in 30 minutes
    schedule_balance_check(context, user_id, amount, 60)  # Check in 1 hour
    
    return DEPOSIT_CONFIRMATION

def generate_stripe_payment_link(amount, user_id):
    """Generate Stripe payment link (you'll need to implement this with your Stripe account)."""
    # Example implementation - replace with your actual Stripe integration
    
    # import stripe
    # stripe.api_key = "your_stripe_secret_key"
    # 
    # session = stripe.checkout.Session.create(
    #     payment_method_types=['card'],
    #     line_items=[{
    #         'price_data': {
    #             'currency': 'usd',
    #             'product_data': {
    #                 'name': f'VFX Trading Account Deposit',
    #             },
    #             'unit_amount': int(amount * 100),  # Stripe uses cents
    #         },
    #         'quantity': 1,
    #     }],
    #     mode='payment',
    #     success_url=f'https://your-website.com/payment-success?user_id={user_id}',
    #     cancel_url=f'https://your-website.com/payment-cancel?user_id={user_id}',
    #     metadata={'user_id': str(user_id)}
    # )
    # return session.url
    
    # For now, return a placeholder link
    return f"https://your-payment-processor.com/pay?amount={amount}&user={user_id}"

def generate_paypal_payment_link(amount, user_id):
    """Generate PayPal payment link (you'll need to implement this with your PayPal account)."""
    # Example implementation - replace with your actual PayPal integration
    
    # Option 1: PayPal SDK Integration
    # import paypalrestsdk
    # 
    # paypalrestsdk.configure({
    #     "mode": "sandbox",  # Change to "live" for production
    #     "client_id": "your_paypal_client_id",
    #     "client_secret": "your_paypal_client_secret"
    # })
    # 
    # payment = paypalrestsdk.Payment({
    #     "intent": "sale",
    #     "payer": {"payment_method": "paypal"},
    #     "redirect_urls": {
    #         "return_url": f"https://your-website.com/paypal-success?user_id={user_id}",
    #         "cancel_url": f"https://your-website.com/paypal-cancel?user_id={user_id}"
    #     },
    #     "transactions": [{
    #         "item_list": {
    #             "items": [{
    #                 "name": "VFX Trading Account Deposit",
    #                 "sku": f"deposit_{user_id}",
    #                 "price": str(amount),
    #                 "currency": "USD",
    #                 "quantity": 1
    #             }]
    #         },
    #         "amount": {
    #             "total": str(amount),
    #             "currency": "USD"
    #         },
    #         "description": f"VFX Trading deposit for user {user_id}"
    #     }]
    # })
    # 
    # if payment.create():
    #     for link in payment.links:
    #         if link.rel == "approval_url":
    #             return link.href
    
    # Option 2: PayPal Simple Payment Link (easier to implement)
    paypal_business_email = "your-paypal-business@email.com"  # Replace with your PayPal business email
    return_url = f"https://your-website.com/paypal-success?user_id={user_id}"
    cancel_url = f"https://your-website.com/paypal-cancel?user_id={user_id}"
    
    paypal_url = (
        f"https://www.paypal.com/cgi-bin/webscr?"
        f"cmd=_xclick&"
        f"business={paypal_business_email}&"
        f"item_name=VFX Trading Account Deposit&"
        f"amount={amount}&"
        f"currency_code=USD&"
        f"custom={user_id}&"
        f"return={return_url}&"
        f"cancel_return={cancel_url}&"
        f"notify_url=https://your-website.com/paypal-ipn"
    )
    
    return paypal_url

def generate_btc_address(user_id):
    """Generate Bitcoin address for user (implement with your crypto processor)."""
    # Placeholder - implement with your crypto payment processor
    return f"bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"

def generate_eth_address(user_id):
    """Generate Ethereum address for user."""
    # Placeholder - implement with your crypto payment processor
    return f"0x742d35Cc6634C0532925a3b8D64322d2E2b6Ea81"

def schedule_balance_check(context, user_id, expected_amount, delay_minutes):
    """Schedule a balance check after specified delay."""
    from datetime import datetime, timedelta
    
    # Schedule job to check balance
    run_time = datetime.now() + timedelta(minutes=delay_minutes)
    
    context.job_queue.run_once(
        lambda context: check_user_balance_update(context, user_id, expected_amount),
        when=delay_minutes * 60,  # Convert to seconds
        name=f"balance_check_{user_id}_{int(datetime.now().timestamp())}"
    )
    
    print(f"Scheduled balance check for user {user_id} in {delay_minutes} minutes")

async def check_user_balance_update(context, user_id, expected_amount):
    """Check if user's balance has been updated."""
    try:
        # Get user's account info
        user_info = db.get_user(user_id)
        if not user_info or not user_info.get("trading_account"):
            print(f"No account info found for user {user_id}")
            return
        
        account_number = user_info["trading_account"]
        previous_balance = user_info.get("account_balance", 0)
        
        # Check current balance
        mysql_db = get_mysql_connection()
        if not mysql_db.is_connected():
            print("MySQL not connected for balance check")
            return
        
        current_info = mysql_db.verify_account_exists(account_number)
        if not current_info['exists']:
            print(f"Account {account_number} not found during balance check")
            return
        
        current_balance = float(current_info.get('balance', 0))
        
        print(f"Balance check - Previous: ${previous_balance}, Current: ${current_balance}")
        
        # Check if balance increased significantly
        if current_balance >= (previous_balance + expected_amount * 0.9):  # Allow for small variations
            # Deposit detected!
            await handle_deposit_detected(context, user_id, current_balance, expected_amount)
        elif current_balance > previous_balance:
            # Partial deposit detected
            await handle_partial_deposit_detected(context, user_id, current_balance, expected_amount)
        
        # Update stored balance
        db.add_user({
            "user_id": user_id,
            "account_balance": current_balance,
            "last_balance_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        print(f"Error checking balance for user {user_id}: {e}")

async def handle_deposit_detected(context, user_id, new_balance, expected_amount):
    """Handle when a deposit is detected."""
    print(f"🎉 Deposit detected for user {user_id}: ${new_balance}")
    
    congratulations_message = (
        f"🎉 **DEPOSIT CONFIRMED!** 🎉\n\n"
        f"**New Balance:** ${new_balance:,.2f}\n"
        f"**Expected:** ${expected_amount:,.2f}\n\n"
        f"✅ **Your VIP access has been activated!**\n\n"
        f"You now have access to:\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 📈 Advanced Trading Strategies\n"
        f"• 💰 Prop Capital Opportunities\n\n"
        f"Welcome to VFX Trading VIP! 🚀"
    )
    
    # Create VIP access buttons
    keyboard = [
        [
            InlineKeyboardButton("🔔 Access VIP Signals", callback_data="access_vip_signals"),
            InlineKeyboardButton("📈 Access VIP Strategy", callback_data="access_vip_strategy")
        ],
        [
            InlineKeyboardButton("💰 Access Prop Capital", callback_data="access_vip_propcapital"),
            InlineKeyboardButton("👨‍💼 Personal Advisor", callback_data="speak_advisor")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=congratulations_message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )
    
    # Update user status
    db.add_user({
        "user_id": user_id,
        "funding_status": "completed",
        "vip_eligible": True,
        "vip_activated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "actual_deposit_amount": new_balance
    })
    
    # Notify admins
    await notify_admins_deposit_success(context, user_id, new_balance, expected_amount)

async def handle_partial_deposit_detected(context, user_id, current_balance, expected_amount):
    """Handle when a partial deposit is detected."""
    remaining = expected_amount - current_balance
    
    message = (
        f"💰 **Deposit Detected!**\n\n"
        f"**Current Balance:** ${current_balance:,.2f}\n"
        f"**Target Amount:** ${expected_amount:,.2f}\n"
        f"**Remaining:** ${remaining:,.2f}\n\n"
        f"Great progress! You're getting closer to full VIP access.\n\n"
        f"Would you like to complete the remaining deposit?"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit Remaining ${remaining:,.0f}", callback_data=f"deposit_exact_{remaining}")],
        [InlineKeyboardButton("🚀 Start with Current Balance", callback_data="start_with_current")],
        [InlineKeyboardButton("⏰ I'll Complete Later", callback_data="complete_later")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=message,
        parse_mode='Markdown',
        reply_markup=reply_markup
    )


async def check_balance_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle check balance button callback."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Get user's account info
    user_info = db.get_user(user_id)
    if not user_info or not user_info.get("trading_account"):
        await query.edit_message_text(
            "⚠️ No account information found. Please complete verification first."
        )
        return
    
    account_number = user_info["trading_account"]
    
    await query.edit_message_text("🔍 Checking your current balance...")
    
    # Check current balance
    mysql_db = get_mysql_connection()
    if not mysql_db.is_connected():
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Unable to check balance at the moment. Please try again later."
        )
        return
    
    try:
        current_info = mysql_db.verify_account_exists(account_number)
        
        if not current_info['exists']:
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Account not found. Please contact support."
            )
            return
        
        current_balance = float(current_info.get('balance', 0))
        previous_balance = user_info.get("account_balance", 0)
        
        # Check if balance increased
        if current_balance > previous_balance:
            balance_change = current_balance - previous_balance
            status_emoji = "📈"
            status_text = f"Increased by ${balance_change:,.2f}!"
            
            # Check if they now qualify for VIP
            target_amount = user_info.get("deposit_amount", 0)
            if current_balance >= target_amount and not user_info.get("vip_eligible"):
                # They now qualify!
                await handle_deposit_detected(context, user_id, current_balance, target_amount)
                return
                
        elif current_balance < previous_balance:
            balance_change = previous_balance - current_balance
            status_emoji = "📉"
            status_text = f"Decreased by ${balance_change:,.2f}"
        else:
            status_emoji = "💰"
            status_text = "No change since last check"
        
        # Update stored balance
        db.add_user({
            "user_id": user_id,
            "account_balance": current_balance,
            "last_balance_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Format response
        balance_message = (
            f"{status_emoji} **Balance Update**\n\n"
            f"**Account:** {account_number}\n"
            f"**Current Balance:** ${current_balance:,.2f}\n"
            f"**Status:** {status_text}\n"
            f"**Last Checked:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        )
        
        # Add appropriate buttons based on balance
        target_amount = user_info.get("deposit_amount", 0)
        if current_balance >= target_amount:
            balance_message += "🎉 **You qualify for VIP access!**"
            keyboard = [
                [InlineKeyboardButton("🚀 Activate VIP Access", callback_data="activate_vip")],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_balance_now")]
            ]
        else:
            remaining = target_amount - current_balance
            balance_message += f"💡 **${remaining:,.2f} more needed for VIP access**"
            keyboard = [
                [InlineKeyboardButton(f"💳 Deposit ${remaining:,.0f}", callback_data=f"deposit_exact_{remaining}")],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_balance_now")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=balance_message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⚠️ Error checking balance: {e}"
        )
async def handle_paypal_completion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle PayPal payment completion callback."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = query.from_user.id
    
    if callback_data.startswith("paypal_completed_"):
        reference = callback_data.replace("paypal_completed_", "")
        
        message = (
            f"✅ **PayPal Payment Submitted**\n\n"
            f"**Reference:** {reference}\n\n"
            f"Thank you for completing your PayPal payment! Here's what happens next:\n\n"
            f"**⏰ Processing Timeline:**\n"
            f"• PayPal confirmation: Immediate\n"
            f"• Funds transfer to MT5: 1-2 hours\n"
            f"• VIP access activation: Automatic upon deposit\n\n"
            f"**📧 You'll receive:**\n"
            f"• PayPal payment confirmation email\n"
            f"• MT5 deposit notification\n"
            f"• VIP access confirmation from us\n\n"
            f"We're monitoring your account balance and will notify you immediately when the deposit is confirmed!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Check Balance Now", callback_data="check_balance_now")],
            [InlineKeyboardButton("📧 Resend Confirmation", callback_data=f"resend_paypal_{reference}")],
            [InlineKeyboardButton("❓ Payment Status Help", callback_data="paypal_status_help")],
            [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
        
        # Update payment status
        db.add_user({
            "user_id": user_id,
            "paypal_status": "completed",
            "paypal_completed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Notify admins of PayPal completion
        await notify_admins_paypal_completion(context, user_id, reference)
        
        return DEPOSIT_CONFIRMATION

async def handle_payment_help_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle various payment help callbacks."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data == "paypal_help":
        await show_paypal_help(query, context)
    elif callback_data == "paypal_status_help":
        await show_paypal_status_help(query, context)
    elif callback_data.startswith("resend_paypal_"):
        reference = callback_data.replace("resend_paypal_", "")
        await resend_paypal_confirmation(query, context, reference)

async def show_paypal_help(query, context):
    """Show PayPal payment help."""
    
    help_message = (
        f"📱 **PayPal Payment Help**\n\n"
        f"**❓ Common Questions:**\n\n"
        f"**Q: Is PayPal payment secure?**\n"
        f"A: Yes! PayPal provides buyer protection and secure payment processing.\n\n"
        f"**Q: How long does it take?**\n"
        f"A: PayPal payment is instant, MT5 deposit takes 1-2 hours.\n\n"
        f"**Q: What if I don't have a PayPal account?**\n"
        f"A: You can pay with credit/debit card through PayPal checkout.\n\n"
        f"**Q: Can I get a refund?**\n"
        f"A: Yes, contact our support team within 24 hours.\n\n"
        f"**Q: What currencies are accepted?**\n"
        f"A: USD, EUR, GBP, and other major currencies.\n\n"
        f"**🔍 Payment Status:**\n"
        f"You can track your payment status in your PayPal account and we'll notify you when funds reach your MT5 account."
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
        [InlineKeyboardButton("🔄 Check Balance", callback_data="check_balance_now")],
        [InlineKeyboardButton("🔙 Back to Payment", callback_data="back_to_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(help_message, parse_mode='Markdown', reply_markup=reply_markup)

async def show_paypal_status_help(query, context):
    """Show PayPal payment status help."""
    
    status_help = (
        f"📊 **PayPal Payment Status Guide**\n\n"
        f"**🔍 How to Check Your Payment Status:**\n\n"
        f"**1. In PayPal:**\n"
        f"• Log into your PayPal account\n"
        f"• Go to 'Activity' or 'Transaction History'\n"
        f"• Look for 'VFX Trading Account Deposit'\n"
        f"• Status should show 'Completed'\n\n"
        f"**2. In Your Email:**\n"
        f"• Check for PayPal confirmation email\n"
        f"• Look for MT5 deposit notification\n"
        f"• Wait for our VIP access confirmation\n\n"
        f"**3. Processing Times:**\n"
        f"• PayPal payment: Instant ⚡\n"
        f"• Fund transfer: 1-2 hours ⏱️\n"
        f"• VIP activation: Automatic 🚀\n\n"
        f"**⚠️ If Payment is Pending:**\n"
        f"• Check your PayPal account verification\n"
        f"• Verify your payment method\n"
        f"• Contact PayPal customer service\n\n"
        f"**🚨 If Payment Failed:**\n"
        f"• Try a different payment method\n"
        f"• Check your account limits\n"
        f"• Contact our support team"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check Balance Now", callback_data="check_balance_now")],
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
        [InlineKeyboardButton("💳 Try Different Payment", callback_data="back_to_payment")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(status_help, parse_mode='Markdown', reply_markup=reply_markup)
    
async def resend_paypal_confirmation(query, context, reference):
    """Resend PayPal payment confirmation details."""
    user_id = query.from_user.id
    
    # Get user's PayPal payment details
    user_info = db.get_user(user_id)
    if not user_info:
        await query.edit_message_text("⚠️ User information not found.")
        return
    
    paypal_amount = user_info.get("paypal_amount", 0)
    paypal_date = user_info.get("paypal_initiated_date", "Unknown")
    
    confirmation_message = (
        f"📧 **PayPal Payment Confirmation Resent**\n\n"
        f"**Payment Details:**\n"
        f"• Reference: {reference}\n"
        f"• Amount: ${paypal_amount:,.2f}\n"
        f"• Date: {paypal_date}\n"
        f"• Status: Payment Submitted\n\n"
        f"**Next Steps:**\n"
        f"1. ✅ PayPal payment completed\n"
        f"2. ⏳ Waiting for MT5 deposit (1-2 hours)\n"
        f"3. 🚀 VIP access will activate automatically\n\n"
        f"**Tracking:**\n"
        f"• Check your PayPal account for transaction details\n"
        f"• Monitor your MT5 account balance\n"
        f"• We'll notify you when VIP access is ready\n\n"
        f"**Questions?** Contact our support team anytime!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check Balance", callback_data="check_balance_now")],
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(confirmation_message, parse_mode='Markdown', reply_markup=reply_markup)

# =============================================================================
# ============== VIP ACCESS HANDLERS
# =============================================================================

async def handle_vip_access(query, context, service):
    """Handle VIP service access requests."""
    user_id = query.from_user.id
    
    # Verify user is eligible
    user_info = db.get_user(user_id)
    if not user_info or not user_info.get("vip_eligible"):
        await query.edit_message_text(
            "⚠️ VIP access not available. Please complete your deposit first.",
            reply_markup=None
        )
        return
    
    # Service mapping
    service_mapping = {
        "signals": {
            "name": "VIP Trading Signals",
            "channel_id": SIGNALS_CHANNEL_ID,
            #"group_id": SIGNALS_GROUP_ID,
            "emoji": "🔔"
        },
        "strategy": {
            "name": "VIP Trading Strategy",
            "channel_id": STRATEGY_CHANNEL_ID,
            #"group_id": STRATEGY_GROUP_ID,
            "emoji": "📈"
        },
        "propcapital": {
            "name": "VIP Prop Capital",
            "channel_id": PROP_CHANNEL_ID,
            #"group_id": PROP_GROUP_ID,
            "emoji": "💰"
        }
    }
    
    if service not in service_mapping:
        await query.edit_message_text("⚠️ Invalid service requested.")
        return
    
    service_info = service_mapping[service]
    
    try:
        # Create invite links
        channel_invite = await context.bot.create_chat_invite_link(
            chat_id=service_info["channel_id"],
            member_limit=1,
            name=f"{service_info['name']} invite for user {user_id}"
        )
        
        # group_invite = await context.bot.create_chat_invite_link(
        #     chat_id=service_info["group_id"],
        #     member_limit=1,
        #     name=f"{service_info['name']} group invite for user {user_id}"
        # )
        
        # Success message
        access_message = (
            f"✅ **{service_info['name']} Access Granted!** {service_info['emoji']}\n\n"
            f"**Channel:** {channel_invite.invite_link}\n"
            #f"**Discussion Group:** {group_invite.invite_link}\n\n"
            f"**Important Instructions:**\n"
            f"• Click both links to join\n"
            f"• Links expire after one use\n"
            f"• Enable notifications for updates\n"
            f"• Read pinned messages for guidelines\n\n"
            f"Welcome to {service_info['name']}! 🚀"
        )
        
        await query.edit_message_text(access_message, parse_mode='Markdown')
        
        # Update database
        current_vip = user_info.get('vip_channels', '') or ''
        new_vip = f"{current_vip},{service}".strip(',')
        
        db.add_user({
            "user_id": user_id,
            "vip_channels": new_vip,
            f"vip_{service}_added": True,
            f"vip_{service}_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Notify admins
        await notify_admins_vip_access(context, user_id, service_info["name"])
        
    except Exception as e:
        await query.edit_message_text(
            f"⚠️ Error creating access links for {service_info['name']}: {e}"
        )

async def handle_deposit_later(query, context):
    """Handle when user chooses to deposit later."""
    user_id = query.from_user.id
    
    message = (
        f"⏰ **No Problem!**\n\n"
        f"We understand you'd like to deposit later. Here's what happens next:\n\n"
        f"✅ Your account is verified and ready\n"
        f"✅ We'll monitor your balance automatically\n"
        f"✅ You'll get VIP access immediately upon deposit\n"
        f"✅ Our team will follow up with you\n\n"
        f"**In the meantime:**\n"
        f"• 📚 Access our free educational content\n"
        f"• 📊 Join our community discussions\n"
        f"• 📧 Receive market updates and tips\n\n"
        f"When you're ready to deposit, just let us know!"
    )
    
    keyboard = [
        [InlineKeyboardButton("📚 Free Educational Content", callback_data="free_resources")],
        [InlineKeyboardButton("💬 Join Community", callback_data="join_community")],
        [InlineKeyboardButton("🔔 Set Deposit Reminder", callback_data="set_reminder")],
        [InlineKeyboardButton("👨‍💼 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    # Mark user for follow-up
    db.add_user({
        "user_id": user_id,
        "deposit_status": "deferred",
        "followup_required": True,
        "followup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Schedule follow-up messages
    schedule_followup_messages(context, user_id)
    
    return ConversationHandler.END

async def start_with_current_balance(query, context):
    """Handle starting with current balance."""
    user_id = query.from_user.id
    verified_account = context.user_data.get("verified_account", {})
    current_balance = verified_account.get("balance", 0)
    
    message = (
        f"🚀 **Let's Get Started!**\n\n"
        f"**Current Balance:** ${current_balance:,.2f}\n\n"
        f"Based on your current balance, here's what you can access:\n\n"
    )
    
    # Determine what they can access with current balance
    if current_balance >= 100:
        message += (
            f"✅ **Full VIP Access Available:**\n"
            f"• 🔔 Premium Trading Signals\n"
            f"• 📈 Advanced Trading Strategies\n"
            f"• 💰 Prop Capital Opportunities\n"
        )
        keyboard = [
            [InlineKeyboardButton("🔔 Access VIP Signals", callback_data="access_vip_signals")],
            [InlineKeyboardButton("📈 Access VIP Strategy", callback_data="access_vip_strategy")],
            [InlineKeyboardButton("💰 Access Prop Capital", callback_data="access_vip_propcapital")]
        ]
    else:
        message += (
            f"✅ **Basic Access Available:**\n"
            f"• 🔔 Basic Trading Signals\n"
            f"• 📚 Educational Content\n"
        )
        keyboard = [
            [InlineKeyboardButton("🔔 Access Basic Signals", callback_data="access_basic_signals")],
            [InlineKeyboardButton("📚 Educational Content", callback_data="access_education")],
            [InlineKeyboardButton("⬆️ Upgrade Account", callback_data="upgrade_account")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    
    return ConversationHandler.END

# =============================================================================
# =============  NOTIFICATION FUNCTIONS
# =============================================================================

async def notify_admins_success(context, user_id, account_info, stated_amount, real_balance):
    """Notify admins of successful verification with sufficient funds."""
    
    admin_message = (
        f"🎉 **USER VERIFIED WITH SUFFICIENT FUNDS** 🎉\n\n"
        f"**User ID:** {user_id}\n"
        f"**Account:** {account_info['account_number']}\n"
        f"**Account Holder:** {account_info['name']}\n"
        f"**Stated Amount:** ${stated_amount:,.2f}\n"
        f"**Actual Balance:** ${real_balance:,.2f}\n"
        f"**Status:** ✅ VIP Access Granted\n\n"
        f"User has been automatically granted VIP access to all services."
    )
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def notify_admins_deposit_success(context, user_id, new_balance, expected_amount):
    """Notify admins when a deposit is detected."""
    
    admin_message = (
        f"💰 **DEPOSIT DETECTED!** 💰\n\n"
        f"**User ID:** {user_id}\n"
        f"**New Balance:** ${new_balance:,.2f}\n"
        f"**Expected:** ${expected_amount:,.2f}\n"
        f"**Status:** ✅ Deposit Confirmed\n\n"
        f"User has been automatically upgraded to VIP access!"
    )
    
    keyboard = [
        [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{user_id}")],
        [InlineKeyboardButton("💬 Contact User", callback_data=f"start_conv_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def notify_admins_vip_access(context, user_id, service_name):
    """Notify admins when user accesses VIP service."""
    
    admin_message = (
        f"🚀 **VIP ACCESS GRANTED**\n\n"
        f"**User ID:** {user_id}\n"
        f"**Service:** {service_name}\n"
        f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"User has been added to {service_name}."
    )
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

def schedule_followup_messages(context, user_id):
    """Schedule follow-up messages for users who defer deposits."""
    
    # Schedule follow-up messages at different intervals
    followup_times = [
        (24, "Thanks for verifying your account! Ready to start trading with us?"),
        (72, "Don't miss out on today's trading opportunities! Your account is ready for funding."),
        (168, "Weekly market wrap-up! See what profits our VIP members made this week."),
    ]
    
    for hours, message in followup_times:
        context.job_queue.run_once(
            lambda context, msg=message: send_followup_message(context, user_id, msg),
            when=hours * 3600,  # Convert hours to seconds
            name=f"followup_{user_id}_{hours}h"
        )

async def send_followup_message(context, user_id, message):
    """Send a follow-up message to user."""
    try:
        keyboard = [
            [InlineKeyboardButton("💳 Ready to Deposit", callback_data="ready_to_deposit")],
            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error sending follow-up message to user {user_id}: {e}")

async def notify_admins_paypal_completion(context, user_id, reference):
    """Notify admins when user completes PayPal payment."""
    
    user_info = db.get_user(user_id)
    amount = user_info.get("paypal_amount", 0) if user_info else 0
    
    admin_message = (
        f"📱 **PAYPAL PAYMENT COMPLETED** 📱\n\n"
        f"**User ID:** {user_id}\n"
        f"**Reference:** {reference}\n"
        f"**Amount:** ${amount:,.2f}\n"
        f"**Status:** User confirmed payment completion\n"
        f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"⏳ **Next Steps:**\n"
        f"• Monitor MT5 account for deposit\n"
        f"• Auto-upgrade user when funds arrive\n"
        f"• PayPal processing: 1-2 hours expected\n\n"
        f"💡 **Action Required:** Verify PayPal payment in your PayPal business account."
    )
    
    keyboard = [
        [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{user_id}")],
        [InlineKeyboardButton("💬 Contact User", callback_data=f"start_conv_{user_id}")],
        [InlineKeyboardButton("💰 Check PayPal Account", url="https://www.paypal.com/businessmanage/")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id} about PayPal completion: {e}")

async def notify_admins_success_auto_welcome(context, user_id, account_info, stated_amount, real_balance):
    """Notify admins of successful verification with sufficient funds (auto welcome flow)."""
    
    admin_message = (
        f"🎉 **USER VERIFIED WITH SUFFICIENT FUNDS** 🎉\n"
        f"**(Auto Welcome Flow)**\n\n"
        f"**User ID:** {user_id}\n"
        f"**Account:** {account_info['account_number']}\n"
        f"**Account Holder:** {account_info['name']}\n"
        f"**Stated Amount:** ${stated_amount:,.2f}\n"
        f"**Actual Balance:** ${real_balance:,.2f}\n"
        f"**Status:** ✅ VIP Access Granted\n\n"
        f"User has been automatically granted VIP access to all services."
    )
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

# ********************************************************** #

def main() -> None:
    """Start the bot."""
    # Create the Application
    print("Starting bot...")
    print("Setting up VFX message scheduler...")
    print(f"Admin ID is set to {ADMIN_USER_ID}")
    
    mysql_db = get_mysql_connection()
    if mysql_db.is_connected():
        print("✅ MySQL database ready for real-time account verification")
    else:
        print("⚠️ MySQL connection failed - will use CSV fallback")
    
    try:
        # Try to initialize schedulers
        from vfx_Scheduler import VFXMessageScheduler
        global vfx_scheduler, strategy_scheduler, prop_scheduler, signals_scheduler, education_scheduler
        
        vfx_scheduler = VFXMessageScheduler()
        strategy_scheduler = VFXMessageScheduler(config_path="./bot_data/strategy_messages.json")
        prop_scheduler = VFXMessageScheduler(config_path="./bot_data/prop_messages.json")
        signals_scheduler = VFXMessageScheduler(config_path="./bot_data/signals_messages.json")
        education_scheduler = VFXMessageScheduler(config_path="./bot_data/ed_messages.json")
        
        print(f"Main scheduler initialized with {len(vfx_scheduler.get_all_messages())} messages")
        print(f"Strategy scheduler initialized with {len(strategy_scheduler.get_all_messages())} messages")
    except Exception as e:
        print(f"Error initializing scheduler: {e}")
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Create instance of custom filter for forwarded messages
    forwarded_filter = ForwardedMessageFilter()

    
    """------------------------------
        ------ Message Handlers ----- 
    ---------------------------------"""
    # Add handler for messages forwarded to the admin
    application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_USER_ID) & ~filters.COMMAND,
        handle_admin_forward,
        block=True
    ))

    # Add handler for regular admin messages (not forwarded)
    application.add_handler(MessageHandler(
        filters.User(user_id=ADMIN_USER_ID) & filters.TEXT & ~forwarded_filter & ~filters.COMMAND,
        handle_admin_forward,
        block=True
    ))
    
    """------------------------------
        ------ Call Handlers ----- 
    ---------------------------------"""

    # Add callback handlers for VIP channel and copier team actions
    application.add_handler(CallbackQueryHandler(
        add_to_vip_callback,
        pattern=r"^add_vip_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        forward_to_copier_callback,
        pattern=r"^forward_copier_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        copier_team_action_callback,
        pattern=r"^copier_(added|rejected)_\d+$"
    ))

    application.add_handler(CallbackQueryHandler(
        copier_team_action_callback,
        pattern=r"^contact_user_\d+$"
    ))
    
    # Add callback handlers for all button types
    application.add_handler(CallbackQueryHandler(
        start_user_conversation_callback,
        pattern=r"^start_conv_\d+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        send_instructions_callback,
        pattern=r"^instr_"
    ))

    application.add_handler(CallbackQueryHandler(
        initialize_registration_callback,
        pattern=r"^init_reg_"
    ))

    application.add_handler(CallbackQueryHandler(
        send_registration_form_callback,
        pattern=r"^send_form_"
    ))

    application.add_handler(CallbackQueryHandler(
        start_casual_conversation_callback,
        pattern=r"^start_casual_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        copy_template_callback,
        pattern=r"^copy_(reg|casual)_\d+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        trading_interest_callback,
        pattern=r"^interest_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        view_profile_callback,
        pattern=r"^view_profile_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        start_guided_callback,
        pattern=r"^start_guided$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        risk_profile_callback,
        pattern=r"^risk_"
    ))

    application.add_handler(CallbackQueryHandler(
        experience_callback,
        pattern=r"^experience_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        restart_process_callback,
        pattern=r"^restart_process$"
    ))
    

    application.add_handler(CallbackQueryHandler(
        confirm_registration_callback,
        pattern=r"^confirm_registration$"
    ))

    application.add_handler(CallbackQueryHandler(
        edit_registration_callback,
        pattern=r"^edit_registration$"
    ))

    application.add_handler(CallbackQueryHandler(
        speak_advisor_callback,
        pattern=r"^speak_advisor$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        edit_account_callback,
        pattern=r"^edit_account$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        view_summary_callback,
        pattern=r"^view_summary$"
    ))

    application.add_handler(
        MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_auto_welcome_response,
        block=False  
    ))
    
    application.add_handler(CallbackQueryHandler(
        generate_welcome_link_callback,
        pattern=r"^gen_welcome_"
    ))
    
    application.add_handler(CallbackQueryHandler(
        handle_deposit_callbacks, 
        pattern=r"^(deposit_|start_with_|deposit_later|free_resources|access_vip_)"
    ))

    application.add_handler(CallbackQueryHandler(
        handle_payment_methods, 
        pattern=r"^pay_"
    ))
    # Add conversation handler for manual entry
    manual_entry_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(manual_entry_callback, pattern=r"^manual_")
        ],
        states={
            RISK_APPETITE_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, risk_appetite_manual)],
            DEPOSIT_AMOUNT_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount_manual)],
            TRADING_ACCOUNT_MANUAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, trading_account_manual)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="manual_entry_conversation",
    )
    application.add_handler(manual_entry_handler)
    
    # Add admin-specific command handlers
    application.add_handler(CommandHandler("users", list_users_command))
    application.add_handler(CommandHandler("endchat", end_user_conversation))
    application.add_handler(CommandHandler("startform", start_form_command))
    application.add_handler(CommandHandler("addtovip", add_to_vip_command))
    application.add_handler(CommandHandler("forwardmt5", forward_mt5_command))
    application.add_handler(CommandHandler("testaccount", test_account_command))
    application.add_handler(CommandHandler("signalstatus", signal_status_command))
    application.add_handler(CommandHandler("debugdb", debug_db_command))
    
    application.add_handler(CommandHandler("testmysql", test_mysql_command))
    application.add_handler(CommandHandler("searchaccount", search_account_command))
    application.add_handler(CommandHandler("checktable", check_table_command))
    application.add_handler(CommandHandler("debugreg", debug_registrations_command))
    application.add_handler(CommandHandler("checkmyaccounts", check_my_accounts_command))
    application.add_handler(CommandHandler("quickbalance", quick_balance_command))
    application.add_handler(CommandHandler("simpleregcheck", simple_reg_check_command))
    application.add_handler(CommandHandler("testrecent", test_recent_fix_command))
    application.add_handler(CommandHandler("testtimestamp", test_timestamp_approach))
    application.add_handler(CommandHandler("recentbylogin", recent_accounts_by_login_command))
    application.add_handler(CommandHandler("recentbytime", recent_accounts_timestamp_command))
    application.add_handler(CommandHandler("newest", newest_accounts_simple_command))

    
    application.add_handler(CommandHandler("debugzero", debug_zero_dates_command))
    application.add_handler(CommandHandler("checkmysqlmode", check_mysql_mode_command))
    application.add_handler(CommandHandler("findthreshold", find_recent_login_threshold_command))
    application.add_handler(CommandHandler("checkperms", check_user_permissions_command))
    application.add_handler(CommandHandler("diagnoseaccess", diagnose_account_access_command))
    application.add_handler(CommandHandler("testsafe", test_safe_login_query_command))  
    application.add_handler(CommandHandler("decodetimestamp", decode_mt5_timestamp_command))
    application.add_handler(CommandHandler("recentaccounts", recent_accounts_final_command))  # Replace the old one
    application.add_handler(CommandHandler("currenttable", compare_current_table_command))
    application.add_handler(CommandHandler("showtables", show_all_tables_command))
    application.add_handler(CommandHandler("searchusertables", search_user_tables_command))
    application.add_handler(CommandHandler("showdatabases", show_all_databases_command))
    application.add_handler(CommandHandler("checktable", check_table_for_high_accounts_command))
    application.add_handler(CommandHandler("checkaccounts", check_mt5_accounts_table_command))
    application.add_handler(CommandHandler("compareusers", compare_users_vs_accounts_command))
    application.add_handler(CommandHandler("sampleaccounts", check_accounts_table_sample_command))
    
        
    
    application.add_handler(MessageHandler(filters.ALL, silent_update_logger), group=999)
    
    

    # Add conversation handler for the CAPTCHA and authentication process
    auth_conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(auth_callback, pattern=r"^auth_\d+$")
        ],
        states={
            CAPTCHA_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_captcha_response)],
            TRADING_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_account_verification)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_chat=False,  # This allows the conversation to span across multiple chats
        name="auth_conversation",
    )
    application.add_handler(auth_conv_handler)
    
    # Add conversation handler for private messages (user info collection)
    # This should be AFTER the admin handlers to avoid conflicts
    private_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, private_message)
        ],
        states={
            RISK_APPETITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, risk_appetite)],
            DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
            TRADING_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enhanced_trading_account)],
            AWAITING_DEPOSIT_DECISION: [CallbackQueryHandler(handle_deposit_callbacks)],
            PAYMENT_METHOD_SELECTION: [CallbackQueryHandler(handle_payment_methods)],
            DEPOSIT_CONFIRMATION: [
                CallbackQueryHandler(check_balance_now_callback),
                CallbackQueryHandler(handle_paypal_completion),
                CallbackQueryHandler(handle_payment_help_callbacks)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(private_conv_handler)
    
    # Add handlers for other functionalities
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("managemsg", manage_messages_command))
    # application.add_handler(CommandHandler("updatemsg", update_message_command))
    # application.add_handler(CommandHandler("viewmsgs", view_messages_command))

    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # # Add periodic job for sending messages (interval from settings)
    job_queue = application.job_queue
    
    """------------------------------
    --- Send Report Messages ----- 
    ---------------------------------"""
    # Schedule daily signup report
    job_queue.run_daily(
        send_daily_signup_report,
        time=time(hour=0, minute=0)
    )
    # Schedule daily response report
    job_queue.run_daily(
        send_daily_response_report,
        time=time(hour=23, minute=0)
    )
    
    # Calculate the first run time for hourly job - at the start of the next hour
    now = datetime.now()
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    seconds_until_next_hour = (next_hour - now).total_seconds()
    
    job_queue.run_once(log_all_chats, 5)
    
    # Market session messages (on weekdays only)
    # Calculate first run time for each market session
    # Tokyo session (00:00)
    """------------------------------
    --- Send Messages at Market Open ----- 
    ---------------------------------"""
    tokyo_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if tokyo_time <= now:
        tokyo_time += timedelta(days=1)
    seconds_until_tokyo = (tokyo_time - now).total_seconds()
    
    # London session (08:00)
    london_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    if london_time <= now:
        london_time += timedelta(days=1)
    seconds_until_london = (london_time - now).total_seconds()
    
    # NY session (13:00)
    ny_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
    if ny_time <= now:
        ny_time += timedelta(days=1)
    seconds_until_ny = (ny_time - now).total_seconds()
    
    # --------------------------------------------------------------------- #
    
    job_queue.run_once(send_hourly_welcome, seconds_until_tokyo)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=0, minute=0))
    
    job_queue.run_once(send_hourly_welcome, seconds_until_london)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=8, minute=0))
    
    job_queue.run_once(send_hourly_welcome, seconds_until_ny)
    job_queue.run_daily(send_hourly_welcome, time=time(hour=13, minute=0))
    

    """------------------------------
        ------ Give aways Messages ----- 
    ---------------------------------"""
     # 17:00 - Daily giveaway announcement
    job_queue.run_daily(
        send_giveaway_message,
        time=time(hour=15, minute=0)
    )
    
    # 18:00 - Countdown to giveaway
    job_queue.run_daily(
        send_giveaway_message,
        time=time(hour=16, minute=0)
    )
    
    # 19:00 - Giveaway winner announcement
    job_queue.run_daily(
        send_giveaway_message,
        time=time(hour=17, minute=0)
    )
     
    
    """---------------------------------
    Send Messages at specified intervals
    ------------------------------------"""
    # Schedule interval messages - runs every 20 minutes
    # Calculate time until next 20-minute mark
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
        first=seconds_until_next_interval  # Time in seconds until first run
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
    
    # job_queue.run_repeating(
    #     lambda context: check_all_pending_deposits(context),
    #     interval=600,  # Every 10 minutes
    #     first=60
    # )
    
    """---------------------------------
         Signal Jobs
    ------------------------------------"""
    
    job_queue.run_once(init_signal_system, 30)
    
    # Schedule regular signal checks - run every hour
    # job_queue.run_repeating(
    #     check_and_send_signals,
    #     interval=300,  # 5 Min
    #     first=60  # First check 1 minute after bot start
    # )
    
    job_queue.run_repeating(
        report_signal_system_status,
        interval=21600,  # Every 6 hours
        first=600  # First report 10 minutes after startup
    )
    
    job_queue.run_repeating(
        lambda context: asyncio.create_task(signal_dispatcher.check_and_apply_trailing_stops()),
        interval=120,  # Every 2 minutes
        first=60  # Start 1 minute after bot startup
    )
    
    job_queue.run_daily(
        lambda context: asyncio.create_task(signal_dispatcher.send_daily_stats()),
        time=time(hour=22, minute=0)
    )
  
    
    # Log scheduled jobs
    logger.info(f"Scheduled hourly welcome messages starting in {seconds_until_next_hour:.2f} seconds")
    logger.info(f"Scheduled interval messages every 20 minutes starting in {seconds_until_next_interval:.2f} seconds")
    logger.info(f"Scheduled strategy messages every 20 minutes starting in {seconds_until_next_interval:.2f} seconds")
    logger.info(f"Scheduled propCapital messages every 20 minutes starting in {seconds_until_next_interval:.2f} seconds")
    logger.info(f"Scheduled signals messages every 20 minutes starting in {seconds_until_next_interval:.2f} seconds")
    logger.info(f"Scheduled education messages every 20 minutes starting in {seconds_until_next_interval:.2f} seconds")
    logger.info(f"Tokyo session messages scheduled at 00:00 (in {seconds_until_tokyo/3600:.1f} hours)")
    logger.info(f"London session messages scheduled at 08:00 (in {seconds_until_london/3600:.1f} hours)")
    logger.info(f"NY session messages scheduled at 13:00 (in {seconds_until_ny/3600:.1f} hours)")
    logger.info(f"Scheduled giveaway messages at 17:00, 18:00, and 19:00")
    
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# Main running name # 
if __name__ == "__main__":
    main()