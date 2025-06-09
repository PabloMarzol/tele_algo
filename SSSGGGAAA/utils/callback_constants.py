# CREAR NUEVO ARCHIVO: utils/callback_constants.py

from enum import Enum

class CallbackData(Enum):
    """
    Centralización de callback_data siguiendo el patrón de SystemAction
    Elimina strings hardcodeados y mejora debugging
    """
    
    # ===== PANEL PRINCIPAL =====
    PANEL_UNIFIED_MAIN = "panel_unified_main"
    PANEL_UNIFIED_REFRESH = "panel_unified_refresh"
    PANEL_REFRESH = "panel_refresh"
    PANEL_HEALTH = "panel_health"
    PANEL_MAINTENANCE = "panel_maintenance"
    PANEL_STATISTICS = "panel_statistics"
    PANEL_ADVANCED_ANALYTICS = "panel_advanced_analytics"
    PANEL_BASIC_ANALYTICS = "panel_basic_analytics"
    PANEL_PENDING_WINNERS = "panel_pending_winners"
    
    # ===== AUTOMATION =====
    AUTOMATION_CONTROL = "automation_control"
    AUTOMATION_TOGGLE_AUTO_MODE = "automation_toggle_auto_mode"
    AUTOMATION_TOGGLE_INVITATIONS = "automation_toggle_invitations"
    AUTOMATION_SET_FREQUENCIES = "automation_set_frequencies"
    AUTOMATION_REFRESH = "automation_refresh"
    AUTOMATION_BACK_TO_PANEL = "automation_back_to_panel"
    
    # ===== MAINTENANCE =====
    MAINTENANCE_CLEANUP = "maintenance_cleanup"
    MAINTENANCE_BACKUP = "maintenance_backup"
    MAINTENANCE_HEALTH = "maintenance_health"
    MAINTENANCE_FILES = "maintenance_files"

    MAINTENANCE_MEMBERSHIP_ISSUES = "maintenance_membership_issues"
    MAINTENANCE_MEMBERSHIP_DETAILED = "maintenance_membership_detailed"
    MAINTENANCE_MEMBERSHIP_CLEAR = "maintenance_membership_clear"
    MAINTENANCE_MEMBERSHIP_REFRESH = "maintenance_membership_refresh"
    
    MAINTENANCE_CACHE_STATS = "maintenance_cache_stats"
    MAINTENANCE_CACHE_DETAILED = "maintenance_cache_detailed"
    MAINTENANCE_CACHE_CLEAR_ALL = "maintenance_cache_clear_all"
    
    
    # ===== ANALYTICS =====
    ANALYTICS_CROSS_TYPE = "analytics_cross_type"
    ANALYTICS_COMBINED = "analytics_combined"
    ANALYTICS_REVENUE = "analytics_revenue"
    ANALYTICS_USER_OVERLAP = "analytics_user_overlap"
    ANALYTICS_REVENUE_DETAILED = "analytics_revenue_detailed"
    ANALYTICS_USER_PATTERNS = "analytics_user_patterns"
    ANALYTICS_TIME_PATTERNS = "analytics_time_patterns"
    ANALYTICS_EXPORT_REPORT = "analytics_export_report"
    ANALYTICS_REVENUE_IMPACT = "analytics_revenue_impact"
    ANALYTICS_USER_BEHAVIOR = "analytics_user_behavior"
    ANALYTICS_TIME_TRENDS = "analytics_time_trends"
    ANALYTICS_DEEP_DIVE = "analytics_deep_dive"
    ANALYTICS_EFFICIENCY_TRENDS = "analytics_efficiency_trends"
    ANALYTICS_USER_ENGAGEMENT = "analytics_user_engagement"
    ANALYTICS_LOYALTY_PATTERNS = "analytics_loyalty_patterns"
    ANALYTICS_USER_BEHAVIOR_PATTERNS = "analytics_user_behavior_patterns"
    ANALYTICS_TIME_ANALYSIS = "analytics_time_analysis"
    ANALYTICS_DEEP_ANALYSIS = "analytics_deep_analysis"
    
    # ===== UNIFIED ACTIONS =====
    UNIFIED_ALL_PENDING = "unified_all_pending"
    UNIFIED_COMBINED_STATS = "unified_combined_stats"
    UNIFIED_SEND_ALL_INVITATIONS = "unified_send_all_invitations"
    UNIFIED_EXECUTE_ALL_DRAWS = "unified_execute_all_draws"
    UNIFIED_MULTI_ANALYTICS = "unified_multi_analytics"
    UNIFIED_CROSS_ANALYTICS = "unified_cross_analytics"
    UNIFIED_MAINTENANCE = "unified_maintenance"
    
    # ===== VIEW_ONLY =====
    VIEW_ONLY_HEALTH = "view_only_health"
    VIEW_ONLY_TODAY_DETAILS = "view_only_today_details"
    VIEW_ONLY_REFRESH = "view_only_refresh"
    VIEW_ONLY_PERMISSIONS_INFO = "view_only_permissions_info"
    
    # ===== TYPE SELECTOR =====
    TYPE_SELECTOR_MAIN = "type_selector_main"
    
    
    
    # ===== USER INTERFACE =====
    SHOW_RULES = "show_rules"
    START_MAIN = "start_main"
    
    # ===== SPECIAL =====
    NO_ACTION = "no_action"
    PANEL_PENDING_BY_TYPE = "panel_pending_by_type"
    PANEL_SEND_INVITATIONS = "panel_send_invitations"
    PANEL_EXECUTE_DRAWS = "panel_execute_draws"
    
    # ===== REVENUE ANALYSIS =====
    REVENUE_ANALYSIS = "revenue_analysis"

    # ===== AUTOMATION ESPECÍFICOS =====
    AUTOMATION_TOGGLE_DAILY = "automation_toggle_daily"
    AUTOMATION_TOGGLE_WEEKLY = "automation_toggle_weekly" 
    AUTOMATION_TOGGLE_MONTHLY = "automation_toggle_monthly"
    AUTOMATION_ENABLE_ALL = "automation_enable_all"
    AUTOMATION_DISABLE_ALL = "automation_disable_all"
    # AUTOMATION_TOGGLE_INVITATIONS = "automation_toggle_invitations"
    
    # ===== FREQUENCY SETTINGS =====
    FREQ_DAILY_2 = "freq_daily_2"
    FREQ_DAILY_3 = "freq_daily_3"
    FREQ_DAILY_4 = "freq_daily_4"
    FREQ_WEEKLY_4 = "freq_weekly_4"
    FREQ_WEEKLY_6 = "freq_weekly_6"
    FREQ_WEEKLY_8 = "freq_weekly_8"
    FREQ_MONTHLY_6 = "freq_monthly_6"
    FREQ_MONTHLY_8 = "freq_monthly_8"
    FREQ_MONTHLY_12 = "freq_monthly_12"
    
    # ===== PANELS ESPECÍFICOS =====
    PANEL_DAILY = "panel_daily"
    PANEL_WEEKLY = "panel_weekly"
    PANEL_MONTHLY = "panel_monthly"
    
    # ===== ANALYTICS ADICIONALES =====
    # ANALYTICS_REVENUE_IMPACT = "analytics_revenue_impact"
    # ANALYTICS_USER_BEHAVIOR = "analytics_user_behavior"
    # ANALYTICS_TIME_TRENDS = "analytics_time_trends"
    # ANALYTICS_DEEP_DIVE = "analytics_deep_dive"
    # ANALYTICS_REVENUE_DETAILED = "analytics_revenue_detailed"
    # ANALYTICS_USER_PATTERNS = "analytics_user_patterns"
    # ANALYTICS_TIME_PATTERNS = "analytics_time_patterns"
    # ANALYTICS_EXPORT_REPORT = "analytics_export_report"
    # ANALYTICS_EFFICIENCY_TRENDS = "analytics_efficiency_trends"
    # ANALYTICS_USER_ENGAGEMENT = "analytics_user_engagement"
    # ANALYTICS_LOYALTY_PATTERNS = "analytics_loyalty_patterns"
    # ANALYTICS_USER_BEHAVIOR_PATTERNS = "analytics_user_behavior_patterns"
    # ANALYTICS_TIME_ANALYSIS = "analytics_time_analysis"
    # ANALYTICS_DEEP_ANALYSIS = "analytics_deep_analysis"
    
    # # ===== AUTOMATION ADICIONALES =====
    # AUTOMATION_REFRESH = "automation_refresh"
    
    # ===== MÉTODOS ESTÁTICOS PARA CALLBACKS DINÁMICOS =====
    
    @staticmethod
    def panel_type(giveaway_type: str) -> str:
        """Generate panel_type_{giveaway_type}"""
        return f"panel_type_{giveaway_type}"
    
    @staticmethod
    def panel_pending_winners_type(giveaway_type: str) -> str:
        """Generate panel_pending_winners_{giveaway_type}"""
        return f"panel_pending_winners_{giveaway_type}"
    
    @staticmethod
    def panel_analytics_type(giveaway_type: str) -> str:
        """Generate panel_analytics_{giveaway_type}"""
        return f"panel_analytics_{giveaway_type}"
    
    @staticmethod
    def panel_top_users_type(giveaway_type: str) -> str:
        """Generate panel_top_users_{giveaway_type}"""
        return f"panel_top_users_{giveaway_type}"
    
    @staticmethod
    def confirm_payment(giveaway_type: str, identifier: str) -> str:
        """Generate confirm_payment_{giveaway_type}_{identifier}"""
        return f"confirm_payment_{giveaway_type}_{identifier}"
    
    @staticmethod
    def giveaway_participate(giveaway_type: str) -> str:
        """Generate giveaway_participate_{giveaway_type}"""
        return f"giveaway_participate_{giveaway_type}"
    
    @staticmethod
    def analytics_type_days(giveaway_type: str, days: int) -> str:
        """Generate analytics_{giveaway_type}_{days}"""
        return f"analytics_{giveaway_type}_{days}"
    
    @staticmethod
    def frequency_setting(giveaway_type: str, hours: int) -> str:
        """Generate freq_{giveaway_type}_{hours}"""
        return f"freq_{giveaway_type}_{hours}"
    
    @staticmethod
    def panel_send_invitation_type(giveaway_type: str) -> str:
        """Generate panel_send_invitation_{giveaway_type}"""
        return f"panel_send_invitation_{giveaway_type}"
    
    @staticmethod
    def panel_run_giveaway_type(giveaway_type: str) -> str:
        """Generate panel_run_giveaway_{giveaway_type}"""
        return f"panel_run_giveaway_{giveaway_type}"
    
    @staticmethod
    def panel_refresh_type(giveaway_type: str) -> str:
        """Generate panel_refresh_{giveaway_type}"""
        return f"panel_refresh_{giveaway_type}"
    
    @staticmethod
    def panel_full_stats_type(giveaway_type: str) -> str:
        """Generate panel_full_stats_{giveaway_type}"""
        return f"panel_full_stats_{giveaway_type}"
    
    @staticmethod
    def revenue_analysis_type(giveaway_type: str) -> str:
        """Generate revenue_analysis_{giveaway_type}"""
        return f"revenue_analysis_{giveaway_type}"
    
    @staticmethod
    def account_report_type(giveaway_type: str) -> str:
        """Generate account_report_{giveaway_type}"""
        return f"account_report_{giveaway_type}"
    
    # ===== PARSING HELPERS PARA CALLBACKS DINÁMICOS =====
    
    @staticmethod
    def parse_confirm_payment(callback_data: str) -> tuple:
        """Parse confirm_payment_{type}_{identifier} -> (type, identifier)"""
        if not callback_data.startswith("confirm_payment_"):
            return None, None
        parts = callback_data.split("_", 3)
        if len(parts) < 4:
            return None, None
        return parts[2], parts[3]
    
    @staticmethod
    def parse_analytics_type_days(callback_data: str) -> tuple:
        """Parse analytics_{type}_{days} -> (type, days)"""
        if not callback_data.startswith("analytics_"):
            return None, None
        parts = callback_data.split("_")
        if len(parts) < 3:
            return None, None
        try:
            return parts[1], int(parts[2])
        except (ValueError, IndexError):
            return None, None
    
    @staticmethod
    def parse_frequency_setting(callback_data: str) -> tuple:
        """Parse freq_{type}_{hours} -> (type, hours)"""
        if not callback_data.startswith("freq_"):
            return None, None
        parts = callback_data.split("_")
        if len(parts) < 3:
            return None, None
        try:
            return parts[1], int(parts[2])
        except (ValueError, IndexError):
            return None, None
    
    @staticmethod
    def parse_panel_type_specific(callback_data: str) -> str:
        """Parse panel_*_{type} patterns -> type"""
        parts = callback_data.split("_")
        if len(parts) < 3:
            return None
        # Último elemento es el tipo en patrones como panel_analytics_daily
        return parts[-1] if parts[-1] in ['daily', 'weekly', 'monthly'] else None
    
    # ===== DEBUGGING HELPER =====
    
    @classmethod
    def is_valid_callback(cls, callback_data: str) -> bool:
        """Check if a callback_data string is valid"""
        try:
            cls(callback_data)
            return True
        except ValueError:
            return False
    
    @classmethod
    def get_all_callbacks(cls) -> list:
        """Get all available callback values for debugging"""
        return [callback.value for callback in cls]
    
    @classmethod
    def debug_callback(cls, callback_data: str) -> str:
        """Debug helper - returns info about callback"""
        if cls.is_valid_callback(callback_data):
            callback = cls(callback_data)
            return f"✅ Valid callback: {callback.name} = '{callback.value}'"
        else:
            return f"❌ Invalid callback: '{callback_data}'"
        
    @classmethod
    def get_maintenance_callbacks(cls):
        """Get all maintenance-related callbacks"""
        return [
            
            cls.MAINTENANCE_CLEANUP,
            cls.MAINTENANCE_BACKUP,
            cls.MAINTENANCE_HEALTH,
            cls.MAINTENANCE_FILES,
            cls.MAINTENANCE_MEMBERSHIP_ISSUES,
            cls.MAINTENANCE_MEMBERSHIP_DETAILED,
            cls.MAINTENANCE_MEMBERSHIP_CLEAR,
            cls.MAINTENANCE_MEMBERSHIP_REFRESH,
            cls.MAINTENANCE_CACHE_STATS
        ]
    
    @classmethod
    def get_membership_callbacks(cls):
        """Get all membership-related callbacks"""
        return [
            cls.MAINTENANCE_MEMBERSHIP_ISSUES,
            cls.MAINTENANCE_MEMBERSHIP_DETAILED,
            cls.MAINTENANCE_MEMBERSHIP_CLEAR,
            cls.MAINTENANCE_MEMBERSHIP_REFRESH
        ]
    
    @classmethod
    def is_maintenance_callback(cls, callback_data: str) -> bool:
        """Check if callback is maintenance-related"""
        maintenance_callbacks = [cb.value for cb in cls.get_maintenance_callbacks()]
        return callback_data in maintenance_callbacks
    
    @classmethod
    def is_membership_callback(cls, callback_data: str) -> bool:
        """Check if callback is membership-related"""
        # membership_callbacks = [cb.value for cb in cls.get_membership_callbacks()]
        """Check if callback is membership-related"""
        membership_callbacks = [
            CallbackData.MAINTENANCE_MEMBERSHIP_ISSUES.value,
            CallbackData.MAINTENANCE_MEMBERSHIP_DETAILED.value,
            CallbackData.MAINTENANCE_MEMBERSHIP_CLEAR.value,
            CallbackData.MAINTENANCE_MEMBERSHIP_REFRESH.value,
        ]
        return callback_data in membership_callbacks
    
    @staticmethod
    def is_cache_callback(callback_data: str) -> bool:
        """Check if callback is cache-related"""
        cache_callbacks = [
            CallbackData.MAINTENANCE_CACHE_STATS.value,
            CallbackData.MAINTENANCE_CACHE_DETAILED.value,
            CallbackData.MAINTENANCE_CACHE_CLEAR_ALL.value,
            
        ]
        return callback_data in cache_callbacks


