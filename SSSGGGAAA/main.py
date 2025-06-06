#!/usr/bin/env python3
"""
🎯 MAIN.PY - SISTEMA DE GIVEAWAYS
=====================================

Sistema principal utilizando la arquitectura existente bien estructurada:
- core/: MultiGiveawayIntegration + GiveawaySystem
- handlers/: Comandos y callbacks organizados
- utils/: Utilidades especializadas

Basado en test_botTTT.py pero usando la estructura modular existente.
"""
import os
import sys

# Agregar carpeta raíz al sys.path si estás ejecutando desde SSSGGGAAA
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import logging
import asyncio
import os
import signal
import sys
from datetime import datetime
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# ==================== IMPORTS DE LA ESTRUCTURA EXISTENTE ====================

# Core System - Ya existe y funciona
from core.ga_integration import MultiGiveawayIntegration
from core.ga_manager import GiveawaySystem

# Utils - Sistema de soporte ya implementado
from utils.config_loader import ConfigLoader
from utils.admin_permission import setup_permission_system, get_permission_manager
from utils.async_manager import setup_async_safety
from utils.automation_manager import AutomationManager
from utils.utils import check_automation_dependencies

# Handlers - Ya organizados por funcionalidad
from handlers.user_commands import start_command, help_command, stats_command
from handlers.admin_commands import (
    admin_confirm_daily_payment, admin_confirm_weekly_payment, admin_confirm_monthly_payment,
    admin_pending_daily, admin_pending_weekly, admin_pending_monthly,
    admin_pending_winners, admin_confirm_payment
)
from handlers.callback_handlers import (
    handle_user_interface_callbacks, handle_payment_confirmations_only
)
from handlers.participation_flow import handle_participate_button, handle_mt5_input

# Legacy - Funciones específicas que mantienen compatibilidad  
from handlers.admin_commands import (
    admin_send_daily_invitation, admin_send_weekly_invitation, admin_send_monthly_invitation,
    admin_run_daily_draw, admin_run_weekly_draw, admin_run_monthly_draw
)



    
async def initialize(self):
        """🔧 Inicialización usando estructura existente"""
        try:
            print("🚀 Inicializando Sistema Multi-Giveaway...")
            
            # 1. Setup logging (usando utils existente)
            logging.basicConfig(
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=logging.INFO,
                handlers=[
                    logging.FileHandler('multi_giveaway_bot.log'),
                    logging.StreamHandler()
                ]
            )
            self.logger = logging.getLogger('MultiGiveawayBot')
            
            # 2. Cargar configuración (usando ConfigLoader existente)
            self.config_loader = ConfigLoader()
            bot_config = self.config_loader.get_bot_config()
            self.logger.info(f"Configuración cargada: {bot_config['token'][:10]}...")
            
            # 3. Crear aplicación Telegram
            self.app = Application.builder().token(bot_config['token']).build()
            
            # 4. Setup sistemas de seguridad (usando utils existentes)
            setup_async_safety(self.app)
            permission_manager = setup_permission_system(self.app, "admin_permissions.json")
            self.logger.info("Sistemas de seguridad configurados")
            
            
            
            # 6. Inicializar MultiGiveawayIntegration (núcleo existente)
            self.multi_giveaway_integration = MultiGiveawayIntegration(
                application=self.app,
                
                config_file="config.json"
            )
            
            # 7. Setup automatización (usando AutomationManager existente si disponible)
            if check_automation_dependencies():
                self.multi_giveaway_integration.setup_automatic_draws()
                self.logger.info("Sistema de automatización configurado")
            
            # 8. Configurar handlers usando estructura existente
            self._setup_handlers()
            
            # 9. Hacer disponible globalmente (compatibilidad con handlers existentes)
            global multi_giveaway_integration
            multi_giveaway_integration = self.multi_giveaway_integration
            
            self.is_initialized = True
            self.logger.info("✅ Sistema inicializado correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error en inicialización: {e}")
            return False
    
    
    
    
async def start(self):
        """🚀 Iniciar el sistema completo"""
        try:
            if not self.is_initialized:
                raise Exception("Sistema no inicializado")
            
            self.logger.info("Iniciando bot...")
            
            # Inicializar aplicación
            await self.app.initialize()
            await self.app.start()
            
            # Iniciar polling
            await self.app.updater.start_polling(
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True
            )
            
            self.is_running = True
            
            # Mostrar información del sistema
            self._show_startup_info()
            
            # Configurar señales de sistema
            stop_event = asyncio.Event()
            self._setup_signal_handlers(stop_event)
            
            self.logger.info("🚀 Sistema completamente operativo")
            
            # Esperar señal de parada
            await stop_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error iniciando sistema: {e}")
            raise
    
