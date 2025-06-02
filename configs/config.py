import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration manager for the Telegram Trading Bot."""
    
    def __init__(self, config_path="./configs/config.json"):
        """Initialize config with specified config file path."""
        self.config_path = config_path
        self.config = {}
        
        # Load config file if exists
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f: 
                self.config = json.load(f)
        else:
            # Create default config with all constants
            self.config = self._create_default_config()
            self.save()
    
    def _create_default_config(self):
        """Create default configuration with all required constants."""
        return {
            "bot_manager_token": os.getenv("BOT_MANAGER_TOKEN", ""),
            "bot_algo_token": os.getenv("BOT_ALGO_TOKEN", ""),
            "admin_user_id": [int(x.strip()) for x in os.getenv("ADMIN_USER_ID", "").split(",") if x.strip()],
            "admin_user_id_2": int(os.getenv("ADMIN_USER_ID_2", "0")),
            "channels": {
                "main_channel_id": os.getenv("MAIN_CHANNEL_ID", ""),
                "support_group_id": int(os.getenv("SUPPORT_GROUP_ID", "0")),
                "strategy_channel_id": os.getenv("STRATEGY_CHANNEL_ID", ""),
                "strategy_group_id": int(os.getenv("STRATEGY_GROUP_ID", "0")),
                "signals_channel_id": os.getenv("SIGNALS_CHANNEL_ID", ""),
                "signals_group_id": int(os.getenv("SIGNALS_GROUP_ID", "0")),
                "prop_channel_id": os.getenv("PROP_CHANNEL_ID", ""),
                "prop_group_id": int(os.getenv("PROP_GROUP_ID", "0")),
                "ed_channel_id": os.getenv("ED_CHANNEL_ID", ""),
                "ed_group_id": int(os.getenv("ED_GROUP_ID", "0"))
            },
            "message_interval_hours": int(os.getenv("MESSAGE_INTERVAL_HOURS", "1")),
            "data_dir": os.getenv("DATA_DIR", "./bot_data"),
            "messages": {
                "welcome": os.getenv("WELCOME_MSG", "Welcome to our Trading Community! Please complete the authentication process."),
                "periodic": os.getenv("PERIODIC_MSG", "📊 Remember to check our latest trading signals!"),
                "private_welcome": os.getenv("PRIVATE_WELCOME_MSG", "Thanks for reaching out! To better serve you, please answer a few questions:")
            },
            "auth": {
                "captcha_enabled": True,
                "max_attempts": 3,
                "account_format_regex": r'^TR\d{8}$'
            }
        }
    
    # Properties for easy access to common constants
    @property
    def BOT_MANAGER_TOKEN(self):
        return self.get("bot_manager_token")
    
    @property
    def BOT_ALGO_TOKEN(self):
        return self.get("bot_algo_token")
    
    @property 
    def ADMIN_USER_ID(self):
        return self.get("admin_user_id", [])
    
    @property
    def ADMIN_USER_ID_2(self):
        return self.get("admin_user_id_2", 0)
    
    @property
    def MAIN_CHANNEL_ID(self):
        return self.get("channels.main_channel_id")
    
    @property
    def SUPPORT_GROUP_ID(self):
        return self.get("channels.support_group_id")
    
    @property
    def STRATEGY_CHANNEL_ID(self):
        return self.get("channels.strategy_channel_id")
    
    @property
    def STRATEGY_GROUP_ID(self):
        return self.get("channels.strategy_group_id")
    
    @property
    def SIGNALS_CHANNEL_ID(self):
        return self.get("channels.signals_channel_id")
    
    @property
    def SIGNALS_GROUP_ID(self):
        return self.get("channels.signals_group_id")
    
    @property
    def PROP_CHANNEL_ID(self):
        return self.get("channels.prop_channel_id")
    
    @property
    def PROP_GROUP_ID(self):
        return self.get("channels.prop_group_id")
    
    @property
    def ED_CHANNEL_ID(self):
        return self.get("channels.ed_channel_id")
    
    @property
    def ED_GROUP_ID(self):
        return self.get("channels.ed_group_id")
    
    def save(self):
        """Save current config to file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:  
            json.dump(self.config, f, indent=4)
    
    def get(self, key, default=None):
        """Get a config value by key path (supports nested keys with dots)."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key, value):
        """Set a config value by key path (supports nested keys with dots)."""
        keys = key.split('.')
        config = self.config
        
        # Navigate to the deepest dict
        for k in keys[:-1]:
            if k not in config or not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
        
        # Save changes
        self.save()
        return True

# Create global config instance
config = Config()