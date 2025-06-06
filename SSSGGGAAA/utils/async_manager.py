import asyncio
import time
import logging
from typing import Dict, Set, Optional
from functools import wraps
from contextlib import asynccontextmanager
import threading

class AsyncSafetyManager:
    """
    🔒 Gestor de seguridad para operaciones asíncronas críticas
    Previene race conditions y operaciones duplicadas
    """
    
    def __init__(self):
        # 🔐 LOCKS POR TIPO DE OPERACIÓN
        self._operation_locks: Dict[str, asyncio.Lock] = {}
        
        # 🚫 PREVENCIÓN DE CLICKS DUPLICADOS
        self._user_last_action: Dict[int, float] = {}
        self._debounce_time = 2.0  # 2 segundos entre acciones
        
        # 📝 OPERACIONES EN PROGRESO
        self._active_operations: Set[str] = set()
        
        # 🎯 LOCKS ESPECÍFICOS POR GIVEAWAY TYPE
        self._giveaway_locks: Dict[str, asyncio.Lock] = {
            'daily': asyncio.Lock(),
            'weekly': asyncio.Lock(),
            'monthly': asyncio.Lock()
        }
        
        # 💰 LOCKS PARA CONFIRMACIONES DE PAGO
        self._payment_locks: Dict[str, asyncio.Lock] = {}
        
        # 📄 LOCK GLOBAL PARA ARCHIVOS
        self._file_lock = asyncio.Lock()
        self._file_lock = threading.Lock()
        
        self.logger = logging.getLogger('AsyncSafetyManager')
    
    def get_operation_key(self, user_id: int, operation: str, giveaway_type: str = None) -> str:
        """Generar clave única para operación"""
        if giveaway_type:
            return f"{user_id}_{operation}_{giveaway_type}"
        return f"{user_id}_{operation}"
    
    async def is_user_rate_limited(self, user_id: int) -> bool:
        """Verificar si el usuario está en rate limit"""
        current_time = time.time()
        last_action = self._user_last_action.get(user_id, 0)
        
        if current_time - last_action < self._debounce_time:
            return True
        
        self._user_last_action[user_id] = current_time
        return False
    
    @asynccontextmanager
    async def acquire_operation_lock(self, operation_key: str):
        """Context manager para locks de operación"""
        if operation_key not in self._operation_locks:
            self._operation_locks[operation_key] = asyncio.Lock()
        
        lock = self._operation_locks[operation_key]
        
        try:
            # Timeout de 30 segundos para evitar deadlocks
            await asyncio.wait_for(lock.acquire(), timeout=30.0)
            self._active_operations.add(operation_key)
            yield
        except asyncio.TimeoutError:
            raise Exception(f"Operation timeout: {operation_key}")
        finally:
            self._active_operations.discard(operation_key)
            if lock.locked():
                lock.release()
    
    @asynccontextmanager
    async def acquire_giveaway_lock(self, giveaway_type: str):
        """Lock específico para operaciones de giveaway"""
        if giveaway_type not in self._giveaway_locks:
            self._giveaway_locks[giveaway_type] = asyncio.Lock()
        
        lock = self._giveaway_locks[giveaway_type]
        
        try:
            await asyncio.wait_for(lock.acquire(), timeout=30.0)
            yield
        except asyncio.TimeoutError:
            raise Exception(f"Giveaway operation timeout: {giveaway_type}")
        finally:
            if lock.locked():
                lock.release()
    
    @asynccontextmanager
    async def acquire_payment_lock(self, winner_id: str, giveaway_type: str):
        """Lock específico para confirmaciones de pago"""
        payment_key = f"payment_{giveaway_type}_{winner_id}"
        
        if payment_key not in self._payment_locks:
            self._payment_locks[payment_key] = asyncio.Lock()
        
        lock = self._payment_locks[payment_key]
        
        try:
            await asyncio.wait_for(lock.acquire(), timeout=15.0)
            yield
        except asyncio.TimeoutError:
            raise Exception(f"Payment confirmation timeout: {payment_key}")
        finally:
            if lock.locked():
                lock.release()
    
    @asynccontextmanager
    async def acquire_file_lock(self):
        """Lock global para operaciones de archivos CSV"""
        try:
            await asyncio.wait_for(self._file_lock.acquire(), timeout=20.0)
            yield
        except asyncio.TimeoutError:
            raise Exception("File operation timeout")
        finally:
            if self._file_lock.locked():
                self._file_lock.release()
    
    def get_active_operations(self) -> Set[str]:
        """Obtener operaciones activas para debugging"""
        return self._active_operations.copy()
    
    def cleanup_expired_locks(self):
        """Limpiar locks expirados (llamar periódicamente)"""
        current_time = time.time()
        expired_users = [
            user_id for user_id, last_time in self._user_last_action.items()
            if current_time - last_time > 300  # 5 minutos
        ]
        
        for user_id in expired_users:
            del self._user_last_action[user_id]
        
        self.logger.info(f"Cleaned {len(expired_users)} expired user locks")