def _show_startup_info(self):
        """📊 Mostrar información del sistema al iniciar"""
        
        bot_config = self.config_loader.get_bot_config()
        giveaway_configs = self.config_loader.get_giveaway_configs()
        
        print("\n" + "="*70)
        print("🎯 SISTEMA MULTI-GIVEAWAY OPERATIVO")
        print("="*70)
        
        print(f"\n📡 CONFIGURACIÓN:")
        print(f"   🤖 Token: {bot_config['token'][:10]}...")
        print(f"   📢 Canal: {bot_config['channel_id']}")
        print(f"   👤 Admin: {bot_config['admin_id']}")
        
        print(f"\n🎯 GIVEAWAYS DISPONIBLES:")
        for giveaway_type, config in giveaway_configs.items():
            prize = config['prize']
            cooldown = config['cooldown_days']
            # Verificar ventana usando el sistema existente
            giveaway_system = self.multi_giveaway_integration.get_giveaway_system(giveaway_type)
            window_status = giveaway_system.is_participation_window_open(giveaway_type)
            status_emoji = "🟢" if window_status else "🔴"
            print(f"   {status_emoji} {giveaway_type.title()}: ${prize} USD (cooldown: {cooldown}d)")
        
        # Información de automatización (usando sistema existente)
        if hasattr(self.multi_giveaway_integration, 'get_automation_status'):
            automation_status = self.multi_giveaway_integration.get_automation_status()
            print(f"\n🤖 AUTOMATIZACIÓN:")
            print(f"   📅 Scheduler: {'🟢 ACTIVO' if automation_status.get('scheduler_running') else '🔴 INACTIVO'}")
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                auto_enabled = automation_status.get(giveaway_type, False)
                status = "🟢 AUTO" if auto_enabled else "👤 MANUAL"
                print(f"   {status} {giveaway_type.title()}")
        
        print(f"\n📱 COMANDOS PRINCIPALES:")
        print(f"   👤 Usuario: /start, /help")
        print(f"   🔧 Admin: /admin_panel, /stats")
        print(f"   🎲 Sorteos: /admin_run_daily, /admin_run_weekly, /admin_run_monthly")
        print(f"   💳 Pagos: /admin_confirm_daily, /admin_confirm_weekly, /admin_confirm_monthly")
        
        print(f"\n📁 ARQUITECTURA UTILIZADA:")
        print(f"   ✅ core/: MultiGiveawayIntegration + GiveawaySystem")
        print(f"   ✅ handlers/: Comandos y callbacks organizados")
        print(f"   ✅ utils/: Utilidades especializadas")
        print(f"   ✅ Permisos: Sistema granular activo")
        print(f"   ✅ Concurrencia: AsyncSafetyManager activo")
        
        print("\n" + "="*70)
        print("Sistema utilizando arquitectura existente 🚀")
        print("="*70 + "\n")
    

    
async def stop(self):
        """🛑 Detener el sistema"""
        try:
            self.logger.info("Deteniendo sistema...")
            
            self.is_running = False
            
            # Detener automatización (usando método existente)
            if (hasattr(self.multi_giveaway_integration, 'shutdown_scheduler') and 
                self.multi_giveaway_integration.scheduler):
                self.multi_giveaway_integration.shutdown_scheduler()
                self.logger.info("Automatización detenida")
            
            # Detener bot
            if self.app and self.app.updater.running:
                await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            
            self.logger.info("✅ Sistema detenido correctamente")
            
        except Exception as e:
            self.logger.error(f"Error deteniendo sistema: {e}")


# ==================== FUNCIONES DE VERIFICACIÓN ====================

def check_system_requirements():
    """🔍 Verificar requisitos usando estructura existente"""
    
    print("🔍 Verificando estructura del proyecto...")
    
    # Verificar que existe la estructura organizacional
    required_structure = {
        'core/ga_integration.py': 'MultiGiveawayIntegration',
        'core/ga_manager.py': 'GiveawaySystem', 
        'handlers/user_commands.py': 'Comandos de usuario',
        'handlers/admin_commands.py': 'Comandos administrativos',
        'handlers/callback_handlers.py': 'Manejo de callbacks',
        'utils/config_loader.py': 'ConfigLoader',
        'utils/admin_permission.py': 'Sistema de permisos',
        'config.json': 'Configuración principal'
    }
    
    missing_components = []
    for file_path, description in required_structure.items():
        if not os.path.exists(file_path):
            missing_components.append(f"{file_path} ({description})")
    
    if missing_components:
        print("❌ Componentes faltantes de la estructura:")
        for component in missing_components:
            print(f"   • {component}")
        return False
    
    print("✅ Estructura del proyecto verificada")
    return True

