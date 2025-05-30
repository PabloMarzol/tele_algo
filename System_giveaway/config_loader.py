# =================== ARCHIVO: config_loader.py ===================

import json
import os
from typing import Dict, Any, Optional

class ConfigLoader:
    """Configuration loader with security and validation"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        Initialize config loader
        
        Args:
            config_file: Path to JSON configuration file
        """
        self.config_file = config_file
        self.config = {}
        self._load_config()
    
    def _load_config(self):
        """Load and validate configuration from JSON file"""
        try:
            if not os.path.exists(self.config_file):
                raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            
            # Validate required sections
            self._validate_config()
            
            print(f"✅ Configuration loaded successfully from {self.config_file}")
            
        except Exception as e:
            print(f"❌ Error loading configuration: {e}")
            raise
    
    def _validate_config(self):
        """Validate that all required sections exist"""
        required_sections = ['bot', 'giveaway_configs']
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate bot section
        bot_config = self.config['bot']
        required_bot_fields = ['token', 'channel_id', 'admin_id']
        
        for field in required_bot_fields:
            if field not in bot_config or not bot_config[field]:
                raise ValueError(f"Missing required bot configuration: {field}")
        
        # Validate giveaway types
        giveaway_configs = self.config['giveaway_configs']
        required_types = ['daily', 'weekly', 'monthly']
        
        for giveaway_type in required_types:
            if giveaway_type not in giveaway_configs:
                raise ValueError(f"Missing giveaway configuration for: {giveaway_type}")
    
    def get_bot_config(self) -> Dict[str, Any]:
        """Get bot configuration"""
        return self.config.get('bot', {})
    
    def get_mt5_config(self) -> Dict[str, Any]:
        """Get MT5 API configuration"""
        return self.config.get('mt5_api', {})
    
    def get_giveaway_configs(self) -> Dict[str, Any]:
        """Get all giveaway configurations"""
        return self.config.get('giveaway_configs', {})
    
    def get_giveaway_config(self, giveaway_type: str) -> Dict[str, Any]:
        """Get configuration for specific giveaway type"""
        configs = self.get_giveaway_configs()
        return configs.get(giveaway_type, {})
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self.config.get('database', {'type': 'csv', 'base_path': './System_giveaway/data'})
    
    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        return self.config.get('security', {})
    
    def get_timezone(self) -> str:
        """Get configured timezone"""
        return self.config.get('timezone', 'Europe/London')
    
    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration"""
        return self.config.get('logging', {'level': 'INFO'})
    
    def get_all_config(self) -> Dict[str, Any]:
        """Get complete configuration"""
        return self.config
    
    def reload_config(self):
        """Reload configuration from file"""
        self._load_config()