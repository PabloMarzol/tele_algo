import threading
import time
import asyncio
from contextlib import contextmanager
from typing import Dict, Set, Optional
from datetime import datetime

class OptimizedLockManager:
    """
    Sistema de locks optimizado con granularidad fina y manejo de timeouts
    """
    
    def __init__(self, giveaway_type: str, logger):
        self.giveaway_type = giveaway_type
        self.logger = logger
        
        # 🔒 LOCKS ESPECÍFICOS POR OPERACIÓN
        self._locks = {
            'participants': threading.RLock(),  # RLock para operaciones anidadas
            'winners': threading.RLock(),
            'history': threading.RLock(),
            'pending_winners': threading.RLock(),
            'backup': threading.Lock(),
            'cache': threading.RLock(),
            'stats': threading.RLock()
        }
        
        # 🕐 TIMEOUT MANAGEMENT
        self._lock_timeouts = {}
        self._lock_owners = {}
        self._default_timeout = 30.0  # 30 segundos
        
        # 📊 PERFORMANCE TRACKING
        self._lock_stats = {
            'acquisitions': 0,
            'timeouts': 0,
            'contentions': 0,
            'avg_hold_time': 0.0
        }
        
        # 🔄 ASYNC OPERATIONS TRACKING
        self._active_async_operations: Set[str] = set()
        self._operation_timestamps: Dict[str, float] = {}
        
        self.logger.info(f"OptimizedLockManager initialized for {giveaway_type}")
    
    # ============================================================================
    # 🔒 CORE LOCK METHODS
    # ============================================================================
    
    @contextmanager
    def acquire_file_lock(self, file_type: str, timeout: Optional[float] = None):
        """
        Adquirir lock específico para tipo de archivo
        
        Args:
            file_type: 'participants', 'winners', 'history', 'pending_winners'
            timeout: Tiempo máximo de espera en segundos
        """
        if file_type not in self._locks:
            raise ValueError(f"Unknown file type: {file_type}")
        
        lock = self._locks[file_type]
        timeout = timeout or self._default_timeout
        start_time = time.time()
        
        try:
            # Intentar adquirir lock con timeout
            acquired = lock.acquire(timeout=timeout)
            
            if not acquired:
                self._lock_stats['timeouts'] += 1
                raise TimeoutError(f"Could not acquire {file_type} lock within {timeout}s")
            
            # Track acquisition
            self._lock_stats['acquisitions'] += 1
            acquisition_time = time.time()
            thread_id = threading.get_ident()
            
            self._lock_owners[file_type] = {
                'thread_id': thread_id,
                'acquired_at': acquisition_time,
                'giveaway_type': self.giveaway_type
            }
            
            self.logger.debug(f"Lock acquired for {file_type} (thread: {thread_id})")
            
            try:
                yield
            finally:
                # Calculate hold time for stats
                hold_time = time.time() - acquisition_time
                self._update_hold_time_stats(hold_time)
                
                # Clean tracking data
                self._lock_owners.pop(file_type, None)
                
                self.logger.debug(f"Lock released for {file_type} (held: {hold_time:.3f}s)")
                
        finally:
            # Always release lock
            try:
                lock.release()
            except:
                pass  # Lock might not have been acquired
    
    @contextmanager
    def acquire_multi_file_lock(self, file_types: list, timeout: Optional[float] = None):
        """
        Adquirir múltiples locks en orden consistente para evitar deadlocks
        """
        # Ordenar para evitar deadlocks
        sorted_types = sorted(file_types)
        timeout = timeout or self._default_timeout
        
        acquired_locks = []
        start_time = time.time()
        
        try:
            for file_type in sorted_types:
                if file_type not in self._locks:
                    raise ValueError(f"Unknown file type: {file_type}")
                
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    raise TimeoutError("Multi-lock timeout exceeded")
                
                lock = self._locks[file_type]
                acquired = lock.acquire(timeout=remaining_timeout)
                
                if not acquired:
                    raise TimeoutError(f"Could not acquire multi-lock for {file_type}")
                
                acquired_locks.append((file_type, lock))
                
                self.logger.debug(f"Multi-lock acquired: {file_type}")
            
            self._lock_stats['acquisitions'] += len(acquired_locks)
            yield
            
        finally:
            # Release in reverse order
            for file_type, lock in reversed(acquired_locks):
                try:
                    lock.release()
                    self.logger.debug(f"Multi-lock released: {file_type}")
                except:
                    pass
    
    # ============================================================================
    # 🔄 ASYNC OPERATIONS MANAGEMENT
    # ============================================================================
    
    @contextmanager
    def track_async_operation(self, operation_id: str, timeout: float = 30.0):
        """
        Rastrear operaciones async para evitar duplicaciones
        """
        if operation_id in self._active_async_operations:
            # Check for stale operations
            operation_time = self._operation_timestamps.get(operation_id, time.time())
            if time.time() - operation_time > timeout:
                self.logger.warning(f"Cleaning stale async operation: {operation_id}")
                self._active_async_operations.discard(operation_id)
                self._operation_timestamps.pop(operation_id, None)
            else:
                raise RuntimeError(f"Async operation already active: {operation_id}")
        
        # Mark operation as active
        self._active_async_operations.add(operation_id)
        self._operation_timestamps[operation_id] = time.time()
        
        try:
            self.logger.debug(f"Async operation started: {operation_id}")
            yield
        finally:
            # Clean up
            self._active_async_operations.discard(operation_id)
            self._operation_timestamps.pop(operation_id, None)
            self.logger.debug(f"Async operation completed: {operation_id}")
    
    def cleanup_stale_operations(self, max_age: float = 60.0):
        """Limpiar operaciones async obsoletas"""
        current_time = time.time()
        stale_operations = [
            op_id for op_id, timestamp in self._operation_timestamps.items()
            if current_time - timestamp > max_age
        ]
        
        for op_id in stale_operations:
            self._active_async_operations.discard(op_id)
            self._operation_timestamps.pop(op_id, None)
            self.logger.warning(f"Cleaned stale operation: {op_id}")
        
        return len(stale_operations)
    
    # ============================================================================
    # 📊 PERFORMANCE & MONITORING
    # ============================================================================
    
    def _update_hold_time_stats(self, hold_time: float):
        """Actualizar estadísticas de tiempo de retención de locks"""
        current_avg = self._lock_stats['avg_hold_time']
        total_acquisitions = self._lock_stats['acquisitions']
        
        if total_acquisitions == 1:
            self._lock_stats['avg_hold_time'] = hold_time
        else:
            # Weighted average
            self._lock_stats['avg_hold_time'] = (
                (current_avg * (total_acquisitions - 1) + hold_time) / total_acquisitions
            )
    
    def get_lock_diagnostics(self) -> dict:
        """Obtener diagnósticos del sistema de locks"""
        current_time = time.time()
        
        # Active locks info
        active_locks = {}
        for file_type, owner_info in self._lock_owners.items():
            if owner_info:
                hold_duration = current_time - owner_info['acquired_at']
                active_locks[file_type] = {
                    'thread_id': owner_info['thread_id'],
                    'hold_duration': round(hold_duration, 3),
                    'giveaway_type': owner_info['giveaway_type']
                }
        
        # Performance metrics
        total_ops = self._lock_stats['acquisitions']
        timeout_rate = (self._lock_stats['timeouts'] / total_ops * 100) if total_ops > 0 else 0
        
        return {
            'giveaway_type': self.giveaway_type,
            'performance': {
                'total_acquisitions': total_ops,
                'timeouts': self._lock_stats['timeouts'],
                'timeout_rate_percent': round(timeout_rate, 2),
                'avg_hold_time_seconds': round(self._lock_stats['avg_hold_time'], 3),
                'contentions': self._lock_stats['contentions']
            },
            'active_locks': active_locks,
            'active_async_operations': len(self._active_async_operations),
            'async_operations_list': list(self._active_async_operations),
            'available_locks': list(self._locks.keys()),
            'timestamp': datetime.now().isoformat()
        }
    
    def force_release_stale_locks(self, max_hold_time: float = 120.0):
        """
        Forzar liberación de locks que han sido retenidos demasiado tiempo
        ⚠️  USAR SOLO EN EMERGENCIAS
        """
        current_time = time.time()
        released_locks = []
        
        for file_type, owner_info in list(self._lock_owners.items()):
            if owner_info:
                hold_duration = current_time - owner_info['acquired_at']
                if hold_duration > max_hold_time:
                    try:
                        lock = self._locks[file_type]
                        lock.release()
                        self._lock_owners.pop(file_type, None)
                        released_locks.append(file_type)
                        self.logger.warning(
                            f"Force released stale lock: {file_type} "
                            f"(held for {hold_duration:.1f}s by thread {owner_info['thread_id']})"
                        )
                    except Exception as e:
                        self.logger.error(f"Error force releasing lock {file_type}: {e}")
        
        return released_locks

# ============================================================================
# 🔧 HELPER DECORATORS
# ============================================================================

def with_file_lock(file_type: str, timeout: Optional[float] = None):
    """
    Decorator para funciones que necesitan acceso exclusivo a archivos
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'lock_manager'):
                raise AttributeError("Object must have 'lock_manager' attribute")
            
            with self.lock_manager.acquire_file_lock(file_type, timeout):
                return func(self, *args, **kwargs)
        return wrapper
    return decorator

def with_multi_file_lock(file_types: list, timeout: Optional[float] = None):
    """
    Decorator para funciones que necesitan acceso a múltiples archivos
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, 'lock_manager'):
                raise AttributeError("Object must have 'lock_manager' attribute")
            
            with self.lock_manager.acquire_multi_file_lock(file_types, timeout):
                return func(self, *args, **kwargs)
        return wrapper
    return decorator
