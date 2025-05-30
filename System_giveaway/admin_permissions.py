# admin_permissions.py - Sistema de Permisos Granulares MEJORADO
"""
VERSIÓN HÍBRIDA: Tu implementación robusta + acciones adicionales de mi versión
Mantiene toda tu funcionalidad superior y agrega más opciones de configuración
"""

import json
import os
import logging
from datetime import datetime, time
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from functools import wraps
from telegram.ext import ContextTypes

class SystemAction(Enum):
    """🎯 ACCIONES EXPANDIDAS - Manteniendo tu estructura pero con más opciones"""
    
    # === GIVEAWAY MANAGEMENT === (TUS ORIGINALES)
    SEND_DAILY_INVITATION = "send_daily_invitation"
    SEND_WEEKLY_INVITATION = "send_weekly_invitation"
    SEND_MONTHLY_INVITATION = "send_monthly_invitation"
    SEND_ALL_INVITATIONS = "send_all_invitations"
    
    EXECUTE_DAILY_DRAW = "execute_daily_draw"
    EXECUTE_WEEKLY_DRAW = "execute_weekly_draw"
    EXECUTE_MONTHLY_DRAW = "execute_monthly_draw"
    EXECUTE_ALL_DRAWS = "execute_all_draws"
    
    # === PAYMENT MANAGEMENT === (TUS ORIGINALES)
    CONFIRM_DAILY_PAYMENTS = "confirm_daily_payments"
    CONFIRM_WEEKLY_PAYMENTS = "confirm_weekly_payments"
    CONFIRM_MONTHLY_PAYMENTS = "confirm_monthly_payments"
    CONFIRM_ALL_PAYMENTS = "confirm_all_payments"
    
    # === STATISTICS & ANALYTICS === (TUS ORIGINALES + NUEVAS)
    VIEW_BASIC_STATS = "view_basic_stats"
    VIEW_ADVANCED_STATS = "view_advanced_stats"
    VIEW_REVENUE_REPORTS = "view_revenue_reports"
    VIEW_USER_ANALYTICS = "view_user_analytics"
    VIEW_CROSS_TYPE_ANALYTICS = "view_cross_type_analytics"
    VIEW_ALL_PENDING_WINNERS = "view_all_pending_winners"
    VIEW_PAYMENT_HISTORY = "view_payment_history"
    VIEW_BASIC_ANALYTICS = "view_basic_analytics"
    VIEW_PARTICIPANT_COUNT = "view_participant_count"
    
    # 🆕 NUEVAS ACCIONES ADICIONALES
    VIEW_TOP_PARTICIPANTS = "view_top_participants"
    VIEW_ACCOUNT_REPORTS = "view_account_reports"
    EXPORT_PAYMENT_HISTORY = "export_payment_history"
    VIEW_DAILY_ANALYTICS = "view_daily_analytics"
    VIEW_WEEKLY_ANALYTICS = "view_weekly_analytics"
    VIEW_MONTHLY_ANALYTICS = "view_monthly_analytics"
    
    # === SYSTEM MANAGEMENT === (TUS ORIGINALES + NUEVAS)
    MANAGE_ADMINS = "manage_admins"
    MODIFY_PRIZE_AMOUNTS = "modify_prize_amounts"
    MODIFY_SCHEDULES = "modify_schedules"
    BACKUP_SYSTEM = "backup_system"
    EXPORT_DATA = "export_data"
    
    # 🆕 NUEVAS GESTIÓN DE SISTEMA
    ADD_ADMINS = "add_admins"
    REMOVE_ADMINS = "remove_admins"
    MODIFY_ADMIN_PERMISSIONS = "modify_admin_permissions"
    SYSTEM_CONFIG = "system_config"
    MODIFY_COOLDOWN_PERIODS = "modify_cooldown_periods"
    RESTORE_BACKUP = "restore_backup"
    
    # === DEBUG Y MANTENIMIENTO === (TUS ORIGINALES + NUEVAS)
    DEBUG_ACCESS = "debug_access"
    HEALTH_CHECK = "health_check"
    TEST_CONNECTIONS = "test_connections"
    VIEW_SYSTEM_LOGS = "view_system_logs"
    MAINTENANCE_MODE = "maintenance_mode"
    
    # 🆕 NUEVAS DEBUG
    RESTART_SERVICES = "restart_services"
    EMERGENCY_STOP = "emergency_stop"
    FORCE_CLEANUP = "force_cleanup"
    
    # 🆕 NOTIFICACIONES
    RECEIVE_WINNER_NOTIFICATIONS = "receive_winner_notifications"
    RECEIVE_PAYMENT_NOTIFICATIONS = "receive_payment_notifications"
    RECEIVE_SYSTEM_ALERTS = "receive_system_alerts"
    RECEIVE_ERROR_NOTIFICATIONS = "receive_error_notifications"
    RECEIVE_REVENUE_REPORTS = "receive_revenue_reports"
    
    # 🆕 USER MANAGEMENT
    VIEW_USER_DETAILS = "view_user_details"
    INVESTIGATE_USERS = "investigate_users"
    BAN_USERS = "ban_users"
    UNBAN_USERS = "unban_users"
    VIEW_USER_HISTORY = "view_user_history"

    # 🆕 NUEVOS PERMISOS GRANULARES
    VIEW_PANEL_BASIC = "view_panel_basic"           # Panel limitado para VIEW_ONLY
    VIEW_TODAY_STATS = "view_today_stats"           # Solo estadísticas del día
    # VIEW_PARTICIPANT_COUNT = "view_participant_count" # Solo conteos básicos
    
    # 🆕 SEPARAR analytics por nivel
    # VIEW_BASIC_ANALYTICS = "view_basic_analytics"    # Solo para VIEW_ONLY
    VIEW_ADVANCED_ANALYTICS = "view_advanced_analytics" # Para especialistas+

