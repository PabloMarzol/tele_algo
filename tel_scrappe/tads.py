"""
Telegram Automated Discovery System (TADS)

This system automatize the process of discovering channels, groups, and users in Telegram.
Save all data of the entities in a database.
It integrate with an existing bot that generates trading signals and moderates channels.
Developed to work with funtions from existing class TelegramEntityFinder2 on file full2.py

"""

import asyncio
import json
import logging
import os
import random
import sys
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union, Any

# Asegúrate de que el módulo full2.py esté en el path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar la clase principal de full2.py
from full2 import TelegramEntityFinder2

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tads.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TADS")

class TelegramDiscoveryTask:
    """Represent a single task in the TADS system."""
    
    def __init__(
        self, 
        task_id: str,
        task_type: str,
        parameters: dict,
        priority: int = 5,
        scheduled_time: Optional[datetime] = None,
        max_attempts: int = 3
    ):
        self.task_id = task_id
        self.task_type = task_type  # search, extract, join, etc.
        self.parameters = parameters
        self.priority = priority  # 1-10, donde 10 es la máxima prioridad
        self.scheduled_time = scheduled_time or datetime.now()
        self.attempts = 0
        self.max_attempts = max_attempts
        self.status = "pending"  # pending, in_progress, completed, failed
        self.result = None
        self.error = None
        self.last_attempt_time = None
    
    def to_dict(self) -> dict:
        """Converts the task to a dictionary for serialization storage."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "parameters": self.parameters,
            "priority": self.priority,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "last_attempt_time": self.last_attempt_time.isoformat() if self.last_attempt_time else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TelegramDiscoveryTask':
        """Create a TelegramDiscoveryTask instance task from a dictionary."""
        task = cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            parameters=data["parameters"],
            priority=data["priority"],
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]) if data["scheduled_time"] else None,
            max_attempts=data["max_attempts"]
        )
        task.attempts = data["attempts"]
        task.status = data["status"]
        task.result = data["result"]
        task.error = data["error"]
        task.last_attempt_time = datetime.fromisoformat(data["last_attempt_time"]) if data["last_attempt_time"] else None
        return task

class DiscoveryState:
    """Represent the actual state of the discovery process."""
    
    def __init__(self):
        self.tasks: List[TelegramDiscoveryTask] = []
        self.discovered_entities: Set[str] = set()  # IDs de entidades ya descubiertas
        self.last_cycle_time: Optional[datetime] = None
        self.cycle_count: int = 0
        self.api_usage: Dict[str, int] = {
            "search_requests": 0,
            "entity_requests": 0,
            "join_requests": 0
        }
        # self.api_limits: Dict[str, tuple] = {
        #     # (requests_per_minute, requests_per_hour)
        #     "search_requests": (20, 300),
        #     "entity_requests": (30, 500),
        #     "join_requests": (5, 40)
        # }
        self.api_limits = {
            "search_requests": (3, 10),  # Reducido de (20, 300)
            "entity_requests": (3, 10),  # Reducido de (30, 500)
            "join_requests": (2, 5)      # Reducido de (5, 40)
        }
        # Estadísticas de eficacia
        self.effectiveness: Dict[str, Dict[str, float]] = {
            "categories": {},
            "terms": {}
        }
        # Configuración actual
        self.current_config: Dict[str, Any] = {}
    
    def to_dict(self) -> dict:
        """Converts the state to a dictionary for serialization."""
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "discovered_entities": list(self.discovered_entities),
            "last_cycle_time": self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "cycle_count": self.cycle_count,
            "api_usage": self.api_usage,
            "api_limits": self.api_limits,
            "effectiveness": self.effectiveness,
            "current_config": self.current_config
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DiscoveryState':

        """Create a DiscoveryState instance from a dictionary deserialized."""
        state = cls()
        state.tasks = [TelegramDiscoveryTask.from_dict(task_data) for task_data in data["tasks"]]
        state.discovered_entities = set(data["discovered_entities"])
        state.last_cycle_time = datetime.fromisoformat(data["last_cycle_time"]) if data["last_cycle_time"] else None
        state.cycle_count = data["cycle_count"]
        state.api_usage = data["api_usage"]
        state.api_limits = data["api_limits"]
        state.effectiveness = data["effectiveness"]
        state.current_config = data["current_config"]
        return state

class TelegramDiscoveryBot:
    
    """
    This class handles the core functionality of the bot, including task scheduling, API usage, and state management.
    Utilize the TelegramEntityFinder2 for entity discovery (channel, group, supergroup, members) and joining.

    """
    
    def __init__(
        self,
        config_file: str = "tads_config.json",
        state_file: str = "tads_state.json",
        credentials_file: str = "credentials.json"
    ):
        self.config_file = config_file
        self.state_file = state_file
        self.credentials_file = credentials_file
        
        # Estado del sistema
        self.state = DiscoveryState()

        
        # Configuración y ajustes
        self.config = self._load_config()
        
        # Cliente Telegram (utilizando TelegramEntityFinder2)
        self.finder = None
        
        # Control de ejecución
        self.running = False
        self.paused = False
        
        # Integración con bot externo
        self.bot_api_url = self.config.get("bot_api_url", "")
        self.bot_api_key = self.config.get("bot_api_key", "")
    
    def _load_config(self) -> dict:
        """ Load configuration from JSON file or create a default one."""
        
        default_config = {
            "run_interval_minutes": 30,
            "categories": {
                "crypto": {"priority": 10, "max_entities": 100},
                "forex": {"priority": 8, "max_entities": 50},
                "investing": {"priority": 7, "max_entities": 50}
            },
            "search_terms_boost": {
                "signals": 2.0,
                "strategy": 1.5,
                "analysis": 1.3,
                "chart": 1.2
            },
            "max_tasks_per_cycle": 20,
            "max_joins_per_day": 15,
            "entity_relevance_threshold": 0.6,
            "auto_join": True,
            "extraction_depth": {
                "high_relevance": 5,
                "medium_relevance": 3,
                "low_relevance": 1
            },
            "backoff_strategy": {
                "initial_wait": 2,
                "max_wait": 300,
                "factor": 2
            },
            "bot_api_url": "",
            "bot_api_key": "",
            "notifications": {
                "enable_telegram": True,
                "admin_chat_id": "",
                "status_interval_hours": 6
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    logger.info(f"Configuration loaded from: {self.config_file}")
                    # Actualizar config predeterminada con valores del archivo
                    # (esto preserva valores predeterminados para claves faltantes)
                    self._deep_update(default_config, config)
                    return default_config
            else:
                # Crear archivo de configuración inicial
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4)
                logger.info(f"Configuration file created in: {self.config_file}")
                return default_config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return default_config
    
    def _deep_update(self, original, update):
        """Update a nested dictionary or similar mapping."""
        """Update recursively a dictionary with a another one."""

        for key, value in update.items():
            if key in original and isinstance(original[key], dict) and isinstance(value, dict):
                self._deep_update(original[key], value)
            else:
                original[key] = value
    
    async def initialize_automated_discovery(self) -> bool:
        """Initialize and start the Telegram automated discovery system."""
        try:
            logger.info("Inicializing Telegram automated discovery system ...")
            
            
            # Cargar estado previo si existe
            self._load_state()
            
            # Inicializar TelegramEntityFinder2
            self.finder = TelegramEntityFinder2()
            
            # Llamar directamente al método asíncrono
            if not await self.finder.initialize_async():
                logger.error("Error inizialiting TelegramEntityFinder2")
                return False
            
            # if not self.finder.initialize():
            #     logger.error("Could not initialize TelegramEntityFinder2")
            #     return False
            
            # Actualizar configuración en el estado
            self.state.current_config = self.config
            
            logger.info("System initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing system: {e}")
            traceback.print_exc()
            return False
    
    def _load_state(self) -> None:
        """Load the current state from a file if exist."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                    self.state = DiscoveryState.from_dict(state_data)
                    logger.info(f"Load state from: {self.state_file}: Cycle {self.state.cycle_count}")
            else:
                logger.info("Could not create file of previous state. Initializing with new state.")
        except Exception as e:
            logger.error(f"Error loadig state: {e}")
            # Continuar con estado nuevo
    
    def _save_state(self) -> None:
        """Save the current state to a file."""
        try:
            state_data = self.state.to_dict()
            
            # Crear copia de respaldo antes de sobrescribir
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.bak"
                try:
                    import shutil
                    shutil.copy2(self.state_file, backup_file)
                except Exception as e:
                    logger.warning(f"Could not create a backup of the state: {e}")
            
            # Guardar estado actual
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, indent=4)
            
            logger.debug(f"State saved on: {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def schedule_discovery_tasks(self) -> List[TelegramDiscoveryTask]:
        """
        Generate and schedule discovery tasks based on the current configuration.
        
        Returns:
            List[TelegramDiscoveryTask]: List of scheduled tasks for the current cycle.
        """
        logger.info("Programing discovery tasks...")
        
        # Limpiar tareas completadas o fallidas
        self.state.tasks = [task for task in self.state.tasks 
                           if task.status not in ["completed", "failed"]]
        
        # Cantidad máxima de tareas por ciclo
        max_tasks = self.config.get("max_tasks_per_cycle", 20)
        
        # Si ya tenemos suficientes tareas pendientes, no crear más
        if len([t for t in self.state.tasks if t.status == "pending"]) >= max_tasks:
            logger.info(f"Ya hay suficientes tareas pendientes ({len(self.state.tasks)})")
            return self.state.tasks
        
        # Obtener categorías configuradas ordenadas por prioridad
        categories = sorted(
            self.config["categories"].items(), 
            key=lambda x: x[1]["priority"], 
            reverse=True
        )
        
        # Crear tareas de búsqueda por categoría
        new_tasks = []
        
        # Añadir tareas de búsqueda por categoría con alta prioridad
        for category_name, settings in categories:
            # Crear tarea de búsqueda por categoría
            task_id = f"search_category_{category_name}_{int(time.time())}"
            
            # Ajustar prioridad basada en eficacia histórica
            adjusted_priority = settings["priority"]
            if category_name in self.state.effectiveness["categories"]:
                effectiveness = self.state.effectiveness["categories"][category_name]
                # Aumentar prioridad para categorías más efectivas
                if effectiveness > 0.7:
                    adjusted_priority += 2
                elif effectiveness > 0.5:
                    adjusted_priority += 1
                # Disminuir prioridad para categorías menos efectivas
                elif effectiveness < 0.3:
                    adjusted_priority -= 1
            
            task = TelegramDiscoveryTask(
                task_id=task_id,
                task_type="search_category",
                parameters={"category": category_name},
                priority=adjusted_priority,
                scheduled_time=datetime.now() + timedelta(minutes=random.randint(0, 10))
            )
            
            new_tasks.append(task)
        
        # Si hay términos de búsqueda específicos en la configuración, añadirlos
        boost_terms = self.config.get("search_terms_boost", {})
        for term, boost in boost_terms.items():
            # Crear tarea de búsqueda por término
            task_id = f"search_term_{term}_{int(time.time())}"
            
            # La prioridad depende del boost configurado
            priority = min(int(5 * boost), 10)  # Escala 1-10
            
            task = TelegramDiscoveryTask(
                task_id=task_id,
                task_type="search_term",
                parameters={"term": term},
                priority=priority,
                scheduled_time=datetime.now() + timedelta(minutes=random.randint(5, 15))
            )
            
            new_tasks.append(task)
        
        # Añadir algunas tareas aleatorias para diversificar
        random_tasks = self._generate_random_tasks(3)  # 3 tareas aleatorias
        new_tasks.extend(random_tasks)
        
        # Limitar cantidad de tareas nuevas
        remaining_slots = max_tasks - len(self.state.tasks)
        if remaining_slots <= 0:
            return self.state.tasks
        
        if len(new_tasks) > remaining_slots:
            # Ordenar por prioridad y tomar solo las que quepan
            new_tasks.sort(key=lambda x: x.priority, reverse=True)
            new_tasks = new_tasks[:remaining_slots]
        
        # Añadir nuevas tareas a la lista existente
        self.state.tasks.extend(new_tasks)
        
        logger.info(f" {len(new_tasks)}  New tasks were nuevas tareas. Total: {len(self.state.tasks)}")
        return self.state.tasks
    
    def _generate_random_tasks(self, count: int) -> List[TelegramDiscoveryTask]:
        """"""
        random_tasks = []
        
        # Lista de términos genéricos para diversificar
        generic_terms = [
            "group", "channel", "chat", "community", "official", "news",
            "alerts", "signal", "free", "premium", "vip", "exclusive",
            "analysis", "daily", "trading", "investor", "market", "finance"
        ]
        
        # Seleccionar términos aleatorios sin repetir
        selected_terms = random.sample(
            generic_terms, 
            min(count, len(generic_terms))
        )
        
        for term in selected_terms:
            task_id = f"random_search_{term}_{int(time.time())}"
            
            task = TelegramDiscoveryTask(
                task_id=task_id,
                task_type="search_term",
                parameters={"term": term},
                priority=3,  # Prioridad media-baja para tareas aleatorias
                scheduled_time=datetime.now() + timedelta(minutes=random.randint(10, 20))
            )
            
            random_tasks.append(task)
        
        return random_tasks
    
    async def execute_discovery_cycle(self, tasks: List[TelegramDiscoveryTask]) -> dict:
        """
        Execute a complete discovery cycle, including task execution and entity discovery.
        
        Args:
            tasks: List of TelegramDiscoveryTask objects to be executed.
            
        Returns:
            Results of the discovery cycle.
        """
        cycle_results = {
            "cycle_id": str(int(time.time())),
            "start_time": datetime.now().isoformat(),
            "tasks_results": [],
            "new_entities": [],
            "errors": [],
            "api_usage": {}
        }
        
        logger.info(f"Starting discovery cycle {cycle_results['cycle_id']}")
        
        # Ordenar tareas por prioridad y tiempo programado
        sorted_tasks = sorted(tasks, 
                             key=lambda t: (-t.priority, t.scheduled_time.timestamp() if t.scheduled_time else float('inf')))
        
        # Filtrar solo tareas pendientes
        pending_tasks = [t for t in sorted_tasks if t.status == "pending"]
        
        if not pending_tasks:
            logger.info("There's not pending task to execute")
            return cycle_results
        
        logger.info(f"Executing {len(pending_tasks)} pending tarsk")
        
        # Control de API y límites
        api_usage_tracker = self.state.api_usage.copy()
        api_limits = self.state.api_limits
        
        # Ejecutar cada tarea pendiente
        for task in pending_tasks:
            # Verificar si ya se alcanzó el límite de API para este tipo de tarea
            task_api_type = self._get_api_type_for_task(task.task_type)
            
            if task_api_type:
                # Verificar si hemos superado límites
                limit_per_minute, limit_per_hour = api_limits[task_api_type]
                
                current_usage = api_usage_tracker[task_api_type]
                if current_usage >= limit_per_hour:
                    logger.warning(f"API limit reached for {task_api_type}. Postponing task {task.task_id}")
                    # Reprogramar la tarea para más tarde
                    task.scheduled_time = datetime.now() + timedelta(hours=1)
                    continue
            
            try:
                logger.info(f"Executing task {task.task_id} - Type: {task.task_type}")
                
                # Marcar tarea como en progreso
                task.status = "in_progress"
                task.attempts += 1
                task.last_attempt_time = datetime.now()
                
                # Ejecutar según tipo de tarea
                if task.task_type == "search_category":
                    task_result = await self._execute_search_category_task(task)
                    if task_api_type:
                        api_usage_tracker[task_api_type] += 1
                
                elif task.task_type == "search_term":
                    task_result = await self._execute_search_term_task(task)
                    if task_api_type:
                        api_usage_tracker[task_api_type] += 1
                
                elif task.task_type == "join_entity":
                    task_result = await self._execute_join_entity_task(task)
                    if task_api_type:
                        api_usage_tracker[task_api_type] += 1
                
                elif task.task_type == "extract_members":
                    task_result = await self._execute_extract_members_task(task)
                    if task_api_type:
                        api_usage_tracker[task_api_type] += 1
                
                else:
                    logger.warning(f"Unknow type task: {task.task_type}")
                    task.status = "failed"
                    task.error = f"Unknow type task: {task.task_type}"
                    cycle_results["errors"].append({
                        "task_id": task.task_id,
                        "error": task.error
                    })
                    continue
                
                # Actualizar resultado de la tarea
                task.result = task_result
                task.status = "completed"
                
                # Añadir resultado al ciclo
                cycle_results["tasks_results"].append({
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "result": task_result
                })
                
                # Si encontró entidades, añadirlas al resultado del ciclo
                if "entities" in task_result:
                    new_entities = []
                    for entity in task_result["entities"]:
                        entity_id = entity.get("entity_id")
                        if entity_id and entity_id not in self.state.discovered_entities:
                            new_entities.append(entity)
                            self.state.discovered_entities.add(entity_id)
                    
                    if new_entities:
                        cycle_results["new_entities"].extend(new_entities)
                
                # Espera adaptativa entre tareas para evitar límites
                wait_time = self._calculate_wait_time(task_api_type, api_usage_tracker)
                if wait_time > 0:
                    logger.debug(f" Waiting {wait_time} segundos entre tareas")
                    await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Error executing task {task.task_id}: {e}")
                traceback.print_exc()
                
                task.error = str(e)
                
                # Verificar si se debe reintentar
                if task.attempts < task.max_attempts:
                    # Reprogramar con backoff exponencial
                    backoff = self.config["backoff_strategy"]
                    wait_time = min(
                        backoff["initial_wait"] * (backoff["factor"] ** (task.attempts - 1)),
                        backoff["max_wait"]
                    )
                    task.scheduled_time = datetime.now() + timedelta(seconds=wait_time)
                    task.status = "pending"
                    logger.info(f"Task {task.task_id} reprogramed to retry in {wait_time} seconds")
                else:
                    task.status = "failed"
                    cycle_results["errors"].append({
                        "task_id": task.task_id,
                        "error": task.error
                    })
        
        # Actualizar información de uso de API
        self.state.api_usage = api_usage_tracker
        cycle_results["api_usage"] = api_usage_tracker
        
        # Actualizar estado
        self.state.last_cycle_time = datetime.now()
        self.state.cycle_count += 1
        
        # Guardar estado al finalizar el ciclo
        self._save_state()
        
        logger.info(f"Discovery cycle completed. New entities: {len(cycle_results['new_entities'])}")
        
        return cycle_results
    
    def _get_api_type_for_task(self, task_type: str) -> Optional[str]:
        """Determines the API type for a given task type."""
        if task_type in ["search_category", "search_term"]:
            return "search_requests"
        elif task_type in ["extract_members"]:
            return "entity_requests"
        elif task_type in ["join_entity"]:
            return "join_requests"
        return None
    
    def _calculate_wait_time(self, api_type: Optional[str], usage: dict) -> float:
        """Calculate waiting time base on actual use of API."""
        if not api_type:
            return random.uniform(1.0, 3.0)  # Espera base para tareas sin tipo específico
        
        # Obtener límites configurados
        limit_per_minute, limit_per_hour = self.state.api_limits[api_type]
        current_usage = usage[api_type]
        
        # Calcular porcentaje de uso respecto al límite horario
        usage_percent = current_usage / limit_per_hour
        
        if usage_percent > 0.9:
            # Uso muy alto, espera más larga
            return random.uniform(15.0, 30.0)
        elif usage_percent > 0.7:
            # Uso alto
            return random.uniform(8.0, 15.0)
        elif usage_percent > 0.5:
            # Uso medio
            return random.uniform(5.0, 8.0)
        elif usage_percent > 0.3:
            # Uso bajo-medio
            return random.uniform(3.0, 5.0)
        else:
            # Uso bajo
            return random.uniform(1.0, 3.0)
    
    async def _execute_search_category_task(self, task: TelegramDiscoveryTask) -> dict:
        """Execute a search category task."""
        category = task.parameters.get("category")
        if not category:
            return {"error": "Categoría no especificada en parámetros"}
        
        logger.info(f"Buscando entidades para categoría: {category}")
        
        # Usar función existente en TelegramEntityFinder2
        entities = await self.finder.search_by_category_async(category)
        
        # Actualizamos estadísticas de efectividad
        if category not in self.state.effectiveness["categories"]:
            self.state.effectiveness["categories"][category] = 0.0
            
        if entities:
            # Calcular efectividad (entidades nuevas / total)
            new_entities = 0
            for entity in entities:
                entity_id = entity.get("entity_id")
                if entity_id and entity_id not in self.state.discovered_entities:
                    new_entities += 1
            
            effectiveness = new_entities / len(entities) if entities else 0
            
            # Actualizar efectividad con suavizado exponencial
            current = self.state.effectiveness["categories"][category]
            self.state.effectiveness["categories"][category] = 0.7 * current + 0.3 * effectiveness
            
            logger.info(f"Search completed. Entities: {len(entities)}, New: {new_entities}")
        else:
            # Disminuir efectividad si no se encontraron resultados
            current = self.state.effectiveness["categories"][category]
            self.state.effectiveness["categories"][category] = 0.7 * current
            
            logger.info(f"Search completed. No entities were found for: {category}")
        
        return {
            "category": category,
            "entities": entities or [],
            "timestamp": datetime.now().isoformat()
        }
    
    async def _execute_search_term_task(self, task: TelegramDiscoveryTask) -> dict:

        """Execute a search term task."""

        term = task.parameters.get("term")
        if not term:
            return {"error": "Term no specify in parameters"}
        
        logger.info(f" Searching entities for term: {term}")
        
        # Usar función existente en TelegramEntityFinder2
        entities = await self.finder.search_by_term_async(term)
        
        # Actualizamos estadísticas de efectividad
        if term not in self.state.effectiveness["terms"]:
            self.state.effectiveness["terms"][term] = 0.0
            
        if entities:
            # Calcular efectividad (entidades nuevas / total)
            new_entities = 0
            for entity in entities:
                entity_id = entity.get("entity_id")
                if entity_id and entity_id not in self.state.discovered_entities:
                    new_entities += 1
            
            effectiveness = new_entities / len(entities) if entities else 0
            
            # Actualizar efectividad con suavizado exponencial
            current = self.state.effectiveness["terms"][term]
            self.state.effectiveness["terms"][term] = 0.7 * current + 0.3 * effectiveness
            
            logger.info(f"Search completed. Entities: {len(entities)}, News: {new_entities}")
        else:
            # Disminuir efectividad si no se encontraron resultados
            current = self.state.effectiveness["terms"][term]
            self.state.effectiveness["terms"][term] = 0.7 * current
            
            logger.info(f"Search completed. No entities were found for term: '{term}'")
        
        return {
            "term": term,
            "entities": entities or [],
            "timestamp": datetime.now().isoformat()
        }
    
    async def _execute_join_entity_task(self, task: TelegramDiscoveryTask) -> dict:
        """Ejecuta una tarea de unirse a una entidad."""
        entity_id = task.parameters.get("entity_id")
        username = task.parameters.get("username")
        
        if not entity_id and not username:
            return {"error": "Identity id or username is needed to join an entity."}
        
        if entity_id:
            logger.info(f"Trying to joing entity ID: {entity_id}")
            
            # Usar función existente en TelegramEntityFinder2
            success = self.finder.join_entity_with_csv_data(entity_id)
        else:
            logger.info(f" Trying  {username}")
            
            # Usar función existente en TelegramEntityFinder2
            success = await self.finder.join_entity_async(username)
        
        return {
            "entity_id": entity_id,
            "username": username,
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
    
    # async def _execute_extract_members_task(self, task: TelegramDiscoveryTask) -> dict:
    #     """Ejecuta una tarea de extracción de miembros de una entidad."""
    #     entity_id = task.parameters.get("entity_id")
    #     method = task.parameters.get("method", "comprehensive")
    #     # discover_user_groups = task.parameters.get("discover_user_groups", True)
        
    #     if not entity_id:
    #         return {"error": "Entity ID needed for members extraction"}
        
    #     logger.info(f"Extracting members from  entity ID: {entity_id} xith method: {method}")
        
    #     try:
    #         if method == "comprehensive":
    #             # Usar el método más completo
    #             result = await self.finder.extract_users_ultimate_comprehensive_async(entity_id)
    #         elif method == "messages":
    #             # Usar método de análisis de mensajes
    #             result = await self.finder.extract_users_from_messages_comprehensive_async(entity_id)
    #         elif method == "reactions":
    #             # Usar método de análisis de reacciones
    #             result = await self.finder.extract_users_from_reactions_comprehensive_async(entity_id)
    #         elif method == "standard":
    #             # Usar método estándar
    #             result = await self.finder.extract_members_from_entity_async(entity_id)
    #         else:
    #             # Por defecto usar el método más completo
    #             result = await self.finder.extract_users_ultimate_comprehensive_async(entity_id)
                
    #         return {
    #             "entity_id": entity_id,
    #             "method": method,
    #             "members_extracted": result,
    #             "timestamp": datetime.now().isoformat()
    #         }
            
    #     except Exception as e:
    #         logger.error(f"Error extrating members from: {entity_id}: {e}")
    #         return {
            #     "entity_id": entity_id,
            #     "method": method,
            #     "error": str(e),
            #     "timestamp": datetime.now().isoformat()
            # }
    
    async def _execute_extract_members_task(self, task: TelegramDiscoveryTask) -> dict:
        """Ejecuta una tarea de extracción de miembros de una entidad."""
        entity_id = task.parameters.get("entity_id")
        method = task.parameters.get("method", "comprehensive")
        discover_user_groups = task.parameters.get("discover_user_groups", True)  # Nuevo parámetro
        
        if not entity_id:
            return {"error": "Entity ID needed for members extraction"}
        
        logger.info(f"Extracting members from entity ID: {entity_id} with method: {method}")
        
        try:
            # MODIFICACIÓN: Primero intentar resolver la entidad para manejar tanto usernames como IDs numéricos
            try:
                # Si es un username o contiene caracteres no numéricos, usarlo directamente
                if isinstance(entity_id, str) and (entity_id.startswith('@') or not entity_id.isdigit()):
                    # Es un username, usarlo directamente sin convertir a int
                    logger.info(f"Handling entity as username: {entity_id}")
                    
                    # Intentar resolver la entidad para verificar que existe
                    try:
                        entity = await self.finder.client.get_entity(entity_id)
                        logger.info(f"Entity resolved successfully: {entity.title}")
                        # Actualizamos entity_id al ID numérico para futuras referencias si es necesario
                        numeric_entity_id = str(entity.id)
                    except Exception as e:
                        logger.warning(f"Could not resolve entity with username {entity_id}: {e}")
                        # Continuamos con el username original si no se puede resolver
                        numeric_entity_id = entity_id
                else:
                    # Es un ID numérico, continuar como antes
                    logger.info(f"Handling entity as numeric ID: {entity_id}")
                    numeric_entity_id = entity_id
            except Exception as e:
                logger.warning(f"Error resolving entity type, proceeding with original: {e}")
                numeric_entity_id = entity_id
            # Extraer miembros con el método solicitado
            if method == "comprehensive":
                # Usar el método más completo
                result = await self.finder.extract_users_ultimate_comprehensive_async(entity_id)
            elif method == "messages":
                # Usar método de análisis de mensajes
                result = await self.finder.extract_users_from_messages_comprehensive_async(entity_id)
            elif method == "reactions":
                # Usar método de análisis de reacciones
                result = await self.finder.extract_users_from_reactions_comprehensive_async(entity_id)
            elif method == "standard":
                # Usar método estándar
                result = await self.finder.extract_members_from_entity_async(entity_id)
            else:
                # Por defecto usar el método más completo
                result = await self.finder.extract_users_ultimate_comprehensive_async(entity_id)
            
            # Resultado base
            task_result = {
                "entity_id": entity_id,
                "method": method,
                "members_extracted": result,
                "timestamp": datetime.now().isoformat()
            }
            
            # NUEVO: Descubrir grupos de usuarios si está habilitado
            if discover_user_groups and result > 0:
                # Recuperar información de usuarios extraídos
                user_groups_discovered = 0
                users_processed = 0
                
                # Obtener lista de miembros extraídos para esta entidad
                entity_members = []
                for key, member in self.finder.members.items():
                    if member.get('entity_id') == entity_id or member.get('entity_id') == numeric_entity_id:
                        entity_members.append(member)
                
                # Si hay miembros, seleccionar algunos para descubrir sus grupos
                if entity_members:
                    # Limitar usuarios a procesar (máximo 3 por entidad)
                    import random
                    sample_size = max(1, len(entity_members))
                    # selected_members = random.sample(entity_members, sample_size)
                    
                    logger.info(f"Discovering groups from {sample_size} users in entity {entity_id}")
                    # for member in selected_members:
                    for member in entity_members:
                        user_id = member.get('user_id')
                        username = member.get('username')
                        
                        # Usar identificador adecuado
                        user_identifier = f"@{username}" if username else user_id
                        
                        try:
                            # Usar la función original para descubrir grupos del usuario
                            # user_groups =  self.finder.discover_user_groups_original(user_identifier, limit=sample_size)
                            try:
                                # Usar la función mejorada para descubrir grupos del usuario
                                user_groups = await self.finder.discover_user_groups_improved_async(user_identifier, limit=sample_size)
                            except AttributeError:
                                # Si la función asíncrona no está disponible, usar la versión sincrónica
                                user_groups = self.finder.discover_user_groups_improved(user_identifier, limit=sample_size)
                            users_processed += 1
                            
                            if user_groups:
                                user_groups_discovered += len(user_groups)
                                logger.info(f"Found {len(user_groups)} groups for user {user_identifier}")
                                
                                # Crear tareas para unirse a grupos con alta confianza
                                for group in user_groups:
                                    if group.get("user_membership_confidence", 0) >= 0.5:
                                        # Solo si tiene username para poder unirse
                                        if group.get("username"):
                                            # Crear tarea para unirse más tarde
                                            self.state.tasks.append(TelegramDiscoveryTask(
                                                task_id=f"join_user_group_{int(time.time())}",
                                                task_type="join_entity",
                                                parameters={
                                                    "username": group.get("username"),
                                                    "entity_id": group.get("entity_id"),
                                                    "source": f"user_{user_id}"
                                                },
                                                priority=7,
                                                scheduled_time=datetime.now() + timedelta(
                                                    minutes=random.randint(15, 60)
                                                )
                                            ))
                            
                            # Pausa entre usuarios
                            await asyncio.sleep(5)
                            
                        except Exception as e:
                            logger.error(f"Error discovering groups for user {user_identifier}: {e}")
                    
                    # Incluir resultados de descubrimiento de grupos
                    task_result["user_groups_discovered"] = user_groups_discovered
                    task_result["users_processed_for_groups"] = users_processed
                else:
                    print(f"No members found for entity {entity_id} in method : {method}")
                
            return task_result
            
        except Exception as e:
            logger.error(f"Error extracting members from: {entity_id}: {e}")
            return {
                "entity_id": entity_id,
                "method": method,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
        }
    async def process_discovered_entities(self, entities: List[dict]) -> dict:
        """
        Process discovered entities to determine classification, actions, etc
        
        Args:
            entities: List of dictionaries representing discovered entities
            
        Returns:
            Clasification of entities and recommended actions
            
        """
        if not entities:
            return {
                "prioritized": [],
                "for_interaction": [],
                "for_monitoring": [],
                "irrelevant": []
            }
        
        logger.info(f"Processing {len(entities)} discovered entities...")
        
        # Clasificaciones de entidades
        prioritized = []  # Alta prioridad para extracción detallada
        for_interaction = []  # Entidades para unirse y/o interactuar
        for_monitoring = []  # Entidades para monitorear pasivamente
        irrelevant = []  # Entidades de baja relevancia
        
        # Calcular un score de relevancia para cada entidad
        threshold = self.config.get("entity_relevance_threshold", 0.6)

        # Lista para almacenar usuarios encontrados para procesamiento posterior
        discovered_users = []
        
        for entity in entities:
            # Calcular score de relevancia (0-1)
            relevance_score = self._calculate_entity_relevance(entity)
            entity["relevance_score"] = relevance_score

            
            
            # Clasificar según score
            if relevance_score >= 0.8:
                # Alta relevancia
                prioritized.append(entity)

                
                # Si se configura auto-join, también marcar para interacción
                if self.config.get("auto_join", True):
                    for_interaction.append(entity)
                    
            elif relevance_score >= threshold:
                # Relevancia media
                for_monitoring.append(entity)
                
                # Si tiene muchos miembros, considerar para interacción
                members_count = entity.get("members_count", 0)
                if isinstance(members_count, str):
                    try:
                        members_count = int(members_count)
                    except ValueError:
                        members_count = 0
                
                if members_count > 1000:
                    for_interaction.append(entity)
            else:
                # Baja relevancia
                irrelevant.append(entity)
        
        # Ordenar por relevancia
        prioritized.sort(key=lambda e: e.get("relevance_score", 0), reverse=True)
        for_interaction.sort(key=lambda e: e.get("relevance_score", 0), reverse=True)
        for_monitoring.sort(key=lambda e: e.get("relevance_score", 0), reverse=True)
        
        # Limitar cantidad de entidades para interacción (evitar unirse a demasiadas)
        max_joins = self.config.get("max_joins_per_day", 15)
        for_interaction = for_interaction[:max_joins]
        
        logger.info(f"Procesamiento completado: {len(prioritized)} prioritizadas, "
                  f"{len(for_interaction)} para interacción, {len(for_monitoring)} para monitoreo, "
                  f"{len(irrelevant)} irrelevantes")
        
        return {
            "prioritized": prioritized,
            "for_interaction": for_interaction,
            "for_monitoring": for_monitoring,
            "irrelevant": irrelevant
        }
    
    def _calculate_entity_relevance(self, entity: dict) -> float:
        """
        Calculate a relevance score for the entity based on various factors.
        Returns a value between 0 and 1, where 1 is maximum relevance.
        
        """
        score = 0.5  # Score inicial neutral
        
        # Factores que aumentan relevancia
        
        # 1. Tipo de entidad
        entity_type = entity.get("type", "unknown")
        if entity_type == "channel":
            score += 0.1  # Los canales suelen ser más relevantes para señales
        elif entity_type == "megagroup":
            score += 0.07  # Los supergrupos también pueden ser relevantes
        elif entity_type == "group":
            score += 0.06  # Los grupos también pueden ser relevantes para leads
        elif entity_type == "forum":
            score += 0.06     # Los foros también pueden ser relevantes para leads
            
        # 2. Categoría
        category = entity.get("category", "unknown")
        if category in self.config["categories"]:
            category_priority = self.config["categories"][category]["priority"]
            # Normalizar prioridad (1-10) a un boost de score (0-0.2)
            score += (category_priority / 10) * 0.2
            
        # 3. Cantidad de miembros
        members_count = entity.get("members_count", 0)
        if isinstance(members_count, str):
            try:
                members_count = int(members_count)
            except ValueError:
                members_count = 0
                
        if members_count > 10000:
            score += 0.15  # Canales muy grandes
        elif members_count > 5000:
            score += 0.1  # Canales grandes
        elif members_count > 1000:
            score += 0.05  # Canales medianos
        elif members_count < 100:
            score -= 0.1  # Canales muy pequeños suelen ser menos relevantes
            
        # 4. Verificación
        if entity.get("is_verified", False):
            score += 0.1  # Canales verificados son más confiables
            
        # 5. Descripción y título
        description = entity.get("description", "").lower()
        title = entity.get("title", "").lower()
        
        # Keywords que indican alta relevancia en el contexto de trading/señales
        high_value_keywords = ["signal", "alert", "trading", "profit", "analysis", 
                              "crypto", "forex", "stock", "market", "invest", "fx", "stock", "stockmarket", "strategy", "gold", "bitcoin", "ETH", "BTCUSD", "ETHUSD", "USD", "GBP", "EUR", "JPY", "AUS", "broker"]
        
        for keyword in high_value_keywords:
            if keyword in description or keyword in title:
                score += 0.03  # Cada keyword relevante suma
                
        # Keywords que indican posibles estafas o contenido de baja calidad
        low_value_keywords = ["scam", "spam", "fake", "porn", "bet", "gambling", 
                             "loan", "casino", "free money", "get rich"]
        
        for keyword in low_value_keywords:
            if keyword in description or keyword in title:
                score -= 0.05  # Cada keyword negativa resta
                
        # Restringidos suelen ser menos confiables
        if entity.get("is_restricted", False):
            score -= 0.1
            
        # 6. Lenguaje (ajustar según preferencias)
        language = entity.get("language", "unknown")
        if language in ["en", "es"]:  # Ejemplo: priorizar inglés y español
            score += 0.05
            
        # Normalizar a rango 0-1
        return max(0.0, min(1.0, score))
    
    async def extract_relevant_data(self, prioritized_entities: List[dict]) -> dict:
        """
        Extract relevant data from prioritized entities.
        
        Args:
            prioritized_entities: List of prioritized entities
            
        Returns:
            Data extraction results from entities
        """
        if not prioritized_entities:
            return {"entities_processed": 0, "extraction_results": []}
        
        logger.info(f"Extracting data from: {len(prioritized_entities)} priority entities.")
        
        extraction_results = []
        
        # Determinar profundidad de extracción según config
        extraction_depth = self.config.get("extraction_depth", {})
        high_depth = extraction_depth.get("high_relevance", 5)
        medium_depth = extraction_depth.get("medium_relevance", 3)
        low_depth = extraction_depth.get("low_relevance", 1)
        
        for entity in prioritized_entities:
            entity_id = entity.get("entity_id")
            relevance = entity.get("relevance_score", 0)
            
            if not entity_id:
                continue
                
            # Determinar método y profundidad según relevancia
            if relevance >= 0.8:
                # Alta relevancia: extracción completa
                method = "comprehensive"
                depth = high_depth
            elif relevance >= 0.6:
                # Media relevancia: extracción de mensajes
                method = "messages"
                depth = medium_depth
            else:
                # Baja relevancia: extracción básica
                method = "standard"
                depth = low_depth
                
            # Crear tarea de extracción
            task_id = f"extract_{entity_id}_{int(time.time())}"
            task = TelegramDiscoveryTask(
                task_id=task_id,
                task_type="extract_members",
                parameters={
                    "entity_id": entity_id,
                    "method": method,
                    "depth": depth
                },
                priority=int(relevance * 10)  # Prioridad basada en relevancia (0-10)
            )
            
            # Ejecutar tarea directamente
            try:
                result = await self._execute_extract_members_task(task)
                extraction_results.append(result)
                
                # Esperar entre extracciones para evitar límites
                await asyncio.sleep(random.uniform(5, 10))
                
            except Exception as e:
                logger.error(f"Error extracting entity data {entity_id}: {e}")
                extraction_results.append({
                    "entity_id": entity_id,
                    "error": str(e)
                })
        
        return {
            "entities_processed": len(prioritized_entities),
            "extraction_results": extraction_results
        }
    
    async def manage_entity_interactions(self, entities_to_interact: List[dict]) -> dict:
        """
        Manage interactions with entities( e.g. join groups, send messages, etc.)
        
        Args:
            entities_to_interact: Entities list to interact with
            
        Returns:
            Interaction results
        """
        if not entities_to_interact:
            return {"interactions": 0, "results": []}
        
        logger.info(f" Managing interaction with : {len(entities_to_interact)} entities")
        
        # Verificar límite diario de interacciones
        max_joins = self.config.get("max_joins_per_day", 15)
        
        # Contar cuántas uniones ya hemos realizado hoy
        today = datetime.now().date()
        today_joins = 0
        
        # Buscar en tareas completadas hoy
        for task in self.state.tasks:
            if (task.task_type == "join_entity" and 
                task.status == "completed" and 
                task.last_attempt_time and 
                task.last_attempt_time.date() == today):
                today_joins += 1
        
        remaining_joins = max_joins - today_joins
        if remaining_joins <= 0:
            logger.warning(f"Day limit of union raised ({max_joins}). There willbe no more interactions today.")
            return {"interactions": 0, "results": [], "limit_reached": True}
        
        # Limitar cantidad de interacciones a realizar
        entities_to_process = entities_to_interact[:remaining_joins]
        
        interaction_results = []
        interactions_count = 0
        
        for entity in entities_to_process:
            entity_id = entity.get("entity_id")
            username = entity.get("username")
            
            if not entity_id:
                continue
                
            # Crear tarea de unión
            task_id = f"join_{entity_id}_{int(time.time())}"
            task = TelegramDiscoveryTask(
                task_id=task_id,
                task_type="join_entity",
                parameters={
                    "entity_id": entity_id,
                    "username": username
                },
                priority=7  # Prioridad alta para uniones
            )
            
            # Ejecutar tarea directamente
            try:
                result = await self._execute_join_entity_task(task)
                interaction_results.append(result)
                
                if result.get("success"):
                    interactions_count += 1
                
                # Esperar entre interacciones para parecer más natural
                await asyncio.sleep(random.uniform(20, 60))
                
            except Exception as e:
                logger.error(f"Error interacting with entity: {entity_id}: {e}")
                interaction_results.append({
                    "entity_id": entity_id,
                    "error": str(e)
                })
        
        return {
            "interactions": interactions_count,
            "results": interaction_results
        }
    
    def adapt_discovery_strategy(self, cycle_results: dict) -> dict:
        """
        Adapts the discovery strategy based on recent results.
        
        Args:
            cycle_results: Results of the current discovery cycle
            
        Returns:
            Updated strategy configuration
        """
        logger.info("Adapting discovery strategy based on recent results...")
        
        strategy_updates = {
            "categories_adjusted": {},
            "terms_adjusted": {},
            "api_limits_adjusted": False
        }
        
        # 1. Ajustar prioridades de categorías según efectividad
        for category, effectiveness in self.state.effectiveness["categories"].items():
            if category in self.config["categories"]:
                old_priority = self.config["categories"][category]["priority"]
                
                # Ajustar prioridad según efectividad
                if effectiveness > 0.7:
                    # Categoría muy efectiva: aumentar prioridad
                    new_priority = min(10, old_priority + 1)
                elif effectiveness < 0.3 and effectiveness > 0:
                    # Categoría poco efectiva: disminuir prioridad
                    new_priority = max(1, old_priority - 1)
                else:
                    # Mantener igual
                    new_priority = old_priority
                
                if new_priority != old_priority:
                    self.config["categories"][category]["priority"] = new_priority
                    strategy_updates["categories_adjusted"][category] = {
                        "old_priority": old_priority,
                        "new_priority": new_priority,
                        "effectiveness": effectiveness
                    }
        
        # 2. Ajustar boost de términos según efectividad
        for term, effectiveness in self.state.effectiveness["terms"].items():
            if term in self.config["search_terms_boost"]:
                old_boost = self.config["search_terms_boost"][term]
                
                # Ajustar boost según efectividad
                if effectiveness > 0.7:
                    # Término muy efectivo: aumentar boost
                    new_boost = min(3.0, old_boost + 0.2)
                elif effectiveness < 0.3 and effectiveness > 0:
                    # Término poco efectivo: disminuir boost
                    new_boost = max(0.5, old_boost - 0.2)
                else:
                    # Mantener igual
                    new_boost = old_boost
                
                if abs(new_boost - old_boost) > 0.1:  # Cambio significativo
                    self.config["search_terms_boost"][term] = new_boost
                    strategy_updates["terms_adjusted"][term] = {
                        "old_boost": old_boost,
                        "new_boost": new_boost,
                        "effectiveness": effectiveness
                    }
        
        # 3. Ajustar límites de API si se alcanzaron
        api_usage = cycle_results.get("api_usage", {})
        for api_type, usage in api_usage.items():
            if api_type in self.state.api_limits:
                limit_per_minute, limit_per_hour = self.state.api_limits[api_type]
                
                # Si estamos cerca del límite, reducir actividad
                if usage > limit_per_hour * 0.9:
                    logger.warning(f"API {api_type} usage is close to the limit. Adjusting strategy.")
                    strategy_updates["api_limits_adjusted"] = True
                    
                    # Reducir max_tasks_per_cycle temporalmente
                    original = self.config.get("max_tasks_per_cycle", 20)
                    self.config["max_tasks_per_cycle"] = max(5, original // 2)
                    
                    # Programar recuperación después de un tiempo
                    task_id = f"restore_limits_{int(time.time())}"
                    restore_task = TelegramDiscoveryTask(
                        task_id=task_id,
                        task_type="restore_limits",
                        parameters={"original_max_tasks": original},
                        scheduled_time=datetime.now() + timedelta(hours=6)
                    )
                    self.state.tasks.append(restore_task)
        
        # Guardar configuración actualizada
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Updated Configuration saved")
        except Exception as e:
            logger.error(f"Error saving updated configuration {e}")
        
        return strategy_updates
    
    async def send_to_bot(self, data: dict) -> dict:
        """
        Sent relevate data to external bot.
        
        Args:
            data: Data to send
            
        Returns:
            Integration state with external bot
        """
        if not self.bot_api_url or not self.bot_api_key:
            logger.warning("External bot integration has not been configured")
            return {"success": False, "reason": "Bot API no configurada"}
        
        try:
            logger.info("Sending data to external bot")
            
            # Preparar datos para el bot en formato adecuado
            bot_data = {
                "api_key": self.bot_api_key,
                "timestamp": datetime.now().isoformat(),
                "action": "discovery_update",
                "data": {
                    "new_entities": self._format_entities_for_bot(data.get("new_entities", [])),
                    "extracted_data": data.get("extracted_data", {}),
                    "interactions": data.get("interactions", {})
                }
            }
            
            # Aquí implementaríamos la llamada real a la API del bot
            # Para este ejemplo, solo simulamos la respuesta
            
            # En una implementación real:
            # import aiohttp
            # async with aiohttp.ClientSession() as session:
            #     async with session.post(self.bot_api_url, json=bot_data) as response:
            #         if response.status == 200:
            #             bot_response = await response.json()
            #             return {"success": True, "response": bot_response}
            #         else:
            #             error_text = await response.text()
            #             return {"success": False, "error": error_text}
            
            # Simulación para este ejemplo
            simulated_response = {
                "status": "ok",
                "received_entities": len(data.get("new_entities", [])),
                "message": "Data processed successfully"
            }
            
            logger.info(f"Data successfully sent to the bot. Entities: {len(data.get('new_entities', []))}")
            
            return {"success": True, "response": simulated_response}
            
        except Exception as e:
            logger.error(f"Error sending data to the bot: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_entities_for_bot(self, entities: List[dict]) -> List[dict]:
        """Format entities for external bot communication."""
        formatted = []
        
        for entity in entities:
            # Incluir solo campos relevantes para el bot
            formatted.append({
                "entity_id": entity.get("entity_id", ""),
                "username": entity.get("username", ""),
                "title": entity.get("title", ""),
                "type": entity.get("type", "unknown"),
                "category": entity.get("category", "unknown"),
                "language": entity.get("language", "unknown"),
                "members_count": entity.get("members_count", 0),
                "invite_link": entity.get("invite_link", ""),
                "relevance_score": entity.get("relevance_score", 0),
                "discovery_date": datetime.now().isoformat()
            })
        
        return formatted
    
    async def run(self) -> None:
        """Execute the main cycle of the discovery system."""
        if self.running:
            logger.warning("The discovery system is already running.")
            return
        
        self.running = True
        
        try:
            # Inicializar el sistema
            initialized = await self.initialize_automated_discovery()
            if not initialized:
                logger.error("The discovery system could not be initialized.")
                self.running = False
                return
            
            logger.info("Starting main cycle of automatic discovery")
            
            # Ciclo principal de ejecución continua
            while self.running:
                if self.paused:
                    logger.info("System paused. Waiting...")
                    await asyncio.sleep(60)  # Verificar cada minuto si se reanuda
                    continue
                
                try:
                    # 1. Generar tareas de descubrimiento
                    tasks = self.schedule_discovery_tasks()
                    
                    # 2. Ejecutar tareas programadas
                    cycle_results = await self.execute_discovery_cycle(tasks)
                    
                    # 3. Procesar entidades encontradas
                    if cycle_results.get("new_entities"):
                        processed_entities = await self.process_discovered_entities(cycle_results["new_entities"])
                        
                        # 4. Extraer datos relevantes de entidades prioritarias
                        extraction_results = await self.extract_relevant_data(processed_entities["prioritized"])
                        
                        # 5. Gestionar interacciones con entidades seleccionadas
                        interaction_results = await self.manage_entity_interactions(processed_entities["for_interaction"])
                        
                        # 6. Adaptar estrategia según resultados
                        self.adapt_discovery_strategy(cycle_results)
                        
                        # 7. Enviar datos relevantes al bot existente
                        bot_update = await self.send_to_bot({
                            "new_entities": processed_entities["for_interaction"] + processed_entities["for_monitoring"],
                            "extracted_data": extraction_results,
                            "interactions": interaction_results
                        })
                        
                        if not bot_update.get("success"):
                            logger.warning(f"Data could not be sent to the bot: {bot_update.get('error', 'Unknown error')}")
                    else:
                        logger.info("No new entities were found in this cycle")
                    
                    # Guardar estado actual
                    self._save_state()
                    
                    # Esperar hasta el próximo ciclo
                    await self.wait_until_next_cycle()
                    
                except Exception as e:
                    logger.error(f"Error in discovery system: {e}")
                    traceback.print_exc()
                    
                    # Esperar un tiempo y continuar con el siguiente ciclo
                    await asyncio.sleep(300)  # 5 minutos
            
            logger.info("Main discovery cycle completed")
            
        except Exception as e:
            logger.error(f"Error (mayor) in discovery system: {e}")
            traceback.print_exc()
        finally:
            self.running = False
            # Cerrar conexiones y recursos
            if self.finder:
                self.finder.close()
    
    async def wait_until_next_cycle(self) -> None:
        """Wait until it's time to run the next cycle."""
        run_interval = self.config.get("run_interval_minutes", 30)
        
        # Añadir un poco de variación para evitar patrones predecibles
        jitter = random.uniform(-2, 5)  # Entre -2 y +5 minutos de variación
        wait_minutes = max(1, run_interval + jitter)  # Mínimo 1 minuto
        
        logger.info(f"Waiting {wait_minutes:.1f} minutes until next discovery cycle")
        
        # Esperar el tiempo configurado
        await asyncio.sleep(wait_minutes * 60)
    
    def pause(self) -> None:
        """Pause the execution from the system."""
        if not self.paused:
            self.paused = True
            logger.info("System Paused")
    
    def resume(self) -> None:
        """Resume the execution of the system."""
        if self.paused:
            self.paused = False
            logger.info("Resuming System")
    
    def stop(self) -> None:
        """Stop the execution of the system."""
        self.running = False
        logger.info("Stopping system... Wait for the actual cycle to finish")


# Función principal para ejecutar el sistema
async def main():
    # Configuración inicial
    discovery_bot = TelegramDiscoveryBot()
    
    # Iniciar sistema
    await discovery_bot.run()


# Función de inicio para ejecutar en main
def run_discovery_bot():
    # Configurar event loop
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("System stoped by user")
    finally:
        loop.close()


# Punto de entrada cuando se ejecuta como script
if __name__ == "__main__":
    run_discovery_bot()