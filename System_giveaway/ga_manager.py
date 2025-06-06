import csv
import json
import random
import calendar
from datetime import datetime, timedelta
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from config_loader import ConfigLoader
from async_manager import require_giveaway_lock, require_file_safety
import threading
import asyncio
import sys
import os
import time

# Agregar la ruta del directorio padre para poder importar mysql
sys.path.append('../mySQL')

try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)  # tele_algo
    mysql_repo_dir = os.path.join(parent_dir, 'mySQL')
    mysql_file_path = os.path.join(mysql_repo_dir, 'mysql_manager.py')
    
    print(f"🔍 Looking for MySQL repo at: {mysql_repo_dir}")
    
    if os.path.exists(mysql_file_path):
        # Añadir el directorio del repo al sys.path
        if mysql_repo_dir not in sys.path:
            sys.path.insert(0, mysql_repo_dir)
            print(f"✅ Added MySQL repo to path: {mysql_repo_dir}")
        
        # 🎯 IMPORT directo ahora que sabemos las dependencias
        from mysql_manager import MySQLManager, get_mysql_connection
        
        MYSQL_AVAILABLE = True
        print("✅ MySQL Manager loaded from external repo")
        print(f"📁 Source: {mysql_file_path}")
        
        # Test básico de disponibilidad
        try:
            test_connection = get_mysql_connection()
            if test_connection:
                print("✅ MySQL connection test: Available")
            else:
                print("⚠️ MySQL loaded but connection requires configuration")
        except Exception as e:
            print(f"💡 MySQL loaded, connection test: {e}")
        
    else:
        raise ImportError(f"MySQL repo file not found: {mysql_file_path}")
        
except ImportError as e:
    print(f"⚠️ MySQL import failed: {e}")
    print("💡 Install with: pip install mysql-connector-python")
    MYSQL_AVAILABLE = False
    MySQLManager = None
    get_mysql_connection = None
    print("💾 Using CSV-only mode (fully functional)")
    
except Exception as e:
    print(f"❌ Unexpected MySQL error: {e}")
    MYSQL_AVAILABLE = False
    MySQLManager = None
    get_mysql_connection = None
    print("💾 Using CSV-only mode (fully functional)")

if MYSQL_AVAILABLE:
        try:
            # Test de conexión básico para verificar que el repo funciona
            test_connection = get_mysql_connection()
            if test_connection:
                print("✅ MySQL repo connection test: SUCCESS")
            else:
                print("⚠️ MySQL repo loaded but connection failed")
        except Exception as test_error:
            print(f"⚠️ MySQL repo test failed: {test_error}")
            print("💡 This is normal if database credentials are not configured")

