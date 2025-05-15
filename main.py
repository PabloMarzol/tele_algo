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
from mt5_signal_generator import MT5SignalGenerator
from signal_dispatcher import SignalDispatcher
from config import Config

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
ADMIN_USER_ID = [7823596188, 7396303047]
ADMIN_USER_ID_2 = 7396303047

MAIN_CHANNEL_ID = "-1002586937373"

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
                "trading_account": account_number,
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

async def trading_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store trading account, validate against Accounts_List.csv, and complete the registration."""
    account_number = update.message.text.strip()
    user_id = update.effective_user.id
    
    print(f"===== TRADING ACCOUNT FUNCTION =====")
    print(f"Received: {account_number} from user {user_id}")
    print(f"Current context.user_data: {context.user_data}")
    
    # Initial response to user
    await update.message.reply_text("Processing your trading account...")
    
    try:
        # Validate account format 
        is_valid = auth.validate_account_format(account_number)
        print(f"Account format validation result: {is_valid}")
        
        if not is_valid:
            await update.message.reply_text("Invalid account format. Please enter a valid account number.")
            return TRADING_ACCOUNT
        
        # Get stored user data or create if missing
        if "user_info" not in context.user_data:
            print("WARNING: user_info missing from context, creating empty dict")
            context.user_data["user_info"] = {}
        
        # Verify against Accounts_List.csv
        account_verified = False
        account_owner = None
        
        try:
            # Load accounts from CSV file
            accounts_df = pl.read_csv("./bot_data/Accounts_List.csv")
            
            # Convert account_number to integer for comparison with the Account column
            try:
                account_int = int(account_number)
                # Check if account exists in the dataframe
                account_match = accounts_df.filter(pl.col("Account") == account_int)
                
                if account_match.height > 0:
                    account_verified = True
                    account_owner = account_match.select("Name")[0, 0]
                    print(f"Account verified: {account_number} belongs to {account_owner}")
                else:
                    print(f"Account {account_number} not found in Accounts_List.csv")
            except ValueError:
                print(f"Could not convert account number to integer for verification")
        except Exception as e:
            print(f"Error verifying account against CSV: {e}")
        
        # Store in user_data
        context.user_data["user_info"]["trading_account"] = account_number
        context.user_data["user_info"]["account_verified"] = account_verified
        context.user_data["user_info"]["account_owner"] = account_owner
        
        print(f"Stored account in user_data: {context.user_data}")
        
        # Update in database with proper error handling
        try:
            db_result = db.add_user({
                "user_id": user_id,
                "trading_account": account_number,
                "is_verified": account_verified,
                "account_owner": account_owner if account_owner else "Unknown",
                "last_response": account_number,
                "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            print(f"Database update result: {db_result}")
            
            # If account is verified, also mark it verified in the database
            if account_verified:
                mark_result = db.mark_user_verified(user_id)
                print(f"Mark verified result: {mark_result}")
        except Exception as e:
            print(f"ERROR updating database: {e}")
        
        # Set verification message based on result
        if account_verified:
            verification_message = (
                f"✅ Account {account_number} verified successfully!\n\n"
                f"Account owner: {account_owner}\n\n"
                f"Thank you for completing your registration. Our team will now process your information "
                f"and add you to the appropriate VIP channels based on your selected interests."
            )
            
            # Send profile summary to admins (add this function if not already defined)
            asyncio.create_task(send_profile_summary_to_admins(context, user_id))
        else:
            verification_message = (
                f"⚠️ Account {account_number} could not be verified automatically.\n\n"
                f"Your details have been saved and our team will manually review your information. "
                f"You'll receive access to your selected VIP channels after verification is complete."
            )
        
        # Send appropriate response to user
        await update.message.reply_text(verification_message)
        
        # Try to send admin notification independently
        asyncio.create_task(send_registration_notification(context, user_id, account_number, account_verified))
        
        # Clean up conversation data safely
        if "user_info" in context.user_data:
            user_info_copy = context.user_data["user_info"].copy()  # Keep a copy for logging
            del context.user_data["user_info"]
            print(f"Cleaned up user_info, contained: {user_info_copy}")
        
        print("===== TRADING ACCOUNT FUNCTION COMPLETED =====")
        return ConversationHandler.END
        
    except Exception as e:
        print(f"CRITICAL ERROR in trading_account: {e}")
        # Provide a fallback response
        await update.message.reply_text(
            "We encountered an issue processing your account. Please try again or contact support."
        )
        return ConversationHandler.END

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

                # Send the welcome message with HTML parsing and buttons
                await context.bot.send_message(
                    chat_id=original_sender_id,
                    text=formatted_msg,
                    parse_mode='HTML',  # Enable HTML parsing
                    reply_markup=reply_markup  # Add buttons
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
            
            # Get risk appetite and deposit amount
            user_name = user_info.get('first_name', 'Unknown')
            risk_appetite = user_info.get('risk_appetite', 'Not specified')
            deposit_amount = user_info.get('deposit_amount', 'Not specified')
            
            # Format copier team message
            copier_message = (
                f"🔄 NEW ACCOUNT FOR COPIER SYSTEM 🔄\n\n"
                f"User: {user_name} {user_info.get('last_name', '')}\n"
                f"Trading Account: {trading_account}\n"
                f"Risk Level: {risk_appetite}/10\n"
                f"Deposit Amount: ${deposit_amount}\n"
                f"VIP Channels: {user_info.get('vip_channels', 'None')}\n"
                f"Date Added: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"👉 Please add this account to the copier system."
            )
            
            # Update database to mark as forwarded to copier team
            db.add_user({
                "user_id": user_id,
                "copier_forwarded": True,
                "copier_forwarded_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # In production, this would be sent to a specific copier team chat
            # For now, we'll just update the message
            await query.edit_message_text(
                text=f"✅ Account forwarded to copier team:\n\n{copier_message}\n\n"
                f"(In production, this would be sent to your copier team's chat)",
                reply_markup=None
            )
            
            # Also notify the user
            try:
                user_notification = (
                    f"📊 Your trading account has been forwarded to our trading team!\n\n"
                    f"Account: {trading_account}\n"
                    f"Risk Level: {risk_appetite}/10\n\n"
                    f"Our team will set up your account with the optimal parameters based on your risk profile. "
                    f"You'll receive confirmation once your account is connected to our trading system."
                )
                
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_notification
                )
                print(f"Successfully sent copier team notification to user {user_id}")
            except Exception as e:
                print(f"Failed to send notification to user {user_id}: {e}")
                
        except Exception as e:
            await query.edit_message_text(
                text=f"⚠️ Error forwarding to copier team: {e}",
                reply_markup=None
            )
    else:
        await query.edit_message_text(
            text="⚠️ Invalid callback data format",
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
    if context.args and context.args[0].startswith("ref_"):
        # Don't await here, let it run independently
        asyncio.create_task(handle_referral(context, user, context.args[0]))
    
    # Add user to database if not exists
    db.add_user({
        "user_id": user.id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name
    })
    
    # Update user activity
    db.update_user_activity(user.id)
    
    # Send welcome message - this is the FIRST message the user should see
    await update.message.reply_text(f"Hello {user.first_name}! I'm your trading assistant bot.")
    
    # Update analytics
    db.update_analytics(active_users=1)
    
    # If this is a private chat, start the conversation
    if update.effective_chat.type == "private":
        await update.message.reply_text(
            f"{PRIVATE_WELCOME_MSG}\n\nFirst, what's your risk appetite from 1-10?"
        )
        return RISK_APPETITE
    
    return ConversationHandler.END

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
    if current_hour == 17:
        message = vfx_scheduler.get_welcome_message(17)
        message_type = "Daily Giveaway Announcement"
    elif current_hour == 18:
        message = vfx_scheduler.get_welcome_message(18)
        message_type = "Giveaway Countdown"
    elif current_hour == 19:
        message = vfx_scheduler.get_welcome_message(19)
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
    """Handle responses to the automated welcome message."""
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
            # Process as account number (after experience or explicitly in account_number state)
            print(f"Processing as account number: {message_text}")
            
            # Check if it looks like an account number
            if message_text.isdigit() and len(message_text) == 6:
                # Process account number
                db.add_user({
                    "user_id": user_id,
                    "trading_account": message_text,
                    "last_response": message_text,
                    "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Attempt to verify the account
                is_valid = auth.validate_account_format(message_text)
                print(f"Account validation for {message_text}: {is_valid}")
                
                if is_valid:
                    account_verified = auth.verify_account(message_text, user_id)
                    print(f"Account verification for {message_text}: {account_verified}")
                    
                    if account_verified:
                        db.mark_user_verified(user_id)
                        
                        # Show summary button
                        keyboard = [
                            [InlineKeyboardButton("📋 View Profile Summary", callback_data="view_summary")],
                            [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            "<b>Account Verified:</b> ✅\n\n"
                            "Thank you! Your MT5 account has been verified.\n\n"
                            "Our team will set up your strategy based on your risk profile. "
                            "You'll receive confirmation once everything is ready.",
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                        
                        # Reset state after completion
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "completed"
                        
                        # Send profile summary to admins
                        await send_profile_summary_to_admins(context, user_id)
                        
                    else:
                        # Account not verified
                        keyboard = [
                            [InlineKeyboardButton("Try Another Account", callback_data="edit_account")],
                            [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await update.message.reply_text(
                            "<b>Account Not Found:</b> ⚠️\n\n"
                            "We couldn't verify this account number in our system. "
                            "Our team will review it manually, or you can try entering a different account number.",
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                        
                        # Stay in same state
                        context.bot_data.setdefault("user_states", {})
                        context.bot_data["user_states"][user_id] = "account_pending"
                
                # Notify admin
                for admin_id in ADMIN_USER_ID:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=f"🔢 User {user_name} (ID: {user_id}) provided account: {message_text}\n"
                                 f"Verified: {'✅' if is_valid and account_verified else '❌'}"
                        )
                    except Exception as e:
                        print(f"Error notifying admin {admin_id}: {e}")
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


(RISK_APPETITE, DEPOSIT_AMOUNT, TRADING_INTEREST, TRADING_ACCOUNT, CAPTCHA_RESPONSE) = range(5)
async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store deposit amount and ask for trading interests."""
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
            
            # Ask for trading interests with buttons
            keyboard = [
                [InlineKeyboardButton("Trading Signals", callback_data="interest_signals")],
                [InlineKeyboardButton("Trading Strategy", callback_data="interest_strategy")],
                [InlineKeyboardButton("Prop Capital", callback_data="interest_propcapital")],
                [InlineKeyboardButton("All Services", callback_data="interest_all")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Great! Which of our VIP services are you interested in?",
                reply_markup=reply_markup
            )
            
            return TRADING_INTEREST
        else:
            await update.message.reply_text("Please enter an amount between 100 and 10,000.")
            return DEPOSIT_AMOUNT
    except ValueError:
        await update.message.reply_text("Please enter a valid amount between 100 and 10,000.")
        return DEPOSIT_AMOUNT

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



# ********************************************************** #

def main() -> None:
    """Start the bot."""
    # Create the Application
    print("Starting bot...")
    print("Setting up VFX message scheduler...")
    
    print(f"Admin ID is set to {ADMIN_USER_ID}")
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
    
    # Add callback handlers for all button types
    application.add_handler(CallbackQueryHandler(
        start_user_conversation_callback,
        pattern=r"^start_conv_\d+$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        send_instructions_callback,
        pattern=r"^instr_"
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
            TRADING_INTEREST: [CallbackQueryHandler(trading_interest_callback, pattern=r"^interest_")],
            TRADING_ACCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, trading_account)],
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
        time=time(hour=17, minute=0)
    )
    
    # 18:00 - Countdown to giveaway
    job_queue.run_daily(
        send_giveaway_message,
        time=time(hour=18, minute=0)
    )
    
    # 19:00 - Giveaway winner announcement
    job_queue.run_daily(
        send_giveaway_message,
        time=time(hour=19, minute=0)
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
    
    """---------------------------------
         Signal Jobs
    ------------------------------------"""
    
    job_queue.run_once(init_signal_system, 60)
    
    # Schedule regular signal checks - run every hour
    job_queue.run_repeating(
        check_and_send_signals,
        interval=300,  # 5 Min
        first=30  # First check 1 minute after bot start
    )
    
    job_queue.run_repeating(
        report_signal_system_status,
        interval=21600,  # Every 6 hours
        first=600  # First report 10 minutes after startup
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