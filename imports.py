import logging
import polars as pl
import asyncio
import os
from datetime import datetime, time, timedelta

from telegram.ext.filters import MessageFilter
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
from userReg.auth_system import TradingAccountAuth
from local_DB.db_manager import TradingBotDatabase
from local_DB.vfx_Scheduler import VFXMessageScheduler
from mySQL.mysql_manager import get_mysql_connection
from configs.config import Config
from mySQL.mysql_manager import get_mysql_connection

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

# Global instance of the VFX message scheduler
config = Config()
vfx_scheduler = VFXMessageScheduler()
strategyChannel_scheduler = VFXMessageScheduler("./bot_data/strategy_messages.json")
propChannel_scheduler = VFXMessageScheduler("./bot_data/prop_messages.json")
signalsChannel_scheduler = VFXMessageScheduler("./bot_data/signals_messages.json")
educationChannel_scheduler = VFXMessageScheduler("./bot_data/ed_messages.json")

# GLOBAL CONSTS
BOT_MANAGER_TOKEN = config.BOT_MANAGER_TOKEN
BOT_ALGO_TOKEN = config.BOT_ALGO_TOKEN
ADMIN_USER_ID = config.ADMIN_USER_ID
ADMIN_USER_ID_2 = config.ADMIN_USER_ID_2

MAIN_CHANNEL_ID = config.MAIN_CHANNEL_ID
SUPPORT_GROUP_ID = config.SUPPORT_GROUP_ID
STRATEGY_CHANNEL_ID = config.STRATEGY_CHANNEL_ID
STRATEGY_GROUP_ID = config.STRATEGY_GROUP_ID
SIGNALS_CHANNEL_ID = config.SIGNALS_CHANNEL_ID
SIGNALS_GROUP_ID = config.SIGNALS_GROUP_ID
PROP_CHANNEL_ID = config.PROP_CHANNEL_ID
PROP_GROUP_ID = config.PROP_GROUP_ID
ED_CHANNEL_ID = config.ED_CHANNEL_ID
ED_GROUP_ID = config.ED_GROUP_ID


# Define conversation states
(RISK_APPETITE_MANUAL, DEPOSIT_AMOUNT_MANUAL, TRADING_ACCOUNT_MANUAL) = range(100, 103)  # Using different ranges to avoid conflicts


(RISK_APPETITE, DEPOSIT_AMOUNT, TRADING_INTEREST, TRADING_ACCOUNT, CAPTCHA_RESPONSE, 
 AWAITING_DEPOSIT_DECISION, PAYMENT_METHOD_SELECTION, DEPOSIT_CONFIRMATION) = range(8)





# Initialize database and auth system
db = TradingBotDatabase(data_dir="./bot_data")
auth = TradingAccountAuth(db_path="./bot_data/trading_accounts.csv")

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