def debug_mysql_path():
    """🔍 Debug function to verify MySQL path resolution"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    mysql_dir = os.path.join(parent_dir, 'mySQL')
    mysql_file = os.path.join(mysql_dir, 'mysql_manager.py')
    
    print("🔍 PATH DEBUG:")
    print(f"   Current file: {__file__}")
    print(f"   Current dir: {current_dir}")
    print(f"   Parent dir: {parent_dir}")
    print(f"   MySQL dir: {mysql_dir}")
    print(f"   MySQL file: {mysql_file}")
    print(f"   MySQL dir exists: {os.path.exists(mysql_dir)}")
    print(f"   MySQL file exists: {os.path.exists(mysql_file)}")
    print(f"   Directory contents: {os.listdir(parent_dir) if os.path.exists(parent_dir) else 'N/A'}")
# __name__ == "__main__":
    
# # 🧪 Ejecutar debug al importar (temporal)
#     debug_mysql_path()    

class GiveawaySystem:
    """Sistema completo de giveaways para bot de Telegram con validación MT5 y proceso de pago manual"""
    
    def __init__(self, mt5_api, bot, giveaway_type = 'daily', config_file='config.json'):
        """
        MODIFIED: Initialize giveaway system with specific type
        
        Args:
            mt5_api: MT5 API client for account validation
            bot: Telegram bot instance
            config_file: Path to JSON configuration file
            giveaway_type: Type of giveaway ('daily', 'weekly', 'monthly')
        """
        self.config_loader = ConfigLoader(config_file)
        
        # 🆕 NEW: Get configurations from loaded file
        bot_config = self.config_loader.get_bot_config()
        self.GIVEAWAY_CONFIGS = self.config_loader.get_giveaway_configs()
        
        # 🔄 MODIFIED: Use configuration from file
        self.mt5_api = mt5_api
        self.bot = bot
        self.channel_id = bot_config['channel_id']
        self.admin_id = bot_config['admin_id']
        self.admin_username = bot_config.get('admin_username', 'admin')
        
        # Type-specific configuration
        self.giveaway_type = giveaway_type
        self.config = self.GIVEAWAY_CONFIGS[giveaway_type]
        
        # 🆕 NEW: Database configuration from file
        db_config = self.config_loader.get_database_config()
        base_path = db_config.get('base_path', './System_giveaway/data')
        
        # File paths with configurable base path
        self.data_dir = f"{base_path}/{giveaway_type}"
        self.participants_file = f"{self.data_dir}/participants.csv"
        self.winners_file = f"{self.data_dir}/winners.csv"
        self.history_file = f"{self.data_dir}/history.csv"
        self.pending_winners_file = f"{self.data_dir}/pending_winners.csv"
        
        # Messages files
        self.messages_file = f"./System_giveaway/messages_{giveaway_type}.json"
        self.messages_common_file = "./System_giveaway/messages_common.json"
        
        # Use config values
        self.min_balance = self.config['min_balance']
        self.daily_prize = self.config['prize']  # Keep for compatibility
        self.winner_cooldown_days = self.config['cooldown_days']

        self._file_lock = threading.Lock()

        self.mysql_db = get_mysql_connection()
        # if MYSQL_AVAILABLE:
        #     try:
        #         self.mysql_db = get_mysql_connection()
        #         self.use_mysql = True
        #         self.logger.info(f"MySQL connection established for {giveaway_type}")
        #     except Exception as e:
        #         self.logger.warning(f"MySQL connection failed, falling back to CSV: {e}")
        #         self.mysql_db = None
        #         self.use_mysql = False
        # else:
        #     self.mysql_db = None
        #     self.use_mysql = False
        
        # 🆕 NEW: Configure logging from file
        logging_config = self.config_loader.get_logging_config()
        logging.basicConfig(
            level=getattr(logging, logging_config.get('level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(logging_config.get('file', 'giveaway_bot.log')),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(f'GiveawaySystem_{giveaway_type}')
        
        # Initialize files and messages
        self._initialize_files()
        self._load_messages()
        
        self.logger.info(f"{giveaway_type.upper()} Giveaway System initialized successfully")
        self.logger.info(f"Config loaded from: {config_file}")
        
    def get_config_value(self, key_path: str, default=None):
        """
        Get configuration value using dot notation
        
        Example: get_config_value('bot.token') or get_config_value('giveaway_configs.daily.prize')
        """
        try:
            keys = key_path.split('.')
            value = self.config_loader.get_all_config()
            
            for key in keys:
                value = value[key]
            
            return value
        except (KeyError, TypeError):
            return default

    def reload_configuration(self):
        """Reload configuration from file (useful for runtime updates)"""
        try:
            self.config_loader.reload_config()
            
            # Update runtime values
            bot_config = self.config_loader.get_bot_config()
            self.channel_id = bot_config['channel_id']
            self.admin_id = bot_config['admin_id']
            self.admin_username = bot_config.get('admin_username', 'admin')
            
            # Update giveaway configs
            self.GIVEAWAY_CONFIGS = self.config_loader.get_giveaway_configs()
            self.config = self.GIVEAWAY_CONFIGS[self.giveaway_type]
            
            # Update derived values
            self.min_balance = self.config['min_balance']
            self.daily_prize = self.config['prize']
            self.winner_cooldown_days = self.config['cooldown_days']
            
            self.logger.info("Configuration reloaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error reloading configuration: {e}")
            return False 

    def get_security_config(self):
        """Get security configuration"""
        return self.config_loader.get_security_config()
    
    def get_rate_limit_config(self):
        """Get rate limiting configuration"""
        security_config = self.get_security_config()
        return security_config.get('rate_limit', {'max_attempts': 4, 'window_minutes': 60}) 
    
    def get_configured_timezone(self):
        """Get configured timezone"""
        timezone_str = self.config_loader.get_timezone()
        
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(timezone_str)
        except ImportError:
            import pytz
            return pytz.timezone(timezone_str)

    def get_giveaway_config(self, giveaway_type=None):
        """Get configuration for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        return self.config.get(giveaway_type, {})
    
    def get_all_giveaway_types(self):
        """Get list of all available giveaway types"""
        return list(self.GIVEAWAY_CONFIGS.keys())
    
    def get_prize_amount(self, giveaway_type=None):
        """Get prize amount for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        return self.GIVEAWAY_CONFIGS[giveaway_type]['prize']
    
    def get_cooldown_days(self, giveaway_type=None):
        """Get cooldown days for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        return self.GIVEAWAY_CONFIGS[giveaway_type]['cooldown_days']
    
    def get_file_paths(self, giveaway_type=None):
        """Get file paths for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        base_dir = f"./System_giveaway/data/{giveaway_type}"
        return {
            'participants': f"{base_dir}/participants.csv",
            'winners': f"{base_dir}/winners.csv",
            'history': f"{base_dir}/history.csv",
            'pending_winners': f"{base_dir}/pending_winners.csv"
        }
    
    # 🆕 NEW: Participation window validation
    def is_participation_window_open(self, giveaway_type=None):
        """Check if participation window is currently open"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        if giveaway_type == self.giveaway_type:
            config = self.config  # ✅ Más eficiente para tipo actual
        else:
            config = self.GIVEAWAY_CONFIGS[giveaway_type]  # ✅ Para otros tipos
        
        window = config['participation_window']
        
        # Use London timezone
        try:
            from zoneinfo import ZoneInfo
            london_tz = ZoneInfo("Europe/London")
        except ImportError:
            # Fallback for older Python versions
            import pytz
            london_tz = pytz.timezone("Europe/London")
        
        # ORIGINAL
        now = datetime.now(london_tz)

        # 🎭 TESTING SIMULAR QUE ES VIERNES 16:30 (dentro de ventana de participación)
        # from datetime import timedelta
        # base_time = datetime.now(london_tz).replace(hour=16, minute=30, second=0, microsecond=0)
        # current_weekday = base_time.weekday()
        
        # # Calcular días hasta el próximo viernes (o mantener si ya es viernes)
        # if current_weekday <= 4:  # Lunes a viernes
        #     days_to_friday = 4 - current_weekday  # 0 si ya es viernes
        # else:  # Sábado o domingo
        #     days_to_friday = 7 - current_weekday + 4  # Ir al próximo viernes
        
        # now = base_time + timedelta(days=days_to_friday)
        
        # # 🧪 DEBUG: Mostrar fecha simulada
        # print(f"🎭 TESTING: Simulating {now.strftime('%A, %Y-%m-%d %H:%M')} (weekday: {now.weekday()})")
        
        # ==============================================================
        if giveaway_type == 'daily':
            # Monday to Friday, 1:00 AM - 4:50 PM
            return (now.weekday() < 5 and 
                    (now.hour > window['start_hour'] or 
                     (now.hour == window['start_hour'] and now.minute >= window['start_minute'])) and
                    (now.hour < window['end_hour'] or 
                     (now.hour == window['end_hour'] and now.minute <= window['end_minute'])))
        
        elif giveaway_type == 'weekly':
            # Monday 9:00 AM - Friday 5:00 PM
            return ((now.weekday() == 0 and now.hour >= window['start_hour']) or
                    (0 < now.weekday() < 4) or
                    (now.weekday() == 4 and now.hour < window['end_hour']))
        
        elif giveaway_type == 'monthly':
            # Day 1 - last Friday of month
            last_friday = self.get_last_friday_of_month()
            return (now.day >= window['start_day'] and 
                    now.date() <= last_friday.date() and
                    now.hour >= window['start_hour'])
        
        return False
    
    def get_participation_window_status(self, giveaway_type=None):
        """Get detailed participation window status"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        is_open = self.is_participation_window_open(giveaway_type)
        next_open = self.get_next_participation_window(giveaway_type)
        
        return {
            'is_open': is_open,
            'next_open': next_open,
            'giveaway_type': giveaway_type
        }
    
    # 🆕 NEW: Schedule helper functions
    def get_last_friday_of_month(self, year=None, month=None):
        """Calculate last Friday of current or specified month"""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        # Get last day of month
        last_day = calendar.monthrange(year, month)[1]
        last_date = datetime(year, month, last_day)
        
        # Find last Friday (Friday = 4)
        days_back = (last_date.weekday() - 4) % 7
        last_friday = last_date - timedelta(days=days_back)
        
        return last_friday
    
    def is_business_day(self, date):
        """Check if date is a business day (Monday-Friday)"""
        return date.weekday() < 5
    
    def get_next_draw_time(self, giveaway_type=None):
        """Get next scheduled draw time"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        if giveaway_type == self.giveaway_type:
            config = self.config  # ✅ Más eficiente
        else:
            config = self.GIVEAWAY_CONFIGS[giveaway_type]  # ✅ Para otros tipos
        
        schedule = config['draw_schedule']
        
        try:
            from zoneinfo import ZoneInfo
            london_tz = ZoneInfo("Europe/London")
        except ImportError:
            import pytz
            london_tz = pytz.timezone("Europe/London")
        
        # ORIGINAL
        now = datetime.now(london_tz)

        # 🎭 TESTING OVERRIDE  SIMULAR QUE ES VIERNES 14:30 
        # from datetime import timedelta
        # base_time = datetime.now(london_tz).replace(hour=16, minute=30, second=0, microsecond=0)
        # current_weekday = base_time.weekday()
        
        # # Calcular días hasta el próximo viernes
        # if current_weekday <= 4:  # Lunes a viernes
        #     days_to_friday = 4 - current_weekday
        # else:  # Sábado o domingo
        #     days_to_friday = 7 - current_weekday + 4
        
        # now = base_time + timedelta(days=days_to_friday)
        
        # =======================================testend===============
        if giveaway_type == 'daily':
            # Next weekday at 5:00 PM
            next_draw = now.replace(hour=schedule['hour'], minute=schedule['minute'], second=0, microsecond=0)
            if now >= next_draw or now.weekday() >= 5:
                # Move to next business day
                days_ahead = 1
                if now.weekday() >= 4:  # Thursday or Friday
                    days_ahead = 7 - now.weekday()  # Move to Monday
                next_draw += timedelta(days=days_ahead)
            
        elif giveaway_type == 'weekly':
            # Next Friday at 5:15 PM
            days_ahead = 4 - now.weekday()  # Friday = 4
            if days_ahead <= 0 or (days_ahead == 0 and now.hour >= schedule['hour']):
                days_ahead += 7
            next_draw = now + timedelta(days=days_ahead)
            next_draw = next_draw.replace(hour=schedule['hour'], minute=schedule['minute'], second=0, microsecond=0)
            
        elif giveaway_type == 'monthly':
            # Last Friday of current or next month at 5:30 PM
            last_friday = self.get_last_friday_of_month()
            if now.date() > last_friday.date() or (now.date() == last_friday.date() and now.hour >= schedule['hour']):
                # Move to next month
                if now.month == 12:
                    last_friday = self.get_last_friday_of_month(now.year + 1, 1)
                else:
                    last_friday = self.get_last_friday_of_month(now.year, now.month + 1)
            
            next_draw = last_friday.replace(hour=schedule['hour'], minute=schedule['minute'], second=0, microsecond=0)
        
        return next_draw
    
    def get_next_participation_window(self, giveaway_type=None):
        """Get next participation window opening time"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        if self.is_participation_window_open(giveaway_type):
            return "Currently open"
        
        # Calculate next opening based on type
        if giveaway_type == self.giveaway_type:
            config = self.config  # ✅ Más eficiente
        else:
            config = self.GIVEAWAY_CONFIGS[giveaway_type]  # ✅ Para otros tipos
        
        window = config['participation_window']
        
        try:
            from zoneinfo import ZoneInfo
            london_tz = ZoneInfo("Europe/London")
        except ImportError:
            import pytz
            london_tz = pytz.timezone("Europe/London")
        
        now = datetime.now(london_tz)
        
        if giveaway_type == 'daily':
            # Next weekday at 1:00 AM
            next_open = now.replace(hour=window['start_hour'], minute=window['start_minute'], second=0, microsecond=0)
            if now >= next_open or now.weekday() >= 5:
                days_ahead = 1
                if now.weekday() >= 4:
                    days_ahead = 7 - now.weekday()
                next_open += timedelta(days=days_ahead)
                
        elif giveaway_type == 'weekly':
            # Next Monday at 9:00 AM
            days_ahead = 7 - now.weekday()  # Days until next Monday
            next_open = now + timedelta(days=days_ahead)
            next_open = next_open.replace(hour=window['start_hour'], minute=window['start_minute'], second=0, microsecond=0)
            
        elif giveaway_type == 'monthly':
            # Day 1 of next month at 9:00 AM
            if now.month == 12:
                next_open = datetime(now.year + 1, 1, 1, window['start_hour'], window['start_minute'], tzinfo=london_tz)
            else:
                next_open = datetime(now.year, now.month + 1, 1, window['start_hour'], window['start_minute'], tzinfo=london_tz)
        
        return next_open
    
    def _initialize_files(self):
        """🔄 MODIFIED: Create type-specific files and directories"""
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Participants file
        if not os.path.exists(self.participants_file):
            with open(self.participants_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
        
        # Winners file
        if not os.path.exists(self.winners_file):
            with open(self.winners_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'mt5_account', 'prize', 'giveaway_type'])
        
        # History file
        if not os.path.exists(self.history_file):
            with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'won_prize', 'prize_amount', 'giveaway_type'])
        
        # Pending winners file
        if not os.path.exists(self.pending_winners_file):
            with open(self.pending_winners_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type'])
    
    def _load_messages(self):
        """🔄 MODIFIED: Load type-specific and common messages"""
        try:
            # Load common messages
            if os.path.exists(self.messages_common_file):
                with open(self.messages_common_file, 'r', encoding='utf-8') as f:
                    common_messages = json.load(f)
            else:
                common_messages = {}
            
            # Load type-specific messages
            if os.path.exists(self.messages_file):
                with open(self.messages_file, 'r', encoding='utf-8') as f:
                    type_messages = json.load(f)
            else:
                type_messages = {}
            
            # Merge messages (type-specific overrides common)
            self.messages = {**common_messages, **type_messages}
            
            # Merge messages (type-specific overrides common)
            self.messages = {**common_messages, **type_messages}
            # If no messages exist, create defaults
            if not self.messages:
                self._create_default_messages()
                self._save_messages()
            
            self.logger.info(f"Messages loaded for {self.giveaway_type} giveaway")
            
        except Exception as e:
            self.logger.error(f"Error loading messages: {e}")
            self._create_default_messages()
    
    def _create_default_messages(self):
        """🔄 MODIFIED: Create type-specific default messages in English"""
        # 🆕 NEW: Don't override existing messages from JSON files
        if hasattr(self, 'messages') and self.messages:
            # Messages already loaded from files, don't override
            self.logger.info(f"Using existing messages for {self.giveaway_type}")
            return
        # Base messages for this giveaway type
        prize = self.config['prize']
        min_balance = self.config['min_balance']  # 🎯 Dynamic min_balance
        
        if self.giveaway_type == 'daily':
            draw_schedule = "Monday to Friday at 5:00 PM London Time"
            next_draw = "Tomorrow at 5:00 PM London Time"
        elif self.giveaway_type == 'weekly':
            draw_schedule = "Every Friday at 5:15 PM London Time"
            next_draw = "Next Friday at 5:15 PM London Time"
        elif self.giveaway_type == 'monthly':
            draw_schedule = "Last Friday of each month at 5:30 PM London Time"
            next_draw = "Last Friday of next month at 5:30 PM London Time"

        period_name = {
            'daily': 'day',
            'weekly': 'week',
            'monthly': 'month'
        }.get(self.giveaway_type, 'period')
        
        self.messages = {
            "invitation": f"🎁 <b>{self.giveaway_type.upper()} GIVEAWAY ${prize} USD</b> 🎁\n\n💰 <b>Prize:</b> ${prize} USD\n⏰ <b>Draw:</b> {draw_schedule}\n\n<b>📋 Requirements to participate:</b>\n✅ Active VFX MT5 LIVE account\n✅ Minimum balance of ${min_balance} USD\n✅ Be a channel member\n\n👆 Press the button to participate",
            
            "success": f"✅ <b>Successfully registered!</b>\n\nYou are participating in the {self.giveaway_type} giveaway of ${prize} USD.\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "success_with_history": f"✅ <b>Successfully registered!</b>\n\nYou are participating in the {self.giveaway_type} giveaway of ${prize} USD with account {{account}}.\n\n📊 <b>Your history:</b> You have participated {{total_participations}} times with {{unique_accounts}} different account(s).\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "success_first_time": f"✅ <b>Successfully registered!</b>\n\n🎉 This is your first participation! You are in the {self.giveaway_type} giveaway of ${prize} USD.\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "already_registered": f"ℹ️ <b>Already registered</b>\n\nYou are already participating in today's {self.giveaway_type} giveaway.\n\n🍀 Good luck in the draw!\n\n⏰ Draw: {draw_schedule}",

            "already_participated_period": f"❌ <b>Already participated this {period_name}</b>\n\nYou already participated in this {period_name}'s {self.giveaway_type.upper()} giveaway with MT5 account {{previous_account}}.\n\n💡 <b>Rule:</b> Only one participation per user per {self.giveaway_type} {period_name}, regardless of the MT5 account used.\n\n🎁 You can participate in the next {self.giveaway_type} {period_name}.",
            
            "registration_in_progress": "⏳ <b>Registration in progress</b>\n\nYou already have a pending registration.\n\nPlease send your VFX MT5 account number to complete your participation.",
            
            "account_already_used_today": f"❌ <b>Account already registered today</b>\n\nThis VFX MT5 account was already used today by another user.\n\n💡 <b>Rule:</b> Each account can only participate once per {self.giveaway_type} period.\n\n🎁 You can participate in the next {self.giveaway_type} giveaway with any valid account.",
            
            "account_owned_by_other_user": "❌ <b>Account belongs to another user</b>\n\nThis VFX MT5 account was previously registered by another participant on {first_used}.\n\n💡 <b>Rule:</b> Each VFX MT5 account belongs exclusively to the first user who registered it.\n\n🎯 Use an MT5 account that is exclusively yours.",
            
            "insufficient_balance": "❌ <b>Insufficient balance</b>\n\nMinimum balance of ${min_balance} USD required\nYour current balance: <b>${balance}</b>\n\n💡 Deposit more funds to participate in future giveaways.",
            
            "not_live": "❌ <b>Invalid account</b>\n\nOnly VFX MT5 LIVE accounts can participate in the giveaway.\n\n💡 Verify that you entered the correct number of your LIVE account.",
            
            "account_not_found": "❌ <b>Account not found</b>\n\n VFX MT5 account #{account} was not found in our records.\n\n💡 Verify that the account number is correct.",
            
            "not_channel_member": "❌ <b>Not a channel member</b>\n\nYou must be a member of the main channel to participate.\n\n💡 Join the channel and try again.",
            
            "request_mt5": "🔢 <b>Enter your VFX MT5 account number</b>\n\nPlease send your VFX MT5 LIVE account number to verify that you meet the giveaway requirements.\n\n⚠️ <b>Important:</b> You can only register ONE account per day.\n\n📋 <b>Requirements for {self.giveaway_type.upper()}:</b>\n✅ LIVE account (not demo)\n✅ Minimum balance: ${min_balance} USD",
            
            "invalid_format_retry": "❌ <b>Invalid format</b>\n\nAccount number must contain only numbers.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n⚠️ Try again:",
            
            "max_attempts_reached": "❌ <b>Maximum attempts reached</b>\n\nYou have tried {max_attempts} times without success.\n\n🔄 <b>To participate again:</b>\n1. Go to the main channel\n2. Press \"PARTICIPATE NOW\" again\n3. Send a valid VFX MT5 account\n\n💡 Remember: Only LIVE accounts with balance ≥ ${min_balance} USD",
            
            "processing": "⏳ Verifying your VFX MT5 account...\n\nThis may take a few seconds.",
            
            "api_error": "❌ <b>Verification error</b>\n\nWe couldn't verify your account at this time.\n\n💡 Try again in a few minutes.",
            
            "no_eligible_participants": f"⚠️ No eligible participants for today's {self.giveaway_type} giveaway.\n\n📢 Join the next giveaway!",
            
            "winner_announcement": f"🏆 <b>{self.giveaway_type.upper()} GIVEAWAY WINNER!</b> 🏆\n\n🎉 Congratulations: {{username}}\n💰 Prize: <b>${prize} USD</b>\n📊 VFX MT5 Account: <b>{{account}}</b>\n👥 Total participants: <b>{{total_participants}}</b>\n\n📅 Next draw: {next_draw}\n\n🎁 Participate too!",
            
            "winner_private_congratulation": f"🎉 <b>CONGRATULATIONS!</b> 🎉\n\n🏆 <b>You won the {self.giveaway_type} giveaway of ${prize} USD!</b>\n\n💰 <b>Your VFX MT5 account {{account}} has been credited</b>\n\n📸 <b>IMPORTANT - Confirmation required:</b>\n• Check your VFX MT5 account\n• Confirm that you received the ${prize} USD\n• Send a screenshot as evidence\n\n🙏 This confirmation helps us improve the service",
            
            "participation_window_closed": f"⏰ <b>Participation window closed</b>\n\nThe {self.giveaway_type} giveaway participation is currently closed.\n\n🔄 <b>Next participation window:</b>\n{{next_window}}\n\n💡 Stay tuned for the next opportunity!",
            
            "error_internal": "❌ Internal error. Try again in a few minutes.",
            
            "help_main": f"🆘 <b>{self.giveaway_type.upper()} GIVEAWAY RULES</b>\n\n💰 <b>Prize:</b> ${prize} USD\n⏰ <b>Draw:</b> {draw_schedule}\n\n<b>📋 REQUIREMENTS TO PARTICIPATE:</b>\n✅ Be a member of this channel\n✅ Active VFX MT5 LIVE account (not demo)\n✅ Minimum balance of ${min_balance} USD\n✅ One participation per user per {self.giveaway_type} period\n\n<b>🔒 IMPORTANT RULES:</b>\n• Each Vortex-FX MT5 account belongs to the first user who registers it\n• You cannot win twice in {self.winner_cooldown_days} days\n• You must confirm receipt of prize if you win\n\n<b>❌ COMMON ERRORS:</b>\n• \"Account not found\" → Verify the number\n• \"Insufficient balance\" → Deposit more than $100 USD\n• \"Account is not LIVE\" → Use real account, not demo\n• \"Already registered\" → Only one participation per {self.giveaway_type} period\n• \"Account belongs to another\" → Use your own VFX MT5 account\n\n<b>📞 NEED HELP?</b>\nContact administrator: @{self.admin_username}\n\n<b>⏰ NEXT DRAW:</b>\n{next_draw}"
        }

    
    def _save_messages(self):
        """🔄 MODIFIED: Save type-specific messages"""
        try:
            os.makedirs(os.path.dirname(self.messages_file), exist_ok=True)
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving messages: {e}")
    
    # ================== INVITATION AND PARTICIPATION ==================
    
    async def send_invitation(self, giveaway_type=None):
        """🔄 MODIFIED: Send type-specific invitation with direct bot link"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            # Check if participation window is open
            if not self.is_participation_window_open(giveaway_type):
                self.logger.warning(f"Attempted to send {giveaway_type} invitation outside participation window")
                return False
            
            bot_info = await self.bot.get_me()
            bot_username = bot_info.username
            
            # Type-specific participation link
            participate_link = f"https://t.me/{bot_username}?start=participate_{giveaway_type}"
            
            keyboard = [[InlineKeyboardButton(f"🎯 PARTICIPATE {giveaway_type.upper()}", url=participate_link)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = self.messages.get("invitation", f"{giveaway_type.upper()} Giveaway active - Press PARTICIPATE")
            
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )
            
            self.logger.info(f"{giveaway_type.upper()} invitation with direct link sent to channel")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending {giveaway_type} invitation: {e}")
            return False
    
    async def handle_participate_button(self, update, context, giveaway_type=None):
        """🔄 MODIFIED: Handle participation button with type awareness"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            query = update.callback_query
            await query.answer()
            
            user = query.from_user
            user_id = user.id
            
            # Check participation window
            if not self.is_participation_window_open(giveaway_type):
                window_status = self.get_participation_window_status(giveaway_type)
                await self.bot.send_message(
                    chat_id=user_id,
                    text=self.messages.get("participation_window_closed", "Participation window closed").format(
                        next_window=window_status['next_open']
                    ),
                    parse_mode='HTML'
                )
                return
            
            # Check if already registered for this type
            if self._is_already_registered(user_id, giveaway_type):
                await self.bot.send_message(
                    chat_id=user_id,
                    text=self.messages.get("already_registered", "Already registered"),
                    parse_mode='HTML'
                )
                return
            
            # Check if has pending registration for this type
            if self._has_pending_registration(user_id, context, giveaway_type):
                await self.bot.send_message(
                    chat_id=user_id,
                    text=self.messages.get("registration_in_progress", "Registration in progress"),
                    parse_mode='HTML'
                )
                return
            
            # Check channel membership
            if not await self._check_channel_membership(user_id):
                await self.bot.send_message(
                    chat_id=user_id,
                    text=self.messages.get("not_channel_member", "Not a channel member"),
                    parse_mode='HTML'
                )
                return
            
            # Request MT5 account
            await self.bot.send_message(
                chat_id=user_id,
                text=self.messages.get("request_mt5", "Enter your VFX MT5 account number"),
                parse_mode='HTML'
            )
            
            # Save state for this giveaway type
            context.user_data[f'awaiting_mt5_{giveaway_type}'] = True
            context.user_data[f'user_info_{giveaway_type}'] = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'giveaway_type': giveaway_type
            }
            
        except Exception as e:
            self.logger.error(f"Error handling {giveaway_type} participate button: {e}")
    
    async def handle_mt5_input(self, update, context, giveaway_type=None):
        """🔄 MODIFIED: Handle MT5 input with type awareness"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            # Check if awaiting MT5 for this type
            if not context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                return
            
            mt5_account = update.message.text.strip()
            user_info = context.user_data.get(f'user_info_{giveaway_type}')
            
            # Initialize attempt counter for this type
            attempts_key = f'mt5_attempts_{giveaway_type}'
            if attempts_key not in context.user_data:
                context.user_data[attempts_key] = 0
            
            context.user_data[attempts_key] += 1
            max_attempts = 4
            remaining_attempts = max_attempts - context.user_data[attempts_key]
            
            # Validate format
            if not mt5_account.isdigit():
                if remaining_attempts > 0:
                    retry_message = self.messages.get("invalid_format_retry", "Invalid format. Attempts remaining: {remaining_attempts}").format(
                        remaining_attempts=remaining_attempts
                    )
                    await update.message.reply_text(retry_message, parse_mode='HTML')
                    return
                else:
                    await self._handle_max_attempts_reached(update, context, max_attempts, giveaway_type)
                    return
            
            # Process participation with retry logic
            success = await self.process_participation_with_retry(
                user_info, mt5_account, update, context, remaining_attempts, max_attempts, giveaway_type
            )
            
            # Clean state if successful or no attempts left
            if success or remaining_attempts <= 0:
                context.user_data.pop(f'awaiting_mt5_{giveaway_type}', None)
                context.user_data.pop(f'user_info_{giveaway_type}', None)
                context.user_data.pop(attempts_key, None)
            
        except Exception as e:
            self.logger.error(f"Error processing {giveaway_type} MT5 input: {e}")
            await update.message.reply_text(
                self.messages.get("error_internal", "Internal error. Try again in a few minutes."),
                parse_mode='HTML'
            )
    
    async def process_participation_with_retry(self, user_info, mt5_account, update, context, remaining_attempts, max_attempts, giveaway_type=None):
        """🔄 MODIFIED: Process participation with retry logic and type awareness"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            user_id = user_info['id']

            already_participated, previous_account = self._user_already_participated_today(user_id, giveaway_type)
            if already_participated:
                period_name = {
                    'daily': 'day',
                    'weekly': 'week', 
                    'monthly': 'month'
                }.get(giveaway_type, 'period')
                
                await update.message.reply_text(
                    f"❌ <b>Already participated this {period_name}</b>\n\n"
                    f"You already participated in this {period_name}'s {giveaway_type.upper()} giveaway with VFX MT5 account: <code>{previous_account}</code>\n\n"
                    f"💡 <b>Rule:</b> Only one participation per user per {giveaway_type} {period_name}, regardless of the VFX MT5 account used.\n\n"
                    f"🎁 You can participate in the next {giveaway_type} {period_name}.",
                    parse_mode='HTML'
                )
                return True  # End process
            
            # VALIDATION 1: User already registered for this type today?
            if self._is_already_registered(user_id, giveaway_type):
                await update.message.reply_text(
                    self.messages.get("already_registered", "Already registered"),
                    parse_mode='HTML'
                )
                return True
            
            # VALIDATION 2: Account already used today for this type?
            account_used_today, other_user_id = self._is_account_already_used_today(mt5_account, giveaway_type)
            if account_used_today:
                if remaining_attempts > 0:
                    retry_message = f"❌ <b>Account already registered today</b>\n\nThis VFX MT5 account was already used today for the {giveaway_type} giveaway by another user.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Try with a different account:"
                    await update.message.reply_text(retry_message, parse_mode='HTML')
                    return False
                else:
                    await self._handle_max_attempts_reached(update, context, max_attempts, giveaway_type)
                    return True
            
            # VALIDATION 3: Account belongs to another user historically?
            is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(mt5_account, user_id, giveaway_type)
            if is_other_user_account:
                if remaining_attempts > 0:
                    retry_message = f"❌ <b>Account belongs to another user</b>\n\nThis VFX MT5 account was previously registered by another participant.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use an MT5 account that is exclusively yours:"
                    await update.message.reply_text(retry_message, parse_mode='HTML')
                    return False
                else:
                    await self._handle_max_attempts_reached(update, context, max_attempts, giveaway_type)
                    return True
            
            # VALIDATION 4: Validate MT5 account with API
            # validation_result = self.validate_mt5_account(mt5_account)
            validation_result = self.validate_account_for_giveaway(mt5_account, user_id, giveaway_type)
            
            if not validation_result['valid']:
                error_type = validation_result['error_type']
                
                if remaining_attempts > 0:
                    if error_type == 'not_found':
                        retry_message = f"❌ <b>Account not found</b>\n\n Vortex-FX MT5 account #{mt5_account} was not found in our records.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Verify the number and try again:"
                    elif error_type == 'not_live':
                        retry_message = f"❌ <b>Invalid account</b>\n\nOnly Vortex-FX MT5 LIVE accounts can participate in the giveaway.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use a LIVE account and try again:"
                    elif error_type == 'insufficient_balance':
                        balance = validation_result.get('balance', 0)
                        required_balance = validation_result.get('required_balance', 100)
                        retry_message = f"❌ <b>Insufficient balance {giveaway_type.upper()}</b>\n\nMinimum balance of ${required_balance} USD required for {giveaway_type} giveaway\nYour current balance: <b>${balance}</b>\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use an account with sufficient balance:"
                    else:
                        retry_message = f"❌ <b>Verification error</b>\n\nWe couldn't verify your account at this time.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Try with another account:"
                    
                    await update.message.reply_text(retry_message, parse_mode='HTML')
                    return False
                else:
                    await self._handle_max_attempts_reached(update, context, max_attempts, giveaway_type)
                    return True
            
            # VALIDATION 5: Check channel membership
            if not await self._check_channel_membership(user_id):
                await update.message.reply_text(
                    self.messages.get("not_channel_member", "Not a channel member"),
                    parse_mode='HTML'
                )
                return True
            
            # ALL VALIDATIONS PASSED - Save participant
            participant_data = {
                'telegram_id': user_id,
                'username': user_info.get('username', ''),
                'first_name': user_info.get('first_name', ''),
                'mt5_account': mt5_account,
                'balance': validation_result['balance'],
                'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'active',
                'giveaway_type': giveaway_type
            }
            
            self._save_participant(participant_data, giveaway_type)
            
            # Get user history for personalized message
            user_history = self.get_user_account_history(user_id, giveaway_type)
            
            if len(user_history) > 1:
                unique_accounts = len(set(acc['mt5_account'] for acc in user_history))
                success_message = self.messages.get("success_with_history", "Successfully registered").format(
                    account=mt5_account,
                    total_participations=len(user_history),
                    unique_accounts=unique_accounts
                )
            else:
                success_message = self.messages.get("success_first_time", "First participation!")
            
            await update.message.reply_text(success_message, parse_mode='HTML')
            
            self.logger.info(f"User {user_id} registered successfully for {giveaway_type} giveaway with account {mt5_account}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing {giveaway_type} participation with retries: {e}")
            await update.message.reply_text(
                self.messages.get("error_internal", "Internal error. Try again."),
                parse_mode='HTML'
            )
            return True
    
    async def _handle_max_attempts_reached(self, update, context, max_attempts, giveaway_type=None):
        """🔄 MODIFIED: Handle max attempts with type awareness"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            max_attempts_message = self.messages.get("max_attempts_reached", "Maximum attempts reached").format(
                max_attempts=max_attempts
            )
            
            await update.message.reply_text(max_attempts_message, parse_mode='HTML')
            
            # Clean type-specific state
            context.user_data.pop(f'awaiting_mt5_{giveaway_type}', None)
            context.user_data.pop(f'user_info_{giveaway_type}', None)
            context.user_data.pop(f'mt5_attempts_{giveaway_type}', None)
            
            user_id = context.user_data.get(f'user_info_{giveaway_type}', {}).get('id', 'unknown')
            self.logger.info(f"User {user_id} reached max attempts for {giveaway_type} giveaway")
            
        except Exception as e:
            self.logger.error(f"Error handling max attempts for {giveaway_type}: {e}")
    
    # ================== VALIDATIONS To MT5 Accounts ==================
    
    # def validate_mt5_account(self, account_number):
    #     """✅ ORIGINAL: Validate MT5 account using API (no changes needed)"""
    #     try:
    #         account_info = self._simulate_mt5_api(account_number)
            
    #         if account_info is None:
    #             return {
    #                 'valid': False,
    #                 'error_type': 'not_found',
    #                 'message': 'Account not found'
    #             }
            
    #         if not account_info.get('is_live', False):
    #             return {
    #                 'valid': False,
    #                 'error_type': 'not_live',
    #                 'message': 'Account is not LIVE'
    #             }
            
    #         balance = account_info.get('balance', 0)
    #         if balance < self.min_balance:
    #             return {
    #                 'valid': False,
    #                 'error_type': 'insufficient_balance',
    #                 'balance': balance,
    #                 'message': f'Insufficient balance: ${balance}'
    #             }
            
    #         return {
    #             'valid': True,
    #             'balance': balance,
    #             'message': 'Valid account'
    #         }
            
    #     except Exception as e:
    #         self.logger.error(f"Error validating MT5 account: {e}")
    #         return {
    #             'valid': False,
    #             'error_type': 'api_error',
    #             'message': 'Validation error'
    #         }

    def validate_mt5_account(self, account_number):
        """Validate MT5 account using REAL MySQL database"""
        try:
            # 🎯 USAR LA FUNCIÓN HELPER (recomendado)
            mysql_db = get_mysql_connection()
            
            if not mysql_db.is_connected():
                return {
                    'valid': False,
                    'error_type': 'api_error',
                    'message': 'Database connection failed'
                }
            
            # ✅ Usar el método verify_account_exists de la clase
            account_info = mysql_db.verify_account_exists(account_number)
            
            # Resto de tu lógica...
            if not account_info.get('exists', False):
                return {
                    'valid': False,
                    'error_type': 'not_found',
                    'message': 'Account not found'
                }
            
            if not account_info.get('is_real_account', False):
                return {
                    'valid': False,
                    'error_type': 'not_live',
                    'message': 'Account is not LIVE (demo account detected)',
                    'account_type': account_info.get('account_type', 'Demo')
                }
            
            balance = account_info.get('balance', 0)
            if balance < self.min_balance:
                return {
                    'valid': False,
                    'error_type': 'insufficient_balance',
                    'balance': balance,
                    'message': f'Insufficient balance: ${balance} (minimum: ${self.min_balance})'
                }
            
            return {
                'valid': True,
                'balance': balance,
                'account_info': account_info,
                'account_holder_name': account_info.get('name', ''),
                'email': account_info.get('email', ''),
                'country': account_info.get('country', ''),
                'message': 'Valid LIVE account with sufficient balance'
            }
            
        except Exception as e:
            self.logger.error(f"Error validating VFX MT5 account {account_number}: {e}")
            return {
                'valid': False,
                'error_type': 'api_error',
                'message': f'Validation error: {str(e)}'
            }
    
    # def _simulate_mt5_api(self, account_number):
    #     """✅ ORIGINAL: MT5 API simulation (no changes needed)"""
    #     test_accounts = {
    #         # Valid accounts for testing
    #         '1234': {'exists': True, 'is_live': True, 'balance': 150.50, 'currency': 'USD'},
    #         '8765': {'exists': True, 'is_live': True, 'balance': 250.75, 'currency': 'USD'},
    #         '3333': {'exists': True, 'is_live': True, 'balance': 300.00, 'currency': 'USD'},
    #         '4444': {'exists': True, 'is_live': True, 'balance': 125.25, 'currency': 'USD'},
    #         '5555': {'exists': True, 'is_live': True, 'balance': 500.00, 'currency': 'USD'},
    #         '6666': {'exists': True, 'is_live': True, 'balance': 199.99, 'currency': 'USD'},
    #         '7777': {'exists': True, 'is_live': True, 'balance': 1000.00, 'currency': 'USD'},
    #         '8888': {'exists': True, 'is_live': True, 'balance': 750.50, 'currency': 'USD'},
    #         '1010': {'exists': True, 'is_live': True, 'balance': 100.00, 'currency': 'USD'},
    #         '2020': {'exists': True, 'is_live': True, 'balance': 100.01, 'currency': 'USD'},
            
    #         # Insufficient balance
    #         '2222': {'exists': True, 'is_live': True, 'balance': 50.00, 'currency': 'USD'},
    #         '3030': {'exists': True, 'is_live': True, 'balance': 99.99, 'currency': 'USD'},
    #         '4040': {'exists': True, 'is_live': True, 'balance': 25.50, 'currency': 'USD'},
    #         '5050': {'exists': True, 'is_live': True, 'balance': 0.00, 'currency': 'USD'},
            
    #         # Demo accounts
    #         '1111': {'exists': True, 'is_live': False, 'balance': 200.00, 'currency': 'USD'},
    #         '6060': {'exists': True, 'is_live': False, 'balance': 500.00, 'currency': 'USD'},
    #         '7070': {'exists': True, 'is_live': False, 'balance': 1000.00, 'currency': 'USD'},
    #     }
        
    #     return test_accounts.get(account_number)

    # def validate_account_for_giveaway(self, account_number, user_id):
    #     """Complete validation including giveaway-specific rules"""
        
    #     # 1. Validación básica de cuenta MT5
    #     mt5_validation = self.validate_mt5_account(account_number)
        
    #     if not mt5_validation['valid']:
    #         return mt5_validation
        
    #     # 2. Verificar si la cuenta ya fue usada hoy por otro usuario
    #     account_used_today, other_user_id = self._is_account_already_used_today(account_number, self.giveaway_type)
    #     if account_used_today:
    #         return {
    #             'valid': False,
    #             'error_type': 'account_already_used_today',
    #             'message': f'Account already used today by another participant',
    #             'used_by': other_user_id
    #         }
        
    #     # 3. Verificar ownership histórico
    #     is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(account_number, user_id, self.giveaway_type)
    #     if is_other_user_account:
    #         return {
    #             'valid': False,
    #             'error_type': 'account_owned_by_other_user',
    #             'message': f'Account belongs to another user (first used: {first_used})',
    #             'owner_id': owner_id
    #         }
        
    #     # ✅ Todas las validaciones pasadas
    #     return {
    #         'valid': True,
    #         'account_info': mt5_validation['account_info'],
    #         'balance': mt5_validation['balance'],
    #         'message': 'Account validated for giveaway participation'
    #     }

    def validate_account_for_giveaway(self, account_number, user_id, giveaway_type=None):
        """🔄 ENHANCED: Complete validation including giveaway-specific rules and min_balance"""
        
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # 🆕 GET TYPE-SPECIFIC MIN_BALANCE from config
        type_min_balance = self.GIVEAWAY_CONFIGS[giveaway_type]['min_balance']
        
        # 1. Validación básica de cuenta MT5 (with type-specific min_balance)
        mt5_validation = self.validate_mt5_account_with_balance(account_number, type_min_balance)
        
        if not mt5_validation['valid']:
            return mt5_validation
        
        # 2. Verificar si la cuenta ya fue usada hoy por otro usuario
        account_used_today, other_user_id = self._is_account_already_used_today(account_number, giveaway_type)
        if account_used_today:
            return {
                'valid': False,
                'error_type': 'account_already_used_today',
                'message': f'Account already used today by another participant',
                'used_by': other_user_id
            }
        
        # 3. Verificar ownership histórico
        is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(account_number, user_id, giveaway_type)
        if is_other_user_account:
            return {
                'valid': False,
                'error_type': 'account_owned_by_other_user',
                'message': f'Account belongs to another user (first used: {first_used})',
                'owner_id': owner_id
            }
        
        # ✅ Todas las validaciones pasadas
        return {
            'valid': True,
            'account_info': mt5_validation['account_info'],
            'balance': mt5_validation['balance'],
            'min_balance_required': type_min_balance,  # 🆕 Include for reference
            'giveaway_type': giveaway_type,  # 🆕 Include for reference
            'message': f'Account validated for {giveaway_type} giveaway (min: ${type_min_balance})'
        }
    
    def validate_mt5_account_with_balance(self, account_number, required_min_balance):
        """🆕 NEW: Validate MT5 account with custom minimum balance requirement"""
        try:
            mysql_db = get_mysql_connection()
            
            if not mysql_db.is_connected():
                return {
                    'valid': False,
                    'error_type': 'api_error',
                    'message': 'Database connection failed'
                }
            
            # ✅ Usar el método verify_account_exists de la clase
            account_info = mysql_db.verify_account_exists(account_number)
            
            if not account_info.get('exists', False):
                return {
                    'valid': False,
                    'error_type': 'not_found',
                    'message': 'Account not found'
                }
            
            if not account_info.get('is_real_account', False):
                return {
                    'valid': False,
                    'error_type': 'not_live',
                    'message': 'Account is not LIVE (demo account detected)',
                    'account_type': account_info.get('account_type', 'Demo')
                }
            
            balance = account_info.get('balance', 0)
            
            # 🎯 USE THE PROVIDED MIN_BALANCE (type-specific)
            if balance < required_min_balance:
                return {
                    'valid': False,
                    'error_type': 'insufficient_balance',
                    'balance': balance,
                    'required_balance': required_min_balance,
                    'message': f'Insufficient balance: ${balance} (minimum: ${required_min_balance})'
                }
            
            return {
                'valid': True,
                'balance': balance,
                'account_info': account_info,
                'account_holder_name': account_info.get('name', ''),
                'email': account_info.get('email', ''),
                'country': account_info.get('country', ''),
                'min_balance_met': True,
                'required_min_balance': required_min_balance,
                'message': f'Valid LIVE account with sufficient balance (${balance} >= ${required_min_balance})'
            }
            
        except Exception as e:
            self.logger.error(f"Error validating MT5 account {account_number} with min_balance {required_min_balance}: {e}")
            return {
                'valid': False,
                'error_type': 'api_error',
                'message': f'Validation error: {str(e)}'
            }
    def get_account_full_info(self, account_number):
        """Get complete account information for logging/admin purposes"""
        try:
            mysql_db = get_mysql_connection()
            
            if not mysql_db.is_connected():
                return None
            
            account_info = mysql_db.verify_account_exists(account_number)
            
            if account_info.get('exists'):
                return {
                    'account_number': account_info['account_number'],
                    'name': account_info['name'],
                    'email': account_info['email'],
                    'balance': account_info['balance'],
                    'group': account_info['group'],
                    'status': account_info['status'],
                    'country': account_info['country'],
                    'company': account_info['company'],
                    'account_type': account_info['account_type'],
                    'is_real': account_info['is_real_account'],
                    'creation_date': account_info['creation_date']
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return None
    
    def _is_already_registered(self, user_id, giveaway_type=None):
        """🔄 MODIFIED: Check if user is registered for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            if giveaway_type is None:
                giveaway_type = self.giveaway_type
    
        
            today = datetime.now().strftime('%Y-%m-%d')
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            print(f"🔍 DEBUG: Checking registration for user {user_id} in {giveaway_type}")
            print(f"🔍 DEBUG: Participants file: {participants_file}")
            print(f"🔍 DEBUG: Today's date: {today}")
            print(f"🔍 DEBUG: File exists: {os.path.exists(participants_file)}")
            
            if not os.path.exists(participants_file):
                print(f"🔍 DEBUG: File doesn't exist, user not registered")
                return False
            
            # 🆕 LEER TODO EL ARCHIVO PRIMERO
            with open(participants_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"🔍 DEBUG: Full file content ({len(content)} chars):")
                print(f"🔍 DEBUG: Content preview: {repr(content[:200])}...")
            
            # 🆕 PROCESAR LÍNEA POR LÍNEA
            with open(participants_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                row_count = 0
                for row in reader:
                    row_count += 1
                    print(f"🔍 DEBUG: Row {row_count} - ID: '{row.get('telegram_id')}', Date: '{row.get('registration_date')}', Status: '{row.get('status')}'")
                    
                    # Verificar cada condición por separado
                    id_match = row.get('telegram_id') == str(user_id)
                    date_match = row.get('registration_date', '').startswith(today)
                    status_match = row.get('status') == 'active'
                    
                    print(f"🔍 DEBUG: ID match: {id_match}, Date match: {date_match}, Status match: {status_match}")
                    
                    if id_match and date_match and status_match:
                        print(f"✅ DEBUG: User {user_id} IS registered for {giveaway_type}")
                        return True
            
            print(f"🔍 DEBUG: Processed {row_count} rows, user {user_id} NOT registered for {giveaway_type}")
            return False
        except Exception as e:
            self.logger.error(f"Error checking registration for {giveaway_type}: {e}")
            return False
    
    def _user_already_participated_today(self, user_id, giveaway_type=None):
        """Check if user already participated today with ANY account"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            participants_file = self.get_file_paths(giveaway_type)['participants']
        
            if not os.path.exists(participants_file):
                return False, None
            
            # 🔄 DIFFERENT PERIOD LOGIC based on giveaway type
            if giveaway_type == 'daily':
                # Check today only
                today = datetime.now().strftime('%Y-%m-%d')
                period_check = lambda date_str: date_str.startswith(today)
                
            elif giveaway_type == 'weekly':
                # Check current week (Monday to current day)
                current_date = datetime.now()
                week_start = current_date - timedelta(days=current_date.weekday())  # Monday
                week_start_str = week_start.strftime('%Y-%m-%d')
                period_check = lambda date_str: date_str >= week_start_str
                
            elif giveaway_type == 'monthly':
                # Check current month
                current_month = datetime.now().strftime('%Y-%m')
                period_check = lambda date_str: date_str.startswith(current_month)
            
            else:
                # Fallback to daily
                today = datetime.now().strftime('%Y-%m-%d')
                period_check = lambda date_str: date_str.startswith(today)
            
            with open(participants_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row.get('telegram_id') == str(user_id) and 
                        period_check(row.get('registration_date', '')) and 
                        row.get('status') == 'active'):
                        return True, row['mt5_account']
            
            return False, None
            
        except Exception as e:
            self.logger.error(f"Error checking {giveaway_type} user participation: {e}")
            return False, None

    def _has_pending_registration(self, user_id, context, giveaway_type=None):
        """🔄 MODIFIED: Check pending registration for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        return (context.user_data.get(f'awaiting_mt5_{giveaway_type}') and 
                context.user_data.get(f'user_info_{giveaway_type}', {}).get('id') == user_id)
    
    def _is_account_already_used_today(self, mt5_account, giveaway_type=None):
        """🔄 MODIFIED: Check if account used today for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            if not os.path.exists(participants_file):
                return False, None
            
            with open(participants_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['mt5_account'] == str(mt5_account) and 
                        row['registration_date'].startswith(today) and 
                        row['status'] == 'active'):
                        return True, row['telegram_id']
            return False, None
        except Exception as e:
            self.logger.error(f"Error checking duplicate account for {giveaway_type}: {e}")
            return False, None
    
    def _is_account_owned_by_other_user(self, mt5_account, current_user_id, giveaway_type=None):
        """🔄 MODIFIED: Check account ownership for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            file_paths = self.get_file_paths(giveaway_type)
            
            # Check current participants
            if os.path.exists(file_paths['participants']):
                with open(file_paths['participants'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['mt5_account'] == str(mt5_account) and 
                            row['telegram_id'] != str(current_user_id) and 
                            row['status'] == 'active'):
                            return True, row['telegram_id'], row['registration_date']
            
            # Check permanent history
            if os.path.exists(file_paths['history']):
                with open(file_paths['history'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['mt5_account'] == str(mt5_account) and 
                            row['telegram_id'] != str(current_user_id) and 
                            row['telegram_id'] != 'NO_PARTICIPANTS'):
                            return True, row['telegram_id'], row['date']
            
            return False, None, None
        except Exception as e:
            self.logger.error(f"Error checking account ownership for {giveaway_type}: {e}")
            return False, None, None
    
    async def _check_channel_membership(self, user_id):
        """✅ ORIGINAL: Check channel membership (no changes needed)"""
        try:
            member = await self.bot.get_chat_member(self.channel_id, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            self.logger.error(f"Error checking membership: {e}")
            return False


    # Segunda parte de la implementacion

    # ================== GIVEAWAY EXECUTION AND WINNER MANAGEMENT ==================
    
    async def run_giveaway(self, giveaway_type=None, prize_amount=None):
        """🔄 MODIFIED: Execute giveaway for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            period_names = {
                'daily': 'daily',
                'weekly': 'weekly',
                'monthly': 'monthly'
            }
            
            period_name = period_names.get(giveaway_type, 'daily')
            prize = prize_amount or self.get_prize_amount(giveaway_type)
            
            self.logger.info(f"Starting {period_name} giveaway")
            print(f"🎲 DEBUG: Executing {giveaway_type} giveaway with prize ${prize}")
            
            # Get eligible participants for this type
            eligible_participants = self._get_eligible_participants(giveaway_type)
            
            if not eligible_participants:
                # Save empty period to history
                await self._save_empty_period_to_history(giveaway_type)
                admin_config = self.config_loader.get_all_config().get('admin_channel_id', {})
                admin_channel_id = admin_config.get('admin_channel_id')
                await self.bot.send_message(
                    chat_id=admin_channel_id,
                    text=self.messages.get("no_eligible_participants", "No eligible participants"),
                    parse_mode='HTML'
                )
                
                # Clean up even without participants
                self._prepare_for_next_period(giveaway_type)
                return
            
            print(f"👥 DEBUG: {len(eligible_participants)} eligible participants found for {giveaway_type}")
            
            # Select winner
            winner = self._select_winner(eligible_participants)
            
            if winner:
                print(f"🏆 DEBUG: Winner selected for {giveaway_type}: {winner['telegram_id']}")
                
                # 1. Save winner as pending payment
                self._save_winner_pending_payment(winner, giveaway_type, prize)
                
                # 2. Notify administrator
                await self._notify_admin_winner(winner, len(eligible_participants), giveaway_type, prize)
                
                # 3. Save period results to permanent history
                await self._save_period_results_to_history(winner, giveaway_type)
                
                # 4. Prepare for next period
                self._prepare_for_next_period(giveaway_type)
                
                self.logger.info(f"{period_name.title()} giveaway completed. Winner: {winner['telegram_id']}")
                print(f"✅ DEBUG: {giveaway_type} giveaway completed and participants cleaned")
            
        except Exception as e:
            self.logger.error(f"Error executing {giveaway_type} giveaway: {e}")
            raise
    
#     async def _notify_admin_winner(self, winner, total_participants, giveaway_type=None, prize_amount=None):
#         """🔄 MODIFIED: Notify admin with type-specific information"""
#         if giveaway_type is None:
#             giveaway_type = self.giveaway_type
#         if prize_amount is None:
#             prize_amount = self.get_prize_amount(giveaway_type)
        
#         try:
#             today = datetime.now().strftime('%Y-%m-%d')
#             username = winner.get('username', '').strip()
#             first_name = winner.get('first_name', 'N/A')
            
#             # Prepare winner display
#             if username:
#                 winner_display = f"@{username}"
#                 command_identifier = username
#             else:
#                 winner_display = f"{first_name} (No username)"
#                 command_identifier = winner['telegram_id']

#             # 🆕 OBTENER admin principal por nombre "Main Administrator"
#             permission_manager = None
#             try:
#                 if hasattr(self.bot, 'application') and hasattr(self.bot.application, 'bot_data'):
#                     permission_manager = self.bot.application.bot_data.get('permission_manager')
#             except:
#                 pass
            
#             main_admin_id = None
#             if permission_manager:
#                 main_admin_id = permission_manager.get_main_admin_id()
            
#             # Fallback al config si no encuentra "Main Administrator"
#             if not main_admin_id:
#                 main_admin_id = self.admin_id
            
#             admin_message = f"""🏆 <b>{giveaway_type.upper()} WINNER SELECTED - ACTION REQUIRED</b>

# 🎉 <b>Winner:</b> {first_name} ({winner_display})
# 💰 <b>Prize:</b> ${prize_amount} USD
# 📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
# 🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
# 👥 <b>Total participants:</b> {total_participants}
# 📅 <b>Date:</b> {today}
# 🎯 <b>Giveaway Type:</b> {giveaway_type.upper()}

# ⚠️ <b>INSTRUCTIONS:</b>
# 1️⃣ Transfer ${prize_amount} USD to MT5 account: <code>{winner['mt5_account']}</code>
# 2️⃣ Once completed, press the confirmation button below

# ⏳ <b>Status:</b> Waiting for manual transfer
# 💡 <b>Use command:</b> <code>/admin_confirm_payment_{giveaway_type} {command_identifier}</code>"""
            
#             # Create inline button for quick confirmation
#             button_text = f"✅ Confirm payment to {first_name}"
#             callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
            
#             keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
#             reply_markup = InlineKeyboardMarkup(keyboard)
            
#             await self.bot.send_message(
#                 chat_id=self.admin_id,
#                 text=admin_message,
#                 parse_mode='HTML',
#                 reply_markup=reply_markup
#             )

#             # 🆕 AGREGAR SOLO ESTO - Enviar al canal admin también
#             admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
#             admin_channel_id = admin_config.get('admin_channel_id')
            
#             if admin_channel_id:
#                 await self.bot.send_message(
#                     chat_id=admin_channel_id,
#                     text=admin_message,
#                     parse_mode='HTML',
#                     reply_markup=reply_markup
#                 )
            
#             self.logger.info(f"Administrator notified about {giveaway_type} winner: {winner['telegram_id']} (@{username})")
            
#         except Exception as e:
#             self.logger.error(f"Error notifying administrator about {giveaway_type} winner: {e}")

    async def _notify_admin_winner(self, winner, total_participants, giveaway_type=None, prize_amount=None):
        """🔄 ENHANCED: Notify Main Administrator by name"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        if prize_amount is None:
            prize_amount = self.get_prize_amount(giveaway_type)
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            
            if username:
                winner_display = f"@{username}"
                command_identifier = username
            else:
                winner_display = f"{first_name} (No username)"
                command_identifier = winner['telegram_id']
            
            # 🆕 OBTENER admin principal por nombre "Main Administrator"
            permission_manager = None
            try:
                if hasattr(self.bot, 'application') and hasattr(self.bot.application, 'bot_data'):
                    permission_manager = self.bot.application.bot_data.get('permission_manager')
            except:
                pass
            
            main_admin_id = None
            if permission_manager:
                main_admin_id = permission_manager.get_main_admin_id()
            
            # Fallback al config si no encuentra "Main Administrator"
            if not main_admin_id:
                main_admin_id = self.admin_id
            
            # 🎯 MENSAJE PERSONAL al Main Administrator
            personal_message = f"""📱 <b>PERSONAL NOTIFICATION - {giveaway_type.upper()}</b>

    🎉 <b>Winner Selected:</b> {first_name} ({winner_display})
    💰 <b>Prize:</b> ${prize_amount} USD
    📊 <b>VFX MT5 Account:</b> <code>{winner['mt5_account']}</code>
    🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
    👥 <b>Total participants:</b> {total_participants}
    📅 <b>Date:</b> {today}

    ℹ️ <b>Next Steps:</b>
    1️⃣ Admin channel has been notified for payment confirmation
    2️⃣ Authorized payment admins will handle the transfer
    3️⃣ You will receive confirmation when payment is completed

    💡 <b>Status:</b> Winner selected, awaiting payment confirmation"""

            await self.bot.send_message(
                chat_id=main_admin_id,  # 🎯 Tu cuenta profesional (Main Administrator)
                text=personal_message,
                parse_mode='HTML'
            )
            
            # 🎯 MENSAJE AL CANAL de administradores con botón
            admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
            admin_channel_id = admin_config.get('admin_channel_id')
            
            if admin_channel_id:
                channel_message = f"""🔔 <b>{giveaway_type.upper()} WINNER - PAYMENT CONFIRMATION NEEDED</b>

    🎯 <b>Winner:</b> {first_name} ({winner_display})
    💰 <b>Prize:</b> ${prize_amount} USD
    📊 <b>VFX MT5 Account:</b> <code>{winner['mt5_account']}</code>
    🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
    👥 <b>Participants:</b> {total_participants}

    ⚠️ <b>ACTION REQUIRED:</b>
    💸 Transfer ${prize_amount} USD to VFX MT5 account: <code>{winner['mt5_account']}</code>
    ✅ Press button below after completing transfer

    🎯 <b>Authorized for payment confirmation:</b>
    - PAYMENT_SPECIALIST level admins
    - FULL_ADMIN level admins"""

                # Create confirmation button
                button_text = f"✅ Confirm ${prize_amount} Payment to {first_name}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await self.bot.send_message(
                    chat_id=admin_channel_id,
                    text=channel_message,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            
            self.logger.info(f"Winner notifications sent: Main Administrator ({main_admin_id}) + admin channel")
            
        except Exception as e:
            self.logger.error(f"Error notifying winner for {giveaway_type}: {e}")
    
    # @require_giveaway_lock()
    async def confirm_payment_and_announce(self, winner_telegram_id, confirmed_by_admin_id, giveaway_type=None):
        """🔄 ENHANCED: Confirm payment and announce with type awareness + CONCURRENCY PROTECTION"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # 🆕 PROTECCIÓN ADICIONAL CONTRA CONCURRENCIA
        safety_manager = None
        try:
            # Intentar obtener safety manager del contexto si está disponible
            # import asyncio
            current_task = asyncio.current_task()
            if hasattr(current_task, 'context') and hasattr(current_task.context, 'bot_data'):
                safety_manager = current_task.context.bot_data.get('safety_manager')
        except:
            pass
        
        if safety_manager:
            try:
                async with safety_manager.acquire_payment_lock(str(winner_telegram_id), giveaway_type):
                    return await self._execute_payment_confirmation(winner_telegram_id, confirmed_by_admin_id, giveaway_type)
            except asyncio.TimeoutError:
                # Si hay timeout, intentar sin lock como fallback
                self.logger.warning(f"Payment lock timeout for {winner_telegram_id}, proceeding without lock")
                return await self._execute_payment_confirmation(winner_telegram_id, confirmed_by_admin_id, giveaway_type)
        else:
            # Fallback sin safety manager
            self.logger.warning(f"Payment lock timeout for {winner_telegram_id}, proceeding without lock")
            return await self._execute_payment_confirmation(winner_telegram_id, confirmed_by_admin_id, giveaway_type)
    
    async def _execute_payment_confirmation(self, winner_telegram_id, confirmed_by_admin_id, giveaway_type=None):
        """
        🆕 NEW: Lógica completa de confirmación de pago extraída para protección
        Esta función contiene toda la implementación original de confirm_payment_and_announce
        """
        if giveaway_type is None:
            giveaway_type = self.giveaway_type

        # 🔒 SIMPLE CONCURRENCY CHECK
        operation_key = f"payment_{giveaway_type}_{winner_telegram_id}"
        
        if not hasattr(self, '_active_payments'):
            self._active_payments = set()
        # 🔧 ENHANCED: Check with timeout and forced cleanup
        if operation_key in self._active_payments:
            # Check if this is a stale lock (older than 30 seconds)
            if not hasattr(self, '_payment_timestamps'):
                self._payment_timestamps = {}
            
            # import time
            current_time = time.time()
            lock_time = self._payment_timestamps.get(operation_key, current_time)
            
            if current_time - lock_time > 30:  # 30 second timeout
                print(f"🧹 DEBUG: Cleaning stale payment lock for {operation_key}")
                self._active_payments.discard(operation_key)
                self._payment_timestamps.pop(operation_key, None)
            else:
                return False, "Payment confirmation already in progress"
        
        # Mark as active with timestamp
        self._active_payments.add(operation_key)
        if not hasattr(self, '_payment_timestamps'):
            self._payment_timestamps = {}
        self._payment_timestamps[operation_key] = time.time()
        
        try:
            print(f"🔍 DEBUG: ===== STARTING {giveaway_type.upper()} PAYMENT CONFIRMATION =====")
            print(f"🔍 DEBUG: Winner ID: {winner_telegram_id}")
            print(f"🔍 DEBUG: Confirmed by admin: {confirmed_by_admin_id}")
            
            # 1. Find pending winner data
            print(f"🔍 DEBUG: Step 1 - Finding winner data...")
            winner_data = self._get_pending_winner_data(winner_telegram_id, giveaway_type)
            if not winner_data:
                print(f"❌ DEBUG: No pending {giveaway_type} winner found with ID {winner_telegram_id}")
                return False, f"No pending {giveaway_type} winner found or already processed"
            
            print(f"✅ DEBUG: {giveaway_type.title()} winner found: {winner_data['first_name']} (MT5: {winner_data['mt5_account']})")
            
            # 2. Update status to payment_confirmed
            print(f"🔍 DEBUG: Step 2 - Updating status...")
            update_success = self._update_winner_status(winner_telegram_id, "payment_confirmed", confirmed_by_admin_id, giveaway_type)
            if not update_success:
                print(f"❌ DEBUG: ERROR updating {giveaway_type} winner status {winner_telegram_id}")
                return False, f"Error updating {giveaway_type} winner status"
            
            print(f"✅ DEBUG: {giveaway_type.title()} status updated successfully")
            
            # 3. Save to definitive winners history
            print(f"🔍 DEBUG: Step 3 - Saving to definitive history...")
            self._save_confirmed_winner(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} winner saved to definitive history")
            
            # 4. Public announcement
            print(f"🔍 DEBUG: Step 4 - Public announcement...")
            await self._announce_winner_public(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} public announcement sent")
            
            # 5. Private congratulation
            print(f"🔍 DEBUG: Step 5 - Private congratulation...")
            await self._congratulate_winner_private(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} private congratulation sent")

            # 🆕 SOLO AGREGAR ESTAS 2 LÍNEAS:
            # 6. Notify main admin of completion
            permission_manager = None
            try:
                if hasattr(self.bot, 'application') and hasattr(self.bot.application, 'bot_data'):
                    permission_manager = self.bot.application.bot_data.get('permission_manager')
            except:
                pass

            main_admin_id = None
            if permission_manager:
                main_admin_id = permission_manager.get_main_admin_id()  # Busca "Main Administrator"

            if not main_admin_id:
                main_admin_id = self.admin_id  # fallback

            completion_msg = f"✅ {giveaway_type.title()} payment confirmed by admin {confirmed_by_admin_id}. Winner announced and congratulated."
            await self.bot.send_message(chat_id=main_admin_id, text=completion_msg)  # 🎯 Ahora a tu cuenta profesional

            # 7. Notify admin channel of completion
            admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
            admin_channel_id = admin_config.get('admin_channel_id')
            if admin_channel_id:
                await self.bot.send_message(chat_id=admin_channel_id, text=completion_msg)
            
            print(f"🔍 DEBUG: ===== {giveaway_type.upper()} CONFIRMATION COMPLETED =====")
            return True, f"{giveaway_type.title()} payment confirmed and winner announced"
            
        except Exception as e:
            self.logger.error(f"Error confirming {giveaway_type} payment: {e}")
            print(f"❌ DEBUG: EXCEPTION in {giveaway_type} payment confirmation: {e}")
            
            return False, f"Error: {e}"
        finally:
            # 🆕 CRITICAL: Always clean up the lock in finally block
            try:
                self._active_payments.discard(operation_key)
                if hasattr(self, '_payment_timestamps'):
                    self._payment_timestamps.pop(operation_key, None)
                print(f"🧹 DEBUG: Cleaned up payment lock for {operation_key}")
            except Exception as cleanup_error:
                print(f"⚠️ DEBUG: Error cleaning payment lock: {cleanup_error}")
    
    async def _announce_winner_public(self, winner_data, giveaway_type=None):
        """🔄 MODIFIED: Announce winner with type-specific message"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            username = winner_data.get('username', '')
            first_name = winner_data.get('first_name', 'Winner').strip()
            # 🐛 BUGFIX: Improved username handling
            if username:
                if not username.startswith('@'):
                    winner_display = f"@{username}"
                else:
                    winner_display = username
            else:
                # Use first name if no username
                winner_display = first_name
            
            # Get participant count for this giveaway type
            total_participants = self._get_period_participants_count(giveaway_type)
            prize = self.get_prize_amount(giveaway_type)
            
            message = self.messages.get("winner_announcement", f"{giveaway_type.upper()} 🏆 Winner announcement!").format(
                username=winner_display,
                prize=prize,
                account=winner_data['mt5_account'],
                total_participants=total_participants
            )
            
            await self.bot.send_message(
                chat_id=self.channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            self.logger.info(f"{giveaway_type.title()} winner announced publicly: {winner_data['telegram_id']}")
            
        except Exception as e:
            self.logger.error(f"Error announcing {giveaway_type} winner: {e}")
            # 🆕 NEW: Simple fallback if template fails
            try:
                fallback_message = f"🏆 {giveaway_type.upper()} WINNER: {winner_data.get('first_name', 'Winner')} won ${self.get_prize_amount(giveaway_type)} USD!"
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=fallback_message
                )
                self.logger.info(f"Fallback {giveaway_type} announcement sent")
            except Exception as fallback_error:
                self.logger.error(f"Even fallback announcement failed: {fallback_error}")
    
    async def _congratulate_winner_private(self, winner_data, giveaway_type=None):
        """🔄 MODIFIED: Send type-specific private congratulation"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            # Get admin username
            admin_username = await self._get_admin_username()
            prize = self.get_prize_amount(giveaway_type)
            
            congratulation_message = self.messages.get("winner_private_congratulation", "Congratulations!").format(
                prize=prize,
                account=winner_data['mt5_account']
            )
            
            # Add admin contact info
            if admin_username:
                congratulation_message += f"\n\n📞 <b>To confirm receipt:</b>\nContact administrator: @{admin_username}"
            else:
                congratulation_message += f"\n\n📞 <b>To confirm receipt:</b>\nReply to this message with confirmation and photo."
            
            await self.bot.send_message(
                chat_id=winner_data['telegram_id'],
                text=congratulation_message,
                parse_mode='HTML'
            )
            
            self.logger.info(f"Private congratulation sent to {giveaway_type} winner: {winner_data['telegram_id']}")
            
        except Exception as e:
            self.logger.error(f"Error sending {giveaway_type} private congratulation: {e}")

    async def _get_admin_username(self):
        """✅ ORIGINAL: Get administrator username (no changes needed)"""
        try:
            admin_info = await self.bot.get_chat(self.admin_id)
            return admin_info.username
        except Exception as e:
            self.logger.error(f"Error getting admin info: {e}")
            return None

    # ================== PENDING WINNERS MANAGEMENT ==================
    
    def _save_winner_pending_payment(self, winner, giveaway_type=None, prize_amount=None):
        """🔄 MODIFIED: Save winner with type and prize information"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        if prize_amount is None:
            prize_amount = self.get_prize_amount(giveaway_type)
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            telegram_id = winner['telegram_id']
            
            print(f"💾 DEBUG: Saving {giveaway_type} winner {telegram_id} with prize ${prize_amount}")
            
            pending_file = self.get_file_paths(giveaway_type)['pending_winners']
            
            # Check if already exists as pending today
            if os.path.exists(pending_file):
                with open(pending_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['telegram_id'] == str(telegram_id) and 
                            row['date'] == today and 
                            row['status'] == 'pending_payment' and
                            row.get('giveaway_type', 'daily') == giveaway_type):
                            print(f"⚠️ DEBUG: {giveaway_type.title()} winner {telegram_id} already exists as pending today")
                            return
            
            # Save with giveaway type
            with open(pending_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    today,
                    telegram_id,
                    winner.get('username', ''),
                    winner.get('first_name', ''),
                    winner['mt5_account'],
                    prize_amount,
                    'pending_payment',
                    now,
                    '',  # confirmed_time empty
                    '',  # confirmed_by empty
                    giveaway_type  # giveaway type
                ])
                
            print(f"✅ DEBUG: {giveaway_type.title()} winner {telegram_id} saved as pending payment")
            
        except Exception as e:
            self.logger.error(f"Error saving {giveaway_type} pending winner: {e}")
    
    def _get_pending_winner_data(self, telegram_id, giveaway_type=None):
        """🔄 MODIFIED: Get pending winner data for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            pending_file = self.get_file_paths(giveaway_type)['pending_winners']
            
            if not os.path.exists(pending_file):
                return None
                
            with open(pending_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['telegram_id'] == str(telegram_id) and 
                        row['status'] == 'pending_payment' and
                        row.get('giveaway_type', 'daily') == giveaway_type):
                        return row
            return None
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} pending winner data: {e}")
            return None
    
    # @require_file_safety()
    # def _update_winner_status(self, telegram_id, new_status, confirmed_by_admin_id, giveaway_type=None):
    #     """🔄 ENHANCED: Update winner status for specific type + FILE PROTECTION"""

    #     if giveaway_type is None:
    #         giveaway_type = self.giveaway_type
    #     with self._file_lock:
    #         try:
    #             print(f"🔍 DEBUG: Updating {giveaway_type} status for {telegram_id}")
                
    #             pending_file = self.get_file_paths(giveaway_type)['pending_winners']
                
    #             if not os.path.exists(pending_file):
    #                 print(f"❌ DEBUG: {giveaway_type.title()} file does not exist: {pending_file}")
    #                 return False
                
    #             # 🆕 VERIFICACIÓN ADICIONAL DE ESTADO ANTES DE MODIFICAR
    #             # Verificar que el ganador aún esté en estado 'pending_payment'
    #             current_status = self._get_winner_current_status(telegram_id, giveaway_type)
    #             if current_status != 'pending_payment':
    #                 print(f"⚠️ DEBUG: Winner {telegram_id} is not in pending_payment status (current: {current_status})")
    #                 return False
                
    #             # Backup original file
    #             backup_file = f"{pending_file}.backup"
    #             import shutil
    #             shutil.copy2(pending_file, backup_file)
                
    #             rows = []
    #             updated = False
    #             target_found = False
                
    #             # Read all rows
    #             with open(pending_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['telegram_id'] == str(telegram_id) and
    #                         row.get('giveaway_type', 'daily') == giveaway_type):
    #                         target_found = True
                            
    #                         if row['status'] == 'pending_payment':
    #                             # Update status
    #                             row['status'] = new_status
    #                             row['confirmed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #                             row['confirmed_by'] = str(confirmed_by_admin_id)
    #                             updated = True
    #                             print(f"✅ DEBUG: {giveaway_type.title()} status updated to '{new_status}'")
    #                         else:
    #                             print(f"⚠️ DEBUG: Winner {telegram_id} status was '{row['status']}', not 'pending_payment'")
                        
    #                     rows.append(row)
                
    #             if not target_found:
    #                 print(f"❌ DEBUG: {giveaway_type.title()} winner {telegram_id} NOT found")
    #                 return False
                
    #             if not updated:
    #                 print(f"❌ DEBUG: {giveaway_type.title()} status was not 'pending_payment'")
    #                 return False
                
    #             # Write updated file
    #             temp_file = f"{pending_file}.temp"
    #             with open(temp_file, 'w', newline='', encoding='utf-8') as f:
    #                 fieldnames = ['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type']
    #                 writer = csv.DictWriter(f, fieldnames=fieldnames)
    #                 writer.writeheader()
    #                 writer.writerows(rows)
                
    #             # Replace original file
    #             os.replace(temp_file, pending_file)
    #             print(f"✅ DEBUG: {giveaway_type.title()} CSV file updated successfully")
                
    #             return True
                
    #         except Exception as e:
    #             self.logger.error(f"Error updating {giveaway_type} winner status: {e}")
    #             return False

    def _update_winner_status(self, telegram_id, new_status, confirmed_by_admin_id, giveaway_type=None):
        """🔄 ENHANCED: Update status and remove confirmed winners from pending"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        with self._file_lock:
            try:
                print(f"🔍 DEBUG: Updating {giveaway_type} status for {telegram_id} to {new_status}")
                
                pending_file = self.get_file_paths(giveaway_type)['pending_winners']
                
                if not os.path.exists(pending_file):
                    print(f"❌ DEBUG: {giveaway_type.title()} file does not exist: {pending_file}")
                    return False
                
                # 🆕 VERIFICACIÓN DE ESTADO ACTUAL
                current_status = self._get_winner_current_status(telegram_id, giveaway_type)
                print(f"🔍 DEBUG: Current status for {telegram_id}: {current_status}")
                
                if current_status == 'payment_confirmed':
                    print(f"✅ DEBUG: Winner {telegram_id} already confirmed, removing from pending")
                    # 🆕 YA CONFIRMADO - SOLO REMOVER
                    return self._remove_winner_from_pending(telegram_id, giveaway_type)
                elif current_status != 'pending_payment':
                    print(f"⚠️ DEBUG: Winner {telegram_id} in unexpected status: {current_status}")
                    return False
                
                # Backup original file
                backup_file = f"{pending_file}.backup"
                import shutil
                shutil.copy2(pending_file, backup_file)
                
                rows = []
                updated = False
                target_found = False
                
                # Read all rows
                with open(pending_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['telegram_id'] == str(telegram_id) and
                            row.get('giveaway_type', 'daily') == giveaway_type and
                            row['status'] == 'pending_payment'):
                            target_found = True
                            
                            if new_status == 'payment_confirmed':
                                # 🆕 DON'T add to rows - REMOVE the entry completely
                                print(f"🗑️ DEBUG: Removing confirmed {giveaway_type} winner {telegram_id}")
                                updated = True
                                continue  # Skip adding this row
                            else:
                                # Update status for other cases
                                row['status'] = new_status
                                row['confirmed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                row['confirmed_by'] = str(confirmed_by_admin_id)
                                updated = True
                        
                        rows.append(row)
                
                if not target_found:
                    print(f"❌ DEBUG: Winner {telegram_id} NOT found in pending")
                    return False
                
                if not updated:
                    print(f"❌ DEBUG: No updates made for {telegram_id}")
                    return False
                
                # Write updated file (without confirmed entries)
                temp_file = f"{pending_file}.temp"
                with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                
                # Replace original file
                os.replace(temp_file, pending_file)
                print(f"✅ DEBUG: {giveaway_type.title()} CSV file updated - confirmed entries removed")
                
                return True
                
            except Exception as e:
                self.logger.error(f"Error updating {giveaway_type} winner status: {e}")
                return False
            
    def _remove_winner_from_pending(self, telegram_id, giveaway_type=None):
        """🆕 NEW: Remove winner from pending list (already confirmed case)"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            pending_file = self.get_file_paths(giveaway_type)['pending_winners']
            
            if not os.path.exists(pending_file):
                return False
            
            rows = []
            removed = False
            
            with open(pending_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['telegram_id'] == str(telegram_id) and 
                        row.get('giveaway_type', 'daily') == giveaway_type):
                        print(f"🧹 DEBUG: Removing already confirmed {giveaway_type} winner {telegram_id}")
                        removed = True
                        continue  # Don't add to rows
                    rows.append(row)
            
            if removed:
                # Write file without the confirmed winner
                temp_file = f"{pending_file}.temp"
                with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                
                os.replace(temp_file, pending_file)
                print(f"✅ DEBUG: {giveaway_type.title()} confirmed winner removed from pending")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error removing {giveaway_type} winner from pending: {e}")
            return False

    def _save_confirmed_winner_record(self, winner_data, confirmed_by_admin_id, giveaway_type=None):
        """🆕 NEW: Save confirmation record when removing from pending"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            # Update the winner_data with confirmation info
            winner_data['status'] = 'payment_confirmed'
            winner_data['confirmed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            winner_data['confirmed_by'] = str(confirmed_by_admin_id)
            
            # Save to confirmed winners file (if you have this functionality)
            self._save_confirmed_winner(winner_data, giveaway_type)
            
            print(f"✅ DEBUG: Confirmed {giveaway_type} winner record saved for {winner_data['telegram_id']}")
            
        except Exception as e:
            self.logger.error(f"Error saving confirmed {giveaway_type} winner record: {e}")

    def _get_winner_current_status(self, telegram_id, giveaway_type=None):
        """🆕 NEW: Obtener estado actual del ganador para verificación"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            pending_file = self.get_file_paths(giveaway_type)['pending_winners']
            
            if not os.path.exists(pending_file):
                return None
            
            with open(pending_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['telegram_id'] == str(telegram_id) and 
                        row.get('giveaway_type', 'daily') == giveaway_type):
                        return row['status']
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} winner status: {e}")
            return None
    
    def get_pending_winners(self, giveaway_type=None):
        """🔄 MODIFIED: Get pending winners for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            pending_winners = []
            pending_file = self.get_file_paths(giveaway_type)['pending_winners']
            
            print(f"🔍 DEBUG: Getting {giveaway_type} pending winners from {pending_file}")
            
            if not os.path.exists(pending_file):
                print(f"🔍 DEBUG: {giveaway_type.title()} pending winners file does not exist")
                return pending_winners
            
            with open(pending_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                total_count = 0
                pending_count = 0
                
                for row in reader:
                    total_count += 1
                    
                    # Only include if status is exactly "pending_payment" and correct type
                    if (row['status'].strip() == 'pending_payment' and
                        row.get('giveaway_type', 'daily') == giveaway_type):
                        pending_winners.append(row)
                        pending_count += 1
                        print(f"✅ DEBUG: {giveaway_type.title()} winner {row['telegram_id']} added to pending list")
            
            print(f"🔍 DEBUG: Total {giveaway_type} records: {total_count}, Pending: {pending_count}")
            
            return pending_winners
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} pending winners: {e}")
            return []

    # 🆕 NEW: Multi-type pending winners function
    def get_all_pending_winners(self):
        """Get pending winners from all giveaway types"""
        try:
            all_pending = {}
            
            for giveaway_type in self.get_all_giveaway_types():
                pending = self.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
            
            return all_pending
            
        except Exception as e:
            self.logger.error(f"Error getting all pending winners: {e}")
            return {}

    async def _save_empty_period_to_history(self, giveaway_type=None):
        """🔄 MODIFIED: Save empty period for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            history_file = self.get_file_paths(giveaway_type)['history']
            
            with open(history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    today,
                    'NO_PARTICIPANTS',
                    'NO_PARTICIPANTS', 
                    'NO_PARTICIPANTS',
                    'NO_PARTICIPANTS',
                    0,
                    False,
                    0,
                    f'{giveaway_type}_empty'
                ])
            
            self.logger.info(f"{giveaway_type.title()} period without participants saved to history")
            
        except Exception as e:
            self.logger.error(f"Error saving empty {giveaway_type} period: {e}")

    # ================== DATA MANAGEMENT ==================
    # @require_file_safety()
    def _save_participant(self, participant_data, giveaway_type=None):
        """🔄 MODIFIED: Save participant to type-specific file"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        with self._file_lock:
            try:
                participants_file = self.get_file_paths(giveaway_type)['participants']

                print(f"🔍 DEBUG: Saving participant to: {participants_file}")
                print(f"🔍 DEBUG: Participant data: {participant_data}")

                # 🆕 VERIFICACIÓN ADICIONAL - No guardar duplicados del mismo día
                today = datetime.now().strftime('%Y-%m-%d')
                telegram_id = participant_data['telegram_id']
                
                # if os.path.exists(participants_file):
                #     with open(participants_file, 'r', encoding='utf-8') as f:
                #         reader = csv.DictReader(f)
                #         for row in reader:
                #             if (row['telegram_id'] == str(telegram_id) and 
                #                 row['registration_date'].startswith(today) and 
                #                 row['status'] == 'active'):
                #                 print(f"⚠️ DEBUG: User {telegram_id} already registered for {giveaway_type} today")
                #                 return  # Ya registrado, no duplicar

                import os
                directory = os.path.dirname(participants_file)
                if not os.path.exists(directory):
                    print(f"🔍 DEBUG: Creating directory: {directory}")
                    os.makedirs(directory, exist_ok=True)
                
                # 🆕 VERIFICAR SI ARCHIVO EXISTE Y TIENE HEADERS
                file_exists = os.path.exists(participants_file)
                print(f"🔍 DEBUG: File exists before write: {file_exists}")
                
                if not file_exists:
                    print(f"🔍 DEBUG: Creating new file with headers")
                    with open(participants_file, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
                
                with open(participants_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        participant_data['telegram_id'],
                        participant_data['username'],
                        participant_data['first_name'],
                        participant_data['mt5_account'],
                        participant_data['balance'],
                        participant_data['registration_date'],
                        participant_data['status']
                    ])

                print(f"✅ DEBUG: Participant saved successfully")
            
                # 🆕 VERIFICAR QUE SE GUARDÓ
                
                with open(participants_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"🔍 DEBUG: File size after write: {len(content)} characters")
                    print(f"🔍 DEBUG: File lines: {len(content.splitlines())}")
                self.logger.info(f"{giveaway_type.title()} participant {participant_data['telegram_id']} saved")
            except Exception as e:
                self.logger.error(f"Error saving {giveaway_type} participant: {e}")
    
    # @require_file_safety()
    def _save_confirmed_winner(self, winner_data, giveaway_type=None):
        """🔄 MODIFIED: Save confirmed winner to type-specific file"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        with self._file_lock:
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                winners_file = self.get_file_paths(giveaway_type)['winners']
                prize = self.get_prize_amount(giveaway_type)

                # Verificar si ya existe este ganador en winners definitivos
                if os.path.exists(winners_file):
                    with open(winners_file, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if (row['telegram_id'] == winner_data['telegram_id'] and 
                                row['date'] == today and
                                row.get('giveaway_type', giveaway_type) == giveaway_type):
                                print(f"⚠️ DEBUG: Winner {winner_data['telegram_id']} already exists in {giveaway_type} winners file")
                                return  # Ya existe, no duplicar
                
                with open(winners_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        today,
                        winner_data['telegram_id'],
                        winner_data['username'],
                        winner_data['mt5_account'],
                        prize,
                        giveaway_type
                    ])
                    
                self.logger.info(f"{giveaway_type.title()} confirmed winner saved: {winner_data['telegram_id']}")
                
            except Exception as e:
                self.logger.error(f"Error saving {giveaway_type} confirmed winner: {e}")
    
    def _get_eligible_participants(self, giveaway_type=None):
        """🔄 MODIFIED: Get eligible participants for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            eligible = []
            
            participants_file = self.get_file_paths(giveaway_type)['participants']
            print(f"🔍 DEBUG ELIGIBILITY: Checking {giveaway_type} participants")
            print(f"🔍 DEBUG ELIGIBILITY: File path: {participants_file}")
            print(f"🔍 DEBUG ELIGIBILITY: Today's date: {today}")
            print(f"🔍 DEBUG ELIGIBILITY: File exists: {os.path.exists(participants_file)}")
            
            if not os.path.exists(participants_file):
                print(f"❌ DEBUG ELIGIBILITY: File doesn't exist")
                return eligible
            
            # Check file content first
            with open(participants_file, 'r', encoding='utf-8') as f:
                content = f.read()
                print(f"🔍 DEBUG ELIGIBILITY: File size: {len(content)} characters")
                print(f"🔍 DEBUG ELIGIBILITY: File content preview:")
                print(f"🔍 DEBUG ELIGIBILITY: {repr(content[:500])}")

             # Now process participants
            total_rows = 0
            today_rows = 0
            active_rows = 0   
            # Get today's participants
            with open(participants_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total_rows += 1
                    print(f"🔍 DEBUG ELIGIBILITY: Row {total_rows}:")
                    print(f"   ID: '{row.get('telegram_id')}'")
                    print(f"   Date: '{row.get('registration_date')}'")
                    print(f"   Status: '{row.get('status')}'")
                    print(f"   MT5: '{row.get('mt5_account')}'")
                    
                    # Check each condition
                    date_match = row.get('registration_date', '').startswith(today)
                    status_match = row.get('status') == 'active'
                    
                    print(f"   Date match ({today}): {date_match}")
                    print(f"   Status match (active): {status_match}")
                    
                    if date_match:
                        today_rows += 1
                        
                    if status_match:
                        active_rows += 1
                    
                    if date_match and status_match:
                        print(f"✅ DEBUG ELIGIBILITY: Row {total_rows} is eligible")
                        eligible.append(row)
                    else:
                        print(f"❌ DEBUG ELIGIBILITY: Row {total_rows} NOT eligible")
            
            print(f"🔍 DEBUG ELIGIBILITY SUMMARY:")
            print(f"   Total rows: {total_rows}")
            print(f"   Today's rows: {today_rows}")
            print(f"   Active rows: {active_rows}")
            print(f"   Eligible before recent winners filter: {len(eligible)}")
            
            # Filter recent winners for this type
            recent_winners = self._get_recent_winners(giveaway_type)
            print(f"🔍 DEBUG ELIGIBILITY: Recent winners: {recent_winners}")
            eligible_before_filter = len(eligible)
            eligible = [p for p in eligible if p['telegram_id'] not in recent_winners]

            print(f"🔍 DEBUG ELIGIBILITY: Eligible after recent winners filter: {len(eligible)}")
            print(f"🔍 DEBUG ELIGIBILITY: Filtered out: {eligible_before_filter - len(eligible)}")
            
            if eligible:
                print(f"✅ DEBUG ELIGIBILITY: Final eligible participants:")
                for i, p in enumerate(eligible):
                    print(f"   {i+1}. ID: {p['telegram_id']}, MT5: {p['mt5_account']}")
            else:
                print(f"❌ DEBUG ELIGIBILITY: NO eligible participants found")
            
            # self.logger.info(f"Eligible participants for {giveaway_type}: {len(eligible)}")
            
            self.logger.info(f"Eligible participants for {giveaway_type}: {len(eligible)}")
            return eligible
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} eligible participants: {e}")
            return []
    
    def _get_recent_winners(self, giveaway_type=None):
        """🔄 MODIFIED: Get recent winners for specific type with type-specific cooldown"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            cooldown_days = self.get_cooldown_days(giveaway_type)
            cutoff_date = datetime.now() - timedelta(days=cooldown_days)
            recent_winners = set()
            
            winners_file = self.get_file_paths(giveaway_type)['winners']
            
            if os.path.exists(winners_file):
                with open(winners_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            win_date = datetime.strptime(row['date'], '%Y-%m-%d')
                            if win_date >= cutoff_date:
                                recent_winners.add(row['telegram_id'])
                        except ValueError:
                            continue
            
            return recent_winners
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} recent winners: {e}")
            return set()
    
    def _select_winner(self, participants):
        """✅ ORIGINAL: Select random winner (no changes needed)"""
        if not participants:
            return None
        return random.choice(participants)
    
    def _get_period_participants_count(self, giveaway_type=None):
        """🔄 MODIFIED: Get participant count for specific period/type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            count = 0
            
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            if os.path.exists(participants_file):
                with open(participants_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if (row['registration_date'].startswith(today) and 
                            row['status'] == 'active'):
                            count += 1
            return count
        except Exception as e:
            self.logger.error(f"Error counting {giveaway_type} participants: {e}")
            return 0
    
    async def _save_period_results_to_history(self, winner_data, giveaway_type=None):
        """🔄 MODIFIED: Save period results for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            winner_id = winner_data['telegram_id'] if winner_data else None
            
            participants_file = self.get_file_paths(giveaway_type)['participants']
            history_file = self.get_file_paths(giveaway_type)['history']
            
            # Read all participants for this period
            period_participants = []
            if os.path.exists(participants_file):
                with open(participants_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['status'] == 'active':
                            period_participants.append(row)
            
            if not period_participants:
                self.logger.info(f"No {giveaway_type} participants to save to history")
                return
            
            # Save each participant to permanent history
            prize = self.get_prize_amount(giveaway_type)
            
            with open(history_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                for participant in period_participants:
                    # Determine if won
                    won_prize = participant['telegram_id'] == winner_id
                    prize_amount = prize if won_prize else 0
                    
                    writer.writerow([
                        today,  # date
                        participant['telegram_id'],
                        participant['username'],
                        participant['first_name'],
                        participant['mt5_account'],
                        participant['balance'],
                        won_prize,  # won_prize (True/False)
                        prize_amount,  # prize_amount
                        giveaway_type  # giveaway_type
                    ])
            
            self.logger.info(f"Saved {len(period_participants)} {giveaway_type} participants to permanent history")
            
        except Exception as e:
            self.logger.error(f"Error saving {giveaway_type} period results to history: {e}")

    def _prepare_for_next_period(self, giveaway_type=None):
        """🔄 MODIFIED: Clean participants file for next period"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            # Recreate empty participants file
            with open(participants_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
            
            period_names = {
                'daily': 'next day',
                'weekly': 'next week', 
                'monthly': 'next month'
            }
            
            period_name = period_names.get(giveaway_type, 'next period')
            self.logger.info(f"{giveaway_type.title()} participants file prepared for {period_name}")
            
            print(f"🧹 DEBUG: {giveaway_type.title()} participants cleaned")
            print(f"📁 DEBUG: File {participants_file} is now empty")
            
        except Exception as e:
            self.logger.error(f"Error preparing {giveaway_type} file for next period: {e}")

    # 🆕 NEW: Multi-type cleanup function
    def cleanup_old_participants(self, giveaway_type=None, days=1):
        """Clean old participants for specific type or all types"""
        try:
            if giveaway_type is None:
                # Clean all types
                for gt in self.get_all_giveaway_types():
                    self._prepare_for_next_period(gt)
                self.logger.info("All giveaway types cleaned")
            else:
                self._prepare_for_next_period(giveaway_type)
                self.logger.info(f"{giveaway_type.title()} participants cleaned")
            
        except Exception as e:
            self.logger.error(f"Error in cleanup: {e}")

    def debug_participant_cleanup(self, giveaway_type=None):
        """🔄 MODIFIED: Debug cleanup for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            print(f"🔍 DEBUG: Verifying {giveaway_type} file status...")
            
            file_paths = self.get_file_paths(giveaway_type)
            
            # Count current participants
            current_participants = 0
            if os.path.exists(file_paths['participants']):
                with open(file_paths['participants'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    current_participants = len(list(reader))
            
            # Count history
            total_history = 0
            if os.path.exists(file_paths['history']):
                with open(file_paths['history'], 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    total_history = len(list(reader))
            
            # Count pending
            pending_count = len(self.get_pending_winners(giveaway_type))
            
            print(f"📊 DEBUG: {giveaway_type.title()} status:")
            print(f"   Current participants: {current_participants}")
            print(f"   Total history: {total_history}")
            print(f"   Pending winners: {pending_count}")
            
            return {
                'giveaway_type': giveaway_type,
                'current_participants': current_participants,
                'total_history': total_history,
                'pending_winners': pending_count
            }
            
        except Exception as e:
            print(f"❌ DEBUG: Error verifying {giveaway_type} files: {e}")
            return None

    # ================== STATISTICS AND ANALYTICS ==================
    
    def get_stats(self, giveaway_type=None):
        """🔄 MODIFIED: Get statistics for specific type or current type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Count today's participants for this type
            today_participants = self._get_period_participants_count(giveaway_type)
            
            # Count total winners for this type
            total_winners = 0
            winners_file = self.get_file_paths(giveaway_type)['winners']
            if os.path.exists(winners_file):
                with open(winners_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    total_winners = sum(1 for row in reader)
            
            # Count unique historical users for this type
            unique_users = set()
            history_file = self.get_file_paths(giveaway_type)['history']
            if os.path.exists(history_file):
                with open(history_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['telegram_id'] != 'NO_PARTICIPANTS':
                            unique_users.add(row['telegram_id'])
            
            prize = self.get_prize_amount(giveaway_type)
            
            return {
                'giveaway_type': giveaway_type,
                'today_participants': today_participants,
                'total_participants': len(unique_users),
                'total_winners': total_winners,
                'total_prize_distributed': total_winners * prize,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} statistics: {e}")
            return {}

    # 🆕 NEW: Multi-type statistics
    def get_stats_all_types(self):
        """Get combined statistics for all giveaway types"""
        try:
            all_stats = {}
            combined_stats = {
                'total_participants_all': 0,
                'total_winners_all': 0,
                'total_prize_distributed_all': 0,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_stats(giveaway_type)
                all_stats[giveaway_type] = stats
                
                # Add to combined totals
                combined_stats['total_participants_all'] += stats.get('total_participants', 0)
                combined_stats['total_winners_all'] += stats.get('total_winners', 0)
                combined_stats['total_prize_distributed_all'] += stats.get('total_prize_distributed', 0)
            
            return {
                'by_type': all_stats,
                'combined': combined_stats
            }
            
        except Exception as e:
            self.logger.error(f"Error getting all types statistics: {e}")
            return {}
        
    def get_user_account_history(self, user_id, giveaway_type=None):
        """🔄 MODIFIED: Get user account history for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            complete_history = self.get_user_complete_history(user_id, giveaway_type)
            
            account_history = []
            for entry in complete_history:
                account_history.append({
                    'mt5_account': entry['mt5_account'],
                    'date': entry['date'],
                    'balance': entry['balance'],
                    'giveaway_type': entry['giveaway_type']
                })
            
            return account_history
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} user account history: {e}")
            return []
    
    def get_user_complete_history(self, user_id, giveaway_type=None):
        """🔄 MODIFIED: Get complete user history for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            user_history = []
            history_file = self.get_file_paths(giveaway_type)['history']
            
            if not os.path.exists(history_file):
                return user_history
            
            with open(history_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['telegram_id'] == str(user_id) and 
                        row['telegram_id'] != 'NO_PARTICIPANTS'):
                        user_history.append({
                            'date': row['date'],
                            'mt5_account': row['mt5_account'],
                            'balance': row['balance'],
                            'won_prize': row['won_prize'].lower() == 'true',
                            'prize_amount': float(row['prize_amount']) if row['prize_amount'] else 0,
                            'giveaway_type': row.get('giveaway_type', giveaway_type)
                        })
            
            # Sort by date (most recent first)
            user_history.sort(key=lambda x: x['date'], reverse=True)
            return user_history
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} complete history: {e}")
            return []

    # 🆕 NEW: Cross-type user analysis
    def get_user_multi_type_stats(self, user_id):
        """Get user statistics across all giveaway types"""
        try:
            multi_stats = {}
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_user_participation_stats(user_id, giveaway_type)
                multi_stats[giveaway_type] = stats
            
            # Calculate combined stats
            combined = {
                'total_participations_all': sum(stats['total_participations'] for stats in multi_stats.values()),
                'total_wins_all': sum(stats['total_wins'] for stats in multi_stats.values()),
                'total_prize_won_all': sum(stats['total_prize_won'] for stats in multi_stats.values()),
                'unique_accounts_all': len(set().union(*[stats['accounts_used'] for stats in multi_stats.values()])),
                'active_types': [gt for gt, stats in multi_stats.items() if stats['total_participations'] > 0]
            }
            
            return {
                'by_type': multi_stats,
                'combined': combined
            }
            
        except Exception as e:
            self.logger.error(f"Error getting multi-type user stats: {e}")
            return {}

    def get_user_participation_stats(self, user_id, giveaway_type=None):
        """🔄 MODIFIED: Get participation stats for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            complete_history = self.get_user_complete_history(user_id, giveaway_type)
            
            if not complete_history:
                return {
                    'giveaway_type': giveaway_type,
                    'total_participations': 0,
                    'unique_accounts': 0,
                    'total_wins': 0,
                    'total_prize_won': 0,
                    'first_participation': None,
                    'last_participation': None,
                    'accounts_used': [],
                    'win_rate': 0,
                    'average_balance': 0
                }
            
            unique_accounts = list(set(entry['mt5_account'] for entry in complete_history))
            total_wins = sum(1 for entry in complete_history if entry['won_prize'])
            total_prize = sum(entry['prize_amount'] for entry in complete_history)
            win_rate = (total_wins / len(complete_history)) * 100 if complete_history else 0
            
            # Calculate average balance
            balances = [float(entry['balance']) for entry in complete_history if entry['balance']]
            average_balance = sum(balances) / len(balances) if balances else 0
            
            return {
                'giveaway_type': giveaway_type,
                'total_participations': len(complete_history),
                'unique_accounts': len(unique_accounts),
                'total_wins': total_wins,
                'total_prize_won': total_prize,
                'first_participation': complete_history[-1]['date'],  # Oldest
                'last_participation': complete_history[0]['date'],   # Most recent
                'accounts_used': unique_accounts,
                'win_rate': round(win_rate, 2),
                'average_balance': round(average_balance, 2)
            }
            
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} participation stats: {e}")
            return None

    def backup_history_file(self, giveaway_type=None):
        """🔄 MODIFIED: Create backup for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            history_file = self.get_file_paths(giveaway_type)['history']
            
            if not os.path.exists(history_file):
                return False
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"{history_file}.backup_{timestamp}"
            
            import shutil
            shutil.copy2(history_file, backup_name)
            
            self.logger.info(f"{giveaway_type.title()} history backup created: {backup_name}")
            return backup_name
            
        except Exception as e:
            self.logger.error(f"Error creating {giveaway_type} backup: {e}")
            return False

    # 🆕 NEW: Advanced analytics functions (placeholder for complex analysis)
    def get_giveaway_analytics(self, days_back=30, giveaway_type=None):
        """🔄 MODIFIED: Get analytics for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: This would be a complex function requiring detailed implementation
        # For now, returning basic structure
        try:
            return {
                'giveaway_type': giveaway_type,
                'period_days': days_back,
                'message': 'Advanced analytics implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} analytics: {e}")
            return {}

    def get_account_ownership_report(self, giveaway_type=None):
        """🔄 MODIFIED: Get account ownership report for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'message': 'Account ownership report implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} account report: {e}")
            return {}

    def get_top_participants_report(self, limit=10, giveaway_type=None):
        """🔄 MODIFIED: Get top participants for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'limit': limit,
                'message': 'Top participants report implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} top participants: {e}")
            return []

    def get_revenue_impact_analysis(self, giveaway_type=None):
        """🔄 MODIFIED: Get revenue analysis for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        # Note: Complex function requiring detailed implementation
        try:
            return {
                'giveaway_type': giveaway_type,
                'message': 'Revenue impact analysis implementation needed'
            }
        except Exception as e:
            self.logger.error(f"Error getting {giveaway_type} revenue analysis: {e}")
            return {}

    # 🆕 NEW: Cross-type comparison and analysis
    def get_cross_type_analytics(self):
        """Compare performance across all giveaway types"""
        try:
            comparison = {}
            
            for giveaway_type in self.get_all_giveaway_types():
                stats = self.get_stats(giveaway_type)
                comparison[giveaway_type] = {
                    'participants': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'prizes_distributed': stats.get('total_prize_distributed', 0),
                    'conversion_rate': (stats.get('total_winners', 0) / max(stats.get('total_participants', 1), 1)) * 100
                }
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error getting cross-type analytics: {e}")
            return {}

    def get_type_comparison_report(self):
        """Generate comparison report between giveaway types"""
        try:
            all_stats = self.get_stats_all_types()
            cross_analytics = self.get_cross_type_analytics()
            
            return {
                'stats_summary': all_stats,
                'performance_comparison': cross_analytics,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            self.logger.error(f"Error generating type comparison report: {e}")
            return {}  





























































































    