def check_configuration():
    """⚙️ Verificar configuración usando ConfigLoader existente"""
    
    try:
        from utils.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        
        bot_config = config_loader.get_bot_config()
        required_keys = ['token', 'channel_id', 'admin_id']
        
        for key in required_keys:
            if not bot_config.get(key) or 'YOUR_' in str(bot_config.get(key, '')):
                print(f"❌ Configuración inválida: {key}")
                return False
        
        print("✅ Configuración válida")
        return True
        
    except Exception as e:
        print(f"❌ Error verificando configuración: {e}")
        return False


# ==================== FUNCIÓN PRINCIPAL ====================

async def async_main():
    """🚀 Función principal utilizando arquitectura existente"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    print("🎯 SISTEMA MULTI-GIVEAWAY")
    print("="*50)
    print("Utilizando arquitectura modular existente")
    print("="*50)
    
    # 1. Verificar que tenemos la estructura correcta
    if not check_system_requirements():
        print("❌ La estructura del proyecto no está completa")
        print("💡 Asegúrese de tener todos los archivos en core/, handlers/, utils/")
        return 1
    
    # 2. Verificar configuración
    if not check_configuration():
        print("❌ Configuración inválida en config.json")
        return 1
    

    # 3. Verificar dependencias para automatización
    automation_available = check_automation_dependencies()
    if not automation_available:
        print("⚠️ APScheduler no disponible - modo manual únicamente")
    
    # 4. Inicializar y ejecutar
    application = None
    try:
        print("\n🚀 Iniciando sistema usando estructura existente...")
        
        # 1. Cargar configuración
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        
        # 2. Crear aplicación
        application = Application.builder().token(bot_config['token']).build()
        
        # 3. Setup sistemas de seguridad
        setup_permission_system(application)
        setup_async_safety(application)
        
        # 4. Inicializar sistema multi-giveaway
        # (NO necesita mt5_api porque usa MySQL directamente en ga_manager)
        multi_giveaway_integration = MultiGiveawayIntegration(
            application=application, 
            config_file="config.json"
            
        )
        
        # 5. Hacer disponible globalmente
        application.bot_data['giveaway_integration'] = multi_giveaway_integration
        
        # 6. Setup automatización si está disponible
        if check_automation_dependencies():
            multi_giveaway_integration.setup_automatic_draws()
            logger.info("Automatización configurada")
        
        logger.info("🚀 Sistema inicializado con MySQL connection")
        
        # 7. 🔧 CORREGIDO: Inicializar manualmente en lugar de run_polling
        await application.initialize()
        await application.start()
        
        # 8. Configurar señales para detener correctamente
        stop_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            print(f"\n🛑 Señal {signum} recibida. Deteniendo bot...")
            stop_event.set()
        
        import signal
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # 9. Iniciar polling
        await application.updater.start_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
        print("✅ Sistema completamente operativo")
        print("Presiona Ctrl+C para detener...")
        
        # 10. Esperar señal de parada
        await stop_event.wait()
        
        return 0
    except KeyboardInterrupt:
        print("\n🛑 Bot detenido por el usuario")
        return 0
    except Exception as e:
        print(f"\n❌ Error crítico: {e}")
        logging.error(f"Error crítico en main: {e}")
        return 1
        
    finally:
        if application:
            try:
                print("🧹 Deteniendo servicios...")
                
                # Detener polling
                if application.updater.running:
                    await application.updater.stop()
                
                # Detener automatización si existe
                if hasattr(multi_giveaway_integration, 'scheduler') and multi_giveaway_integration.automation_manager.scheduler:
                    multi_giveaway_integration.shutdown_scheduler()
                
                # Detener aplicación
                await application.stop()
                await application.shutdown()
                
                print("✅ Sistema detenido correctamente")
                
            except Exception as cleanup_error:
                logging.error(f"Error en cleanup: {cleanup_error}")


# 👇 Síncrona: punto de entrada del script
def main():
    print("🎯 Multi-Giveaway System")
    print("Utilizando arquitectura modular existente bien estructurada")
    print("-" * 60)
    
    try:
        # 🔧 CORREGIDO: usar asyncio.run() directamente
        exit_code = asyncio.run(async_main())
        print(f"Sistema finalizado con código: {exit_code}")
        sys.exit(exit_code)
        
    except KeyboardInterrupt:
        print("🛑 Sistema interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        logging.error(f"Error fatal en main: {e}")
        sys.exit(1)


# ==================== PUNTO DE ENTRADA ====================

if __name__ == "__main__":
    print("🎯 Multi-Giveaway System")
    print("Utilizando arquitectura modular existente bien estructurada")
    print("-"*60)
    
    try:
        # exit_code = asyncio.run(main())
        # sys.exit(exit_code)
        main()
        
    except Exception as e:
        print(f"❌ Error fatal: {e}")
        sys.exit(1)