# ===== FUNCIONES DE MIGRACIÓN HELPER =====

def validate_callback_usage():
    """
    Helper para validar que todos los callbacks en el código usan CallbackData
    Ejecutar después de migrar para detectar callbacks hardcodeados restantes
    """
    import os
    import re
    
    hardcoded_patterns = [
        r'callback_data\s*=\s*["\'][^"\']*["\']',  # callback_data="string"
        r'callback_data\s*==\s*["\'][^"\']*["\']',  # callback_data == "string"
    ]
    
    hardcoded_found = []
    
    # Buscar en archivos principales
    search_files = [
        'callback_handlers.py',
        'admin_commands.py', 
        'user_commands.py',
        'ga_integration.py'
    ]
    
    for filename in search_files:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern in hardcoded_patterns:
                        matches = re.findall(pattern, line)
                        if matches:
                            # Filtrar exclusiones válidas (comentarios, etc.)
                            if not line.strip().startswith('#'):
                                hardcoded_found.append({
                                    'file': filename,
                                    'line': i,
                                    'content': line.strip(),
                                    'matches': matches
                                })
    
    return hardcoded_found

# ===== EJEMPLO DE USO COMPLETO =====

"""
MIGRACIÓN PASO A PASO:

1. CREAR EL ARCHIVO:
   utils/callback_constants.py (este archivo)

2. IMPORTAR EN TUS ARCHIVOS:
   from utils.callback_constants import CallbackData

3. MIGRAR GRADUALMENTE:

   ANTES:
   InlineKeyboardButton("🏠 Panel", callback_data="panel_unified_main")
   if callback_data == "panel_unified_main":

   DESPUÉS:
   InlineKeyboardButton("🏠 Panel", callback_data=CallbackData.PANEL_UNIFIED_MAIN.value)
   if callback_data == CallbackData.PANEL_UNIFIED_MAIN.value:

4. PARA CALLBACKS DINÁMICOS:

   ANTES:
   callback_data=f"panel_type_{giveaway_type}"
   
   DESPUÉS:
   callback_data=CallbackData.panel_type(giveaway_type)

5. DEBUGGING MEJORADO:

   ANTES:
   print(f"❌ DEBUG: Unrecognized callback: {callback_data}")
   
   DESPUÉS:
   print(CallbackData.debug_callback(callback_data))

6. VALIDACIÓN POST-MIGRACIÓN:
   
   hardcoded = validate_callback_usage()
   if hardcoded:
       print("⚠️ Callbacks hardcodeados restantes:")
       for item in hardcoded:
           print(f"  {item['file']}:{item['line']} - {item['content']}")
"""