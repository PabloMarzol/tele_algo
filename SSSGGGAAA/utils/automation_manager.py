import logging
import asyncio
from datetime import datetime, timedelta
from utils.config_loader import ConfigLoader
# import ConfigLoader from config_loader

class AutomationManager:
    """🤖 Gestiona toda la automatización del sistema de giveaways"""
    
    def __init__(self, app, multi_giveaway_integration, config_file="config.json"):
        """
        Inicializar AutomationManager
        
        Args:
            app: Telegram Application instance
            multi_giveaway_integration: MultiGiveawayIntegration instance
            config_file: Path to configuration file
        """
        self.app = app
        self.integration = multi_giveaway_integration
        self.config_loader = ConfigLoader(config_file)
        
        # Scheduler
        self.scheduler = None
        
        # Estado de automatización
        self.auto_mode_enabled = {
            'daily': False,
            'weekly': False,
            'monthly': False
        }
        
        # Configuración de invitaciones recurrentes
        self.recurring_invitations_enabled = False
        self.invitation_frequencies = {
            'daily': 2,
            'weekly': 4,
            'monthly': 6
        }
        
        # Obtener configuración inicial
        self._load_automation_config()
        
        logging.info("AutomationManager initialized") 

    def _load_automation_config(self):
        """Cargar configuración de automatización desde config.json"""
        try:
            automation_config = self.config_loader.get_all_config().get('automation', {})
            
            # Cargar modos automáticos por defecto
            default_modes = automation_config.get('default_auto_modes', {})
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                self.auto_mode_enabled[giveaway_type] = default_modes.get(giveaway_type, False)
            
            # Cargar configuración de invitaciones recurrentes
            recurring_config = automation_config.get('recurring_invitations', {})
            self.recurring_invitations_enabled = recurring_config.get('enabled', False)
            
            # Cargar frecuencias personalizadas si existen
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                freq_key = f'{giveaway_type}_frequency_hours'
                if freq_key in recurring_config:
                    self.invitation_frequencies[giveaway_type] = recurring_config[freq_key]
                    
            logging.info(f"Automation config loaded: {self.auto_mode_enabled}")
            logging.info(f"Recurring invitations: {self.recurring_invitations_enabled}")
            
        except Exception as e:
            logging.warning(f"Error loading automation config, using defaults: {e}")
    
    def get_giveaway_system(self, giveaway_type):
        """Helper para obtener giveaway system desde integration"""
        return self.integration.get_giveaway_system(giveaway_type)   

    # 🤖 SETUP AUTOMATIZACIÓN

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


# 🎛️ CONTROL AUTOMATIZACIÓN
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


# ⚡ EJECUCIÓN AUTOMÁTICA
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


# 🔔 NOTIFICACIONES AUTOMÁTICAS
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