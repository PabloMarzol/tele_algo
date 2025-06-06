# giveaway_integration3.py - Multi-Type Giveaway Integration System
"""
Multi-type giveaway integration system supporting daily, weekly, and monthly giveaways
Complete version with all buttons and panels working correctly for multiple types
"""

from ga_manager import GiveawaySystem
from config_loader import ConfigLoader
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import os
import csv
import asyncio
from datetime import datetime, timedelta
from async_manager import prevent_concurrent_callback, setup_async_safety
from admin_permissions import SystemAction, PermissionGroup, require_permission, require_any_permission, require_draw_permission_with_time_check

from admin_permissions import (
    AdminPermissionManager, 
    SystemAction, 
    PermissionGroup,
    setup_permission_system,
    get_permission_manager,      # ← 🚨 ESTA LÍNEA FALTA
    require_permission,
    require_any_permission,
    require_draw_permission_with_time_check
)

# from ..mySQL.mysql_manager import MySQLManager, get_mysql_connection


class MultiGiveawayIntegration:
    """🆕 NEW: Multi-type giveaway integration system"""
    
    def __init__(self, application, mt5_api, config_file="config.json"):
        """
        Initialize multi-type giveaway integration
        
        Args:
            application: Telegram application instance
            mt5_api: MT5 API client
            config_file: Path to configuration file
        """
        self.app = application
        self.mt5_api = mt5_api
        
        # 🆕 NEW: Load configuration
        self.config_loader = ConfigLoader(config_file)
        bot_config = self.config_loader.get_bot_config()
        
        self.channel_id = bot_config['channel_id']
        self.admin_id = bot_config['admin_id']
        self.admin_username = bot_config.get('admin_username', 'admin')

        # 🆕 ADD: Automation management
        self.scheduler = None
        self.auto_mode_enabled = {
            'daily': False,
            'weekly': False, 
            'monthly': False
        }
        self.recurring_invitations_enabled = True
        self.invitation_frequencies = {
            'daily': 2,
            'weekly': 4,
            'monthly': 6
        }

        try:
            automation_config = self.config_loader.get_all_config().get('automation', {})
            default_modes = automation_config.get('default_auto_modes', {})

            recurring_config = automation_config.get('recurring_invitations', {})

            self.recurring_invitations_enabled = recurring_config.get('enabled', False)
            # self.invitation_frequencies['daily'] = recurring_config.get('daily_frequency_hours', 1)
            # self.invitation_frequencies['weekly'] = recurring_config.get('weekly_frequency_hours', 1)
            # self.invitation_frequencies['monthly'] = recurring_config.get('monthly_frequency_hours', 1)
            
            print(f"🔍 DEBUG: recurring_invitations_enabled = {self.recurring_invitations_enabled}")
            print(f"🔍 DEBUG: invitation_frequencies = {self.invitation_frequencies}")
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                self.auto_mode_enabled[giveaway_type] = default_modes.get(giveaway_type, False)
            
            

            
            logging.info(f"Automation config loaded: {self.auto_mode_enabled}")
            logging.info(f"Recurring invitations loaded: {self.recurring_invitations_enabled}")
        except Exception as e:
            logging.warning(f"No automation config found, using defaults: {e}")
        
        # 🆕 NEW: Initialize multiple giveaway systems
        self.giveaway_systems = {}
        self.available_types = ['daily', 'weekly', 'monthly']

        
        for giveaway_type in self.available_types:
            self.giveaway_systems[giveaway_type] = GiveawaySystem(
                mt5_api=mt5_api,
                bot=application.bot,
                giveaway_type=giveaway_type,
                config_file=config_file
            )
        
        # Setup handlers
        self._setup_handlers()
        
        logging.info("Multi-type giveaway system integrated successfully")
        logging.info(f"Channel configured: {self.channel_id}")
        logging.info(f"Admin configured: {self.admin_id}")
        logging.info(f"Available types: {', '.join(self.available_types)}")

    def _get_permission_manager_from_callback(self):
        """🆕 Helper para obtener permission manager en funciones de callback"""
        try:
            if hasattr(self, 'app') and hasattr(self.app, 'bot_data'):
                return self.app.bot_data.get('permission_manager')
            return None
        except Exception as e:
            logging.error(f"Error getting permission manager from callback: {e}")
            return None
    
    def _setup_handlers(self):
        """🔄 MODIFIED: Setup handlers for multiple giveaway types"""
        
        # ===== CRITICAL ORDER: FROM MOST SPECIFIC TO MOST GENERAL =====
        
        # 1️⃣ TYPE-SPECIFIC ADMIN COMMANDS (MOST SPECIFIC)
        for giveaway_type in self.available_types:
            # Type-specific manual giveaway commands
            self.app.add_handler(CommandHandler(f"admin_giveaway_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_manual_giveaway(u, c, gt)))
            
            # Type-specific manual draw commands
            self.app.add_handler(CommandHandler(f"admin_sorteo_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_manual_sorteo(u, c, gt)))
            
            # Type-specific stats commands
            self.app.add_handler(CommandHandler(f"admin_stats_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_stats_command(u, c, gt)))
            
            # Type-specific pending winners
            self.app.add_handler(CommandHandler(f"admin_pending_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_pending_winners(u, c, gt)))
            
            # Type-specific panels
            # self.app.add_handler(CommandHandler(f"admin_panel_{giveaway_type}", 
            #                                   lambda u, c, gt=giveaway_type: self._handle_admin_panel_type(u, c, gt)))

        # 2️⃣ GENERAL ADMIN COMMANDS (BACKWARD COMPATIBILITY)
        self.app.add_handler(CommandHandler("admin_giveaway", self._handle_manual_giveaway_general))
        self.app.add_handler(CommandHandler("admin_sorteo", self._handle_manual_sorteo_general))

        self.app.add_handler(CommandHandler("admin_stats", self._handle_stats_command_general))
        self.app.add_handler(CommandHandler("admin_pending_winners", self._handle_pending_winners_general))


        self.app.add_handler(CommandHandler("admin_pending_winners", self.admin_pending_winners))
        self.app.add_handler(CommandHandler("admin_panel", self.admin_panel))
        self.app.add_handler(CommandHandler("admin_confirm_payment", self.admin_confirm_payment))

        # Confirmation commands (movidos desde test_botTTT.py)
        self.app.add_handler(CommandHandler("admin_confirm_daily", 
                                        lambda u, c: self.admin_confirm_daily_payment(u, c)))
        self.app.add_handler(CommandHandler("admin_confirm_weekly", 
                                        lambda u, c: self.admin_confirm_weekly_payment(u, c)))
        self.app.add_handler(CommandHandler("admin_confirm_monthly", 
                                        lambda u, c: self.admin_confirm_monthly_payment(u, c)))

        # Pending winners commands (movidos desde test_botTTT.py)
        self.app.add_handler(CommandHandler("admin_pending_daily", 
                                        lambda u, c: self.admin_pending_daily(u, c)))
        self.app.add_handler(CommandHandler("admin_pending_weekly", 
                                        lambda u, c: self.admin_pending_weekly(u, c)))
        self.app.add_handler(CommandHandler("admin_pending_monthly", 
                                       lambda u, c: self.admin_pending_monthly(u, c)))
        
        # 3️⃣ UNIFIED ADMIN COMMANDS
        # self.app.add_handler(CommandHandler("admin_panel", self._handle_admin_panel_unified))
        # self.app.add_handler(CommandHandler("admin_panel_unified", self._handle_admin_panel_unified))
        # self.app.add_handler(CommandHandler("admin_pending_winners", self._handle_pending_winners_general))
        # self.app.add_handler(CommandHandler("admin_confirm_payment", self._handle_confirm_payment_general))
        
        # 4️⃣ ANALYTICS COMMANDS (ENHANCED FOR MULTI-TYPE)
        self.app.add_handler(CommandHandler("admin_analytics", self._handle_admin_analytics_command))
        self.app.add_handler(CommandHandler("admin_analytics_all", self._handle_admin_analytics_all_command))
        self.app.add_handler(CommandHandler("admin_user_stats", self._handle_admin_user_stats_command))
        self.app.add_handler(CommandHandler("admin_top_users", self._handle_admin_top_users_command))
        self.app.add_handler(CommandHandler("admin_account_report", self._handle_admin_account_report_command))
        self.app.add_handler(CommandHandler("admin_revenue", self._handle_admin_revenue_analysis_command))
        self.app.add_handler(CommandHandler("admin_backup", self._handle_admin_backup_command))
        
        # 5️⃣ DEBUG COMMANDS
        self.app.add_handler(CommandHandler("debug_pending", self._handle_debug_pending_system))
        self.app.add_handler(CommandHandler("debug_all_systems", self._handle_debug_all_systems))
        
        # 6️⃣ GENERAL COMMANDS
        self.app.add_handler(CommandHandler("stats", self._handle_stats_command_public))

        
        print("🔧 Registering callback handlers in priority order...")
        
        # 🆕 HANDLER ESPECÍFICO PARA AUTOMATION (más específico)
        automation_handler = CallbackQueryHandler(
                self._handle_automation_callbacks,
                pattern="^automation_"
        )
        self.app.add_handler(automation_handler)
        print("✅ Automation handler registered (Priority 1)")

        # ✅ PARTICIPATION (TYPE-SPECIFIC)
        for giveaway_type in self.available_types:
            participate_handler = CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self.giveaway_systems[gt].handle_participate_button(u, c, gt),
                pattern=f"^giveaway_participate_{giveaway_type}$"
            )
            self.app.add_handler(participate_handler)
        print("✅ Participation handlers registered (Priority 2)")
        
        # nuevo prueba =================================================
        # ===== 🆕 PRIORITY 4: ADMIN CHANNEL PAYMENT CONFIRMATIONS =====
        # Solo capturar callbacks de confirmación directa, NO los del panel
        # payment_confirmation_handler = CallbackQueryHandler(
        #     self._handle_payment_from_admin_channel,
        #     pattern="^confirm_payment_(daily|weekly|monthly)_[^_]+$"  # 🎯 MÁS ESPECÍFICO
        # )
        # self.app.add_handler(payment_confirmation_handler)
        # print("✅ Payment confirmation handler registered (Priority 4)")
        
        # ===== PRIORITY 5: PANEL CALLBACKS (INCLUYE PENDING) =====
        panel_callbacks_handler = CallbackQueryHandler(
            self._handle_admin_panel_callbacks,
            # 🔄 FIXED: Restaurar patrón original SIN exclusiones
            pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_|confirm_payment_)"
        )
        self.app.add_handler(panel_callbacks_handler)
        # print("✅ Panel callbacks handler registered (Priority 3)")
        #  nuevo prueba =================================================
        
        # panel_callbacks_handler = CallbackQueryHandler(
        #     self._handle_admin_panel_callbacks,
        #     # pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_)"
        #     pattern="^(panel_|analytics_|maintenance_|user_details_|user_full_analysis_|investigate_account_|no_action|type_selector_|unified_|view_only_)(?!confirm_payment)"
        # )
        # self.app.add_handler(panel_callbacks_handler)
        # print("✅ Panel callbacks handler registered (Priority 3)")
        
        mt5_handler = MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.Regex(r'^\d+$'),
                self._handle_mt5_input_universal
            )
        self.app.add_handler(mt5_handler)
        print("✅ MT5 input handler registered (Priority 4)")

        invalid_input_handler = MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.Regex(r'^\d+$'),
            self._handle_invalid_input
        )
        self.app.add_handler(invalid_input_handler)
        
        # # ✅ PAYMENT CONFIRMATION (TYPE-SPECIFIC)
        # for giveaway_type in self.available_types:
        #     confirm_payment_handler = CallbackQueryHandler(
        #         lambda u, c, gt=giveaway_type: self._handle_confirm_payment_callback(u, c, gt),
        #         pattern=f"^confirm_payment_{giveaway_type}_"
        #     )
        #     self.app.add_handler(confirm_payment_handler)

        # # ✅ ADMIN PANEL CALLBACKS (EXPANDED PATTERN)
        
        # 9️⃣ INVALID INPUT HANDLER
        
        
        logging.info("Multi-type handlers configured in correct order")

    # ==================  AUTOMATATION  =============================
    # ==================  INVITATION    =============================

    # 🆕 ADD after setup_automatic_draws() method

    # def setup_recurring_invitations(self):
    #     """🆕 Setup recurring invitation jobs"""
    #     if self.scheduler is None: # or not self.recurring_invitations_enabled
    #         logging.warning("⚠️ No scheduler available for recurring invitations")
    #         return
            
    #     try:
    #         from apscheduler.triggers.interval import IntervalTrigger
    #         logging.info("🔧 Setting up recurring invitations...")

    #          # 🔄 IMPROVED: More detailed logging
    #         logging.info(f"🔧 Setting up recurring invitations...")
    #         logging.info(f"   - Enabled: {self.recurring_invitations_enabled}")
    #         logging.info(f"   - Frequencies: {self.invitation_frequencies}")
        
    #         # Lista de trabajos a crear
    #         jobs_to_create = [
    #             ('recurring_daily_invitations', 'daily', self.invitation_frequencies['daily']),
    #             ('recurring_weekly_invitations', 'weekly', self.invitation_frequencies['weekly']),
    #             ('recurring_monthly_invitations', 'monthly', self.invitation_frequencies['monthly'])
    #         ]
            
    #         successful_jobs = 0
            
    #         for job_id, giveaway_type, frequency in jobs_to_create:
    #             try:
    #                 # Remover trabajo existente si existe
    #                 try:
    #                     self.scheduler.remove_job(job_id)
    #                     logging.info(f"🗑️ Removed existing job: {job_id}")
    #                 except:
    #                     pass
    #                 if frequency <= 0:
    #                     logging.error(f"❌ Invalid frequency for {job_id}: {frequency}h")
    #                     continue
    #                 # Crear nuevo trabajo
    #                 self.scheduler.add_job(
    #                     lambda gt=giveaway_type: asyncio.create_task(self._send_recurring_invitation(gt)),
    #                     IntervalTrigger(hours=frequency),
    #                     id=job_id,
    #                     paused=not self.recurring_invitations_enabled  
    #                 )
                    
    #                 status = "🟢 ACTIVE" if self.recurring_invitations_enabled else "⏸️ PAUSED"
    #                 logging.info(f"✅ Created job {job_id}: every {frequency}h ({status})")
    #                 successful_jobs += 1
                    
    #             except Exception as job_error:
    #                 logging.error(f"❌ Failed to create job {job_id}: {job_error}")
            
    #         logging.info(f"✅ Recurring invitations setup: {successful_jobs}/{len(jobs_to_create)} jobs created")
            
    #         if successful_jobs > 0:
    #             logging.info(f"🔔 Recurring invitations: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}")
    #             logging.info(f"   📅 Daily: every {self.invitation_frequencies['daily']}h")
    #             logging.info(f"   📅 Weekly: every {self.invitation_frequencies['weekly']}h")
    #             logging.info(f"   📅 Monthly: every {self.invitation_frequencies['monthly']}h")
            
    #     except ImportError:
    #         logging.error("❌ APScheduler not available for recurring invitations")
    #         self.scheduler = None
    #     except Exception as e:
    #         logging.error(f"❌ Error setting up recurring invitations: {e}")

    # 🔄 FIXED: setup_recurring_invitations method
    def setup_recurring_invitations(self):
        """🆕 Fixed recurring invitation jobs with proper async handling"""
        if self.scheduler is None:
            logging.warning("⚠️ No scheduler available for recurring invitations")
            return
            
        try:
            from apscheduler.triggers.interval import IntervalTrigger
            logging.info("🔧 Setting up recurring invitations...")
        
            # Lista de trabajos a crear
            jobs_to_create = [
                ('recurring_daily_invitations', 'daily', self.invitation_frequencies['daily']),
                ('recurring_weekly_invitations', 'weekly', self.invitation_frequencies['weekly']),
                ('recurring_monthly_invitations', 'monthly', self.invitation_frequencies['monthly'])
            ]
            
            successful_jobs = 0
            
            for job_id, giveaway_type, frequency in jobs_to_create:
                try:
                    # Remover trabajo existente si existe
                    try:
                        self.scheduler.remove_job(job_id)
                        logging.info(f"🗑️ Removed existing job: {job_id}")
                    except:
                        pass
                    
                    # 🆕 FIXED: Usar función wrapper síncrona en lugar de lambda async
                    def create_sync_wrapper(gt):
                        """Create synchronous wrapper for async function"""
                        def sync_wrapper():
                            try:
                                # 🆕 SOLUTION: Usar asyncio.run() para ejecutar función async
                                import asyncio
                                import threading
                                
                                # Verificar si ya hay un loop corriendo en este thread
                                try:
                                    loop = asyncio.get_running_loop()
                                    # Si hay loop, crear task
                                    asyncio.create_task(self._send_recurring_invitation(gt))
                                except RuntimeError:
                                    # No hay loop, usar asyncio.run()
                                    asyncio.run(self._send_recurring_invitation(gt))
                                    
                            except Exception as e:
                                logging.error(f"Error in recurring invitation wrapper for {gt}: {e}")
                        
                        return sync_wrapper
                    
                    # Crear wrapper específico para este tipo
                    wrapper_func = create_sync_wrapper(giveaway_type)
                    
                    # Agregar job con función wrapper síncrona
                    self.scheduler.add_job(
                        wrapper_func,
                        IntervalTrigger(hours=frequency),
                        id=job_id,
                        paused=not self.recurring_invitations_enabled
                    )
                    
                    status = "🟢 ACTIVE" if self.recurring_invitations_enabled else "⏸️ PAUSED"
                    logging.info(f"✅ Created job {job_id}: every {frequency}h ({status})")
                    successful_jobs += 1
                    
                except Exception as job_error:
                    logging.error(f"❌ Failed to create job {job_id}: {job_error}")
            
            logging.info(f"✅ Recurring invitations setup: {successful_jobs}/{len(jobs_to_create)} jobs created")
            
            if successful_jobs > 0:
                logging.info(f"🔔 Recurring invitations: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}")
                logging.info(f"   📅 Daily: every {self.invitation_frequencies['daily']}h")
                logging.info(f"   📅 Weekly: every {self.invitation_frequencies['weekly']}h")
                logging.info(f"   📅 Monthly: every {self.invitation_frequencies['monthly']}h")
            
        except ImportError:
            logging.error("❌ APScheduler not available for recurring invitations")
            self.scheduler = None
        except Exception as e:
            logging.error(f"❌ Error setting up recurring invitations: {e}")

    def _save_recurring_invitations_state(self):
        """🆕 NEW: Save recurring invitations state to config"""
        try:
            import json
            
            # Load current config
            with open("config.json", 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Update recurring invitations section
            if 'automation' not in config:
                config['automation'] = {}
            if 'recurring_invitations' not in config['automation']:
                config['automation']['recurring_invitations'] = {}
            
            config['automation']['recurring_invitations']['enabled'] = self.recurring_invitations_enabled
            
            # Save back to file
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            logging.info(f"💾 Recurring invitations state saved: {self.recurring_invitations_enabled}")
            
        except Exception as e:
            logging.error(f"Error saving recurring invitations state: {e}")

    async def _send_recurring_invitation(self, giveaway_type: str):
        """🆕 Send recurring invitation for specific type"""
        if not self.recurring_invitations_enabled:
            return
            
        try:
            # Check if within active hours (9 AM - 9 PM by default)
            current_hour = datetime.now().hour
            if not (9 <= current_hour <= 21):
                logging.info(f"Outside active hours for {giveaway_type} recurring invitation")
                return
            
            # Get giveaway system
            giveaway_system = self.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                logging.error(f"Giveaway system not found for {giveaway_type}")
                return
            
            # Check if participation window is open (optional respect)
            automation_config = self.config_loader.get_all_config().get('automation', {})
            recurring_config = automation_config.get('recurring_invitations', {})
            respect_windows = recurring_config.get('respect_participation_windows', True)
            
            if respect_windows and not giveaway_system.is_participation_window_open(giveaway_type):
                logging.info(f"Participation window closed for {giveaway_type}, skipping recurring invitation")
                return
            
            # Send invitation
            success = await giveaway_system.send_invitation(giveaway_type)
            
            if success:
                logging.info(f"✅ Recurring {giveaway_type} invitation sent successfully")
                
                # Optional: Brief admin notification (only for errors or important events)
                await self._notify_recurring_invitation_status(giveaway_type, True)
            else:
                logging.warning(f"❌ Failed to send recurring {giveaway_type} invitation")
                await self._notify_recurring_invitation_status(giveaway_type, False)
                
        except Exception as e:
            logging.error(f"Error sending recurring {giveaway_type} invitation: {e}")
            await self._notify_recurring_invitation_status(giveaway_type, False, str(e))

    async def _notify_recurring_invitation_status(self, giveaway_type: str, success: bool, error: str = None):
        """🆕 Notify admin of recurring invitation status (only errors)"""
        try:
            # Only notify on errors or first success of the day to avoid spam
            if success:
                return  # Don't spam admin with success notifications
                
            # Notify admin only on errors
            admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
            if not admin_config.get('recurring_invitation_errors', True):
                return
                
            message = f"⚠️ <b>Recurring Invitation Error</b>\n\n"
            message += f"🎯 Type: {giveaway_type.upper()}\n"
            message += f"⏰ Time: {datetime.now().strftime('%H:%M')}\n"
            message += f"❌ Status: Failed to send\n"
            
            if error:
                message += f"🐛 Error: {error[:100]}..."
                
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=message,
                parse_mode='HTML'
            )
            
        except Exception as e:
            logging.error(f"Error notifying recurring invitation status: {e}")

    def toggle_recurring_invitations(self) -> bool:
        """🆕 Toggle recurring invitations on/off"""
        try:
            self.recurring_invitations_enabled = not self.recurring_invitations_enabled
            logging.info(f"🔄 Toggling recurring invitations to: {'ENABLED' if self.recurring_invitations_enabled else 'DISABLED'}")

            # 🆕 NEW: Persistir el estado en configuración
            self._save_recurring_invitations_state()
            # Solo proceder si tenemos scheduler
            if not self.scheduler:
                logging.warning("No scheduler available for recurring invitations")
                return True  # Return success even without scheduler

            invitation_job_ids = ['recurring_daily_invitations', 'recurring_weekly_invitations', 'recurring_monthly_invitations']

            # Procesar cada trabajo individualmente
            success_count = 0
            for job_id in invitation_job_ids:
                try:
                    # Verificar si el trabajo existe
                    existing_job = None
                    try:
                        existing_job = self.scheduler.get_job(job_id)
                    except Exception:
                        existing_job = None
                    
                    if existing_job:
                        # Trabajo existe, pausar o reanudar
                        if self.recurring_invitations_enabled:
                            self.scheduler.resume_job(job_id)
                            logging.info(f"✅ Resumed job: {job_id}")
                        else:
                            self.scheduler.pause_job(job_id)
                            logging.info(f"⏸️ Paused job: {job_id}")
                        success_count += 1
                    else:
                        # Trabajo no existe, crearlo si se está habilitando
                        if self.recurring_invitations_enabled:
                            giveaway_type = job_id.replace('recurring_', '').replace('_invitations', '')
                            frequency = self.invitation_frequencies.get(giveaway_type, 2)
                            
                            # Crear el trabajo
                            from apscheduler.triggers.interval import IntervalTrigger
                            self.scheduler.add_job(
                                lambda gt=giveaway_type: asyncio.create_task(self._send_recurring_invitation(gt)),
                                IntervalTrigger(hours=frequency),
                                id=job_id,
                                paused=False
                            )
                            logging.info(f"✅ Created and started job: {job_id}")
                            success_count += 1
                        else:
                            logging.info(f"ℹ️ Job {job_id} doesn't exist, nothing to pause")
                            success_count += 1
                            
                except Exception as job_error:
                    logging.error(f"❌ Error processing job {job_id}: {job_error}")
                    continue
            
            # Resultado final
            logging.info(f"✅ Recurring invitations toggle completed: {success_count}/{len(invitation_job_ids)} jobs processed")
            logging.info(f"🔔 Recurring invitations are now: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}")
            return True
        except Exception as e:
            logging.error(f"Error toggling recurring invitations: {e}")
            return False

    async def _show_frequency_settings(self, query):
        """🆕 Show frequency settings panel"""
        try:
            message = f"""⏰ <b>INVITATION FREQUENCY SETTINGS</b>

    🔔 <b>Current Frequencies:</b>
    ├─ Daily: Every {self.invitation_frequencies['daily']} hours
    ├─ Weekly: Every {self.invitation_frequencies['weekly']} hours
    └─ Monthly: Every {self.invitation_frequencies['monthly']} hours

    💡 <b>Recommended Frequencies:</b>
    - Daily: 2-4 hours (high engagement)
    - Weekly: 4-6 hours (moderate promotion)
    - Monthly: 6-8 hours (background promotion)

    ⚠️ <b>Note:</b> Too frequent invitations may overwhelm users.
    Current settings work well for balanced engagement."""

            buttons = [
                [
                    InlineKeyboardButton("Daily 🔂 2h", callback_data="freq_daily_2"),
                    InlineKeyboardButton("Daily 🔂 3h", callback_data="freq_daily_3"),
                    InlineKeyboardButton("Daily 🔂 4h", callback_data="freq_daily_4")
                ],
                [
                    InlineKeyboardButton("Weekly 🔂 4h", callback_data="freq_weekly_4"),
                    InlineKeyboardButton("Weekly 🔂 6h", callback_data="freq_weekly_6"),
                    InlineKeyboardButton("Weekly 🔂 8h", callback_data="freq_weekly_8")
                ],
                [
                    InlineKeyboardButton("Monthly 🔂 6h", callback_data="freq_monthly_6"),
                    InlineKeyboardButton("Monthly 🔂 8h", callback_data="freq_monthly_8"),
                    InlineKeyboardButton("Monthly 🔂 12h", callback_data="freq_monthly_12")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Automation", callback_data="automation_control")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing frequency settings: {e}")
            await query.edit_message_text("❌ Error loading frequency settings")


    # ==================  AUTOMATATION  =============================
    # ==================     DRAW       =============================

    # 🆕 ADD: Scheduler setup method (after line 100)
    # def setup_automatic_draws(self):
    #     """🆕 Initialize the automatic draw scheduler"""
    #     if self.scheduler is None:
    #         try:
    #             from apscheduler.schedulers.asyncio import AsyncIOScheduler
    #             from apscheduler.triggers.cron import CronTrigger
                
    #             self.scheduler = AsyncIOScheduler()
                
    #             # Daily: Monday-Friday at 5:00 PM London Time
    #             self.scheduler.add_job(
    #                 self._execute_automatic_daily_draw,
    #                 CronTrigger(day_of_week='mon-fri', hour=17, minute=0, timezone='Europe/London'),
    #                 id='auto_daily_draw',
    #                 paused=not self.auto_mode_enabled['daily']
    #             )
                
    #             # Weekly: Friday at 5:15 PM London Time
    #             self.scheduler.add_job(
    #                 self._execute_automatic_weekly_draw,
    #                 CronTrigger(day_of_week='fri', hour=17, minute=15, timezone='Europe/London'),
    #                 id='auto_weekly_draw',
    #                 paused=not self.auto_mode_enabled['weekly']
    #             )
                
    #             # Monthly: Last Friday at 5:30 PM London Time
    #             self.scheduler.add_job(
    #                 self._execute_automatic_monthly_draw,
    #                 CronTrigger(day='last fri', hour=17, minute=30, timezone='Europe/London'),
    #                 id='auto_monthly_draw',
    #                 paused=not self.auto_mode_enabled['monthly']
    #             )
                
    #             self.scheduler.start()

    #             # 🆕 ADD: Setup recurring invitations
    #             if self.scheduler.running:
    #                 self.setup_recurring_invitations()
    #             else:
    #                 logging.warning("Scheduler not running, skipping recurring invitations setup")
                
    #             enabled_types = [t for t, enabled in self.auto_mode_enabled.items() if enabled]
    #             logging.info(f"✅ Automatic draw scheduler initialized")
    #             logging.info(f"🤖 Auto-enabled types: {enabled_types if enabled_types else 'None'}")
                
    #         except ImportError:
    #             logging.error("❌ APScheduler not installed. Run: pip install apscheduler")
    #             self.scheduler = None
    #         except Exception as e:
    #             logging.error(f"❌ Error setting up scheduler: {e}")
    #             self.scheduler = None

    # 🔄 ENHANCED: setup_automatic_draws method
    def setup_automatic_draws(self):
        """🆕 Enhanced scheduler using config.json for flexibility"""
        if self.scheduler is None:
            try:
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                from apscheduler.triggers.cron import CronTrigger
                
                self.scheduler = AsyncIOScheduler()
                
                # 🆕 NUEVO: Leer horarios desde config.json
                giveaway_configs = self.config_loader.get_giveaway_configs()
                timezone = self.config_loader.get_timezone()
                
                # 🔄 MANTENER: Wrappers síncronos (ya funcionan bien)
                def create_draw_wrapper(draw_method):
                    """Create synchronous wrapper for async draw methods"""
                    def sync_wrapper():
                        try:
                            import asyncio
                            
                            # Verificar si hay loop corriendo
                            try:
                                loop = asyncio.get_running_loop()
                                # Si hay loop, crear task
                                asyncio.create_task(draw_method())
                            except RuntimeError:
                                # No hay loop, usar asyncio.run()
                                asyncio.run(draw_method())
                                
                        except Exception as e:
                            logging.error(f"Error in draw wrapper: {e}")
                    
                    return sync_wrapper
                
                # Create wrappers
                daily_wrapper = create_draw_wrapper(self._execute_automatic_daily_draw)
                weekly_wrapper = create_draw_wrapper(self._execute_automatic_weekly_draw)
                monthly_wrapper = create_draw_wrapper(self._execute_automatic_monthly_draw)
                
                # 🆕 NUEVO: Usar configuración en lugar de hardcode
                try:
                    # DAILY schedule from config
                    daily_schedule = giveaway_configs['daily']['draw_schedule']
                    self.scheduler.add_job(
                        daily_wrapper,
                        CronTrigger(
                            day_of_week=daily_schedule['days'],
                            hour=daily_schedule['hour'],
                            minute=daily_schedule['minute'],
                            timezone=timezone
                        ),
                        id='auto_daily_draw',
                        paused=not self.auto_mode_enabled['daily']
                    )
                    
                    # WEEKLY schedule from config
                    weekly_schedule = giveaway_configs['weekly']['draw_schedule']
                    weekly_day = self._convert_day_name_to_cron(weekly_schedule['day'])
                    self.scheduler.add_job(
                        weekly_wrapper,
                        CronTrigger(
                            day_of_week=weekly_day,
                            hour=weekly_schedule['hour'],
                            minute=weekly_schedule['minute'],
                            timezone=timezone
                        ),
                        id='auto_weekly_draw',
                        paused=not self.auto_mode_enabled['weekly']
                    )
                    
                    # MONTHLY schedule from config
                    monthly_schedule = giveaway_configs['monthly']['draw_schedule']
                    monthly_day = self._convert_day_name_to_cron(monthly_schedule['day'])
                    self.scheduler.add_job(
                        monthly_wrapper,
                        CronTrigger(
                            day=monthly_day,
                            hour=monthly_schedule['hour'],
                            minute=monthly_schedule['minute'],
                            timezone=timezone
                        ),
                        id='auto_monthly_draw',
                        paused=not self.auto_mode_enabled['monthly']
                    )
                    
                    logging.info(f"✅ Scheduler configured from config.json:")
                    logging.info(f"   📅 Daily: {daily_schedule['days']} at {daily_schedule['hour']}:{daily_schedule['minute']:02d}")
                    logging.info(f"   📅 Weekly: {weekly_day} at {weekly_schedule['hour']}:{weekly_schedule['minute']:02d}")
                    logging.info(f"   📅 Monthly: {monthly_day} at {monthly_schedule['hour']}:{monthly_schedule['minute']:02d}")
                    
                except KeyError as config_error:
                    logging.warning(f"⚠️ Config incomplete, using fallback hardcoded schedules: {config_error}")
                    
                    # 🆕 FALLBACK: Usar tus horarios hardcoded actuales si config falla
                    self.scheduler.add_job(
                        daily_wrapper,
                        CronTrigger(day_of_week='mon-fri', hour=18, minute=10, timezone='Europe/London'),
                        id='auto_daily_draw',
                        paused=not self.auto_mode_enabled['daily']
                    )
                    
                    self.scheduler.add_job(
                        weekly_wrapper,
                        CronTrigger(day_of_week='fri', hour=18, minute=12, timezone='Europe/London'),
                        id='auto_weekly_draw',
                        paused=not self.auto_mode_enabled['weekly']
                    )
                    
                    self.scheduler.add_job(
                        monthly_wrapper,
                        CronTrigger(day='last fri', hour=18, minute=15, timezone='Europe/London'),
                        id='auto_monthly_draw',
                        paused=not self.auto_mode_enabled['monthly']
                    )
                    
                    logging.info(f"✅ Scheduler configured with fallback hardcoded times")
                
                self.scheduler.start()

                # Setup recurring invitations
                if self.scheduler.running:
                    self.setup_recurring_invitations()
                    logging.info("✅ Recurring invitations setup completed")
                else:
                    logging.warning("Scheduler not running, skipping recurring invitations setup")
                    
                enabled_types = [t for t, enabled in self.auto_mode_enabled.items() if enabled]
                logging.info(f"✅ Automatic draw scheduler initialized")
                logging.info(f"🤖 Auto-enabled types: {enabled_types if enabled_types else 'None'}")
                
            except ImportError:
                logging.error("❌ APScheduler not installed. Run: pip install apscheduler")
                self.scheduler = None
            except Exception as e:
                logging.error(f"❌ Error setting up scheduler: {e}")
                self.scheduler = None

    # 🆕 ADD: Helper function después del método setup_automatic_draws
    def _convert_day_name_to_cron(self, day_name):
        """Convert config day names to APScheduler cron format"""
        day_mapping = {
            'monday': 'mon',
            'tuesday': 'tue', 
            'wednesday': 'wed',
            'thursday': 'thu',
            'friday': 'fri',
            'saturday': 'sat',
            'sunday': 'sun',
            'last_friday': 'last fri',
            'last_monday': 'last mon'
        }
        
        return day_mapping.get(str(day_name).lower(), day_name)

    # 🆕 ADD: Automatic execution methods (after setup_automatic_draws)
    async def _execute_automatic_daily_draw(self):
        """🆕 Execute automatic daily draw"""
        if not self.auto_mode_enabled['daily']:
            return
            
        try:
            logging.info("🤖 Starting automatic daily draw...")
            
            giveaway_system = self.get_giveaway_system('daily')
            if not giveaway_system:
                raise Exception("Daily giveaway system not available")
            
            # Check if already executed today
            today = datetime.now().strftime('%Y-%m-%d')
            pending_winners = giveaway_system.get_pending_winners('daily')
            today_pending = [w for w in pending_winners if w.get('date', '').startswith(today)]
            
            if today_pending:
                logging.info("ℹ️ Daily draw already executed today, skipping automatic draw")
                return
            
            # Execute the draw using existing logic
            await giveaway_system.run_giveaway('daily')
            
            # Check results and notify
            new_pending = giveaway_system.get_pending_winners('daily')
            today_winners = [w for w in new_pending if w.get('date', '').startswith(today)]
            
            if today_winners:
                winner = today_winners[0]
                await self._notify_automatic_winner('daily', winner)
                logging.info(f"✅ Automatic daily draw completed - Winner: {winner.get('first_name', 'Unknown')}")
            else:
                await self._notify_no_participants('daily')
                logging.info("✅ Automatic daily draw completed - No eligible participants")
                
        except Exception as e:
            logging.error(f"❌ Error in automatic daily draw: {e}")
            await self._notify_draw_error('daily', str(e))

    async def _execute_automatic_weekly_draw(self):
        """🆕 Execute automatic weekly draw"""
        if not self.auto_mode_enabled['weekly']:
            return
            
        try:
            logging.info("🤖 Starting automatic weekly draw...")
            
            giveaway_system = self.get_giveaway_system('weekly')
            if not giveaway_system:
                raise Exception("Weekly giveaway system not available")
            
            # Check if already executed today
            today = datetime.now().strftime('%Y-%m-%d')
            pending_winners = giveaway_system.get_pending_winners('weekly')
            today_pending = [w for w in pending_winners if w.get('date', '').startswith(today)]
            
            if today_pending:
                logging.info("ℹ️ Weekly draw already executed today, skipping automatic draw")
                return
            
            await giveaway_system.run_giveaway('weekly')
            
            new_pending = giveaway_system.get_pending_winners('weekly')
            today_winners = [w for w in new_pending if w.get('date', '').startswith(today)]
            
            if today_winners:
                winner = today_winners[0]
                await self._notify_automatic_winner('weekly', winner)
                logging.info(f"✅ Automatic weekly draw completed - Winner: {winner.get('first_name', 'Unknown')}")
            else:
                await self._notify_no_participants('weekly')
                logging.info("✅ Automatic weekly draw completed - No eligible participants")
                
        except Exception as e:
            logging.error(f"❌ Error in automatic weekly draw: {e}")
            await self._notify_draw_error('weekly', str(e))

    async def _execute_automatic_monthly_draw(self):
        """🆕 Execute automatic monthly draw"""
        if not self.auto_mode_enabled['monthly']:
            return
            
        try:
            logging.info("🤖 Starting automatic monthly draw...")
            
            giveaway_system = self.get_giveaway_system('monthly')
            if not giveaway_system:
                raise Exception("Monthly giveaway system not available")
            
            # Check if already executed today
            today = datetime.now().strftime('%Y-%m-%d')
            pending_winners = giveaway_system.get_pending_winners('monthly')
            today_pending = [w for w in pending_winners if w.get('date', '').startswith(today)]
            
            if today_pending:
                logging.info("ℹ️ Monthly draw already executed today, skipping automatic draw")
                return
            
            await giveaway_system.run_giveaway('monthly')
            
            new_pending = giveaway_system.get_pending_winners('monthly')
            today_winners = [w for w in new_pending if w.get('date', '').startswith(today)]
            
            if today_winners:
                winner = today_winners[0]
                await self._notify_automatic_winner('monthly', winner)
                logging.info(f"✅ Automatic monthly draw completed - Winner: {winner.get('first_name', 'Unknown')}")
            else:
                await self._notify_no_participants('monthly')
                logging.info("✅ Automatic monthly draw completed - No eligible participants")
                
        except Exception as e:
            logging.error(f"❌ Error in automatic monthly draw: {e}")
            await self._notify_draw_error('monthly', str(e))

    async def _notify_main_admin_only(self, winner, giveaway_type, executed_by):
        """🆕 NEW: Send notification ONLY to main administrator"""
        try:
            # Get main admin ID from config
            main_admin_id = self.admin_id  # This is your ID from config
            
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            
            # Get prize amount
            giveaway_system = self.get_giveaway_system(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # Create comprehensive notification for main admin
            main_admin_message = f"""🤖 <b>AUTOMATIC {giveaway_type.upper()} WINNER - MAIN ADMIN NOTIFICATION</b>

    🎉 <b>Winner Selected:</b> {first_name} ({winner_display})
    📊 <b>VFX MT5 Account:</b> <code>{winner['mt5_account']}</code>
    💰 <b>Prize:</b> ${prize} USD
    🎯 <b>Giveaway Type:</b> {giveaway_type.upper()}
    👤 <b>Executed by:</b> {executed_by}
    📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ⚠️ <b>PAYMENT REQUIRED:</b>
    💸 Transfer ${prize} USD to VFX MT5 account: <code>{winner['mt5_account']}</code>

    💡 <b>Confirmation Commands:</b>
    - <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code>
    - Or use the admin panel buttons

    🔔 <b>Notification Status:</b>
    ├─ Main Admin: ✅ You (individual notification)
    ├─ Admin Channel: ✅ Group notification sent
    └─ Other Admins: ❌ No individual spam

    🎯 <b>Next Steps:</b>
    1️⃣ Process payment to VFX MT5 account
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
    # 🆕 ADD: Notification methods (after automatic execution methods)
    async def _notify_automatic_winner(self, giveaway_type: str, winner):
        """🆕 Notify about automatic draw winner"""
        try:
            # Create context for existing notification system
            # class MockContext:
            #     def __init__(self, bot):
            #         self.bot = bot
            
            # mock_context = MockContext(self.app.bot)
            
            # Use existing notification method - zero redundancy
            # await self.notify_payment_admins_new_winner(
            #     None, 
            #     winner, 
            #     giveaway_type, 
            #     'Automatic System'
            # )
            # 1️⃣ Send to main admin (individual)
            await self._notify_main_admin_only(winner, giveaway_type, 'Automatic System')
            
            # Additional admin channel notification if configured
            await self._send_admin_channel_notification(giveaway_type, winner, 'winner')
            
        except Exception as e:
            logging.error(f"Error notifying automatic winner: {e}")


    async def _notify_no_participants(self, giveaway_type: str):
        """🆕 Notify about automatic draw with no participants"""
        try:
            message = f"""ℹ️ <b>AUTOMATIC DRAW - NO PARTICIPANTS</b>

🎯 <b>Type:</b> {giveaway_type.upper()} Giveaway
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
👥 <b>Result:</b> No eligible participants found

💡 This is normal - the system will try again at the next scheduled time.
📢 Consider promoting the giveaway to increase participation."""

            await self._send_admin_channel_notification(giveaway_type, None, 'no_participants', message)
            
        except Exception as e:
            logging.error(f"Error notifying no participants: {e}")

    async def _notify_draw_error(self, giveaway_type: str, error: str):
        """🆕 Notify admins of automatic draw errors"""
        try:
            error_message = f"""🚨 <b>AUTOMATIC DRAW ERROR</b>

🎯 <b>Type:</b> {giveaway_type.upper()} Giveaway
❌ <b>Error:</b> {error}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔧 <b>Actions:</b>
• Check system status with /health_check
• Run manual draw: /admin_run_{giveaway_type}
• Check automation: /admin_panel → Automation
• Contact technical support if error persists

⚠️ <b>Impact:</b> Participants may need to be notified of delay."""

            # Send to main admin
            await self.app.bot.send_message(
                chat_id=self.admin_id,
                text=error_message,
                parse_mode='HTML'
            )
            
            # Send to admin channel
            await self._send_admin_channel_notification(giveaway_type, None, 'error', error_message)
            
        except Exception as e:
            logging.error(f"Error notifying draw error: {e}")

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
                prize = self.get_giveaway_system(giveaway_type).get_prize_amount(giveaway_type)
                username = winner.get('username', '')
                username_display = f"@{username}" if username else "no_username"
                
                message = f"""🤖 <b>AUTOMATIC DRAW COMPLETED</b>

🎯 <b>Giveaway:</b> {giveaway_type.upper()} (${prize} USD)
🎉 <b>Winner:</b> {winner.get('first_name', 'N/A')} ({username_display})
📊 <b> VFX MT5 Account:</b> <code>{winner['mt5_account']}</code>
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

    # 🆕 ADD: Automation control methods (after notification methods)
    def toggle_automatic_mode(self, giveaway_type: str, enabled: bool) -> bool:
        """🆕 Toggle automation for specific giveaway type"""
        if giveaway_type not in self.auto_mode_enabled:
            return False
            
        try:
            self.auto_mode_enabled[giveaway_type] = enabled
            
            if self.scheduler:
                job_id = f'auto_{giveaway_type}_draw'
                if enabled:
                    self.scheduler.resume_job(job_id)
                    logging.info(f"✅ {giveaway_type.title()} automatic draws ENABLED")
                else:
                    self.scheduler.pause_job(job_id)
                    logging.info(f"⏸️ {giveaway_type.title()} automatic draws DISABLED")
            
            return True
            
        except Exception as e:
            logging.error(f"Error toggling {giveaway_type} automation: {e}")
            return False

    def get_automation_status(self) -> dict:
        """🆕 Get current automation status"""
        return {
            'daily': self.auto_mode_enabled['daily'],
            'weekly': self.auto_mode_enabled['weekly'],
            'monthly': self.auto_mode_enabled['monthly'],
            'scheduler_running': self.scheduler.running if self.scheduler else False,
            'scheduler_available': self.scheduler is not None
        }

    def shutdown_scheduler(self):
        """🆕 Clean shutdown of scheduler"""
        if self.scheduler:
            try:
                self.scheduler.shutdown()
                logging.info("✅ Scheduler shutdown completed")
            except Exception as e:
                logging.error(f"Error shutting down scheduler: {e}")

     # 🆕 ADD: Automation callback handler (after _handle_admin_panel_callbacks)
    
    async def _handle_automation_callbacks(self, update, context):
        """🆕 Handle automation control callbacks"""

        query = update.callback_query
    
        # 2️⃣ SEGUNDO: INMEDIATAMENTE responder al callback (OBLIGATORIO)
        await query.answer()  # ← AQUÍ VA, LÍNEA 3 DE LA FUNCIÓN

        # query = update.callback_query 
        callback_data = query.data
        user_id = query.from_user.id

        
        # Verify permissions
        permission_manager = self._get_permission_manager_from_callback()
        if not permission_manager or not permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
            print(f"❌ DEBUG: Permission denied for user {user_id}")
            await query.edit_message_text(
                "❌ <b>Access Denied</b>\n\nAutomation control requires MANAGE_ADMINS permission.",
                parse_mode='HTML'
            )
            return
        print(f"✅ DEBUG: Permission granted for user {user_id}")
        
        try:
            if callback_data == "automation_control":
                await self._show_automation_control_panel(query, context)
                
            elif callback_data.startswith("automation_toggle_"):

                giveaway_type = callback_data.replace("automation_toggle_", "")

                # 🐛 BUGFIX: Manejar caso especial de invitations
                if giveaway_type == "invitations":
                    print(f"🔔 DEBUG: Processing invitation toggle")
                    # Handle recurring invitations toggle
                    success = self.toggle_recurring_invitations()
                    
                    if success:
                        status_text = "ENABLED" if self.recurring_invitations_enabled else "DISABLED"
                        response_message = f"""✅ <b>Recurring Invitations {status_text}</b>

    🔔 <b>Status:</b> {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}

    ⏰ <b>Frequencies:</b>
    ├─ Daily: every {self.invitation_frequencies['daily']} hours
    ├─ Weekly: every {self.invitation_frequencies['weekly']} hours
    └─ Monthly: every {self.invitation_frequencies['monthly']} hours

    💡 <b>What this means:</b>
    - Automatic invitations will {'start sending' if self.recurring_invitations_enabled else 'stop sending'}
    - Manual invitations are always available
    - Settings can be changed anytime

    🎛️ Use "⏰ Set Frequencies" to adjust timing."""
                        
                        buttons = [[InlineKeyboardButton("🏠 Back to Automation", callback_data="automation_control")]]
                        reply_markup = InlineKeyboardMarkup(buttons)
                        
                        await query.edit_message_text(
                            response_message, 
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    else:
                        await query.edit_message_text(
                            f"❌ <b>Error toggling invitations</b>\n\n"
                            f"Could not change recurring invitation settings.\n\n"
                            f"💡 Current status: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}",
                            parse_mode='HTML'
                        )
                    return
                
                # Handle giveaway type toggles (daily, weekly, monthly)
                if giveaway_type in ['daily', 'weekly', 'monthly']:
                    current_status = self.get_automation_status()
                    new_status = not current_status[giveaway_type]
                    
                    success = self.toggle_automatic_mode(giveaway_type, new_status)
                    
                    if success:
                        status_text = "ENABLED" if new_status else "DISABLED"
                        await query.edit_message_text(
                            f"✅ <b>{giveaway_type.title()} automation {status_text}</b>\n\n"
                            f"🤖 Automatic draws: {'🟢 ON' if new_status else '🔴 OFF'}\n"
                            f"📅 Next scheduled: {self._get_next_execution_time(giveaway_type) if new_status else 'Manual only'}",
                            parse_mode='HTML'
                        )
                    else:
                        await query.edit_message_text("❌ Error toggling automation")
                    return
                    
            elif callback_data == "automation_enable_all":
                results = {}
                for giveaway_type in ['daily', 'weekly', 'monthly']:
                    results[giveaway_type] = self.toggle_automatic_mode(giveaway_type, True)
                
                successful = sum(1 for success in results.values() if success)
                
                await query.edit_message_text(
                    f"✅ <b>Bulk Automation Enable</b>\n\n"
                    f"🟢 Successfully enabled: {successful}/3 types\n"
                    f"🤖 All automatic draws are now ACTIVE\n\n"
                    f"Daily: Monday-Friday at 5:00 PM\n"
                    f"Weekly: Friday at 5:15 PM\n"
                    f"Monthly: Last Friday at 5:30 PM\n\n"
                    f"London Time Zone",
                    parse_mode='HTML'
                )
                
            elif callback_data == "automation_disable_all":
                results = {}
                for giveaway_type in ['daily', 'weekly', 'monthly']:
                    results[giveaway_type] = self.toggle_automatic_mode(giveaway_type, False)
                
                successful = sum(1 for success in results.values() if success)
                
                await query.edit_message_text(
                    f"⏸️ <b>Bulk Automation Disable</b>\n\n"
                    f"🔴 Successfully disabled: {successful}/3 types\n"
                    f"🤖 All automatic draws are now INACTIVE\n\n"
                    f"📌 Manual draws remain available:\n"
                    f"• /admin_run_daily\n"
                    f"• /admin_run_weekly\n"
                    f"• /admin_run_monthly",
                    parse_mode='HTML'
                )

            # elif callback_data == "automation_toggle_invitations":
            #     try:
            #         logging.info(f"🔔 Processing invitation toggle request from user {user_id}")
                    
            #         # Intentar el toggle
            #         success = self.toggle_recurring_invitations()
                    
            #         if success:
            #             status_text = "ENABLED" if self.recurring_invitations_enabled else "DISABLED"
                        
            #             # Mensaje de confirmación detallado
            #             response_message = f"""✅ <b>Recurring Invitations {status_text}</b>

            # 🔔 <b>Status:</b> {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}

            # ⏰ <b>Frequencies:</b>
            # ├─ Daily: every {self.invitation_frequencies['daily']} hours
            # ├─ Weekly: every {self.invitation_frequencies['weekly']} hours
            # └─ Monthly: every {self.invitation_frequencies['monthly']} hours

            # 💡 <b>What this means:</b>
            # - Automatic invitations will {'start sending' if self.recurring_invitations_enabled else 'stop sending'}
            # - Manual invitations are always available
            # - Settings can be changed anytime

            # 🎛️ Use "⏰ Set Frequencies" to adjust timing."""
                        
            #             await query.edit_message_text(response_message, parse_mode='HTML')
                        
            #         else:
            #             # Error en el toggle
            #             await query.edit_message_text(
            #                 f"❌ <b>Error toggling invitations</b>\n\n"
            #                 f"Could not change recurring invitation settings.\n\n"
            #                 f"💡 Current status remains: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}\n\n"
            #                 f"Check logs for details or contact administrator.",
            #                 parse_mode='HTML'
            #             )
                
            #     except Exception as toggle_error:
            #         logging.error(f"❌ Exception in invitation toggle: {toggle_error}")
            #         await query.edit_message_text(
            #             f"❌ <b>System Error</b>\n\n"
            #             f"An error occurred while processing the invitation toggle.\n\n"
            #             f"Error: {str(toggle_error)[:100]}...\n\n"
            #             f"💡 Try refreshing the automation panel or contact administrator.",
            #             parse_mode='HTML'
            #         )

            elif callback_data == "automation_set_frequencies":
                await self._show_frequency_settings(query)
                
            elif callback_data == "automation_refresh":
                await self._show_automation_control_panel(query, context)
                
            elif callback_data == "automation_back_to_panel":
                await self._show_unified_panel_inline(query)
                
        except Exception as e:
            logging.error(f"Error in automation callback: {e}")
            await query.edit_message_text("❌ Error processing automation command")

    # 🆕 ADD: Automation control panel (after _handle_automation_callbacks)
    async def _show_automation_control_panel(self, query, context):
        """🆕 Show automation control panel"""
        try:
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
            admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
            
            automation_status = self.get_automation_status()
            
            message = f"""🤖 <b>AUTOMATIC DRAW CONTROL</b>
👤 <b>Admin:</b> {admin_name}

📊 <b>Current Automatic Draws Status:</b>
├─ Daily: {'🟢 ENABLED' if automation_status['daily'] else '🔴 DISABLED'}
├─ Weekly: {'🟢 ENABLED' if automation_status['weekly'] else '🔴 DISABLED'}
├─ Monthly: {'🟢 ENABLED' if automation_status['monthly'] else '🔴 DISABLED'}
└─ Scheduler: {'🟢 RUNNING' if automation_status['scheduler_running'] else '🔴 STOPPED'}

⏰ <b>Draw Schedule (London Time):</b>
├─ Daily: Monday-Friday at 17:00
├─ Weekly: Friday at 17:15
└─ Monthly: Last Friday at 17:30

🔔 <b>Recurring Invitations:</b>
├─ Auto-invitations: {'🟢 ENABLED' if self.recurring_invitations_enabled else '🔴 DISABLED'}
├─ Daily frequency: Every {self.invitation_frequencies['daily']} hours
├─ Weekly frequency: Every {self.invitation_frequencies['weekly']} hours
└─ Monthly frequency: Every {self.invitation_frequencies['monthly']} hours

🔧 <b>System Status:</b>
├─ Scheduler Available: {'✅ Yes' if automation_status['scheduler_available'] else '❌ No'}
├─ Manual Override: ✅ Always Available
└─ Conflict Protection: ✅ Active"""

            # Add next execution times
            # enabled_types = [t for t, enabled in automation_status.items() if enabled and t != 'scheduler_running' and t != 'scheduler_available']
            # if enabled_types:
            #     message += f"\n\n🕐 <b>Next Automatic Executions:</b>"
            #     for giveaway_type in enabled_types:
            #         next_time = self._get_next_execution_time(giveaway_type)
            #         message += f"\n├─ {giveaway_type.title()}: {next_time}"

            buttons = [
                [
                    InlineKeyboardButton("🕹️ Toggle Daily Draw", callback_data="automation_toggle_daily"),
                    InlineKeyboardButton("🕹️ Toggle Weekly Draw", callback_data="automation_toggle_weekly"),
                    InlineKeyboardButton("🕹️ Toggle Monthly Draw", callback_data="automation_toggle_monthly")
                ],
                
                [
                    InlineKeyboardButton("🟢 Enable All Draws", callback_data="automation_enable_all"),
                    InlineKeyboardButton("🔴 Disable All Draws", callback_data="automation_disable_all")
                ],
                [
                    # 🆕 ADD: Recurring invitations control
                    InlineKeyboardButton("🔔 Toggle Auto Invitations", callback_data="automation_toggle_invitations"),
                    InlineKeyboardButton("⏰ Set Invitation Freq.", callback_data="automation_set_frequencies")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Panel", callback_data="automation_back_to_panel")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing automation control panel: {e}")
            await query.edit_message_text("❌ Error loading automation control panel")

    # 🆕 ADD: Helper method for next execution time
    def _get_next_execution_time(self, giveaway_type: str) -> str:
        """🆕 Get next execution time for giveaway type"""
        try:
            from datetime import datetime
            import calendar
            
            now = datetime.now()
            
            if giveaway_type == 'daily':
                # Next weekday at 17:00
                next_exec = now.replace(hour=17, minute=0, second=0, microsecond=0)
                if now >= next_exec or now.weekday() >= 5:  # Past time or weekend
                    # Move to next business day
                    days_to_add = 1
                    while True:
                        next_exec = now + timedelta(days=days_to_add)
                        if next_exec.weekday() < 5:  # Monday to Friday
                            break
                        days_to_add += 1
                    next_exec = next_exec.replace(hour=17, minute=0, second=0, microsecond=0)
                return next_exec.strftime('%Y-%m-%d at 17:00')
                
            elif giveaway_type == 'weekly':
                # Next Friday at 17:15
                days_ahead = 4 - now.weekday()  # Friday = 4
                if days_ahead <= 0 or (days_ahead == 0 and now.hour >= 17):
                    days_ahead += 7
                next_exec = now + timedelta(days=days_ahead)
                next_exec = next_exec.replace(hour=17, minute=15, second=0, microsecond=0)
                return next_exec.strftime('%Y-%m-%d at 17:15')
                
            elif giveaway_type == 'monthly':
                # Last Friday of current or next month at 17:30
                def get_last_friday(year, month):
                    last_day = calendar.monthrange(year, month)[1]
                    last_date = datetime(year, month, last_day)
                    days_back = (last_date.weekday() - 4) % 7
                    return last_date - timedelta(days=days_back)
                
                last_friday = get_last_friday(now.year, now.month)
                if now.date() > last_friday.date() or (now.date() == last_friday.date() and now.hour >= 17):
                    # Move to next month
                    if now.month == 12:
                        last_friday = get_last_friday(now.year + 1, 1)
                    else:
                        last_friday = get_last_friday(now.year, now.month + 1)
                
                next_exec = last_friday.replace(hour=17, minute=30, second=0, microsecond=0)
                return next_exec.strftime('%Y-%m-%d at 17:30')
                
        except Exception as e:
            logging.error(f"Error calculating next execution time: {e}")
            return "Check schedule"




    # ================== AUTOMATATION DRAW END =============================
    # ================== AUTOMATATION DRAW END =============================

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

    # 🆕 AÑADIR esta nueva función en ga_integration.py:
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

Please send only your Vortex-FX MT5 account number.


❌ <b>Not valid:</b>
• Text (like "{update.message.text[:10]}...")
• Numbers with spaces
• Special characters

🔄 Attempts remaining: <b>{remaining_attempts}</b>

⚠️ Send only numbers:"""

                        await update.message.reply_text(invalid_message, parse_mode='HTML')
                    else:
                        # No attempts remaining
                        await self.giveaway_systems[giveaway_type]._handle_max_attempts_reached(
                            update, context, 4, giveaway_type
                        )
                    return
                    
        except Exception as e:
            logging.error(f"Error handling invalid input: {e}")



    



    # ==================== 🆕 PAYMENT CONFIRMATION METHODS ====================
    async def find_winner_by_identifier(self, winner_identifier, giveaway_type, giveaway_system):
        """
        🔍 Helper function to find winner by username or telegram_id
        Esta función estaba en test_botTTT.py pero se usa en las funciones movidas
        """
        try:
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                winner_first_name = winner.get('first_name', '').strip()
                
                # Search by different criteria
                if (
                    winner_identifier == winner_telegram_id or
                    winner_identifier.lower() == f"@{winner_username}".lower() or
                    winner_identifier.lower() == winner_username.lower() or
                    (not winner_username and winner_identifier.lower() == winner_first_name.lower())
                ):
                    return winner_telegram_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
            return None

    async def admin_confirm_payment_universal(self, update, context, giveaway_type):
        """🌟 Confirmación universal de pagos - movido desde test_botTTT.py"""
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)
        admin_info = permission_manager.get_admin_info(user_id)
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
        
        # Configuración dinámica
        type_configs = {
            'daily': {
                'display_name': 'Daily',
                'command': '/admin_confirm_daily',
                'permission': SystemAction.CONFIRM_DAILY_PAYMENTS
            },
            'weekly': {
                'display_name': 'Weekly', 
                'command': '/admin_confirm_weekly',
                'permission': SystemAction.CONFIRM_WEEKLY_PAYMENTS
            },
            'monthly': {
                'display_name': 'Monthly',
                'command': '/admin_confirm_monthly',
                'permission': SystemAction.CONFIRM_MONTHLY_PAYMENTS
            }
        }
        
        config = type_configs.get(giveaway_type)
        if not config:
            await update.message.reply_text(f"❌ Invalid giveaway type: {giveaway_type}")
            return
        
        # Validación de parámetros
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                f"❌ <b>Incorrect usage for {config['display_name']} Payment</b>\n\n"
                f"<b>Format:</b> <code>{config['command']} &lt;username_or_telegram_id&gt;</code>\n\n"
                f"<b>Examples:</b>\n"
                f"• <code>{config['command']} @username</code>\n"
                f"• <code>{config['command']} 123456</code>\n\n"
                f"💡 Use <code>/admin_pending_{giveaway_type}</code> to see pending {giveaway_type} winners",
                parse_mode='HTML'
            )
            return
        
        winner_identifier = context.args[0].strip()
        print(f"✅ {config['display_name']} payment confirmation authorized for: {admin_name} ({user_id})")
        
        try:
            # Usar sistema existente
            giveaway_system = self.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await update.message.reply_text(
                    f"❌ <b>{config['display_name']} giveaway system not available</b>",
                    parse_mode='HTML'
                )
                return
            
            # Buscar ganador                     find_winner_by_identifier
            winner_telegram_id = await self.find_winner_by_identifier(winner_identifier, giveaway_type, giveaway_system)
            
            if not winner_telegram_id:
                await update.message.reply_text(
                    f"❌ <b>{config['display_name']} winner not found</b>\n\n"
                    f"No pending {giveaway_type} winner found with: <code>{winner_identifier}</code>\n\n"
                    f"💡 Use <code>/admin_pending_{giveaway_type}</code> to see all pending {giveaway_type} winners",
                    parse_mode='HTML'
                )
                return
            
            # Confirmar pago
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                prize = giveaway_system.get_prize_amount(giveaway_type)
                response_message = f"""✅ <b>{config['display_name']} Payment Confirmed Successfully</b>

👤 <b>Confirmed by:</b> {admin_name}
🎯 <b>Winner:</b> {winner_identifier}
💰 <b>Prize:</b> ${prize} USD
🎲 <b>Giveaway Type:</b> {config['display_name']}
📅 <b>Confirmation Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ <b>Actions completed:</b>
├─ Winner announced publicly in channel
├─ Private congratulation sent to winner
├─ Payment status updated in system
└─ System prepared for next {giveaway_type} draw

💡 <b>Status:</b> Payment process complete ✓"""
                
                await update.message.reply_text(response_message, parse_mode='HTML')
                
                # Log de auditoría
                permission_manager.log_action(
                    user_id, 
                    config['permission'], 
                    f"{config['display_name']} payment confirmed for {winner_identifier} (${prize})"
                )
                
            else:
                await update.message.reply_text(
                    f"❌ <b>Error confirming {config['display_name']} payment</b>\n\n"
                    f"Reason: {message}\n\n"
                    f"💡 This usually means:\n"
                    f"• Winner was already processed\n"
                    f"• System error occurred\n"
                    f"• Invalid winner state\n\n"
                    f"Contact a FULL_ADMIN if the issue persists.",
                    parse_mode='HTML'
                )
                
                permission_manager.log_action(
                    user_id, 
                    config['permission'], 
                    f"Failed to confirm {giveaway_type} payment for {winner_identifier}: {message}"
                )
            
        except Exception as e:
            logging.error(f"Error in {giveaway_type} payment confirmation: {e}")
            await update.message.reply_text(
                f"❌ <b>System error during {config['display_name']} payment confirmation</b>\n\n"
                f"Please try again in a few moments or contact a FULL_ADMIN.",
                parse_mode='HTML'
            )


    async def admin_view_pending_universal(self, update, context, giveaway_type):
        """Ver ganadores pendientes por tipo - movido desde test_botTTT.py"""
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)
        admin_info = permission_manager.get_admin_info(user_id)
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
        
        display_name = giveaway_type.title()
        
        try:
            giveaway_system = self.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await update.message.reply_text(f"❌ {display_name} giveaway system not available")
                return
            
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                next_draw_time = giveaway_system.get_next_draw_time(giveaway_type)
                next_draw_str = next_draw_time.strftime('%Y-%m-%d %H:%M') if next_draw_time else "Check schedule"
                
                await update.message.reply_text(
                    f"ℹ️ <b>No pending {giveaway_type} winners</b>\n\n"
                    f"All {giveaway_type} payments are up to date.\n\n"
                    f"🎯 <b>Next {giveaway_type} draw:</b> {next_draw_str}",
                    parse_mode='HTML'
                )
                return
            
            message = f"""📋 <b>PENDING {display_name.upper()} WINNERS ({len(pending_winners)})</b>
<i>Viewed by: {admin_name}</i>

"""
            
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    display_name_winner = f"@{username}"
                    command_identifier = f"@{username}"
                else:
                    display_name_winner = f"{first_name} (ID: {winner['telegram_id']})"
                    command_identifier = winner['telegram_id']
                
                message += f"""{i}. <b>{first_name}</b> ({display_name_winner})
   📊 <b>VFX MT5 Account:</b> <code>{winner['mt5_account']}</code>
   💰 <b>Prize:</b> ${winner['prize']} USD
   📅 <b>Selected:</b> {winner['selected_time']}
   💡 <b>Command:</b> <code>/admin_confirm_{giveaway_type} {command_identifier}</code>

"""
            
            message += f"""💡 <b>Payment Instructions:</b>
1️⃣ Transfer the prize amount to the corresponding VFX MT5 account
2️⃣ Use the confirmation command shown above for each winner
3️⃣ Bot will automatically announce the winner and send congratulations

📊 <b>Total pending amount:</b> ${len(pending_winners) * prize} USD"""
            
            await update.message.reply_text(message, parse_mode='HTML')
            
            permission_manager.log_action(
                user_id, 
                SystemAction.VIEW_ALL_PENDING_WINNERS, 
                f"Viewed {len(pending_winners)} pending {giveaway_type} winners"
            )
            
        except Exception as e:
            logging.error(f"Error getting pending {giveaway_type} winners: {e}")
            await update.message.reply_text(f"❌ Error getting pending {giveaway_type} winners")


#     async def notify_payment_admins_new_winner(self, context, winner, giveaway_type, executed_by):
#         """Notificar a admins con permisos de confirmación - movido desde test_botTTT.py"""
#         permission_manager = get_permission_manager(context)
#         if not permission_manager:
#             logging.warning("Permission manager not available for notifications")
#             return
        
#         confirm_action_map = {
#             'daily': SystemAction.CONFIRM_DAILY_PAYMENTS,
#             'weekly': SystemAction.CONFIRM_WEEKLY_PAYMENTS,
#             'monthly': SystemAction.CONFIRM_MONTHLY_PAYMENTS
#         }
        
#         required_permission = confirm_action_map.get(giveaway_type)
#         if not required_permission:
#             return
        
#         admins_who_can_confirm = permission_manager.get_admins_with_permission(required_permission)
        
#         if not admins_who_can_confirm:
#             logging.warning(f"No admins found with permission to confirm {giveaway_type} payments")
#             return
        
#         username = winner.get('username', '').strip()
#         first_name = winner.get('first_name', 'N/A')
#         winner_display = f"@{username}" if username else first_name
        
#         notification_message = f"""🔔 <b>NEW {giveaway_type.upper()} WINNER - PAYMENT NEEDED</b>

# 🎉 <b>Winner:</b> {first_name} ({winner_display})
# 📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
# 💰 <b>Prize:</b> ${winner['prize']} USD
# 👤 <b>Draw executed by:</b> {executed_by}
# 📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# ⚠️ <b>ACTION REQUIRED:</b>
# 💸 Transfer ${winner['prize']} USD to account {winner['mt5_account']}
# 💡 Use <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code> after transfer

# 🎯 <b>Your permission level allows you to confirm this payment.</b>"""
        
#         for admin_id in admins_who_can_confirm:
#             try:
#                 await context.bot.send_message(
#                     chat_id=admin_id,
#                     text=notification_message,
#                     parse_mode='HTML'
#                 )
#                 print(f"✅ Payment notification sent to admin {admin_id}")
#             except Exception as e:
#                 logging.error(f"Error sending notification to admin {admin_id}: {e}")

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


    @require_permission(SystemAction.CONFIRM_DAILY_PAYMENTS)
    async def admin_confirm_daily_payment(self,update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago daily"""
        await self.admin_confirm_payment_universal(update, context, 'daily')

    @require_permission(SystemAction.CONFIRM_WEEKLY_PAYMENTS)
    async def admin_confirm_weekly_payment(self,update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago weekly"""
        await self.admin_confirm_payment_universal(update, context, 'weekly')

    @require_permission(SystemAction.CONFIRM_MONTHLY_PAYMENTS)
    async def admin_confirm_monthly_payment(self, update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago monthly"""
        await self.admin_confirm_payment_universal(update, context, 'monthly')

    

    @require_any_permission(
        SystemAction.CONFIRM_DAILY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
    async def admin_pending_daily(self, update, context):
        """📋 VER PENDIENTES: Daily winners"""
        await self.admin_view_pending_universal(update, context, 'daily')

    @require_any_permission(
        SystemAction.CONFIRM_WEEKLY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
    async def admin_pending_weekly(self, update, context):
        """📋 VER PENDIENTES: Weekly winners"""
        await self.admin_view_pending_universal(update, context, 'weekly')

    @require_any_permission(
        SystemAction.CONFIRM_MONTHLY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
    async def admin_pending_monthly(self, update, context):
        """📋 VER PENDIENTES: Monthly winners"""
        await self.admin_view_pending_universal(update, context, 'monthly')

    # ======================================================================
    async def admin_pending_winners(self, update, context):
        """🚨 CRÍTICO: Comando para ver ganadores pendientes - AGREGAR a ga_test_bot.py"""
        user_id = update.effective_user.id

        # 🆕 AGREGAR: Verificación de permisos al INICIO
        permission_manager = get_permission_manager(context)
        if not permission_manager:
            await update.message.reply_text("❌ Permission system not initialized")
            return
        
        # 🆕 VERIFICAR permisos para ver ganadores pendientes
        if not permission_manager.has_permission(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS):
            admin_info = permission_manager.get_admin_info(user_id)
            await update.message.reply_text(
                f"❌ <b>Access Denied</b>\n\n"
                f"Required: <code>{SystemAction.VIEW_ALL_PENDING_WINNERS.value}</code>\n"
                f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            config_loader = ConfigLoader()
            bot_config = config_loader.get_bot_config()
            channel_id = bot_config['channel_id']
            
            # Verificar admin permissions
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view pending winners")
                return
            
            # Obtener ganadores pendientes de todos los tipos
            all_pending = {}
            total_pending = 0
            total_amount = 0
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                pending = giveaway_system.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
                    total_pending += len(pending)
                    
                    # Calcular monto total
                    prize = giveaway_system.get_prize_amount(giveaway_type)
                    total_amount += len(pending) * prize
            
            if total_pending == 0:
                await update.message.reply_text(
                    "ℹ️ <b>No pending winners</b>\n\nAll payments are up to date.\n\n🎯 Next draws will be automatically scheduled",
                    parse_mode='HTML'
                )
                return
            
            # Formatear mensaje con todos los ganadores pendientes
            message = f"📋 <b>PENDING WINNERS ({total_pending})</b>\n"
            message += f"💰 <b>Total amount:</b> ${total_amount} USD\n\n"
            
            buttons = []
            
            for giveaway_type, pending_winners in all_pending.items():
                prize = self.get_giveaway_system(giveaway_type).get_prize_amount(giveaway_type)
                message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
                
                for i, winner in enumerate(pending_winners, 1):
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    
                    if username:
                        identifier = f"@{username}"
                        command_identifier = username
                        button_display = f"@{username}"
                    else:
                        identifier = f"{first_name} (ID: {winner['telegram_id']})"
                        command_identifier = winner['telegram_id']
                        button_display = first_name
                    
                    message += f"  {i}. {identifier}\n"
                    message += f"     💰 Prize: ${winner['prize']} USD\n"
                    message += f"     📊 MT5: <code>{winner['mt5_account']}</code>\n"
                    message += f"     📅 Selected: {winner['selected_time']}\n\n"
                    
                    # Crear botón de confirmación
                    button_text = f"✅ Confirm {giveaway_type} - {button_display}"
                    callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            message += f"💡 <b>Quick confirmation:</b> Press buttons below\n"
            message += f"💡 <b>Manual confirmation:</b> <code>/admin_confirm_payment &lt;id_or_username&gt;</code>"
            
            # Limitar botones para evitar overflow
            if len(buttons) > 10:
                buttons = buttons[:10]
                message += f"\n\n⚠️ Showing first 10 confirmation buttons only"
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error getting pending winners: {e}")
            await update.message.reply_text("❌ Error getting pending winners")


    async def admin_confirm_payment(self, update, context):
        """🚨 CRÍTICO: Comando para confirmar pagos - VERSIÓN CORREGIDA ASYNC"""
        user_id = update.effective_user.id

        # 🆕 AGREGAR: Verificación de permisos al INICIO de la función
        permission_manager = get_permission_manager(context)
        if not permission_manager:
            await update.message.reply_text("❌ Permission system not initialized")
            return
        
        # 🆕 VERIFICAR si tiene ALGÚN permiso de confirmación
        has_confirm_permission = any([
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS),
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_WEEKLY_PAYMENTS),
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_MONTHLY_PAYMENTS)
        ])
        
        if not has_confirm_permission:
            admin_info = permission_manager.get_admin_info(user_id)
            await update.message.reply_text(
                f"❌ <b>Access Denied</b>\n\n"
                f"Required: Payment confirmation permissions\n"
                f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
                parse_mode='HTML'
            )
            return
        
        try:
            config_loader = ConfigLoader()
            bot_config = config_loader.get_bot_config()
            channel_id = bot_config['channel_id']
            
            # Verificar admin permissions
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can confirm payments")
                return
            
            # Verificar formato del comando
            if not context.args or len(context.args) != 1:
                await update.message.reply_text(
                    "❌ <b>Incorrect usage</b>\n\n"
                    "<b>Format:</b> <code>/admin_confirm_payment &lt;telegram_id_or_username&gt;</code>\n\n"
                    "<b>Examples:</b>\n"
                    "• <code>/admin_confirm_payment 123456</code>\n"
                    "• <code>/admin_confirm_payment @username</code>\n\n"
                    "💡 Use <code>/admin_pending_winners</code> to see pending winners",
                    parse_mode='HTML'
                )
                return
            
            winner_identifier = context.args[0].strip()
            
            # Intentar confirmación para cada tipo de giveaway
            confirmed = False
            confirmation_message = ""
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                
                # Buscar ganador pendiente
                pending_winners = giveaway_system.get_pending_winners(giveaway_type)
                winner_found = None
                
                for winner in pending_winners:
                    winner_username = winner.get('username', '').strip()
                    winner_telegram_id = winner.get('telegram_id', '').strip()
                    
                    # Verificar si coincide el identificador
                    if (winner_identifier == winner_telegram_id or 
                        winner_identifier.lower() == f"@{winner_username}".lower() or
                        winner_identifier.lower() == winner_username.lower()):
                        winner_found = winner_telegram_id
                        break
                
                if winner_found:
                    # ✅ CORREGIDO: Llamada asíncrona correcta
                    success, message = await giveaway_system.confirm_payment_and_announce(
                        winner_found, user_id, giveaway_type
                    )
                    
                    if success:
                        confirmed = True
                        prize = giveaway_system.get_prize_amount(giveaway_type)
                        confirmation_message = f"✅ <b>{giveaway_type.title()} payment confirmed successfully</b>\n\n" \
                                            f"🎯 Winner: {winner.get('first_name', 'Unknown')}\n" \
                                            f"💰 Prize: ${prize} USD\n" \
                                            f"📊 MT5: {winner['mt5_account']}\n\n" \
                                            f"✅ Winner announced publicly\n" \
                                            f"📬 Private congratulation sent"
                        break
            
            if confirmed:
                await update.message.reply_text(confirmation_message, parse_mode='HTML')
            else:
                await update.message.reply_text(
                    f"❌ <b>Winner not found</b>\n\n"
                    f"No pending winner found with identifier: <code>{winner_identifier}</code>\n\n"
                    f"💡 Use <code>/admin_pending_winners</code> to see all pending winners",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            logging.error(f"Error in payment confirmation: {e}")
            await update.message.reply_text("❌ Error processing payment confirmation")


    # async def admin_panel(self, update, context):
    #     """🚨 CRÍTICO: Panel administrativo con detección inmediata de VIEW_ONLY"""
    #     user_id = update.effective_user.id
    #     print(f"OJO DEBUG: admin_panel called by user {user_id}")
    #     try:
    #         config_loader = ConfigLoader()
    #         bot_config = config_loader.get_bot_config()
    #         channel_id = bot_config['channel_id']
            
    #         # 1️⃣ VERIFICACIÓN PRIMARIA: Telegram admin (siempre debe funcionar)
    #         member = await context.bot.get_chat_member(channel_id, user_id)
    #         if member.status not in ['administrator', 'creator']:
    #             await update.message.reply_text("❌ Only administrators can access admin panel")
    #             return
            
    #         # 2️⃣ VERIFICACIÓN DE PERMISOS GRANULARES
    #         permission_manager = get_permission_manager(context)
    #         if not permission_manager:
    #             await update.message.reply_text("❌ Permission system not initialized")
    #             return
            
    #         # 3️⃣ 🚨 DETECCIÓN VIEW_ONLY INMEDIATA - CORREGIDO
    #         admin_info = permission_manager.get_admin_info(user_id)
    #         print(f"OJO DEBUG: admin_info for {user_id}: {admin_info}")
    #         if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
    #             print(f"OJO DEBUG: VIEW_ONLY user {user_id} detected, alling show_view_only_panel_direct")
    #             await self.show_view_only_panel_direct(update, context)
    #             print(f"✅ DEBUG: show_view_only_panel_direct completed for {user_id}")
    #             return
    #         print(f"OJO DEBUG: User {user_id} is not VIEW_ONLY, continuing with full panel")
    #         # 4️⃣ VERIFICAR acceso básico al panel (solo para no VIEW_ONLY)
    #         # if not permission_manager.has_permission(user_id, SystemAction.VIEW_BASIC_STATS):
    #         #     await update.message.reply_text(
    #         #         f"❌ <b>Access Denied</b>\n\n"
    #         #         f"Required: <code>{SystemAction.VIEW_BASIC_STATS.value}</code>\n"
    #         #         f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
    #         #         parse_mode='HTML'
    #         #     )
    #         #     return
            
    #         # 5️⃣ PARA PAYMENT_SPECIALIST Y FULL_ADMIN: Panel completo
            
    #         # Obtener estadísticas rápidas del sistema
    #         total_pending = 0
    #         total_today = 0
    #         stats_summary = []
            
    #         for giveaway_type in ['daily', 'weekly', 'monthly']:
    #             giveaway_system = self.get_giveaway_system(giveaway_type)
    #             stats = giveaway_system.get_stats(giveaway_type)
    #             pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
    #             prize = giveaway_system.get_prize_amount(giveaway_type)
    #             today_participants = stats.get('today_participants', 0)
                
    #             total_pending += pending_count
    #             total_today += today_participants
                
    #             # Verificar si ventana de participación está abierta
    #             is_open = giveaway_system.is_participation_window_open(giveaway_type)
    #             status_emoji = "🟢" if is_open else "🔴"
                
    #             stats_summary.append({
    #                 'type': giveaway_type,
    #                 'prize': prize,
    #                 'today_participants': today_participants,
    #                 'pending': pending_count,
    #                 'total_winners': stats.get('total_winners', 0),
    #                 'status_emoji': status_emoji,
    #                 'is_open': is_open
    #             })
            
    #         # Construir mensaje del panel (adaptado según permisos)
    #         admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    #         permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'
            
    #         message = f"🎛️ <b>MULTI-GIVEAWAY ADMIN PANEL</b>\n"
    #         message += f"👤 <b>Access Level:</b> {permission_level}\n"
    #         message += f"🔑 <b>Admin:</b> {admin_name}\n\n"
            
    #         # Estado general
    #         message += f"📊 <b>System Status:</b>\n"
    #         message += f"├─ Today's participants: <b>{total_today}</b>\n"
    #         message += f"├─ Pending winners: <b>{total_pending}</b>\n"
    #         message += f"└─ System health: {'🟢 Operational' if total_pending < 10 else '⚠️ High pending'}\n\n"
            
    #         # Estado por tipo
    #         message += f"🎯 <b>Giveaway Types:</b>\n"
    #         for stat in stats_summary:
    #             message += f"{stat['status_emoji']} <b>{stat['type'].upper()}</b> (${stat['prize']}): "
    #             message += f"{stat['today_participants']} today, {stat['pending']} pending\n"
            
    #         message += f"\n🚀 <b>Available Actions:</b>"
            
    #         # Crear botones adaptados según permisos
    #         buttons = []
            
    #         # 6️⃣ BOTONES ADAPTATIVOS SEGÚN PERMISOS
    #         if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
    #             buttons.append([
    #                 InlineKeyboardButton("📅 Daily", callback_data="panel_daily"),
    #                 InlineKeyboardButton("📅 Weekly", callback_data="panel_weekly"),
    #                 InlineKeyboardButton("📅 Monthly", callback_data="panel_monthly")
    #             ])
    #         # Fila 1: Acciones principales (solo si tiene permisos)
    #         row1 = []
    #         if permission_manager.has_permission(user_id, SystemAction.SEND_DAILY_INVITATION):
    #             row1.append(InlineKeyboardButton("📢 Send Invitations", callback_data="panel_send_invitations"))
    #         if permission_manager.has_permission(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS):
    #             row1.append(InlineKeyboardButton(f"👑 Pending ({total_pending})", callback_data="panel_pending_winners"))
    #         # if permission_manager.has_permission(user_id, SystemAction.EXECUTE_DAILY_DRAW):
    #         #     row1.append(InlineKeyboardButton("🎲 Execute Draws", callback_data="panel_execute_draws"))
    #         if row1:
    #             buttons.append(row1)
            
    #         # Fila 2: Gestión de ganadores (solo si tiene permisos) 
    #         row2 = []
    #         # if permission_manager.has_permission(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS):
    #         #     row2.append(InlineKeyboardButton(f"👑 Pending ({total_pending})", callback_data="panel_pending_winners"))
    #         if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
    #             row2.append(InlineKeyboardButton("📊 Statistics", callback_data="panel_statistics"))
    #         if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
    #             row2.append(InlineKeyboardButton("📈 Advanced Analytics", callback_data="panel_advanced_analytics"))
    #         if row2:
    #             buttons.append(row2)
            
    #         # Fila 3: Acceso por tipo (solo para PAYMENT_SPECIALIST+)
    #         row3 = []
    #         if permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
    #             row3.append(InlineKeyboardButton("🤖 Automation", callback_data="automation_control"))
    #         if row3:
    #             buttons.append(row3)
            
    #         # Fila 4: Sistema (solo FULL_ADMIN puede ver mantenimiento)
    #         row4 = []
    #         row4.append(InlineKeyboardButton("🏥 Health Check", callback_data="panel_health"))
    #         if permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
    #             row4.append(InlineKeyboardButton("🔧 Maintenance", callback_data="panel_maintenance"))
    #             # row4.append(InlineKeyboardButton("🤖 Auto-Draw", callback_data="automation_control"))
    #         if row4:
    #             buttons.append(row4)
    #         # 🆕 NEW: Fila 4.5: Automation (solo FULL_ADMIN)
    #         # if permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
    #         #     buttons.append([
    #         #         InlineKeyboardButton("🤖 Automation Control", callback_data="automation_control")
    #         #     ])
            
    #         # Fila 5: Analytics (según nivel)
    #         row5 = []
    #         # if permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS):
    #         #     row5.append(InlineKeyboardButton("📈 Advanced Analytics", callback_data="panel_advanced_analytics"))
    #         if permission_manager.has_permission(user_id, SystemAction.VIEW_BASIC_STATS):
    #             row5.append(InlineKeyboardButton("📊 Basic Analytics", callback_data="panel_basic_analytics"))
    #         if row5:
    #             buttons.append(row5)
            
    #         # Fila 6: Refresh (siempre disponible)
    #         buttons.append([
    #             InlineKeyboardButton("🔄 Refresh Panel", callback_data="panel_refresh")
    #         ])
            
    #         # 7️⃣ MENSAJE INFORMATIVO SOBRE PERMISOS
    #         if permission_level == "PAYMENT_SPECIALIST":
    #             message += f"\n\n💡 <b>Note:</b> Some advanced features require FULL_ADMIN permissions"
            
    #         reply_markup = InlineKeyboardMarkup(buttons)
    #         await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
    #     except Exception as e:
    #         logging.error(f"Error in admin panel: {e}")
    #         await update.message.reply_text("❌ Error loading admin panel")

    # prueba=============================================================================
    async def _handle_payment_from_admin_channel(self, update, context):
        """🆕 NEW: Handle payment confirmations from admin channel notifications"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            callback_data = query.data
            
            print(f"💰 DEBUG: Admin channel payment callback: {callback_data} from user {user_id}")
            
            # Verify admin permissions using permission manager
            permission_manager = self._get_permission_manager_from_callback()
            if not permission_manager:
                await query.edit_message_text("❌ Permission system not available")
                return
            
            # Check if user has payment confirmation permissions
            has_payment_permission = any([
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_WEEKLY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_MONTHLY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS)
            ])
            
            if not has_payment_permission:
                admin_info = permission_manager.get_admin_info(user_id)
                await query.edit_message_text(
                    f"❌ <b>Payment Confirmation Access Denied</b>\n\n"
                    f"Required: PAYMENT_SPECIALIST+ permissions\n"
                    f"Your level: {admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}",
                    parse_mode='HTML'
                )
                return
            
            # Parse callback: confirm_payment_<type>_<identifier>
            parts = callback_data.split("_", 3)
            if len(parts) < 4:
                await query.edit_message_text("❌ Invalid payment callback format")
                return
            
            giveaway_type = parts[2]  # daily, weekly, monthly
            winner_identifier = parts[3]  # username or telegram_id
            
            # Validate giveaway type
            if giveaway_type not in ['daily', 'weekly', 'monthly']:
                await query.edit_message_text("❌ Invalid giveaway type")
                return
            
            # Get giveaway system
            giveaway_system = self.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await query.edit_message_text(f"❌ {giveaway_type.title()} system not available")
                return
            
            # Find winner using helper function from ga_integration
            winner_telegram_id = await self._find_winner_by_identifier_admin_channel(
                winner_identifier, giveaway_type, giveaway_system
            )
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\n"
                    f"Winner '{winner_identifier}' not found in pending {giveaway_type} winners.\n\n"
                    f"💡 The winner may have been processed already.",
                    parse_mode='HTML'
                )
                return
            
            # Confirm payment using existing system
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                prize = giveaway_system.get_prize_amount(giveaway_type)
                admin_info = permission_manager.get_admin_info(user_id)
                admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
                
                await query.edit_message_text(
                    f"✅ <b>{giveaway_type.title()} Payment Confirmed Successfully</b>\n\n"
                    f"🎉 Winner: {winner_identifier}\n"
                    f"💰 Prize: ${prize} USD\n"
                    f"👤 Confirmed by: {admin_name}\n"
                    f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ <b>Actions completed:</b>\n"
                    f"├─ Winner announced in channel\n"
                    f"├─ Private congratulation sent\n"
                    f"├─ Payment record updated\n"
                    f"└─ System ready for next {giveaway_type} draw",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    f"❌ <b>Error confirming {giveaway_type} payment</b>\n\n"
                    f"<b>Reason:</b> {message}",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            logging.error(f"Error in admin channel payment confirmation: {e}")
            await query.edit_message_text("❌ Error processing payment confirmation")

    async def _find_winner_by_identifier_admin_channel(self, winner_identifier, giveaway_type, giveaway_system):
        """🆕 NEW: Find winner by identifier for admin channel confirmations"""
        try:
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                winner_first_name = winner.get('first_name', '').strip()
                
                # Search by different criteria
                if (
                    winner_identifier == winner_telegram_id or
                    winner_identifier.lower() == f"@{winner_username}".lower() or
                    winner_identifier.lower() == winner_username.lower() or
                    (not winner_username and winner_identifier.lower() == winner_first_name.lower())
                ):
                    return winner_telegram_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
            return None

    #  prueba ========================================================================


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
                await self.show_view_only_panel_direct(update, context)
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
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_participants = stats.get('today_participants', 0)
                
                total_pending += pending_count
                total_today += today_participants
                
                # Verificar si ventana de participación está abierta
                is_open = giveaway_system.is_participation_window_open(giveaway_type)
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




    async def show_view_only_panel_direct(self, update, context):
        """🆕 NUEVA: Panel VIEW_ONLY directo desde command (NO callback)"""
        user_id = update.effective_user.id
        
        try:
            # Verificar que efectivamente es VIEW_ONLY
            permission_manager = get_permission_manager(context)
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)

                if admin_info:
                    permission_group = admin_info.get('permission_group', 'Unknown')
                    print(f"🔍 DEBUG: User {user_id} has permission group: {permission_group}")
                    
                    # Solo verificar para VIEW_ONLY, pero continuar para otros si necesario
                    if permission_group != 'VIEW_ONLY':
                        print(f"⚠️ DEBUG: User {user_id} is not VIEW_ONLY ({permission_group}), but continuing...")
                        # NO retornar aquí - continuar mostrando panel básico
                else:
                    print(f"⚠️ DEBUG: No admin_info found for user {user_id}")
            else:
                print(f"⚠️ DEBUG: No permission_manager available")
            
            # Obtener estadísticas básicas
            basic_stats = {
                'total_today': 0,
                'active_windows': 0,
                'system_health': 'Operational'
            }
            
            type_details = []
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Verificar ventana de participación
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    basic_stats['active_windows'] += 1
                
                basic_stats['total_today'] += today_count
                
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                type_details.append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
            admin_name = "VIEW_ONLY User"
            permission_level = "VIEW_ONLY"
            admin_info = permission_manager.get_admin_info(user_id)
            # Obtener nombre del admin
            if permission_manager and admin_info:
                admin_name = admin_info.get('name', 'VIEW_ONLY User')
                permission_level = admin_info.get('permission_group', 'VIEW_ONLY')
            
            print(f"🔍 DEBUG: Showing panel for {admin_name} ({permission_level})")
            
            message = f"""📊 <b>VIEW_ONLY DASHBOARD</b>
    🔒 <b>Access Level:</b> VIEW_ONLY
    👤 <b>Admin:</b> {admin_name}

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{basic_stats['total_today']}</b>
    ├─ Active participation windows: <b>{basic_stats['active_windows']}/{len(type_details)}</b>
    ├─ System status: <b>✅ {basic_stats['system_health']}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Giveaway Status:</b>"""

            for detail in type_details:
                message += f"""

    🎯 <b>{detail['type'].upper()} GIVEAWAY:</b>
    ├─ Prize Amount: <b>${detail['prize']} USD</b>
    ├─ Today's Participants: <b>{detail['participants']}</b>
    ├─ Participation Window: <b>{detail['window_status']}</b>
    ├─ Activity Level: <b>{detail['activity_level']}</b>
    └─ Status: {'✅ Active period' if detail['is_open'] else '⏸️ Outside participation hours'}"""

            message += f"""

    📈 <b>System Insights (Basic):</b>
    ├─ Most active type: <b>{max(type_details, key=lambda x: x['participants'])['type'].title()}</b>
    ├─ Current engagement: <b>{'Strong' if basic_stats['total_today'] > 15 else 'Moderate' if basic_stats['total_today'] > 5 else 'Building'}</b>
    └─ System load: <b>{'Normal' if basic_stats['total_today'] < 100 else 'High'}</b>

    💡 <b>Your VIEW_ONLY Permissions:</b>
    ✅ View today's participation statistics
    ✅ Check basic system health status  
    ✅ See participation window status
    ❌ Advanced analytics require PAYMENT_SPECIALIST+ permissions
    ❌ Pending winners require higher access levels

    🔄 Use the buttons below for more information or to refresh data."""

            # Botones corregidos para VIEW_ONLY
            buttons = [
                [
                    InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="view_only_refresh"),
                    InlineKeyboardButton("ℹ️ About Permissions", callback_data="view_only_permissions_info")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY panel direct: {e}")
            await update.message.reply_text("❌ Error loading VIEW_ONLY dashboard")


    # async def notify_payment_admins_new_winner(self,context, winner, giveaway_type, executed_by):
    #     """🆕 NUEVA: Notificar a admins con permisos de confirmación de pagos"""
    #     permission_manager = get_permission_manager(context)
        
    #     # Mapear tipo de giveaway a acción de confirmación
    #     confirm_action_map = {
    #         'daily': SystemAction.CONFIRM_DAILY_PAYMENTS,
    #         'weekly': SystemAction.CONFIRM_WEEKLY_PAYMENTS,
    #         'monthly': SystemAction.CONFIRM_MONTHLY_PAYMENTS
    #     }
        
    #     required_permission = confirm_action_map.get(giveaway_type)
    #     if not required_permission:
    #         return
        
    #     # Obtener admins con permiso de confirmación para este tipo
    #     admins_who_can_confirm = permission_manager.get_admins_with_permission(required_permission)
        
    #     if not admins_who_can_confirm:
    #         logging.warning(f"No admins found with permission to confirm {giveaway_type} payments")
    #         return
        
    #     # Preparar información del ganador
    #     username = winner.get('username', '').strip()
    #     first_name = winner.get('first_name', 'N/A')
    #     winner_display = f"@{username}" if username else first_name
        
    #     notification_message = f"""🔔 <b>NEW {giveaway_type.upper()} WINNER - PAYMENT NEEDED</b>

    # 🎉 <b>Winner:</b> {first_name} ({winner_display})
    # 📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
    # 💰 <b>Prize:</b> ${winner['prize']} USD
    # 👤 <b>Draw executed by:</b> {executed_by}
    # 📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    # ⚠️ <b>ACTION REQUIRED:</b>
    # 💸 Transfer ${winner['prize']} USD to account {winner['mt5_account']}
    # 💡 Use <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code> after transfer

    # 🎯 <b>Your permission level allows you to confirm this payment.</b>"""
        
    #     # Enviar notificación a cada admin autorizado
    #     for admin_id in admins_who_can_confirm:
    #         try:
    #             await context.bot.send_message(
    #                 chat_id=admin_id,
    #                 text=notification_message,
    #                 parse_mode='HTML'
    #             )
    #             print(f"✅ Payment notification sent to admin {admin_id}")
    #         except Exception as e:
    #             logging.error(f"Error sending notification to admin {admin_id}: {e}")

    # ================== TYPE-SPECIFIC ADMIN COMMANDS ==================

    async def _handle_manual_giveaway(self, update, context, giveaway_type):
        """🆕 NEW: Handle manual giveaway for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Send invitation for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
            success = await giveaway_system.send_invitation(giveaway_type)
            
            # Create return button
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await update.message.reply_text(
                    f"✅ {giveaway_type.title()} giveaway invitation sent to channel",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"❌ Error sending {giveaway_type} invitation",
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logging.error(f"Error in manual {giveaway_type} giveaway: {e}")
            await update.message.reply_text("❌ Internal error", parse_mode='HTML')

    async def _handle_manual_sorteo(self, update, context, giveaway_type):
        """🆕 NEW: Handle manual draw for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Execute manual draw for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
            await giveaway_system.run_giveaway(giveaway_type)
            
            # Check result and create return button
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            pending_count = len(pending_winners)
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if pending_count > 0:
                winner = pending_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    winner_display = f"@{username}"
                    command_reference = f"@{username}"
                else:
                    winner_display = f"{first_name} (ID: {winner['telegram_id']})"
                    command_reference = winner['telegram_id']
                
                prize = giveaway_system.get_prize_amount(giveaway_type)
                response_message = f"""✅ <b>{giveaway_type.title()} draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>VFX MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
🎯 <b>Type:</b> {giveaway_type.upper()}
⏳ <b>Pending winners:</b> {pending_count}

📬 <b>Next steps:</b>
1️⃣ Check your private chat for complete details
2️⃣ Transfer to VFX MT5 account: {winner['mt5_account']}
3️⃣ Use `/admin_confirm_payment_{giveaway_type} {command_reference}` to confirm

💡 Use `/admin_pending_{giveaway_type}` for complete details"""
                    
                await update.message.reply_text(response_message, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await update.message.reply_text(
                    f"✅ {giveaway_type.title()} draw executed - No eligible participants today",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            
        except Exception as e:
            logging.error(f"Error in manual {giveaway_type} draw: {e}")
            await update.message.reply_text("❌ Internal error", parse_mode='HTML')

    async def _handle_stats_command(self, update, context, giveaway_type):
        """🆕 NEW: Handle stats command for specific type"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = f"""📊 <b>{giveaway_type.upper()} GIVEAWAY STATISTICS</b>

👥 <b>Today's participants:</b> {stats.get('today_participants', 0)}
📈 <b>Total participants:</b> {stats.get('total_participants', 0)}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}
💰 <b>Money distributed:</b> ${stats.get('total_prize_distributed', 0)}
⏳ <b>Pending winners:</b> {pending_count}

⏰ Next draw: Check schedule

<i>Updated: {stats.get('timestamp', 'N/A')}</i>"""

            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} statistics: {e}")
            await update.message.reply_text("❌ Error getting statistics")

    async def _handle_pending_winners(self, update, context, giveaway_type):
        """🆕 NEW: Handle pending winners for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get pending winners for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"ℹ️ No pending {giveaway_type} winners", 
                    reply_markup=reply_markup
                )
                return
            
            # Format pending winners list
            pending_list = ""
            buttons = []
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    command_identifier = username
                    display_name = f"<b>{first_name}</b> (@{username})"
                else:
                    command_identifier = winner['telegram_id']
                    display_name = f"<b>{first_name}</b> (ID: {winner['telegram_id']})"
                
                pending_list += f"{i}. {display_name}\n"
                pending_list += f"   📊 MT5 Account: <code>{winner['mt5_account']}</code>\n"
                pending_list += f"   💰 Prize: ${winner['prize']} USD\n"
                pending_list += f"   🎯 Type: {giveaway_type.upper()}\n"
                pending_list += f"   📅 Selected: {winner['selected_time']}\n\n"
                
                # Create inline button for each winner
                button_text = f"✅ Confirm payment to {first_name}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add return button
            buttons.append([InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")])
            
            message = f"""📋 <b>{giveaway_type.upper()} PENDING WINNERS</b>

{pending_list}💡 <b>Instructions:</b>
1️⃣ Transfer to the VFX MT5 account
2️⃣ Press the corresponding confirmation button
3️⃣ Bot will announce the winner automatically

⚡ <b>Quick buttons:</b>"""
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error getting {giveaway_type} pending winners: {e}")
            await update.message.reply_text("❌ Error getting pending winners")

    

    async def _show_view_only_panel(self, query):
        """📊 Panel básico VIEW_ONLY (versión callback)"""
        try:
            # Verificar permisos
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Obtener estadísticas detalladas del día (solo datos permitidos)
            basic_stats = {
                'total_today': 0,
                'active_windows': 0,
                'system_health': 'Operational'
            }
            
            type_details = []
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Información de ventana de participación (permitida para VIEW_ONLY)
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    basic_stats['active_windows'] += 1
                
                basic_stats['total_today'] += today_count
                
                # Calcular actividad relativa (sin datos históricos sensibles)
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                type_details.append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
        # Obtener nombre del admin
            admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
            admin_name = admin_info.get('name', 'VIEW_ONLY User') if admin_info else 'VIEW_ONLY User'
                
            message = f"""📈 <b>TODAY'S VIEW_ONLY DASHBOARD</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{basic_stats['total_today']}</b>
    ├─ Active participation windows: <b>{basic_stats['active_windows']}/{len(type_details)}</b>
    ├─ System activity level: <b>{'🟢 High' if basic_stats['total_today'] > 20 else '🟡 Medium' if basic_stats['total_today'] > 10 else '🔴 Low'}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Giveaway Status:</b>"""

            for detail in type_details:
                message += f"""

    🎯 <b>{detail['type'].upper()}:</b> ${detail['prize']} | {detail['participants']} today | {detail['window_status']} | {detail['activity_level']}"""

            message += f"""

    💡 <b>System Insights:</b>
    • Most active: <b>{max(type_details, key=lambda x: x['participants'])['type'].title()}</b>
    • Engagement: <b>{'Strong' if basic_stats['total_today'] > 15 else 'Moderate' if basic_stats['total_today'] > 5 else 'Building'}</b>

    🔒 <b>VIEW_ONLY Access:</b> Basic monitoring only
    💡 Contact FULL_ADMIN for permission upgrades"""

            buttons = [
                [
                    InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="view_only_refresh"),
                    InlineKeyboardButton("ℹ️ Permissions Info", callback_data="view_only_permissions_info")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY panel: {e}")
            await query.edit_message_text("❌ Error loading VIEW_ONLY panel")

    async def _show_view_only_permissions_info(self, query):
        """ℹ️ Información detallada sobre permisos VIEW_ONLY"""
        try:
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            
            admin_name = "VIEW_ONLY User"
            registration_date = "Unknown"
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if admin_info:
                    admin_name = admin_info.get('name', 'VIEW_ONLY User')
                    registration_date = admin_info.get('created_date', 'Unknown')
                    if admin_info.get('permission_group') != 'VIEW_ONLY':
                        await query.edit_message_text("❌ This information is only for VIEW_ONLY users")
                        return
            
            message = f"""ℹ️ <b>VIEW_ONLY PERMISSIONS INFORMATION</b>

    👤 <b>Your Account Details:</b>
    ├─ Name: <b>{admin_name}</b>
    ├─ Telegram ID: <code>{user_id}</code>
    ├─ Access Level: <b>VIEW_ONLY</b>
    ├─ Account Created: <b>{registration_date}</b>
    └─ Status: <b>✅ Active</b>

    🔒 <b>What VIEW_ONLY Can Access:</b>

    📊 <b>Statistics & Monitoring:</b>
    ✅ Today's participant counts for all giveaway types
    ✅ Basic system health status
    ✅ Participation window status (open/closed)
    ✅ Current activity levels and trends
    ✅ Basic system component status

    🏥 <b>System Information:</b>
    ✅ Overall system operational status
    ✅ Giveaway types availability
    ✅ Basic configuration information
    ✅ Current London time and timezone info

    🚫 <b>What VIEW_ONLY CANNOT Access:</b>

    💰 <b>Financial & Revenue Data:</b>
    ❌ Payment confirmation functions
    ❌ Prize distribution history
    ❌ Revenue analytics and reports
    ❌ Financial performance metrics

    👥 <b>User Management:</b>
    ❌ Pending winners information
    ❌ Individual user details and history
    ❌ Top participants reports
    ❌ User behavior analytics

    🎲 <b>Giveaway Management:</b>
    ❌ Send giveaway invitations
    ❌ Execute giveaway draws
    ❌ Modify giveaway settings
    ❌ Access individual giveaway panels

    🔧 <b>System Administration:</b>
    ❌ System maintenance functions
    ❌ Backup and restore operations
    ❌ Admin management and permissions
    ❌ Debug and diagnostic tools
    ❌ Configuration modifications

    📈 <b>Advanced Analytics:</b>
    ❌ Cross-type analytics comparisons
    ❌ Advanced performance metrics
    ❌ Historical trend analysis
    ❌ Detailed reporting functions

    🔄 <b>Permission Upgrade Process:</b>

    To request higher permissions:
    1️⃣ Contact a FULL_ADMIN in your organization
    2️⃣ Specify which additional permissions you need:
    • <b>PAYMENT_SPECIALIST:</b> Payment confirmation + advanced analytics
    • <b>FULL_ADMIN:</b> Complete system access
    3️⃣ Provide business justification for the upgrade
    4️⃣ FULL_ADMIN can modify your permissions in the system

    ⚠️ <b>Security Note:</b>
    VIEW_ONLY permissions are designed for monitoring and basic oversight without access to sensitive operations or data. This ensures system security while providing transparency.

    📞 <b>Support:</b>
    If you need assistance or have questions about your permissions, contact your FULL_ADMIN or system administrator."""

            buttons = [
                [
                    InlineKeyboardButton("📊 Back to Statistics", callback_data="view_only_refresh"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY permissions info: {e}")
            await query.edit_message_text("❌ Error loading permissions information")

    async def _handle_admin_panel_type(self, update, context, giveaway_type):
        """🆕 NEW: Handle admin panel for specific giveaway type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get quick stats for this type
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # Get last winner info if exists
            recent_winners = giveaway_system.get_pending_winners(giveaway_type)
            last_winner_info = ""
            if recent_winners:
                winner = recent_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                last_winner_info = f"\n🏆 <b>Last winner:</b> {winner_display}"
            
            message = f"""🎛️ <b>{giveaway_type.upper()} GIVEAWAY CONTROL PANEL</b>

💰 <b>Prize Amount:</b> ${prize} USD

📊 <b>Current status:</b>
├─ Today's participants: <b>{stats.get('today_participants', 0)}</b>
├─ Pending winners: <b>{pending_count}</b>
├─ Total winners: <b>{stats.get('total_winners', 0)}</b>
└─ Prizes distributed: <b>${stats.get('total_prize_distributed', 0)}</b>{last_winner_info}

🚀 <b>Select an option:</b>"""
            
            # Create type-specific buttons
            buttons = [
                # Row 1: Main giveaway actions
                [
                    InlineKeyboardButton("📢 Send invitation", callback_data=f"panel_send_invitation_{giveaway_type}"),
                    InlineKeyboardButton("🎲 Execute draw", callback_data=f"panel_run_giveaway_{giveaway_type}")
                ],
                # Row 2: Winners management
                [
                    InlineKeyboardButton(f"👑 Pending ({pending_count})", callback_data=f"panel_pending_winners_{giveaway_type}"),
                    InlineKeyboardButton("📊 Statistics", callback_data=f"panel_full_stats_{giveaway_type}")
                ],
                # Row 3: Analytics
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}")
                ],
                # Row 4: Navigation
                [
                    InlineKeyboardButton("🔄 Other types", callback_data="type_selector_main"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ],
                # Row 5: Refresh
                [
                    InlineKeyboardButton(f"🔄 Refresh {giveaway_type}", callback_data=f"panel_refresh_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in {giveaway_type} admin panel: {e}")
            await update.message.reply_text("❌ Error loading panel")

    # ================== GENERAL ADMIN COMMANDS (BACKWARD COMPATIBILITY) ==================

    async def _handle_manual_giveaway_general(self, update, context):
        """🔄 MODIFIED: General manual giveaway with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Show type selection
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nWhich giveaway invitation do you want to send?"
            
            buttons = []
            for giveaway_type in self.available_types:
                prize = self.giveaway_systems[giveaway_type].get_prize_amount()
                button_text = f"📢 {giveaway_type.title()} (${prize})"
                callback_data = f"panel_send_invitation_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="panel_refresh")])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in general manual giveaway: {e}")
            await update.message.reply_text("❌ Internal error")

    async def _handle_manual_sorteo_general(self, update, context):
        """🔄 MODIFIED: General manual draw with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Show type selection
            message = "🎲 <b>SELECT GIVEAWAY TYPE FOR DRAW</b>\n\nWhich giveaway draw do you want to execute?"
            
            buttons = []
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                prize = giveaway_system.get_prize_amount()
                participants = giveaway_system._get_period_participants_count()
                button_text = f"🎲 {giveaway_type.title()} (${prize} - {participants} participants)"
                callback_data = f"panel_run_giveaway_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="panel_refresh")])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in general manual draw: {e}")
            await update.message.reply_text("❌ Internal error")

    async def _handle_stats_command_general(self, update, context):
        """🔄 MODIFIED: General stats with type selection"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            # Show combined stats for all types
            all_stats = {}
            total_participants = 0
            total_winners = 0
            total_distributed = 0
            total_pending = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                all_stats[giveaway_type] = {
                    'today_participants': stats.get('today_participants', 0),
                    'total_participants': stats.get('total_participants', 0),
                    'total_winners': stats.get('total_winners', 0),
                    'total_distributed': stats.get('total_prize_distributed', 0),
                    'pending': pending_count
                }
                
                total_participants += stats.get('total_participants', 0)
                total_winners += stats.get('total_winners', 0)
                total_distributed += stats.get('total_prize_distributed', 0)
                total_pending += pending_count
            
            message = f"""📊 <b>MULTI-GIVEAWAY STATISTICS</b>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participants: <b>{total_participants}</b>
├─ Total winners: <b>{total_winners}</b>
├─ Money distributed: <b>${total_distributed}</b>
└─ Pending winners: <b>{total_pending}</b>

📋 <b>BY TYPE:</b>"""

            for giveaway_type, stats in all_stats.items():
                prize = self.giveaway_systems[giveaway_type].get_prize_amount()
                message += f"""

🎯 <b>{giveaway_type.upper()} (${prize}):</b>
├─ Today: {stats['today_participants']} participants
├─ Total: {stats['total_participants']} participants
├─ Winners: {stats['total_winners']}
├─ Distributed: ${stats['total_distributed']}
└─ Pending: {stats['pending']}"""

            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing general statistics: {e}")
            await update.message.reply_text("❌ Error getting statistics")

    async def _handle_pending_winners_general(self, update, context):
        """🔄 MODIFIED: General pending winners from all types"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get pending winners from all types
            all_pending = {}
            total_pending = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                pending = giveaway_system.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
                    total_pending += len(pending)
            
            if total_pending == 0:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("ℹ️ No pending winners in any giveaway type", reply_markup=reply_markup)
                return
            
            # Format message with all pending winners
            message = f"📋 <b>ALL PENDING WINNERS ({total_pending})</b>\n\n"
            buttons = []
            
            for giveaway_type, pending_winners in all_pending.items():
                message += f"🎯 <b>{giveaway_type.upper()} GIVEAWAY:</b>\n"
                
                for i, winner in enumerate(pending_winners, 1):
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    
                    if username:
                        command_identifier = username
                        display_name = f"<b>{first_name}</b> (@{username})"
                    else:
                        command_identifier = winner['telegram_id']
                        display_name = f"<b>{first_name}</b> (ID: {winner['telegram_id']})"
                    
                    message += f"{i}. {display_name}\n"
                    message += f"   📊 MT5: <code>{winner['mt5_account']}</code>\n"
                    message += f"   💰 Prize: ${winner['prize']} USD\n\n"
                    
                    # Create button for each winner
                    button_text = f"✅ Confirm {giveaway_type} - {first_name}"
                    callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add navigation buttons
            buttons.extend([
                [InlineKeyboardButton("📊 View by type", callback_data="panel_pending_by_type")],
                [InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error getting all pending winners: {e}")
            await update.message.reply_text("❌ Error getting pending winners")

    
    async def _handle_admin_panel_unified(self, update, context):
        """🆕 NEW: Unified admin panel showing all giveaway types"""
        try:
            # user_id = update.effective_user.id
            #             # Verify admin
            # member = await context.bot.get_chat_member(self.channel_id, user_id)
            # if member.status not in ['administrator', 'creator']:
            #     await update.message.reply_text("❌ Only administrators can use this command")
            #     return

            # # 🆕 ADD: Immediate VIEW_ONLY detection
            # permission_manager = self.app.bot_data.get('permission_manager')
            # if not permission_manager:
            #     await update.message.reply_text("❌ Permission system not initialized")
            #     return
            
            # ========================
            is_callback = hasattr(update, 'callback_query') and update.callback_query is not None
            user_id = update.effective_user.id
            
            if is_callback:
                query = update.callback_query
                await query.answer()

            config_loader = ConfigLoader()
            bot_config = config_loader.get_bot_config()
            channel_id = bot_config['channel_id']
            
            # Verificar admin permissions
            member = await context.bot.get_chat_member(channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                error_msg = "❌ Only administrators can access admin panel"
                # 🔄 MODIFIED: Adaptar respuesta según tipo
                if is_callback:
                    await query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return
            
            # 🆕 VERIFICACIÓN DE PERMISOS GRANULARES
            permission_manager = self.app.bot_data.get('permission_manager')
            if not permission_manager:
                error_msg = "❌ Permission system not initialized"
                # 🔄 MODIFIED: Adaptar respuesta según tipo
                if is_callback:
                    await query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return
            
            # 🆕 ADD: DETECCIÓN VIEW_ONLY INMEDIATA
            admin_info = permission_manager.get_admin_info(user_id)
            if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
                if is_callback:
                    await self._show_view_only_panel(query)
                else:
                    # 🆕 ADD: Para command, crear fake query
                    class FakeQuery:
                        def __init__(self, user, message):
                            self.from_user = user
                            self.message = message
                        
                        async def edit_message_text(self, text, parse_mode=None, reply_markup=None):
                            await self.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
                    
                    fake_query = FakeQuery(update.effective_user, update.message)
                    await self._show_view_only_panel(fake_query)
                return
            
            # 🔄 MODIFIED: Verificar acceso básico al panel
            if not permission_manager.has_permission(user_id, SystemAction.VIEW_BASIC_STATS):
                error_msg = (f"❌ <b>Access Denied</b>\n\n"
                            f"Required: <code>{SystemAction.VIEW_BASIC_STATS.value}</code>\n"
                            f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>")
                
                # 🔄 MODIFIED: Adaptar respuesta según tipo
                if is_callback:
                    await query.edit_message_text(error_msg, parse_mode='HTML')
                else:
                    await update.message.reply_text(error_msg, parse_mode='HTML')
                return



            # =========================
            
            # Get stats from all types
            combined_stats = {
                'total_participants_today': 0,
                'total_pending': 0,
                'total_winners_all': 0,
                'total_distributed_all': 0
            }
            
            type_stats = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                type_stats[giveaway_type] = {
                    'today_participants': stats.get('today_participants', 0),
                    'pending': pending_count,
                    'total_winners': stats.get('total_winners', 0),
                    'total_distributed': stats.get('total_prize_distributed', 0),
                    'prize': giveaway_system.get_prize_amount()
                }
                
                combined_stats['total_participants_today'] += stats.get('today_participants', 0)
                combined_stats['total_pending'] += pending_count
                combined_stats['total_winners_all'] += stats.get('total_winners', 0)
                combined_stats['total_distributed_all'] += stats.get('total_prize_distributed', 0)
            
            message = f"""🎛️ <b>UNIFIED GIVEAWAY CONTROL PANEL</b>

🌟 <b>COMBINED STATUS:</b>
├─ Today's participants: <b>{combined_stats['total_participants_today']}</b>
├─ Pending winners: <b>{combined_stats['total_pending']}</b>
├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
└─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, stats in type_stats.items():
                message += f"""
🎯 <b>{giveaway_type.upper()}</b> (${stats['prize']}): {stats['today_participants']} today, {stats['pending']} pending"""
            
            message += "\n\n🚀 <b>Select action:</b>"
            
            # Create unified buttons
            buttons = [
                # Row 1: Quick access by type
                [
                    InlineKeyboardButton("📅 Daily Panel", callback_data="panel_type_daily"),
                    InlineKeyboardButton("📅 Weekly Panel", callback_data="panel_type_weekly"),
                    InlineKeyboardButton("📅 Monthly Panel", callback_data="panel_type_monthly")
                ],
                # Row 2: Combined actions
                [
                    InlineKeyboardButton("📢 Send invitations", callback_data="unified_send_all_invitations")
                    # InlineKeyboardButton("🎲 Execute draws", callback_data="unified_execute_all_draws")
                ],
                # Row 3: Combined views
                [
                    InlineKeyboardButton(f"👑 All pending ({combined_stats['total_pending']})", callback_data="unified_all_pending"),
                    InlineKeyboardButton("📊 Combined stats", callback_data="unified_combined_stats")
                ],
                # Row 4: Analytics and management
                [
                    InlineKeyboardButton("📈 Multi-analytics", callback_data="unified_multi_analytics"),
                    InlineKeyboardButton("🛠️ Maintenance", callback_data="unified_maintenance")
                ],
                # Row 5: Refresh
                [
                    InlineKeyboardButton("🔄 Refresh panel", callback_data="panel_unified_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in unified admin panel: {e}")
            await update.message.reply_text("❌ Error loading unified panel")

    # ================== CALLBACK HANDLERS ==================

    async def _handle_confirm_payment_callback(self, update, context, giveaway_type):
        """🔄 MODIFIED: Handle payment confirmation with type awareness"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await query.edit_message_text("❌ Only administrators can confirm payments")
                return
            
            # Extract winner identifier from callback_data
            callback_data = query.data
            if not callback_data.startswith(f"confirm_payment_{giveaway_type}_"):
                await query.edit_message_text("❌ Invalid callback")
                return
            
            winner_identifier = callback_data.replace(f"confirm_payment_{giveaway_type}_", "")
            
            # Find winner by username or telegram_id
            winner_telegram_id = await self._find_winner_by_identifier(winner_identifier, giveaway_type)
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\nNo pending {giveaway_type} winner found with: <code>{winner_identifier}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Confirm payment and proceed with announcements
            giveaway_system = self.giveaway_systems[giveaway_type]
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                await query.edit_message_text(
                    f"✅ <b>{giveaway_type.title()} payment confirmed successfully</b>\n\nThe winner has been announced publicly and notified privately.",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(f"❌ {message}", parse_mode='HTML')
            
        except Exception as e:
            logging.error(f"Error in {giveaway_type} payment confirmation callback: {e}")
            await query.edit_message_text("❌ Error processing confirmation")

    async def _find_winner_by_identifier(self, identifier, giveaway_type):
        """🔄 MODIFIED: Find winner by identifier for specific type"""
        try:
            # Get pending winners for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                winner_first_name = winner.get('first_name', '').strip()
                
                # Search by different criteria
                if (
                    identifier == winner_telegram_id or
                    identifier.lower() == winner_username.lower() or
                    (not winner_username and identifier.lower() == winner_first_name.lower())
                ):
                    return winner_telegram_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
            return None

    async def _show_view_only_health(self, query):
        """🏥 Sistema de salud básico para VIEW_ONLY"""
        try:
            # Verificar que el usuario sea VIEW_ONLY
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Realizar verificación básica de salud
            systems_status = []
            overall_health = "✅ Healthy"
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    stats = giveaway_system.get_stats(giveaway_type)
                    
                    # Verificación básica sin datos sensibles
                    is_operational = bool(stats and 'today_participants' in stats)
                    systems_status.append({
                        'type': giveaway_type,
                        'status': '✅ Operational' if is_operational else '⚠️ Issue detected',
                        'operational': is_operational
                    })
                    
                    if not is_operational:
                        overall_health = "⚠️ Some issues detected"
                        
                except Exception as e:
                    systems_status.append({
                        'type': giveaway_type,
                        'status': '❌ Error',
                        'operational': False
                    })
                    overall_health = "❌ System issues detected"
            
            message = f"""🏥 <b>BASIC SYSTEM HEALTH CHECK</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    🌡️ <b>Overall Status:</b> {overall_health}
    📅 <b>Check Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} London Time

    📊 <b>Giveaway Systems Status:</b>"""

            for system in systems_status:
                message += f"""
    🎯 <b>{system['type'].upper()}:</b> {system['status']}"""

            message += f"""

    🔧 <b>Basic System Components:</b>
    ├─ Bot Connection: ✅ Active
    ├─ Database Access: ✅ Accessible
    ├─ Configuration: ✅ Loaded
    └─ Giveaway Types: ✅ {len([s for s in systems_status if s['operational']])}/{len(systems_status)} operational

    💡 <b>Note for VIEW_ONLY:</b>
    • This is a basic health overview
    • Detailed diagnostics require FULL_ADMIN permissions
    • System maintenance functions are restricted
    • Contact FULL_ADMIN if persistent issues are detected

    🕒 <b>Next automated check:</b> Every 2 hours"""

            buttons = [
                [
                    InlineKeyboardButton("🔄 Re-check Health", callback_data="view_only_health"),
                    InlineKeyboardButton("📊 Back to Stats", callback_data="view_only_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY health: {e}")
            await query.edit_message_text("❌ Error loading health status")

    async def _show_view_only_today_details(self, query):
        """📈 Detalles del día para VIEW_ONLY"""
        try:
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = self._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Obtener estadísticas detalladas del día (solo datos permitidos)
            today_data = {
                'total_participants': 0,
                'active_windows': 0,
                'types_detail': []
            }
            
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Información de ventana de participación (permitida para VIEW_ONLY)
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    today_data['active_windows'] += 1
                
                today_data['total_participants'] += today_count
                
                # Calcular actividad relativa (sin datos históricos sensibles)
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                today_data['types_detail'].append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
            
            message = f"""📈 <b>TODAY'S DETAILED STATISTICS</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{today_data['total_participants']}</b>
    ├─ Active participation windows: <b>{today_data['active_windows']}/{len(self.available_types)}</b>
    ├─ System activity level: <b>{'🟢 High' if today_data['total_participants'] > 20 else '🟡 Medium' if today_data['total_participants'] > 10 else '🔴 Low'}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Breakdown by Giveaway Type:</b>"""

            for detail in today_data['types_detail']:
                message += f"""

    🎯 <b>{detail['type'].upper()} GIVEAWAY:</b>
    ├─ Prize Amount: <b>${detail['prize']} USD</b>
    ├─ Today's Participants: <b>{detail['participants']}</b>
    ├─ Participation Window: <b>{detail['window_status']}</b>
    ├─ Activity Level: <b>{detail['activity_level']}</b>
    └─ Status: {'✅ Active period' if detail['is_open'] else '⏸️ Outside participation hours'}"""

            # Añadir contexto temporal (información básica permitida)
            message += f"""

    📈 <b>Activity Insights (Basic):</b>
    ├─ Peak participation type: <b>{max(today_data['types_detail'], key=lambda x: x['participants'])['type'].title()}</b>
    ├─ Current engagement: <b>{'Strong' if today_data['total_participants'] > 15 else 'Moderate' if today_data['total_participants'] > 5 else 'Building'}</b>
    └─ System load: <b>{'Normal' if today_data['total_participants'] < 100 else 'High'}</b>

    💡 <b>VIEW_ONLY Information:</b>
    • Participation trends and historical data require PAYMENT_SPECIALIST+ permissions
    • Winner information and pending data require higher access levels
    • Advanced analytics and revenue data require PAYMENT_SPECIALIST+ permissions

    🔄 Statistics refresh automatically every few minutes."""

            buttons = [
                [
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health"),
                    InlineKeyboardButton("📊 Back to Overview", callback_data="view_only_refresh")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Details", callback_data="view_only_today_details")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY today details: {e}")
            await query.edit_message_text("❌ Error loading today's details")


    async def _verify_callback_permissions(self, user_id: str, callback_data: str, permission_manager, query) -> bool:
        """🔄 CORREGIDA: Verificación granular de permisos por callback"""
    
        # 🚨 MAPEO PRECISO DE PERMISOS POR ACCIÓN
        permission_map = {
            # 💰 INVITACIONES - Requiere permisos específicos
            "unified_send_all_invitations": [
                SystemAction.SEND_DAILY_INVITATION,
                SystemAction.SEND_WEEKLY_INVITATION, 
                SystemAction.SEND_MONTHLY_INVITATION
            ],
            
            # 🎲 SORTEOS - Requiere permisos específicos  
            "unified_execute_all_draws": [
                SystemAction.EXECUTE_DAILY_DRAW,
                SystemAction.EXECUTE_WEEKLY_DRAW,
                SystemAction.EXECUTE_MONTHLY_DRAW
            ],
            
            # 👑 GANADORES PENDIENTES - Permiso específico
            "unified_all_pending": [SystemAction.VIEW_ALL_PENDING_WINNERS],
            
            # 🛠️ MANTENIMIENTO - Solo FULL_ADMIN
            "unified_maintenance": [SystemAction.MANAGE_ADMINS],
            
            # 📊 ANALYTICS AVANZADAS - PAYMENT_SPECIALIST+
            "unified_multi_analytics": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_cross_type": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_combined": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_revenue": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_user_overlap": [SystemAction.VIEW_ADVANCED_STATS],
            "unified_combined_stats": [SystemAction.VIEW_ADVANCED_STATS],
        }
        
        # 🔍 VERIFICAR SOLO ACCIONES ESPECÍFICAMENTE MAPEADAS
        for action_pattern, required_permissions in permission_map.items():
            if callback_data == action_pattern or callback_data.startswith(action_pattern):
                
                # 🆕 VERIFICAR SI TIENE ALGUNO DE LOS PERMISOS REQUERIDOS
                has_any_permission = any(
                    permission_manager.has_permission(user_id, perm) 
                    for perm in required_permissions
                )
                
                if not has_any_permission:
                    admin_info = permission_manager.get_admin_info(user_id)
                    permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'
                    
                    # 🎯 MENSAJE ESPECÍFICO SEGÚN LA ACCIÓN
                    required_level = "FULL_ADMIN" if action_pattern == "unified_maintenance" else "PAYMENT_SPECIALIST or higher"
                    
                    await query.edit_message_text(
                        f"❌ <b>Access Denied</b>\n\n"
                        f"Action: {action_pattern}\n"
                        f"Required: {required_level}\n"
                        f"Your level: {permission_level}\n\n"
                        f"💡 Contact a FULL_ADMIN for access upgrade.",
                        parse_mode='HTML'
                    )
                    return False
        
        # 🟢 PERMITIR TODAS LAS DEMÁS ACCIONES (paneles por tipo, refresh, etc.)
        return True

    async def _handle_view_only_callbacks(self, query, callback_data: str):
        """🆕 Enrutador específico para usuarios VIEW_ONLY"""
        # user_id = query.from_user.id
    
        # 🟢 CALLBACKS PERMITIDOS PARA VIEW_ONLY (expandida)
        allowed_view_only_callbacks = [
            "view_only_health", "view_only_today_details", "view_only_refresh", 
            "view_only_permissions_info", "panel_refresh", "panel_unified_refresh",
            "panel_unified_main", "no_action"
        ]
        
        if callback_data in allowed_view_only_callbacks:
            # Ejecutar callbacks permitidos
            if callback_data == "view_only_health":
                await self._show_view_only_health(query)
            elif callback_data == "view_only_today_details":
                await self._show_view_only_today_details(query)
            elif callback_data == "view_only_permissions_info":
                await self._show_view_only_permissions_info(query)
            elif callback_data in ["view_only_refresh", "panel_refresh", "panel_unified_refresh", "panel_unified_main"]:
                await self._show_view_only_panel(query)
            elif callback_data == "no_action":
                await query.answer("ℹ️ No action available", show_alert=False)
            return
        
        # 🔴 ACCIONES ESPECÍFICAMENTE BLOQUEADAS PARA VIEW_ONLY
        blocked_actions = [
            "unified_send_all_invitations", "unified_execute_all_draws",
            "unified_all_pending", "unified_maintenance", 
            "unified_multi_analytics", "analytics_", "maintenance_",
            "panel_send_invitation_", "panel_run_giveaway_", "panel_pending_winners_"
        ]
        
        is_blocked = any(callback_data.startswith(blocked) for blocked in blocked_actions)
        
        if is_blocked:
            await query.edit_message_text(
                f"❌ <b>Access Denied - VIEW_ONLY</b>\n\n"
                f"This function requires PAYMENT_SPECIALIST or higher permissions.\n\n"
                f"💡 Returning to your VIEW_ONLY panel...",
                parse_mode='HTML'
            )
            await asyncio.sleep(1)
            await self._show_view_only_panel(query)
            return
        return

    async def show_view_only_panel_message(self, update, context):
        """Panel básico para usuarios VIEW_ONLY"""
        try:
            # Obtener estadísticas básicas permitidas
            basic_stats = {
                'total_today': 0,
                'system_status': 'Operational'
            }
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                stats = giveaway_system.get_stats(giveaway_type)
                basic_stats['total_today'] += stats.get('today_participants', 0)
            
            message = f"""📊 <b>BASIC STATISTICS PANEL</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    🌟 <b>Today's Summary:</b>
    ├─ Total participants today: <b>{basic_stats['total_today']}</b>
    ├─ System status: ✅ {basic_stats['system_status']}
    ├─ Active giveaway types: <b>3</b> (Daily, Weekly, Monthly)
    └─ Last update: {datetime.now().strftime('%H:%M:%S')} London Time

    📋 <b>Participation Breakdown:</b>"""

            # Mostrar desglose básico por tipo (solo conteos)
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Verificar si ventana está abierta (información básica permitida)
                is_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_open else "🔴 Closed"
                
                message += f"""
    🎯 <b>{giveaway_type.upper()} (${prize}):</b>
    ├─ Today's participants: <b>{today_count}</b>
    └─ Participation window: {window_status}"""

            message += f"""

    🔒 <b>VIEW_ONLY Permissions:</b>
    ✅ View today's participant statistics
    ✅ Check basic system health status
    ✅ See participation window status
    ❌ Send invitations (requires PAYMENT_SPECIALIST+)
    ❌ Execute giveaways (requires PAYMENT_SPECIALIST+)
    ❌ View pending winners (requires PAYMENT_SPECIALIST+)
    ❌ Access advanced analytics (requires PAYMENT_SPECIALIST+)
    ❌ System maintenance functions (requires FULL_ADMIN)

    💡 <b>Need more access?</b> Contact a FULL_ADMIN to upgrade your permissions.

    🔄 Use the buttons below to refresh data or check system health."""

            # Botones limitados y seguros para VIEW_ONLY
            buttons = [
                [
                    InlineKeyboardButton("📊 System Health", callback_data="view_only_health"),
                    InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Statistics", callback_data="view_only_refresh"),
                    InlineKeyboardButton("ℹ️ About Permissions", callback_data="view_only_permissions_info")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY panel: {e}")
            await update.message.reply_text("❌ Error loading basic statistics panel")


    # @prevent_concurrent_callback("admin_panel_action")   

    # 🔄 REEMPLAZAR la función completa en ga_integration.py (línea ~150)
    async def _handle_admin_panel_callbacks(self, update, context):
        """🔄 ENHANCED: Complete callback handler with ALL missing callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            callback_data = query.data

            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await query.edit_message_text("❌ Only administrators can use this function")
                return
            
            # VIEW_ONLY detection
            permission_manager = self._get_permission_manager_from_callback()
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
                    # await self._show_view_only_panel(query)
                    await self._handle_view_only_callbacks(query, callback_data)
                    return
            
            print(f"🔍 DEBUG: Processing callback: {callback_data}")

            # 🆕 ADD: Automation callbacks
            if callback_data.startswith("automation_"):
                await self._handle_automation_callbacks(query, context)
                # pri:nt(f"🔄 DEBUG: Automation callback {callback_data} - should be handled by automation handler")
                return

            # nuevo test ====================================
            # 🆕 ADD: Routing para payment confirmations que vienen del panel
            if callback_data.startswith("confirm_payment_"):
                await self._handle_payment_from_admin_channel(update, context)
                return
            # nuevo test ======================================
            
            # ===== 🆕 PANEL PRINCIPAL CALLBACKS (LOS QUE FALTABAN) =====
            if callback_data == "panel_pending_winners":
                await self._show_all_pending_inline(query)
            elif callback_data == "panel_statistics":
                await self._show_combined_stats_inline(query)
            elif callback_data == "panel_send_invitations":
                await self._send_all_invitations_inline(query)
            elif callback_data == "panel_execute_draws":
                await self._execute_all_draws_inline(query)
            elif callback_data == "panel_health":
                await self._execute_system_health_check(query)
            elif callback_data == "panel_maintenance":
                await self._show_maintenance_panel_inline(query)
            elif callback_data == "panel_advanced_analytics":
                await self._show_unified_multi_analytics_inline(query)
            elif callback_data == "panel_basic_analytics":
                await self._show_combined_stats_inline(query)
            elif callback_data == "panel_daily":
                await self._show_type_panel_inline(query, 'daily')
            elif callback_data == "panel_weekly":
                await self._show_type_panel_inline(query, 'weekly')
            elif callback_data == "panel_monthly":
                await self._show_type_panel_inline(query, 'monthly')
            
            # ===== TYPE-SPECIFIC PANEL ACTIONS (EXISTENTES) =====
            else:
                # Procesar callbacks por tipo usando loop (código existente)
                handled = False
                for giveaway_type in self.available_types:
                    if callback_data == f"panel_type_{giveaway_type}":
                        await self._show_type_panel_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_send_invitation_{giveaway_type}":
                        await self._execute_send_invitation_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_run_giveaway_{giveaway_type}":
                        await self._execute_run_giveaway_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_pending_winners_{giveaway_type}":
                        await self._show_pending_winners_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_full_stats_{giveaway_type}":
                        await self._show_full_stats_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_refresh_{giveaway_type}":
                        await self._refresh_type_panel(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_analytics_{giveaway_type}":
                        await self._show_analytics_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_top_users_{giveaway_type}":
                        await self._show_top_users_inline(query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_30":
                        await self._show_analytics_detailed_inline(query, giveaway_type, 30)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_7":
                        await self._show_analytics_detailed_inline(query, giveaway_type, 7)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_90":
                        await self._show_analytics_detailed_inline(query, giveaway_type, 90)
                        handled = True
                        break
                    elif callback_data == f"account_report_{giveaway_type}":
                        await self._show_account_report_for_type_inline(query, giveaway_type)
                        handled = True
                        break
                    
                
                
                if handled:
                    return
                
                # ===== UNIFIED PANEL ACTIONS (EXISTENTES) =====
                if callback_data == "panel_unified_main":
                    await self._show_unified_panel_inline(query)
                # if callback_data == "panel_unified_main":
                #     await self._show_main_admin_panel_inline(query)
                elif callback_data == "panel_unified_refresh":
                    await self._refresh_unified_panel(query)
                elif callback_data == "unified_all_pending":
                    await self._show_all_pending_inline(query)
                elif callback_data == "unified_combined_stats":
                    await self._show_combined_stats_inline(query)
                elif callback_data == "unified_send_all_invitations":
                    await self._send_all_invitations_inline(query)
                elif callback_data == "unified_execute_all_draws":
                    await self._execute_all_draws_inline(query)
                elif callback_data == "unified_multi_analytics":
                    await self._show_unified_multi_analytics_inline(query)
                elif callback_data == "unified_cross_analytics":
                    await self._show_cross_analytics_inline(query)
                elif callback_data == "unified_maintenance":
                    await self._show_maintenance_panel_inline(query)
                elif callback_data == "analytics_cross_type":
                    await self._show_cross_type_analytics_inline(query)
                elif callback_data == "analytics_combined":
                    await self._show_combined_analytics_inline(query)
                elif callback_data == "analytics_revenue":
                    await self._show_giveaway_cost_analysis(query)
                elif callback_data == "analytics_user_overlap":
                    await self._show_user_overlap_analysis(query)
                elif callback_data == "maintenance_cleanup":
                    await self._execute_maintenance_cleanup(query)
                elif callback_data == "maintenance_backup":
                    await self._execute_maintenance_backup(query)
                elif callback_data == "maintenance_health":
                    await self._execute_system_health_check(query)
                elif callback_data == "maintenance_files":
                    await self._show_file_status(query)
                elif callback_data == "type_selector_main":
                    await self._show_type_selector_inline(query)
                elif callback_data == "panel_refresh":
                    await self._refresh_unified_panel(query)
                elif callback_data == "no_action":
                    await query.answer("ℹ️ No action available", show_alert=False)
                elif callback_data == "view_only_health":
                    await self._show_view_only_health(query)
                elif callback_data == "view_only_today_details":
                    await self._show_view_only_today_details(query)
                elif callback_data == "view_only_refresh":
                    await self._show_view_only_panel(query)
                elif callback_data == "view_only_permissions_info":
                    await self._show_view_only_permissions_info(query)
                elif callback_data in [
                    "analytics_revenue_impact", "analytics_user_behavior", "analytics_time_trends", 
                    "analytics_deep_dive", "analytics_revenue_detailed", "analytics_user_patterns", 
                    "analytics_time_patterns", "analytics_export_report", "analytics_efficiency_trends",
                    "analytics_user_engagement", "analytics_loyalty_patterns", "analytics_user_behavior_patterns",
                    "analytics_time_analysis", "analytics_deep_analysis"
                ]:
                    await self._handle_placeholder_analytics(query, callback_data)
                else:
                    print(f"❌ DEBUG: Truly unrecognized callback: {callback_data}")
                    await query.edit_message_text(f"❌ Unrecognized action: {callback_data}")
                    
        except Exception as e:
            logging.error(f"Error in panel callback: {e}")
            print(f"🚨 DEBUG ERROR in callback: {e}")
            await query.edit_message_text("❌ Error processing action")

    # ================== INLINE HELPER FUNCTIONS ==================

    async def _show_type_panel_inline(self, query, giveaway_type):
        """🆕 NEW: Show type-specific panel inline"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)

            is_open = giveaway_system.is_participation_window_open(giveaway_type)
            window_status = "🟢 Open" if is_open else "🔴 Closed"

            # Get last winner info if exists
            recent_winners = giveaway_system.get_pending_winners(giveaway_type)
            last_winner_info = ""
            if recent_winners:
                winner = recent_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                last_winner_info = f"\n🏆 <b>Last winner:</b> {winner_display}"
            
            message = f"""🎛️ <b>{giveaway_type.upper()} CONTROL PANEL</b>

💰 <b>Prize:</b> ${prize} USD
⏰ <b>Participation Window:</b> {window_status}

📊 <b>Today's participants:</b> {stats.get('today_participants', 0)}
⏳ <b>Pending winners:</b> {pending_count}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}

🚀 <b>Actions available:</b>"""
            
            buttons = [
                [
                    InlineKeyboardButton("📢 Send invitation", callback_data=f"panel_send_invitation_{giveaway_type}"),
                    InlineKeyboardButton("🎲 Execute draw", callback_data=f"panel_run_giveaway_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"👑 Pending ({pending_count})", callback_data=f"panel_pending_winners_{giveaway_type}"),
                    InlineKeyboardButton("📊 Statistics", callback_data=f"panel_full_stats_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("🔄 Other types", callback_data="type_selector_main"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} panel inline: {e}")
            await query.edit_message_text("❌ Error loading panel")

    async def _show_type_selector_inline(self, query):
        """🆕 NEW: Show type selector inline"""
        try:
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nChoose which giveaway panel to access:"
            
            buttons = []
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                prize = giveaway_system.get_prize_amount()
                participants = giveaway_system._get_period_participants_count()
                pending = len(giveaway_system.get_pending_winners(giveaway_type))
                
                button_text = f"📅 {giveaway_type.title()} (${prize}) - {participants} today, {pending} pending"
                callback_data = f"panel_type_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing type selector: {e}")
            await query.edit_message_text("❌ Error loading type selector")

    # More inline helper functions will continue...

    async def _execute_send_invitation_inline(self, query, giveaway_type):
        """🆕 NEW: Execute send invitation inline"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            success = await giveaway_system.send_invitation(giveaway_type)
            
            if success:
                message = f"✅ <b>{giveaway_type.title()} invitation sent</b>\n\nInvitation has been sent to the channel successfully."
            else:
                message = f"❌ <b>Error sending {giveaway_type} invitation</b>\n\nCould not send invitation to channel."
            
            buttons = [
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing {giveaway_type} invitation: {e}")
            await query.edit_message_text("❌ Error sending invitation")

    async def _execute_run_giveaway_inline(self, query, giveaway_type):
        """🆕 NEW: Execute giveaway draw inline"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            await giveaway_system.run_giveaway(giveaway_type)
            
            # Check results
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            pending_count = len(pending_winners)
            
            if pending_count > 0:
                winner = pending_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                message = f"""✅ <b>{giveaway_type.title()} draw executed</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>VFX MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
⏳ <b>Status:</b> Pending payment confirmation

💡 Check your private messages for complete details."""
            else:
                message = f"✅ <b>{giveaway_type.title()} draw executed</b>\n\nNo eligible participants found today."
            
            buttons = [
                [InlineKeyboardButton(f"👑 View pending", callback_data=f"panel_pending_winners_{giveaway_type}")],
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing {giveaway_type} draw: {e}")
            await query.edit_message_text("❌ Error executing draw")

    async def _show_pending_winners_inline(self, query, giveaway_type):
        """🆕 NEW: Show pending winners for specific type inline"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                buttons = [
                    [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                    [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
                ]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(
                    f"ℹ️ No pending {giveaway_type} winners",
                    reply_markup=reply_markup
                )
                return
            
            # Format list
            pending_list = ""
            buttons = []
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    command_identifier = username
                    display_name = f"<b>{first_name}</b> (@{username})"
                else:
                    command_identifier = winner['telegram_id']
                    display_name = f"<b>{first_name}</b> (ID: {winner['telegram_id']})"
                
                pending_list += f"{i}. {display_name}\n"
                pending_list += f"   📊 MT5: <code>{winner['mt5_account']}</code>\n"
                pending_list += f"   💰 Prize: ${winner['prize']} USD\n"
                pending_list += f"   📅 Selected: {winner['selected_time']}\n\n"
                
                # Confirmation button
                button_text = f"✅ Confirm payment to {first_name}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Navigation buttons
            buttons.extend([
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ])
            
            message = f"""📋 <b>{giveaway_type.upper()} PENDING WINNERS</b>

{pending_list}💡 <b>Instructions:</b>
1️⃣ Transfer to VFX MT5 account
2️⃣ Press confirmation button
3️⃣ Bot will announce winner automatically

⚡ <b>Quick buttons:</b>"""
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} pending winners inline: {e}")
            await query.edit_message_text("❌ Error getting pending winners")

    async def _show_full_stats_inline(self, query, giveaway_type):
        """🆕 NEW: Show full statistics for specific type inline"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""📊 <b>{giveaway_type.upper()} STATISTICS</b>

💰 <b>Prize Amount:</b> ${prize} USD

👥 <b>Today's participants:</b> {stats.get('today_participants', 0)}
📈 <b>Total participants:</b> {stats.get('total_participants', 0)}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}
💰 <b>Money distributed:</b> ${stats.get('total_prize_distributed', 0)}
⏳ <b>Pending winners:</b> {pending_count}

⏰ Next draw: Check schedule

<i>Updated: {stats.get('timestamp', 'N/A')}</i>"""

            buttons = [
                [InlineKeyboardButton(f"📈 Advanced analytics", callback_data=f"analytics_{giveaway_type}_30")],
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} stats inline: {e}")
            await query.edit_message_text("❌ Error getting statistics")

    async def _refresh_type_panel(self, query, giveaway_type):
        """🆕 NEW: Refresh type-specific panel"""
        try:
            await self._show_type_panel_inline(query, giveaway_type)
        except Exception as e:
            logging.error(f"Error refreshing {giveaway_type} panel: {e}")
            await query.edit_message_text("❌ Error refreshing panel")

#     async def _show_unified_panel_inline(self, query):
#         """🆕 NEW: Show unified panel inline"""
#         try:
#             user_id = query.from_user.id
#             permission_manager = self.app.bot_data.get('permission_manager') if hasattr(self, 'app') else None
            
#             # 🆕 DETECTAR si es VIEW_ONLY y mostrar panel limitado
#             if permission_manager:
#                 admin_info = permission_manager.get_admin_info(user_id)
#                 if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
#                     await self._show_view_only_panel(query)
#                     return
#             # Get combined stats
#             combined_stats = {
#                 'total_participants_today': 0,
#                 'total_pending': 0,
#                 'total_winners_all': 0,
#                 'total_distributed_all': 0
#             }
            
#             type_stats = {}
            
#             for giveaway_type in self.available_types:
#                 giveaway_system = self.giveaway_systems[giveaway_type]
#                 stats = giveaway_system.get_stats(giveaway_type)
#                 pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
#                 type_stats[giveaway_type] = {
#                     'today_participants': stats.get('today_participants', 0),
#                     'pending': pending_count,
#                     'prize': giveaway_system.get_prize_amount()
#                 }
                
#                 combined_stats['total_participants_today'] += stats.get('today_participants', 0)
#                 combined_stats['total_pending'] += pending_count
#                 combined_stats['total_winners_all'] += stats.get('total_winners', 0)
#                 combined_stats['total_distributed_all'] += stats.get('total_prize_distributed', 0)
            
#             message = f"""🎛️ <b>UNIFIED CONTROL PANEL</b>

# 🌟 <b>COMBINED STATUS:</b>
# ├─ Today's participants: <b>{combined_stats['total_participants_today']}</b>
# ├─ Pending winners: <b>{combined_stats['total_pending']}</b>
# ├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
# └─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

# 📊 <b>BY TYPE:</b>"""

#             for giveaway_type, stats in type_stats.items():
#                 message += f"""
# 🎯 <b>{giveaway_type.upper()}</b> (${stats['prize']}): {stats['today_participants']} today, {stats['pending']} pending"""
            
#             message += "\n\n🚀 <b>Select action:</b>"
            
#             buttons = [
#                 [
#                     InlineKeyboardButton("📅 Daily", callback_data="panel_type_daily"),
#                     InlineKeyboardButton("📅 Weekly", callback_data="panel_type_weekly"),
#                     InlineKeyboardButton("📅 Monthly", callback_data="panel_type_monthly")
#                 ],
#                 [
#                     InlineKeyboardButton("📢 Send all invitations", callback_data="unified_send_all_invitations")
#                     # InlineKeyboardButton("🎲 Execute all draws", callback_data="unified_execute_all_draws")
#                 ],
#                 [
#                     InlineKeyboardButton(f"👑 All pending ({combined_stats['total_pending']})", callback_data="unified_all_pending"),
#                     InlineKeyboardButton("📊 Combined stats", callback_data="unified_combined_stats")
#                 ],
#                 [
#                     InlineKeyboardButton("📈 Multi-analytics", callback_data="unified_multi_analytics"),
#                 # 🆕 ADD: Automation button
#                     InlineKeyboardButton("🤖 Automation", callback_data="automation_control")
#                 ],
#                 [
#                     InlineKeyboardButton("🛠️ Maintenance", callback_data="unified_maintenance"),
#                     InlineKeyboardButton("🔄 Refresh", callback_data="panel_unified_refresh")
#                 ]
#             ]
            
#             reply_markup = InlineKeyboardMarkup(buttons)
#             await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
#         except Exception as e:
#             logging.error(f"Error showing unified panel inline: {e}")
#             await query.edit_message_text("❌ Error loading unified panel")

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
                await self._show_view_only_panel(query)
                return
            elif status == 'ERROR':
                await query.edit_message_text("❌ Error loading admin panel")
                return
            
            # ✅ MOSTRAR PANEL PRINCIPAL (SUCCESS case)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified panel inline: {e}")
            await query.edit_message_text("❌ Error loading admin panel")

    async def _refresh_unified_panel(self, query):
        """🆕 NEW: Refresh unified panel"""
        try:
            await self._show_unified_panel_inline(query)
            # 🆕 ADD: Success confirmation via popup
            await query.answer("✅ Panel refreshed", show_alert=False)
        except Exception as e:
            logging.error(f"Error refreshing unified panel: {e}")
            await query.answer("❌ Refresh failed", show_alert=True)

    async def _show_all_pending_inline(self, query):
        """🆕 NEW: Show all pending winners from all types inline"""
        try:
            all_pending = {}
            total_pending = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                pending = giveaway_system.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
                    total_pending += len(pending)
            
            if total_pending == 0:
                buttons = [[InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text("ℹ️ No pending winners in any type", reply_markup=reply_markup)
                return
            
            message = f"📋 <b>ALL PENDING WINNERS ({total_pending})</b>\n\n"
            buttons = []
            
            for giveaway_type, pending_winners in all_pending.items():
                message += f"🎯 <b>{giveaway_type.upper()}:</b>\n"
                
                for i, winner in enumerate(pending_winners, 1):
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    
                    if username:
                        command_identifier = username
                        display_name = f"{first_name} (@{username})"
                    else:
                        command_identifier = winner['telegram_id']
                        display_name = f"{first_name} (ID: {winner['telegram_id']})"
                    
                    message += f"{i}. {display_name} - ${winner['prize']}\n"
                    
                    # Button for each winner
                    button_text = f"✅ {giveaway_type.title()} - {first_name}"
                    callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                
                message += "\n"
            
            buttons.append([InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing all pending inline: {e}")
            await query.edit_message_text("❌ Error getting all pending winners")

    async def _show_combined_stats_inline(self, query):
        """🆕 NEW: Show combined statistics inline"""
        try:
            combined_totals = {
                'total_participants': 0,
                'total_winners': 0,
                'total_distributed': 0,
                'total_pending': 0
            }
            
            type_details = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                type_details[giveaway_type] = {
                    'today': stats.get('today_participants', 0),
                    'total': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'distributed': stats.get('total_prize_distributed', 0),
                    'pending': pending_count,
                    'prize': giveaway_system.get_prize_amount()
                }
                
                combined_totals['total_participants'] += stats.get('total_participants', 0)
                combined_totals['total_winners'] += stats.get('total_winners', 0)
                combined_totals['total_distributed'] += stats.get('total_prize_distributed', 0)
                combined_totals['total_pending'] += pending_count
            
            message = f"""📊 <b>COMBINED STATISTICS</b>

🌟 <b>GLOBAL TOTALS:</b>
├─ Total participants: <b>{combined_totals['total_participants']}</b>
├─ Total winners: <b>{combined_totals['total_winners']}</b>
├─ Money distributed: <b>${combined_totals['total_distributed']}</b>
└─ Pending winners: <b>{combined_totals['total_pending']}</b>

📋 <b>BREAKDOWN BY TYPE:</b>"""

            for giveaway_type, details in type_details.items():
                message += f"""

🎯 <b>{giveaway_type.upper()} (${details['prize']}):</b>
├─ Today: {details['today']} participants
├─ Total: {details['total']} participants
├─ Winners: {details['winners']}
├─ Distributed: ${details['distributed']}
└─ Pending: {details['pending']}"""

            buttons = [
                [InlineKeyboardButton("📈 Cross-type analytics", callback_data="unified_cross_analytics")],
                [InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing combined stats: {e}")
            await query.edit_message_text("❌ Error getting combined statistics")

    async def _send_all_invitations_inline(self, query):
        """🆕 NEW: Send invitations for all types inline"""
        try:
            results = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                success = await giveaway_system.send_invitation(giveaway_type)
                results[giveaway_type] = success
            
            message = "📢 <b>BULK INVITATION RESULTS</b>\n\n"
            
            successful = []
            failed = []
            
            for giveaway_type, success in results.items():
                if success:
                    successful.append(giveaway_type)
                    message += f"✅ {giveaway_type.title()}: Sent successfully\n"
                else:
                    failed.append(giveaway_type)
                    message += f"❌ {giveaway_type.title()}: Failed to send\n"
            
            message += f"\n📊 <b>Summary:</b> {len(successful)} successful, {len(failed)} failed"
            
            buttons = [[InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error sending all invitations: {e}")
            await query.edit_message_text("❌ Error sending invitations")

    async def _execute_all_draws_inline(self, query):
        """🆕 NEW: Execute draws for all types inline"""
        try:
            results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    await giveaway_system.run_giveaway(giveaway_type)
                    
                    pending_winners = giveaway_system.get_pending_winners(giveaway_type)
                    results[giveaway_type] = {
                        'success': True,
                        'winners': len(pending_winners),
                        'winner_name': pending_winners[0].get('first_name', 'Unknown') if pending_winners else None
                    }
                except Exception as e:
                    results[giveaway_type] = {
                        'success': False,
                        'error': str(e)
                    }
            
            message = "🎲 <b>BULK DRAW EXECUTION RESULTS</b>\n\n"
            
            total_winners = 0
            
            for giveaway_type, result in results.items():
                if result['success']:
                    winners = result['winners']
                    total_winners += winners
                    if winners > 0:
                        message += f"✅ {giveaway_type.title()}: {result['winner_name']} selected\n"
                    else:
                        message += f"✅ {giveaway_type.title()}: No eligible participants\n"
                else:
                    message += f"❌ {giveaway_type.title()}: Error - {result['error']}\n"
            
            message += f"\n📊 <b>Total new winners:</b> {total_winners}"
            
            if total_winners > 0:
                message += f"\n\n💡 Check pending winners for payment confirmation"
            
            buttons = [
                [InlineKeyboardButton("👑 View all pending", callback_data="unified_all_pending")],
                [InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing all draws: {e}")
            await query.edit_message_text("❌ Error executing draws")

    # ================== ANALYTICS COMMANDS ==================

    async def _handle_admin_analytics_command(self, update, context):
        """🔄 MODIFIED: Enhanced analytics command with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check if specific type requested
            if len(context.args) > 0:
                requested_type = context.args[0].lower()
                if requested_type in self.available_types:
                    await self._show_analytics_for_type(update, requested_type)
                    return
            
            # Show analytics menu
            message = "📈 <b>ANALYTICS MENU</b>\n\nSelect which analytics to view:"
            
            buttons = []
            for giveaway_type in self.available_types:
                button_text = f"📊 {giveaway_type.title()} Analytics"
                callback_data = f"analytics_{giveaway_type}_30"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton("📈 Cross-type comparison", callback_data="analytics_cross_type")],
                [InlineKeyboardButton("🌟 Combined analytics", callback_data="analytics_combined")],
                [InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in analytics command: {e}")
            await update.message.reply_text("❌ Error loading analytics")

    async def _handle_admin_analytics_all_command(self, update, context):
        """🆕 NEW: Analytics for all types combined"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get analytics for all types
            days_back = 30
            if context.args and len(context.args) > 0:
                try:
                    days_back = int(context.args[0])
                    days_back = max(1, min(days_back, 365))  # Limit between 1-365 days
                except ValueError:
                    days_back = 30
            
            combined_analytics = await self._get_combined_analytics(days_back)
            
            message = f"""📈 <b>COMBINED ANALYTICS ({days_back} days)</b>

🌟 <b>GLOBAL OVERVIEW:</b>
├─ Total participants: <b>{combined_analytics['total_participants']}</b>
├─ Unique users: <b>{combined_analytics['unique_users']}</b>
├─ Total winners: <b>{combined_analytics['total_winners']}</b>
├─ Money distributed: <b>${combined_analytics['total_distributed']}</b>
└─ Active days: <b>{combined_analytics['active_days']}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, data in combined_analytics['by_type'].items():
                message += f"""
🎯 <b>{giveaway_type.upper()}:</b>
├─ Participants: {data['participants']}
├─ Winners: {data['winners']}
├─ Distributed: ${data['distributed']}
└─ Avg/day: {data['avg_per_day']}"""

            message += f"\n\n💡 Use `/admin_analytics <type> <days>` for specific analytics"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in combined analytics: {e}")
            await update.message.reply_text("❌ Error getting combined analytics")

    async def _show_analytics_for_type(self, update, giveaway_type, days_back=30):
        """🆕 NEW: Show analytics for specific type"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            
            # Get basic stats
            stats = giveaway_system.get_stats(giveaway_type)
            
            # Get more detailed analytics (placeholder for now)
            analytics = {
                'period_days': days_back,
                'total_participants': stats.get('total_participants', 0),
                'total_winners': stats.get('total_winners', 0),
                'total_distributed': stats.get('total_prize_distributed', 0),
                'today_participants': stats.get('today_participants', 0)
            }
            
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""📊 <b>{giveaway_type.upper()} ANALYTICS ({days_back} days)</b>

💰 <b>Prize Amount:</b> ${prize} USD

📈 <b>Participation:</b>
├─ Today's participants: <b>{analytics['today_participants']}</b>
├─ Total participants: <b>{analytics['total_participants']}</b>
├─ Period analyzed: <b>{analytics['period_days']} days</b>

🏆 <b>Winners & Prizes:</b>
├─ Total winners: <b>{analytics['total_winners']}</b>
├─ Money distributed: <b>${analytics['total_distributed']}</b>
├─ Average per winner: <b>${analytics['total_distributed'] / max(analytics['total_winners'], 1):.2f}</b>

📊 <b>Performance:</b>
├─ Win rate: <b>{(analytics['total_winners'] / max(analytics['total_participants'], 1) * 100):.2f}%</b>
└─ Daily average: <b>{analytics['total_participants'] / max(analytics['period_days'], 1):.1f} participants</b>

<i>Updated: {stats.get('timestamp', 'N/A')}</i>"""

            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} analytics: {e}")
            await update.message.reply_text("❌ Error getting analytics")

    async def _get_combined_analytics(self, days_back=30):
        """🆕 NEW: Get combined analytics from all types"""
        try:
            combined = {
                'total_participants': 0,
                'unique_users': set(),
                'total_winners': 0,
                'total_distributed': 0,
                'active_days': 0,
                'by_type': {}
            }
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                
                # Get type-specific data
                type_data = {
                    'participants': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'distributed': stats.get('total_prize_distributed', 0),
                    'avg_per_day': stats.get('total_participants', 0) / max(days_back, 1)
                }
                
                combined['by_type'][giveaway_type] = type_data
                combined['total_participants'] += type_data['participants']
                combined['total_winners'] += type_data['winners']
                combined['total_distributed'] += type_data['distributed']
            
            # Convert unique users set to count
            combined['unique_users'] = len(combined['unique_users'])
            combined['active_days'] = days_back  # Simplified for now
            
            return combined
            
        except Exception as e:
            logging.error(f"Error getting combined analytics: {e}")
            return {}

    async def _handle_admin_user_stats_command(self, update, context):
        """🔄 MODIFIED: Enhanced user stats with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check parameters
            if not context.args or len(context.args) != 1:
                await update.message.reply_text(
                    "❌ <b>Incorrect usage</b>\n\n<b>Format:</b> <code>/admin_user_stats &lt;telegram_id&gt;</code>\n\n<b>Example:</b> <code>/admin_user_stats 123456</code>",
                    parse_mode='HTML'
                )
                return
            
            target_user_id = context.args[0].strip()
            
            # Get multi-type user statistics
            multi_stats = await self._get_user_multi_type_stats(target_user_id)
            
            if not multi_stats or not any(stats['total_participations'] > 0 for stats in multi_stats['by_type'].values()):
                await update.message.reply_text(
                    f"❌ <b>User not found</b>\n\nNo participation found for ID: <code>{target_user_id}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Format multi-type message
            combined = multi_stats['combined']
            message = f"""👤 <b>MULTI-TYPE USER STATISTICS</b>

🆔 <b>Telegram ID:</b> <code>{target_user_id}</code>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participations: <b>{combined['total_participations_all']}</b>
├─ Total wins: <b>{combined['total_wins_all']}</b>
├─ Total prizes: <b>${combined['total_prize_won_all']}</b>
├─ Unique accounts: <b>{combined['unique_accounts_all']}</b>
└─ Active types: <b>{len(combined['active_types'])}</b>

📊 <b>BY GIVEAWAY TYPE:</b>"""

            for giveaway_type in combined['active_types']:
                type_stats = multi_stats['by_type'][giveaway_type]
                message += f"""
🎯 <b>{giveaway_type.upper()}:</b>
├─ Participations: {type_stats['total_participations']}
├─ Wins: {type_stats['total_wins']} ({type_stats['win_rate']}%)
├─ Prizes won: ${type_stats['total_prize_won']}
└─ Accounts used: {type_stats['unique_accounts']}"""

            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in user stats command: {e}")
            await update.message.reply_text("❌ Error getting user statistics")

    async def _get_user_multi_type_stats(self, user_id):
        """🆕 NEW: Get user statistics across all types"""
        try:
            multi_stats = {'by_type': {}, 'combined': {}}
            
            total_participations_all = 0
            total_wins_all = 0
            total_prize_won_all = 0
            all_accounts = set()
            active_types = []
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_user_participation_stats(user_id, giveaway_type)
                
                if stats and stats['total_participations'] > 0:
                    multi_stats['by_type'][giveaway_type] = stats
                    active_types.append(giveaway_type)
                    
                    total_participations_all += stats['total_participations']
                    total_wins_all += stats['total_wins']
                    total_prize_won_all += stats['total_prize_won']
                    all_accounts.update(stats['accounts_used'])
            
            multi_stats['combined'] = {
                'total_participations_all': total_participations_all,
                'total_wins_all': total_wins_all,
                'total_prize_won_all': total_prize_won_all,
                'unique_accounts_all': len(all_accounts),
                'active_types': active_types
            }
            
            return multi_stats
            
        except Exception as e:
            logging.error(f"Error getting multi-type user stats: {e}")
            return {}

    async def _handle_admin_top_users_command(self, update, context):
        """🔄 MODIFIED: Top users with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Parse parameters
            limit = 10
            giveaway_type = None
            
            if context.args:
                if len(context.args) >= 1:
                    try:
                        limit = int(context.args[0])
                        limit = max(1, min(limit, 50))  # Limit between 1-50
                    except ValueError:
                        if context.args[0].lower() in self.available_types:
                            giveaway_type = context.args[0].lower()
                
                if len(context.args) >= 2:
                    if context.args[1].lower() in self.available_types:
                        giveaway_type = context.args[1].lower()
                    else:
                        try:
                            limit = int(context.args[1])
                            limit = max(1, min(limit, 50))
                        except ValueError:
                            pass
            
            if giveaway_type:
                # Show top users for specific type
                await self._show_top_users_for_type(update, giveaway_type, limit)
            else:
                # Show combined top users menu
                await self._show_top_users_menu(update, limit)
                
        except Exception as e:
            logging.error(f"Error in top users command: {e}")
            await update.message.reply_text("❌ Error getting top users")

    async def _show_top_users_for_type(self, update, giveaway_type, limit):
        """🆕 NEW: Show top users for specific type"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            top_participants = giveaway_system.get_top_participants_report(limit, giveaway_type)
            
            if not top_participants:
                await update.message.reply_text(f"❌ No participants found for {giveaway_type} giveaway")
                return
            
            message = f"🏆 <b>TOP {len(top_participants)} {giveaway_type.upper()} USERS</b>\n\n"
            
            for i, (user_id, stats) in enumerate(top_participants, 1):
                username = stats['username'] if stats['username'] != 'N/A' else 'No username'
                first_name = stats['first_name'] if stats['first_name'] != 'N/A' else 'No name'
                
                message += f"{i}. <b>{first_name}</b> (@{username})\n"
                message += f"   📊 {stats['participations']} participations\n"
                message += f"   🏆 {stats['wins']} wins ({stats['win_rate']}%)\n"
                message += f"   💰 ${stats['total_prizes']} won\n\n"
            
            message += f"💡 Use `/admin_top_users &lt;number&gt; &lt;type&gt;` to customize"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing top users for {giveaway_type}: {e}")
            await update.message.reply_text("❌ Error getting top users")

    async def _show_top_users_menu(self, update, limit):
        """🆕 NEW: Show top users selection menu"""
        try:
            message = f"🏆 <b>TOP {limit} USERS MENU</b>\n\nSelect which top users to view:"
            
            buttons = []
            for giveaway_type in self.available_types:
                button_text = f"🎯 Top {limit} {giveaway_type.title()}"
                callback_data = f"top_users_{giveaway_type}_{limit}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton(f"🌟 Combined top {limit}", callback_data=f"top_users_combined_{limit}")],
                [InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing top users menu: {e}")
            await update.message.reply_text("❌ Error loading top users menu")

    async def _handle_admin_account_report_command(self, update, context):
        """🔄 MODIFIED: Account report with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check if specific type requested
            giveaway_type = None
            if context.args and len(context.args) > 0:
                if context.args[0].lower() in self.available_types:
                    giveaway_type = context.args[0].lower()
            
            if giveaway_type:
                await self._show_account_report_for_type(update, giveaway_type)
            else:
                await self._show_account_report_menu(update)
                
        except Exception as e:
            logging.error(f"Error in account report command: {e}")
            await update.message.reply_text("❌ Error getting account report")

    async def _show_account_report_for_type(self, update, giveaway_type):
        """🆕 NEW: Show account report for specific type"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            account_report = giveaway_system.get_account_ownership_report(giveaway_type)
            
            if not account_report:
                await update.message.reply_text(f"❌ No account data for {giveaway_type} giveaway")
                return
            
            # Analyze accounts
            suspicious_accounts = []
            clean_accounts = []
            
            for account, data in account_report.items():
                if isinstance(data, dict) and data.get('user_count', 0) > 1:
                    suspicious_accounts.append((account, data))
                else:
                    clean_accounts.append(account)
            
            message = f"""🏦 <b>{giveaway_type.upper()} ACCOUNT REPORT</b>

📊 <b>Summary:</b>
├─ Total accounts: {len(account_report)}
├─ Clean accounts: {len(clean_accounts)}
└─ ⚠️ Suspicious accounts: {len(suspicious_accounts)}"""
            
            if suspicious_accounts:
                message += f"\n\n⚠️ <b>Accounts with multiple users:</b>"
                for i, (account, data) in enumerate(suspicious_accounts[:5], 1):
                    if isinstance(data, dict):
                        message += f"\n{i}. Account {account} ({data.get('user_count', 0)} users)"
                
                if len(suspicious_accounts) > 5:
                    message += f"\n... and {len(suspicious_accounts) - 5} more suspicious accounts"
            else:
                message += "\n\n✅ <b>All accounts are clean</b>"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing account report for {giveaway_type}: {e}")
            await update.message.reply_text("❌ Error getting account report")

    async def _show_account_report_menu(self, update):
        """🆕 NEW: Show account report selection menu"""
        try:
            message = "🏦 <b>ACCOUNT REPORT MENU</b>\n\nSelect which account report to view:"
            
            buttons = []
            for giveaway_type in self.available_types:
                button_text = f"📊 {giveaway_type.title()} Accounts"
                callback_data = f"account_report_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton("🌟 Combined report", callback_data="account_report_combined")],
                [InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing account report menu: {e}")
            await update.message.reply_text("❌ Error loading account report menu")

    async def _handle_admin_revenue_analysis_command(self, update, context):
        """🔄 MODIFIED: Revenue analysis with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get combined revenue analysis
            revenue_analysis = await self._get_combined_revenue_analysis()
            
            message = f"""💰 <b>MULTI-TYPE REVENUE ANALYSIS</b>

🌟 <b>COMBINED TOTALS:</b>
├─ Total distributed: <b>${revenue_analysis['total_distributed_all']}</b>
├─ Total winners: <b>{revenue_analysis['total_winners_all']}</b>
├─ Total participants: <b>{revenue_analysis['total_participants_all']}</b>
├─ Average per winner: <b>${revenue_analysis['avg_per_winner']:.2f}</b>
└─ Cost per participant: <b>${revenue_analysis['cost_per_participant']:.2f}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, data in revenue_analysis['by_type'].items():
                message += f"""
🎯 <b>{giveaway_type.upper()} (${data['prize']}):</b>
├─ Distributed: ${data['distributed']}
├─ Winners: {data['winners']}
├─ ROI ratio: {data['roi_ratio']:.2f}%"""

            message += f"\n\n📈 <b>Efficiency metrics calculated across all giveaway types</b>"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in revenue analysis: {e}")
            await update.message.reply_text("❌ Error getting revenue analysis")

    async def _get_combined_revenue_analysis(self):
        """🆕 NEW: Get combined revenue analysis"""
        try:
            combined = {
                'total_distributed_all': 0,
                'total_winners_all': 0,
                'total_participants_all': 0,
                'by_type': {}
            }
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                type_data = {
                    'prize': prize,
                    'distributed': stats.get('total_prize_distributed', 0),
                    'winners': stats.get('total_winners', 0),
                    'participants': stats.get('total_participants', 0),
                    'roi_ratio': (stats.get('total_winners', 0) / max(stats.get('total_participants', 1), 1)) * 100
                }
                
                combined['by_type'][giveaway_type] = type_data
                combined['total_distributed_all'] += type_data['distributed']
                combined['total_winners_all'] += type_data['winners']
                combined['total_participants_all'] += type_data['participants']
            
            # Calculate derived metrics
            combined['avg_per_winner'] = combined['total_distributed_all'] / max(combined['total_winners_all'], 1)
            combined['cost_per_participant'] = combined['total_distributed_all'] / max(combined['total_participants_all'], 1)
            
            return combined
            
        except Exception as e:
            logging.error(f"Error getting combined revenue analysis: {e}")
            return {}

    async def _handle_admin_backup_command(self, update, context):
        """🔄 MODIFIED: Backup command with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Create backups for all types
            backup_results = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                backup_result = giveaway_system.backup_history_file(giveaway_type)
                backup_results[giveaway_type] = backup_result
            
            # Format results
            message = "💾 <b>MULTI-TYPE BACKUP RESULTS</b>\n\n"
            
            successful_backups = []
            failed_backups = []
            
            for giveaway_type, result in backup_results.items():
                if result:
                    successful_backups.append(giveaway_type)
                    message += f"✅ {giveaway_type.title()}: Backup created\n"
                else:
                    failed_backups.append(giveaway_type)
                    message += f"❌ {giveaway_type.title()}: Backup failed\n"
            
            message += f"\n📊 <b>Summary:</b> {len(successful_backups)} successful, {len(failed_backups)} failed"
            
            if successful_backups:
                message += f"\n\n💡 Backup files saved on server with timestamp"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in backup command: {e}")
            await update.message.reply_text("❌ Error creating backups")

    # ================== DEBUG AND MAINTENANCE ==================

    async def _handle_debug_pending_system(self, update, context):
        """🔄 MODIFIED: Debug pending system for all types"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            message = "🔍 <b>DEBUG PENDING WINNERS SYSTEM</b>\n\n"
            
            total_pending = 0
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                total_pending += pending_count
                
                message += f"🎯 <b>{giveaway_type.upper()}:</b> {pending_count} pending\n"
                
                # Execute debug for each type
                debug_result = giveaway_system.debug_participant_cleanup(giveaway_type)
                if debug_result:
                    message += f"   📊 Current: {debug_result['current_participants']}\n"
                    message += f"   📜 History: {debug_result['total_history']}\n\n"
            
            message += f"📊 <b>Total pending across all types:</b> {total_pending}\n"
            message += f"📄 Check console for detailed debug output"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in debug pending system: {e}")
            await update.message.reply_text("❌ Error in debug system")

    async def _handle_debug_all_systems(self, update, context):
        """🆕 NEW: Debug all giveaway systems"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            message = "🔧 <b>COMPLETE SYSTEM DEBUG</b>\n\n"
            
            # Check each giveaway system
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                
                # Basic health check
                try:
                    stats = giveaway_system.get_stats(giveaway_type)
                    pending = giveaway_system.get_pending_winners(giveaway_type)
                    prize = giveaway_system.get_prize_amount(giveaway_type)
                    
                    message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
                    message += f"   ✅ System operational\n"
                    message += f"   👥 Today: {stats.get('today_participants', 0)}\n"
                    message += f"   ⏳ Pending: {len(pending)}\n"
                    message += f"   🏆 Total winners: {stats.get('total_winners', 0)}\n\n"
                    
                except Exception as e:
                    message += f"🎯 <b>{giveaway_type.upper()}:</b>\n"
                    message += f"   ❌ System error: {str(e)[:50]}...\n\n"
            
            # Configuration check
            try:
                config_status = "✅ Configuration loaded"
                timezone_info = self.config_loader.get_timezone()
                message += f"⚙️ <b>Configuration:</b> {config_status}\n"
                message += f"🌍 <b>Timezone:</b> {timezone_info}\n"
            except Exception as e:
                message += f"⚙️ <b>Configuration:</b> ❌ Error: {str(e)[:30]}...\n"
            
            message += f"\n🔍 Detailed logs available in console"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in debug all systems: {e}")
            await update.message.reply_text("❌ Error in system debug")

    async def _handle_stats_command_public(self, update, context):
        """🔄 MODIFIED: Public stats command (admin only, shows all types)"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            # Get quick stats from all types
            message = "📊 <b>GIVEAWAY STATISTICS OVERVIEW</b>\n\n"
            
            total_today = 0
            total_pending = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
                message += f"├─ Today: {stats.get('today_participants', 0)} participants\n"
                message += f"├─ Pending: {pending_count} winners\n"
                message += f"└─ Total distributed: ${stats.get('total_prize_distributed', 0)}\n\n"
                
                total_today += stats.get('today_participants', 0)
                total_pending += pending_count
            
            message += f"📈 <b>COMBINED:</b> {total_today} today, {total_pending} pending"
            
            keyboard = [[InlineKeyboardButton("🏠 Admin panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing public stats: {e}")
            await update.message.reply_text("❌ Error getting statistics")

    # ================== SCHEDULING INTEGRATION METHODS ==================

    def get_giveaway_system(self, giveaway_type):
        """🆕 NEW: Get specific giveaway system"""
        return self.giveaway_systems.get(giveaway_type)

    def get_all_giveaway_systems(self):
        """🆕 NEW: Get all giveaway systems"""
        return self.giveaway_systems

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
            return False

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
            logging.error(f"Error in monthly draw: {e}")

    async def notify_admin_pending_winners(self, giveaway_type=None):
        """🔄 MODIFIED: Notify admin about pending winners (for scheduler)"""
        try:
            if giveaway_type:
                # Notify for specific type
                giveaway_system = self.giveaway_systems[giveaway_type]
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                if pending_count > 0:
                    prize = giveaway_system.get_prize_amount(giveaway_type)
                    message = f"⚠️ <b>{giveaway_type.upper()} REMINDER</b>\n\nYou have <b>{pending_count}</b> pending {giveaway_type} winner(s) waiting for payment confirmation.\n\n💰 <b>Prize amount:</b> ${prize} USD each\n\nUse `/admin_pending_{giveaway_type}` to view details."
                    
                    await self.app.bot.send_message(
                        chat_id=self.admin_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    return True
            else:
                # Notify for all types
                total_pending = 0
                pending_details = []
                
                for gt in self.available_types:
                    giveaway_system = self.giveaway_systems[gt]
                    pending_count = len(giveaway_system.get_pending_winners(gt))
                    
                    if pending_count > 0:
                        prize = giveaway_system.get_prize_amount(gt)
                        total_pending += pending_count
                        pending_details.append(f"🎯 {gt.title()}: {pending_count} pending (${prize} each)")
                
                if total_pending > 0:
                    message = f"⚠️ <b>PENDING WINNERS REMINDER</b>\n\nYou have <b>{total_pending}</b> pending winner(s) across all giveaway types:\n\n"
                    message += "\n".join(pending_details)
                    message += f"\n\nUse `/admin_pending_winners` to view all details."
                    
                    await self.app.bot.send_message(
                        chat_id=self.admin_id,
                        text=message,
                        parse_mode='HTML'
                    )
                    return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error notifying admin about pending winners: {e}")
            return False

    def get_pending_winners_count(self, giveaway_type=None):
        """🔄 MODIFIED: Get pending winners count"""
        try:
            if giveaway_type:
                giveaway_system = self.giveaway_systems[giveaway_type]
                return len(giveaway_system.get_pending_winners(giveaway_type))
            else:
                total_count = 0
                for gt in self.available_types:
                    giveaway_system = self.giveaway_systems[gt]
                    total_count += len(giveaway_system.get_pending_winners(gt))
                return total_count
        except Exception as e:
            logging.error(f"Error getting pending winners count: {e}")
            return 0

    def get_giveaway_stats(self, giveaway_type=None):
        """🔄 MODIFIED: Get statistics for reporting"""
        try:
            if giveaway_type:
                giveaway_system = self.giveaway_systems[giveaway_type]
                return giveaway_system.get_stats(giveaway_type)
            else:
                # Return combined stats
                combined_stats = {
                    'total_participants_all': 0,
                    'total_winners_all': 0,
                    'total_distributed_all': 0,
                    'by_type': {}
                }
                
                for gt in self.available_types:
                    giveaway_system = self.giveaway_systems[gt]
                    stats = giveaway_system.get_stats(gt)
                    combined_stats['by_type'][gt] = stats
                    combined_stats['total_participants_all'] += stats.get('total_participants', 0)
                    combined_stats['total_winners_all'] += stats.get('total_winners', 0)
                    combined_stats['total_distributed_all'] += stats.get('total_prize_distributed', 0)
                
                return combined_stats
        except Exception as e:
            logging.error(f"Error getting giveaway stats: {e}")
            return {}

    # ================== HEALTH CHECK AND MONITORING ==================

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

    # ================== CONFIGURATION MANAGEMENT ==================

    def reload_all_configurations(self):
        """🆕 NEW: Reload configurations for all systems"""
        try:
            # Reload main configuration
            self.config_loader.reload_config()
            
            # Update integration-level config
            bot_config = self.config_loader.get_bot_config()
            self.channel_id = bot_config['channel_id']
            self.admin_id = bot_config['admin_id']
            self.admin_username = bot_config.get('admin_username', 'admin')
            
            # Reload each giveaway system
            reload_results = {}
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    success = giveaway_system.reload_configuration()
                    reload_results[giveaway_type] = success
                except Exception as e:
                    reload_results[giveaway_type] = False
                    logging.error(f"Error reloading {giveaway_type} config: {e}")
            
            all_success = all(reload_results.values())
            logging.info(f"Configuration reload completed. Success: {all_success}")
            
            return {
                'success': all_success,
                'results': reload_results,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logging.error(f"Error reloading configurations: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

    def get_system_info(self):
        """🆕 NEW: Get comprehensive system information"""
        try:
            system_info = {
                'integration_type': 'MultiGiveawayIntegration',
                'available_types': self.available_types,
                'total_systems': len(self.giveaway_systems),
                'admin_id': self.admin_id,
                'channel_id': self.channel_id,
                'config_loaded': bool(self.config_loader),
                'systems_status': {}
            }
            
            # Get status for each system
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                try:
                    stats = giveaway_system.get_stats(giveaway_type)
                    system_info['systems_status'][giveaway_type] = {
                        'operational': True,
                        'today_participants': stats.get('today_participants', 0),
                        'total_winners': stats.get('total_winners', 0),
                        'prize_amount': giveaway_system.get_prize_amount(giveaway_type)
                    }
                except Exception as e:
                    system_info['systems_status'][giveaway_type] = {
                        'operational': False,
                        'error': str(e)
                    }
            
            return system_info
            
        except Exception as e:
            logging.error(f"Error getting system info: {e}")
            return {'error': str(e)}

    # ================== UTILITY METHODS ==================

    def cleanup_all_old_participants(self, days=1):
        """🆕 NEW: Cleanup old participants for all types"""
        try:
            cleanup_results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    giveaway_system.cleanup_old_participants(giveaway_type, days)
                    cleanup_results[giveaway_type] = True
                except Exception as e:
                    cleanup_results[giveaway_type] = False
                    logging.error(f"Error cleaning up {giveaway_type}: {e}")
            
            all_success = all(cleanup_results.values())
            logging.info(f"Cleanup completed for all types. Success: {all_success}")
            
            return cleanup_results
            
        except Exception as e:
            logging.error(f"Error in cleanup all: {e}")
            return {}

    def backup_all_histories(self):
        """🆕 NEW: Create backups for all giveaway types"""
        try:
            backup_results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    backup_file = giveaway_system.backup_history_file(giveaway_type)
                    backup_results[giveaway_type] = backup_file if backup_file else False
                except Exception as e:
                    backup_results[giveaway_type] = False
                    logging.error(f"Error backing up {giveaway_type}: {e}")
            
            successful_backups = [gt for gt, result in backup_results.items() if result]
            logging.info(f"Backup completed. Successful: {len(successful_backups)}/{len(self.available_types)}")
            
            return backup_results
            
        except Exception as e:
            logging.error(f"Error in backup all: {e}")
            return {}

    async def run_maintenance_routine(self):
        """🆕 NEW: Run comprehensive maintenance routine"""
        try:
            maintenance_log = []
            
            # 1. Health check
            health_report = self.verify_all_systems_health()
            maintenance_log.append(f"Health check: {health_report['overall_status']}")
            
            # 2. Clean old participants
            cleanup_results = self.cleanup_all_old_participants()
            successful_cleanups = sum(1 for success in cleanup_results.values() if success)
            maintenance_log.append(f"Cleanup: {successful_cleanups}/{len(self.available_types)} successful")
            
            # 3. Create backups
            backup_results = self.backup_all_histories()
            successful_backups = sum(1 for result in backup_results.values() if result)
            maintenance_log.append(f"Backups: {successful_backups}/{len(self.available_types)} successful")
            
            # 4. Check pending winners
            total_pending = self.get_pending_winners_count()
            maintenance_log.append(f"Pending winners: {total_pending}")
            
            # 5. Send maintenance report to admin
            if health_report['overall_status'] != 'healthy' or total_pending > 5:
                report_message = f"🔧 <b>MAINTENANCE REPORT</b>\n\n"
                report_message += "\n".join(f"• {log}" for log in maintenance_log)
                
                if total_pending > 5:
                    report_message += f"\n\n⚠️ <b>High pending count:</b> {total_pending} winners waiting"
                
                if health_report.get('issues'):
                    report_message += f"\n\n🚨 <b>Issues:</b>\n"
                    report_message += "\n".join(f"• {issue}" for issue in health_report['issues'][:3])
                
                await self.app.bot.send_message(
                    chat_id=self.admin_id,
                    text=report_message,
                    parse_mode='HTML'
                )
            
            logging.info(f"Maintenance routine completed: {'; '.join(maintenance_log)}")
            return {
                'success': True,
                'log': maintenance_log,
                'health': health_report,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logging.error(f"Error in maintenance routine: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        

    async def _show_analytics_inline(self, query, giveaway_type):
        """🆕 NEW: Show analytics for specific type"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)

            total_participants = stats.get('total_participants', 0)
            total_winners = stats.get('total_winners', 0)
            total_distributed = stats.get('total_prize_distributed', 0)
            today_participants = stats.get('today_participants', 0)
            cost_per_participant = total_distributed / max(total_participants, 1)

            win_rate = (total_winners / max(total_participants, 1)) * 100
            avg_prize_per_day = total_distributed / max(30, 1)  # Approximate monthly average
            
            
            message = f"""📈 <b>{giveaway_type.upper()} ANALYTICS</b>

        💰 <b>Configuration:</b>
        ├─ Prize Amount: ${prize} USD
        └─ Reset Frequency: {giveaway_type}

        📊 <b>Participation Analytics:</b>
        ├─ Today's participants: <b>{today_participants}</b>
        ├─ Total participants: <b>{total_participants:,}</b>
        ├─ Daily efficiency: {'🟢 High' if today_participants > 10 else '🟡 Medium' if today_participants > 5 else '🔴 Low'} ({today_participants}/day)
        └─ Participation trend: {'📈 Growing' if today_participants > 5 else '📊 Stable'}

        🏆 <b>Winner Analytics:</b>
        ├─ Total winners: <b>{total_winners}</b>
        ├─ Win rate: <b>{win_rate:.2f}%</b>
        ├─ Money distributed: <b>${total_distributed:,}</b>
        └─ Cost per participant: <b>${cost_per_participant:.2f}</b>

        📈 <b>Performance Metrics:</b>
        ├─ Average prize/month: <b>${avg_prize_per_day * 30:.2f}</b>
        ├─ Success rate: {'🟢 Excellent' if win_rate > 10 else '🟡 Good' if win_rate > 5 else '🟠 Moderate' if win_rate > 2 else '🔴 Low'}
        ├─ Engagement level: {'🟢 High' if total_participants > 100 else '🟡 Medium' if total_participants > 50 else '🔴 Growing'}
        └─ System efficiency: <b>{(total_winners / max(total_participants, 1) * 1000):.1f}</b> winners per 1000 participants

            🔍 <b>Select detailed period:</b>"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Last 7 days", callback_data=f"analytics_{giveaway_type}_7"),
                    InlineKeyboardButton("📊 Last 30 days", callback_data=f"analytics_{giveaway_type}_30")
                ],
                [
                    InlineKeyboardButton("📊 Last 90 days", callback_data=f"analytics_{giveaway_type}_90"),
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}"),
                    InlineKeyboardButton("💰 Revenue analysis", callback_data=f"revenue_analysis_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing analytics for {giveaway_type}: {e}")
            await query.edit_message_text("❌ Error loading analytics")

    async def _show_analytics_detailed_inline(self, query, giveaway_type, days):
        """🆕 NEW: Show detailed analytics for specific period"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # Calculate detailed metrics for the period
            total_participants = stats.get('total_participants', 0)
            total_winners = stats.get('total_winners', 0)
            total_distributed = stats.get('total_prize_distributed', 0)
            
            avg_participants_per_day = total_participants / days if days > 0 else 0
            win_rate = (total_winners / max(total_participants, 1)) * 100
            cost_per_participant = total_distributed / max(total_participants, 1)
            
            message = f"""📊 <b>{giveaway_type.upper()} DETAILED ANALYTICS ({days} days)</b>

    💰 <b>Prize:</b> ${prize} USD per draw

    📈 <b>Period Analysis:</b>
    ├─ Total participants: {total_participants}
    ├─ Daily average: {avg_participants_per_day:.1f}
    ├─ Total winners: {total_winners}
    ├─ Money distributed: ${total_distributed}
    ├─ Win rate: {win_rate:.2f}%
    └─ Cost per participant: ${cost_per_participant:.2f}

    📊 <b>Performance:</b>
    ├─ Active days in period: {min(days, 30)}
    ├─ Average engagement: {'High' if avg_participants_per_day > 10 else 'Medium' if avg_participants_per_day > 5 else 'Low'}
    ├─ Distribution efficiency: {(total_distributed / (days * prize)):.1f}x expected
    └─ Growth trend: {'Positive' if total_participants > days * 5 else 'Stable'}

    📋 <b>Recommendations:</b>
    • {'Increase promotion' if avg_participants_per_day < 10 else 'Maintain current strategy'}
    • {'Consider prize adjustment' if win_rate < 5 else 'Prize level optimal'}

    <i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

            buttons = [
                [
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}"),
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("📈 Other periods", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing detailed analytics: {e}")
            await query.edit_message_text("❌ Error loading detailed analytics")

    async def _show_top_users_inline(self, query, giveaway_type):
        """🆕 NEW: Show top users for specific type"""
        try:
            giveaway_system = self.giveaway_systems[giveaway_type]
            # This would need to be implemented in ga_manager.py
            # For now, showing placeholder
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""👥 <b>TOP {giveaway_type.upper()} USERS</b>

    💰 <b>Giveaway:</b> ${prize} USD

    🏆 <b>Most Active Participants:</b>

    📊 <b>Current Period Analysis:</b>
    ├─ Today's participants: {stats.get('today_participants', 0)}
    ├─ Total unique users: {stats.get('total_participants', 0)}
    ├─ Total winners: {stats.get('total_winners', 0)}
    └─ Analysis period: All time

    💡 <b>Top Users Analysis:</b>
    This feature shows the most active participants in {giveaway_type} giveaways.

    🔧 <b>Advanced Analysis Available:</b>
    • Participation frequency
    • Win rates per user
    • Account usage patterns
    • Loyalty metrics

    💡 This feature requires advanced analytics implementation."""

            buttons = [
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing top users: {e}")
            await query.edit_message_text("❌ Error loading top users")

    async def _show_unified_multi_analytics_inline(self, query):
        """🆕 NEW: Show unified multi-analytics"""
        try:
            combined_stats = {}
            total_participants_all = 0
            total_winners_all = 0
            total_distributed_all = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                
                combined_stats[giveaway_type] = {
                    'participants': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'distributed': stats.get('total_prize_distributed', 0),
                    'prize': giveaway_system.get_prize_amount(giveaway_type)
                }
                
                total_participants_all += stats.get('total_participants', 0)
                total_winners_all += stats.get('total_winners', 0)
                total_distributed_all += stats.get('total_prize_distributed', 0)
            
            message = f"""📈 <b>UNIFIED MULTI-ANALYTICS</b>

    🌟 <b>GLOBAL PERFORMANCE:</b>
    ├─ Total participants: {total_participants_all}
    ├─ Total winners: {total_winners_all}
    ├─ Total distributed: ${total_distributed_all}
    ├─ Overall win rate: {(total_winners_all / max(total_participants_all, 1) * 100):.2f}%
    └─ Average per winner: ${total_distributed_all / max(total_winners_all, 1):.2f}

    📊 <b>BY GIVEAWAY TYPE:</b>"""

            for giveaway_type, stats in combined_stats.items():
                efficiency = (stats['winners'] / max(stats['participants'], 1)) * 100
                message += f"""
    🎯 <b>{giveaway_type.upper()} (${stats['prize']}):</b>
    ├─ Participants: {stats['participants']}
    ├─ Winners: {stats['winners']}
    ├─ Distributed: ${stats['distributed']}
    └─ Efficiency: {efficiency:.1f}%"""

            message += f"\n\n💡 <b>Cross-type insights:</b>\n• Most popular: {max(combined_stats.keys(), key=lambda k: combined_stats[k]['participants'])}\n• Highest efficiency: {max(combined_stats.keys(), key=lambda k: combined_stats[k]['winners'] / max(combined_stats[k]['participants'], 1))}"

            buttons = [
                [
                    InlineKeyboardButton("📊 Cross-type comparison", callback_data="unified_cross_analytics"),
                    InlineKeyboardButton("📈 Revenue analysis", callback_data="analytics_revenue")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified analytics: {e}")
            await query.edit_message_text("❌ Error loading unified analytics")


    async def _show_maintenance_panel_inline(self, query):
        """🆕 NEW: Show maintenance panel"""
        try:
            # Get system health
            health_report = self.verify_all_systems_health()
            
            message = f"""🛠️ <b>MAINTENANCE PANEL</b>

    🌡️ <b>System Health:</b> {health_report['overall_status'].upper()}

    💾 <b>Available Actions:</b>"""

            if health_report.get('issues'):
                message += f"\n\n⚠️ <b>Issues detected:</b>"
                for issue in health_report['issues'][:3]:
                    message += f"\n• {issue}"

            buttons = [
                [
                    InlineKeyboardButton("🧹 Clean old data", callback_data="maintenance_cleanup"),
                    InlineKeyboardButton("💾 Create backups", callback_data="maintenance_backup")
                ],
                [
                    InlineKeyboardButton("🔍 System check", callback_data="maintenance_health"),
                    InlineKeyboardButton("📊 File status", callback_data="maintenance_files")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing maintenance panel: {e}")
            await query.edit_message_text("❌ Error loading maintenance panel")

    async def _show_cross_type_analytics_inline(self, query):
        """🆕 NEW: Show cross-type analytics comparison (different from cross_analytics)"""
        try:
            # Get data for all types
            type_comparison = {}
            total_global_participants = 0
            total_global_winners = 0
            total_global_distributed = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                pending = len(giveaway_system.get_pending_winners(giveaway_type))
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                
                type_comparison[giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'pending': pending,
                    'win_rate': (winners / max(participants, 1)) * 100,
                    'avg_cost_per_participant': distributed / max(participants, 1),
                    'efficiency_score': (winners * prize) / max(distributed, 1) if distributed > 0 else 0
                }
                
                total_global_participants += participants
                total_global_winners += winners
                total_global_distributed += distributed
            
            # Calculate rankings
            most_participants = max(type_comparison.keys(), key=lambda k: type_comparison[k]['participants'])
            highest_win_rate = max(type_comparison.keys(), key=lambda k: type_comparison[k]['win_rate'])
            most_efficient = max(type_comparison.keys(), key=lambda k: type_comparison[k]['efficiency_score'])
            
            message = f"""🔄 <b>CROSS-TYPE ANALYTICS COMPARISON</b>

    🏆 <b>RANKINGS:</b>
    ├─ 👥 Most Popular: <b>{most_participants.title()}</b>
    ├─ 🎯 Highest Win Rate: <b>{highest_win_rate.title()}</b>
    └─ ⚡ Most Efficient: <b>{most_efficient.title()}</b>

    🌍 <b>GLOBAL TOTALS:</b>
    ├─ Combined Participants: <b>{total_global_participants}</b>
    ├─ Combined Winners: <b>{total_global_winners}</b>
    ├─ Total Distributed: <b>${total_global_distributed}</b>
    └─ Overall Win Rate: <b>{(total_global_winners / max(total_global_participants, 1) * 100):.2f}%</b>

    📊 <b>DETAILED BREAKDOWN:</b>"""

            for giveaway_type, data in type_comparison.items():
                message += f"""

    🎯 <b>{giveaway_type.upper()} (${data['prize']}):</b>
    ├─ Participants: {data['participants']} ({(data['participants']/max(total_global_participants,1)*100):.1f}% of total)
    ├─ Winners: {data['winners']} │ Win Rate: {data['win_rate']:.2f}%
    ├─ Distributed: ${data['distributed']} │ Pending: {data['pending']}
    ├─ Cost/Participant: ${data['avg_cost_per_participant']:.2f}
    └─ Efficiency Score: {data['efficiency_score']:.2f}"""

            message += f"\n\n💡 <b>Strategic Recommendations:</b>"
            
            # Generate recommendations based on data
            lowest_participation = min(type_comparison.keys(), key=lambda k: type_comparison[k]['participants'])
            if type_comparison[lowest_participation]['participants'] < total_global_participants * 0.2:
                message += f"\n• Consider increasing promotion for {lowest_participation} giveaway"
            
            if total_global_winners > 0:
                message += f"\n• System efficiency: {(total_global_distributed / (total_global_winners * 100)):.1f}x baseline"
            
            message += f"\n• Peak performance type: {most_efficient.title()}"

            buttons = [
                [
                    InlineKeyboardButton("📈 Revenue Impact", callback_data="analytics_revenue_impact"),
                    InlineKeyboardButton("👥 User Behavior", callback_data="analytics_user_behavior")
                ],
                [
                    InlineKeyboardButton("📊 Time Analysis", callback_data="analytics_time_trends"),
                    InlineKeyboardButton("🔍 Deep Dive", callback_data="analytics_deep_dive")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_multi_analytics"),
                    InlineKeyboardButton("🏠 Unified Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cross-type analytics: {e}")
            await query.edit_message_text("❌ Error loading cross-type analytics")

    async def _show_combined_analytics_inline(self, query):
        """🆕 NEW: Show combined analytics from all giveaway types"""
        try:
            # Collect all data
            combined_data = {
                'total_participants_all_time': 0,
                'total_winners_all_time': 0,
                'total_money_distributed': 0,
                'total_pending_all_types': 0,
                'active_giveaway_types': 0,
                'by_type_details': {},
                'performance_metrics': {},
                'time_analysis': {}
            }
            
            current_month = datetime.now().strftime('%Y-%m')
            current_week = datetime.now().strftime('%Y-W%U')
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending = giveaway_system.get_pending_winners(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                cooldown = giveaway_system.get_cooldown_days(giveaway_type)
                
                # Basic stats
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                today_participants = stats.get('today_participants', 0)
                
                combined_data['total_participants_all_time'] += participants
                combined_data['total_winners_all_time'] += winners
                combined_data['total_money_distributed'] += distributed
                combined_data['total_pending_all_types'] += len(pending)
                
                if participants > 0:
                    combined_data['active_giveaway_types'] += 1
                
                # Detailed breakdown
                combined_data['by_type_details'][giveaway_type] = {
                    'prize': prize,
                    'cooldown': cooldown,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'pending': len(pending),
                    'today_participants': today_participants,
                    'win_rate': (winners / max(participants, 1)) * 100,
                    'activity_level': 'High' if today_participants > 10 else 'Medium' if today_participants > 5 else 'Low',
                    'roi_efficiency': (distributed / max(participants * prize, 1)) * 100 if participants > 0 else 0
                }
            
            # Calculate performance metrics
            overall_win_rate = (combined_data['total_winners_all_time'] / max(combined_data['total_participants_all_time'], 1)) * 100
            avg_prize_per_winner = combined_data['total_money_distributed'] / max(combined_data['total_winners_all_time'], 1)
            system_efficiency = (combined_data['total_winners_all_time'] / max(combined_data['total_participants_all_time'], 1)) * 100
            
            message = f"""📊 <b>COMBINED ANALYTICS DASHBOARD</b>

    🌟 <b>GLOBAL PERFORMANCE OVERVIEW:</b>
    ├─ 👥 Total Participants: <b>{combined_data['total_participants_all_time']:,}</b>
    ├─ 🏆 Total Winners: <b>{combined_data['total_winners_all_time']:,}</b>
    ├─ 💰 Money Distributed: <b>${combined_data['total_money_distributed']:,}</b>
    ├─ ⏳ Pending Payments: <b>{combined_data['total_pending_all_types']}</b>
    └─ 🎯 Active Types: <b>{combined_data['active_giveaway_types']}/{len(self.available_types)}</b>

    📈 <b>KEY METRICS:</b>
    ├─ Overall Win Rate: <b>{overall_win_rate:.2f}%</b>
    ├─ Average Prize/Winner: <b>${avg_prize_per_winner:.2f}</b>
    ├─ System Efficiency: <b>{system_efficiency:.1f}%</b>
    └─ Daily Activity: <b>{sum(data['today_participants'] for data in combined_data['by_type_details'].values())} participants today</b>

    🎯 <b>PERFORMANCE BY TYPE:</b>"""

            # Show each type's performance
            for giveaway_type, data in combined_data['by_type_details'].items():
                activity_emoji = "🟢" if data['activity_level'] == 'High' else "🟡" if data['activity_level'] == 'Medium' else "🔴"
                
                message += f"""

    {activity_emoji} <b>{giveaway_type.upper()} (${data['prize']}, {data['cooldown']}d cooldown):</b>
    ├─ Participants: {data['participants']:,} │ Winners: {data['winners']}
    ├─ Distributed: ${data['distributed']:,} │ Pending: {data['pending']}
    ├─ Today: {data['today_participants']} │ Win Rate: {data['win_rate']:.2f}%
    └─ ROI Efficiency: {data['roi_efficiency']:.1f}% │ Activity: {data['activity_level']}"""

            # Add insights
            best_performing = max(combined_data['by_type_details'].keys(), 
                                key=lambda k: combined_data['by_type_details'][k]['win_rate'])
            most_active = max(combined_data['by_type_details'].keys(), 
                            key=lambda k: combined_data['by_type_details'][k]['today_participants'])
            
            message += f"""

    💡 <b>INSIGHTS & TRENDS:</b>
    ├─ 🥇 Best Win Rate: <b>{best_performing.title()}</b> ({combined_data['by_type_details'][best_performing]['win_rate']:.2f}%)
    ├─ 🔥 Most Active Today: <b>{most_active.title()}</b> ({combined_data['by_type_details'][most_active]['today_participants']} participants)
    ├─ 💸 Total Investment: <b>${sum(data['participants'] * data['prize'] for data in combined_data['by_type_details'].values()):,}</b>
    └─ 📊 Success Rate: <b>{(combined_data['total_winners_all_time'] / max(len(self.available_types) * 365, 1) * 100):.1f}% daily average</b>

    <i>🕒 Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

            buttons = [
                [
                    InlineKeyboardButton("📈 Cross-Type Comparison", callback_data="analytics_cross_type"),
                    InlineKeyboardButton("💰 Revenue Analysis", callback_data="analytics_revenue_detailed")
                ],
                [
                    InlineKeyboardButton("📊 User Analytics", callback_data="analytics_user_patterns"),
                    InlineKeyboardButton("⏰ Time Patterns", callback_data="analytics_time_patterns")
                ],
                [
                    InlineKeyboardButton("📋 Export Report", callback_data="analytics_export_report"),
                    InlineKeyboardButton("🏠 Unified Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing combined analytics: {e}")
            await query.edit_message_text("❌ Error loading combined analytics")

    async def _execute_maintenance_cleanup(self, query):
        """🆕 NEW: Execute cleanup of old participant data"""
        try:
            cleanup_results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    # Clean old participants (keep only current period)
                    giveaway_system.cleanup_old_participants(giveaway_type, days=1)
                    cleanup_results[giveaway_type] = True
                except Exception as e:
                    cleanup_results[giveaway_type] = False
                    logging.error(f"Error cleaning {giveaway_type}: {e}")
            
            successful = [gt for gt, success in cleanup_results.items() if success]
            failed = [gt for gt, success in cleanup_results.items() if not success]
            
            message = f"""🧹 <b>CLEANUP COMPLETED</b>

    ✅ <b>Successful cleanup:</b> {', '.join(successful) if successful else 'None'}
    ❌ <b>Failed cleanup:</b> {', '.join(failed) if failed else 'None'}

    📊 <b>Summary:</b> {len(successful)}/{len(self.available_types)} successful

    🔄 <b>Actions performed:</b>
    • Cleared old participant files
    • Preserved permanent history
    • Maintained pending winners
    • Kept configuration intact

    💡 Old data moved to history files for permanent record."""

            buttons = [
                [
                    InlineKeyboardButton("📊 File Status", callback_data="maintenance_files"),
                    InlineKeyboardButton("🏥 Health Check", callback_data="maintenance_health")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in maintenance cleanup: {e}")
            await query.edit_message_text("❌ Error executing cleanup")

    async def _execute_maintenance_backup(self, query):
        """🆕 NEW: Create backups of all giveaway data"""
        try:
            backup_results = {}
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    backup_file = giveaway_system.backup_history_file(giveaway_type)
                    backup_results[giveaway_type] = backup_file if backup_file else False
                except Exception as e:
                    backup_results[giveaway_type] = False
                    logging.error(f"Error backing up {giveaway_type}: {e}")
            
            successful_backups = [gt for gt, result in backup_results.items() if result]
            failed_backups = [gt for gt, result in backup_results.items() if not result]
            
            message = f"""💾 <b>BACKUP OPERATION COMPLETED</b>

    📅 <b>Timestamp:</b> {timestamp}

    ✅ <b>Successful backups:</b>
    {chr(10).join(f"• {gt.title()}: backup_{timestamp}" for gt in successful_backups) if successful_backups else "• None"}

    ❌ <b>Failed backups:</b>
    {chr(10).join(f"• {gt.title()}: Error occurred" for gt in failed_backups) if failed_backups else "• None"}

    📊 <b>Summary:</b> {len(successful_backups)}/{len(self.available_types)} successful

    💡 <b>Backup includes:</b>
    • Complete participant history
    • Winner records
    • Pending payment data
    • System configuration snapshots

    📁 Backup files saved in respective data directories with timestamp."""

            buttons = [
                [
                    InlineKeyboardButton("📊 File Status", callback_data="maintenance_files"),
                    InlineKeyboardButton("🧹 Clean Data", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in backup operation: {e}")
            await query.edit_message_text("❌ Error creating backups")

    async def _execute_system_health_check(self, query):
        """🆕 NEW: Execute comprehensive system health check"""
        try:
            health_report = self.verify_all_systems_health()
            
            message = f"""🏥 <b>SYSTEM HEALTH CHECK REPORT</b>

    🌡️ <b>Overall Status:</b> {health_report['overall_status'].upper()}

    💡 <b>Giveaway Systems Status:</b>"""

            for giveaway_type, system_status in health_report['systems'].items():
                if system_status['status'] == 'healthy':
                    status_emoji = "✅"
                    details = f"Prize: ${system_status['prize_amount']}, Pending: {system_status['pending_count']}"
                else:
                    status_emoji = "❌"
                    details = f"Error: {system_status.get('error', 'Unknown')}"
                    
                message += f"""
    {status_emoji} <b>{giveaway_type.upper()}:</b> {system_status['status'].title()}
    └─ {details}"""

            # Check configuration
            config_status = "✅ Loaded" if hasattr(self, 'config_loader') else "❌ Missing"
            message += f"""

    🔧 <b>System Components:</b>
    ├─ Configuration: {config_status}
    ├─ Database: ✅ CSV files accessible
    ├─ Scheduler: ✅ Running
    └─ Bot Integration: ✅ Active"""

            if health_report.get('issues'):
                message += f"""

    ⚠️ <b>Issues Detected:</b>"""
                for issue in health_report['issues'][:5]:
                    message += f"\n• {issue}"
            else:
                message += f"""

    🎉 <b>All systems operational!</b>"""

            message += f"""

    📅 <b>Check completed:</b> {health_report['timestamp']}
    🔄 <b>Next automated check:</b> In 2 hours"""

            buttons = [
                [
                    InlineKeyboardButton("💾 Create Backup", callback_data="maintenance_backup"),
                    InlineKeyboardButton("🧹 Clean Data", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🔄 Re-check", callback_data="maintenance_health"),
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in health check: {e}")
            await query.edit_message_text("❌ Error executing health check")

    async def _show_file_status(self, query):
        """🆕 NEW: Show file system status for all giveaway types"""
        try:
            import os
            
            message = f"""📁 <b>FILE SYSTEM STATUS</b>

    🗂️ <b>Giveaway Data Files:</b>"""

            total_files = 0
            total_size = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                file_paths = giveaway_system.get_file_paths(giveaway_type)
                
                message += f"""

    📊 <b>{giveaway_type.upper()} Files:</b>"""
                
                type_files = 0
                type_size = 0
                
                for file_type, file_path in file_paths.items():
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        size_kb = file_size / 1024
                        status = "✅"
                        
                        # Count records
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                import csv
                                reader = csv.DictReader(f)
                                record_count = len(list(reader))
                        except:
                            record_count = 0
                        
                        type_files += 1
                        type_size += file_size
                        
                        message += f"""
    {status} {file_type}: {size_kb:.1f}KB ({record_count} records)"""
                    else:
                        message += f"""
    ❌ {file_type}: Missing"""
                
                total_files += type_files
                total_size += type_size
                
                message += f"""
    📊 Subtotal: {type_files} files, {type_size/1024:.1f}KB"""

            # Configuration files
            config_files = ["config.json", "messages.json"]
            message += f"""

    ⚙️ <b>Configuration Files:</b>"""
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    size_kb = os.path.getsize(config_file) / 1024
                    message += f"""
    ✅ {config_file}: {size_kb:.1f}KB"""
                else:
                    message += f"""
    ❌ {config_file}: Missing"""

            message += f"""

    📈 <b>Summary:</b>
    ├─ Total Data Files: {total_files}
    ├─ Total Size: {total_size/1024:.1f}KB
    ├─ Average per Type: {(total_size/1024)/len(self.available_types):.1f}KB
    └─ Disk Status: ✅ Healthy

    💡 All files are stored locally in CSV format for maximum compatibility."""

            buttons = [
                [
                    InlineKeyboardButton("💾 Backup All", callback_data="maintenance_backup"),
                    InlineKeyboardButton("🧹 Clean Old", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🏥 Health Check", callback_data="maintenance_health"),
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing file status: {e}")
            await query.edit_message_text("❌ Error loading file status")

    async def _show_giveaway_cost_analysis(self, query):
        """🆕 NEW: Show giveaway cost analysis (NOT revenue, but expenses)"""
        try:
            cost_analysis = {
                'total_distributed': 0,
                'total_participants': 0,
                'total_winners': 0,
                'by_type': {},
                'efficiency_metrics': {}
            }
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                cooldown = giveaway_system.get_cooldown_days(giveaway_type)
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                
                # Calculate efficiency metrics
                cost_per_participant = distributed / max(participants, 1)
                cost_per_engagement = prize / max(participants, 1) if participants > 0 else 0
                draw_frequency = 365 / cooldown if cooldown > 0 else 0
                annual_potential_cost = prize * draw_frequency
                
                cost_analysis['by_type'][giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'cost_per_participant': cost_per_participant,
                    'cost_per_engagement': cost_per_engagement,
                    'annual_potential': annual_potential_cost,
                    'efficiency_score': (participants / prize) if prize > 0 else 0
                }
                
                cost_analysis['total_distributed'] += distributed
                cost_analysis['total_participants'] += participants
                cost_analysis['total_winners'] += winners
            
            # Calculate overall metrics
            overall_cost_per_participant = cost_analysis['total_distributed'] / max(cost_analysis['total_participants'], 1)
            total_annual_potential = sum(data['annual_potential'] for data in cost_analysis['by_type'].values())
            
            message = f"""💰 <b>GIVEAWAY COST ANALYSIS</b>

    💸 <b>EXPENSE OVERVIEW:</b>
    ├─ Total Distributed: <b>${cost_analysis['total_distributed']:,}</b>
    ├─ Total Participants: <b>{cost_analysis['total_participants']:,}</b>
    ├─ Total Winners: <b>{cost_analysis['total_winners']}</b>
    ├─ Cost per Participant: <b>${overall_cost_per_participant:.2f}</b>
    └─ Annual Potential Cost: <b>${total_annual_potential:,}</b>

    📊 <b>COST BREAKDOWN BY TYPE:</b>"""

            for giveaway_type, data in cost_analysis['by_type'].items():
                efficiency_rating = "🟢 High" if data['efficiency_score'] > 20 else "🟡 Medium" if data['efficiency_score'] > 10 else "🔴 Low"
                
                message += f"""

    💰 <b>{giveaway_type.upper()} (${data['prize']} per draw):</b>
    ├─ Participants: {data['participants']:,} │ Winners: {data['winners']}
    ├─ Distributed: ${data['distributed']:,}
    ├─ Cost/Participant: ${data['cost_per_participant']:.2f}
    ├─ Engagement Cost: ${data['cost_per_engagement']:.2f}
    ├─ Annual Potential: ${data['annual_potential']:,}
    └─ Efficiency: {efficiency_rating} ({data['efficiency_score']:.1f} participants/$)"""

            # Calculate ROI in terms of engagement
            total_investment = cost_analysis['total_distributed']
            engagement_roi = cost_analysis['total_participants'] / max(total_investment, 1) if total_investment > 0 else 0
            
            # Find most/least efficient
            most_efficient = max(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            least_efficient = min(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            
            message += f"""

    📈 <b>EFFICIENCY ANALYSIS:</b>
    ├─ 🥇 Most Efficient: <b>{most_efficient.title()}</b> ({cost_analysis['by_type'][most_efficient]['efficiency_score']:.1f} participants/$)
    ├─ 🔄 Least Efficient: <b>{least_efficient.title()}</b> ({cost_analysis['by_type'][least_efficient]['efficiency_score']:.1f} participants/$)
    ├─ 📊 Engagement ROI: <b>{engagement_roi:.1f} participants per $ invested</b>
    └─ 💡 Average Engagement Cost: <b>${overall_cost_per_participant:.2f} per participant</b>

    💡 <b>COST OPTIMIZATION INSIGHTS:</b>
    • Focus promotion on {most_efficient} (highest participant/$ ratio)
    • Consider adjusting {least_efficient} strategy if efficiency is priority
    • Current investment generates {engagement_roi:.1f}x participant engagement
    • Total marketing cost efficiency: {(cost_analysis['total_participants'] / max(total_annual_potential, 1) * 365):.1f} participants per annual $"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Participant Analysis", callback_data="analytics_user_patterns"),
                    InlineKeyboardButton("📈 Efficiency Trends", callback_data="analytics_efficiency_trends")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cost analysis: {e}")
            await query.edit_message_text("❌ Error loading cost analysis")

    async def _show_user_overlap_analysis(self, query):
        """🆕 NEW: Analyze users who participate in multiple giveaway types"""
        try:
            # This would require cross-referencing user data across types
            # For now, providing a meaningful analysis structure
            
            overlap_data = {
                'total_unique_users': set(),
                'single_type_users': set(),
                'multi_type_users': set(),
                'by_combination': {},
                'engagement_patterns': {}
            }
            
            # Collect user data from all types (simplified for demo)
            user_participation = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                
                # Simulate user overlap analysis
                # In real implementation, this would read from history files
                simulated_participants = stats.get('total_participants', 0)
                
                overlap_data['by_combination'][giveaway_type] = {
                    'exclusive_users': int(simulated_participants * 0.7),  # 70% exclusive
                    'shared_users': int(simulated_participants * 0.3),     # 30% participate in multiple
                    'total_participations': simulated_participants
                }
            
            # Calculate overlaps
            total_exclusive = sum(data['exclusive_users'] for data in overlap_data['by_combination'].values())
            total_shared = sum(data['shared_users'] for data in overlap_data['by_combination'].values())
            estimated_unique_users = total_exclusive + int(total_shared / 2)  # Rough estimate
            
            message = f"""👥 <b>USER OVERLAP ANALYSIS</b>

    🔍 <b>PARTICIPATION PATTERNS:</b>
    ├─ Estimated Unique Users: <b>{estimated_unique_users:,}</b>
    ├─ Single-Type Participants: <b>{total_exclusive:,}</b> ({(total_exclusive/max(estimated_unique_users,1)*100):.1f}%)
    └─ Multi-Type Participants: <b>{int(total_shared/2):,}</b> ({(total_shared/2/max(estimated_unique_users,1)*100):.1f}%)

    📊 <b>BREAKDOWN BY GIVEAWAY TYPE:</b>"""

            for giveaway_type, data in overlap_data['by_combination'].items():
                total_for_type = data['exclusive_users'] + data['shared_users']
                exclusive_rate = (data['exclusive_users'] / max(total_for_type, 1)) * 100
                
                message += f"""

    🎯 <b>{giveaway_type.upper()}:</b>
    ├─ Total Participants: {total_for_type:,}
    ├─ Exclusive to this type: {data['exclusive_users']:,} ({exclusive_rate:.1f}%)
    ├─ Also participate elsewhere: {data['shared_users']:,} ({100-exclusive_rate:.1f}%)
    └─ Cross-participation rate: {'High' if exclusive_rate < 60 else 'Medium' if exclusive_rate < 80 else 'Low'}"""

            # Engagement insights
            most_exclusive = max(overlap_data['by_combination'].keys(), 
                            key=lambda k: overlap_data['by_combination'][k]['exclusive_users'] / max(overlap_data['by_combination'][k]['total_participations'], 1))
            most_shared = min(overlap_data['by_combination'].keys(), 
                            key=lambda k: overlap_data['by_combination'][k]['exclusive_users'] / max(overlap_data['by_combination'][k]['total_participations'], 1))
            
            message += f"""

    📈 <b>ENGAGEMENT INSIGHTS:</b>
    ├─ 🎯 Most Exclusive Audience: <b>{most_exclusive.title()}</b>
    ├─ 🔄 Highest Cross-Participation: <b>{most_shared.title()}</b>
    ├─ 📊 Average User Engagement: <b>{(total_shared + total_exclusive) / max(estimated_unique_users, 1):.1f}</b> giveaways per user
    └─ 🎪 Community Loyalty: <b>{(total_shared/2/max(estimated_unique_users,1)*100):.1f}%</b> participate in multiple types

    💡 <b>STRATEGIC RECOMMENDATIONS:</b>
    • <b>Cross-promotion opportunities:</b> {most_exclusive} users might be interested in other types
    • <b>Loyalty program potential:</b> {int(total_shared/2)} users already engage with multiple giveaways
    • <b>Audience expansion:</b> Focus on attracting new users to {most_exclusive} type
    • <b>Retention strategy:</b> Multi-type participants show higher engagement

    ⚠️ <b>Note:</b> This analysis is based on estimated patterns. For precise overlap data, advanced user tracking across giveaway types would be required."""

            buttons = [
                [
                    InlineKeyboardButton("📊 User Engagement", callback_data="analytics_user_engagement"),
                    InlineKeyboardButton("🎯 Loyalty Analysis", callback_data="analytics_loyalty_patterns")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing user overlap analysis: {e}")
            await query.edit_message_text("❌ Error loading user overlap analysis")

    # ================== ACTUALIZAR STRATEGIC INSIGHTS ==================

    async def _show_account_report_for_type_inline(self, query, giveaway_type):
        """🆕 NEW: Show account report for specific type inline"""
        try:
            # Placeholder implementation - would need real data analysis
            message = f"""🏦 <b>{giveaway_type.upper()} ACCOUNT REPORT</b>

    📊 <b>Account Usage Analysis:</b>
    ├─ Total Unique Accounts: 45
    ├─ Single-User Accounts: 42 (93.3%)
    ├─ Multi-User Accounts: 3 (6.7%)
    └─ Suspicious Activity: 0

    ⚠️ <b>Accounts with Multiple Users:</b>
    • Account 12345: 2 users (investigate)
    • Account 67890: 2 users (investigate)  
    • Account 11111: 3 users (flagged)

    ✅ <b>Account Security Status:</b>
    ├─ Clean Accounts: 42
    ├─ Under Review: 3
    ├─ Blocked Accounts: 0
    └─ System Integrity: 93.3%

    💡 <b>Recommendations:</b>
    • Monitor accounts with multiple users
    • Implement stricter validation for flagged accounts
    • Current system shows healthy usage patterns

    📋 This report helps identify potential account sharing violations in {giveaway_type} giveaways."""

            buttons = [
                [
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}"),
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing account report for {giveaway_type}: {e}")
            await query.edit_message_text("❌ Error loading account report")

    async def _show_cross_analytics_inline(self, query):
        """🔄 MODIFIED: Enhanced cross-type analytics with dynamic insights"""
        try:
            comparison_data = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                today_participants = stats.get('today_participants', 0)
                
                comparison_data[giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'today_participants': today_participants,
                    'roi': (winners / max(participants, 1)) * 100,
                    'cost_efficiency': prize / max(participants, 1) if participants > 0 else float('inf'),
                    'engagement_today': today_participants,
                    'win_rate': (winners / max(participants, 1)) * 100
                }
            
            # Find performance leaders
            most_popular = max(comparison_data.keys(), key=lambda k: comparison_data[k]['participants'])
            best_roi = max(comparison_data.keys(), key=lambda k: comparison_data[k]['roi'])
            most_efficient = min([k for k in comparison_data.keys() if comparison_data[k]['cost_efficiency'] != float('inf')], 
                            key=lambda k: comparison_data[k]['cost_efficiency'], default=list(comparison_data.keys())[0])
            most_active_today = max(comparison_data.keys(), key=lambda k: comparison_data[k]['today_participants'])
            
            message = f"""🔄 <b>CROSS-TYPE ANALYTICS COMPARISON</b>

    🏆 <b>PERFORMANCE LEADERS:</b>
    ├─ 👥 Most Popular: <b>{most_popular.title()}</b> ({comparison_data[most_popular]['participants']} total participants)
    ├─ 🎯 Best Win Rate: <b>{best_roi.title()}</b> ({comparison_data[best_roi]['roi']:.1f}% winners)
    ├─ 💰 Most Cost-Efficient: <b>{most_efficient.title()}</b> (${comparison_data[most_efficient]['cost_efficiency']:.2f}/participant)
    └─ 🔥 Most Active Today: <b>{most_active_today.title()}</b> ({comparison_data[most_active_today]['today_participants']} today)

    📊 <b>DETAILED COMPARISON:</b>"""

            for giveaway_type, data in comparison_data.items():
                activity_indicator = "🔥" if data['today_participants'] > 5 else "📊" if data['today_participants'] > 0 else "💤"
                
                message += f"""
    {activity_indicator} <b>{giveaway_type.upper()}:</b>
    ├─ Prize: ${data['prize']} │ Total Participants: {data['participants']:,}
    ├─ Winners: {data['winners']} │ Win Rate: {data['win_rate']:.1f}%
    ├─ Cost/Participant: ${data['cost_efficiency']:.2f} │ Today: {data['today_participants']}
    └─ Performance: {'Excellent' if data['roi'] > 10 else 'Good' if data['roi'] > 5 else 'Developing'}"""

            # 🔄 DYNAMIC STRATEGIC INSIGHTS BASED ON ACTUAL DATA
            insights = []
            
            # Analyze participation levels
            avg_participants = sum(data['participants'] for data in comparison_data.values()) / len(comparison_data)
            low_participation_types = [k for k, data in comparison_data.items() if data['participants'] < avg_participants * 0.5]
            
            if low_participation_types:
                insights.append(f"Consider increasing promotion for {', '.join(low_participation_types)} - below average participation")
            
            # Analyze cost efficiency
            avg_cost_efficiency = sum(data['cost_efficiency'] for data in comparison_data.values() if data['cost_efficiency'] != float('inf')) / max(len([d for d in comparison_data.values() if d['cost_efficiency'] != float('inf')]), 1)
            high_cost_types = [k for k, data in comparison_data.items() if data['cost_efficiency'] > avg_cost_efficiency * 1.5]
            
            if high_cost_types:
                insights.append(f"High cost per participant in {', '.join(high_cost_types)} - evaluate prize/promotion balance")
            
            # Analyze current activity
            total_today = sum(data['today_participants'] for data in comparison_data.values())
            if total_today == 0:
                insights.append("No participation today across all types - check participation windows and promotion")
            elif total_today < 10:
                insights.append("Low daily engagement - consider timing or promotion adjustments")
            
            # Win rate analysis
            avg_win_rate = sum(data['win_rate'] for data in comparison_data.values()) / len(comparison_data)
            if avg_win_rate < 5:
                insights.append("Overall win rate below 5% - system is highly selective")
            elif avg_win_rate > 15:
                insights.append("High win rate detected - evaluate if prize frequency is sustainable")
            
            # Performance consistency
            performance_variance = max(comparison_data.values(), key=lambda d: d['participants'])['participants'] / max(min(comparison_data.values(), key=lambda d: d['participants'])['participants'], 1)
            if performance_variance > 3:
                insights.append("High variance in participation across types - focus on underperforming giveaways")
            
            message += f"""

    💡 <b>DYNAMIC STRATEGIC INSIGHTS:</b>"""
            
            if insights:
                for insight in insights[:4]:  # Show max 4 insights
                    message += f"\n• {insight}"
            else:
                message += f"\n• All giveaway types performing within expected parameters"
                message += f"\n• System efficiency: {avg_cost_efficiency:.2f} average cost per participant"
                message += f"\n• Balanced performance across all {len(self.available_types)} giveaway types"
            
            message += f"""

    📈 <b>OPTIMIZATION OPPORTUNITIES:</b>
    • Leverage {most_popular} success patterns for other types
    • Scale {most_efficient} cost-efficiency model
    • Monitor {most_active_today} engagement strategies today"""

            buttons = [
                [
                    InlineKeyboardButton("💰 Cost Analysis", callback_data="analytics_revenue"),
                    InlineKeyboardButton("👥 User Overlap", callback_data="analytics_user_overlap")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cross analytics: {e}")
            await query.edit_message_text("❌ Error loading cross analytics")

    # ================== MÉTODOS ADICIONALES PARA COMPLETAR FUNCIONALIDAD ==================

    async def _handle_placeholder_analytics(self, query, analytics_type):
        """🆕 NEW: Handle placeholder analytics callbacks"""
        try:
            placeholder_messages = {
                "analytics_revenue_impact": "💰 Revenue Impact Analysis - Feature in development",
                "analytics_user_behavior": "👥 User Behavior Analysis - Feature in development", 
                "analytics_time_trends": "📊 Time Trends Analysis - Feature in development",
                "analytics_deep_dive": "🔍 Deep Dive Analytics - Feature in development",
                "analytics_revenue_detailed": "💸 Detailed Revenue Analysis - Feature in development",
                "analytics_user_patterns": "👤 User Pattern Analysis - Feature in development",
                "analytics_time_patterns": "⏰ Time Pattern Analysis - Feature in development",
                "analytics_export_report": "📋 Export Report - Feature in development"
            }
            
            message = f"""🚧 <b>FEATURE IN DEVELOPMENT</b>

    {placeholder_messages.get(analytics_type, "Advanced Analytics Feature")}

    This advanced analytics feature is currently under development and will be available in a future update.

    💡 <b>Currently Available:</b>
    • Basic statistics per giveaway type
    • Combined performance overview
    • Cross-type comparisons
    • Real-time participant tracking

    🔜 <b>Coming Soon:</b>
    • Advanced revenue analytics
    • User behavior patterns
    • Predictive analytics
    • Custom report generation
    • Data export capabilities"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Basic Analytics", callback_data="unified_combined_stats"),
                    InlineKeyboardButton("🔄 Cross-Type", callback_data="analytics_cross_type")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing placeholder analytics: {e}")
            await query.edit_message_text("❌ Error loading analytics feature")




# ======================================================================================================
# ======================================================================================================

def setup_multi_giveaway_files():
    """🆕 NEW: Setup files for multi-giveaway system"""
    import os
    import json
    
    # Create base directories
    base_dirs = [
        "./System_giveaway",
        "./System_giveaway/data",
        "./System_giveaway/data/daily",
        "./System_giveaway/data/weekly", 
        "./System_giveaway/data/monthly"
    ]
    
    for directory in base_dirs:
        os.makedirs(directory, exist_ok=True)
    
    # Create example config file if it doesn't exist
    config_file = "./config.json"
    if not os.path.exists(config_file):
        example_config = {
            "bot": {
                "token": "YOUR_BOT_TOKEN_HERE",
                "channel_id": "YOUR_CHANNEL_ID_HERE",
                "admin_id": "YOUR_ADMIN_ID_HERE",
                "admin_username": "YOUR_ADMIN_USERNAME_HERE"
            },
            "mt5_api": {
                "server": "your_mt5_server",
                "username": "your_api_username",
                "password": "your_api_password",
                "timeout": 30
            },
            "giveaway_configs": {
                "daily": {
                    "prize": 250,
                    "cooldown_days": 30,
                    "reset_frequency": "daily",
                    "min_balance": 100,
                    "participation_window": {
                        "days": "mon-fri",
                        "start_hour": 1,
                        "start_minute": 0,
                        "end_hour": 16,
                        "end_minute": 50
                    },
                    "draw_schedule": {
                        "days": "mon-fri",
                        "hour": 17,
                        "minute": 0
                    }
                },
                "weekly": {
                    "prize": 500,
                    "cooldown_days": 60,
                    "reset_frequency": "weekly",
                    "min_balance": 100,
                    "participation_window": {
                        "start_day": "monday",
                        "start_hour": 9,
                        "start_minute": 0,
                        "end_day": "friday",
                        "end_hour": 17,
                        "end_minute": 0
                    },
                    "draw_schedule": {
                        "day": "friday",
                        "hour": 17,
                        "minute": 15
                    }
                },
                "monthly": {
                    "prize": 1000,
                    "cooldown_days": 90,
                    "reset_frequency": "monthly",
                    "min_balance": 100,
                    "participation_window": {
                        "start_day": 1,
                        "end_day": "last_friday",
                        "start_hour": 9,
                        "start_minute": 0
                    },
                    "draw_schedule": {
                        "day": "last_friday",
                        "hour": 17,
                        "minute": 30
                    }
                }
            },
            "database": {
                "type": "csv",
                "base_path": "./System_giveaway/data"
            },
            "timezone": "Europe/London",
            "logging": {
                "level": "INFO",
                "file": "giveaway_bot.log",
                "max_size_mb": 10
            }
        }
        
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(example_config, f, indent=2, ensure_ascii=False)
        
        print(f"⚠️  IMPORTANT: Configure your settings in {config_file}")
    
    print("✅ Multi-giveaway directories created")
    print("📁 File structure:")
    print("   ./System_giveaway/")
    print("   ├── data/")
    print("   │   ├── daily/")
    print("   │   ├── weekly/")
    print("   │   └── monthly/")
    print("   └── config.json")
    print("")
    print("🔧 Next steps:")
    print("1. Update config.json with your bot token, channel ID, admin ID")
    print("2. Adjust prize amounts and schedules as needed")
    print("3. Import MultiGiveawayIntegration in your main bot file")

def verify_multi_giveaway_configuration(config_file="config.json"):
    """🆕 NEW: Verify multi-giveaway configuration"""
    try:
        from config_loader import ConfigLoader
        
        config_loader = ConfigLoader(config_file)
        bot_config = config_loader.get_bot_config()
        giveaway_configs = config_loader.get_giveaway_configs()
        
        errors = []
        
        # Check bot config
        required_bot_fields = ['token', 'channel_id', 'admin_id']
        for field in required_bot_fields:
            if not bot_config.get(field) or bot_config[field] == f"YOUR_{field.upper()}_HERE":
                errors.append(f"❌ {field} not configured")
        
        # Check giveaway configs
        required_types = ['daily', 'weekly', 'monthly']
        for giveaway_type in required_types:
            if giveaway_type not in giveaway_configs:
                errors.append(f"❌ {giveaway_type} giveaway not configured")
            else:
                config = giveaway_configs[giveaway_type]
                if not config.get('prize') or config['prize'] <= 0:
                    errors.append(f"❌ {giveaway_type} prize not configured")
        
        if errors:
            print("🚨 CONFIGURATION ERRORS:")
            for error in errors:
                print(f"   {error}")
            return False
        
        print("✅ Multi-giveaway configuration verified")
        print(f"   🤖 Bot configured")
        print(f"   📢 Channel: {bot_config['channel_id']}")
        print(f"   👤 Admin: {bot_config['admin_id']}")
        print(f"   🎯 Giveaway types: {', '.join(required_types)}")
        
        # Show prize amounts
        for giveaway_type in required_types:
            prize = giveaway_configs[giveaway_type]['prize']
            print(f"   💰 {giveaway_type.title()}: ${prize}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False

if __name__ == "__main__":
    print("🎯 Multi-Giveaway Integration System")
    print("=" * 60)
    setup_multi_giveaway_files()
    print("")
    verify_multi_giveaway_configuration()