# 🌟 DECORADORES PARA PROTECCIÓN AUTOMÁTICA

def prevent_concurrent_callback(operation_name: str, giveaway_type: str = None):
    """
    🔒 Decorador para prevenir callbacks concurrentes
    Uso: @prevent_concurrent_callback("confirm_payment", "daily")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            # Obtener safety manager del contexto o crear uno
            if not hasattr(context.bot_data, 'safety_manager'):
                context.bot_data['safety_manager'] = AsyncSafetyManager()
            
            safety_manager = context.bot_data['safety_manager']
            user_id = update.effective_user.id
            
            # 🚫 CHECK RATE LIMITING
            if await safety_manager.is_user_rate_limited(user_id):
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(
                        "⏳ Please wait before performing another action", 
                        show_alert=True
                    )
                else:
                    await update.message.reply_text("⏳ Please wait before performing another action")
                return
            
            # 🔐 ACQUIRE OPERATION LOCK
            operation_key = safety_manager.get_operation_key(user_id, operation_name, giveaway_type)
            
            try:
                async with safety_manager.acquire_operation_lock(operation_key):
                    return await func(self, update, context, *args, **kwargs)
            except Exception as e:
                logging.error(f"Concurrent operation error in {operation_name}: {e}")
                if hasattr(update, 'callback_query') and update.callback_query:
                    await update.callback_query.answer(
                        "❌ Operation failed - please try again", 
                        show_alert=True
                    )
                else:
                    await update.message.reply_text("❌ Operation failed - please try again")
                
        return wrapper
    return decorator

def require_giveaway_lock(giveaway_type_param: str = None):
    """
    🔒 Decorador para operaciones que requieren lock de giveaway específico
    Uso: @require_giveaway_lock() para auto-detectar tipo
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            if not hasattr(context.bot_data, 'safety_manager'):
                context.bot_data['safety_manager'] = AsyncSafetyManager()
            
            safety_manager = context.bot_data['safety_manager']
            
            # Detectar giveaway_type del parámetro o argumentos
            giveaway_type = giveaway_type_param
            if not giveaway_type and args:
                # Buscar en argumentos
                for arg in args:
                    if isinstance(arg, str) and arg in ['daily', 'weekly', 'monthly']:
                        giveaway_type = arg
                        break
            
            if not giveaway_type:
                giveaway_type = 'default'
            
            try:
                async with safety_manager.acquire_giveaway_lock(giveaway_type):
                    return await func(self, update, context, *args, **kwargs)
            except Exception as e:
                logging.error(f"Giveaway lock error for {giveaway_type}: {e}")
                raise
                
        return wrapper
    return decorator

def require_file_safety():
    """
    🔒 Decorador para operaciones de archivos CSV
    Uso: @require_file_safety()
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):  # ← SIN async
            # Para funciones síncronas, usar threading lock simple
            import threading
            
            # Lock global simple para archivos
            if not hasattr(wrapper, '_file_lock'):
                wrapper._file_lock = threading.Lock()
            
            with wrapper._file_lock:
                return func(*args, **kwargs)
                
        return wrapper
    return decorator

# 🔧 FUNCIÓN DE INICIALIZACIÓN
def setup_async_safety(app):
    """
    🔧 Configurar el sistema de seguridad async en la aplicación
    Llamar desde main() después de crear la aplicación
    """
    if not hasattr(app.bot_data, 'safety_manager'):
        app.bot_data['safety_manager'] = AsyncSafetyManager()
        
    # Configurar limpieza periódica de locks
    async def cleanup_task():
        while True:
            try:
                await asyncio.sleep(300)  # Cada 5 minutos
                app.bot_data['safety_manager'].cleanup_expired_locks()
            except Exception as e:
                logging.error(f"Error in cleanup task: {e}")
    
    # Iniciar tarea de limpieza
    asyncio.create_task(cleanup_task())
    
    logging.info("✅ Async Safety Manager initialized")
    return app.bot_data['safety_manager']