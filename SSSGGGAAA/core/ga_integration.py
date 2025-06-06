"""
Multi-type giveaway integration system supporting daily, weekly, and monthly giveaways
Complete version with all buttons and panels working correctly for multiple types
"""


from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import os
import csv
import asyncio
from datetime import datetime, timedelta

from core.ga_manager import GiveawaySystem
from utils.config_loader import ConfigLoader
from utils.automation_manager import AutomationManager
import handlers.admin_commands as admin_commands
import handlers.callback_handlers as callback_handlers
import handlers.participation_flow as participation_flow
import handlers.payment_handler as payment_handler
import handlers.user_commands as user_commands
from utils.admin_permission import get_permission_manager
from utils.admin_permission import SystemAction



class MultiGiveawayIntegration:
    """🆕 NEW: Multi-type giveaway integration system"""
    
    def __init__(self, application, config_file="config.json"):
        """
        SIMPLIFIED: Solo inicializar lo esencial y delegar
        """
        # ===== CORE CONFIGURATION =====
        self.app = application
        
        self.config_loader = ConfigLoader(config_file)
        bot_config = self.config_loader.get_bot_config()
        
        self.channel_id = bot_config['channel_id']
        self.admin_id = bot_config['admin_id']
        self.admin_username = bot_config.get('admin_username', 'admin')
        self.available_types = ['daily', 'weekly', 'monthly']
        
        # ===== GIVEAWAY SYSTEMS (CORE) =====
        self.giveaway_systems = {}
        for giveaway_type in self.available_types:
            self.giveaway_systems[giveaway_type] = GiveawaySystem(
                bot=application.bot,
                giveaway_type=giveaway_type,
                config_file=config_file
            )
        
        # ===== AUTOMATION MANAGER (YA EXISTE) =====
        self.automation_manager = AutomationManager(
            app=self.app,                           # ← Primer parámetro: app
            multi_giveaway_integration=self,        # ← Segundo parámetro: la instancia actual
            config_file=config_file        
                )
        
        # ===== SETUP TELEGRAM HANDLERS =====
        self._setup_handlers()
        
        logging.info("✅ Multi-type giveaway system initialized successfully")
        
        logging.info("Multi-type giveaway system integrated successfully")
        logging.info(f"Channel configured: {self.channel_id}")
        logging.info(f"Admin configured: {self.admin_id}")
        logging.info(f"Available types: {', '.join(self.available_types)}")


    @property
    def auto_mode_enabled(self):
        """Acceso a automation status via AutomationManager"""
        return self.automation_manager.auto_mode_enabled

    @property  
    def recurring_invitations_enabled(self):
        """Acceso a recurring invitations status via AutomationManager"""
        return self.automation_manager.recurring_invitations_enabled

    @property
    def invitation_frequencies(self):
        """Acceso a invitation frequencies via AutomationManager"""
        return self.automation_manager.invitation_frequencies
    # CORE INTEGRATION
    def _setup_handlers(self):
        """🔄 MODIFIED: Setup handlers for multiple giveaway types"""
        
        # ===== CRITICAL ORDER: FROM MOST SPECIFIC TO MOST GENERAL =====
        
        # 1️⃣ TYPE-SPECIFIC ADMIN COMMANDS (MOST SPECIFIC)
        for giveaway_type in self.available_types:
            # Type-specific manual giveaway commands
            self.app.add_handler(CommandHandler(f"admin_giveaway_{giveaway_type}",
                                                lambda u, c, gt=giveaway_type: admin_commands._handle_manual_giveaway(self, u, c, gt)))
            
            # Type-specific manual draw commands
            self.app.add_handler(CommandHandler(f"admin_sorteo_{giveaway_type}", 
                                            lambda u, c, gt=giveaway_type: admin_commands._handle_manual_sorteo(self,u, c, gt)))
            
            # Type-specific stats commands
            self.app.add_handler(CommandHandler(f"admin_stats_{giveaway_type}", 
                                            lambda u, c, gt=giveaway_type: admin_commands._handle_stats_command(self,u, c, gt)))
            
            # Type-specific pending winners
            self.app.add_handler(CommandHandler(f"admin_pending_{giveaway_type}", 
                                            lambda u, c, gt=giveaway_type: admin_commands._handle_pending_winners(self,u, c,  gt)))
            
            
        # 🆕 NEW: TYPE-SPECIFIC INVITATION COMMANDS
        self.app.add_handler(CommandHandler("admin_send_daily_invitation", lambda u,c: admin_commands.admin_send_daily_invitation(u, c, self )))
        self.app.add_handler(CommandHandler("admin_send_weekly_invitation", lambda u,c:admin_commands.admin_send_weekly_invitation(u, c, self )))
        self.app.add_handler(CommandHandler("admin_send_monthly_invitation", lambda u,c: admin_commands.admin_send_monthly_invitation(u, c, self )))
        
        # 🆕 NEW: TYPE-SPECIFIC DRAW COMMANDS
        self.app.add_handler(CommandHandler("admin_run_daily_draw", lambda u,c: admin_commands.admin_run_daily_draw(u, c, self )))
        self.app.add_handler(CommandHandler("admin_run_weekly_draw", lambda u,c: admin_commands.admin_run_weekly_draw(u, c, self )))
        self.app.add_handler(CommandHandler("admin_run_monthly_draw", lambda u,c: admin_commands.admin_run_monthly_draw(u, c, self )))
        # 2️⃣ GENERAL ADMIN COMMANDS (BACKWARD COMPATIBILITY)
        # ===== COMANDOS ADMIN GENERALES =====
        self.app.add_handler(CommandHandler("admin_giveaway", 
            lambda u, c: admin_commands._handle_manual_giveaway_general(self, u, c)))
        self.app.add_handler(CommandHandler("admin_sorteo", 
            lambda u, c: admin_commands._handle_manual_sorteo_general(self, u, c)))
        self.app.add_handler(CommandHandler("admin_stats", 
            lambda u, c: admin_commands._handle_stats_command_general(self, u, c)))
        self.app.add_handler(CommandHandler("admin_pending_winners", 
            lambda u, c: admin_commands.admin_pending_winners(self, u, c)))
        
        self.app.add_handler(CommandHandler("admin_panel", self.admin_panel))

        self.app.add_handler(CommandHandler("admin_confirm_payment", 
            lambda u, c: admin_commands.admin_confirm_payment(u, c, self)))

        # Confirmation commands (movidos desde test_botTTT.py)
        # ===== COMANDOS DE CONFIRMACIÓN DE PAGO =====
        self.app.add_handler(CommandHandler("admin_confirm_daily", 
            lambda u, c: admin_commands.admin_confirm_daily_payment(self, u, c)))
        self.app.add_handler(CommandHandler("admin_confirm_weekly", 
            lambda u, c: admin_commands.admin_confirm_weekly_payment(self, u, c)))
        self.app.add_handler(CommandHandler("admin_confirm_monthly", 
            lambda u, c: admin_commands.admin_confirm_monthly_payment(self, u, c)))

        # ===== COMANDOS DE PENDING POR TIPO =====
        self.app.add_handler(CommandHandler("admin_pending_daily", 
            lambda u, c: admin_commands.admin_pending_daily(self, u, c)))
        self.app.add_handler(CommandHandler("admin_pending_weekly", 
            lambda u, c: admin_commands.admin_pending_weekly(self, u, c)))
        self.app.add_handler(CommandHandler("admin_pending_monthly", 
            lambda u, c: admin_commands.admin_pending_monthly(self, u, c)))
        
        
        
        # 4️⃣ ANALYTICS COMMANDS (ENHANCED FOR MULTI-TYPE)
        # ===== COMANDOS DE ANALYTICS =====
        self.app.add_handler(CommandHandler("admin_analytics", 
            lambda u, c: admin_commands._handle_admin_analytics_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_analytics_all", 
            lambda u, c: admin_commands._handle_admin_analytics_all_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_user_stats", 
            lambda u, c: admin_commands._handle_admin_user_stats_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_top_users", 
            lambda u, c: admin_commands._handle_admin_top_users_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_account_report", 
            lambda u, c: admin_commands._handle_admin_account_report_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_revenue", 
            lambda u, c: admin_commands._handle_admin_revenue_analysis_command(self, u, c)))
        self.app.add_handler(CommandHandler("admin_backup", 
            lambda u, c: admin_commands._handle_admin_backup_command(self, u, c)))
        
        # 5️⃣ DEBUG COMMANDS
        # ===== COMANDOS DE DEBUG =====
        self.app.add_handler(CommandHandler("debug_pending", 
            lambda u, c: admin_commands._handle_debug_pending_system(self, u, c)))
        self.app.add_handler(CommandHandler("debug_all_systems", 
            lambda u, c: admin_commands._handle_debug_all_systems(self, u, c)))
        

        # ===== COMANDOS DE USUARIO =====
        self.app.add_handler(CommandHandler("start", 
            lambda u, c: user_commands.start_command(self, self.config_loader, u, c)))
        self.app.add_handler(CommandHandler("help", 
            lambda u, c: user_commands.help_command(self.config_loader, u, c)))
        
        # 6️⃣ GENERAL COMMANDS
        self.app.add_handler(CommandHandler("stats", 
            lambda u, c: user_commands._handle_stats_command_public(self,u, c)))
        
        print("🔧 Registering callback handlers in priority order...")
        
        # 🆕 HANDLER ESPECÍFICO PARA AUTOMATION (más específico)
        # Automation callbacks (prioridad alta)
        self.app.add_handler(CallbackQueryHandler(
            lambda u, c: callback_handlers._handle_automation_callbacks(self, self.automation_manager, u, c),
            pattern="^automation_"
        ))
        print("✅ Automation handler registered (Priority 1)")

        # ✅ PARTICIPATION (TYPE-SPECIFIC)
        # for giveaway_type in self.available_types:
        #     participate_handler = CallbackQueryHandler(
        #         lambda u, c, gt=giveaway_type: self.giveaway_systems[gt].handle_participate_button(u, c, gt),
        #         pattern=f"^giveaway_participate_{giveaway_type}$"
        #     )
        #     self.app.add_handler(participate_handler)
        # print("✅ Participation handlers registered (Priority 2)")

        # Participation buttons (type-specific)
        for giveaway_type in self.available_types:
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: participation_flow.handle_participate_button(u, c, gt),
                pattern=f"^giveaway_participate_{giveaway_type}$"
            ))
        
        # ===== PRIORITY 5: PANEL CALLBACKS (INCLUYE PENDING) =====
        # panel_callbacks_handler = CallbackQueryHandler(
        #     self._handle_admin_panel_callbacks,
        #     # 🔄 FIXED: Restaurar patrón original SIN exclusiones
        #     pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_|confirm_payment_)"
        # )
        # self.app.add_handler(panel_callbacks_handler)
        
        # Panel callbacks (general)
        # self.app.add_handler(CallbackQueryHandler(
        #     lambda u, c: callback_handlers._handle_admin_panel_callbacks(u, c, self),
        #     # pattern="^(panel_|analytics_|maintenance_|user_details_|type_selector_|unified_|view_only_|confirm_payment_)"
        #     pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_|confirm_payment_)"
        # ))
        panel_callbacks_handler = CallbackQueryHandler(
            lambda u, c: callback_handlers._handle_admin_panel_callbacks(self,self.automation_manager, c,u),
            # pattern="^(panel_|analytics_|maintenance_|user_details_|type_selector_|unified_|view_only_|confirm_payment_)"
            pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_|confirm_payment_)"
        )
        self.app.add_handler(panel_callbacks_handler)
        # mt5_handler = MessageHandler(
        #         filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.Regex(r'^\d+$'),
        #         self._handle_mt5_input_universal
        #     )
        # self.app.add_handler(mt5_handler)
        # print("✅ MT5 input handler registered (Priority 4)")

        # MT5 input (numeric)
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.Regex(r'^\d+$'),
            lambda u, c: participation_flow.handle_mt5_input(u, c, self.giveaway_systems)
        ))
        
        

        # invalid_input_handler = MessageHandler(
        #     filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.Regex(r'^\d+$'),
        #     self._handle_invalid_input
        # )
        # self.app.add_handler(invalid_input_handler)

        # ===== MESSAGE HANDLERS =====
        
        
        # Invalid input (non-numeric)
        self.app.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.Regex(r'^\d+$'),
            self._handle_invalid_input
        ))
        
        logging.info("Multi-type handlers configured in correct order")


    # ===== CORE BUSINESS METHODS =====
    def get_giveaway_system(self, giveaway_type):
        """🆕 NEW: Get specific giveaway system"""
        return self.giveaway_systems.get(giveaway_type)

    def get_all_giveaway_systems(self):
        """🆕 NEW: Get all giveaway systems"""
        return self.giveaway_systems
    


    # DELEGATION METHODS (SIMPLE) (Bridge Telegram ↔ GiveawaySystem)

    async def send_daily_invitation(self):
        """🆕 NEW: Send daily invitation (for scheduler)"""
        try:
            return await self.giveaway_systems['daily'].send_invitation('daily')
        except Exception as e:
            logging.error(f"Error sending daily invitation: {e}")
            return False

    async def send_weekly_invitation(self):
        """🆕 NEW: Send weekly invitation (for scheduler)"""
        try:
            return await self.giveaway_systems['weekly'].send_invitation('weekly')
        except Exception as e:
            logging.error(f"Error sending weekly invitation: {e}")
            return False

    async def send_monthly_invitation(self):
        """🆕 NEW: Send monthly invitation (for scheduler)"""
        try:
            return await self.giveaway_systems['monthly'].send_invitation('monthly')
        except Exception as e:
            logging.error(f"Error sending monthly invitation: {e}")
            return False  # → delegation


    async def run_daily_draw(self):
        """🆕 NEW: Execute daily draw (for scheduler)"""
        try:
            await self.giveaway_systems['daily'].run_giveaway('daily')
            logging.info("Daily draw executed successfully")
        except Exception as e:
            logging.error(f"Error in daily draw: {e}")

    async def run_weekly_draw(self):
        """🆕 NEW: Execute weekly draw (for scheduler)"""
        try:
            await self.giveaway_systems['weekly'].run_giveaway('weekly')
            logging.info("Weekly draw executed successfully")
        except Exception as e:
            logging.error(f"Error in weekly draw: {e}")

    async def run_monthly_draw(self):
        """🆕 NEW: Execute monthly draw (for scheduler)"""
        try:
            await self.giveaway_systems['monthly'].run_giveaway('monthly')
            logging.info("Monthly draw executed successfully")
        except Exception as e:
            logging.error(f"Error in monthly draw: {e}")      # → delegation


    async def run_giveaway(self, giveaway_type):
        """🆕 NEW: Execute specific draw (for scheduler)"""
        try:
            await self.giveaway_systems[giveaway_type].run_giveaway(giveaway_type)
            logging.info(f"Draw executed successfully for {giveaway_type}")
        except Exception as e:
            logging.error(f"Error in {giveaway_type} draw: {e}")
    
    
    # ===== AUTOMATION DELEGATION =====
    
    def setup_automatic_draws(self):
        """Delegate to AutomationManager"""
        return self.automation_manager.setup_automatic_draws()
    
    def toggle_automatic_mode(self, giveaway_type: str, enabled: bool) -> bool:
        """Delegate to AutomationManager"""
        return self.automation_manager.toggle_automatic_mode(giveaway_type, enabled)
    
    def get_automation_status(self) -> dict:
        """Delegate to AutomationManager"""
        return self.automation_manager.get_automation_status()



    # ROUTING TELEGRAM INPUT

    async def _route_mt5_input(self, update, context, giveaway_type):
        """🔄 ENHANCED: Route MT5 input to correct giveaway system"""
        try:
            print(f"🔍 DEBUG: _route_mt5_input called for {giveaway_type}")
            print(f"🔍 DEBUG: awaiting_mt5_{giveaway_type} = {context.user_data.get(f'awaiting_mt5_{giveaway_type}')}")
            
            # Check if user is awaiting MT5 input for this specific type
            if context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                print(f"✅ DEBUG: Processing MT5 input for {giveaway_type}")
                await self.giveaway_systems[giveaway_type].handle_mt5_input(update, context, giveaway_type)
            else:
                print(f"⚠️ DEBUG: User not awaiting MT5 input for {giveaway_type}")
        except Exception as e:
            logging.error(f"Error routing MT5 input for {giveaway_type}: {e}")
            print(f"❌ DEBUG: Error in _route_mt5_input: {e}")

    async def _handle_mt5_input_universal(self, update, context):
        """🆕 Handler universal para input de MT5"""
        try:
            print(f"🔍 DEBUG: MT5 input received: {update.message.text}")
            
            # Verificar para qué tipo está esperando input
            for giveaway_type in self.available_types:
                if context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                    print(f"✅ DEBUG: Found awaiting type: {giveaway_type}")
                    await self._route_mt5_input(update, context, giveaway_type)
                    return
            
            print("⚠️ DEBUG: No awaiting type found for MT5 input")
            await update.message.reply_text(
                "ℹ️ <b>No active registration</b>\n\nUse /start to begin participation in a giveaway.",
                parse_mode='HTML'
            )
            
        except Exception as e:
            logging.error(f"Error in universal MT5 handler: {e}")   

    async def _handle_invalid_input(self, update, context):
        """🔄 MODIFIED: Handle invalid input with type awareness"""
        try:
            # Check which giveaway type is awaiting input
            for giveaway_type in self.available_types:
                if context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                    remaining_attempts = 4 - context.user_data.get(f'mt5_attempts_{giveaway_type}', 0)
                    
                    if remaining_attempts > 0:
                        invalid_message = f"""❌ <b>Invalid input</b>

Please send only your MT5 account number.

💡 <b>Valid examples:</b>
• 12345678
• 87654321

❌ <b>Not valid:</b>
• Text (like "{update.message.text[:10]}...")
• Numbers with spaces
• Special characters

🔄 Attempts remaining: <b>{remaining_attempts}</b>

⚠️ Send only numbers:"""

                        await update.message.reply_text(invalid_message, parse_mode='HTML')
                    else:
                        # No attempts remaining
                        await participation_flow._handle_max_attempts_reached(update, context, 4, giveaway_type )
                    return
                    
        except Exception as e:
            logging.error(f"Error handling invalid input: {e}")



