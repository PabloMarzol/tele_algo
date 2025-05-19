import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration manager for the Telegram Trading Bot."""
    
    def __init__(self, config_path="./config.json"):
        """Initialize config with specified config file path."""
        self.config_path = config_path
        self.config = {}
        
        # Load config file if exists
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f: 
                self.config = json.load(f)
        else:
            # Create default config
            self.config = {
                "bot_token": os.getenv("BOT_TOKEN", ""),
                "admin_user_id": int(os.getenv("ADMIN_USER_ID", "0")),
                "channel_id": os.getenv("CHANNEL_ID", ""),
                "group_id": int(os.getenv("GROUP_ID", "0")),
                "message_interval_hours": int(os.getenv("MESSAGE_INTERVAL_HOURS", "0.5")),
                "data_dir": os.getenv("DATA_DIR", "./bot_data"),
                "messages": {
                    "welcome": os.getenv("WELCOME_MSG", "Welcome to our Trading Community! Please complete the authentication process."),
                    "periodic": os.getenv("PERIODIC_MSG", "📊 Remember to check our latest trading signals! Join our premium channel for exclusive access."),
                    "private_welcome": os.getenv("PRIVATE_WELCOME_MSG", "Thanks for reaching out! To better serve you, please answer a few questions:")
                },
                "auth": {
                    "captcha_enabled": True,
                    "max_attempts": 3,
                    "account_format_regex": r'^TR\d{8}$'
                }
            }
            # Save default config
            self.save()
    
    def save(self):
        """Save current config to file."""
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

# Example .env file
def create_env_example():
    """Create an example .env file."""
    env_content = """# Telegram Bot Configuration
BOT_TOKEN=your_bot_token_here
ADMIN_USER_ID=your_telegram_user_id
CHANNEL_ID=@your_channel_name
GROUP_ID=-1001234567890
MESSAGE_INTERVAL_HOURS=12
DATA_DIR=./bot_data

# Message Templates
WELCOME_MSG=Welcome to our Trading Community! Please complete the authentication process.
PERIODIC_MSG=📊 Remember to check our latest trading signals! Join our premium channel for exclusive access.
PRIVATE_WELCOME_MSG=Thanks for reaching out! To better serve you, please answer a few questions:
"""
    
    with open(".env.example", "w") as f:
        f.write(env_content)

# Create installation instructions
def create_installation_instructions():
    """Create installation instructions file."""
    instructions = """# Telegram Trading Bot - Installation Instructions

## Prerequisites
- Python 3.8 or higher
- A Telegram account
- Bot Token from BotFather

## Installation Steps

1. Clone the repository or download the files

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. Install the required packages:
   ```
   pip install python-telegram-bot polars python-dotenv
   ```

4. Create a `.env` file based on `.env.example`:
   ```
   cp .env.example .env
   ```

5. Edit the `.env` file and add your bot token and other configuration values:
   - Get a bot token from @BotFather on Telegram
   - Set your Telegram user ID as the admin ID (you can get it from @userinfobot)
   - Set your channel and group IDs

6. Create the data directory:
   ```
   mkdir -p bot_data
   ```

7. Run the bot:
   ```
   python main.py
   ```

## Bot Setup in Telegram

1. Add your bot to your Telegram group with admin privileges
2. Add your bot to your Telegram channel as an admin
3. Start a private chat with your bot to set up your admin profile

## Commands

- `/start` - Start the bot and begin profile creation
- `/help` - Show help message
- `/cancel` - Cancel the current conversation
- `/stats` - Show bot statistics (admin only)

## Features

- Welcome messages for new group/channel members
- Periodic messages to keep engagement
- User authentication with CAPTCHA
- Trading account verification
- User information collection
- Admin statistics and monitoring
"""
    
    with open("README.md", "w") as f:
        f.write(instructions)

if __name__ == "__main__":
    # Create example files
    create_env_example()
    create_installation_instructions()
    
    # Create config instance
    config = Config()
    print("Configuration initialized successfully.")
    print(f"Admin ID: {config.get('admin_user_id')}")
    print(f"Message interval: {config.get('message_interval_hours')} hours")