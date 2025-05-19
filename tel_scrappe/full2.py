import csv
import os
import time
import random
import json
import logging
import traceback
from telethon.sync import TelegramClient
from telethon.tl.functions.contacts import SearchRequest, ResolveUsernameRequest
from telethon.tl.functions.channels import GetFullChannelRequest, JoinChannelRequest
from telethon.tl.functions.messages import GetDialogsRequest, SearchGlobalRequest, GetFullChatRequest
from telethon.tl.types import InputPeerEmpty, ChannelParticipantsSearch, ChannelParticipantsAdmins
from telethon.errors import FloodWaitError, ChannelPrivateError, UsernameNotOccupiedError

import asyncio
from pyrogram.client import Client
from pyrogram.raw.functions.channels.get_participants import GetParticipants
from pyrogram.raw.types.input_peer_channel import  InputPeerChannel
from pyrogram.raw.types.channel_participants_search import  ChannelParticipantsSearch
import pyrogram
from telethon.tl import functions



from telethon.tl.types import PeerChannel
import re

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("telegram_finder.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constantes y configuración
CREDENTIAL_FILE = "credentials.json"
CHANNELS_CSV = "telegram_entities.csv"  # Archivo CSV principal optimizado
MEMBERS_CSV = "telegram_members.csv"    # Archivo para guardar miembros
CSV_FIELDS = [
    'entity_id',         # ID numérico único de la entidad
    'username',          # Nombre de usuario (sin @)
    'title',             # Título o nombre del canal/grupo
    'type',              # Tipo: channel, megagroup, group
    'members_count',     # Número de miembros
    'invite_link',       # Enlace de invitación (t.me/username)
    'description',       # Descripción o "about"
    'is_public',         # Si es público o privado
    'is_verified',       # Si está verificado
    'is_restricted',     # Si está restringido
    'category',          # Categoría detectada (crypto, forex, etc.)
    'language',          # Idioma detectado
    'discovery_term',    # Término usado para encontrarlo
    'discovery_date',    # Fecha y hora de descubrimiento
    'last_message_date'  # Fecha del último mensaje (si está disponible)
]

MEMBER_FIELDS = [
    'user_id',          # ID único del usuario
    'access_hash',      # Hash de acceso necesario para operaciones
    'username',         # Nombre de usuario (sin @)
    'first_name',       # Nombre
    'last_name',        # Apellido
    'entity_id',        # ID de la entidad a la que pertenece
    'entity_title',     # Nombre de la entidad
    'is_bot',           # Si es un bot
    'is_admin',         # Si es administrador
    'role',             # Rol: admin, bot, regular
    'participation_type', # Tipo: active, forwarded, etc.
    'extraction_date'   # Fecha de extracción
]

# Términos de búsqueda organizados por categoría
SEARCH_TERMS = {
    "crypto": [
        "bitcoin", "btc", "ethereum", "eth", "crypto", "cryptocurrency", "altcoin",
        "binance", "trading", "blockchain", "criptomonedas", "defi", "nft"
    ],
    "forex": [
        "forex", "fx", "forextrading", "forexsignals", "forexmarket", "trader",
        "daytrading", "currencytrading", "pips", "scalping"
    ],
    "investing": [
        "investing", "investment", "stocks", "stockmarket", "dividends", 
        "investor", "bolsa", "inversiones", "finanzas"
    ]
}

# Patrones de idioma para detección automática
LANGUAGE_PATTERNS = {
    "es": ["español", "es", "inversiones", "señales", "beneficios", "mercado", "bolsa", "criptomonedas"],
    "en": ["english", "signals", "market", "trading", "investment", "profits", "crypto"],
    "fr": ["français", "signaux", "marché", "négociation", "investissement"],
    "pt": ["português", "sinais", "mercado", "negociação", "investimento"],
    "ru": ["русский", "сигналы", "рынок", "торговля", "инвестиции"],
    "tr": ["türkçe", "sinyaller", "piyasa", "ticaret", "yatırım"]}

def run_async(coroutine):
        """Runs a coroutine in the existing event loop with proper error handling"""
        import threading
        
        try:
             # Get the current event loop - this should be the same one Telethon is using
            # Intentar obtener el loop actual
            # loop = asyncio.get_event_loop()
            loop = asyncio.get_running_loop()
            
            # Verificar si el loop está corriendo
            if loop.is_running():
                # Si el loop ya está en ejecución, necesitamos un enfoque diferente
                # Creamos un nuevo loop en un nuevo thread
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    return new_loop.run_until_complete(coroutine)
                
                # Ejecutar en un nuevo thread
                thread = threading.Thread(target=run_in_new_loop)
                thread.start()
                thread.join()  # Esperar a que termine
                return None  # No podemos devolver el resultado directamente en este caso
            else:
                # Si el loop no está en ejecución, podemos usar run_until_complete
                return loop.run_until_complete(coroutine)
        except RuntimeError:
            # Si hay un error porque no existe un loop, creamos uno nuevo
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coroutine)
            finally:
                loop.close()  # Cerrar el loop solo si lo creamos nosotros

