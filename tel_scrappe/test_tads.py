# test_discovery_system.py
import asyncio
import logging
from tads import TelegramDiscoveryBot

# Configurar logging para ver resultados detallados
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("test_discovery.log"),
        logging.StreamHandler()
    ]
)

class TestDiscoveryBot(TelegramDiscoveryBot):
    """Versión del bot para pruebas con modificaciones para aislamiento."""
    
    def __init__(self):
        # Usar archivos de configuración y estado específicos para pruebas
        super().__init__(
            config_file="test_tads_config.json",
            state_file="test_tads_state.json",
            credentials_file="credentials.json"  # Usar las mismas credenciales
        )
        # Sobrescribir configuraciones clave para pruebas
        self.test_mode = True
        
    async def send_to_bot(self, data):
        """Sobrescribir método para no enviar datos al bot real."""
        print("\n=== DATOS QUE SE ENVIARÍAN AL BOT ===")
        print(f"Nuevas entidades: {len(data.get('new_entities', []))}")
        print(f"Datos extraídos: {len(data.get('extracted_data', {}).get('extraction_results', []))}")
        print(f"Interacciones: {data.get('interactions', {}).get('interactions', 0)}")
        print("=====================================\n")
        
        # Guardar los datos a un archivo para inspeccionarlos después
        import json
        with open('test_bot_data.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
        return {"success": True, "message": "Test mode - data logged to file"}
    
    async def run_test_cycle(self):
        """Ejecuta un único ciclo completo de prueba."""
        print("Iniciando ciclo de prueba...")
        
        # Inicializar sistema
        initialized = await self.initialize_automated_discovery()
        if not initialized:
            print("Error: No se pudo inicializar el sistema")
            return False
            
        # 1. Generar tareas (limitar cantidad para pruebas)
        self.config["max_tasks_per_cycle"] = 5  # Reducir para pruebas
        tasks = self.schedule_discovery_tasks()
        print(f"Tareas programadas: {len(tasks)}")
        
        # 2. Ejecutar un ciclo
        print("Ejecutando ciclo de descubrimiento...")
        cycle_results = await self.execute_discovery_cycle(tasks)
        
        # 3. Procesar resultados si hay nuevas entidades
        if cycle_results.get("new_entities"):
            print(f"Nuevas entidades encontradas: {len(cycle_results['new_entities'])}")
            
            # Procesar entidades
            processed = await self.process_discovered_entities(cycle_results["new_entities"])
            print(f"Entidades prioritarias: {len(processed['prioritized'])}")
            print(f"Entidades para interacción: {len(processed['for_interaction'])}")
            
            # Si hay entidades prioritarias, extraer datos
            if processed["prioritized"]:
                print("Extrayendo datos de entidades prioritarias...")
                extraction = await self.extract_relevant_data(processed["prioritized"][:2])  # Limitar a 2 para pruebas
                
            # Si hay entidades para interacción, simular interacción
            if processed["for_interaction"] and self.config.get("auto_join", False):
                print("AVISO: Auto-join está activado. Se unirá a entidades.")
                print("¿Desea continuar con las uniones? (s/n)")
                choice = input("> ").lower()
                if choice == 's':
                    print("Procesando interacciones...")
                    interaction = await self.manage_entity_interactions(processed["for_interaction"][:1])  # Limitar a 1
                else:
                    print("Interacciones omitidas por elección del usuario")
            
            # Enviar datos (simulado en esta clase)
            await self.send_to_bot({
                "new_entities": processed["prioritized"] + processed["for_monitoring"],
                "extracted_data": extraction if 'extraction' in locals() else {},
                "interactions": interaction if 'interaction' in locals() else {}
            })
            
        else:
            print("No se encontraron nuevas entidades en este ciclo")
        
        print("Ciclo de prueba completado")
        return True


async def run_test():
    """Ejecuta una prueba del sistema de descubrimiento."""
    bot = TestDiscoveryBot()
    
    # Imprimir opciones de prueba
    print("\n=== PRUEBA DEL SISTEMA DE DESCUBRIMIENTO ===")
    print("1. Ejecutar un ciclo completo de prueba")
    print("2. Ejecutar búsqueda en una categoría específica")
    print("3. Probar extracción en una entidad conocida")
    print("0. Salir")
    
    option = input("Selecciona una opción: ")
    
    if option == "1":
        await bot.run_test_cycle()
    
    elif option == "2":
        print("\nCategorías disponibles:")
        categories = ["crypto", "forex", "investing"]
        for i, cat in enumerate(categories, 1):
            print(f"{i}. {cat}")
        
        cat_option = input("Selecciona una categoría: ")
        try:
            category = categories[int(cat_option) - 1]
            # Crear y ejecutar tarea de búsqueda
            from tads import TelegramDiscoveryTask
            task = TelegramDiscoveryTask(
                task_id=f"test_search_{category}",
                task_type="search_category",
                parameters={"category": category}
            )
            
            # Inicializar
            await bot.initialize_automated_discovery()
            
            # Ejecutar búsqueda
            print(f"Buscando en categoría: {category}...")
            result = await bot._execute_search_category_task(task)
            
            # Mostrar resultados
            print(f"Entidades encontradas: {len(result.get('entities', []))}")
            for i, entity in enumerate(result.get('entities', [])[:5], 1):  # Mostrar primeras 5
                print(f"{i}. {entity.get('title')} (@{entity.get('username', '')})")
                print(f"   Tipo: {entity.get('type')}, Miembros: {entity.get('members_count')}")
                print()
        except (IndexError, ValueError):
            print("Opción inválida")
    
    elif option == "3":
        # Probar extracción en entidad específica
        entity_id = input("Ingresa ID de entidad para probar extracción: ")
        if entity_id:
            # Inicializar
            await bot.initialize_automated_discovery()
            
            # Crear tarea
            from tads import TelegramDiscoveryTask
            task = TelegramDiscoveryTask(
                task_id=f"test_extract_{entity_id}",
                task_type="extract_members",
                parameters={
                    "entity_id": entity_id,
                    "method": "comprehensive"
                }
            )
            
            # Ejecutar extracción
            print(f"Extrayendo datos de entidad {entity_id}...")
            result = await bot._execute_extract_members_task(task)
            
            # Mostrar resultados
            print(f"Resultado de extracción: {result}")
    
    elif option == "0":
        print("Saliendo...")
    
    else:
        print("Opción inválida")


# Ejecutar prueba
if __name__ == "__main__":
    asyncio.run(run_test())