# Sistema de salud y utilidades:
    def verify_all_systems_health(self):
        """🆕 NEW: Comprehensive health check for all systems"""
        try:
            health_report = {
                'overall_status': 'healthy',
                'systems': {},
                'issues': [],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    
                    # Test basic operations
                    stats = giveaway_system.get_stats(giveaway_type)
                    pending = giveaway_system.get_pending_winners(giveaway_type)
                    config = giveaway_system.get_giveaway_config(giveaway_type)
                    
                    # Check file access
                    file_paths = giveaway_system.get_file_paths(giveaway_type)
                    files_ok = all(os.path.exists(path) or path.endswith('.csv') for path in file_paths.values())
                    
                    system_status = {
                        'status': 'healthy',
                        'stats_accessible': bool(stats),
                        'pending_count': len(pending),
                        'files_accessible': files_ok,
                        'config_loaded': bool(config),
                        'prize_amount': giveaway_system.get_prize_amount(giveaway_type)
                    }
                    
                    health_report['systems'][giveaway_type] = system_status
                    
                except Exception as e:
                    health_report['systems'][giveaway_type] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    health_report['issues'].append(f"{giveaway_type}: {str(e)}")
                    health_report['overall_status'] = 'degraded'
            
            # Check configuration
            try:
                bot_config = self.config_loader.get_bot_config()
                config_ok = all(key in bot_config for key in ['channel_id', 'admin_id'])
                if not config_ok:
                    health_report['issues'].append("Configuration incomplete")
                    health_report['overall_status'] = 'degraded'
            except Exception as e:
                health_report['issues'].append(f"Configuration error: {e}")
                health_report['overall_status'] = 'error'
            
            return health_report
            
        except Exception as e:
            logging.error(f"Error in health check: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    async def emergency_system_check(self):
        """🆕 NEW: Emergency check and notification"""
        try:
            health_report = self.verify_all_systems_health()
            
            if health_report['overall_status'] != 'healthy':
                # Send emergency notification to admin
                message = f"🚨 <b>GIVEAWAY SYSTEM ALERT</b>\n\n"
                message += f"Status: <b>{health_report['overall_status'].upper()}</b>\n"
                message += f"Time: {health_report['timestamp']}\n\n"
                
                if health_report.get('issues'):
                    message += "<b>Issues detected:</b>\n"
                    for issue in health_report['issues'][:5]:  # Limit to 5 issues
                        message += f"• {issue}\n"
                
                message += f"\n🔧 Please check the system immediately."
                
                await self.app.bot.send_message(
                    chat_id=self.admin_id,
                    text=message,
                    parse_mode='HTML'
                )
                
                logging.warning(f"Emergency system alert sent: {health_report['overall_status']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Error in emergency system check: {e}")
            return False

    def get_system_info(self):
        """🆕 NEW: Get comprehensive system information"""
        try:
            return  {
                'integration_type': 'MultiGiveawayIntegration',
                'available_types': self.available_types,
                'total_systems': len(self.giveaway_systems),
                'admin_id': self.admin_id,
                'channel_id': self.channel_id,
                'automation_enabled': bool(self.automation_manager.scheduler),
                'config_loaded': bool(self.config_loader),
                'systems_status': {
                    giveaway_type: {
                        'operational': True,
                        'today_participants': giveaway_system.get_stats(giveaway_type).get('today_participants', 0),
                        'total_winners': giveaway_system.get_stats(giveaway_type).get('total_winners', 0),
                        'prize_amount': giveaway_system.get_prize_amount(giveaway_type)
                    }
                    for giveaway_type, giveaway_system in self.giveaway_systems.items()
                }
            }
            
            # return system_info
            
        except Exception as e:
            logging.error(f"Error getting system info: {e}")
            return {'error': str(e)}
        

    # Notificaciones especializadas:
    async def _notify_main_admin_only(self, winner, giveaway_type, executed_by):
        """🆕 NEW: Send notification ONLY to main administrator"""
        try:
            # Get main admin ID from config
            main_admin_id = self.admin_id  # This is your ID from config
            
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            
            # Get prize amount
            # giveaway_system = self.get_giveaway_system(giveaway_type)
            prize = self.giveaway_systems[giveaway_type].get_prize_amount(giveaway_type)
            
            # Create comprehensive notification for main admin
            main_admin_message = f"""🤖 <b>AUTOMATIC {giveaway_type.upper()} WINNER - MAIN ADMIN NOTIFICATION</b>

    🎉 <b>Winner Selected:</b> {first_name} ({winner_display})
    📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
    💰 <b>Prize:</b> ${prize} USD
    🎯 <b>Giveaway Type:</b> {giveaway_type.upper()}
    👤 <b>Executed by:</b> {executed_by}
    📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ⚠️ <b>PAYMENT REQUIRED:</b>
    💸 Transfer ${prize} USD to MT5 account: <code>{winner['mt5_account']}</code>

    💡 <b>Confirmation Commands:</b>
    - <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code>
    - Or use the admin panel buttons

    🔔 <b>Notification Status:</b>
    ├─ Main Admin: ✅ You (individual notification)
    ├─ Admin Channel: ✅ Group notification sent
    └─ Other Admins: ❌ No individual spam

    🎯 <b>Next Steps:</b>
    1️⃣ Process payment to MT5 account
    2️⃣ Confirm using command or admin panel
    3️⃣ Winner will be announced automatically"""

            # Send only to main admin
            await self.app.bot.send_message(
                chat_id=main_admin_id,
                text=main_admin_message,
                parse_mode='HTML'
            )
            
            logging.info(f"Main admin notification sent for {giveaway_type} winner: {winner['telegram_id']}")
            
        except Exception as e:
            logging.error(f"Error notifying main admin: {e}")

    async def _send_admin_channel_notification(self, giveaway_type: str, winner=None, notification_type='winner', custom_message=None):
        """🆕 Send notification to admin channel if configured"""
        try:
            admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
            admin_channel_id = admin_config.get('admin_channel_id')
            
            if not admin_channel_id  or admin_channel_id == "-1001234567890":
                logging.info("No admin channel configured, skipping group notification")
                return
                
            
            if custom_message:
                message = custom_message
            elif notification_type == 'winner' and winner:
                prize = self.giveaway_systems[giveaway_type].get_prize_amount(giveaway_type)

                username = winner.get('username', '')
                username_display = f"@{username}" if username else "no_username"
                
                message = f"""🤖 <b>AUTOMATIC DRAW COMPLETED</b>

🎯 <b>Giveaway:</b> {giveaway_type.upper()} (${prize} USD)
🎉 <b>Winner:</b> {winner.get('first_name', 'N/A')} ({username_display})
📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ <b>PAYMENT REQUIRED</b> Pending manual transfer
💸 Transfer ${prize} USD to account <code>{winner['mt5_account']}</code>
📱 Confirm: <code>/admin_confirm_{giveaway_type} {username or winner['telegram_id']}</code>

🔔 Individual notifications sent to authorized payment admins.
🎯 Winner will receive private congratulation after payment confirmation."""
            else:
                return  # No message to send
            
            await self.app.bot.send_message(
                chat_id=admin_channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            logging.info(f"✅ Admin channel notification sent for {giveaway_type} {notification_type}")
            
        except Exception as e:
            logging.error(f"Error sending admin channel notification: {e}")

    async def notify_payment_admins_new_winner(self, context, winner, giveaway_type, executed_by):
        """🔄 MODIFIED: Simplified notification - only main admin + channel"""
        try:
            logging.info(f"Sending {giveaway_type} winner notifications...")
            
            # 1️⃣ Notify main admin individually (detailed notification)
            await self._notify_main_admin_only(winner, giveaway_type, executed_by)
            
            # 2️⃣ Notify admin channel (group notification)
            await self._send_admin_channel_notification(giveaway_type, winner, 'winner')
            
            # ✅ SIMPLIFIED: No more individual spam to all admins
            logging.info(f"{giveaway_type.title()} notifications sent: Main admin + Admin channel")
            
        except Exception as e:
            logging.error(f"Error in simplified notification system: {e}")

    # Helpers de sistema:
    




    # TELEGRAM INTEGRATION UTILS
    def _get_permission_manager_from_callback(self):
        """🆕 Helper para obtener permission manager en funciones de callback"""
        try:
            if hasattr(self, 'app') and hasattr(self.app, 'bot_data'):
                return self.app.bot_data.get('permission_manager')
            return None
        except Exception as e:
            logging.error(f"Error getting permission manager from callback: {e}")
            return None

    async def _generate_main_admin_panel_content(self, user_id, permission_manager):
        try:
            admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
            admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
            
            # 🚨 DETECTAR VIEW_ONLY (retorna None para que la función llamadora maneje)
            if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
                return None, None, 'VIEW_ONLY'
            
            # 📊 OBTENER ESTADÍSTICAS (copiado de admin_panel actual)
            total_pending = 0
            total_today = 0
            stats_summary = []
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                stats = self.giveaway_systems[giveaway_type].get_stats(giveaway_type)
                pending_count = len(self.giveaway_systems[giveaway_type].get_pending_winners(giveaway_type))
                prize = self.giveaway_systems[giveaway_type].get_prize_amount(giveaway_type)
                today_participants = stats.get('today_participants', 0)
                
                total_pending += pending_count
                total_today += today_participants
                
                # Verificar si ventana de participación está abierta
                is_open = self.giveaway_systems[giveaway_type].is_participation_window_open(giveaway_type)
                status_emoji = "🟢" if is_open else "🔴"
                
                stats_summary.append({
                    'type': giveaway_type,
                    'prize': prize,
                    'today_participants': today_participants,
                    'pending': pending_count,
                    'total_winners': stats.get('total_winners', 0),
                    'status_emoji': status_emoji,
                    'is_open': is_open
                })
            
            # 📝 CONSTRUIR MENSAJE (copiado de admin_panel actual)
            permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'
            # Construir mensaje del panel (adaptado según permisos)
            admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
            permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'
            
            message = f"🎛️ <b>MULTI-GIVEAWAY ADMIN PANEL</b>\n"
            message += f"👤 <b>Access Level:</b> {permission_level}\n"
            message += f"🔑 <b>Admin:</b> {admin_name}\n\n"
            
            # Estado general
            message += f"📊 <b>System Status:</b>\n"
            message += f"├─ Today's participants: <b>{total_today}</b>\n"
            message += f"├─ Pending winners: <b>{total_pending}</b>\n"
            message += f"└─ System health: {'🟢 Operational' if total_pending < 10 else '⚠️ High pending'}\n\n"
            
            # Estado por tipo
            message += f"🎯 <b>Giveaway Types:</b>\n"
            for stat in stats_summary:
                message += f"{stat['status_emoji']} <b>{stat['type'].upper()}</b> (${stat['prize']}): "
                message += f"{stat['today_participants']} today, {stat['pending']} pending\n"
            
            message += f"\n🚀 <b>Available Actions:</b>"
            from datetime import datetime
            refresh_time = datetime.now().strftime('%H:%M:%S')
            message += f"\n\n⏰ <b>Last updated:</b> {refresh_time} London Time"
            # Crear botones adaptados según permisos
            buttons = []
            
            # 6️⃣ BOTONES ADAPTATIVOS SEGÚN PERMISOS
            if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
                buttons.append([
                    InlineKeyboardButton("📅 Daily", callback_data="panel_daily"),
                    InlineKeyboardButton("📅 Weekly", callback_data="panel_weekly"),
                    InlineKeyboardButton("📅 Monthly", callback_data="panel_monthly")
                ])
            # Fila 1: Acciones principales (solo si tiene permisos)
            row1 = []
            if permission_manager.has_permission(user_id, SystemAction.SEND_DAILY_INVITATION):
                row1.append(InlineKeyboardButton("📢 Send Invitations", callback_data="panel_send_invitations"))
            if permission_manager.has_permission(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS):
                row1.append(InlineKeyboardButton(f"👑 Pending ({total_pending})", callback_data="panel_pending_winners"))
            
            if row1:
                buttons.append(row1)
            
            # Fila 2: Gestión de ganadores (solo si tiene permisos) 
            row2 = []            
            if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
                row2.append(InlineKeyboardButton("📊 Statistics", callback_data="panel_statistics"))
            if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
                row2.append(InlineKeyboardButton("📈 Advanced Analytics", callback_data="panel_advanced_analytics"))
            if row2:
                buttons.append(row2)
            
            # Fila 3: Acceso por tipo (solo para PAYMENT_SPECIALIST+)
            row3 = []
            if permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
                row3.append(InlineKeyboardButton("🤖 Automation", callback_data="automation_control"))
            if row3:
                buttons.append(row3)
            
            # Fila 4: Sistema (solo FULL_ADMIN puede ver mantenimiento)
            row4 = []
            row4.append(InlineKeyboardButton("🏥 Health Check", callback_data="panel_health"))
            if permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
                row4.append(InlineKeyboardButton("🔧 Maintenance", callback_data="panel_maintenance"))
                # row4.append(InlineKeyboardButton("🤖 Auto-Draw", callback_data="automation_control"))
            if row4:
                buttons.append(row4)
            
            
            
            row5 = []            
            if permission_manager.has_permission(user_id, SystemAction.VIEW_BASIC_STATS):
                row5.append(InlineKeyboardButton("📊 Basic Analytics", callback_data="panel_basic_analytics"))
            if row5:
                buttons.append(row5)
            
            # Fila 6: Refresh (siempre disponible)
            buttons.append([
                InlineKeyboardButton("🔄 Refresh Panel", callback_data="panel_refresh")
            ])
            
            # 7️⃣ MENSAJE INFORMATIVO SOBRE PERMISOS
            if permission_level == "PAYMENT_SPECIALIST":
                message += f"\n\n💡 <b>Note:</b> Some advanced features require FULL_ADMIN permissions"
            
            reply_markup = InlineKeyboardMarkup(buttons)
            return message, reply_markup, 'SUCCESS'
            
        except Exception as e:
            logging.error(f"Error in admin panel: {e}")
            
            return "", None, 'ERROR'
        
    async def admin_panel(self, update, context):
        """🔄 REFACTORED: Panel administrativo usando función base compartida"""
        user_id = update.effective_user.id
        print(f"OJO DEBUG: admin_panel called by user {user_id}")
        
        try:
            config_loader = ConfigLoader()
            bot_config = config_loader.get_bot_config()
            channel_id = bot_config['channel_id']
            
            # 1️⃣ VERIFICACIÓN PRIMARIA: Telegram admin (siempre debe funcionar)
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can access admin panel")
                return
            
            # 2️⃣ VERIFICACIÓN DE PERMISOS GRANULARES
            permission_manager = get_permission_manager(context)
            if not permission_manager:
                await update.message.reply_text("❌ Permission system not initialized")
                return
            
            # 3️⃣ 🆕 USAR FUNCIÓN BASE COMPARTIDA
            message, reply_markup, status = await self._generate_main_admin_panel_content(user_id, permission_manager)
            
            if status == 'VIEW_ONLY':
                # 🚨 DETECCIÓN VIEW_ONLY INMEDIATA - usar función específica para comandos
                print(f"OJO DEBUG: VIEW_ONLY user {user_id} detected, calling show_view_only_panel_direct")
                await user_commands.show_view_only_panel_direct(self, update, context)
                print(f"✅ DEBUG: show_view_only_panel_direct completed for {user_id}")
                return
            elif status == 'ERROR':
                await update.message.reply_text("❌ Error loading admin panel")
                return
            
            # 4️⃣ MOSTRAR PANEL PRINCIPAL (SUCCESS case)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in admin panel: {e}")
            await update.message.reply_text("❌ Error loading admin panel")

    async def _show_unified_panel_inline(self, query):
        """🔄 REFACTORED: Mostrar panel principal usando función base compartida"""
        try:
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            
            if not permission_manager:
                await query.edit_message_text("❌ Permission system not initialized")
                return
            
            # 🆕 USAR FUNCIÓN BASE COMPARTIDA
            message, reply_markup, status = await self._generate_main_admin_panel_content(user_id, permission_manager)
            
            if status == 'VIEW_ONLY':
                # 🚨 DETECCIÓN VIEW_ONLY - usar función específica para callbacks
                await callback_handlers._show_view_only_panel(self,query)
                return
            elif status == 'ERROR':
                await query.edit_message_text("❌ Error loading admin panel")
                return
            
            # ✅ MOSTRAR PANEL PRINCIPAL (SUCCESS case)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified panel inline: {e}")
            await query.edit_message_text("❌ Error loading admin panel")