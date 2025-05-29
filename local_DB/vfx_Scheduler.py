import os
import json
import random
from datetime import datetime, timedelta
import logging

class VFXMessageScheduler:
    """Advanced message scheduler for VFX trading messages."""
    
    def __init__(self, config_path="./bot_data/vfx_messages.json"):
        """Initialize the message scheduler with a configuration file."""
        self.config_path = config_path
        self.messages = {}
        self.current_interval_index = 0
        self.last_interval_time = datetime.now()
        
        # Initialize logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            filename='message_scheduler.log'
        )
        self.logger = logging.getLogger('VFXMessageScheduler')
        
        # Load messages
        self.load_messages()
    
    def load_messages(self):
        """Load messages from JSON file."""
        try:

            print(f"Attempting to load messages from {self.config_path}")
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.messages = json.load(f)
                self.logger.info(f"Loaded message configuration from {self.config_path}")
            else:
                # If file doesn't exist, create it with a template
                self.create_default_config()
        except Exception as e:
            self.logger.error(f"Error loading messages: {e}")
            # Fall back to creating default config
            self.create_default_config()
    
    def create_default_config(self):
        """Create a default configuration file with sample messages."""
        default_config = {
            "hourly_welcome": {
                "00:00": "Welcome to VFX Trading! Midnight edition.",
                "01:00": "Welcome to VFX Trading! Early morning edition.",
                # Add more default hourly messages...
            },
            "interval_messages": [
                {
                    "name": "signal_example",
                    "message": "This is a sample signal message."
                },
                {
                    "name": "tip_example",
                    "message": "This is a sample trading tip."
                }
                # Add more default interval messages...
            ]
        }
        
        self.messages = default_config
        self.save_messages()
        self.logger.info("Created default message configuration")
    
    def save_messages(self):
        """Save messages to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Saved message configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Error saving messages: {e}")
    
    def get_welcome_message(self, hour=None):
        """Get the welcome message for the specified or current hour."""
        if hour is None:
            # Use current hour
            hour = datetime.now().hour
        
        hour_str = f"{hour:02d}:00"
        print(f"Getting welcome message for hour: {hour_str}")
        hourly_messages = self.messages.get("hourly_welcome", {})
        
        # Try to get the specific hour message
        if hour_str in hourly_messages:
            return hourly_messages[hour_str]
        
        # If no specific message for this hour, get a random welcome message
        if hourly_messages:
            return random.choice(list(hourly_messages.values()))
        
        # No welcome messages available
        return "Welcome to VFX Trading!"
    
    def get_next_interval_message(self):
        """Get the next message in the interval rotation."""
        print(f"Getting interval message, current index: {self.current_interval_index}")
        interval_messages = self.messages.get("interval_messages", [])
        
        if not interval_messages:
            return "Stay tuned for VFX trading signals!"
        
        # Get the next message in sequence
        message = interval_messages[self.current_interval_index]["message"]
        message_name = interval_messages[self.current_interval_index]["name"]
        
        # Update the index for the next call
        self.current_interval_index = (self.current_interval_index + 1) % len(interval_messages)
        
        self.logger.info(f"Sending interval message: {message_name}")
        return message
    
    def should_send_interval_message(self, interval_minutes=20):
        """Check if it's time to send an interval message."""
        now = datetime.now()
        time_since_last = now - self.last_interval_time
        
        if time_since_last.total_seconds() >= interval_minutes * 60:
            self.last_interval_time = now
            return True
        
        return False
    
    def add_message(self, message_type, key, content):
        """Add or update a message in the configuration."""
        if message_type == "hourly":
            if "hourly_welcome" not in self.messages:
                self.messages["hourly_welcome"] = {}
            
            # Format the hour key correctly
            try:
                hour = int(key)
                hour_key = f"{hour:02d}:00"
                self.messages["hourly_welcome"][hour_key] = content
                self.save_messages()
                return True
            except ValueError:
                self.logger.error(f"Invalid hour format: {key}")
                return False
        
        elif message_type == "interval":
            if "interval_messages" not in self.messages:
                self.messages["interval_messages"] = []
            
            # Check if message with this name already exists
            for i, msg in enumerate(self.messages["interval_messages"]):
                if msg.get("name") == key:
                    # Update existing message
                    self.messages["interval_messages"][i]["message"] = content
                    self.save_messages()
                    return True
            
            # Add new message
            self.messages["interval_messages"].append({
                "name": key,
                "message": content
            })
            self.save_messages()
            return True
        
        return False
    
    def remove_message(self, message_type, key):
        """Remove a message from the configuration."""
        if message_type == "hourly" and "hourly_welcome" in self.messages:
            if key in self.messages["hourly_welcome"]:
                del self.messages["hourly_welcome"][key]
                self.save_messages()
                return True
        
        elif message_type == "interval" and "interval_messages" in self.messages:
            for i, msg in enumerate(self.messages["interval_messages"]):
                if msg.get("name") == key:
                    del self.messages["interval_messages"][i]
                    self.save_messages()
                    return True
        
        return False
    
    def get_all_messages(self, message_type=None):
        """Get all messages of a specific type or all messages."""
        if message_type == "hourly":
            return self.messages.get("hourly_welcome", {})
        
        elif message_type == "interval":
            return self.messages.get("interval_messages", [])
        
        # Return all messages
        return self.messages
    
    def reset_interval_rotation(self):
        """Reset the interval message rotation to the beginning."""
        self.current_interval_index = 0
        self.last_interval_time = datetime.now()