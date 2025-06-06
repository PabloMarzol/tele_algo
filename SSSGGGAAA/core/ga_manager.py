import csv
import json
import random
import calendar
from datetime import datetime, timedelta
import logging
import threading
import asyncio
import sys
import os

"""
Giveaway System Modules

Módulos especializados para el sistema de giveaways:
- FileManager: Gestión de archivos CSV
- MessageManager: Gestión de mensajes y templates
- ParticipationFlow: Flujo de participación de usuarios
- PaymentHandler: Gestión de pagos y anuncios de ganadores
- StatsManager: Estadísticas y reportes
"""

# Import módulos
import handlers.participation_flow as participation_flow
import handlers.payment_handler as payment_handler
from utils.file_manager import FileManager
from utils.message_manager import MessageManager
from utils.stats_manager import StatsManager


from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from utils.config_loader import ConfigLoader
from utils.async_manager import require_giveaway_lock, require_file_safety

__all__ = [
    'FileManager',
    'MessageManager', 
    'ParticipationFlow',
    'PaymentHandler',
    'StatsManager'
]
# Agregar la ruta del directorio padre para poder importar mysql
sys.path.append('../mySQL')



try:
    from mysql_manager import MySQLManager, get_mysql_connection
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    get_mysql_connection = None


class GiveawaySystem:
    """SOLO lógica de negocio core"""
    
    # ✅ CONSTRUCTOR Y CONFIGURACIÓN
    def __init__(self, bot, giveaway_type, config_file ='config.json'):
        """
        Initialize giveaway system with modular architecture
        
        Args:
            mt5_api: MT5 API client for account validation
            bot: Telegram bot instance
            giveaway_type: Type of giveaway ('daily', 'weekly', 'monthly')
            config_file: Path to JSON configuration file
        """
        # ✅ 1. CONFIGURACIÓN BÁSICA
        self.config_loader = ConfigLoader(config_file)
        
        self.bot = bot
        self.giveaway_type = giveaway_type
        
        # ✅ 2. CARGAR CONFIGURACIONES
        bot_config = self.config_loader.get_bot_config()
        self.GIVEAWAY_CONFIGS = self.config_loader.get_giveaway_configs()
        
        # ✅ 3. CONFIGURACIÓN DEL BOT
        self.channel_id = bot_config['channel_id']
        self.admin_id = bot_config['admin_id']
        self.admin_username = bot_config.get('admin_username', 'admin')
        
        # ✅ 4. CONFIGURACIÓN ESPECÍFICA DEL TIPO
        self.config = self.GIVEAWAY_CONFIGS[giveaway_type]
        self.min_balance = self.config['min_balance']
        self.daily_prize = self.config['prize']  # Keep for compatibility
        self.winner_cooldown_days = self.config['cooldown_days']
        
        # ✅ 5. CONFIGURACIÓN DE ARCHIVOS
        db_config = self.config_loader.get_database_config()
        base_path = db_config.get('base_path', './System_giveaway/data')
        self.data_dir = f"{base_path}/{giveaway_type}"
        
        # ✅ 6. CONFIGURACIÓN DE LOGGING
        self._setup_logging()
        
        # ✅ 7. CONFIGURACIÓN DE CONCURRENCIA
        self._file_lock = threading.Lock()
        self._active_payments = set()
        
        # ✅ 8. CONEXIÓN MYSQL
        self.mysql_db = get_mysql_connection() if MYSQL_AVAILABLE else None
        
        # ✅ 9. INICIALIZAR MÓDULOS
        self._initialize_modules()
        
        self.logger.info(f"{giveaway_type.upper()} Giveaway System initialized successfully")

    def _setup_logging(self):
        """Configurar sistema de logging"""
        logging_config = self.config_loader.get_logging_config()
        logging.basicConfig(
            level=getattr(logging, logging_config.get('level', 'INFO')),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(logging_config.get('file', 'giveaway_bot.log')),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(f'GiveawaySystem_{self.giveaway_type}')
    
    def _initialize_modules(self):
        """Inicializar todos los módulos especializados"""
        # Compartir referencias necesarias entre módulos
        shared_context = {
            'giveaway_system': self,
            'bot': self.bot,
            'logger': self.logger,
            'config': self.config,
            'config_loader': self.config_loader,
            'giveaway_type': self.giveaway_type,
            'data_dir': self.data_dir,
            'file_lock': self._file_lock
        }
        # 🏗️ FASE 2: Crear todos los módulos (sin referencias cruzadas)
        self.logger.info("Creating modules...")

        # Inicializar módulos
        self.file_manager = FileManager(shared_context)
        self.message_manager = MessageManager(shared_context)
        self.stats_manager = StatsManager(shared_context)

        # 🔗 FASE 3: Establecer referencias entre módulos
        self.logger.info("Setting up module references...")
        
        # StatsManager necesita: FileManager
        self.stats_manager.set_module_references(
            file_manager=self.file_manager
        )
        
        # 🎯Inicializar archivos y mensajes
        self.file_manager.initialize_files()
        self.message_manager.load_messages()

        self.logger.info("All modules initialized and references set")

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
        return self.GIVEAWAY_CONFIGS.get(giveaway_type, {})
    
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
    
    # verificar 
    def get_file_paths(self, giveaway_type=None):
        """Get file paths for specific giveaway type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        base_dir = f"./System_giveaway/data/{giveaway_type}"

        # db_config = self.config_loader.get_database_config()
        # base_path = db_config.get('base_path', './System_giveaway/data')
        # base_dir = f"{base_path}/{giveaway_type}"
        return {
            'participants': f"{base_dir}/participants.csv",
            'winners': f"{base_dir}/winners.csv",
            'history': f"{base_dir}/history.csv",
            'pending_winners': f"{base_dir}/pending_winners.csv"
        }
    
    async def send_invitation(self):
        return await participation_flow.send_invitation(self)

    def get_message(self, key, **kwargs):
        """DELEGATE TO: MessageManager"""
        return self.message_manager.get_message(key, **kwargs)
    
    def get_stats(self, giveaway_type=None):
        """DELEGATE TO: StatsManager"""
        return self.stats_manager.get_stats(giveaway_type)
    
    def get_user_participation_stats(self, user_id, giveaway_type=None):
        """DELEGATE TO: StatsManager"""
        return self.stats_manager.get_user_participation_stats(user_id, giveaway_type)



    # ✅ VALIDACIONES MT5 (Core Business Logic)
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
            self.logger.error(f"Error validating MT5 account {account_number}: {e}")
            return {
                'valid': False,
                'error_type': 'api_error',
                'message': f'Validation error: {str(e)}'
            }
    
    def validate_account_for_giveaway(self, account_number, user_id):
        """Complete validation including giveaway-specific rules"""
        
        # 1. Validación básica de cuenta MT5
        mt5_validation = self.validate_mt5_account(account_number)
        
        if not mt5_validation['valid']:
            return mt5_validation
        
        # 2. Verificar si la cuenta ya fue usada hoy por otro usuario
        account_used_today, other_user_id = self._is_account_already_used_today(account_number, self.giveaway_type)
        if account_used_today:
            return {
                'valid': False,
                'error_type': 'account_already_used_today',
                'message': f'Account already used today by another participant',
                'used_by': other_user_id
            }
        
        # 3. Verificar ownership histórico
        is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(account_number, user_id, self.giveaway_type)
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
            'message': 'Account validated for giveaway participation'
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

    
    
    # ✅ LÓGICA DE PARTICIPACIÓN (Core)
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
    
    
    
    # ✅ EJECUCIÓN DE SORTEOS (Core Business Logic)
    async def run_giveaway(self, giveaway_type=None, prize_amount=None, force_execution=False):
        """🔄 MODIFIED: Execute giveaway for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            # 🆕 GET SYSTEM MODE
            system_config = self.config_loader.get_all_config().get('system_mode', {})
            environment = system_config.get('environment', 'testing')
            mode_config = system_config.get(environment, {})
            
            # 🚨 PRODUCTION MODE VALIDATIONS
            if environment == 'production' and not force_execution:
                
                # 1️⃣ Check if already executed today
                if not mode_config.get('allow_multiple_draws_per_period', False):
                    today = datetime.now().strftime('%Y-%m-%d')
                    pending_winners = self.get_pending_winners(giveaway_type)
                    today_pending = [w for w in pending_winners if w.get('date', '').startswith(today)]
                    
                    if today_pending:
                        self.logger.warning(f"🚨 PRODUCTION: {giveaway_type} draw already executed today")
                        await self.bot.send_message(
                            chat_id=self.admin_id,
                            text=f"🚨 <b>PRODUCTION MODE RESTRICTION</b>\n\n"
                                f"❌ {giveaway_type.upper()} draw already executed today\n"
                                f"📅 Date: {today}\n"
                                f"👤 Existing winner: {today_pending[0].get('first_name', 'Unknown')}\n\n"
                                f"💡 <b>Production rule:</b> Only 1 draw per {giveaway_type} period allowed",
                            parse_mode='HTML'
                        )
                        return
                
                # 2️⃣ Check draw time window
                if not mode_config.get('bypass_draw_time_restrictions', False):
                    if not self.is_participation_window_open(giveaway_type):
                        next_draw = self.get_next_draw_time(giveaway_type)
                        self.logger.warning(f"🚨 PRODUCTION: {giveaway_type} draw outside time window")
                        await self.bot.send_message(
                            chat_id=self.admin_id,
                            text=f"🚨 <b>PRODUCTION MODE RESTRICTION</b>\n\n"
                                f"❌ {giveaway_type.upper()} draw outside scheduled window\n"
                                f"🕐 Next valid time: {next_draw.strftime('%Y-%m-%d %H:%M:%S')} London Time\n\n"
                                f"💡 <b>Production rule:</b> Draws only during participation hours",
                            parse_mode='HTML'
                        )
                        return
            
            # 🟢 TESTING MODE or PRODUCTION with FORCE
            elif environment == 'testing':
                self.logger.info(f"🧪 TESTING MODE: {giveaway_type} draw allowed anytime")
            
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
                await self.file_manager._save_empty_period_to_history(giveaway_type)
                message = self.get_message("no_eligible_participants")
                await self.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode='HTML'
                )
                
                # Clean up even without participants
                self.file_manager._prepare_for_next_period(giveaway_type)
                return
            
            print(f"👥 DEBUG: {len(eligible_participants)} eligible participants found for {giveaway_type}")
            
            # Select winner
            winner = self._select_winner(eligible_participants)
            
            if winner:
                print(f"🏆 DEBUG: Winner selected for {giveaway_type}: {winner['telegram_id']}")
                
                # 1. Save winner as pending payment
                self._save_winner_pending_payment(winner, giveaway_type, prize)
                
                # 2. Notify administrator
                await payment_handler._notify_admin_winner(winner, len(eligible_participants), giveaway_type, prize)
                
                # 3. Save period results to permanent history
                await self.file_manager._save_period_results_to_history(winner, giveaway_type)
                
                # 4. Prepare for next period
                self.file_manager._prepare_for_next_period(giveaway_type)
                
                self.logger.info(f"{period_name.title()} giveaway completed. Winner: {winner['telegram_id']}")
                print(f"✅ DEBUG: {giveaway_type} giveaway completed and participants cleaned")
            
        except Exception as e:
            self.logger.error(f"Error executing {giveaway_type} giveaway: {e}")
            raise

    def _get_eligible_participants(self, giveaway_type=None):
        """🔄 MODIFIED: Get eligible participants for specific type"""
        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            eligible = []
            
            participants_file = self.get_file_paths(giveaway_type)['participants']
            
            if not os.path.exists(participants_file):
                return eligible
            
            # Get today's participants
            with open(participants_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if (row['registration_date'].startswith(today) and 
                        row['status'] == 'active'):
                        eligible.append(row)
            
            # Filter recent winners for this type
            recent_winners = self._get_recent_winners(giveaway_type)
            eligible = [p for p in eligible if p['telegram_id'] not in recent_winners]
            
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

    



    # ✅ GESTIÓN DE DATOS (Core)
        
    def _save_participant(self, participant_data, giveaway_type=None):
        """DELEGATE TO: FileManager._save_participant - but keep for direct calls"""
        return self.file_manager._save_participant(participant_data, giveaway_type)
    
    def _save_confirmed_winner(self, winner_data, giveaway_type=None):
        """DELEGATE TO: FileManager._save_confirmed_winner"""
        return self.file_manager._save_confirmed_winner(winner_data, giveaway_type)
        

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
    def _update_winner_status(self, telegram_id, new_status, confirmed_by_admin_id, giveaway_type=None):
        """🔄 ENHANCED: Update winner status for specific type + FILE PROTECTION"""

        if giveaway_type is None:
            giveaway_type = self.giveaway_type
        with self._file_lock:
            try:
                self.logger.info(f"Updating {giveaway_type} status for {telegram_id} to {new_status}")
                
                pending_file = self.get_file_paths(giveaway_type)['pending_winners']
                
                if not os.path.exists(pending_file):
                    self.logger.error(f"{giveaway_type.title()} pending file does not exist: {pending_file}")
                    return False
                
                # 🆕 VERIFICACIÓN ADICIONAL DE ESTADO ANTES DE MODIFICAR
                # Verificar que el ganador aún esté en estado 'pending_payment'
                current_status = self._get_winner_current_status(telegram_id, giveaway_type)
                
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
                                # self.logger.info(f"{giveaway_type.title()} status updated to '{new_status}'")
                                updated = True
                                continue  # Skip adding this row
                            else:
                                # Update status for other cases
                                row['status'] = new_status
                                row['confirmed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                row['confirmed_by'] = str(confirmed_by_admin_id)
                                updated = True

                                
                                # self.logger.warning(f"Winner {telegram_id} status was '{row['status']}', not 'pending_payment'")
                        
                        rows.append(row)
                
                if not target_found:
                    self.logger.error(f"{giveaway_type.title()} winner {telegram_id} NOT found")
                    return False
                
                if not updated:
                    self.logger.error(f"{giveaway_type.title()} status was not 'pending_payment'")
                    return False
                
                # Write updated file
                temp_file = f"{pending_file}.temp"
                with open(temp_file, 'w', newline='', encoding='utf-8') as f:
                    fieldnames = ['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by', 'giveaway_type']
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
                
                # Replace original file
                os.replace(temp_file, pending_file)
                print(f"✅ DEBUG: {giveaway_type.title()} CSV file updated successfully - confirmed entries removed")
                
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

    
    
    # ✅ VENTANAS DE PARTICIPACION (Core Data)
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
    
    def get_next_draw_time(self, giveaway_type):
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
    
    def get_next_participation_window(self, giveaway_type):
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




    
        
    
        
    

    