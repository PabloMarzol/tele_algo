
def check_automation_dependencies():
    """Check if required dependencies for automation are installed"""
    try:
        import apscheduler
        print("✅ APScheduler available")
        return True
    except ImportError:
        print("❌ APScheduler not found")
        print("💡 Install with: pip install apscheduler")
        return False

# Rate limiting
# - user_last_action = {} (variable global)
# - RATE_LIMIT_SECONDS = 3

def is_user_rate_limited(user_id):
    """Simple rate limiting"""
    import time
    current_time = time.time()
    last_action = user_last_action.get(user_id, 0)
    
    if current_time - last_action < RATE_LIMIT_SECONDS:
        return True
    
    user_last_action[user_id] = current_time
    return False

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
        
async def notify_payment_confirmed_to_authorized_admins(context, winner_identifier, giveaway_type, confirmed_by, prize):
    """
    🔔 NOTIFICAR confirmación de pago solo a admins con permisos relevantes
    """
    permission_manager = get_permission_manager(context)
    
    # Determinar quién debe recibir la notificación
    relevant_permissions = [
        SystemAction.VIEW_PAYMENT_HISTORY,
        SystemAction.VIEW_ALL_PENDING_WINNERS,
        SystemAction.MANAGE_ADMINS  # FULL_ADMIN siempre debe saber
    ]
    
    # También incluir admins que pueden confirmar este tipo específico
    type_permission_map = {
        'daily': SystemAction.CONFIRM_DAILY_PAYMENTS,
        'weekly': SystemAction.CONFIRM_WEEKLY_PAYMENTS,
        'monthly': SystemAction.CONFIRM_MONTHLY_PAYMENTS
    }
    
    if giveaway_type in type_permission_map:
        relevant_permissions.append(type_permission_map[giveaway_type])
    
    # Obtener todos los admins autorizados (sin duplicados)
    authorized_admins = set()
    for permission in relevant_permissions:
        admins_with_permission = permission_manager.get_admins_with_permission(permission)
        authorized_admins.update(admins_with_permission)
    
    if not authorized_admins:
        logging.warning(f"No authorized admins found for {giveaway_type} payment confirmation notification")
        return
    
    # Mensaje de notificación
    notification_message = f"""✅ <b>{giveaway_type.upper()} PAYMENT CONFIRMED</b>

🏆 <b>Winner:</b> {winner_identifier}
💰 <b>Prize:</b> ${prize} USD
👤 <b>Confirmed by:</b> {confirmed_by}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ <b>Actions completed:</b>
├─ Winner announced in channel
├─ Private congratulation sent
└─ System updated for next {giveaway_type} draw

💡 <b>Status:</b> Payment process complete ✓"""
    
    # Enviar a cada admin autorizado
    success_count = 0
    for admin_id in authorized_admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification_message,
                parse_mode='HTML'
            )
            success_count += 1
        except Exception as e:
            logging.error(f"Error notifying admin {admin_id} about {giveaway_type} payment confirmation: {e}")
    
    logging.info(f"{giveaway_type.title()} payment confirmation sent to {success_count}/{len(authorized_admins)} authorized admins")
