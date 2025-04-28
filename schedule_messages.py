import json
from datetime import datetime, time, timedelta

class ScheduledMessageSystem:
    """A system to manage scheduled messages for the Telegram trading bot."""
    
    def __init__(self, db_path="./bot_data/scheduled_messages.json"):
        """Initialize the scheduled message system with a file path."""
        self.db_path = db_path
        self.messages = {}
        self.load_messages()
    
    def load_messages(self):
        """Load scheduled messages from JSON file."""
        try:
            with open(self.db_path, 'r') as f:
                self.messages = json.load(f)
            print(f"Loaded {len(self.messages)} scheduled messages")
        except FileNotFoundError:
            # Create default messages
            self.messages = {
                "hourly": {
                    "00:00": "📊 It's midnight! Time to review your trading strategy for tomorrow.",
                    "01:00": "💤 Markets are quiet now. Rest well to trade better tomorrow!",
                    "02:00": "📉 Asian markets are active. Keep an eye on emerging trends.",
                    "03:00": "📋 Use this time to update your trading journal.",
                    "04:00": "📚 Improve your trading skills with our educational resources.",
                    "05:00": "🌅 Early bird gets the worm! Prepare for the European market opening.",
                    "06:00": "⏰ European markets will open soon. Get ready for new opportunities!",
                    "07:00": "🚀 European session has started. Watch for initial momentum.",
                    "08:00": "📊 Check out our latest trading signals for the European session.",
                    "09:00": "💼 Peak trading time in Europe. Stay focused and stick to your strategy.",
                    "10:00": "💹 US pre-market activity is starting. Get ready for potential volatility.",
                    "11:00": "🔄 Overlapping session between Europe and US pre-market. Great opportunities!",
                    "12:00": "🕛 Noon check-in: Have you stuck to your trading plan today?",
                    "13:00": "🇺🇸 US markets opening soon. Prepare for increased volatility.",
                    "14:00": "📈 US session in full swing. Our analysts are monitoring key levels.",
                    "15:00": "🔍 Mid-US session - this is often when key reversals happen.",
                    "16:00": "📝 Time to evaluate your open positions and adjust your stops.",
                    "17:00": "🌎 European markets closing. Review your day trades.",
                    "18:00": "📊 Check our premium channel for after-hours analysis.",
                    "19:00": "🔚 US markets approaching close. Secure your profits and manage risk.",
                    "20:00": "📑 Time to review your trading performance for the day.",
                    "21:00": "🌠 Asian markets opening soon. New opportunities on the horizon!",
                    "22:00": "🔮 Looking ahead: Check our forecasts for tomorrow's trading session.",
                    "23:00": "📋 End of day summary: See our analysts' take on today's market moves.",
                    "23:36": "📋 End of day summary: See our analysts' take on today's market moves.",
                    "23:38:03": "📋 End of day summary: See our analysts' take on today's market moves."
                },
                "daily": {
                    "Monday": "🚀 Welcome to a new trading week! Check our weekly outlook in the premium channel.",
                    "Tuesday": "💼 Tuesday trading tip: Consistency beats intensity. Stick to your strategy!",
                    "Wednesday": "📊 Mid-week market update: See how our predictions are playing out.",
                    "Thursday": "📈 Economic calendar highlight: Check major announcements coming tomorrow.",
                    "Friday": "🎯 Friday focus: Remember to close positions before the weekend if that's your strategy.",
                    "Saturday": "📚 Weekend learning: Check our educational resources to improve your skills.",
                    "Sunday": "🔮 Sunday market preview: Get ready for the week ahead with our analysis."
                },
                "weekly": {
                    "Week 1": "🌟 First week of the month: Major economic indicators are releasing soon.",
                    "Week 2": "💹 Second week outlook: Mid-month momentum is building.",
                    "Week 3": "📝 Options expiration approaching: Be aware of potential volatility.",
                    "Week 4": "🔄 Month-end flows may affect market movements this week.",
                    "Week 5": "📊 Rare fifth week of the month: Check our special analysis."
                }
            }
            self.save_messages()
            print("Created default scheduled messages")
    
    def save_messages(self):
        """Save scheduled messages to JSON file."""
        # Ensure the directory exists
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with open(self.db_path, 'w') as f:
            json.dump(self.messages, f, indent=4)
        print("Saved scheduled messages to file")
    
    def get_hourly_message(self, hour=None):
        """Get the message for the current or specified hour."""
        if hour is None:
            # Use current hour
            current_time = datetime.now()
            hour_str = current_time.strftime("%H:00")
        else:
            # Format provided hour
            hour_str = f"{hour:02d}:00"
        
        # Get the message for this hour
        return self.messages.get("hourly", {}).get(hour_str, f"📊 Trading update for {hour_str}")
    
    def get_daily_message(self, day=None):
        """Get the message for the current or specified day of the week."""
        if day is None:
            # Use current day
            day = datetime.now().strftime("%A")
        
        # Get the message for this day
        return self.messages.get("daily", {}).get(day, f"📊 Trading update for {day}")
    
    def get_weekly_message(self, week=None):
        """Get the message for the current or specified week of the month."""
        if week is None:
            # Calculate current week of the month
            today = datetime.now()
            week_num = (today.day - 1) // 7 + 1
            week = f"Week {week_num}"
        
        # Get the message for this week
        return self.messages.get("weekly", {}).get(week, f"📊 Trading update for {week}")
    
    def update_hourly_message(self, hour, message):
        """Update the message for a specific hour."""
        hour_str = f"{hour:02d}:00"
        
        if "hourly" not in self.messages:
            self.messages["hourly"] = {}
        
        self.messages["hourly"][hour_str] = message
        self.save_messages()
        return True
    
    def update_daily_message(self, day, message):
        """Update the message for a specific day."""
        if "daily" not in self.messages:
            self.messages["daily"] = {}
        
        self.messages["daily"][day] = message
        self.save_messages()
        return True
    
    def update_weekly_message(self, week, message):
        """Update the message for a specific week."""
        if "weekly" not in self.messages:
            self.messages["weekly"] = {}
        
        self.messages["weekly"][week] = message
        self.save_messages()
        return True
    
    def get_next_message(self):
        """Get the message for the current hour, day and week."""
        hourly = self.get_hourly_message()
        daily = self.get_daily_message()
        weekly = self.get_weekly_message()
        
        # customize how to combine or select from these messages
        # For now, we'll just return the hourly message
        return hourly