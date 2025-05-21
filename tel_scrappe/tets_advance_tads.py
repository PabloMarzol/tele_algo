import asyncio
import random
import time
import os
import sys
from test_tads import TestDiscoveryBot
from tads import TelegramDiscoveryTask

# [Implementación de NetworkErrorSimulator y NetworkTestDiscoveryBot aquí]

class NetworkTestDiscoveryBot(TestDiscoveryBot):
    def __init__(self):
        super().__init__()
        self.error_simulator = NetworkErrorSimulator(failure_rate=0.4)
        
        # Reemplazar métodos originales con versiones que puedan fallar
        self._original_search_term = self._execute_search_term_task
        self._execute_search_term_task = self._wrap_with_simulator(self._execute_search_term_task)
        
        self._original_extract_members = self._execute_extract_members_task
        self._execute_extract_members_task = self._wrap_with_simulator(self._execute_extract_members_task)
    
    def _wrap_with_simulator(self, method):
        async def wrapped(*args, **kwargs):
            return await self.error_simulator.simulate_network_error(method, *args, **kwargs)
        return wrapped
    
class NetworkErrorSimulator:
    def __init__(self, failure_rate=0.5, recovery_time=5):
        self.failure_rate = failure_rate  # Probabilidad de fallo
        self.recovery_time = recovery_time  # Segundos hasta recuperación
        self.is_active = True
    
    async def simulate_network_error(self, original_method, *args, **kwargs):
        if self.is_active and random.random() < self.failure_rate:
            # Simular error de red
            print("⚠️ Simulando error de red/servicio...")
            await asyncio.sleep(2)  # Simular latencia
            raise ConnectionError("Simulación de error de red")
        else:
            # Comportamiento normal
            return await original_method(*args, **kwargs)
            
    def deactivate(self):
        self.is_active = False

# [Implementación de test_api_limits, test_network_resilience y test_continuous_operation aquí]
async def test_api_limits():
    bot = TestDiscoveryBot()
    await bot.initialize_automated_discovery()
    
    # Forzar múltiples búsquedas secuenciales
    print("Ejecutando múltiples búsquedas para alcanzar límites API...")
    for i in range(15):  # Más que nuestro límite
        term = f"test_term_{i}"
        print(f"Búsqueda {i+1}: {term}")
        # Ejecutar búsqueda
        task = TelegramDiscoveryTask(
            task_id=f"test_search_{i}",
            task_type="search_term",
            parameters={"term": term}
        )
        result = await bot._execute_search_term_task(task)
        print(f"  Resultado: {'Éxito' if result.get('entities') else 'Fallo/Límite'}")
        # No esperar entre búsquedas para forzar límites
    
    # Verificar gestión de backoff
    print("\nVerificando backoff y recuperación...")
    # Esperar tiempo suficiente para recuperar cuota
    print("Esperando 60 segundos para recuperar cuota...")
    await asyncio.sleep(60)
    
    # Intentar nuevamente
    recovery_task = TelegramDiscoveryTask(
        task_id="recovery_test",
        task_type="search_term",
        parameters={"term": "recovery_test"}
    )
    recovery_result = await bot._execute_search_term_task(recovery_task)
    print(f"Prueba de recuperación: {'Éxito' if recovery_result.get('entities') is not None else 'Fallo'}")
    
    # Verificar contadores de API
    print(f"\nContadores de API final: {bot.state.api_usage}")
async def test_network_resilience():
    bot = NetworkTestDiscoveryBot()
    await bot.initialize_automated_discovery()
    
    print("Prueba de resiliencia: ejecutando 10 tareas con fallos de red aleatorios")
    
    # Crear varias tareas
    tasks = []
    for i in range(10):
        task = TelegramDiscoveryTask(
            task_id=f"resilience_test_{i}",
            task_type="search_term",
            parameters={"term": f"resilience_{i}"},
            max_attempts=3  # Permitir reintentos
        )
        tasks.append(task)
    
    # Ejecutar ciclo con fallos simulados
    cycle_results = await bot.execute_discovery_cycle(tasks)
    
    # Analizar resultados
    completed = sum(1 for t in bot.state.tasks if t.status == "completed")
    failed = sum(1 for t in bot.state.tasks if t.status == "failed")
    pending = sum(1 for t in bot.state.tasks if t.status == "pending")
    
    print(f"\nEstadísticas de tareas:")
    print(f"- Completadas: {completed}")
    print(f"- Fallidas: {failed}")
    print(f"- Pendientes: {pending}")
    print(f"- Errores registrados: {len(cycle_results['errors'])}")
    
    # Desactivar simulador y probar tareas pendientes
    print("\nDesactivando simulador de errores y reintentando tareas pendientes...")
    bot.error_simulator.deactivate()
    
    # Filtrar solo tareas pendientes
    pending_tasks = [t for t in bot.state.tasks if t.status == "pending"]
    if pending_tasks:
        recovery_results = await bot.execute_discovery_cycle(pending_tasks)
        print(f"Tareas recuperadas: {sum(1 for t in pending_tasks if t.status == 'completed')}")
