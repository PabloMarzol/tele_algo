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