class PermissionGroup(Enum):
    """Grupos predefinidos de permisos - MANTENIENDO TU ESTRUCTURA"""
    FULL_ADMIN = "FULL_ADMIN"
    PAYMENT_SPECIALIST = "PAYMENT_SPECIALIST"
    VIEW_ONLY = "VIEW_ONLY"
    CUSTOM = "CUSTOM"

class AdminPermissionManager:
    """TU IMPLEMENTACIÓN MANTENIDA + Mejoras adicionales"""
    
    def __init__(self, config_file: str = "admin_permissions.json"):
        self.config_file = config_file
        self.admins: Dict[str, Dict] = {}
        self.permission_groups: Dict[str, List[SystemAction]] = {}
        self.logger = logging.getLogger('AdminPermissions')
        
        self._initialize_permission_groups()
        self._load_config()
    
    def _initialize_permission_groups(self):
        """TU FUNCIÓN ORIGINAL + Grupos adicionales"""
        
        # ✅ MANTENIENDO TUS GRUPOS ORIGINALES
        
        # FULL_ADMIN: Acceso total sin restricciones
        self.permission_groups[PermissionGroup.FULL_ADMIN.value] = [action for action in SystemAction]
        
        # PAYMENT_SPECIALIST: Enfocado en pagos y analytics
        self.permission_groups[PermissionGroup.PAYMENT_SPECIALIST.value] = [
            # Confirmar pagos (TU CONFIGURACIÓN)
            SystemAction.CONFIRM_DAILY_PAYMENTS,
            SystemAction.CONFIRM_WEEKLY_PAYMENTS,
            SystemAction.CONFIRM_MONTHLY_PAYMENTS,
            # SystemAction.CONFIRM_ALL_PAYMENTS,
            
            # Ejecutar sorteos (CON restricciones horarias - TU CONFIGURACIÓN)
            SystemAction.EXECUTE_DAILY_DRAW,
            SystemAction.EXECUTE_WEEKLY_DRAW,
            SystemAction.EXECUTE_MONTHLY_DRAW,
            
            # Ver estadísticas avanzadas (TU CONFIGURACIÓN)
            SystemAction.VIEW_ADVANCED_STATS,
            SystemAction.VIEW_REVENUE_REPORTS,
            SystemAction.VIEW_USER_ANALYTICS,
            SystemAction.VIEW_ALL_PENDING_WINNERS,
            SystemAction.VIEW_PAYMENT_HISTORY,
            
            # 🆕 NUEVAS PARA PAYMENT_SPECIALIST
            SystemAction.VIEW_TOP_PARTICIPANTS,
            SystemAction.VIEW_ACCOUNT_REPORTS,
            SystemAction.VIEW_DAILY_ANALYTICS,
            SystemAction.VIEW_WEEKLY_ANALYTICS,
            SystemAction.VIEW_MONTHLY_ANALYTICS,
            SystemAction.EXPORT_PAYMENT_HISTORY,
            
            # Health check básico (TU CONFIGURACIÓN)
            SystemAction.HEALTH_CHECK,
            SystemAction.VIEW_BASIC_STATS,
            
            # 🆕 NOTIFICACIONES
            SystemAction.RECEIVE_WINNER_NOTIFICATIONS,
            SystemAction.RECEIVE_PAYMENT_NOTIFICATIONS,
            SystemAction.RECEIVE_SYSTEM_ALERTS,
            # SystemAction.RECEIVE_REVENUE_REPORTS
        ]
        
        # VIEW_ONLY: Solo visualización (TU CONFIGURACIÓN)
        self.permission_groups[PermissionGroup.VIEW_ONLY.value] = [
            SystemAction.VIEW_PANEL_BASIC,
            SystemAction.VIEW_BASIC_STATS,
            SystemAction.VIEW_TODAY_STATS,
            SystemAction.VIEW_PARTICIPANT_COUNT,
            SystemAction.VIEW_ALL_PENDING_WINNERS,
            SystemAction.VIEW_BASIC_ANALYTICS,
            # SystemAction.HEALTH_CHECK
        ]
    
    def _load_config(self):
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.admins = data.get('admins', {})
                    self.logger.info(f"Loaded {len(self.admins)} admin configurations")
            else:
                # Crear configuración por defecto
                self._create_default_config()
                self.logger.info("Created default admin configuration")
        except Exception as e:
            self.logger.error(f"Error loading admin config: {e}")
            self._create_default_config()
    
    def _create_default_config(self):
        """TU FUNCIÓN ORIGINAL - Manteniendo tu configuración específica"""
        default_config = {
            "admins": {
                "8177033621": {  # TU ID
                    "name": "Admin Principal (Tú)",
                    "permission_group": "FULL_ADMIN",
                    "active": True,
                    "created_date": datetime.now().strftime('%Y-%m-%d'),
                    "restrictions": {
                        "time_based": False,
                        "allowed_hours": {},
                        "timezone": "Europe/London"
                    },
                    "notifications": {
                        "private_notifications": True,
                        "channel_notifications": True
                    }
                },
                "ID_ADMIN_1": {  # REEMPLAZAR con ID real
                    "name": "Administrador 1",
                    "permission_group": "FULL_ADMIN",
                    "active": True,
                    "created_date": datetime.now().strftime('%Y-%m-%d'),
                    "restrictions": {
                        "time_based": False,
                        "allowed_hours": {},
                        "timezone": "Europe/London"
                    },
                    "notifications": {
                        "private_notifications": True,
                        "channel_notifications": True
                    }
                },
                "ID_DUENO": {  # REEMPLAZAR con ID real del dueño
                    "name": "Dueño del Negocio",
                    "permission_group": "PAYMENT_SPECIALIST",
                    "active": True,
                    "created_date": datetime.now().strftime('%Y-%m-%d'),
                    "restrictions": {
                        "time_based": True,  # CON restricciones horarias
                        "allowed_hours": {
                            "daily_draw": [17],    # Solo 5:00 PM
                            "weekly_draw": [17],   # Solo 5:00 PM
                            "monthly_draw": [17]   # Solo 5:00 PM
                        },
                        "timezone": "Europe/London"
                    },
                    "custom_permissions": [],
                    "denied_permissions": [],
                    "notifications": {
                        "private_notifications": True,
                        "channel_notifications": True
                    }
                },
                "ID_OTRO_ADMIN": {  # REEMPLAZAR con ID real
                    "name": "Admin Especializado",
                    "permission_group": "PAYMENT_SPECIALIST", 
                    "active": True,
                    "created_date": datetime.now().strftime('%Y-%m-%d'),
                    "restrictions": {
                        "time_based": True,  # CON restricciones horarias
                        "allowed_hours": {
                            "daily_draw": [17],    # Solo 5:00 PM
                            "weekly_draw": [17],   # Solo 5:00 PM
                            "monthly_draw": [17]   # Solo 5:00 PM
                        },
                        "timezone": "Europe/London"
                    },
                    "custom_permissions": [],
                    "denied_permissions": ["MODIFY_PRIZE_AMOUNTS"],  # Específicamente bloqueado
                    "notifications": {
                        "private_notifications": True,
                        "channel_notifications": True
                    }
                }
            },
            "system_config": {
                "require_two_factor_for_draws": False,
                "log_all_actions": True,
                "notification_channel_id": None,
                "default_timezone": "Europe/London"
            }
        }
        
        self.admins = default_config["admins"]
        self._save_config(default_config)
    
    def _save_config(self, config_data: Dict):
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving admin config: {e}")

    def verify_time_restricted_action(self, user_id: str, action: SystemAction, giveaway_type: str = None) -> Tuple[bool, str]:
        """🆕 NEW: Verificación completa incluyendo restricciones horarias"""
        
        # 1. Verificar permiso básico
        if not self.has_permission(user_id, action):
            return False, f"No permission for {action.value}"
        
        # 2. Verificar restricciones horarias si aplica
        draw_actions = [
            SystemAction.EXECUTE_DAILY_DRAW,
            SystemAction.EXECUTE_WEEKLY_DRAW,
            SystemAction.EXECUTE_MONTHLY_DRAW
        ]
        
        if action in draw_actions and giveaway_type:
            can_execute, message = self.can_execute_draw_now(user_id, giveaway_type)
            if not can_execute:
                return False, f"Time restriction: {message}"
        
        # 3. Verificar si el usuario está activo
        admin_info = self.get_admin_info(user_id)
        if not admin_info or not admin_info.get('active', True):
            return False, "User not active"
        
        return True, "Authorized"
    
    # ============== TUS FUNCIONES ORIGINALES MANTENIDAS ==============
    
    def has_permission(self, user_id: str, action: SystemAction) -> bool:
        """TU FUNCIÓN ORIGINAL - Superior a la mía"""
        user_id = str(user_id)
        
        if user_id not in self.admins:
            return False
        
        admin_info = self.admins[user_id]
        
        # Verificar si está activo
        if not admin_info.get('active', True):
            return False
        
        # Obtener permisos del grupo
        permission_group = admin_info.get('permission_group', 'VIEW_ONLY')
        group_permissions = self.permission_groups.get(permission_group, [])
        
        # Verificar permisos personalizados
        custom_permissions = admin_info.get('custom_permissions', [])
        denied_permissions = admin_info.get('denied_permissions', [])
        
        # Convertir strings a SystemAction si es necesario
        if isinstance(action, str):
            try:
                action = SystemAction(action)
            except ValueError:
                return False
        
        # Verificar si está explícitamente denegado
        if action.value in denied_permissions:
            return False
        
        # Verificar si tiene el permiso (grupo o personalizado)
        return (action in group_permissions or 
                action.value in custom_permissions)
    
    def can_execute_draw_now(self, user_id: str, giveaway_type: str) -> Tuple[bool, str]:
        """TU FUNCIÓN ORIGINAL - Mucho más robusta que la mía"""
        user_id = str(user_id)
        
        # Mapear tipo de giveaway a acción
        action_map = {
            'daily': SystemAction.EXECUTE_DAILY_DRAW,
            'weekly': SystemAction.EXECUTE_WEEKLY_DRAW,
            'monthly': SystemAction.EXECUTE_MONTHLY_DRAW
        }
        
        required_action = action_map.get(giveaway_type)
        if not required_action:
            return False, f"Invalid giveaway type: {giveaway_type}"
        
        # 1. Verificar permiso básico
        if not self.has_permission(user_id, required_action):
            return False, f"No permission to execute {giveaway_type} draws"
        
        # 2. Verificar restricciones horarias
        admin_info = self.admins.get(user_id, {})
        restrictions = admin_info.get('restrictions', {})
        
        if restrictions.get('time_based', False):
            # Obtener hora actual en London timezone
            try:
                from zoneinfo import ZoneInfo
                london_tz = ZoneInfo("Europe/London")
            except ImportError:
                import pytz
                london_tz = pytz.timezone("Europe/London")
            
            now = datetime.now(london_tz)
            current_hour = now.hour
            
            # Verificar horas permitidas para este tipo de sorteo
            allowed_hours = restrictions.get('allowed_hours', {})
            type_allowed_hours = allowed_hours.get(f'{giveaway_type}_draw', [17])  # Default 5 PM
            
            if current_hour not in type_allowed_hours:
                allowed_times = ', '.join([f"{h:02d}:00" for h in type_allowed_hours])
                return False, f"{giveaway_type.title()} draw only allowed at: {allowed_times}. Current time: {now.strftime('%H:%M')}"
        
        return True, "Authorized to execute draw"
    
    def get_admins_with_permission(self, action: SystemAction) -> List[str]:
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        authorized_admins = []
        
        for user_id, admin_info in self.admins.items():
            if admin_info.get('active', True) and self.has_permission(user_id, action):
                authorized_admins.append(user_id)
        
        return authorized_admins
    
    def get_admin_info(self, user_id: str) -> Optional[Dict]:
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        user_id = str(user_id)
        return self.admins.get(user_id)
    
    def add_admin(self, user_id: str, name: str, permission_group: str = "VIEW_ONLY", 
                  time_restrictions: bool = False) -> bool:
        """TU FUNCIÓN ORIGINAL - Más completa que la mía"""
        try:
            user_id = str(user_id)
            
            # Configuración de horas permitidas para sorteos (solo 5 PM)
            allowed_hours = {
                "daily_draw": [17],    # 5:00 PM
                "weekly_draw": [17],   # 5:00 PM
                "monthly_draw": [17]   # 5:00 PM
            } if time_restrictions else {}
            
            self.admins[user_id] = {
                "name": name,
                "permission_group": permission_group,
                "active": True,
                "created_date": datetime.now().strftime('%Y-%m-%d'),
                "restrictions": {
                    "time_based": time_restrictions,
                    "allowed_hours": allowed_hours,
                    "timezone": "Europe/London"
                },
                "custom_permissions": [],
                "denied_permissions": [],
                "notifications": {
                    "private_notifications": True,
                    "channel_notifications": True
                }
            }
            
            # Guardar cambios
            current_config = {"admins": self.admins}
            self._save_config(current_config)
            
            self.logger.info(f"Added admin: {name} ({user_id}) with group {permission_group}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error adding admin: {e}")
            return False
    
    def remove_admin(self, user_id: str) -> bool:
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        try:
            user_id = str(user_id)
            if user_id in self.admins:
                self.admins[user_id]['active'] = False
                self.admins[user_id]['deactivated_date'] = datetime.now().strftime('%Y-%m-%d')
                
                current_config = {"admins": self.admins}
                self._save_config(current_config)
                
                self.logger.info(f"Deactivated admin: {user_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing admin: {e}")
            return False
    
    def add_permission_to_user(self, user_id: str, action: SystemAction) -> bool:
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        try:
            user_id = str(user_id)
            if user_id not in self.admins:
                return False
            
            custom_perms = self.admins[user_id].get('custom_permissions', [])
            if action.value not in custom_perms:
                custom_perms.append(action.value)
                self.admins[user_id]['custom_permissions'] = custom_perms
                
                current_config = {"admins": self.admins}
                self._save_config(current_config)
                
                self.logger.info(f"Added permission {action.value} to {user_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error adding permission: {e}")
            return False
    
    def remove_permission_from_user(self, user_id: str, action: SystemAction) -> bool:
        """TU FUNCIÓN ORIGINAL - Sin cambios"""
        try:
            user_id = str(user_id)
            if user_id not in self.admins:
                return False
            
            denied_perms = self.admins[user_id].get('denied_permissions', [])
            if action.value not in denied_perms:
                denied_perms.append(action.value)
                self.admins[user_id]['denied_permissions'] = denied_perms
                
                current_config = {"admins": self.admins}
                self._save_config(current_config)
                
                self.logger.info(f"Denied permission {action.value} to {user_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error removing permission: {e}")
            return False
    
    def log_action(self, user_id: str, action: SystemAction, details: str = ""):
        """TU FUNCIÓN ORIGINAL - Mejor sistema de logging que el mío"""
        try:
            log_entry = {
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "user_id": str(user_id),
                "admin_name": self.admins.get(str(user_id), {}).get('name', 'Unknown'),
                "action": action.value,
                "details": details,
                "authorized": self.has_permission(user_id, action)
            }
            
            # Log a archivo
            self.logger.info(f"Admin action: {log_entry}")
            
            # También podrías guardar en archivo específico de auditoría
            audit_file = "admin_actions.log"
            with open(audit_file, 'a', encoding='utf-8') as f:
                f.write(f"{json.dumps(log_entry)}\n")
                
        except Exception as e:
            self.logger.error(f"Error logging admin action: {e}")
    
    def audit_permission_violations(self):
        """🆕 NEW: Auditar posibles violaciones de permisos"""
        violations = []
        
        # Verificar si hay admins con permisos inconsistentes
        for user_id, admin_info in self.admins.items():
            if not admin_info.get('active', True):
                continue
                
            permission_group = admin_info.get('permission_group')
            custom_perms = admin_info.get('custom_permissions', [])
            denied_perms = admin_info.get('denied_permissions', [])
            
            # 🚨 VERIFICACIÓN 1: PAYMENT_SPECIALIST con permisos de FULL_ADMIN
            if permission_group == "PAYMENT_SPECIALIST":
                dangerous_perms = [
                    SystemAction.MANAGE_ADMINS.value,
                    SystemAction.MODIFY_PRIZE_AMOUNTS.value,
                    SystemAction.DEBUG_ACCESS.value
                ]
                
                for perm in custom_perms:
                    if perm in dangerous_perms:
                        violations.append({
                            'user_id': user_id,
                            'violation': f'PAYMENT_SPECIALIST with dangerous permission: {perm}',
                            'severity': 'HIGH'
                        })
            
            # 🚨 VERIFICACIÓN 2: VIEW_ONLY con permisos de ejecución
            if permission_group == "VIEW_ONLY":
                execution_perms = [perm.value for perm in SystemAction if 'EXECUTE' in perm.value or 'CONFIRM' in perm.value]
                
                for perm in custom_perms:
                    if perm in execution_perms:
                        violations.append({
                            'user_id': user_id,
                            'violation': f'VIEW_ONLY with execution permission: {perm}',
                            'severity': 'CRITICAL'
                        })
        
        return violations
    # ============== 🆕 NUEVAS FUNCIONES AGREGADAS ==============
    
    def get_user_permissions(self, user_id: str) -> Set[SystemAction]:
        """🆕 NUEVA: Obtener todos los permisos de un usuario"""
        user_id = str(user_id)
        admin_info = self.admins.get(user_id)
        
        if not admin_info or not admin_info.get('active', True):
            return set()
        
        # Permisos del grupo
        permission_group = admin_info.get('permission_group')
        permissions = set(self.permission_groups.get(permission_group, []))
        
        # Agregar permisos personalizados
        custom_permissions = admin_info.get('custom_permissions', [])
        for perm in custom_permissions:
            try:
                permissions.add(SystemAction(perm))
            except ValueError:
                continue
        
        # Remover permisos denegados
        denied_permissions = admin_info.get('denied_permissions', [])
        for perm in denied_permissions:
            try:
                permissions.discard(SystemAction(perm))
            except ValueError:
                continue
        
        return permissions
    
    def generate_permissions_report(self) -> Dict:
        """🆕 NUEVA: Generar reporte completo de permisos"""
        report = {
            'total_admins': len([a for a in self.admins.values() if a.get('active', True)]),
            'total_actions_available': len(SystemAction),
            'admins_detail': [],
            'permission_distribution': {},
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Contar distribución de permisos
        for action in SystemAction:
            report['permission_distribution'][action.value] = len(self.get_admins_with_permission(action))
        
        # Detalles por admin
        for user_id, admin_info in self.admins.items():
            if admin_info.get('active', True):
                permissions = self.get_user_permissions(user_id)
                admin_detail = {
                    'user_id': user_id,
                    'name': admin_info.get('name', 'Unknown'),
                    'permission_group': admin_info.get('permission_group', 'None'),
                    'total_permissions': len(permissions),
                    'has_time_restrictions': admin_info.get('restrictions', {}).get('time_based', False),
                    'can_execute_draws': any(p in permissions for p in [
                        SystemAction.EXECUTE_DAILY_DRAW,
                        SystemAction.EXECUTE_WEEKLY_DRAW,
                        SystemAction.EXECUTE_MONTHLY_DRAW
                    ]),
                    'can_confirm_payments': any(p in permissions for p in [
                        SystemAction.CONFIRM_DAILY_PAYMENTS,
                        SystemAction.CONFIRM_WEEKLY_PAYMENTS,
                        SystemAction.CONFIRM_MONTHLY_PAYMENTS
                    ])
                }
                report['admins_detail'].append(admin_detail)
        
        return report
    
    def is_admin(self, user_id: str) -> bool:
        """🆕 NUEVA: Verificar si un usuario es administrador activo"""
        user_id = str(user_id)
        admin_info = self.admins.get(user_id)
        return admin_info is not None and admin_info.get('active', True)

# ============== TUS DECORADORES ORIGINALES MANTENIDOS ==============

# Variable global para el permission manager
_permission_manager = None

def setup_permission_system(app, config_file: str = "admin_permissions.json"):
    """TU FUNCIÓN ORIGINAL - Más robusta que la mía"""
    global _permission_manager
    _permission_manager = AdminPermissionManager(config_file)
    
    # Almacenar en el contexto de la app para acceso fácil
    app.bot_data['permission_manager'] = _permission_manager
    
    return _permission_manager

def get_permission_manager(context: ContextTypes.DEFAULT_TYPE) -> AdminPermissionManager:
    """TU FUNCIÓN ORIGINAL - Mejor integración con Telegram"""
    return context.bot_data.get('permission_manager') or _permission_manager
    # pm = context.bot_data.get('permission_manager')
    # return pm if isinstance(pm, AdminPermissionManager) else _permission_manager

def require_permission(required_action: SystemAction):
    """TU DECORADOR ORIGINAL - Mucho más robusto que el mío"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            permission_manager = get_permission_manager(context)
            
            if not permission_manager:
                await update.message.reply_text("❌ Permission system not initialized")
                return
            
            # Verificar permiso
            if not permission_manager.has_permission(user_id, required_action):
                admin_info = permission_manager.get_admin_info(user_id)
                admin_name = admin_info.get('name', 'Unknown') if admin_info else 'Unknown'
                
                permission_manager.log_action(user_id, required_action, f"DENIED - {func.__name__}")
                
                await update.message.reply_text(
                    f"❌ <b>Access Denied</b>\n\n"
                    f"Required permission: <code>{required_action.value}</code>\n"
                    f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>\n\n"
                    f"Contact a FULL_ADMIN for access.",
                    parse_mode='HTML'
                )
                return
            
            # Log acción autorizada
            admin_info = permission_manager.get_admin_info(user_id)
            admin_name = admin_info.get('name', 'Unknown') if admin_info else 'Unknown'
            permission_manager.log_action(user_id, required_action, f"AUTHORIZED - {func.__name__}")
            
            # Ejecutar función
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator

def require_any_permission(*required_actions: SystemAction):
    """TU DECORADOR ORIGINAL - Sin cambios"""
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            permission_manager = get_permission_manager(context)
            
            if not permission_manager:
                await update.message.reply_text("❌ Permission system not initialized")
                return
            
            # Verificar si tiene alguno de los permisos
            has_any_permission = any(
                permission_manager.has_permission(user_id, action) 
                for action in required_actions
            )
            
            if not has_any_permission:
                admin_info = permission_manager.get_admin_info(user_id)
                required_list = [action.value for action in required_actions]
                
                permission_manager.log_action(user_id, required_actions[0], f"DENIED - {func.__name__} - needs any of {required_list}")
                
                await update.message.reply_text(
                    f"❌ <b>Access Denied</b>\n\n"
                    f"Required: ANY of these permissions:\n" +
                    "\n".join([f"• <code>{action.value}</code>" for action in required_actions]) +
                    f"\n\nYour access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Log acción autorizada
            admin_info = permission_manager.get_admin_info(user_id)
            permission_manager.log_action(user_id, required_actions[0], f"AUTHORIZED - {func.__name__}")
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator

def require_draw_permission_with_time_check(giveaway_type: str):
    """TU DECORADOR ORIGINAL - Único con verificación horaria avanzada"""
    action_map = {
        'daily': SystemAction.EXECUTE_DAILY_DRAW,
        'weekly': SystemAction.EXECUTE_WEEKLY_DRAW,
        'monthly': SystemAction.EXECUTE_MONTHLY_DRAW
    }
    
    required_action = action_map.get(giveaway_type)
    if not required_action:
        raise ValueError(f"Invalid giveaway type: {giveaway_type}")
    
    def decorator(func):
        @wraps(func)
        async def wrapper(update, context, *args, **kwargs):
            user_id = update.effective_user.id
            permission_manager = get_permission_manager(context)
            
            if not permission_manager:
                await update.message.reply_text("❌ Permission system not initialized")
                return
            
            # Verificar permiso Y restricciones horarias
            can_execute, message = permission_manager.can_execute_draw_now(user_id, giveaway_type)
            
            if not can_execute:
                admin_info = permission_manager.get_admin_info(user_id)
                permission_manager.log_action(user_id, required_action, f"DENIED - {message}")
                
                await update.message.reply_text(
                    f"❌ <b>{giveaway_type.title()} Draw Denied</b>\n\n"
                    f"Reason: {message}\n\n"
                    f"💡 Check your time restrictions or contact a FULL_ADMIN.",
                    parse_mode='HTML'
                )
                return
            
            # Log acción autorizada
            admin_info = permission_manager.get_admin_info(user_id)
            permission_manager.log_action(user_id, required_action, f"AUTHORIZED - {func.__name__} at {datetime.now().strftime('%H:%M')}")
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    return decorator

# ============== TU FUNCIÓN DE CONFIGURhACIÓN ESPECÍFICA ==============

def create_your_specific_config():
    """TU FUNCIÓN ORIGINAL - Configuración perfecta para tu caso"""
    
    config = {
        "admins": {
            "8177033621": {  # TU ID
                "name": "Admin Principal (Tú)",
                "permission_group": "FULL_ADMIN",
                "active": True,
                "created_date": datetime.now().strftime('%Y-%m-%d'),
                "restrictions": {
                    "time_based": False,  # SIN restricciones
                    "allowed_hours": {},
                    "timezone": "Europe/London"
                },
                "custom_permissions": [],
                "denied_permissions": [],
                "notifications": {
                    "private_notifications": True,
                    "channel_notifications": True
                }
            },
            "7823596188": {  # REEMPLAZAR con ID real
                "name": "Administrador 1",
                "permission_group": "FULL_ADMIN",
                "active": True,
                "created_date": datetime.now().strftime('%Y-%m-%d'),
                "restrictions": {
                    "time_based": False,  # SIN restricciones
                    "allowed_hours": {},
                    "timezone": "Europe/London"
                },
                "custom_permissions": [],
                "denied_permissions": [],
                "notifications": {
                    "private_notifications": True,
                    "channel_notifications": True
                }
            },
            "7396303047": {  # REEMPLAZAR con ID real del dueño
                "name": "Dueño del Negocio",
                "permission_group": "FULL_ADMIN",
                "active": True,
                "created_date": datetime.now().strftime('%Y-%m-%d'),
                "restrictions": {
                    "time_based": False,  # CON restricciones horarias
                    "allowed_hours": {
                        "daily_draw": [17],    # Solo 5:00 PM
                        "weekly_draw": [17],   # Solo 5:00 PM
                        "monthly_draw": [17]   # Solo 5:00 PM
                    },
                    "timezone": "Europe/London"
                },
                "custom_permissions": [],
                "denied_permissions": [],
                "notifications": {
                    "private_notifications": True,
                    "channel_notifications": True
                }
            },
            "ID_OTRO_ADMIN": {  # REEMPLAZAR con ID real
                "name": "Admin Especializado",
                "permission_group": "PAYMENT_SPECIALIST", 
                "active": True,
                "created_date": datetime.now().strftime('%Y-%m-%d'),
                "restrictions": {
                    "time_based": True,  # CON restricciones horarias
                    "allowed_hours": {
                        "daily_draw": [17],    # Solo 5:00 PM
                        "weekly_draw": [17],   # Solo 5:00 PM
                        "monthly_draw": [17]   # Solo 5:00 PM
                    },
                    "timezone": "Europe/London"
                },
                "custom_permissions": [],
                "denied_permissions": ["MODIFY_PRIZE_AMOUNTS"],  # Específicamente bloqueado
                "notifications": {
                    "private_notifications": True,
                    "channel_notifications": True
                }
            }
        },
        "system_config": {
            "require_two_factor_for_draws": False,
            "log_all_actions": True,
            "notification_channel_id": None,  # Para canal de admins futuro
            "default_timezone": "Europe/London",
            "created_date": datetime.now().strftime('%Y-%m-%d'),
            "version": "1.0"
        }
    }
    
    # Guardar configuración
    with open("admin_permissions.json", 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print("✅ Configuración específica creada en admin_permissions.json")
    print("🔧 RECUERDA: Reemplazar ID_ADMIN_1, ID_DUENO, ID_OTRO_ADMIN con los IDs reales")

if __name__ == "__main__":
    # Crear configuración específica si se ejecuta directamente
    create_your_specific_config()