async def test_continuous_operation():
    bot = TestDiscoveryBot()
    await bot.initialize_automated_discovery()
    
    # Configurar para prueba prolongada
    bot.config["run_interval_minutes"] = 5  # Acortar para prueba
    bot.config["max_tasks_per_cycle"] = 5   # Limitar para no agotar API
    
    print("Iniciando prueba de operación continua (duración: 2 horas)")
    print("Presiona Ctrl+C para detener la prueba")
    
    start_time = time.time()
    end_time = start_time + (2 * 60 * 60)  # 2 horas
    cycle_count = 0
    
    # Métricas a monitorear
    memory_usage = []
    cycle_durations = []
    tasks_processed = []
    entities_found = []
    
    try:
        while time.time() < end_time:
            cycle_start = time.time()
            
            # Programar tareas
            tasks = bot.schedule_discovery_tasks()
            
            # Ejecutar ciclo
            cycle_results = await bot.execute_discovery_cycle(tasks)
            
            # Registrar métricas
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            memory_usage.append(memory_mb)
            
            cycle_duration = time.time() - cycle_start
            cycle_durations.append(cycle_duration)
            
            tasks_processed.append(len(tasks))
            entities_found.append(len(cycle_results.get("new_entities", [])))
            
            # Mostrar progreso
            cycle_count += 1
            elapsed_mins = (time.time() - start_time) / 60
            print(f"\nCiclo {cycle_count} completado")
            print(f"Tiempo transcurrido: {elapsed_mins:.1f} minutos")
            print(f"Memoria usada: {memory_mb:.1f} MB")
            print(f"Duración del ciclo: {cycle_duration:.1f} segundos")
            print(f"Tareas procesadas: {len(tasks)}")
            print(f"Nuevas entidades: {len(cycle_results.get('new_entities', []))}")
            
            # Esperar hasta próximo ciclo
            await bot.wait_until_next_cycle()
            
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario")
    finally:
        # Análisis final
        print("\n=== RESUMEN DE PRUEBA CONTINUA ===")
        print(f"Ciclos completados: {cycle_count}")
        print(f"Tiempo total: {(time.time() - start_time) / 60:.1f} minutos")
        print(f"Memoria inicial: {memory_usage[0]:.1f} MB")
        print(f"Memoria final: {memory_usage[-1]:.1f} MB")
        print(f"Incremento de memoria: {memory_usage[-1] - memory_usage[0]:.1f} MB")
        
        if len(cycle_durations) > 1:
            print(f"Duración promedio de ciclo: {sum(cycle_durations) / len(cycle_durations):.1f} segundos")
            print(f"Primera duración: {cycle_durations[0]:.1f} seg, Última: {cycle_durations[-1]:.1f} seg")
            
        # Generar gráfico de uso de memoria
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 6))
            plt.plot(range(len(memory_usage)), memory_usage)
            plt.title("Uso de memoria durante operación continua")
            plt.xlabel("Ciclo")
            plt.ylabel("Memoria (MB)")
            plt.savefig("tads_memory_usage.png")
            print("Gráfico de memoria guardado como 'tads_memory_usage.png'")
        except:
            print("No se pudo generar gráfico (matplotlib no disponible)")

async def main():
    print("=== PRUEBAS AVANZADAS PARA TADS ===")
    print("1. Prueba de límites de API")
    print("2. Prueba de recuperación ante fallos")
    print("3. Prueba de operación continua (2 horas)")
    print("0. Salir")
    
    option = input("\nSelecciona una prueba: ")
    
    if option == "1":
        await test_api_limits()
    elif option == "2":
        await test_network_resilience()
    elif option == "3":
        await test_continuous_operation()
    elif option == "0":
        print("Saliendo...")
    else:
        print("Opción inválida")

if __name__ == "__main__":
    asyncio.run(main())