class TelegramEntityFinder2:
    
    def __init__(self):
        # Código de inicialización existente
        self.client = None
        self.entities = {}  
        self.members = {}   
        self.csv_file = None
        self.csv_writer = None
        self.member_csv_file = None
        self.member_csv_writer = None
        self.initialized = False
    
    #############################################
    # SECCIÓN 1: INICIALIZACIÓN Y CONFIGURACIÓN #
    #############################################
    
    def initialize(self):
        """Inicializa el cliente y prepara los archivos CSV"""
        
        try:
            # Inicializar cliente de Telegram
            
            # Inicializar cliente de Telegram
            self.client = self.get_telegram_client()
            
            # Preparar archivo CSV para entidades
            file_exists = os.path.exists(CHANNELS_CSV)
            
            # Cargar entidades existentes para evitar duplicados
            if file_exists:
                self.load_existing_entities()
            
            # Abrir archivo en modo append
            self.csv_file = open(CHANNELS_CSV, 'a', newline='', encoding='utf-8')
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=CSV_FIELDS)
            
            # Escribir encabezados si es un archivo nuevo
            if not file_exists:
                self.csv_writer.writeheader()
            
            # Preparar archivo CSV para miembros
            member_file_exists = os.path.exists(MEMBERS_CSV)
            
            # Cargar miembros existentes para evitar duplicados
            if member_file_exists:
                self.load_existing_members()
            
            # Abrir archivo para miembros
            self.member_csv_file = open(MEMBERS_CSV, 'a', newline='', encoding='utf-8')
            self.member_csv_writer = csv.DictWriter(self.member_csv_file, fieldnames=MEMBER_FIELDS)
            
            # Escribir encabezados si es un archivo nuevo
            if not member_file_exists:
                self.member_csv_writer.writeheader()
            
            self.initialized = True
            logger.info("Sistema inicializado correctamente")
            return True
        
        except Exception as e:
            logger.error(f"Error durante la inicialización: {e}")
            traceback.print_exc()
            if self.csv_file:
                self.csv_file.close()
            if self.member_csv_file:
                self.member_csv_file.close()
            return False
    
    def get_telegram_client(self):
        """Obtiene o crea un cliente de Telegram"""
        if not os.path.exists(CREDENTIAL_FILE):
            self.create_credentials_file()
        
        try:
            with open(CREDENTIAL_FILE, 'r') as f:
                credentials = json.load(f)
            
            client = TelegramClient(
                session=credentials['phone'],
                api_id=credentials['api_id'],
                api_hash=credentials['api_hash'],
                system_version="4.16.30-vxCUSTOM",  # Versión personalizada para evitar restricciones
                device_model="Desktop",
                app_version="1.0.0"
            )
            
            client.connect()
            
            if not client.is_user_authorized():
                client.send_code_request(credentials['phone'])
                code = input('Ingresa el código de verificación recibido: ')
                client.sign_in(credentials['phone'], code)
            
            me = client.get_me()
            logger.info(f"Conectado como: {me.first_name} {getattr(me, 'last_name', '')}")
            
            return client
        
        except Exception as e:
            logger.error(f"Error al iniciar cliente: {e}")
            raise
    
    def create_credentials_file(self):
        """Crea un archivo de credenciales para la API de Telegram"""
        print("\n=== CONFIGURACIÓN DE CREDENCIALES ===")
        print("Para usar este script, necesitas obtener api_id y api_hash de Telegram.")
        print("Sigue estos pasos:")
        print("1. Visita https://my.telegram.org/auth")
        print("2. Inicia sesión con tu número de teléfono")
        print("3. Haz clic en 'API development tools'")
        print("4. Crea una nueva aplicación")
        
        api_id = input("\nIngresa tu api_id: ")
        api_hash = input("Ingresa tu api_hash: ")
        phone = input("Ingresa tu número de teléfono (con código de país, ej: +34612345678): ")
        
        credentials = {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "phone": phone
        }
        
        with open(CREDENTIAL_FILE, "w") as f:
            json.dump(credentials, f, indent=2)
        
        print(f"Credenciales guardadas en {CREDENTIAL_FILE}")
    
    def load_existing_entities(self):
        """Carga entidades existentes para evitar duplicados"""
        try:
            with open(CHANNELS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_id = row.get('entity_id')
                    if entity_id:
                        self.entities[entity_id] = row
            
            logger.info(f"Cargadas {len(self.entities)} entidades existentes")
        except Exception as e:
            logger.error(f"Error cargando entidades existentes: {e}")
    
    def load_existing_members(self):
        """Carga miembros existentes para evitar duplicados"""
        try:
            if os.path.exists(MEMBERS_CSV):
                with open(MEMBERS_CSV, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        user_id = row.get('user_id')
                        entity_id = row.get('entity_id')
                        if user_id and entity_id:
                            key = f"{user_id}_{entity_id}"
                            self.members[key] = row
                
                logger.info(f"Cargados {len(self.members)} miembros existentes")
        except Exception as e:
            logger.error(f"Error cargando miembros existentes: {e}")
    
    def close(self):
        """Cierra recursos abiertos"""
        try:
            if self.csv_file:
                self.csv_file.close()
            
            if self.member_csv_file:
                self.member_csv_file.close()
            
            if self.client:
                self.client.disconnect()
            
            logger.info("Recursos cerrados correctamente")
        except Exception as e:
            logger.error(f"Error cerrando recursos: {e}")
    
    ###########################
    # SECCIÓN 2: UTILIDADES  #
    ###########################
    
    def detect_language(self, text):
        """Detecta el idioma del texto basado en patrones conocidos"""
        if not text:
            return "unknown"
        
        text = text.lower()
        scores = {lang: 0 for lang in LANGUAGE_PATTERNS}
        
        for lang, patterns in LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if pattern in text:
                    scores[lang] += 1
        
        # Determinar el idioma con mayor puntuación
        max_score = 0
        detected_lang = "unknown"
        
        for lang, score in scores.items():
            if score > max_score:
                max_score = score
                detected_lang = lang
        
        return detected_lang
    
    def detect_category(self, title, description):
        """Detecta la categoría basada en título y descripción"""
        if not title and not description:
            return "unknown"
        
        text = (title + " " + (description or "")).lower()
        scores = {category: 0 for category in SEARCH_TERMS}
        
        for category, terms in SEARCH_TERMS.items():
            for term in terms:
                if term in text:
                    scores[category] += 1
        
        # Determinar la categoría con mayor puntuación
        max_score = 0
        detected_category = "unknown"
        
        for category, score in scores.items():
            if score > max_score:
                max_score = score
                detected_category = category
        
        return detected_category
    
    def update_entity_in_csv(self, entity_id, field, new_value):
        """Actualiza un campo de una entidad en el archivo CSV"""
        try:
            # Leer todo el CSV
            rows = []
            with open(CHANNELS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('entity_id') == entity_id:
                        row[field] = new_value
                    rows.append(row)
            
            # Escribir de vuelta todo el CSV
            with open(CHANNELS_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
                writer.writerows(rows)
                
            logger.info(f"Actualizado campo {field} de entidad {entity_id} a {new_value} en CSV")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando entidad en CSV: {e}")
            return False
    
    # Nuevas funciones auxiliares para reducir duplicación
    def _process_user_safely(self, user, entity_id, entity_title, user_ids_found, users_list, is_admin=False, is_forwarded=False, source=""):
        """
        Procesa un usuario de manera segura, verificando que sea válido y no duplicado.
        
            Args:
            user: Objeto de usuario a procesar
            entity_id: ID de la entidad
            entity_title: Título de la entidad
            user_ids_found: Conjunto de IDs de usuarios ya encontrados
            users_list: Lista donde agregar el usuario
            is_admin: Si el usuario es administrador
            is_forwarded: Si el usuario fue encontrado a través de un reenvío
            source: Descripción de la fuente (para registro)
        
        Returns:
            bool: Si el usuario fue procesado exitosamente
        """
        # Verificaciones comunes
        if not user:
            return False
            
        # Verificar si es un canal en lugar de un usuario
        if hasattr(user, 'broadcast') or hasattr(user, 'megagroup') or not hasattr(user, 'first_name'):
            return False
            
        if hasattr(user, 'bot') and user.bot:
            return False
            
        if user.id in user_ids_found:
            return False
        
        try:
            # Procesar el usuario
            self.process_member(user, entity_id, entity_title, is_admin, is_forwarded)
            users_list.append(user)
            user_ids_found.add(user.id)
            
            if source:
                username_display = f"@{user.username}" if hasattr(user, 'username') and user.username else "sin username"
                print(f"Usuario encontrado vía {source}: {user.first_name} ({username_display})")
            
            return True
        except Exception as e:
            logger.warning(f"Error procesando usuario {getattr(user, 'id', 'desconocido')}: {e}")
            return False
    
    async def _get_entity_safely(self, entity_id):
        """
        Obtiene una entidad con manejo de errores.
        Args:
            : ID o username de la entidad
    
        Returns:
            tuple: (entity, entity_title, error_message)
        """
        try:
            if isinstance(entity_id, str) and entity_id.startswith('@'):
                entity = await self.client.get_entity(entity_id)
            else:
                entity = await self.client.get_entity(int(entity_id))
            
            entity_title = entity.title if hasattr(entity, 'title') else "Entidad desconocida"
            return entity, entity_title, None
        except Exception as e:
            error_message = f"Error obteniendo entidad {entity_id}: {e}"
            logger.error(error_message)
            return None, None, error_message
    
    ############################################
    # SECCIÓN 3: BÚSQUEDA Y ESCANEO DE ENTIDADES #
    ############################################
    
    def process_entity(self, entity, discovery_term=""):
        """Procesa una entidad de Telegram y extrae sus datos relevantes"""
        try:
            entity_id = str(entity.id)
        
            # Verificar si ya tenemos esta entidad
            if entity_id in self.entities:
                return None
            
            # Detectar tipo de entidad (mejorado para cubrir todos los tipos)
            entity_type = "unknown"
            
            # Canales de difusión
            if hasattr(entity, 'broadcast') and entity.broadcast:
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    # Esto es técnicamente un supergrupo con capacidades de difusión
                    entity_type = "megagroup"
                else:
                    entity_type = "channel"
            
            # Supergrupos
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                entity_type = "megagroup"
            
            # Grupos gigantes (otra variante de supergrupos)
            elif hasattr(entity, 'gigagroup') and entity.gigagroup:
                entity_type = "megagroup"
            
            # Foros (grupos con hilos de discusión)
            elif hasattr(entity, 'forum') and entity.forum:
                entity_type = "forum"
            
            # Grupos normales (no supergrupos)
            # Los grupos normales no tienen el atributo broadcast ni megagroup
            elif hasattr(entity, 'chat') or (hasattr(entity, 'title') and not hasattr(entity, 'broadcast')):
                entity_type = "group"
            
            # Extraer atributos básicos
            username = entity.username if hasattr(entity, 'username') else ""
            title = entity.title if hasattr(entity, 'title') else "Unknown"
            is_verified = entity.verified if hasattr(entity, 'verified') else False
            is_restricted = entity.restricted if hasattr(entity, 'restricted') else False
            invite_link = f"https://t.me/{username}" if username else ""
            
            # Verificar si es un grupo con capacidad de voz/video
            has_voice = False
            has_video = False
            if hasattr(entity, 'call_active') and entity.call_active:
                has_voice = True
                if hasattr(entity, 'call_not_empty') and entity.call_not_empty:
                    has_video = True
            
            # Obtener detalles completos (si es posible)
            members_count = 0
            description = ""
            last_message_date = ""
            topics_count = 0  # Para foros
            
            try:
                # Intentar diferentes métodos según el tipo de entidad
                if entity_type in ["channel", "megagroup", "forum"]:
                    full_entity = self.client(GetFullChannelRequest(channel=entity))
                    members_count = full_entity.full_chat.participants_count
                    description = full_entity.full_chat.about or ""
                    
                    # Para foros, intentar obtener el número de temas
                    if entity_type == "forum" and hasattr(full_entity.full_chat, 'topics_count'):
                        topics_count = full_entity.full_chat.topics_count
                
                elif entity_type == "group":
                    # Para grupos normales usamos diferentes métodos
                    try:
                        full_chat = self.client(GetFullChatRequest(chat_id=entity.id))
                        if hasattr(full_chat, 'participants_count'):
                            members_count = full_chat.participants_count
                        if hasattr(full_chat, 'about'):
                            description = full_chat.about or ""
                    except:
                        # Si falla, intentar obtener participantes directamente
                        participants = self.client.get_participants(entity)
                        members_count = len(participants)
                
                # Intentar obtener el último mensaje
                messages = self.client.get_messages(entity, limit=1)
                if messages and len(messages) > 0:
                    last_message_date = messages[0].date.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"No se pudieron obtener detalles completos para entidad {entity_id}: {e}")
            
            # Detectar idioma y categoría
            detected_language = self.detect_language(description + " " + title)
            detected_category = self.detect_category(title, description)
            
            # Crear registro estructurado
            entity_data = {
                'entity_id': entity_id,
                'username': username,
                'title': title,
                'type': entity_type,
                'members_count': members_count,
                'invite_link': invite_link,
                'description': description,
                'is_public': True if username else False,
                'is_verified': is_verified,
                'is_restricted': is_restricted,
                'category': detected_category,
                'language': detected_language,
                'discovery_term': discovery_term,
                'discovery_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_message_date': last_message_date
            }
            
            # Guardar en memoria
            self.entities[entity_id] = entity_data
            
            # Filtrar solo campos válidos que existan en CSV_FIELDS
            csv_entity_data = {}
            for field in CSV_FIELDS:
                if field in entity_data:
                    csv_entity_data[field] = entity_data[field]
            
            # Escribir en CSV
            self.csv_writer.writerow(csv_entity_data)
            self.csv_file.flush()  # Asegurar que se escriba inmediatamente
            
            logger.info(f"Entidad guardada: {title} ({entity_id}) - {entity_type}, {members_count} miembros")
            
            return entity_data
        
        except Exception as e:
            logger.error(f"Error procesando entidad: {e}")
            traceback.print_exc()
            return None
    
    async def process_entity_async(self, entity, discovery_term=""):
        """Versión asíncrona de process_entity"""
        try:
            entity_id = str(entity.id)
        
            # Verificar si ya tenemos esta entidad
            if entity_id in self.entities:
                return None
            
            # Detectar tipo de entidad (mejorado para cubrir todos los tipos)
            entity_type = "unknown"
            
            # Canales de difusión
            if hasattr(entity, 'broadcast') and entity.broadcast:
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    # Esto es técnicamente un supergrupo con capacidades de difusión
                    entity_type = "megagroup"
                else:
                    entity_type = "channel"
            
            # Supergrupos
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                entity_type = "megagroup"
            
            # Grupos gigantes (otra variante de supergrupos)
            elif hasattr(entity, 'gigagroup') and entity.gigagroup:
                entity_type = "megagroup"
            
            # Foros (grupos con hilos de discusión)
            elif hasattr(entity, 'forum') and entity.forum:
                entity_type = "forum"
            
            # Grupos normales (no supergrupos)
            # Los grupos normales no tienen el atributo broadcast ni megagroup
            elif hasattr(entity, 'chat') or (hasattr(entity, 'title') and not hasattr(entity, 'broadcast')):
                entity_type = "group"
            
            # Extraer atributos básicos
            username = entity.username if hasattr(entity, 'username') else ""
            title = entity.title if hasattr(entity, 'title') else "Unknown"
            is_verified = entity.verified if hasattr(entity, 'verified') else False
            is_restricted = entity.restricted if hasattr(entity, 'restricted') else False
            invite_link = f"https://t.me/{username}" if username else ""
            
            # Verificar si es un grupo con capacidad de voz/video
            has_voice = False
            has_video = False
            if hasattr(entity, 'call_active') and entity.call_active:
                has_voice = True
                if hasattr(entity, 'call_not_empty') and entity.call_not_empty:
                    has_video = True
            
            # Obtener detalles completos (si es posible)
            members_count = 0
            description = ""
            last_message_date = ""
            topics_count = 0  # Para foros
            
            try:
                # Intentar diferentes métodos según el tipo de entidad
                if entity_type in ["channel", "megagroup", "forum"]:
                    full_entity = await self.client(GetFullChannelRequest(channel=entity))
                    members_count = full_entity.full_chat.participants_count
                    description = full_entity.full_chat.about or ""
                    
                    # Para foros, intentar obtener el número de temas
                    if entity_type == "forum" and hasattr(full_entity.full_chat, 'topics_count'):
                        topics_count = full_entity.full_chat.topics_count
                
                elif entity_type == "group":
                    # Para grupos normales usamos diferentes métodos
                    try:
                        full_chat = await self.client(GetFullChatRequest(chat_id=entity.id))
                        if hasattr(full_chat, 'participants_count'):
                            members_count = full_chat.participants_count
                        if hasattr(full_chat, 'about'):
                            description = full_chat.about or ""
                    except Exception:
                        # Si falla, intentar obtener participantes directamente
                        participants = await self.client.get_participants(entity)
                        members_count = len(participants)
                
                # Intentar obtener el último mensaje
                messages = await self.client.get_messages(entity, limit=1)
                if messages and len(messages) > 0:
                    last_message_date = messages[0].date.strftime("%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logger.warning(f"No se pudieron obtener detalles completos para entidad {entity_id}: {e}")
            
            # Detectar idioma y categoría
            detected_language = self.detect_language(description + " " + title)
            detected_category = self.detect_category(title, description)
            
            # Crear registro estructurado
            entity_data = {
                'entity_id': entity_id,
                'username': username,
                'title': title,
                'type': entity_type,
                'members_count': members_count,
                'invite_link': invite_link,
                'description': description,
                'is_public': True if username else False,
                'is_verified': is_verified,
                'is_restricted': is_restricted,
                'category': detected_category,
                'language': detected_language,
                'discovery_term': discovery_term,
                'discovery_date': time.strftime("%Y-%m-%d %H:%M:%S"),
                'last_message_date': last_message_date
            }
            
            # Guardar en memoria
            self.entities[entity_id] = entity_data
            
            # Filtrar solo campos válidos que existan en CSV_FIELDS
            csv_entity_data = {}
            for field in CSV_FIELDS:
                if field in entity_data:
                    csv_entity_data[field] = entity_data[field]
            
            # Escribir en CSV
            self.csv_writer.writerow(csv_entity_data)
            self.csv_file.flush()  # Asegurar que se escriba inmediatamente
            
            logger.info(f"Entidad guardada: {title} ({entity_id}) - {entity_type}, {members_count} miembros")
            
            return entity_data
        
        except Exception as e:
            logger.error(f"Error procesando entidad en async: {e}")
            traceback.print_exc()
            return None
    
    def search_by_term(self, term, limit=30):
        """Busca entidades por un término específico
        Busca entidades por un término específico.
        Versión sincrónica que sirve como envoltura para la implementación asíncrona.
        """
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_by_term_async(term, limit))
        except Exception as e:
            logger.error(f"Error en search_by_term: {e}")
            return []
        
    
    async def search_by_term_async(self, term, limit=30):
        """Versión asíncrona de search_by_term        
        Busca entidades por un término específico.        
        Args:
            term: Término de búsqueda
            limit: Número máximo de resultados            
        Returns:
            Lista de entidades encontradas
        """
        logger.info(f"Buscando con término (async): {term}")
        entities_found = []
        try:
            
            
            # Usar la misma función de SearchRequest pero con await
            results = await self.client(SearchRequest(
                q=term,
                limit=limit
            ))
            
            if hasattr(results, 'chats'):
                logger.info(f"Encontrados {len(results.chats)} resultados para '{term}'")
                
                for chat in results.chats:
                    # Llamar a la versión asíncrona de process_entity
                    if hasattr(self, 'process_entity_async'):
                        entity_data = await self.process_entity_async(chat, term)
                    else:
                        # Si no existe la versión asíncrona, usar la sincrónica
                        entity_data = self.process_entity(chat, term)
                    
                    if entity_data:
                        entities_found.append(entity_data)
            
            return entities_found
        
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
            return []
        
        except Exception as e:
            logger.error(f"Error en búsqueda asíncrona '{term}': {e}")
            return []
    
    def search_by_category(self, category):
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_by_category_async(category))
        except Exception as e:
            logger.error(f"Error en search_by_category: {e}")
            return []
            
    
    async def search_by_category_async(self, category):
        """Versión asíncrona de search_by_category"""
        """Busca entidades en una categoría específica"""
        if category not in SEARCH_TERMS:
            logger.warning(f"Categoría no soportada: {category}")
            return []
        
        all_entities = []
        terms = SEARCH_TERMS[category]
        
        for term in terms:
            try:
                logger.info(f"Buscando término: {term}")
                # Llamar a la versión asíncrona directamente con await
                results = await self.search_by_term_async(term, 20)
                all_entities.extend(results)
                # Usar asyncio.sleep en lugar de time.sleep
                await asyncio.sleep(random.uniform(2, 5))
            except Exception as e:
                logger.error(f"Error en búsqueda por categoría '{term}': {e}")
        
        return all_entities
    
    def search_all_categories(self):
        """Busca entidades en todas las categorías disponibles"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_all_categories_async())
        except Exception as e:
            logger.error(f"Error en search_all_categories: {e}")
            return []

    
    async def search_all_categories_async(self):
        """Versión asíncrona de search_all_categories"""
        try:
            all_entities = []
        
            for category in SEARCH_TERMS.keys():
                try:
                    logger.info(f"Buscando en categoría: {category}")
                    # Llamar a la versión asíncrona directamente con await
                    results = await self.search_by_category_async(category)
                    all_entities.extend(results)
                except Exception as e:
                    logger.error(f"Error en categoría {category}: {e}")
            
            return all_entities
        except Exception as e:
            logger.error(f"Error ")
        return []
    
    def search_by_language(self, language_code):
        """Busca entidades en un idioma específico"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_by_language_async(language_code))
        except Exception as e:
            logger.error(f"Error en search_by_language: {e}")
            return []
        
    
    async def search_by_language_async(self, language_code):
        """Versión asíncrona de search_by_language"""
        try:
            if language_code not in LANGUAGE_PATTERNS:
                logger.warning(f"Código de idioma no soportado: {language_code}")
                return []
            
            all_entities = []
            terms = LANGUAGE_PATTERNS[language_code]
            
            for term in terms:
                try:
                    results = self.search_by_term(term, 20)
                    all_entities.extend(results)
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(f"Error en búsqueda por idioma '{term}': {e}")
            
            return all_entities
       
        except Exception as e:
                logger.error(f"Error en búsqueda por idioma: {e}")
                return []
    
    def search_similar_entities(self, username):
        """Busca entidades similares a partir de una existente"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.search_similar_entities_async(username))
        except Exception as e:
            logger.error(f"Error en search_similar_entities: {e}")
            return []

        
    
    async def search_similar_entities_async(self, username):
        """Versión asíncrona de search_similar_entities"""
        try:
            entity = self.client.get_entity(f"@{username}")
            title_terms = entity.title.lower().split()
            
            similar_entities = []
            
            # Usar términos del título como búsqueda
            for term in title_terms:
                if len(term) > 4:  # Solo términos suficientemente largos
                    results = self.search_by_term(term, 10)
                    similar_entities.extend(results)
                    time.sleep(random.uniform(1, 3))
            
            return similar_entities
        
        
        except Exception as e:
            logger.error(f"Error buscando similares a @{username}: {e}")
            return []
        
    
    def scan_my_dialogs(self):
        """Escanea los diálogos donde el usuario ya es miembro"""
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.scan_my_dialogs_async())
        except Exception as e:
            logger.error(f"Error en scan_my_dialogs")
            return []
        
    
    async def scan_my_dialogs_async(self):
        """Versión asíncrona de scan_my_dialogs"""
        logger.info("Escaneando diálogos existentes...")
        
        try:
            # Obtener todos los diálogos
            dialogs = []
            chunk_size = 200
            last_date = None
            
            while True:
                result = await self.client(GetDialogsRequest(
                    offset_date=last_date,
                    offset_id=0,
                    offset_peer=InputPeerEmpty(),
                    limit=chunk_size,
                    hash=0
                ))
                
                if not result.dialogs:
                    break
                
                dialogs.extend(result.dialogs)
                
                # Verificar si hay más diálogos
                if len(result.dialogs) < chunk_size:
                    break
                
                # Actualizar offset para la próxima solicitud
                last_date = result.messages[-1].date
                
                # Pausa para evitar límites
                await asyncio.sleep()
                # time.sleep(1)
            
            logger.info(f"Encontrados {len(dialogs)} diálogos")
            
            # Filtrar solo canales y grupos 
            entities_count = 0
            existing_count = 0
            entity_types = {"channel": 0, "megagroup": 0, "group": 0, "forum": 0, "unknown": 0}
            # Para depuración
            dialog_types = {}
            for dialog in dialogs:
                if dialog.peer:
                    try:
                        peer_type = dialog.peer.__class__.__name__
                        dialog_types[peer_type] = dialog_types.get(peer_type, 0) + 1
                        # Obtener la entidad completa
                        entity = await self.client.get_entity(dialog.peer)
                        
                         # Verificar si la entidad ya existe
                        entity_id = str(entity.id)
                        if entity_id in self.entities:
                            existing_count += 1
                            # print(f"Entidad {entity_id} ya existe (saltando)")
                            continue
                        # Procesar la entidad
                        entity_data = await self.process_entity_async(entity, "my_dialogs") # self.process_entity(entity, "my_dialogs")
                        if entity_data:
                            entities_count += 1
                            entity_type = entity_data.get('type', 'unknown')
                            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
                    except Exception as e:
                        logger.warning(f"Error procesando diálogo: {e}")
            print(f"Entidades existentes (no procesadas): {existing_count}")
            print(f"Nuevas entidades procesadas: {entities_count}")
            # Mostrar resumen
            print("\n=== RESUMEN DE ESCANEO DE DIÁLOGOS ===")
            print(f"Total de entidades procesadas: {entities_count}")
            for tipo, count in entity_types.items():
                if count > 0:
                    print(f"- {tipo}: {count}")
                    
            logger.info(f"Se procesaron {entities_count} entidades de tus diálogos")
            return entities_count
        
        
        except Exception as e:
            logger.error(f"Error escaneando diálogos: {e}")
            traceback.print_exc()
            return 0
    
    def scan_for_all_entity_types(self):
        """Escanea activamente buscando todos los tipos de entidades"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.scan_for_all_entity_types_async())
        
    
    async def scan_for_all_entity_types_async(self):
        """Versión asíncrona de scan_for_all_entity_types"""
        logger.info("Iniciando escaneo exhaustivo de todos los tipos de entidades...")
        
        total_found = {
            "channel": 0,
            "megagroup": 0,
            "forum": 0,
            "group": 0,
            "unknown": 0
        }
        
        try:
            # 1. Buscar en diálogos actuales (incluye todos los tipos)
            logger.info("Escaneando diálogos existentes...")
            dialogs = []
            
            result = await self.client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=100,
                hash=0
            ))
            
            dialogs.extend(result.dialogs)
            
            # Procesar cada diálogo encontrado
            for dialog in dialogs:
                try:
                    if dialog.peer:
                        # Obtener la entidad completa
                        entity = await self.client.get_entity(dialog.peer)
                        
                        # Procesar la entidad
                        entity_data = self.process_entity(entity, "dialog_scan")
                        
                        if entity_data:
                            entity_type = entity_data.get('type', 'unknown')
                            total_found[entity_type] = total_found.get(entity_type, 0) + 1
                except Exception as e:
                    logger.warning(f"Error procesando diálogo: {e}")
            
            # 2. Búsqueda específica de términos para diferentes tipos de entidades
            general_terms = [
                "group", "community", "chat", "discussion", "forum", "channel",
                "talk", "debate", "conversations", "members", "topic"
            ]
            
            for term in general_terms:
                try:
                    logger.info(f"Buscando término general: {term}")
                    results = await self.client(SearchRequest(
                        q=term,
                        limit=50
                    ))
                    
                    if hasattr(results, 'chats'):
                        for chat in results.chats:
                            entity_data = self.process_entity(chat, term)
                            if entity_data:
                                entity_type = entity_data.get('type', 'unknown')
                                total_found[entity_type] = total_found.get(entity_type, 0) + 1
                    
                    # Pausa para evitar límites
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(f"Error en búsqueda del término '{term}': {e}")
            
            # 3. Búsqueda específica de foros
            forum_terms = ["forum", "topics", "threads", "discussion"]
            for term in forum_terms:
                try:
                    logger.info(f"Buscando foros con término: {term}")
                    results = await self.client(SearchRequest(
                        q=term,
                        limit=30
                    ))
                    
                    if hasattr(results, 'chats'):
                        for chat in results.chats:
                            # Verificar si es un foro
                            if hasattr(chat, 'forum') and chat.forum:
                                entity_data = self.process_entity(chat, "forum_search")
                                if entity_data:
                                    total_found["forum"] = total_found.get("forum", 0) + 1
                    
                    # Pausa para evitar límites
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    logger.error(f"Error en búsqueda de foros '{term}': {e}")
            
            # Resumen de resultados
            logger.info("Escaneo exhaustivo completado")
            for entity_type, count in total_found.items():
                if count > 0:
                    logger.info(f"Entidades tipo {entity_type}: {count}")
            
            # Imprimir resumen para el usuario
            print("\n=== RESUMEN DE ESCANEO EXHAUSTIVO ===")
            print(f"Canales (broadcast): {total_found['channel']}")
            print(f"Supergrupos: {total_found['megagroup']}")
            print(f"Foros de discusión: {total_found['forum']}")
            print(f"Grupos normales: {total_found['group']}")
            if total_found['unknown'] > 0:
                print(f"Entidades no identificadas: {total_found['unknown']}")
            print(f"Total de entidades encontradas: {sum(total_found.values())}")
            
            return total_found
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
            return []
        
        except Exception as e:
            logger.error(f"Error en escaneo exhaustivo: {e}")
            traceback.print_exc()
            return total_found
    
    def join_entity(self, username):
        """Intenta unirse a una entidad por su nombre de usuario"""
        try:
            loop = asyncio.get_event_loop()
            
            # Ejecutar la versión asíncrona
            if loop.is_running():
                # Si el loop está en ejecución, necesitamos manejar esto de otra manera
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(self.join_entity_async(username))
                    finally:
                        new_loop.close()
                
                # Ejecutar en un nuevo thread para evitar el error "loop already running"
                import threading
                thread = threading.Thread(target=run_in_new_loop)
                thread.start()
                thread.join()
                
                # No podemos obtener el resultado directamente del thread
                # Asumiremos éxito si no hay excepciones, pero esto no es ideal
                return True
            else:
                # Si el loop no está en ejecución, podemos usar run_until_complete
                return loop.run_until_complete(self.join_entity_async(username))
        except Exception as e:
            logger.error(f"Error en join_entity: {e}")
            print(f"Error al unirse: {str(e)}")
            return False
        
    
    async def join_entity_async(self, username):
        """Versión asíncrona mejorada de join_entity que verifica el resultado"""
        try:
            print(f"Intentando unirse a @{username}...")
            
            # Verificar si ya somos miembros
            try:
                entity = await self.client.get_entity(f"@{username}")
                
                # Verificar si ya somos miembros
                dialogs = await self.client.get_dialogs(limit=500)
                already_member = False
                
                for dialog in dialogs:
                    if hasattr(dialog.entity, 'username') and dialog.entity.username == username:
                        print(f"¡Ya eres miembro de @{username}!")
                        already_member = True
                        return True  # Ya somos miembros, no hay que unirse
            except Exception as e:
                print(f"Aviso: No se pudo verificar membresía previa: {e}")
            
            # Intentar unirse
            result = await self.client(JoinChannelRequest(username))
            
            # Verificar que el resultado fue exitoso
            if result and hasattr(result, 'chats') and len(result.chats) > 0:
                logger.info(f"Unido exitosamente a @{username}")
                print(f"¡Te has unido exitosamente a @{username}!")
                
                # Esperar un momento para que Telegram procese la unión
                await asyncio.sleep(3)
                
                # Verificar que ahora realmente somos miembros
                try:
                    # Intentar obtener diálogos nuevamente
                    new_dialogs = await self.client.get_dialogs(limit=10, archived=False)
                    verification_success = False
                    
                    # Verificar si ahora aparece en nuestros diálogos
                    for dialog in new_dialogs:
                        if hasattr(dialog.entity, 'username') and dialog.entity.username == username:
                            print(f"✓ Verificado: Ahora eres miembro de @{username}")
                            verification_success = True
                            break
                    
                    if not verification_success:
                        print(f"⚠️ Aviso: La unión a @{username} parece haberse completado, pero no aparece en tus diálogos recientes.")
                        print("Esto puede deberse a la paginación de diálogos o a una demora en Telegram.")
                        print("Verifica manualmente en tu aplicación de Telegram.")
                except Exception as ve:
                    print(f"⚠️ Aviso: No se pudo verificar la membresía después de unirse: {ve}")
                
                return True
                
            else:
                logger.warning(f"Respuesta inesperada al intentar unirse a @{username}")
                print(f"⚠️ Aviso: La respuesta de Telegram no confirma la unión a @{username}")
                print("Verifica manualmente en tu aplicación de Telegram.")
                return False
                
        except ChannelPrivateError:
            logger.warning(f"@{username} es privado y requiere invitación")
            print(f"No se pudo unir: @{username} es privado y requiere invitación")
            return False
        except Exception as e:
            logger.error(f"Error al unirse a @{username}: {e}")
            print(f"Error al unirse a @{username}: {str(e)}")
            return False
    
    def explore_messages(self, username, limit=10):
        """Explora los mensajes recientes de una entidad"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.explore_messages_async(username, limit))
        
    
    async def explore_messages_async(self, username, limit=10):
        """Versión asíncrona de explore_messages"""
        try:
            entity = await self.client.get_entity(f"@{username}")
            messages = await self.client.get_messages(entity, limit=limit)
            
            if not messages:
                print("No se encontraron mensajes recientes.")
                return
            
            print(f"\n=== MENSAJES RECIENTES DE @{username} ===")
            for i, msg in enumerate(messages, 1):
                date = msg.date.strftime("%d/%m/%Y %H:%M")
                content = msg.message if msg.message else "[Contenido multimedia o sin texto]"
                if len(content) > 100:
                    content = content[:97] + "..."
                print(f"{i}. [{date}] {content}")
            print("=====================================\n")
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
        except Exception as e:
            logger.error(f"Error explorando mensajes de @{username}: {e}")
            print(f"Error: {str(e)}")
    
    ############################################
    # SECCIÓN 4: EXTRACCIÓN BÁSICA DE MIEMBROS #
    ############################################
    
    def process_member(self, user, entity_id, entity_title, is_admin=False, is_forwarded=False, is_probable=False, is_from_linked=False):
        """Procesa y guarda la información de un miembro"""
        try:
            user_id = str(user.id)
            
            # Verificar si ya tenemos este miembro para esta entidad
            key = f"{user_id}_{entity_id}"
            if key in self.members:
                return False
            
            # Extraer atributos del usuario
            username = user.username or ""
            first_name = user.first_name or ""
            last_name = user.last_name or ""
            access_hash = user.access_hash if hasattr(user, 'access_hash') else 0
            is_bot = user.bot if hasattr(user, 'bot') else False
            
            # Determinar rol y tipo de participación
            role = "regular"
            if is_admin:
                role = "admin"
            elif is_bot:
                role = "bot"
            
            participation_type = "active"
            if is_forwarded:
                participation_type = "forwarded"
            
            # Crear registro estructurado
            member_data = {
                'user_id': user_id,
                'access_hash': access_hash,
                'username': username,
                'first_name': first_name,
                'last_name': last_name,
                'entity_id': entity_id,
                'entity_title': entity_title,
                'is_bot': is_bot,
                'is_admin': is_admin,
                'role': role,
                'participation_type': participation_type,
                'extraction_date': time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Guardar en memoria
            self.members[key] = member_data
            
            # Escribir en CSV
            self.member_csv_writer.writerow(member_data)
            self.member_csv_file.flush()  # Asegurar que se escriba inmediatamente
            
            return True
            
        except Exception as e:
            logger.error(f"Error procesando miembro: {e}")
            return False
    
    def extract_members_from_entity(self, entity_id_or_obj, limit=None):
        """Extrae miembros de una entidad específica"""
        try:
            # Determinar si tenemos una entidad o un ID
            if isinstance(entity_id_or_obj, str):
                entity_id = entity_id_or_obj
                if entity_id in self.entities:
                    entity_data = self.entities[entity_id]
                    username = entity_data.get('username', '')
                    title = entity_data.get('title', 'Entidad desconocida')
                    entity = self.client.get_entity(int(entity_id))
                else:
                    logger.error(f"Entidad con ID {entity_id} no encontrada")
                    return 0
            else:
                entity = entity_id_or_obj
                entity_id = str(entity.id)
                title = entity.title if hasattr(entity, 'title') else "Entidad desconocida"
            
            print(f"\nExtrayendo miembros de: {title}")
            logger.info(f"Iniciando extracción de miembros para {title} ({entity_id})")
            
            # Obtener participantes con manejo correcto de la corutina
            try:
                # PUNTO CLAVE: Aquí está el problema principal
                # La función client.get_participants() devuelve una corutina que debe ser esperada
                
                # SOLUCIÓN: Definir función asíncrona y ejecutarla apropiadamente 
                async def get_members_and_admins():
                    from telethon.tl.types import ChannelParticipantsAdmins
                    
                    # Obtener todos los participantes
                    participants = await self.client.get_participants(entity, limit=limit)
                    
                    # Obtener administradores
                    admin_ids = set()
                    try:
                        admins = await self.client.get_participants(
                            entity, filter=ChannelParticipantsAdmins()
                        )
                        admin_ids = {admin.id for admin in admins}
                    except Exception as e:
                        logger.warning(f"Error obteniendo administradores: {e}")
                    
                    return participants, admin_ids
                
                # Ejecutar la función asíncrona en el event loop
                loop = asyncio.get_event_loop()
                members, admin_ids = loop.run_until_complete(get_members_and_admins())
                
                # Procesar los miembros
                logger.info(f"Se obtuvieron {len(members)} miembros")
                
                processed_count = 0
                regular_members = 0
                admin_members = 0
                bot_members = 0
                
                for member in members:
                    is_admin = member.id in admin_ids
                    is_bot = member.bot if hasattr(member, 'bot') else False
                    
                    if self.process_member(member, entity_id, title, is_admin):
                        processed_count += 1
                        
                        if is_admin:
                            admin_members += 1
                        elif is_bot:
                            bot_members += 1
                        else:
                            regular_members += 1
                
                logger.info(f"Extracción completada. Total procesados: {processed_count}")
                print(f"\nExtracción completada:")
                print(f"- Miembros regulares: {regular_members}")
                print(f"- Administradores: {admin_members}")
                print(f"- Bots: {bot_members}")
                print(f"- Total: {processed_count}")
                
                return processed_count
                
            except Exception as e:
                logger.error(f"Error extrayendo miembros: {e}")
                print(f"Error: {e}")
                return 0
        except Exception as e:
            logger.error(f"Error general: {e}")
            print(f"Error general: {e}")
            return 0
        
    
    async def extract_members_from_entity_async(self, entity_id_or_obj, limit=None):
        """Versión asíncrona de extract_members_from_entity"""
        try:
            # Determinar si tenemos una entidad o un ID
            if isinstance(entity_id_or_obj, str):
                entity_id = entity_id_or_obj
                if entity_id in self.entities:
                    entity_data = self.entities[entity_id]
                    username = entity_data.get('username', '')
                    title = entity_data.get('title', 'Entidad desconocida')
                    entity = await self.client.get_entity(int(entity_id))
                else:
                    logger.error(f"Entidad con ID {entity_id} no encontrada")
                    return 0
            else:
                entity = entity_id_or_obj
                entity_id = str(entity.id)
                title = entity.title if hasattr(entity, 'title') else "Entidad desconocida"
            
            print(f"\nExtrayendo miembros de: {title}")
            logger.info(f"Iniciando extracción de miembros para {title} ({entity_id})")
            
            # Obtener participantes
            try:
                # IMPORTANTE: Usar await correctamente con get_participants
                members = await self.client.get_participants(entity, limit=limit)
                logger.info(f"Se obtuvieron {len(members)} miembros")
                
                # Obtener administradores para marcarlos
                admins = []
                try:
                    from telethon.tl.types import ChannelParticipantsAdmins
                    admin_participants = await self.client.get_participants(
                        entity, filter=ChannelParticipantsAdmins()
                    )
                    for admin in admin_participants:
                        admins.append(admin.id)
                    logger.info(f"Se identificaron {len(admins)} administradores")
                except Exception as e:
                    logger.warning(f"Error obteniendo administradores: {e}")
                
                # Procesar cada miembro
                processed_count = 0
                regular_members = 0
                admin_members = 0
                bot_members = 0
                
                for member in members:
                    is_admin = member.id in admins
                    
                    # Determinar si es un bot
                    is_bot = member.bot if hasattr(member, 'bot') else False
                    
                    if self.process_member(member, entity_id, title, is_admin):
                        processed_count += 1
                        
                        if is_admin:
                            admin_members += 1
                        elif is_bot:
                            bot_members += 1
                        else:
                            regular_members += 1
                
                logger.info(f"Extracción completada. Total procesados: {processed_count}")
                print(f"\nExtracción completada:")
                print(f"- Miembros regulares: {regular_members}")
                print(f"- Administradores: {admin_members}")
                print(f"- Bots: {bot_members}")
                print(f"- Total: {processed_count}")
                
                return processed_count
                
            except Exception as e:
                logger.error(f"Error extrayendo miembros: {e}")
                print(f"Error: {e}")
                return 0
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep        
        except Exception as e:
            logger.error(f"Error en extract_members_from_entity: {e}")
            traceback.print_exc()
            return 0
    
    def extract_active_participants(self, entity_id, message_limit=100):
        """Extrae participantes activos analizando mensajes"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_active_participants_async(entity_id, message_limit))
        
        
    
    async def extract_active_participants_async(self, entity_id, message_limit=100):
        """Versión asíncrona de extract_active_participants
            Esta función es útil cuando no se tiene acceso a la lista completa de miembros.
        
        Args:
            entity_id: ID de la entidad (grupo o canal)
            message_limit: Cantidad de mensajes recientes a analizar
            
        Returns:
            Número de participantes activos extraídos
        """
        if not entity_id in self.entities:
            logger.warning(f"Entidad {entity_id} no encontrada en la base de datos")
            return 0
        
        entity_data = self.entities[entity_id]
        title = entity_data.get('title', 'Unknown')
        entity_type = entity_data.get('type', 'unknown')
        username = entity_data.get('username', '')
        
        logger.info(f"Analizando participantes activos en: {title} ({entity_id}) - {entity_type}")
        print(f"Analizando los últimos {message_limit} mensajes para identificar participantes activos...")
        
        try:
            # Obtener la entidad
            if username:
                entity = await self.client.get_entity(f"@{username}")
            else:
                entity = await self.client.get_entity(int(entity_id))
            
            # Obtener mensajes recientes
            messages = await self.client.get_messages(entity, limit=message_limit)
            logger.info(f"Se obtuvieron {len(messages)} mensajes recientes de {title}")
            
            # Recopilar información de los remitentes únicos
            active_users = set()
            forwarded_from = set()
            active_participants_extracted = 0
            
            # Análisis de mensajes y participantes
            for msg in messages:
                # Procesar el remitente del mensaje
                if msg.sender_id and hasattr(msg.sender_id, 'user_id'):
                    user_id = msg.sender_id.user_id
                    if user_id not in active_users:
                        active_users.add(user_id)
                        try:
                            # Obtener información completa del usuario
                            user = self.client.get_entity(user_id)
                            self.process_member(user, entity_id, title, False)
                            active_participants_extracted += 1
                        except Exception as e:
                            logger.warning(f"No se pudo obtener información del usuario {user_id}: {e}")
                
                # Procesar mensajes reenviados
                if hasattr(msg, 'forward') and msg.forward:
                    if hasattr(msg.forward.sender_id, 'user_id'):
                        fwd_user_id = msg.forward.sender_id.user_id
                        if fwd_user_id not in forwarded_from:
                            forwarded_from.add(fwd_user_id)
                            try:
                                # Intentar obtener información del remitente original
                                fwd_user = self.client.get_entity(fwd_user_id)
                                # Guardarlo con una nota especial como "forwarded_from"
                                self.process_member(fwd_user, entity_id, title, False, is_forwarded=True)
                                active_participants_extracted += 1
                            except Exception as e:
                                logger.warning(f"No se pudo obtener información del remitente original {fwd_user_id}: {e}")
            
            # Intentar obtener administradores (que suele ser posible incluso sin permisos especiales)
            try:
                admins = self.client.get_participants(entity, filter=ChannelParticipantsAdmins())
                for admin in admins:
                    if self.process_member(admin, entity_id, title, True):
                        active_participants_extracted += 1
                logger.info(f"Se identificaron {len(admins)} administradores en {title}")
            except Exception as e:
                logger.warning(f"No se pudieron obtener administradores de {title}: {e}")
            
            # Estadísticas de la extracción
            logger.info(f"Análisis completado para {title}")
            logger.info(f"Participantes activos encontrados: {len(active_users)}")
            logger.info(f"Remitentes originales de reenvíos: {len(forwarded_from)}")
            logger.info(f"Total de participantes procesados: {active_participants_extracted}")
            
            print(f"Se encontraron {len(active_users)} participantes activos en los mensajes")
            print(f"Se identificaron {len(forwarded_from)} remitentes originales de reenvíos")
            print(f"Total de participantes guardados: {active_participants_extracted}")
            
            return active_participants_extracted
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
        except Exception as e:
            logger.error(f"Error analizando participantes activos en {title}: {e}")
            print(f"Error: {str(e)}")
            return 0
    
    def get_regular_members(self, entity_id, limit=100):
        """Intenta obtener miembros regulares usando iteradores específicos"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.get_regular_members_async(entity_id,limit))
        
    
    async def get_regular_members_async(self, entity_id, limit=100):
        """Versión asíncrona de get_regular_members"""
        try:
            entity = self.client.get_entity(int(entity_id))
            
            # Intentar obtener participantes recientes
            # Esta clase en particular a veces funciona mejor que otras
            from telethon.tl.types import ChannelParticipantsRecent
            
            users = []
            
            # Usar get_participants con offset para paginar resultados
            offset = 0
            while len(users) < limit:
                batch = self.client.get_participants(
                    entity,
                    filter=ChannelParticipantsRecent(),
                    offset=offset,
                    limit=100
                )
                
                if not batch:
                    break
                    
                # Filtrar solo usuarios regulares
                regular_users = [user for user in batch if not user.bot and not user.admin_rights]
                users.extend(regular_users)
                
                offset += len(batch)
                time.sleep(2)  # Pausa respetuosa
                
            return users[:limit]
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
        except Exception as e:
            logger.error(f"Error obteniendo miembros regulares: {e}")
            traceback.print_exc()
            return []
    
    def find_users_from_mentions(self, entity_id, message_limit=200):
        """Descubre usuarios a través de menciones en mensajes"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.find_users_from_mentions_async(entity_id, message_limit))
        
    
    async def find_users_from_mentions_async(self, entity_id, message_limit=200):
        """Versión asíncrona de find_users_from_mentions"""
        try:
            entity = await self.client.get_entity(int(entity_id))
            messages = await self.client.get_messages(entity, limit=message_limit)
            
            mentioned_users = set()
            
            for msg in messages:
                # Analizar menciones en el texto
                if msg.entities:
                    for entity in msg.entities:
                        if hasattr(entity, 'user_id'):
                            try:
                                user = await self.client.get_entity(entity.user_id)
                                if not user.bot and not hasattr(user, 'admin_rights'):
                                    user_key = f"{user.id}_{entity_id}"
                                    # Procesar y guardar el usuario si aún no existe
                                    if user_key not in self.members:
                                        self.process_member(user, str(entity_id), entity.title, False)
                                        mentioned_users.add(user.id)
                            except Exception as e:
                                logger.warning(f"No se pudo obtener usuario mencionado: {e}")
                
                # Pausa respetuosa
                time.sleep(0.5)
                    
            return len(mentioned_users)
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
        except Exception as e:
            logger.error(f"Error buscando menciones: {e}")
            return 0
    
    def discover_regular_users(self, entity_id, max_users=200):
        """Método híbrido para descubrir usuarios regulares"""
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.discover_regular_users_async(entity_id, max_users))
        
    
    async def discover_regular_users_async(self, entity_id, max_users=200):
        """Versión asíncrona de discover_regular_users"""
        try:
            users_found = set()
            entity_title = self.entities.get(entity_id, {}).get('title', 'Entidad desconocida')
            
            print(f"\nBuscando usuarios regulares en: {entity_title}")
            print("Este proceso puede tardar varios minutos. Por favor espera...")
            
            # 1. Intentar métodos directos primero (ordenados del más al menos efectivo)
            methods = [
                {"name": "Participantes recientes", "func": self.get_regular_members},
                {"name": "Análisis de mensajes", "func": self.extract_active_participants},
                {"name": "Análisis de menciones", "func": self.find_users_from_mentions}
            ]
            
            for method in methods:
                if len(users_found) >= max_users:
                    break
                    
                print(f"\nProbando método: {method['name']}...")
                try:
                    # Cada método debería actualizar self.members
                    result = method["func"](entity_id)
                    
                    # Contar cuántos nuevos usuarios encontramos
                    new_count = 0
                    for key, member in self.members.items():
                        if member['entity_id'] == entity_id and not member['is_bot'] and member['role'] == 'regular':
                            if member['user_id'] not in users_found:
                                users_found.add(member['user_id'])
                                new_count += 1
                    
                    print(f"  → {new_count} nuevos usuarios encontrados con este método")
                    
                    # Pausa entre métodos
                    time.sleep(3)
                    
                except Exception as e:
                    print(f"  → Error con este método: {e}")
            
            # Resumen final
            print(f"\nBúsqueda completada. Se encontraron {len(users_found)} usuarios regulares únicos.")
            return len(users_found)
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"Límite de API alcanzado. Esperando {wait_time} segundos...")
            await asyncio.sleep(wait_time)  # Usar asyncio.sleep en lugar de time.sleep
            
        except Exception as e:
            logger.error(f"Error en descubrimiento de usuarios: {e}")
            traceback.print_exc()
            return 0
    
    ############################################
    # SECCIÓN 5: MÉTODOS AVANZADOS DE EXTRACCIÓN #
    ############################################

    # 5.1 MÉTODOS COMPREHENSIVOS UNIFICADOS

    def extract_users_from_messages_comprehensive(self, entity_id, depth=5, messages_per_batch=100):
        """
        Analiza mensajes exhaustivamente para extraer usuarios combinando todas las técnicas.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
            depth: Número de lotes de mensajes a analizar
            messages_per_batch: Número de mensajes por lote
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_messages_comprehensive_async(entity_id, depth, messages_per_batch))

    async def extract_users_from_messages_comprehensive_async(self, entity_id, depth=5, messages_per_batch=100):
        """
        Analiza mensajes exhaustivamente para extraer usuarios combinando todas las técnicas.
        Fusiona extract_users_from_historic_messages y extract_messages_and_users en un único método robusto.
        
        Args:
            entity_id: ID de la entidad
            depth: Número de lotes de mensajes a analizar
            messages_per_batch: Número de mensajes por lote
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"Analizando historial profundo de mensajes para {entity_title}")
            print(f"Profundidad configurada: {depth} lotes de {messages_per_batch} mensajes cada uno")
            
            users_found = []
            user_ids_found = set()  # Para seguimiento
            
            # Función auxiliar para procesar usuarios de forma segura
            def process_user_safely(user, is_admin=False, is_forwarded=False, source=""):
                # Verificaciones comunes
                if not user:
                    return False
                    
                # Verificar si es un canal en lugar de un usuario
                if hasattr(user, 'broadcast') or hasattr(user, 'megagroup') or not hasattr(user, 'first_name'):
                    return False
                    
                if hasattr(user, 'bot') and user.bot:
                    return False
                    
                if user.id in user_ids_found:
                    return False
                
                try:
                    # Procesar el usuario
                    self.process_member(user, entity_id, entity_title, is_admin, is_forwarded)
                    users_found.append(user)
                    user_ids_found.add(user.id)
                    
                    if source:
                        username_display = f"@{user.username}" if hasattr(user, 'username') and user.username else "sin username"
                        print(f"Usuario encontrado vía {source}: {user.first_name} ({username_display})")
                    
                    return True
                except Exception as e:
                    print(f"Error procesando usuario {getattr(user, 'id', 'desconocido')}: {e}")
                    return False
            
            # FASE 1: Obtener administradores primero (suele funcionar incluso sin permisos)
            print("Intentando obtener administradores primero...")
            try:
                from telethon.tl.types import ChannelParticipantsAdmins
                admins = await self.client.get_participants(entity, filter=ChannelParticipantsAdmins())
                
                for admin in admins:
                    if process_user_safely(admin, is_admin=True, source="administrador"):
                        pass  # Ya registrado en process_user_safely
            except Exception as e:
                print(f"No se pudieron obtener administradores: {e}")
            
            # FASE 2: Analizar mensajes en lotes históricos
            offset_id = 0
            processed_batch_count = 0
            
            for batch in range(depth):
                try:
                    print(f"Analizando lote {batch+1}/{depth} de mensajes...")
                    
                    # Obtener mensajes con offsets
                    messages = await self.client.get_messages(
                        entity, 
                        limit=messages_per_batch,
                        offset_id=offset_id
                    )
                    
                    if not messages:
                        print("No hay más mensajes para analizar.")
                        break
                    
                    # Actualizar offset para el próximo lote
                    offset_id = messages[-1].id
                    processed_batch_count += 1
                    processed_count = 0
                    
                    # Analizar cada mensaje profundamente
                    for msg in messages:
                        users_in_message = 0
                        
                        # 1. Verificar remitente del mensaje
                        try:
                            if msg.sender_id and not isinstance(msg.sender_id, type):
                                from telethon.tl.types import PeerChannel
                                if not isinstance(msg.sender_id, PeerChannel):
                                    try:
                                        user = await self.client.get_entity(msg.sender_id)
                                        if process_user_safely(user, source="remitente de mensaje"):
                                            users_in_message += 1
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        
                        # 2. Verificar autor del post (para canales)
                        try:
                            if hasattr(msg, 'post_author') and msg.post_author:
                                # Buscar usuarios con este nombre
                                try:
                                    results = await self.client(
                                        functions.contacts.SearchRequest(
                                            q=msg.post_author,
                                            limit=5
                                        )
                                    )
                                    
                                    for user in results.users:
                                        if user.first_name == msg.post_author or user.last_name == msg.post_author:
                                            if process_user_safely(user, source="autor de post"):
                                                users_in_message += 1
                                                print(f"Autor de post encontrado: {user.first_name}")
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        
                        # 3. Verificar mensajes reenviados
                        try:
                            if hasattr(msg, 'forward') and msg.forward:
                                # Si tenemos el ID del remitente original
                                if hasattr(msg.forward, 'sender_id') and msg.forward.sender_id:
                                    from telethon.tl.types import PeerChannel
                                    if not isinstance(msg.forward.sender_id, PeerChannel):
                                        try:
                                            original_sender = await self.client.get_entity(msg.forward.sender_id)
                                            if process_user_safely(original_sender, is_forwarded=True, source="reenvío"):
                                                users_in_message += 1
                                        except Exception:
                                            pass
                                
                                # Si tenemos el nombre del remitente original
                                elif hasattr(msg.forward, 'from_name') and msg.forward.from_name:
                                    try:
                                        # Buscar usuarios con este nombre
                                        results = await self.client(
                                            functions.contacts.SearchRequest(
                                                q=msg.forward.from_name,
                                                limit=5
                                            )
                                        )
                                        
                                        for user in results.users:
                                            if user.first_name == msg.forward.from_name or user.last_name == msg.forward.from_name:
                                                if process_user_safely(user, is_forwarded=True, source="reenvío por nombre"):
                                                    users_in_message += 1
                                                    break  # Solo el primer match
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        
                        # 4. Verificar TODOS los tipos de entidades en el mensaje
                        try:
                            if hasattr(msg, 'entities') and msg.entities:
                                for entity_in_msg in msg.entities:
                                    # Caso 1: Entidad tiene user_id (menciones de usuario directas)
                                    if hasattr(entity_in_msg, 'user_id') and entity_in_msg.user_id:
                                        try:
                                            user = await self.client.get_entity(entity_in_msg.user_id)
                                            if process_user_safely(user, source="mención directa"):
                                                users_in_message += 1
                                        except Exception:
                                            pass
                                    
                                    # Caso 2: Menciones estándar "@username"
                                    elif hasattr(entity_in_msg, 'offset') and hasattr(entity_in_msg, 'length'):
                                        try:
                                            entity_class_name = entity_in_msg.__class__.__name__
                                            if entity_class_name == 'MessageEntityMention' and msg.text:
                                                start = entity_in_msg.offset
                                                end = entity_in_msg.offset + entity_in_msg.length
                                                
                                                if 0 <= start < len(msg.text) and end <= len(msg.text):
                                                    mention = msg.text[start:end]
                                                    
                                                    if mention.startswith('@'):
                                                        username = mention[1:]
                                                        try:
                                                            user = await self.client.get_entity(username)
                                                            if process_user_safely(user, source="mención @username"):
                                                                users_in_message += 1
                                                        except Exception:
                                                            pass
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        
                        # Si encontramos usuarios en este mensaje, contarlos
                        if users_in_message > 0:
                            processed_count += 1
                    
                    print(f"Análisis del lote {batch+1} completado. Se encontraron usuarios en {processed_count} mensajes.")
                    
                    # Breve pausa entre lotes para evitar rate limits
                    await asyncio.sleep(2)
                    
                except Exception as e:
                    print(f"Error procesando lote {batch+1}: {e}")
                    # Continuar con el siguiente lote en lugar de terminar
                    continue
            
            # FASE 3: Analizar descripciones y firmas
            try:
                print("\nVerificando información adicional del canal...")
                
                # Intentar obtener descripción completa y otros metadatos
                full_entity = await self.client(functions.channels.GetFullChannelRequest(channel=entity))
                
                if hasattr(full_entity, 'full_chat') and hasattr(full_entity.full_chat, 'about'):
                    about = full_entity.full_chat.about
                    
                    if about:
                        print("Analizando descripción del canal...")
                        
                        # Buscar menciones en la descripción (formato @username)
                        mentions = re.findall(r'@(\w+)', about)
                        
                        for username in mentions:
                            try:
                                user = await self.client.get_entity(username)
                                if process_user_safely(user, is_admin=True, source="descripción"):
                                    pass  # Ya registrado en process_user_safely
                            except Exception:
                                pass
                        
                        # Buscar patrones típicos que podrían indicar administradores/contactos
                        patterns = [
                            r'admin[s]?:?\s+@(\w+)',
                            r'owner:?\s+@(\w+)',
                            r'contact:?\s+@(\w+)',
                            r'support:?\s+@(\w+)',
                            r'by:?\s+@(\w+)',
                            r'created\s+by:?\s+@(\w+)',
                            r'founder:?\s+@(\w+)',
                            r'admin[s]?:?\s+@(\w+)',
                            r'moderator[s]?:?\s+@(\w+)',
                            r'mod[s]?:?\s+@(\w+)',
                            r'manager[s]?:?\s+@(\w+)',
                            r'ceo:?\s+@(\w+)',
                            r'creador:?\s+@(\w+)',
                            r'propietario:?\s+@(\w+)',
                            r'dueño:?\s+@(\w+)',
                            r'developer:?\s+@(\w+)',
                            r'desarrollador:?\s+@(\w+)',
                            r'programador:?\s+@(\w+)',
                            r'colaborador:?\s+@(\w+)',
                            r'colabora:?\s+@(\w+)',
                            r'autor:?\s+@(\w+)',
                            r'ayuda:?\s+@(\w+)',
                            r'soporte:?\s+@(\w+)',
                            r'contact[o]?:?\s+@(\w+)',
                            r'escribir\s+a:?\s+@(\w+)',
                            r'write\s+to:?\s+@(\w+)',
                            r'help:?\s+@(\w+)',
                            r'inquiries:?\s+@(\w+)',
                            r'consultas:?\s+@(\w+)',
                            r'preguntas:?\s+@(\w+)',
                            r'questions:?\s+@(\w+)',
                            r'contactar?:?\s+@(\w+)'
                        ]
                        
                        for pattern in patterns:
                            matches = re.finditer(pattern, about, re.IGNORECASE)
                            for match in matches:
                                username = match.group(1)
                                try:
                                    user = await self.client.get_entity(username)
                                    if process_user_safely(user, is_admin=True, source="patrón en descripción"):
                                        pass  # Ya registrado en process_user_safely
                                except Exception:
                                    pass
            except Exception as e:
                print(f"Error analizando información adicional: {e}")
            
            # FASE 4: Analizar chat vinculado si existe
            try:
                print("\nVerificando si hay chat de discusión vinculado...")
                
                # Obtener chat vinculado
                full_entity = await self.client(functions.channels.GetFullChannelRequest(channel=entity))
                
                if hasattr(full_entity, 'full_chat') and hasattr(full_entity.full_chat, 'linked_chat_id') and full_entity.full_chat.linked_chat_id:
                    linked_chat_id = full_entity.full_chat.linked_chat_id
                    print(f"Chat de discusión vinculado encontrado (ID: {linked_chat_id})")
                    
                    # Intentar extraer usuarios del chat vinculado
                    try:
                        linked_entity = await self.client.get_entity(linked_chat_id)
                        print(f"Analizando chat vinculado: {linked_entity.title}")
                        
                        # Obtener mensajes del chat vinculado
                        linked_messages = await self.client.get_messages(linked_entity, limit=50)
                        
                        for msg in linked_messages:
                            # Procesar remitente
                            if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                                try:
                                    user = await self.client.get_entity(msg.sender_id)
                                    if process_user_safely(user, source="chat vinculado"):
                                        pass  # Ya registrado en process_user_safely
                                except Exception:
                                    pass
                    except Exception as e:
                        print(f"Error analizando chat vinculado: {e}")
            except Exception as e:
                print(f"Error verificando chat vinculado: {e}")
            
            print(f"\nAnálisis de mensajes completado.")
            print(f"Se procesaron {processed_batch_count} lotes de mensajes.")
            print(f"Se encontraron {len(users_found)} usuarios únicos mediante análisis profundo.")
            return len(users_found)
            
        except Exception as e:
            logger.error(f"Error en análisis de mensajes: {e}")
            traceback.print_exc()
            return 0

    def extract_users_from_reactions_comprehensive(self, entity_id):
        """
        Extrae usuarios que han reaccionado a mensajes combinando todas las técnicas disponibles.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_reactions_comprehensive_async(entity_id))

    async def extract_users_from_reactions_comprehensive_async(self, entity_id):
        """
        Extrae usuarios que han reaccionado a mensajes combinando todas las técnicas disponibles.
        Fusiona las funcionalidades de todas las versiones anteriores y maximiza la extracción.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            # Obtener entidad con Telethon
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"Analizando reacciones e interacciones en mensajes de {entity_title}...")
            
            # Inicialización de variables
            all_users = []
            user_ids_found = set()
            messages_with_reactions = 0
            
            # Función auxiliar para procesar usuarios de forma segura
            def process_user_safely(user, source=""):
                if not user or hasattr(user, 'bot') and user.bot:
                    return False
                    
                if user.id in user_ids_found:
                    return False
                    
                self.process_member(user, entity_id, entity_title, False)
                all_users.append(user)
                user_ids_found.add(user.id)
                if source:
                    print(f"Usuario encontrado vía {source}: {user.first_name} (@{user.username or 'sin username'})")
                return True
            
            # Obtener mensajes recientes para analizar
            messages = await self.client.get_messages(entity, limit=50)
            
            if not messages:
                print("No se encontraron mensajes para analizar.")
                return 0
                
            print(f"Analizando {len(messages)} mensajes recientes...")
            
            # FASE 1: Analizar reacciones básicas
            for msg in messages:
                try:
                    if hasattr(msg, 'reactions') and msg.reactions and hasattr(msg.reactions, 'results') and msg.reactions.results:
                        messages_with_reactions += 1
                        print(f"Mensaje {msg.id} tiene {len(msg.reactions.results)} tipos de reacciones")
                        
                        # Iterar por cada tipo de reacción
                        for reaction in msg.reactions.results:
                            # MÉTODO 1: API de Telethon directa
                            try:
                                from telethon.tl.functions.messages import GetMessageReactionsListRequest
                                
                                # Obtener la reacción como string
                                reaction_str = None
                                if hasattr(reaction, 'reaction'):
                                    if isinstance(reaction.reaction, str):
                                        reaction_str = reaction.reaction
                                    elif hasattr(reaction.reaction, 'emoticon'):
                                        reaction_str = reaction.reaction.emoticon
                                
                                if reaction_str:
                                    # Intentar obtener usuarios que reaccionaron
                                    reactors = await self.client(GetMessageReactionsListRequest(
                                        peer=entity,
                                        id=msg.id,
                                        reaction=reaction_str,
                                        offset="",
                                        limit=100
                                    ))
                                    
                                    if hasattr(reactors, 'users'):
                                        for user in reactors.users:
                                            process_user_safely(user, "reacción Telethon")
                            except Exception as e:
                                # Si el primer método falla, continuar con otros
                                pass
                            
                            # MÉTODO 2: Usando Pyrogram para mayor efectividad
                            try:
                                # Cargar credenciales para Pyrogram
                                with open(CREDENTIAL_FILE, 'r') as f:
                                    credentials = json.load(f)
                                
                                async with Client(
                                    "reaction_extractor",
                                    api_id=credentials['api_id'],
                                    api_hash=credentials['api_hash'],
                                    phone_number=credentials['phone']
                                ) as app:
                                    try:
                                        # CRÍTICO: Obtener el chat primero para que Pyrogram lo reconozca
                                        chat = await app.get_chat(int(entity_id))
                                        print(f"Chat reconocido por Pyrogram: {chat.title}")
                                        
                                        # Resolver el peer de manera segura
                                        from pyrogram.raw.types.input_peer_channel import InputPeerChannel
                                        from pyrogram.raw.functions.messages.get_message_reactions_list import GetMessageReactionsList
                                        
                                        # Intentar obtener access_hash desde la entidad de Telethon
                                        if hasattr(entity, 'access_hash'):
                                            access_hash = entity.access_hash
                                            
                                            # Construir InputPeerChannel manualmente
                                            peer = InputPeerChannel(
                                                channel_id=int(entity_id),
                                                access_hash=access_hash
                                            )
                                            
                                            # Obtener la reacción como string
                                            reaction_str = ""
                                            if hasattr(reaction, 'reaction'):
                                                if isinstance(reaction.reaction, str):
                                                    reaction_str = reaction.reaction
                                                elif hasattr(reaction.reaction, 'emoticon'):
                                                    reaction_str = reaction.reaction.emoticon
                                            
                                            if reaction_str:
                                                # Obtener usuarios que reaccionaron
                                                reactors_result = await app.invoke(
                                                    GetMessageReactionsList(
                                                        peer=peer,
                                                        id=msg.id,
                                                        reaction=reaction_str,
                                                        offset="",
                                                        limit=100
                                                    )
                                                )
                                                
                                                if hasattr(reactors_result, 'users') and reactors_result.users:
                                                    for user in reactors_result.users:
                                                        # Crear objeto compatible con process_member
                                                        telethon_user = type('', (), {})()
                                                        telethon_user.id = user.id
                                                        telethon_user.first_name = getattr(user, 'first_name', "")
                                                        telethon_user.last_name = getattr(user, 'last_name', "")
                                                        telethon_user.username = getattr(user, 'username', "")
                                                        telethon_user.bot = getattr(user, 'bot', False)
                                                        
                                                        process_user_safely(telethon_user, "reacción Pyrogram")
                                    except Exception as e:
                                        print(f"Error en método Pyrogram: {e}")
                            except Exception as e:
                                # Continuar con otros métodos si este falla
                                pass
                except Exception:
                    # Ignorar errores en mensajes individuales
                    pass
            
            # FASE 2: Analizar interacciones en comentarios
            for msg in messages:
                try:
                    if hasattr(msg, 'replies') and msg.replies:
                        print(f"Mensaje {msg.id} tiene {msg.replies.replies} respuestas")
                        
                        # Si hay respuestas, intentar analizarlas
                        if msg.replies.replies > 0:
                            try:
                                # Obtener respuestas a este mensaje
                                comments = await self.client.get_messages(
                                    entity,
                                    reply_to=msg.id,
                                    limit=min(msg.replies.replies, 20)  # Limitar a 20 comentarios
                                )
                                
                                for comment in comments:
                                    if comment.sender_id and not isinstance(comment.sender_id, type) and not hasattr(comment.sender_id, 'channel_id'):
                                        try:
                                            user = await self.client.get_entity(comment.sender_id)
                                            process_user_safely(user, "comentario")
                                        except Exception:
                                            pass
                            except Exception as e:
                                print(f"Error obteniendo comentarios: {e}")
                except Exception:
                    pass
            
            # FASE 3: Analizar menciones en los mensajes más recientes
            for msg in messages:
                try:
                    if hasattr(msg, 'entities') and msg.entities:
                        for entity_in_msg in msg.entities:
                            # Verificar si hay menciones explícitas a usuarios
                            try:
                                # Si la entidad tiene directamente un ID de usuario
                                if hasattr(entity_in_msg, 'user_id') and entity_in_msg.user_id:
                                    try:
                                        user = await self.client.get_entity(entity_in_msg.user_id)
                                        process_user_safely(user, "mención directa")
                                    except Exception:
                                        pass
                                
                                # Si es una mención del tipo @username
                                elif msg.text:
                                    # Verificar tipo de entidad por nombre de clase
                                    entity_class_name = entity_in_msg.__class__.__name__
                                    if entity_class_name == 'MessageEntityMention' and hasattr(entity_in_msg, 'offset') and hasattr(entity_in_msg, 'length'):
                                        start = entity_in_msg.offset
                                        end = entity_in_msg.offset + entity_in_msg.length
                                        
                                        if 0 <= start < len(msg.text) and end <= len(msg.text):
                                            mention = msg.text[start:end]
                                            
                                            if mention.startswith('@'):
                                                username = mention[1:]
                                                try:
                                                    user = await self.client.get_entity(username)
                                                    process_user_safely(user, "mención @username")
                                                except Exception:
                                                    pass
                            except Exception:
                                pass
                except Exception:
                    pass
            
            # FASE 4: Analizar remitentes originales de reenvíos
            for msg in messages:
                try:
                    if hasattr(msg, 'forward') and msg.forward:
                        if hasattr(msg.forward, 'sender_id') and msg.forward.sender_id:
                            try:
                                sender = await self.client.get_entity(msg.forward.sender_id)
                                process_user_safely(sender, "reenvío")
                            except Exception:
                                pass
                        elif hasattr(msg.forward, 'from_name') and msg.forward.from_name:
                            # Buscar por nombre (más especulativo)
                            try:
                                results = await self.client(
                                    functions.contacts.SearchRequest(
                                        q=msg.forward.from_name,
                                        limit=3
                                    )
                                )
                                
                                for user in results.users:
                                    if user.first_name == msg.forward.from_name or user.last_name == msg.forward.from_name:
                                        process_user_safely(user, "reenvío por nombre")
                                        break  # Solo el primer match
                            except Exception:
                                pass
                except Exception:
                    pass
            
            # FASE 5: Analizar patrones globales en todos los mensajes
            try:
                print("\nAnalizando patrones globales en mensajes...")
                
                # Extraer nombres mencionados frecuentemente
                mentioned_names = []
                
                for msg in messages:
                    if msg.text:
                        # Buscar patrones como "John dijo", "según María", etc.
                        patterns = [
                            r'(?:según|according to|as per) ([A-Z][a-z]+)',
                            r'([A-Z][a-z]+) (?:dijo|said|mentioned|mencionó)',
                            r'(?:gracias|thanks) (?:a|to) ([A-Z][a-z]+)',
                            r'([A-Z][a-z]+) (?:cree|piensa|thinks|believes)',
                            r'([A-Z][a-z]+) (?:escribió|escribio|wrote)'
                        ]
                        
                        for pattern in patterns:
                            matches = re.finditer(pattern, msg.text)
                            for match in matches:
                                name = match.group(1)
                                if len(name) >= 4:  # Evitar nombres muy cortos
                                    mentioned_names.append(name)
                
                # Buscar usuarios basados en nombres mencionados frecuentemente
                if mentioned_names:
                    from collections import Counter
                    name_counts = Counter(mentioned_names)
                    
                    for name, count in name_counts.most_common(3):  # Top 3 nombres
                        if count >= 2:  # Mencionado al menos dos veces
                            print(f"Buscando usuario con nombre mencionado frecuentemente: {name}")
                            try:
                                results = await self.client(
                                    functions.contacts.SearchRequest(
                                        q=name,
                                        limit=3
                                    )
                                )
                                
                                for user in results.users:
                                    if user.first_name == name or user.last_name == name:
                                        process_user_safely(user, "nombre mencionado frecuentemente")
                                        break  # Solo el primer match exacto
                            except Exception:
                                pass
            except Exception as e:
                print(f"Error analizando patrones globales: {e}")
            
            print(f"\nAnálisis de interacciones completado.")
            print(f"Mensajes con reacciones: {messages_with_reactions} de {len(messages)}")
            print(f"Se encontraron {len(all_users)} usuarios únicos.")
            return len(all_users)
            
        except Exception as e:
            logger.error(f"Error en análisis de interacciones: {e}")
            traceback.print_exc()
            return 0

    def extract_users_by_association_comprehensive(self, entity_id):
        """
        Busca usuarios por asociación con canales y grupos relacionados, combinando todas las técnicas.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_by_association_comprehensive_async(entity_id))

    async def extract_users_by_association_comprehensive_async(self, entity_id):
        """
        Busca usuarios por asociación con canales y grupos relacionados, combinando todas las técnicas.
        Fusiona las funcionalidades de todas las versiones anteriores y maximiza la extracción.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"\nBuscando usuarios por asociación completa para {entity_title}")
            
            # Variables comunes
            all_users = []
            user_ids_found = set()
            
            # Función auxiliar común
            def process_user_safely(user, source=""):
                if not user or user.id in user_ids_found:
                    return False
                    
                if hasattr(user, 'bot') and user.bot:
                    return False
                    
                self.process_member(user, entity_id, entity_title, False)
                all_users.append(user)
                user_ids_found.add(user.id)
                if source:
                    print(f"Usuario encontrado vía {source}: {user.first_name} (@{user.username or 'sin username'})")
                return True
            
            # FASE 1: Extracción optimizada de palabras clave
            keywords = set()
            
            # Del título (palabras significativas)
            if entity_title:
                # Excluir palabras comunes
                common_words = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'de', 'del', 'al', 'a', 'en', 'con', 
                            'por', 'para', 'sin', 'sobre', 'tras', 'pro', 'según', 'the', 'of', 'and', 'or', 'for', 'to', 'in', 
                            'on', 'at', 'by', 'with', 'without', 'from, it', 'chat', 'channel', 'group', 'telegram', 'official',
                            'welcome', 'news', 'info', 'updates'}
                
                # Extraer palabras significativas (al menos 4 caracteres, no en lista de comunes)
                title_words = re.findall(r'\w+', entity_title.lower())
                keywords.update(word for word in title_words if len(word) >= 4 and word not in common_words)
            
            # Del username (componentes significativos)
            if hasattr(entity, 'username') and entity.username:
                # Dividir por separadores comunes y extraer componentes significativos
                parts = re.split(r'[_.]', entity.username.lower())
                keywords.update([p for p in parts if len(p) >= 4 and p not in common_words])
                
                # Añadir también el username completo como palabra clave
                keywords.add(entity.username.lower())
            
            # De la descripción (análisis profundo)
            try:
                full_entity = await self.client(GetFullChannelRequest(channel=entity))
                if hasattr(full_entity, 'full_chat') and hasattr(full_entity.full_chat, 'about'):
                    about = full_entity.full_chat.about
                    if about:
                        # Extraer palabras significativas
                        about_words = re.findall(r'\w+', about.lower())
                        keywords.update([w for w in about_words if len(w) >= 4 and w not in common_words])
                        
                        # Extraer posibles temáticas o categorías usando n-gramas
                        # Esto permite identificar frases como "crypto trading" o "financial advice"
                        words = about.lower().split()
                        if len(words) >= 2:
                            for i in range(len(words) - 1):
                                bigram = words[i] + " " + words[i+1]
                                if len(bigram) >= 7:  # Solo bigramas significativos
                                    keywords.add(bigram)
            except Exception as e:
                print(f"No se pudo extraer la descripción: {e}")
            
            # Extraer palabras clave del topic (si está disponible)
            # Esto puede dar información adicional sobre la temática
            try:
                if hasattr(entity, 'topics'):
                    for topic in entity.topics:
                        if hasattr(topic, 'title'):
                            topic_words = re.findall(r'\w+', topic.title.lower())
                            keywords.update([w for w in topic_words if len(w) >= 4 and w not in common_words])
            except Exception:
                pass
            
            # Limitar a las palabras clave más relevantes (ordenadas por longitud, las más largas suelen ser más específicas)
            sorted_keywords = sorted(keywords, key=len, reverse=True)
            keywords = sorted_keywords[:15]  # Las 15 más relevantes
            
            if not keywords:
                print("No se pudieron extraer palabras clave relevantes.")
                return 0
                    
            print(f"Palabras clave extraídas: {', '.join(keywords)}")
            
            # FASE 2: Búsqueda avanzada de entidades relacionadas
            related_entities = []
            
            print("\nBuscando entidades relacionadas...")
            
            # Método 1: Búsqueda directa por términos específicos
            for keyword in keywords[:10]:  # Limitar para no exceder rate limits
                try:
                    print(f"Buscando entidades con palabra clave: '{keyword}'")
                    results = await self.client(SearchRequest(
                        q=keyword,
                        limit=5
                    ))
                    
                    if hasattr(results, 'chats'):
                        for chat in results.chats:
                            if chat.id != int(entity_id) and chat.id not in [e.id for e in related_entities]:
                                related_entities.append(chat)
                                print(f"Entidad relacionada encontrada: {chat.title}")
                except Exception as e:
                    print(f"Error buscando con palabra clave '{keyword}': {e}")
                
                await asyncio.sleep(1)
            
            # Método 2: Búsqueda de entidades con nombres similares
            if hasattr(entity, 'username') and entity.username:
                try:
                    print(f"Buscando entidades con nombres similares a @{entity.username}...")
                    
                    # Usar variantes del nombre
                    username_parts = re.split(r'[_.]', entity.username.lower())
                    for part in username_parts:
                        if len(part) >= 4:
                            try:
                                results = await self.client(SearchRequest(
                                    q=part,
                                    limit=5
                                ))
                                
                                if hasattr(results, 'chats'):
                                    for chat in results.chats:
                                        if chat.id != int(entity_id) and chat.id not in [e.id for e in related_entities]:
                                            related_entities.append(chat)
                                            print(f"Entidad relacionada encontrada por similaridad: {chat.title}")
                            except Exception:
                                pass
                            
                            await asyncio.sleep(1)
                except Exception as e:
                    print(f"Error buscando entidades con nombres similares: {e}")
            
            # Método 3: Búsqueda de entidades vinculadas (canales, grupos de discusión, etc.)
            try:
                print("Verificando entidades vinculadas...")
                
                full_entity = await self.client(GetFullChannelRequest(channel=entity))
                
                # Verificar chat vinculado
                if hasattr(full_entity, 'full_chat') and hasattr(full_entity.full_chat, 'linked_chat_id') and full_entity.full_chat.linked_chat_id:
                    linked_chat_id = full_entity.full_chat.linked_chat_id
                    try:
                        linked_chat = await self.client.get_entity(linked_chat_id)
                        related_entities.append(linked_chat)
                        print(f"Chat vinculado encontrado: {linked_chat.title}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"Error verificando entidades vinculadas: {e}")
            
            print(f"Se encontraron {len(related_entities)} entidades potencialmente relacionadas")
            
            # FASE 3: Análisis avanzado de entidades relacionadas
            print("\nAnalizando entidades relacionadas para encontrar usuarios comunes...")
            
            # Categorizar entidades por relevancia
            categorized_entities = {
                "alta": [],   # Alta probabilidad de usuarios comunes
                "media": [],  # Media probabilidad
                "baja": []    # Baja probabilidad
            }
            
            # Clasificar entidades según relevancia
            for rel_entity in related_entities:
                relevance = "baja"
                
                # Alta relevancia: Chat vinculado o similar username
                if (hasattr(full_entity, 'full_chat') and 
                    hasattr(full_entity.full_chat, 'linked_chat_id') and 
                    full_entity.full_chat.linked_chat_id == rel_entity.id):
                    relevance = "alta"
                
                # Alta relevancia: Username similar
                elif (hasattr(entity, 'username') and entity.username and 
                    hasattr(rel_entity, 'username') and rel_entity.username):
                    if (entity.username[:4] == rel_entity.username[:4] or 
                        entity.username[-4:] == rel_entity.username[-4:]):
                        relevance = "alta"
                
                # Media relevancia: Título similar
                elif any(keyword in rel_entity.title.lower() for keyword in keywords):
                    relevance = "media"
                
                categorized_entities[relevance].append(rel_entity)
            
            # Procesar entidades por orden de relevancia
            for relevance in ["alta", "media", "baja"]:
                entities = categorized_entities[relevance]
                if not entities:
                    continue
                    
                print(f"\nAnalizando {len(entities)} entidades de relevancia {relevance}...")
                
                # Limitar según relevancia
                limit = 5 if relevance == "alta" else (3 if relevance == "media" else 1)
                
                for i, rel_entity in enumerate(entities[:limit]):
                    try:
                        print(f"Analizando entidad {i+1}/{min(limit, len(entities))}: {rel_entity.title}")
                        
                        # Método 1: Obtener participantes directamente
                        try:
                            participants = await self.client.get_participants(rel_entity, limit=30)
                            
                            for user in participants:
                                if not user.bot:
                                    # Verificar si pertenece a la entidad original
                                    try:
                                        # Intentar obtener miembro específico
                                        from telethon.tl.functions.channels import GetParticipantRequest
                                        
                                        # Primer intento: verificar directamente
                                        try:
                                            participant = await self.client(GetParticipantRequest(
                                                channel=entity,
                                                participant=user.id
                                            ))
                                            
                                            # Si llegamos aquí, el usuario está confirmado en el canal principal
                                            process_user_safely(user, f"participante confirmado ({rel_entity.title})")
                                        except Exception as e:
                                            print("Error al obtener participante:", e)
                                            traceback.print_exc()
                                            # El usuario no está en el canal original
                                            pass
                                        except Exception:
                                            # Error ambiguo - para relevancia alta, añadir de todos modos
                                            if relevance == "alta":
                                                process_user_safely(user, f"probable participante ({rel_entity.title})")
                                    except Exception:
                                        pass
                        except Exception:
                            # Si no podemos obtener participantes, usar método de mensajes
                            try:
                                messages = await self.client.get_messages(rel_entity, limit=20)
                                
                                for msg in messages:
                                    if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                                        try:
                                            user = await self.client.get_entity(msg.sender_id)
                                            
                                            if not user.bot:
                                                # Para entidades de alta relevancia, añadir directamente
                                                if relevance == "alta":
                                                    process_user_safely(user, f"mensaje en entidad relacionada ({rel_entity.title})")
                                                else:
                                                    # Para otras, verificar si está en la entidad original
                                                    try:
                                                        # Intentar obtener miembro específico
                                                        from telethon.tl.functions.channels import GetParticipantRequest
                                                        participant = await self.client(GetParticipantRequest(
                                                            channel=entity,
                                                            participant=user.id
                                                        ))
                                                        
                                                        # Si llegamos aquí, está confirmado
                                                        process_user_safely(user, f"mensaje+confirmado ({rel_entity.title})")
                                                    except:
                                                        pass
                                        except:
                                            pass
                            except:
                                pass
                    except Exception as e:
                        print(f"Error analizando entidad relacionada: {e}")
                    
                    # Pausa entre entidades
                    await asyncio.sleep(2)
            
            # FASE 4: Análisis de nombres y patrones
            if all_users:
                print("\nAnalizando patrones de nombres para encontrar usuarios adicionales...")
                
                # Extraer nombres significativos de usuarios encontrados
                first_names = [user.first_name for user in all_users if hasattr(user, 'first_name') and user.first_name]
                last_names = [user.last_name for user in all_users if hasattr(user, 'last_name') and user.last_name]
                
                # Encontrar nombres comunes (posibles administradores o miembros importantes)
                from collections import Counter
                name_counts = Counter(first_names + last_names)
                
                # Buscar usuarios con estos nombres
                for name, count in name_counts.most_common(5):  # Top 5 nombres
                    if len(name) >= 4 and count >= 2:  # Solo nombres significativos mencionados múltiples veces
                        try:
                            print(f"Buscando usuarios adicionales con nombre: {name}")
                            results = await self.client(
                                functions.contacts.SearchRequest(
                                    q=name,
                                    limit=5
                                )
                            )
                            
                            for user in results.users:
                                if user.first_name == name or user.last_name == name:
                                    # Verificar si pertenece al canal original
                                    try:
                                        from telethon.tl.functions.channels import GetParticipantRequest
                                        participant = await self.client(GetParticipantRequest(
                                            channel=entity,
                                            participant=user.id
                                        ))
                                        
                                        # Confirmado en el canal
                                        process_user_safely(user, "nombre común confirmado")
                                    except UserNotParticipantError:
                                        # No está en el canal
                                        pass
                                    except Exception:
                                        # Para nombres muy comunes, añadir como probable
                                        if count >= 3:
                                            process_user_safely(user, "nombre muy común (probable)")
                        except Exception:
                            pass
                        
                        await asyncio.sleep(1)
            
            print(f"\nBúsqueda por asociación completa finalizada.")
            print(f"Se encontraron {len(all_users)} usuarios únicos.")
            return len(all_users)
        
        except Exception as e:
            logger.error(f"Error en búsqueda por asociación: {e}")
            traceback.print_exc()
            return 0

    def extract_users_ultimate_comprehensive(self, entity_id, duration_minutes=45):
        """
        Método supremo optimizado para extraer usuarios combinando todas las técnicas.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
            duration_minutes: Duración máxima estimada
        
        Returns:
            Número de usuarios encontrados
        """
        try:    
        # Get the current event loop that Telethon is using
            loop = asyncio.get_event_loop()
            
            # Run the async implementation in that same loop
            return loop.run_until_complete(
                self.extract_users_ultimate_comprehensive_async(entity_id, duration_minutes)
            )
        
        except Exception as e:
            logger.error(f"Error in sync wrapper for extract_users_ultimate_comprehensive: {e}")
            traceback.print_exc()
            return 0

    async def extract_users_ultimate_comprehensive_async(self, entity_id, duration_minutes=45):
        """
        Method supremo optimized for extracting users from channels/groups combining
        all available techniques in one exhaustive execution.
        
        Args:
            entity_id: ID of the entity
            duration_minutes: Estimated maximum duration
        
        Returns:
            Number of users found
        """
        try:
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            entity_type = "canal" if hasattr(entity, 'broadcast') and entity.broadcast else "grupo"
            
            print(f"\n{'='*50}")
            print(f" EXTRACCIÓN SUPREMA EXHAUSTIVA PARA {entity_type.upper()}: {entity_title} ")
            print(f"{'='*50}\n")
            print("Este proceso utiliza todos los métodos disponibles para extraer usuarios.")
            print(f"Duración estimada: {duration_minutes} minutos.\n")
            
            start_time = time.time()
            all_users = set()
            
            # Define methods in order of effectiveness (most effective techniques first)
            methods = [
                {
                    "name": "Análisis exhaustivo de mensajes",
                    "function": self.extract_users_from_messages_comprehensive_async,
                    "args": [entity_id],
                    "kwargs": {"depth": 5, "messages_per_batch": 100}
                },
                {
                    "name": "Análisis exhaustivo de reacciones e interacciones",
                    "function": self.extract_users_from_reactions_comprehensive_async,
                    "args": [entity_id],
                    "kwargs": {}
                },
                {
                    "name": "Análisis de chat vinculado",
                    "function": self.extract_members_from_linked_chat_async,
                    "args": [entity_id, entity_id, entity_title],
                    "kwargs": {}
                },
                {
                    "name": "Búsqueda por asociación exhaustiva",
                    "function": self.extract_users_by_association_comprehensive_async,
                    "args": [entity_id],
                    "kwargs": {}
                },
                {
                    "name": "Análisis de secciones de comentarios",
                    "function": self.extract_users_from_comment_sections_async,
                    "args": [entity_id],
                    "kwargs": {"message_limit": 50}
                },
                {
                    "name": "Extracción MTProto directa",
                    "function": self.extract_users_mtproto_direct_async,
                    "args": [entity_id],
                    "kwargs": {}
                },
                {
                    "name": "Escaneo por rango de IDs",
                    "function": self.extract_users_by_id_range_scan_async,
                    "args": [entity_id],
                    "kwargs": {"batch_size": 30, "max_attempts": 100}
                }
            ]
            
            # Run main methods with time control
            time_per_method = duration_minutes * 60 / len(methods)
            
            for method in methods:
                method_name = method["name"]
                method_func = method["function"]
                
                print(f"\n{'-'*50}")
                print(f" EJECUTANDO: {method_name.upper()} ")
                print(f"{'-'*50}")
                
                # Calculate available time for this method
                method_start = time.time()
                method_time_limit = time_per_method  # Time allocated to this method
                
                # Check if we still have enough time
                elapsed_total = time.time() - start_time
                remaining_total = duration_minutes * 60 - elapsed_total
                
                if remaining_total <= 0:
                    print("\n⚠️ Tiempo total agotado. Finalizando extracción.")
                    break
                    
                # Adjust time for this method if less than assigned remains
                if remaining_total < method_time_limit:
                    method_time_limit = remaining_total
                    
                # Get current count before method
                before_count = len(self.members)
                
                try:
                    # Execute the method with time limit
                    print(f"Tiempo asignado para este método: {method_time_limit/60:.1f} minutos")
                    
                    # Directly await the async function
                    await method_func(*method["args"], **method["kwargs"])
                    
                    # Update set of all users
                    after_count = len(self.members)
                    new_users = after_count - before_count
                    
                    # Record users found with this method
                    for key, member in list(self.members.items())[-new_users:]:
                        if member['entity_id'] == entity_id:
                            all_users.add(member['user_id'])
                    
                    # Show partial results
                    method_elapsed = time.time() - method_start
                    elapsed_total = time.time() - start_time
                    elapsed_min = int(elapsed_total // 60)
                    elapsed_sec = int(elapsed_total % 60)
                    
                    print(f"\n✅ {method_name} completado en {method_elapsed:.1f} segundos")
                    print(f"⏱ Tiempo transcurrido total: {elapsed_min} minutos, {elapsed_sec} segundos")
                    print(f"👤 Usuarios encontrados hasta ahora: {len(all_users)}")
                    
                    # Check if this method consumed all its time
                    if method_elapsed >= method_time_limit:
                        print(f"⚠️ Este método agotó su tiempo asignado.")
                    
                    # Check remaining total time
                    remaining_total = duration_minutes * 60 - elapsed_total
                    if remaining_total <= 0:
                        print("\n⚠️ Tiempo total agotado. Finalizando extracción.")
                        break
                    
                except Exception as e:
                    print(f"\n❌ Error en {method_name}: {e}")
                    traceback.print_exc()
                
                # Brief pause between methods
                await asyncio.sleep(2)
            
            # Final summary
            elapsed = time.time() - start_time
            elapsed_min = int(elapsed // 60)
            elapsed_sec = int(elapsed % 60)
            
            print(f"\n{'='*50}")
            print(f" RESUMEN DE EXTRACCIÓN SUPREMA EXHAUSTIVA ")
            print(f"{'='*50}")
            print(f"✓ {entity_type.capitalize()}: {entity_title}")
            print(f"✓ Tiempo total: {elapsed_min} minutos, {elapsed_sec} segundos")
            print(f"✓ Total de usuarios únicos encontrados: {len(all_users)}")
            print(f"{'='*50}")
            
            return len(all_users)
            
        except Exception as e:
            logger.error(f"Error en extracción suprema: {e}")
            traceback.print_exc()
            return 0

    # 5.2 MÉTODOS ESPECÍFICOS (CONSERVAMOS LOS ORIGINALES PARA COMPATIBILIDAD)

    def extract_users_from_comment_sections(self, entity_id, message_limit=50):
        """
        Busca usuarios en secciones de comentarios de publicaciones.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
            message_limit: Número máximo de mensajes a analizar
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_comment_sections_async(entity_id, message_limit))

    async def extract_users_from_comment_sections_async(self, entity_id, message_limit=50):
        """
        Busca usuarios en secciones de comentarios de publicaciones.
        
        Args:
            entity_id: ID de la entidad
            message_limit: Número máximo de mensajes a analizar
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"Buscando secciones de comentarios en enlaces de {entity_title}")
            
            # Obtener mensajes recientes
            messages = await self.client.get_messages(entity, limit=message_limit)
            
            users_found = []
            discussion_links = []
            
            # Buscar enlaces de discusión o comentarios
            for msg in messages:
                if not msg.entities:
                    continue
                    
                for entity in msg.entities:
                    if hasattr(entity, 'type') and entity.type in ['url', 'text_link']:
                        # Extraer la URL
                        if entity.type == 'url':
                            url = msg.text[entity.offset:entity.offset+entity.length]
                        else:  # text_link
                            url = entity.url
                        
                        # Verificar si es un enlace a una publicación o discusión5
                        if 't.me/' in url and ('/s/' in url or '/c/' in url or '/p/' in url):
                            discussion_links.append(url)
            
            if not discussion_links:
                print("No se encontraron enlaces a publicaciones o discusiones.")
                return 0
            
            print(f"Se encontraron {len(discussion_links)} enlaces potenciales con comentarios.")
            
            # Analizar cada enlace de discusión
            for i, link in enumerate(discussion_links):
                print(f"Analizando enlace {i+1}/{len(discussion_links)}: {link}")
                
                try:
                    # Intentar resolver la URL a una entidad de Telegram
                    resolved = await self.client(ResolveUsernameRequest(link.split('t.me/')[1].split('/')[0]))
                    
                    if resolved.peer:
                        # Intentar obtener el mensaje específico
                        try:
                            # Extraer ID de mensaje del enlace si es posible
                            msg_id = None
                            if '/p/' in link:
                                msg_id = int(link.split('/p/')[1])
                            elif '/c/' in link:
                                parts = link.split('/c/')
                                if len(parts) > 1 and '/' in parts[1]:
                                    msg_id = int(parts[1].split('/')[1])
                            
                            if msg_id:
                                # Obtener la discusión del mensaje
                                message = await self.client.get_messages(resolved.peer, ids=msg_id)
                                
                                if message and hasattr(message, 'replies') and message.replies:
                                    # Si hay una discusión vinculada
                                    if message.replies.channel_id:
                                        discussion_entity = await self.client.get_entity(message.replies.channel_id)
                                        
                                        # Obtener mensajes de la discusión
                                        discussion_messages = await self.client.get_messages(discussion_entity, limit=50)
                                        
                                        for reply in discussion_messages:
                                            if reply.sender_id and not isinstance(reply.sender_id, PeerChannel):
                                                try:
                                                    user = await self.client.get_entity(reply.sender_id)
                                                    if not user.bot and user.id not in [u.id for u in users_found]:
                                                        self.process_member(user, entity_id, entity_title, False)
                                                        users_found.append(user)
                                                        print(f"Usuario encontrado en comentarios: {user.first_name}")
                                                except:
                                                    pass
                        except:
                            pass
                except:
                    pass
                
                # Pausa entre enlaces
                await asyncio.sleep(2)
            
            print(f"Análisis de comentarios completado. Se encontraron {len(users_found)} usuarios únicos.")
            return len(users_found)
        
        except Exception as e:
            logger.error(f"Error en análisis de comentarios: {e}")
            traceback.print_exc()
            return 0  

    def extract_users_mtproto_direct(self, entity_id):
        """
        Utiliza métodos de bajo nivel de la API de MTProto.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_mtproto_direct_async(entity_id))

    async def extract_users_mtproto_direct_async(self, entity_id):
        """
        Utiliza métodos de bajo nivel de la API de MTProto.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            from pyrogram import raw
            import random
            
            
        
            # Cargar credenciales
            with open(CREDENTIAL_FILE, 'r') as f:
                credentials = json.load(f)
            
            # Primero obtenemos la entidad con Telethon para asegurarnos de tener datos correctos
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"Iniciando extracción MTProto directa para {entity_title}")
            print("Advertencia: Este método utiliza técnicas de muy bajo nivel")
            
            # Iniciar cliente Pyrogram con manejo explícito de errores
            async with Client(
                "mtproto_client",
                api_id=credentials['api_id'],
                api_hash=credentials['api_hash'],
                phone_number=credentials['phone']
            ) as app:
                users_found = {}
                
                # CLAVE: Asegurarnos de que Pyrogram conozca este canal antes de hacer cualquier operación
                try:
                    # Primero obtener información general del canal para que Pyrogram lo reconozca
                    # Esto es vital para que la API interna de Pyrogram funcione correctamente
                    print("Obteniendo información básica del canal...")
                    
                    # IMPORTANTE: Usar una combinación de técnicas para asegurar que el peer se resuelva
                    try:
                        # Intentar con get_chat primero (más confiable)
                        chat = await app.get_chat(int(entity_id))
                        print(f"Chat obtenido correctamente como: {chat.title}")
                        
                        # Una vez que get_chat funciona, ahora podemos resolver el peer de manera segura
                        peer = await app.resolve_peer(chat.id)
                    except Exception as e:
                        print(f"Error obteniendo chat con get_chat: {e}")
                        
                        # Intentar método alternativo: construir el peer manualmente
                        from pyrogram.raw.types import InputPeerChannel
                        
                        # Extraer access_hash de la entidad de Telethon
                        if hasattr(entity, 'access_hash'):
                            access_hash = entity.access_hash
                            peer = InputPeerChannel(
                                channel_id=int(entity_id),
                                access_hash=access_hash
                            )
                            print(f"Peer construido manualmente usando access_hash de Telethon")
                        else:
                            # Último recurso: intentar con métodos de búsqueda global
                            print("Intentando búsqueda global para resolver el peer...")
                            results = await app.search_global(entity_title)
                            chat_found = False
                            
                            for result in results:
                                if hasattr(result.chat, 'id') and result.chat.id == int(entity_id):
                                    peer = await app.resolve_peer(result.chat.id)
                                    chat_found = True
                                    print(f"Chat encontrado mediante búsqueda global")
                                    break
                            
                            if not chat_found:
                                raise ValueError("No se pudo resolver el peer por ningún método")
                except Exception as e:
                    print(f"Error fatal al obtener información del canal: {e}")
                    return 0
                
                # Ahora que tenemos el peer correctamente resuelto, podemos proceder con los métodos
                
                # 1. Intentar obtener información básica del canal
                try:
                    print("Obteniendo información del canal...")
                    
                    # Usar método de bajo nivel getFullChannel de manera segura
                    try:
                        full_channel = await app.invoke(
                            raw.functions.channels.GetFullChannel(
                                channel=peer
                            )
                        )
                        
                        if hasattr(full_channel, 'full_chat'):
                            print(f"Información obtenida. Participantes aproximados: {full_channel.full_chat.participants_count}")
                            
                            # Si la respuesta contiene alguna info de participantes, procesarla
                            if hasattr(full_channel.full_chat, 'participants'):
                                for participant in full_channel.full_chat.participants.participants:
                                    try:
                                        user_id = participant.user_id
                                        if user_id not in users_found:
                                            user = await app.get_users(user_id)
                                            users_found[user_id] = user
                                            print(f"Usuario encontrado en información del canal: {user.first_name}")
                                    except Exception:
                                        pass
                    except Exception as e:
                        print(f"Error obteniendo información completa: {e}")
                except Exception as e:
                    print(f"Error en GetFullChannel: {e}")
                
                # 2. Método mejorado: usar SearchPublicChat para obtener más información
                try:
                    print("Intentando método SearchPublicChat...")
                    
                    # Si tenemos un username, podemos usar SearchPublicChat
                    if hasattr(entity, 'username') and entity.username:
                        try:
                            public_chat = await app.invoke(
                                raw.functions.contacts.SearchPublicChat(
                                    username=entity.username
                                )
                            )
                            
                            if hasattr(public_chat, 'users'):
                                for user in public_chat.users:
                                    user_id = user.id
                                    if user_id not in users_found:
                                        users_found[user_id] = await app.get_users(user_id)
                                        print(f"Usuario encontrado vía SearchPublicChat: {users_found[user_id].first_name}")
                        except Exception as e:
                            print(f"Error con SearchPublicChat: {e}")
                except Exception as e:
                    print(f"Error en bloque SearchPublicChat: {e}")
                
                # 3. Método GetParticipants con diferentes filtros
                filter_types = [
                    ("Recientes", raw.types.ChannelParticipantsRecent()),
                    ("Administradores", raw.types.ChannelParticipantsAdmins()),
                    ("Bots", raw.types.ChannelParticipantsBots()),
                    # Búsquedas con varias letras (más efectivo que términos completos)
                    *[
                        (f"Búsqueda '{letra}'", raw.types.ChannelParticipantsSearch(q=letra))
                        for letra in "aeiouбвгдеёжзийклмнопрстуфхцчшщъыьэюя"  # Incluir letras latinas y cirílicas
                    ]
                ]
                
                for desc, filter_obj in filter_types:
                    try:
                        print(f"Probando filtro: {desc}...")
                        
                        # Agregamos randomness al hash para evitar problemas de caché
                        random_hash = random.randint(0, 0x7FFFFFFF)
                        
                        result = await app.invoke(
                            raw.functions.channels.GetParticipants(
                                channel=peer,
                                filter=filter_obj,
                                offset=0,
                                limit=100,
                                hash=random_hash
                            )
                        )
                        
                        if hasattr(result, 'users') and result.users:
                            new_found = 0
                            for user in result.users:
                                user_id = user.id
                                if user_id not in users_found and not getattr(user, 'bot', False):
                                    try:
                                        user_obj = await app.get_users(user_id)
                                        users_found[user_id] = user_obj
                                        new_found += 1
                                    except Exception:
                                        # Si falla get_users, usar directamente el objeto user
                                        if not getattr(user, 'bot', False):
                                            users_found[user_id] = user
                                            new_found += 1
                            
                            print(f"Encontrados {new_found} nuevos usuarios con filtro {desc}")
                    
                    except Exception as e:
                        print(f"Error con filtro {desc}: {str(e)}")
                    
                    # Pausa entre intentos - IMPORTANTE para evitar rate limits
                    await asyncio.sleep(random.uniform(1.5, 3.0))
                
                # 4. Intentar obtener usuarios a través del historial de mensajes
                try:
                    print("Analizando historial de mensajes...")
                    
                    # Usar la API de bajo nivel para obtener mensajes
                    messages_result = await app.invoke(
                        raw.functions.messages.GetHistory(
                            peer=peer,
                            offset_id=0,
                            offset_date=0,
                            add_offset=0,
                            limit=100,
                            max_id=0,
                            min_id=0,
                            hash=0
                        )
                    )
                    
                    if hasattr(messages_result, 'messages') and messages_result.messages:
                        print(f"Obtenidos {len(messages_result.messages)} mensajes")
                        
                        # Extraer IDs de remitentes y usuarios mencionados
                        for message in messages_result.messages:
                            # Remitente del mensaje
                            if hasattr(message, 'from_id') and message.from_id:
                                try:
                                    from_id = None
                                    # Extraer user_id según el tipo de from_id
                                    if hasattr(message.from_id, 'user_id'):
                                        from_id = message.from_id.user_id
                                    
                                    if from_id and from_id not in users_found:
                                        try:
                                            user = await app.get_users(from_id)
                                            if not user.is_bot:
                                                users_found[from_id] = user
                                                print(f"Usuario encontrado como remitente: {user.first_name}")
                                        except Exception:
                                            pass
                                except Exception as e:
                                    pass
                            
                            # Mensajes reenviados
                            if hasattr(message, 'fwd_from') and message.fwd_from:
                                try:
                                    if hasattr(message.fwd_from, 'from_id'):
                                        fwd_id = None
                                        if hasattr(message.fwd_from.from_id, 'user_id'):
                                            fwd_id = message.fwd_from.from_id.user_id
                                        
                                        if fwd_id and fwd_id not in users_found:
                                            try:
                                                user = await app.get_users(fwd_id)
                                                if not user.is_bot:
                                                    users_found[fwd_id] = user
                                                    print(f"Usuario encontrado en reenvío: {user.first_name}")
                                            except Exception:
                                                pass
                                except Exception:
                                    pass
                            
                            # Menciones en el mensaje
                            if hasattr(message, 'entities') and message.entities:
                                for entity in message.entities:
                                    if hasattr(entity, 'type') and entity.type in ['mention', 'text_mention']:
                                        try:
                                            mention_id = None
                                            
                                            # Diferentes tipos de menciones requieren diferente procesamiento
                                            if entity.type == 'text_mention' and hasattr(entity, 'user_id'):
                                                mention_id = entity.user_id
                                            elif entity.type == 'mention' and hasattr(message, 'message'):
                                                # Extraer el username de la mención
                                                offset = entity.offset
                                                length = entity.length
                                                if offset + length <= len(message.message):
                                                    username = message.message[offset+1:offset+length]  # +1 para quitar @
                                                    try:
                                                        mention_user = await app.get_users(username)
                                                        mention_id = mention_user.id
                                                    except Exception:
                                                        pass
                                            
                                            if mention_id and mention_id not in users_found:
                                                try:
                                                    user = await app.get_users(mention_id)
                                                    if not user.is_bot:
                                                        users_found[mention_id] = user
                                                        print(f"Usuario encontrado por mención: {user.first_name}")
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                    
                except Exception as e:
                        print(f"Error analizando mensaje: {str(e)}")
                
                # Procesar usuarios encontrados
                users_processed = 0
                print(f"\nProcesando {len(users_found)} usuarios encontrados...")
                
                for user_id, user_data in users_found.items():
                    try:
                        # Crear objeto compatible con Telethon
                        user = type('', (), {})()
                        
                        # Extraer datos según el tipo de objeto que tengamos
                        if hasattr(user_data, 'first_name'):
                            # Si es un objeto User de Pyrogram
                            user.id = user_data.id
                            user.first_name = user_data.first_name
                            user.last_name = user_data.last_name if user_data.last_name else ""
                            user.username = user_data.username if user_data.username else ""
                            user.bot = user_data.is_bot
                        else:
                            # Si es un objeto raw de MTProto
                            user.id = user_data.id
                            user.first_name = getattr(user_data, 'first_name', "")
                            user.last_name = getattr(user_data, 'last_name', "")
                            user.username = getattr(user_data, 'username', "")
                            user.bot = getattr(user_data, 'bot', False)
                        
                        # Procesar usuario solo si no es bot
                        if not user.bot:
                            self.process_member(user, entity_id, entity_title, False)
                            users_processed += 1
                    except Exception as e:
                        print(f"Error procesando usuario {user_id}: {str(e)}")
                
                print(f"Extracción completada. {users_processed} usuarios procesados correctamente.")
                return users_processed
            
        except Exception as e:
            logger.error(f"Error en extracción MTProto: {e}")
            traceback.print_exc()
            return 0

    def extract_users_by_id_range_scan(self, entity_id, batch_size=30, max_attempts=200):
        """
        Método no convencional para escanear por rangos de ID.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
            batch_size: Tamaño del lote de IDs
            max_attempts: Número máximo de intentos
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_by_id_range_scan_async(entity_id, batch_size, max_attempts))

    async def extract_users_by_id_range_scan_async(self, entity_id, batch_size=30, max_attempts=200):
        """
        Método no convencional para escanear por rangos de ID.
        
        Args:
            entity_id: ID de la entidad
            batch_size: Tamaño del lote de IDs
            max_attempts: Número máximo de intentos
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"Iniciando escaneo inverso por ID para {entity_title}")
            print("Este método intenta inferir posibles usuarios basándose en patrones de ID")
            
            # Intentar obtener algunos usuarios "semilla" para establecer rangos
            seed_users = []
            
            # 1. Buscar administradores (esto suele funcionar incluso sin ser admin)
            try:
                admins = await self.client.get_participants(entity, filter=ChannelParticipantsAdmins())
                seed_users.extend(admins)
            except Exception as e:
                print(f"No se pudieron obtener administradores: {str(e)}")
            
            # 2. Obtener usuarios de mensajes recientes
            try:
                messages = await self.client.get_messages(entity, limit=100)
                for msg in messages:
                    if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                        try:
                            user = await self.client.get_entity(msg.sender_id)
                            seed_users.append(user)
                        except:
                            pass
            except Exception as e:
                print(f"No se pudieron analizar mensajes: {str(e)}")
            
            if not seed_users:
                print("No se pudieron encontrar usuarios semilla para establecer rangos.")
                return 0
            
            # Organizar IDs y calcular rangos potenciales
            seed_ids = sorted([u.id for u in seed_users])
            
            if len(seed_ids) < 2:
                # Si solo tenemos un ID, crear un rango artificial
                min_id = seed_ids[0] - 10000
                max_id = seed_ids[0] + 10000
            else:
                # Calcular el rango basado en los IDs existentes
                min_id = min(seed_ids)
                max_id = max(seed_ids)
                # Extender el rango para capturar más usuarios potenciales
                range_size = max_id - min_id
                min_id = min_id - (range_size // 4)
                max_id = max_id + (range_size // 4)
            
            print(f"Rango de IDs a escanear: {min_id} a {max_id}")
            
            # Realizar escaneo por batches
            users_found = []
            attempts = 0
            
            current_id = min_id
            while current_id < max_id and attempts < max_attempts:
                batch_ids = list(range(current_id, current_id + batch_size))
                attempts += 1
                
                try:
                    # Intentar resolver múltiples IDs a la vez
                    batch_users = await self.client.get_entity(batch_ids)
                    
                    if not isinstance(batch_users, list):
                        batch_users = [batch_users]
                    
                    for user in batch_users:
                        if not hasattr(user, 'bot') or not user.bot:
                            # Comprobar si está en el canal mediante un método indirecto
                            try:
                                # Intentar obtener miembro específico
                                member_info = await self.client(GetParticipantRequest(channel=entity, participant=user.id))
                                # Si no hay error, el usuario está en el canal
                                self.process_member(user, entity_id, entity_title, False)
                                users_found.append(user)
                                print(f"Usuario encontrado en canal: {user.first_name} (@{user.username or 'sin username'})")
                            
                            except Exception as e:
                                # Otro error, ignorar
                                print(f"Error al obtener información del usuario: {e}")
                                pass
                except:
                    pass
                
                current_id += batch_size
                
                # Mostrar progreso
                progress = (current_id - min_id) / (max_id - min_id) * 100
                print(f"\rProgreso: {progress:.1f}% - Usuarios encontrados: {len(users_found)}", end="")
                
                # Pausa para evitar limitaciones
                await asyncio.sleep(1)
            
            print(f"\nEscaneo por ID completado. Se encontraron {len(users_found)} usuarios.")
            return len(users_found)
        
        except Exception as e:
            logger.error(f"Error en escaneo por ID: {e}")
            traceback.print_exc()
            return 0

    def extract_users_ultra_method(self, entity_id):
        """
        Método ultra no convencional para canales extremadamente restrictivos.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_ultra_method_async(entity_id))

    async def extract_users_ultra_method_async(self, entity_id):
        """
        Método ultra no convencional para canales extremadamente restrictivos.
        
        Args:
            entity_id: ID de la entidad
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            import re
            from telethon.tl.types import PeerChannel, User
            from telethon.tl.functions.channels import GetFullChannelRequest
            
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"\n{'='*50}")
            print(f" EXTRACCIÓN ULTRA NO CONVENCIONAL PARA: {entity_title} ")
            print(f"{'='*50}")
            print("Este método utiliza técnicas especializadas para canales muy restrictivos.")
            
            # 1. FASE: Analizar metadata del canal para encontrar pistas
            print("\n[FASE 1] Analizando metadata del canal...")
            
            users_found = []
            channel_info = {}
            
            try:
                # Obtener información completa del canal
                full_info = await self.client(GetFullChannelRequest(channel=entity))
                
                # Extraer información básica
                channel_info = {
                    'id': entity.id,
                    'title': entity.title,
                    'username': getattr(entity, 'username', None),
                    'about': full_info.full_chat.about if hasattr(full_info, 'full_chat') and hasattr(full_info.full_chat, 'about') else None,
                    'members_count': full_info.full_chat.participants_count if hasattr(full_info, 'full_chat') else 0,
                    'linked_chat_id': full_info.full_chat.linked_chat_id if hasattr(full_info, 'full_chat') and hasattr(full_info.full_chat, 'linked_chat_id') else None
                }
                
                print(f"Información obtenida: Título: {channel_info['title']}")
                if channel_info['username']:
                    print(f"Username: @{channel_info['username']}")
                if channel_info['about']:
                    print(f"Descripción: {channel_info['about'][:100]}...")
                if channel_info['members_count']:
                    print(f"Miembros aproximados: {channel_info['members_count']}")
                
                # Verificar si tiene un chat de discusión vinculado
                if channel_info['linked_chat_id']:
                    print(f"Chat de discusión vinculado detectado (ID: {channel_info['linked_chat_id']})")
                    try:
                        linked_chat = await self.client.get_entity(channel_info['linked_chat_id'])
                        print(f"Chat vinculado: {linked_chat.title}")
                        
                        # Intentar extraer miembros del chat vinculado
                        # print("Intentando extraer usuarios del chat vinculado...")
                        # await self.extract_members_from_linked_chat(channel_info['linked_chat_id'], entity_id, entity_title)

                        # Intentar extraer miembros del chat vinculado
                        print("Intentando extraer usuarios del chat vinculado...")
                        linked_users_count = await self.extract_members_from_linked_chat(channel_info['linked_chat_id'], entity_id, entity_title)
                        
                        # Si encontramos usuarios, añadirlos a nuestro contador
                        users_found.extend([1] * linked_users_count)  # Solo para contar, no necesitamos los objetos reales
                    except Exception as e:
                        print(f"No se pudo acceder al chat vinculado: {e}")
                
            except Exception as e:
                print(f"Error obteniendo metadata completa: {e}")
            
            # 2. FASE: Extracción a través de canales relacionados
            print("\n[FASE 2] Buscando canales relacionados por palabras clave...")
            
            # Extraer palabras clave del título y descripción
            keywords = set()
            
            # Del título
            if entity_title:
                # Excluir palabras comunes
                common_words = {'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'de', 'del', 'al', 'a', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'tras', 'pro', 'según', 'the', 'of', 'and', 'or', 'for', 'to', 'in', 'on', 'at', 'by', 'with', 'without', 'from, it'}
                
                # Extraer palabras significativas (al menos 4 caracteres, no en lista de comunes)
                words = re.findall(r'\w+', entity_title.lower())
                keywords.update(word for word in words if len(word) >= 4 and word not in common_words)
            
            # De la descripción
            if channel_info.get('about'):
                words = re.findall(r'\w+', channel_info['about'].lower())
                keywords.update(word for word in words if len(word) >= 4 and word not in common_words)
            
            # Si hay un username, añadirlo como palabra clave
            if channel_info.get('username'):
                keywords.add(channel_info['username'].lower())
            
            print(f"Palabras clave extraídas: {', '.join(keywords)}")
            
            # Buscar canales relacionados usando las palabras clave
            related_entities = []
            
            for keyword in list(keywords)[:5]:  # Limitar a las 5 primeras palabras clave
                try:
                    print(f"Buscando canales relacionados con palabra clave: '{keyword}'")
                    from telethon.tl.functions.contacts import SearchRequest
                    
                    results = await self.client(SearchRequest(
                        q=keyword,
                        limit=10
                    ))
                    
                    if hasattr(results, 'chats'):
                        for chat in results.chats:
                            if chat.id != int(entity_id) and chat.id not in [e.id for e in related_entities]:
                                related_entities.append(chat)
                                print(f"Canal relacionado encontrado: {chat.title}")
                except Exception as e:
                    print(f"Error buscando con palabra clave '{keyword}': {e}")
                
                await asyncio.sleep(1)
            
            print(f"Se encontraron {len(related_entities)} canales potencialmente relacionados")
            
            # 3. FASE: Analizar mensajes buscando patrones específicos
            print("\n[FASE 3] Analizando patrones en mensajes...")
            
            # Obtener mensajes y analizarlos para encontrar patrones de contenido
            try:
                messages = await self.client.get_messages(entity, limit=50)
                print(f"Analizando {len(messages)} mensajes recientes...")
                
                # Patrones específicos que podrían indicar usuarios
                # Buscar menciones especiales como "via @username" o "Shared by @username"
                mention_patterns = [
                    r'via\s+@(\w+)',
                    r'by\s+@(\w+)',
                    r'from\s+@(\w+)',
                    r'courtesy\s+of\s+@(\w+)',
                    r'gracias\s+a\s+@(\w+)',
                    r'vía\s+@(\w+)',
                    r'por\s+@(\w+)',
                    r'fuente:?\s+@(\w+)',
                    r'source:?\s+@(\w+)',
                    r'credit:?\s+@(\w+)',
                    r'crédito:?\s+@(\w+)',
                    r'autor:?\s+@(\w+)',
                    r'author:?\s+@(\w+)',
                    r'owner:?\s+@(\w+)',
                    r'creator:?\s+@(\w+)',
                    r'creador:?\s+@(\w+)',
                    r'contact:?\s+@(\w+)',
                    r'contacto:?\s+@(\w+)',
                    r'admin:?\s+@(\w+)',
                    r'mod:?\s+@(\w+)',
                    r'moderator:?\s+@(\w+)',
                    r'moderador:?\s+@(\w+)',
                    r'partner:?\s+@(\w+)',
                    r'socio:?\s+@(\w+)',
                    r'colaborador:?\s+@(\w+)',
                    r'collaborator:?\s+@(\w+)',
                    r'help:?\s+@(\w+)',
                    r'ayuda:?\s+@(\w+)',
                    r'support:?\s+@(\w+)',
                    r'soporte:?\s+@(\w+)',
                    r'join:?\s+@(\w+)',
                    r'unirse:?\s+@(\w+)',
                    r'follow:?\s+@(\w+)',
                    r'seguir:?\s+@(\w+)',
                    r'team:?\s+@(\w+)',
                    r'equipo:?\s+@(\w+)'
                ]
                
                # Buscar estos patrones en los mensajes
                for msg in messages:
                    if msg.text:
                        for pattern in mention_patterns:
                            matches = re.finditer(pattern, msg.text.lower())
                            for match in matches:
                                username = match.group(1)
                                try:
                                    print(f"Mención especial encontrada: @{username}")
                                    user = await self.client.get_entity(f"@{username}")
                                    if not hasattr(user, 'bot') or not user.bot:
                                        users_found.append(user)
                                        # Procesar usuario
                                        self.process_member(user, entity_id, entity_title, False)
                                        print(f"Usuario procesado vía mención especial: {user.first_name} (@{user.username})")
                                except:
                                    pass
                
                # También analizar menciones en la firma del canal
                if channel_info.get('about'):
                    for pattern in mention_patterns:
                        matches = re.finditer(pattern, channel_info['about'].lower())
                        for match in matches:
                            username = match.group(1)
                            try:
                                user = await self.client.get_entity(f"@{username}")
                                if not hasattr(user, 'bot') or not user.bot:
                                    users_found.append(user)
                                    # Procesar usuario
                                    self.process_member(user, entity_id, entity_title, True)  # Asumimos que son admin o importantes
                                    print(f"Usuario procesado vía mención en descripción: {user.first_name} (@{user.username})")
                            except:
                                pass
                                
            except Exception as e:
                print(f"Error analizando mensajes: {e}")

             # 4. FASE: Mejorada - Análisis de reacciones
            print("\n[FASE 4] Analizando reacciones a mensajes...")
            reaction_users_count = await self.extract_users_from_reactions(entity_id)
            users_found.extend([1] * reaction_users_count)  # Solo para contar
            
            # 5. FASE: Analizar canales relacionados en busca de usuarios comunes
            if related_entities:
                print("\n[FASE 4] Analizando canales relacionados buscando usuarios comunes...")
                
                print("\n[FASE 5] Análisis avanzado de canales relacionados...")
                related_users_count = await self.process_related_channels(entity_id, related_entities)
                users_found.extend([1] * related_users_count)  # Solo para contar
            
            # Resumen final
            total_users = len([u for u in users_found if isinstance(u, User)]) + len([u for u in users_found if isinstance(u, int)])
            
            print(f"\n{'-'*50}")
            print(f"Método ultra no convencional finalizado.")
            print(f"Se encontraron y procesaron {total_users} usuarios potenciales.")
            
            if total_users == 0:
                print("\nRecomendaciones para este canal especialmente restrictivo:")
                print("1. Intenta unirte al canal si es posible")
                print("2. Busca el chat de discusión vinculado (si existe)")
                print("3. Busca canales o grupos del mismo creador")
                print("4. Considera métodos manuales de monitoreo constante")
            
            return total_users
            
        except Exception as e:
            logger.error(f"Error en método ultra no convencional: {e}")
            traceback.print_exc()
            return 0

    def extract_members_from_linked_chat(self, linked_chat_id, original_entity_id, original_entity_title):
        """
        Intenta extraer usuarios del chat de discusión vinculado a un canal.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            linked_chat_id: ID del chat vinculado
            original_entity_id: ID de la entidad original
            original_entity_title: Título de la entidad original
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_members_from_linked_chat_async(linked_chat_id, original_entity_id, original_entity_title))

    async def extract_members_from_linked_chat_async(self, linked_chat_id, original_entity_id, original_entity_title):
        """
        Intenta extraer usuarios del chat de discusión vinculado a un canal.
        
        Args:
            linked_chat_id: ID del chat vinculado
            original_entity_id: ID de la entidad original
            original_entity_title: Título de la entidad original
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            linked_entity = await self.client.get_entity(int(linked_chat_id))
            print(f"Analizando chat vinculado: {linked_entity.title}")
            
            users_found = []
            
            # Obtener access_hash para operaciones de bajo nivel
            linked_access_hash = 0
            if hasattr(linked_entity, 'access_hash'):
                linked_access_hash = linked_entity.access_hash
            
            # Método 1: Usando Telethon de manera estándar
            try:
                print("Intentando método estándar de Telethon...")
                participants = await self.client.get_participants(linked_entity, limit=50)
                
                for user in participants:
                    if not user.bot:
                        # Procesar este miembro para el canal original
                        self.process_member(user, original_entity_id, original_entity_title, False)
                        users_found.append(user)
                
                print(f"Se encontraron {len(users_found)} usuarios en el chat vinculado con Telethon")
                
                if len(users_found) > 0:
                    return len(users_found)  # Si encontramos suficientes, no seguir con métodos más complejos
                    
            except Exception as e:
                print(f"Método estándar de Telethon falló: {e}")
            
            # Método 2: Usando Pyrogram con mejor manejo de errores
            try:
                print("Intentando con Pyrogram...")
                # Cargar credenciales
                with open(CREDENTIAL_FILE, 'r') as f:
                    credentials = json.load(f)
                
                async with Client(
                    "linked_chat_extractor",
                    api_id=credentials['api_id'],
                    api_hash=credentials['api_hash'],
                    phone_number=credentials['phone']
                ) as app:
                    try:
                        # PASO CRÍTICO: Asegurarnos de que Pyrogram reconozca el chat
                        try:
                            # Intentar obtener el chat directamente - opción más segura
                            chat = await app.get_chat(int(linked_chat_id))
                            print(f"Chat obtenido correctamente: {chat.title}")
                            
                            # Una vez que el chat es reconocido, intentar obtener miembros
                            pyrogram_users = []
                            
                            async for member in app.get_chat_members(chat.id, limit=50):
                                if not member.user.is_bot:
                                    # Convertir a formato compatible con Telethon
                                    telethon_user = type('', (), {})()
                                    telethon_user.id = member.user.id
                                    telethon_user.first_name = member.user.first_name
                                    telethon_user.last_name = member.user.last_name if member.user.last_name else ""
                                    telethon_user.username = member.user.username if member.user.username else ""
                                    telethon_user.bot = member.user.is_bot
                                    
                                    # Verificar si ya lo tenemos
                                    if telethon_user.id not in [u.id for u in users_found]:
                                        self.process_member(telethon_user, original_entity_id, original_entity_title, False)
                                        users_found.append(telethon_user)
                                        pyrogram_users.append(telethon_user)
                            
                            print(f"Se encontraron {len(pyrogram_users)} usuarios adicionales con Pyrogram")
                            
                        except Exception as e:
                            print(f"Error en método de alto nivel de Pyrogram: {e}")
                            
                            # Método alternativo: Construir el peer manualmente
                            if linked_access_hash > 0:
                                print("Intentando método de bajo nivel con access_hash...")
                                
                                from pyrogram.raw.types.input_peer_channel import InputPeerChannel
                                from pyrogram.raw.functions.channels.get_participants import GetParticipants
                                from pyrogram.raw.types.channel_participants_recent import ChannelParticipantsRecent
                                
                                try:
                                    peer = InputPeerChannel(
                                        channel_id=int(linked_chat_id),
                                        access_hash=linked_access_hash
                                    )
                                    
                                    # Usar GetParticipants de bajo nivel
                                    result = await app.invoke(
                                        GetParticipants(
                                            channel=peer,
                                            filter=ChannelParticipantsRecent(),
                                            offset=0,
                                            limit=100,
                                            hash=0
                                        )
                                    )
                                    
                                    if hasattr(result, 'users') and result.users:
                                        mtproto_users = []
                                        
                                        for user in result.users:
                                            if not getattr(user, 'bot', False):
                                                # Convertir a formato compatible
                                                telethon_user = type('', (), {})()
                                                telethon_user.id = user.id
                                                telethon_user.first_name = getattr(user, 'first_name', "")
                                                telethon_user.last_name = getattr(user, 'last_name', "")
                                                telethon_user.username = getattr(user, 'username', "")
                                                telethon_user.bot = getattr(user, 'bot', False)
                                                
                                                # Verificar si ya lo tenemos
                                                if telethon_user.id not in [u.id for u in users_found]:
                                                    self.process_member(telethon_user, original_entity_id, original_entity_title, False)
                                                    users_found.append(telethon_user)
                                                    mtproto_users.append(telethon_user)
                                        
                                        print(f"Se encontraron {len(mtproto_users)} usuarios con método de bajo nivel")
                                
                                except Exception as e:
                                    print(f"Error en método de bajo nivel: {e}")
                    
                    except Exception as e:
                        print(f"Error general con Pyrogram: {e}")
                        
            except Exception as e:
                print(f"Error inicializando Pyrogram: {e}")
            
            # Método 3: Análisis de mensajes si los métodos anteriores devuelven pocos usuarios
            if len(users_found) < 10:
                try:
                    print("Analizando mensajes para descubrir más usuarios...")
                    
                    # Obtener mensajes del chat vinculado
                    linked_messages = await self.client.get_messages(linked_entity, limit=100)
                    
                    message_users = set()
                    
                    for msg in linked_messages:
                        # Procesar remitente
                        if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                            try:
                                user = await self.client.get_entity(msg.sender_id)
                                if not user.bot and user.id not in message_users:
                                    message_users.add(user.id)
                                    
                                    # Verificar si ya lo tenemos
                                    if user.id not in [u.id for u in users_found]:
                                        self.process_member(user, original_entity_id, original_entity_title, False)
                                        users_found.append(user)
                            except Exception:
                                pass
                        
                        # Procesar menciones en el mensaje
                        if msg.entities:
                            for entity in msg.entities:
                                if hasattr(entity, 'user_id'):  # Menciones que incluyen una referencia directa al usuario
                                    try:
                                        user = await self.client.get_entity(entity.user_id)
                                        if not user.bot and user.id not in message_users:
                                            message_users.add(user.id)
                                            
                                            # Verificar si ya lo tenemos
                                            if user.id not in [u.id for u in users_found]:
                                                self.process_member(user, original_entity_id, original_entity_title, False)
                                                users_found.append(user)
                                    except Exception:
                                        pass
                                elif hasattr(entity, 'type') and entity.type == 'mention':
                                    # Extraer username de la mención
                                    try:
                                        start = entity.offset
                                        end = entity.offset + entity.length
                                        if start < len(msg.text) and end <= len(msg.text):
                                            mention = msg.text[start:end]
                                            if mention.startswith('@'):
                                                username = mention[1:]
                                                try:
                                                    user = await self.client.get_entity(username)
                                                    if not user.bot and user.id not in message_users:
                                                        message_users.add(user.id)
                                                        
                                                        # Verificar si ya lo tenemos
                                                        if user.id not in [u.id for u in users_found]:
                                                            self.process_member(user, original_entity_id, original_entity_title, False)
                                                            users_found.append(user)
                                                except Exception:
                                                    pass
                                    except Exception:
                                        pass
                    
                    print(f"Se encontraron {len(message_users)} usuarios adicionales analizando mensajes")
                    
                except Exception as e:
                    print(f"Error analizando mensajes: {e}")
            
            print(f"Análisis del chat vinculado completado. Total de usuarios encontrados: {len(users_found)}")
            return len(users_found)
            
        except Exception as e:
            print(f"Error accediendo al chat vinculado: {e}")
            return 0

    def process_related_channels(self, entity_id, related_entities):
        """
        Procesa canales relacionados y extrae usuarios de manera más efectiva.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            entity_id: ID de la entidad
            related_entities: Lista de entidades relacionadas
        
        Returns:
            Número de usuarios encontrados
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.process_related_channels_async(entity_id, related_entities))

    async def process_related_channels_async(self, entity_id, related_entities):
        """
        Procesa canales relacionados y extrae usuarios de manera más efectiva.
        
        Args:
            entity_id: ID de la entidad
            related_entities: Lista de entidades relacionadas
        
        Returns:
            Número de usuarios encontrados
        """
        try:
            from telethon.tl.functions.channels import GetParticipantRequest
            from telethon.errors import UserNotParticipantError
            
            entity = await self.client.get_entity(int(entity_id))
            entity_title = entity.title
            
            print(f"\nProcesando {len(related_entities)} canales relacionados para {entity_title}...")
            
            # Categorizar los canales relacionados por relevancia
            categorized_channels = {
                "alta": [],   # Alta probabilidad de usuarios comunes
                "media": [],  # Media probabilidad
                "baja": []    # Baja probabilidad
            }
            
            # Palabras clave específicas para determinar relevancia
            high_relevance_keywords = ['call', 'signals', 'alert', 'crypto', 'token', 'channel', 'gem']
            
            # Analizar cada canal y categorizar
            for channel in related_entities:
                relevance = "baja"
                
                # Verificar título
                title_lower = channel.title.lower()
                
                # Si tiene palabras muy similares al canal original
                if any(keyword in title_lower for keyword in high_relevance_keywords):
                    relevance = "alta"
                # Si tiene el mismo prefijo/sufijo que el canal original
                elif entity_title.lower().split()[0] in title_lower or (
                    len(entity_title.split()) > 1 and entity_title.lower().split()[-1] in title_lower):
                    relevance = "alta"
                # Si es del mismo creador/comunidad
                elif hasattr(channel, 'username') and channel.username and hasattr(entity, 'username') and entity.username:
                    # Verificar similitud en usernames
                    if (channel.username[:4] == entity.username[:4] or 
                        channel.username[-4:] == entity.username[-4:]):
                        relevance = "alta"
                # Media relevancia para el resto que pasó el filtro inicial
                else:
                    relevance = "media"
                    
                categorized_channels[relevance].append(channel)
            
            # Procesar canales por orden de relevancia
            user_sources = {}  # Rastrear en qué canales se encontró cada usuario
            all_users = []
            
            # Empezar con los más relevantes
            for relevance in ["alta", "media", "baja"]:
                channels = categorized_channels[relevance]
                if not channels:
                    continue
                    
                print(f"\nAnalizando {len(channels)} canales de relevancia {relevance}...")
                
                for i, channel in enumerate(channels[:5 if relevance == "alta" else 3]):  # Limitar por relevancia
                    try:
                        print(f"Analizando canal ({i+1}/{min(5 if relevance == 'alta' else 3, len(channels))}): {channel.title}")
                        
                        # Intentar diferentes métodos según la relevancia
                        if relevance == "alta":
                            # Para canales de alta relevancia, intentar todos los métodos
                            
                            # Método 1: Obtener participantes directamente
                            try:
                                participants = await self.client.get_participants(channel, limit=50)
                                for user in participants:
                                    if not user.bot:
                                        if user.id not in user_sources:
                                            user_sources[user.id] = []
                                        user_sources[user.id].append(channel.title)
                                        
                                        if user.id not in [u.id for u in all_users]:
                                            all_users.append(user)
                                            print(f"Usuario encontrado: {user.first_name} (@{user.username or 'sin username'})")
                            except Exception as e:
                                # Método 2: Analizar mensajes
                                try:
                                    messages = await self.client.get_messages(channel, limit=30)
                                    for msg in messages:
                                        if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                                            try:
                                                user = await self.client.get_entity(msg.sender_id)
                                                if not user.bot:
                                                    if user.id not in user_sources:
                                                        user_sources[user.id] = []
                                                    user_sources[user.id].append(channel.title)
                                                    
                                                    if user.id not in [u.id for u in all_users]:
                                                        all_users.append(user)
                                                        print(f"Usuario encontrado en mensajes: {user.first_name}")
                                            except:
                                                pass
                                except:
                                    pass
                        else:
                            # Para canales de relevancia media/baja, solo analizar mensajes recientes
                            try:
                                messages = await self.client.get_messages(channel, limit=15)
                                for msg in messages:
                                    if msg.sender_id and not isinstance(msg.sender_id, PeerChannel):
                                        try:
                                            user = await self.client.get_entity(msg.sender_id)
                                            if not user.bot:
                                                if user.id not in user_sources:
                                                    user_sources[user.id] = []
                                                user_sources[user.id].append(channel.title)
                                                
                                                if user.id not in [u.id for u in all_users]:
                                                    all_users.append(user)
                                                    print(f"Usuario encontrado en canal {relevance}: {user.first_name}")
                                        except:
                                            pass
                            except:
                                pass
                                
                    except Exception as e:
                        print(f"Error analizando canal: {e}")
                    
                    # Pausa entre canales
                    await asyncio.sleep(1)
            
            # Procesar usuarios encontrados
            users_processed = 0
            
            print(f"\nEncontrados {len(all_users)} usuarios potenciales en canales relacionados")
            print("Verificando su presencia en nuestro canal objetivo...")
            
            # Determinar usuarios más probables basándose en el número de canales donde aparecen
            for user in all_users:
                # Calcular probabilidad basado en apariciones
                channels_found = len(user_sources.get(user.id, []))
                
                # Alta probabilidad: encontrado en 2+ canales o en un canal de alta relevancia
                if channels_found >= 2 or any(channel in user_sources.get(user.id, []) 
                                        for channel in [c.title for c in categorized_channels["alta"]]):
                    try:
                        # Intentar verificar si está también en el canal objetivo
                        try:
                            participant = await self.client(GetParticipantRequest(
                                channel=entity,
                                participant=user.id
                            ))
                            
                            # Confirmado que está en el canal
                            self.process_member(user, entity_id, entity_title, False)
                            print(f"✓ Usuario confirmado: {user.first_name} (@{user.username or 'sin username'})")
                            users_processed += 1
                        except UserNotParticipantError:
                            # Sabemos que NO está en el canal
                            pass
                        except Exception as e:
                            # Error ambiguo - posiblemente restrictivo
                            # Alta probabilidad: registrar con indicador
                            if channels_found >= 2:
                                # Si está en múltiples canales relacionados, considerarlo probable
                                self.process_member(user, entity_id, entity_title, False, is_probable=True)
                                print(f"? Usuario probable (en {channels_found} canales relacionados): {user.first_name}")
                                users_processed += 1
                    except Exception as e:
                        print(f"Error verificando usuario: {e}")
                    
                    # Pausa entre verificaciones
                    await asyncio.sleep(0.5)
            
            print(f"Procesamiento completado. {users_processed} usuarios añadidos.")
            return users_processed
        except Exception as e:
            print(f"Error procesando canales relacionados: {e}")
            traceback.print_exc()
            return 0

    def add_related_channels_to_database(self, related_entities):
        """
        Añade canales relacionados a la base de datos de entidades.
        Versión síncrona que llama a la implementación asíncrona.
        
        Args:
            related_entities: Lista de entidades relacionadas
        
        Returns:
            Número de canales añadidos
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.add_related_channels_to_database_async(related_entities))

    async def add_related_channels_to_database_async(self, related_entities):
        """
        Añade canales relacionados a la base de datos de entidades.
        
        Args:
            related_entities: Lista de entidades relacionadas
        
        Returns:
            Número de canales añadidos
        """
        try:
            print("\nAñadiendo canales relacionados a la base de datos...")
            
            channels_added = 0
            
            for entity in related_entities:
                try:
                    # Verificar si ya existe en nuestra base de datos
                    if str(entity.id) in self.entities:
                        continue
                    
                    # Procesar entidad y añadirla a la base de datos
                    result = await self.process_entity(entity, "related_channel")
                    
                    if result:
                        channels_added += 1
                        print(f"Canal añadido: {entity.title}")
                except Exception as e:
                    print(f"Error añadiendo canal: {e}")
                
                # Pausa entre procesamientos
                await asyncio.sleep(0.5)
            
            print(f"\nSe añadieron {channels_added} nuevos canales a la base de datos.")
            return channels_added
        
        except Exception as e:
            print(f"Error añadiendo canales relacionados: {e}")
            return 0
        

    # 5.3 MÉTODOS OBSOLETOS (MANTENERLOS POR COMPATIBILIDAD PERO MARCARLOS COMO DEPRECATED)

    def extract_users_from_historic_messages(self, entity_id, depth=5, messages_per_batch=100):
        """
        [DEPRECATED] Utilizar extract_users_from_messages_comprehensive en su lugar.
        Analiza mensajes históricos del canal/grupo para extraer usuarios.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_from_messages_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_historic_messages_async(entity_id, depth, messages_per_batch))

    async def extract_users_from_historic_messages_async(self, entity_id, depth=5, messages_per_batch=100):
        """
        [DEPRECATED] Versión asíncrona del método obsoleto.
        """
        # Implementar redirección a la nueva función
        return await self.extract_users_from_messages_comprehensive_async(entity_id, depth, messages_per_batch)

    def extract_messages_and_users(self, entity_id, depth=5, messages_per_batch=100):
        """
        [DEPRECATED] Utilizar extract_users_from_messages_comprehensive en su lugar.
        Método optimizado para extraer usuarios a partir del análisis de mensajes.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_from_messages_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_messages_comprehensive_async(entity_id, depth, messages_per_batch))

    def extract_users_from_reactions(self, entity_id):
        """
        [DEPRECATED] Utilizar extract_users_from_reactions_comprehensive en su lugar.
        Extrae usuarios que han reaccionado a mensajes.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_from_reactions_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_reactions_comprehensive_async(entity_id))

    def extract_users_from_reactions_improved(self, entity_id):
        """
        [DEPRECATED] Utilizar extract_users_from_reactions_comprehensive en su lugar.
        Versión mejorada para extraer usuarios que han reaccionado a mensajes.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_from_reactions_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_from_reactions_comprehensive_async(entity_id))

    def extract_users_by_association(self, entity_id):
        """
        [DEPRECATED] Utilizar extract_users_by_association_comprehensive en su lugar.
        Busca usuarios por asociación con canales y grupos relacionados.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_by_association_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_by_association_comprehensive_async(entity_id))

    def extract_users_by_association_improved(self, entity_id):
        """
        [DEPRECATED] Utilizar extract_users_by_association_comprehensive en su lugar.
        Versión mejorada para buscar usuarios por asociación.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_by_association_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_by_association_comprehensive_async(entity_id))

    def extract_users_ultimate_non_admin(self, entity_id, duration_minutes=45):
        """
        [DEPRECATED] Utilizar extract_users_ultimate_comprehensive en su lugar.
        Método supremo original para extraer usuarios sin permisos de administrador.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_ultimate_comprehensive en su lugar", DeprecationWarning)
        return self.extract_users_ultimate_comprehensive(entity_id, duration_minutes)

    def extract_users_ultimate_improved(self, entity_id):
        """
        [DEPRECATED] Utilizar extract_users_ultimate_comprehensive en su lugar.
        Versión mejorada del método supremo para extraer usuarios.
        """
        import warnings
        warnings.warn("Función obsoleta, use extract_users_ultimate_comprehensive en su lugar", DeprecationWarning)
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.extract_users_ultimate_comprehensive_async(entity_id))
    
    ######################################################
    # SECCIÓN 6: ANÁLISIS Y VISUALIZACIÓN DE INFORMACIÓN #
    ######################################################
    
    def extract_channel_info(self, entity_id):
        """Extrae información detallada de un canal"""
        if entity_id not in self.entities:
            logger.warning(f"Entidad {entity_id} no encontrada en la base de datos")
            return False
        
        entity_data = self.entities[entity_id]
        title = entity_data.get('title', 'Unknown')
        entity_type = entity_data.get('type', '')
        username = entity_data.get('username', '')
        
        # Verificar si es un canal
        if entity_type != 'channel':
            print(f"Esta función es específica para canales. '{title}' es de tipo '{entity_type}'.")
            return False
        
        logger.info(f"Analizando canal: {title} ({entity_id})")
        print(f"\n=== ANÁLISIS DE CANAL: {title} ===")
        
        try:
            # Obtener la entidad
            if username:
                entity = self.client.get_entity(f"@{username}")
            else:
                entity = self.client.get_entity(int(entity_id))
            
            # 1. Obtener información detallada del canal
            try:
                full_channel = self.client(GetFullChannelRequest(channel=entity))
                about = full_channel.full_chat.about or "Sin descripción"
                subscribers_count = full_channel.full_chat.participants_count
                
                print(f"Descripción: {about}")
                print(f"Número de suscriptores: {subscribers_count}")
                
                # Actualizar información en la base de datos
                self.entities[entity_id]['members_count'] = subscribers_count
                self.entities[entity_id]['description'] = about
                self.update_entity_in_csv(entity_id, 'members_count', subscribers_count)
                self.update_entity_in_csv(entity_id, 'description', about)
                
            except Exception as e:
                logger.warning(f"No se pudo obtener información detallada: {e}")
                print("No se pudo obtener información detallada del canal.")
            
            # 2. Analizar los mensajes recientes
            print("\nAnalizando mensajes recientes...")
            message_count = int(input("Número de mensajes a analizar (por defecto 50): ") or 50)
            
            messages =  self.client.get_messages(entity, limit=message_count)
            logger.info(f"Se obtuvieron {len(messages)} mensajes recientes")
            
            if not messages:
                print("No se encontraron mensajes.")
                return False
            
            # Estadísticas de mensajes
            message_types = {}
            message_dates = []
            authors = set()
            forwarded_from = set()
            
            for msg in messages:
                # Tipo de mensaje
                msg_type = "texto"
                if msg.photo:
                    msg_type = "foto"
                elif msg.video:
                    msg_type = "video"
                elif msg.document:
                    msg_type = "documento"
                elif msg.poll:
                    msg_type = "encuesta"
                
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
                message_dates.append(msg.date)
                
                # Autor del mensaje
                if msg.post_author:
                    authors.add(msg.post_author)
                
                # Si es reenviado, registrar origen
                if hasattr(msg, 'forward') and msg.forward:
                    if hasattr(msg.forward, 'from_name') and msg.forward.from_name:
                        forwarded_from.add(msg.forward.from_name)
            
            # Mostrar estadísticas de mensajes
            print("\n--- Estadísticas de Mensajes ---")
            print(f"Total de mensajes analizados: {len(messages)}")
            
            print("\nTipos de mensajes:")
            for msg_type, count in message_types.items():
                percentage = (count / len(messages)) * 100
                print(f"- {msg_type}: {count} ({percentage:.1f}%)")
            
            # Frecuencia de publicación
            if len(message_dates) >= 2:
                first_date = message_dates[-1]
                last_date = message_dates[0]
                days_span = (last_date - first_date).days + 1
                if days_span > 0:
                    posts_per_day = len(messages) / days_span
                    print(f"\nFrecuencia de publicación: ~{posts_per_day:.1f} mensajes por día")
            
            # Autores
            if authors:
                print("\nAutores identificados:")
                for author in authors:
                    print(f"- {author}")
            
            # Reenvíos
            if forwarded_from:
                print("\nCanales/Usuarios de los que se reenvían mensajes:")
                for source in forwarded_from:
                    print(f"- {source}")
            
            # 3. Intentar obtener comentarios si el canal los tiene habilitados
            try:
                recent_message = messages[0]
                if recent_message.reply_to:
                    print("\nAnalizando comentarios en publicaciones...")
                    comments = self.client.get_messages(entity, reply_to=recent_message.id)
                    if comments:
                        commenters = set()
                        for comment in comments:
                            if comment.sender_id:
                                try:
                                    user = self.client.get_entity(comment.sender_id)
                                    username = user.username if hasattr(user, 'username') else None
                                    commenters.add(f"@{username}" if username else f"{user.first_name}")
                                except:
                                    pass
                        
                        if commenters:
                            print(f"Comentadores encontrados: {len(commenters)}")
                            for commenter in commenters:
                                print(f"- {commenter}")
                    else:
                        print("No se encontraron comentarios.")
            except Exception as e:
                logger.warning(f"No se pudieron analizar comentarios: {e}")
            
            print("\nAnálisis de canal completado.")
            return True
            
        except Exception as e:
            logger.error(f"Error analizando canal {title}: {e}")
            print(f"Error: {str(e)}")
            return False
    
    def analyze_unknown_entities(self):
        """Analiza entidades de tipo 'unknown' e intenta reclasificarlas"""
        
        
        unknown_entities = []
        # Recolectar todas las entidades de tipo unknown
        for entity_id, entity in self.entities.items():
            if entity.get('type') == 'unknown':
                unknown_entities.append(entity)
        
        if not unknown_entities:
            print("No hay entidades de tipo 'unknown' para analizar.")
            return
        
        print(f"\nSe encontraron {len(unknown_entities)} entidades de tipo 'unknown'")
        print("Analizando y intentando reclasificar...")
        
        reclassified = 0
        errors = 0
        
        for entity in unknown_entities:
            entity_id = entity.get('entity_id')
            title = entity.get('title', '')
            username = entity.get('username', '')
            
            try:
                # Intentar diferentes métodos para obtener la entidad de Telegram
                telegram_entity = None
                
                # Método 1: Intentar con username si está disponible
                if username:
                    try:
                        # Usar un manejo más seguro de errores
                        try:
                            telegram_entity = self.client.get_entity(f"@{username}")
                            print(f"Obtenida entidad {title} (@{username}) vía username")
                        except FloodWaitError as e:
                            print(f"Límite de API alcanzado, esperando {e.seconds} segundos...")
                            time.sleep(e.seconds)
                            continue
                    except Exception as e:
                        print(f"No se pudo obtener entidad vía username para {title}")
                
                # Método 2: Intentar con el ID si el método 1 falló
                if telegram_entity is None:
                    try:
                        # Asegurarse de que entity_id es un entero
                        numeric_id = int(entity_id)
                        
                        # Usar un enfoque más seguro para obtener la entidad
                        try:
                            # Buscar primero en diálogos existentes
                            dialogs = self.client.get_dialogs(limit=50)
                            for dialog in dialogs:
                                if hasattr(dialog, 'entity') and hasattr(dialog.entity, 'id') and dialog.entity.id == numeric_id:
                                    telegram_entity = dialog.entity
                                    print(f"Obtenida entidad {title} (ID:{entity_id}) vía diálogos")
                                    break
                        except Exception as e:
                            print(f"No se pudieron buscar diálogos: {str(e)}")
                        
                        # Si no se encontró en diálogos, intentar directamente con precaución
                        if telegram_entity is None:
                            try:
                                # Usar una pausa para evitar errores de flood
                                time.sleep(1.5)
                                telegram_entity = self.client.get_entity(numeric_id)
                                print(f"Obtenida entidad {title} (ID:{entity_id}) vía ID directo")
                            except Exception as e:
                                print(f"No se pudo obtener entidad vía ID para {title}")
                                errors += 1
                                continue  # Pasar a la siguiente entidad
                    except ValueError:
                        print(f"ID de entidad inválido para {title}: {entity_id}")
                        errors += 1
                        continue  # Pasar a la siguiente entidad
                
                # Si no pudimos obtener la entidad, continuar
                if telegram_entity is None:
                    print(f"No se pudo obtener información de {title} (ID:{entity_id})")
                    errors += 1
                    continue
                
                # Detectar tipo con más detalle
                new_type = "unknown"
                
                # Verificar atributos para clasificación
                if hasattr(telegram_entity, 'broadcast') and telegram_entity.broadcast:
                    new_type = "channel"
                elif hasattr(telegram_entity, 'megagroup') and telegram_entity.megagroup:
                    new_type = "megagroup"
                elif hasattr(telegram_entity, 'gigagroup') and telegram_entity.gigagroup:
                    new_type = "megagroup"
                elif hasattr(telegram_entity, 'forum') and telegram_entity.forum:
                    new_type = "forum"
                elif hasattr(telegram_entity, 'chat') or (hasattr(telegram_entity, 'title') and not hasattr(telegram_entity, 'broadcast')):
                    new_type = "group"
                
                # Si logramos reclasificar
                if new_type != "unknown":
                    # Actualizar en memoria
                    self.entities[entity_id]['type'] = new_type
                    reclassified += 1
                    
                    print(f"Reclasificado: '{title}' de 'unknown' a '{new_type}'")
                    
                    # También actualizar el archivo CSV
                    self.update_entity_in_csv(entity_id, 'type', new_type)
                else:
                    print(f"No se pudo determinar el tipo para {title}")
                
                # Pausa para evitar límites de API
                time.sleep(2)
                
            except Exception as e:
                logger.warning(f"No se pudo analizar la entidad {entity_id} ({title}): {e}")
                errors += 1
        
        print(f"\nAnálisis completado. Se reclasificaron {reclassified} de {len(unknown_entities)} entidades.")
        if errors > 0:
            print(f"Se encontraron {errors} errores durante el proceso.")

        # Recomendar reiniciar si hay errores
        if errors > 0 and reclassified == 0:
            print("\nRecomendación: Si no se pudo reclasificar ninguna entidad, prueba a:")
            print("1. Reiniciar la aplicación para establecer una nueva sesión con Telegram")
            print("2. Esperar unos minutos antes de volver a intentarlo")
            print("3. Procesar un número más pequeño de entidades a la vez")
            
    
    def display_entities(self, filter_criteria=None):
        """Muestra las entidades descubiertas con filtros opcionales"""
        if not self.entities:
            print("No hay entidades para mostrar.")
            return []
        
        filtered_entities = []
        
        # Aplicar filtros si existen
        if filter_criteria:
            for entity_id, entity in self.entities.items():
                match = True
                for key, value in filter_criteria.items():
                    if key in entity and str(entity[key]).lower() != str(value).lower():
                        match = False
                        break
                if match:
                    filtered_entities.append(entity)
        else:
            filtered_entities = list(self.entities.values())
        
        # Ordenar por número de miembros (si es posible)
        try:
            filtered_entities.sort(key=lambda x: int(x.get('members_count', 0)), reverse=True)
        except:
            pass
        
        # Mostrar entidades
        print(f"\n=== ENTIDADES ({len(filtered_entities)}) ===")
        for i, entity in enumerate(filtered_entities, 1):
            username = entity.get('username', '')
            title = entity.get('title', '')
            entity_type = entity.get('type', '')
            members = entity.get('members_count', 'N/A')
            category = entity.get('category', '')
            language = entity.get('language', '')
            
            print(f"{i}. {title} (@{username})")
            print(f"   Tipo: {entity_type}, Miembros: {members}")
            print(f"   Categoría: {category}, Idioma: {language}")
            print(f"   Enlace: https://t.me/{username}")
            print()
        
        return filtered_entities
    
    def display_members(self, entity_id=None, filter_by_role=None, filter_by_participation=None, limit=100):
        """Muestra los miembros extraídos con filtros opcionales"""
        if not self.members:
            print("No hay miembros para mostrar.")
            return []
        
        filtered_members = []
        
        # Aplicar filtros
        for key, member in self.members.items():
            include = True
            
            if entity_id and member.get('entity_id') != entity_id:
                include = False
            
            if filter_by_role and member.get('role') != filter_by_role:
                include = False
                
            if filter_by_participation and member.get('participation_type') != filter_by_participation:
                include = False
            
            if include:
                filtered_members.append(member)
        
        # Limitar resultados
        if limit and len(filtered_members) > limit:
            filtered_members = filtered_members[:limit]
        
        # Mostrar miembros
        entity_title = ""
        if entity_id and filtered_members:
            entity_title = filtered_members[0].get('entity_title', '')
            print(f"\n=== MIEMBROS DE {entity_title} ({len(filtered_members)}) ===")
        else:
            print(f"\n=== MIEMBROS ({len(filtered_members)}) ===")
        
        for i, member in enumerate(filtered_members, 1):
            username = member.get('username', '')
            first_name = member.get('first_name', '')
            last_name = member.get('last_name', '')
            role = member.get('role', 'regular')
            entity_title = member.get('entity_title', '')
            
            name = f"{first_name} {last_name}".strip()
            username_text = f"@{username}" if username else "[Sin username]"
            
            print(f"{i}. {name} ({username_text})")
            print(f"   Rol: {role}")
            if not entity_id:  # Solo mostrar entidad si no estamos filtrando por ella
                print(f"   Entidad: {entity_title}")
            print()
        
        return filtered_members
    
    def load_all_entities_from_csv(self):
        """
        Carga todas las entidades desde el archivo CSV, asegurando que tengamos la lista completa,
        no solo las que se cargaron al inicio o se han encontrado en esta sesión
        """
        try:
            # Verificar que el archivo existe
            if not os.path.exists(CHANNELS_CSV):
                print(f"El archivo {CHANNELS_CSV} no existe. No hay entidades para cargar.")
                return False
                
            # Contar entidades actualmente en memoria
            before_count = len(self.entities)
            
            # Cargar entidades desde el CSV
            with open(CHANNELS_CSV, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    entity_id = row.get('entity_id')
                    if entity_id and entity_id not in self.entities:
                        self.entities[entity_id] = row
            
            # Contar cuántas nuevas entidades se cargaron
            after_count = len(self.entities)
            new_loaded = after_count - before_count
            
            if new_loaded > 0:
                print(f"Se cargaron {new_loaded} entidades adicionales desde {CHANNELS_CSV}")
            
            logger.info(f"Total de entidades en memoria después de cargar CSV: {after_count}")
            return True
        except Exception as e:
            print(f"Error cargando entidades desde CSV: {e}")
            logger.error(f"Error en load_all_entities_from_csv: {e}")
            traceback.print_exc()
            return False
        
    def join_entity_with_csv_data(self, entity_id):
        """
        Versión mejorada de join_entity que considera datos del CSV
        Args:
            entity_id: ID de la entidad o índice en la lista mostrada
        Returns:
            bool: True si se unió correctamente, False en caso contrario
        """
        try:
            # Primero cargar todas las entidades desde CSV para asegurar datos completos
            self.load_all_entities_from_csv()
            
            # Buscar la entidad en nuestra base de datos
            if entity_id in self.entities:
                entity_data = self.entities[entity_id]
            else:
                print(f"No se encontró entidad con ID {entity_id}")
                return False
            
            # Extraer información relevante
            username = entity_data.get('username', '')
            invite_link = entity_data.get('invite_link', '')
            title = entity_data.get('title', 'Entidad desconocida')
            
            print(f"Intentando unirse a: {title}")
            
            # Estrategia 1: Si tiene username, intentar unirse por ese método
            if username:
                print(f"Intentando unirse mediante username: @{username}")
                join_success = self.join_entity(username)
                if join_success:
                    return True
            
            # Estrategia 2: Si tiene enlace de invitación, intentar usarlo
            if invite_link and invite_link.startswith("https://t.me/"):
                print(f"Intentando unirse mediante enlace de invitación: {invite_link}")
                
                # Determinar tipo de enlace
                if '/joinchat/' in invite_link or 't.me/+' in invite_link:
                    # Es un enlace de invitación privado
                    join_success = self.join_via_invite_link(invite_link)
                else:
                    # Podría ser un enlace público con formato https://t.me/username
                    username_from_link = invite_link.split('t.me/')[1].split('?')[0].split('/')[0]
                    if username_from_link:
                        join_success = self.join_entity(username_from_link)
                    else:
                        join_success = False
                
                if join_success:
                    return True
            
            # Si llegamos aquí, ninguno de los métodos anteriores funcionó
            print(f"No se pudo unir a {title}. No se encontró un método válido de unión.")
            print("La entidad podría requerir una invitación personal o haber cambiado su configuración.")
            return False
        
        except Exception as e:
            logger.error(f"Error en join_entity_with_csv_data: {e}")
            print(f"Error al unirse: {str(e)}")
            return False
        
    

    def display_entities_from_csv(self, filter_criteria=None):
        """
        Muestra las entidades cargadas desde el CSV con filtros opcionales,
        asegurándose de cargar todas las entidades del archivo primero
        """
        # Primero, cargar todas las entidades del CSV
        self.load_all_entities_from_csv()
        
        if not self.entities:
            print("No hay entidades para mostrar.")
            return []
        
        filtered_entities = []
        
        # Aplicar filtros si existen
        if filter_criteria:
            for entity_id, entity in self.entities.items():
                match = True
                for key, value in filter_criteria.items():
                    if key in entity and str(entity[key]).lower() != str(value).lower():
                        match = False
                        break
                if match:
                    filtered_entities.append(entity)
        else:
            filtered_entities = list(self.entities.values())
        
        # Ordenar por número de miembros (si es posible)
        try:
            filtered_entities.sort(key=lambda x: int(x.get('members_count', 0)), reverse=True)
        except:
            pass
        
        # Mostrar entidades
        print(f"\n=== ENTIDADES ({len(filtered_entities)}) ===")
        for i, entity in enumerate(filtered_entities, 1):
            username = entity.get('username', '')
            title = entity.get('title', '')
            entity_type = entity.get('type', '')
            members = entity.get('members_count', 'N/A')
            category = entity.get('category', '')
            language = entity.get('language', '')
            
            print(f"{i}. {title} (@{username})")
            print(f"   Tipo: {entity_type}, Miembros: {members}")
            print(f"   Categoría: {category}, Idioma: {language}")
            print(f"   Enlace: https://t.me/{username}")
            print()
        
        return filtered_entities

    def display_joinable_entities_from_csv(self):
        """
        Muestra únicamente las entidades a las que el usuario aún no pertenece,
        asegurándose de cargar todas las entidades del CSV primero
        """
        # Primero, cargar todas las entidades del CSV
        # Primero, cargar todas las entidades del CSV
        self.load_all_entities_from_csv()
        
        if not self.entities:
            print("No hay entidades para mostrar.")
            return []
        
        # Obtener la lista de diálogos actuales (donde ya eres miembro)
        try:
            print("Obteniendo tus diálogos actuales...")
            dialogs = self.client.get_dialogs(limit=500)  # Ajustar según necesidad
            
            # Extraer los IDs y usernames de entidades donde ya eres miembro
            existing_entity_ids = set()
            existing_usernames = set()
            for dialog in dialogs:
                if hasattr(dialog.entity, 'id'):
                    existing_entity_ids.add(str(dialog.entity.id))
                if hasattr(dialog.entity, 'username') and dialog.entity.username:
                    existing_usernames.add(dialog.entity.username.lower())
            
            print(f"Tienes {len(existing_entity_ids)} diálogos actuales")
            
            # Filtrar entidades a las que podemos unirnos
            joinable_entities = []
            
            for entity_id, entity in self.entities.items():
                # Verificar si no eres miembro ya por ID
                if entity_id in existing_entity_ids:
                    continue
                    
                # Verificar si no eres miembro ya por username
                username = entity.get('username', '').lower()
                if username and username in existing_usernames:
                    continue
                
                # Verificar si tiene username o invite_link (para poder unirse)
                has_username = bool(username)
                has_invite_link = bool(entity.get('invite_link', '')) and entity.get('invite_link', '').startswith('https://t.me/')
                
                # Solo añadir si tiene algún método de unión
                if has_username or has_invite_link:
                    # Verificar si es un tipo válido
                    entity_type = entity.get('type', '')
                    if entity_type in ['channel', 'megagroup', 'group', 'forum']:
                        joinable_entities.append(entity)
            
            # Ordenar por número de miembros
            try:
                joinable_entities.sort(key=lambda x: int(x.get('members_count', 0)), reverse=True)
            except:
                pass
            
            # Mostrar entidades
            if not joinable_entities:
                print("\nNo se encontraron entidades a las que puedas unirte.")
                print("Asegúrate de buscar entidades primero.")
                return []
                
            print(f"\n=== ENTIDADES DISPONIBLES PARA UNIRSE ({len(joinable_entities)}) ===")
            for i, entity in enumerate(joinable_entities, 1):
                username = entity.get('username', '')
                title = entity.get('title', '')
                entity_type = entity.get('type', '')
                members = entity.get('members_count', 'N/A')
                category = entity.get('category', '')
                language = entity.get('language', '')
                invite_link = entity.get('invite_link', '')
                
                join_method = ""
                if username:
                    join_method = f"[@{username}]"
                elif invite_link:
                    join_method = "[Enlace de invitación]"
                
                print(f"{i}. {title} {join_method}")
                print(f"   Tipo: {entity_type}, Miembros: {members}")
                print(f"   Categoría: {category}, Idioma: {language}")
                if invite_link:
                    print(f"   Enlace: {invite_link}")
                elif username:
                    print(f"   Enlace: https://t.me/{username}")
                print()
            
            return joinable_entities
        except Exception as e:
            print(f"Error al obtener entidades para unirse: {e}")
            logger.error(f"Error en display_joinable_entities_from_csv: {e}")
            traceback.print_exc()
            return []


    
    def generate_statistics(self):
        """Genera estadísticas sobre las entidades descubiertas"""
        if not self.entities:
            print("No hay entidades para generar estadísticas.")
            return
        
        # Contar por tipo
        types_count = {}
        for entity_id, entity in self.entities.items():
            entity_type = entity.get('type', 'unknown')
            types_count[entity_type] = types_count.get(entity_type, 0) + 1
        
        # Contar por categoría
        categories_count = {}
        for entity_id, entity in self.entities.items():
            category = entity.get('category', 'unknown')
            categories_count[category] = categories_count.get(category, 0) + 1
        
        # Contar por idioma
        languages_count = {}
        for entity_id, entity in self.entities.items():
            language = entity.get('language', 'unknown')
            languages_count[language] = languages_count.get(language, 0) + 1
        
        # Imprimir estadísticas
        print("\n=== ESTADÍSTICAS DE ENTIDADES ===")
        print(f"Total de entidades: {len(self.entities)}")
        
        print("\nDistribución por tipo:")
        for t, count in sorted(types_count.items(), key=lambda x: x[1], reverse=True):
            print(f"- {t}: {count}")
        
        print("\nDistribución por categoría:")
        for c, count in sorted(categories_count.items(), key=lambda x: x[1], reverse=True):
            print(f"- {c}: {count}")
        
        print("\nDistribución por idioma:")
        for l, count in sorted(languages_count.items(), key=lambda x: x[1], reverse=True):
            print(f"- {l}: {count}")
    
    #############################
    # SECCIÓN 7: EXPORTACIÓN #
    #############################
    
    def export_filtered_data(self, entity_filter=None, member_filter=None, filename_prefix="telegram_export"):
        """Exporta datos filtrados a archivos CSV separados"""
        if self.entities:
            filtered_entities = []
            if entity_filter:
                for entity_id, entity in self.entities.items():
                    match = True
                    for key, value in entity_filter.items():
                        if key in entity and str(entity[key]).lower() != str(value).lower():
                            match = False
                            break
                    if match:
                        filtered_entities.append(entity)
            else:
                filtered_entities = list(self.entities.values())
            
            if filtered_entities:
                entities_filename = f"{filename_prefix}_entities.csv"
                try:
                    with open(entities_filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                        writer.writeheader()
                        for entity in filtered_entities:
                            # Asegurarse de que solo se escriban campos válidos
                            entity_data = {field: entity.get(field, '') for field in CSV_FIELDS}
                            writer.writerow(entity_data)
                    
                    print(f"Se exportaron {len(filtered_entities)} entidades a {entities_filename}")
                except Exception as e:
                    logger.error(f"Error exportando entidades: {e}")
                    print(f"Error: {str(e)}")
        
        # Exportar miembros filtrados
        if self.members:
            filtered_members = []
            if member_filter:
                for key, member in self.members.items():
                    match = True
                    for filter_key, filter_value in member_filter.items():
                        if filter_key in member and str(member[filter_key]).lower() != str(filter_value).lower():
                            match = False
                            break
                    if match:
                        filtered_members.append(member)
            else:
                filtered_members = list(self.members.values())
            
            # Si hay un filtro de entidad, aplicarlo también a los miembros
            if entity_filter and 'type' in entity_filter:
                entity_type = entity_filter['type']
                entity_ids = [entity_id for entity_id, entity in self.entities.items() 
                            if entity.get('type') == entity_type]
                filtered_members = [member for member in filtered_members 
                                if member.get('entity_id') in entity_ids]
            
            if filtered_members:
                members_filename = f"{filename_prefix}_members.csv"
                try:
                    with open(members_filename, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=MEMBER_FIELDS)
                        writer.writeheader()
                        for member in filtered_members:
                            # Asegurarse de que solo se escriban campos válidos
                            member_data = {field: member.get(field, '') for field in MEMBER_FIELDS}
                            writer.writerow(member_data)
                    
                    print(f"Se exportaron {len(filtered_members)} miembros a {members_filename}")
                except Exception as e:
                    logger.error(f"Error exportando miembros: {e}")
                    print(f"Error: {str(e)}")
    
    def generate_links_file(self, filtered_entities, filename):
        """Genera un archivo con enlaces para las entidades filtradas"""
        if not filtered_entities:
            print("No hay entidades para generar enlaces.")
            return
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                for entity in filtered_entities:
                    username = entity.get('username', '')
                    if username:
                        f.write(f"https://t.me/{username}\n")
            
            print(f"Se generaron enlaces para {len(filtered_entities)} entidades en {filename}")
        except Exception as e:
            logger.error(f"Error generando enlaces: {e}")
            print(f"Error: {str(e)}")
    
    def scrape_group_members(self):
        """Implementa la lógica de scraping de miembros"""
        print("\n=== SCRAPER DE MIEMBROS DE GRUPOS ===")
        
        try:
            # Obtener diálogos
            chats = []
            groups = []
            
            result = self.client(GetDialogsRequest(
                offset_date=None,
                offset_id=0,
                offset_peer=InputPeerEmpty(),
                limit=200,
                hash=0
            ))
            
            chats.extend(result.chats)
            
            # Filtrar grupos y canales
            for chat in chats:
                try:
                    if hasattr(chat, 'megagroup') or hasattr(chat, 'channel') or hasattr(chat, 'broadcast'):
                        groups.append(chat)
                except:
                    continue
            
            if len(groups) == 0:
                print("No se encontraron grupos o canales.")
                return
            
            # Mostrar grupos para selección
            print('Elige un grupo/canal para extraer miembros:')
            for i, g in enumerate(groups, 1):
                print(f"{i}- {g.title}")
            
            g_index = input("Ingresa un número: ")
            try:
                g_index = int(g_index)
                if g_index < 1 or g_index > len(groups):
                    print("Número inválido.")
                    return
            except ValueError:
                print("Por favor ingresa un número válido.")
                return
            
            target_group = groups[g_index-1]
            
            # Configuración adicional
            print("\nConfiguración de extracción:")
            include_admins = input("¿Incluir administradores? (s/n): ").lower() == 's'
            include_bots = input("¿Incluir bots? (s/n): ").lower() == 's'
            
            # Solicitar límite opcional de miembros
            try:
                limit_input = input("Número máximo de miembros a extraer (Enter para todos): ")
                member_limit = int(limit_input) if limit_input.strip() else None
            except ValueError:
                print("Valor inválido, se extraerán todos los miembros disponibles")
                member_limit = None
            
            # Extraer miembros
            print('\nObteniendo miembros...')
            
            # Extraer miembros directamente usando nuestra función
            count = self.extract_members_from_entity(target_group, limit=member_limit)
            
            print(f"\nSe han extraído y guardado {count} miembros en {MEMBERS_CSV}")
            print("Puedes usar este archivo para análisis o para añadir miembros a otros grupos.")
        
    
            
        except Exception as e:
            logger.error(f"Error al raspar miembros: {e}")
            traceback.print_exc()
            print(f"Error: {str(e)}")

    

def interactive_menu():
    """Menú interactivo principal"""
    print("=== EXPLORADOR AVANZADO DE TELEGRAM ===")
    print("Versión 2.0 - Búsqueda de entidades y análisis de participantes mejorado")
    
    explorer = TelegramEntityFinder2()
    
    if not explorer.initialize():
        print("Error durante la inicialización. Verificar logs.")
        return
    
    try:
        while True:
            print("\n=== MENÚ PRINCIPAL ===")
            print("1. Buscar entidades por categoría")
            print("2. Escanear mis diálogos")
            print("3. Ver entidades descubiertas")
            print("4. Extraer/analizar participantes")
            print("5. Ver participantes extraídos")
            print("6. Scrapear miembros de un grupo (modo avanzado)")
            print("7. Unirse a una entidad")
            print("8. Ver estadísticas")
            print("9. Exportar datos")
            print("10. Analizar entidades desconocidas")
            print("0. Salir")
            
            option = input("\nSelecciona una opción: ")
            
            if option == "1":
                print("\nCategorías disponibles:")
                for i, category in enumerate(SEARCH_TERMS.keys(), 1):
                    print(f"{i}. {category}")
                
                category_option = input("\nSelecciona una categoría (0 para todas): ")
                
                if category_option == "0":
                    explorer.search_all_categories()  # Esta llama a la versión sincrónica
                else:
                    try:
                        index = int(category_option) - 1
                        categories = list(SEARCH_TERMS.keys())
                        if 0 <= index < len(categories):
                            explorer.search_by_category(categories[index])  # Esta llama a la versión sincrónica
                        else:
                            print("Opción inválida.")
                    except ValueError:
                        print("Por favor, ingresa un número válido.")
            
            elif option == "2":
                print("\nOpciones de escaneo:")
                print("1. Escanear mis diálogos actuales")
                print("2. Escaneo exhaustivo (todos los tipos de entidades)")
                
                scan_option = input("\nSelecciona opción: ")
                
                if scan_option == "1":
                    explorer.scan_my_dialogs()  # Llama a la versión sincrónica
                elif scan_option == "2":
                    explorer.scan_for_all_entity_types()  # Llama a la versión sincrónica
                else:
                    print("Opción inválida")
            
            elif option == "3":
                # Opciones de filtrado
                print("\nOpciones de filtrado:")
                print("1. Ver todas las entidades")
                print("2. Filtrar por tipo")
                print("3. Filtrar por categoría")
                print("4. Filtrar por idioma")
                
                filter_option = input("\nSelecciona opción de filtrado: ")
                
                filter_criteria = None
                
                if filter_option == "2":
                    print("\nTipos disponibles:")
                    print("1. channel")
                    print("2. megagroup")
                    print("3. group")
                    print("4. forum")
                    print("5. unknown")
                    
                    type_option = input("Selecciona tipo: ")
                    if type_option == "1":
                        filter_criteria = {'type': 'channel'}
                    elif type_option == "2":
                        filter_criteria = {'type': 'megagroup'}
                    elif type_option == "3":
                        filter_criteria = {'type': 'group'}
                    elif type_option == "4":
                        filter_criteria = {'type': 'forum'}
                    elif type_option == "5":
                        filter_criteria = {'type': 'unknown'}
                
                elif filter_option == "3":
                    print("\nCategorías disponibles:")
                    for i, category in enumerate(SEARCH_TERMS.keys(), 1):
                        print(f"{i}. {category}")
                    
                    category_option = input("Selecciona categoría: ")
                    
                    try:
                        index = int(category_option) - 1
                        categories = list(SEARCH_TERMS.keys())
                        if 0 <= index < len(categories):
                            filter_criteria = {'category': categories[index]}
                    except ValueError:
                        pass
                
                elif filter_option == "4":
                    print("\nIdiomas disponibles:")
                    for i, lang in enumerate(LANGUAGE_PATTERNS.keys(), 1):
                        print(f"{i}. {lang}")
                    
                    lang_option = input("Selecciona idioma: ")
                    
                    try:
                        index = int(lang_option) - 1
                        languages = list(LANGUAGE_PATTERNS.keys())
                        if 0 <= index < len(languages):
                            filter_criteria = {'language': languages[index]}
                    except ValueError:
                        pass
                
                explorer.display_entities_from_csv(filter_criteria)  # Esta no cambia, sigue siendo sincrónica
            
            elif option == "4":
                print("\nOpciones para participantes:")
                print("1. Extraer miembros completos (requiere permisos)")
                print("2. Analizar participantes activos (funciona con cualquier grupo)")
                print("3. Analizar canal (específico para canales)")
                print("4. Descubrir usuarios regulares (método avanzado, puede tardar)")
                print("5. 🔥 EXTRACCIÓN SUPREMA COMPREHENSIVA (canales sin permisos)")
                
                extract_option = input("\nSelecciona opción: ")
                
                if extract_option == "1":
                    # Mostrar entidades para seleccionar
                    entities = explorer.display_entities()
                    if entities:
                        entity_option = input("\nSelecciona el número de la entidad (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                explorer.extract_members_from_entity(entity_id)  # Llama a la versión sincrónica
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")
                
                elif extract_option == "2":
                    # Mostrar entidades para seleccionar
                    entities = explorer.display_entities()
                    if entities:
                        entity_option = input("\nSelecciona el número de la entidad (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                message_limit = input("Número de mensajes a analizar (por defecto 100): ")
                                try:
                                    message_limit = int(message_limit) if message_limit else 100
                                except ValueError:
                                    message_limit = 100
                                
                                explorer.extract_active_participants(entity_id, message_limit)  # Llama a la versión sincrónica
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")

                elif extract_option == "3":
                    # Mostrar entidades para seleccionar
                    entities = explorer.display_entities({'type': 'channel'})
                    if entities:
                        entity_option = input("\nSelecciona el número del canal (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                explorer.extract_channel_info(entity_id)  # Esta sigue siendo sincrónica
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")

                elif extract_option == "4":
                    # Mostrar entidades para seleccionar
                    entities = explorer.display_entities()
                    if entities:
                        entity_option = input("\nSelecciona el número de la entidad (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                max_users = input("Número máximo de usuarios a buscar (por defecto 200): ")
                                try:
                                    max_users = int(max_users) if max_users else 200
                                except ValueError:
                                    max_users = 200
                                
                                print("\nIniciando búsqueda avanzada de usuarios regulares...")
                                print("Este proceso puede tardar varios minutos y utiliza múltiples técnicas.")
                                explorer.discover_regular_users(entity_id, max_users)  # Llama a la versión sincrónica
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")

                elif extract_option == "5":
                    entities = explorer.display_entities()
                    if entities:
                        entity_option = input("\nSelecciona el número de la entidad (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                duration = input("Duración de la extracción en minutos (recomendado: 45): ")
                                try:
                                    duration = int(duration) if duration else 45
                                except ValueError:
                                    duration = 45
                                
                                print("\n⚠️ ADVERTENCIA: Este proceso utilizará métodos comprehensivos para")
                                print("extraer usuarios de un canal donde no eres administrador.")
                                print("El proceso puede tardar hasta 45 minutos en completarse.")
                                confirm = input("¿Estás seguro de continuar? (s/n): ").lower() == 's'
                                
                                if confirm:
                                    print("\nIniciando extracción suprema comprehensiva. Este proceso tardará varios minutos.")
                                    print("Por favor, no cierres la ventana hasta que finalice.")
                                    
                                    # Use the synchronous wrapper function which properly handles the event loop
                                    # This preserves the original event loop that Telethon was initialized with
                                    try:
                                        count = explorer.extract_users_ultimate_comprehensive(entity_id, duration)
                                        print(f"\nExtracción completada. Se encontraron {count} usuarios.")
                                    except Exception as e:
                                        print(f"\nError en la extracción: {e}")
                                        traceback.print_exc()
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")
            
            elif option == "5":
                print("\nOpciones para ver participantes:")
                print("1. Ver muestra general de participantes")
                print("2. Ver participantes de una entidad específica")
                print("3. Ver solo administradores")
                print("4. Ver solo participantes activos")
                
                view_option = input("\nSelecciona opción: ")
                
                if view_option == "1":
                    limit = input("Número de participantes a mostrar (por defecto 20): ")
                    try:
                        limit = int(limit) if limit else 20
                    except ValueError:
                        limit = 20
                    
                    explorer.display_members(limit=limit)  # Esta sigue siendo sincrónica
                
                elif view_option == "2":
                    # Mostrar entidades para seleccionar
                    entities = explorer.display_entities()
                    if entities:
                        entity_option = input("\nSelecciona el número de la entidad (0 para cancelar): ")
                        try:
                            index = int(entity_option) - 1
                            if index == -1:  # 0 para cancelar
                                continue
                            if 0 <= index < len(entities):
                                entity_id = entities[index].get('entity_id', '')
                                explorer.display_members(entity_id=entity_id)  # Esta sigue siendo sincrónica
                            else:
                                print("Número inválido.")
                        except ValueError:
                            print("Por favor, ingresa un número válido.")
                
                elif view_option == "3":
                    # Mostrar solo administradores
                    explorer.display_members(filter_by_role="admin")  # Esta sigue siendo sincrónica
                
                elif view_option == "4":
                    # Mostrar solo participantes activos
                    explorer.display_members(filter_by_participation="active")  # Esta sigue siendo sincrónica
            
            elif option == "6":
                # Opción para scrapear miembros
                explorer.scrape_group_members()  # Esta debería seguir siendo sincrónica
            
            elif option == "7":
                # Unirse a una entidad
                entities = explorer.display_joinable_entities_from_csv()
                if entities:
                    entity_option = input("\nSelecciona el número de la entidad para unirte (0 para cancelar): ")
                    try:
                        index = int(entity_option) - 1
                        if index == -1:  # 0 para cancelar
                            continue
                        if 0 <= index < len(entities):
                            username = entities[index].get('username', '')
                            entity_id = entities[index].get('entity_id', '')
                            # if username:
                            #     join_success = explorer.join_entity(username)  # Llama a la versión sincrónica
                            #     if join_success:
                            #         # Si nos unimos correctamente, preguntar qué acción tomar
                            #         print("\n¿Qué deseas hacer ahora?")
                            #         print("1. Intentar extraer lista de miembros completa")
                            #         print("2. Analizar participantes activos")
                            #         print("3. Nada por ahora")
                                    
                            #         next_action = input("\nSelecciona una acción: ")
                            #         entity_id = entities[index].get('entity_id', '')
                                    
                            #         if next_action == "1":
                            #             explorer.extract_members_from_entity(entity_id)  # Llama a la versión sincrónica
                            #         elif next_action == "2":
                            #             message_limit = input("Número de mensajes a analizar (por defecto 100): ")
                            #             try:
                            #                 message_limit = int(message_limit) if message_limit else 100
                            #             except ValueError:
                            #                 message_limit = 100
                                        
                            #             explorer.extract_active_participants(entity_id, message_limit)  # Llama a la versión sincrónica
                            # else:
                            #     print("Esta entidad no tiene nombre de usuario.")
                            # Usar la nueva función que considera datos del CSV
                            join_success = explorer.join_entity_with_csv_data(entity_id)
                            
                            if join_success:
                                # Si nos unimos correctamente, preguntar qué acción tomar
                                print("\n¿Qué deseas hacer ahora?")
                                print("1. Intentar extraer lista de miembros completa")
                                print("2. Analizar participantes activos")
                                print("3. Nada por ahora")
                                
                                next_action = input("\nSelecciona una acción: ")
                                
                                if next_action == "1":
                                    explorer.extract_members_from_entity(entity_id)
                                elif next_action == "2":
                                    message_limit = input("Número de mensajes a analizar (por defecto 100): ")
                                    try:
                                        message_limit = int(message_limit) if message_limit else 100
                                    except ValueError:
                                        message_limit = 100
                                    
                                    explorer.extract_active_participants(entity_id, message_limit)
                        else:
                            print("Número inválido.")
                    except ValueError:
                        print("Por favor, ingresa un número válido.")
            
            elif option == "8":
                explorer.generate_statistics()  # Esta sigue siendo sincrónica
            
            elif option == "9":
                print("\nOpciones de exportación:")
                print("1. Exportar todos los datos")
                print("2. Exportar canales y sus participantes")
                print("3. Exportar grupos y sus participantes")
                print("4. Exportar por categoría")
                print("5. Exportar solo participantes activos")
                
                export_option = input("\nSelecciona opción: ")
                
                if export_option == "1":
                    explorer.export_filtered_data(filename_prefix="telegram_all")  # Esta sigue siendo sincrónica
                
                elif export_option == "2":
                    explorer.export_filtered_data(entity_filter={'type': 'channel'}, filename_prefix="telegram_channels")  # Esta sigue siendo sincrónica
                
                elif export_option == "3":
                    explorer.export_filtered_data(entity_filter={'type': 'megagroup'}, filename_prefix="telegram_groups")  # Esta sigue siendo sincrónica
                
                elif export_option == "4":
                    print("\nCategorías disponibles:")
                    for i, category in enumerate(SEARCH_TERMS.keys(), 1):
                        print(f"{i}. {category}")
                    
                    category_option = input("Selecciona categoría: ")
                    
                    try:
                        index = int(category_option) - 1
                        categories = list(SEARCH_TERMS.keys())
                        if 0 <= index < len(categories):
                            category = categories[index]
                            explorer.export_filtered_data(
                                entity_filter={'category': category}, 
                                filename_prefix=f"telegram_{category}"
                            )  # Esta sigue siendo sincrónica
                    except ValueError:
                        print("Opción inválida")
                
                elif export_option == "5":
                    explorer.export_filtered_data(
                        member_filter={'participation_type': 'active'},
                        filename_prefix="telegram_active_participants"
                    )  # Esta sigue siendo sincrónica
            
            elif option == "10":
                # Analizar entidades desconocidas
                explorer.analyze_unknown_entities()  # Esta debería seguir siendo sincrónica
            
            elif option == "0":
                print("Saliendo del programa...")
                break
            
            else:
                print("Opción inválida. Intenta de nuevo.")
        
    except KeyboardInterrupt:
        print("\nOperación interrumpida por el usuario.")
    except Exception as e:
        logger.error(f"Error en el menú principal: {e}")
        traceback.print_exc()
    finally:
        explorer.close()
        print("Programa finalizado. ¡Hasta pronto!")

if __name__ == "__main__":
    interactive_menu()