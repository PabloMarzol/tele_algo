import polars as pl
from datetime import datetime, timedelta
import os
import json

class TradingBotDatabase:
    """A database manager for the Telegram trading bot using Polars."""
    
    def __init__(self, data_dir="./bot_data"):
        """Initialize database with specified data directory."""
        self.data_dir = data_dir
        
        # Ensure data directory exists
        os.makedirs(data_dir, exist_ok=True)
        
        # Define paths for different data files
        self.users_path = os.path.join(data_dir, "users.csv")
        self.group_members_path = os.path.join(data_dir, "group_members.csv")
        self.channel_members_path = os.path.join(data_dir, "channel_members.csv")
        self.analytics_path = os.path.join(data_dir, "analytics.csv")
        self.settings_path = os.path.join(data_dir, "settings.json")
        
        # Initialize all dataframes
        self._init_dataframes()
        # Load settings
        self._load_settings()
        
    def _init_dataframes(self):
        """Initialize all dataframes, creating them if they don't exist."""
        # Define schema with explicit types
        users_schema = {
            # Existing fields
            "user_id": pl.Int64,
            "username": pl.Utf8,
            "first_name": pl.Utf8,
            "last_name": pl.Utf8,
            "risk_appetite": pl.Int64,
            "deposit_amount": pl.Int64,
            "trading_account": pl.Utf8,
            "is_verified": pl.Boolean,
            "join_date": pl.Utf8,
            "last_active": pl.Utf8,
            "banned": pl.Boolean,
            "notes": pl.Utf8,
            "trading_interest": pl.Utf8,
            "vip_channels": pl.Utf8,
            "vip_added_date": pl.Utf8,
            "copier_forwarded": pl.Boolean,
            "copier_forwarded_date": pl.Utf8,
            "source_channel": pl.Utf8,           
            "first_contact_date": pl.Utf8,       
            "auto_welcomed": pl.Boolean,        
            "auto_welcome_date": pl.Utf8,        
            "risk_profile_text": pl.Utf8,       
            "last_response": pl.Utf8,           
            "last_response_time": pl.Utf8,
            
            # NEW VIP ACCESS FIELDS (CRITICAL)
            "vip_access_granted": pl.Boolean,
            "vip_eligible": pl.Boolean,
            "vip_services": pl.Utf8,
            "vip_services_list": pl.Utf8,
            "vip_granted_date": pl.Utf8,
            "vip_request_status": pl.Utf8,
            "vip_links_sent": pl.Boolean,
            "vip_granted_by": pl.Int64,
            
            # NEW BALANCE FIELDS (CRITICAL)
            "account_balance": pl.Float64,
            "funding_status": pl.Utf8,
            "last_balance_update": pl.Utf8,
            "qualification_balance": pl.Float64,
            
            # NEW TRACKING FIELDS
            "registration_confirmed": pl.Boolean,
            "vip_access_date": pl.Utf8,
            "manual_vip_grant": pl.Boolean,
            "manual_grant_date": pl.Utf8,
            "last_vip_update": pl.Utf8,
            "balance_source": pl.Utf8
        }
        
        # Rest of the existing schema definitions...
        group_members_schema = {
            "user_id": pl.Int64,
            "join_date": pl.Utf8,
            "is_admin": pl.Boolean,
            "is_verified": pl.Boolean,
            "last_message_date": pl.Utf8
        }
        
        channel_members_schema = {
            "user_id": pl.Int64,
            "join_date": pl.Utf8,
            "subscription_type": pl.Utf8,
            "expiry_date": pl.Utf8
        }
        
        analytics_schema = {
            "date": pl.Utf8,
            "new_users": pl.Int64,
            "active_users": pl.Int64,
            "messages_sent": pl.Int64,
            "commands_used": pl.Int64
        }
            
        # Users table
        if os.path.exists(self.users_path):
            try:
                # Read existing CSV
                self.users_df = pl.read_csv(self.users_path)
                
                print(f"Loaded existing CSV with {self.users_df.height} rows and columns: {self.users_df.columns}")
                
                # Add any missing columns with default values
                for col_name, dtype in users_schema.items():
                    if col_name not in self.users_df.columns:
                        print(f"Adding missing column: {col_name} ({dtype})")
                        
                        if dtype == pl.Int64:
                            self.users_df = self.users_df.with_columns(pl.lit(0).cast(dtype).alias(col_name))
                        elif dtype == pl.Float64:
                            self.users_df = self.users_df.with_columns(pl.lit(0.0).cast(dtype).alias(col_name))
                        elif dtype == pl.Boolean:
                            self.users_df = self.users_df.with_columns(pl.lit(False).cast(dtype).alias(col_name))
                        else:
                            self.users_df = self.users_df.with_columns(pl.lit("").cast(dtype).alias(col_name))
                
                # Convert existing columns to proper types
                for col_name, dtype in users_schema.items():
                    if col_name in self.users_df.columns:
                        try:
                            self.users_df = self.users_df.with_columns([
                                pl.col(col_name).cast(dtype).alias(col_name)
                            ])
                        except Exception as e:
                            print(f"Error casting column {col_name}: {e}")
                            # Handle failed casting with safe defaults
                            if dtype == pl.Int64:
                                self.users_df = self.users_df.with_columns([
                                    pl.when(pl.col(col_name).is_null())
                                    .then(0)
                                    .otherwise(pl.lit(0))
                                    .cast(dtype)
                                    .alias(col_name)
                                ])
                            elif dtype == pl.Float64:
                                self.users_df = self.users_df.with_columns([
                                    pl.when(pl.col(col_name).is_null())
                                    .then(0.0)
                                    .otherwise(pl.lit(0.0))
                                    .cast(dtype)
                                    .alias(col_name)
                                ])
                            elif dtype == pl.Boolean:
                                self.users_df = self.users_df.with_columns([
                                    pl.when(pl.col(col_name).is_null())
                                    .then(False)
                                    .otherwise(pl.lit(False))
                                    .cast(dtype)
                                    .alias(col_name)
                                ])
                            else:
                                self.users_df = self.users_df.with_columns([
                                    pl.when(pl.col(col_name).is_null())
                                    .then("")
                                    .otherwise(pl.lit(""))
                                    .cast(dtype)
                                    .alias(col_name)
                                ])
                print(f"✅ Users dataframe loaded with {len(self.users_df.columns)} columns")
                print(f"New columns added: {[col for col in users_schema.keys() if col not in ['user_id', 'username', 'first_name']]}")
            
            except Exception as e:
                print(f"Error loading users CSV: {e}")
                # Create a new dataframe with complete schema
                self.users_df = pl.DataFrame(
                    {col: [] for col in users_schema.keys()},
                    schema=users_schema
                )
                print("Created new users dataframe with complete schema")
                
            # CRITICAL: Save the updated dataframe with new columns
            try:
                self.users_df.write_csv(self.users_path)
                print(f"✅ Saved updated users.csv with new VIP columns")
            except Exception as e:
                print(f"❌ Error saving updated CSV: {e}")
                
        else:
            # Create new dataframe with complete schema
            self.users_df = pl.DataFrame(
                {col: [] for col in users_schema.keys()},
                schema=users_schema
            )
            self.users_df.write_csv(self.users_path)
            print("Created new users.csv with complete schema")
        
        # Group members table - similar approach for other tables
        if os.path.exists(self.group_members_path):
            try:
                self.group_members_df = pl.read_csv(self.group_members_path)
                # Apply similar type conversion as for users_df
                for col_name, dtype in group_members_schema.items():
                    if col_name in self.group_members_df.columns:
                        try:
                            self.group_members_df = self.group_members_df.with_columns([
                                pl.col(col_name).cast(dtype).alias(col_name)
                            ])
                        except:
                            # Handle failed casting
                            pass
            except:
                self.group_members_df = pl.DataFrame(
                    {col: [] for col in group_members_schema.keys()},
                    schema=group_members_schema
                )
                self.group_members_df.write_csv(self.group_members_path)
        else:
            self.group_members_df = pl.DataFrame(
                {col: [] for col in group_members_schema.keys()},
                schema=group_members_schema
            )
            self.group_members_df.write_csv(self.group_members_path)
        
        # Channel members table
        if os.path.exists(self.channel_members_path):
            try:
                self.channel_members_df = pl.read_csv(self.channel_members_path)
                # Apply similar type conversion as for users_df
                for col_name, dtype in channel_members_schema.items():
                    if col_name in self.channel_members_df.columns:
                        try:
                            self.channel_members_df = self.channel_members_df.with_columns([
                                pl.col(col_name).cast(dtype).alias(col_name)
                            ])
                        except:
                            # Handle failed casting
                            pass
            except:
                self.channel_members_df = pl.DataFrame(
                    {col: [] for col in channel_members_schema.keys()},
                    schema=channel_members_schema
                )
                self.channel_members_df.write_csv(self.channel_members_path)
        else:
            self.channel_members_df = pl.DataFrame(
                {col: [] for col in channel_members_schema.keys()},
                schema=channel_members_schema
            )
            self.channel_members_df.write_csv(self.channel_members_path)
        
        # Analytics table
        if os.path.exists(self.analytics_path):
            try:
                self.analytics_df = pl.read_csv(self.analytics_path)
                # Apply similar type conversion as for users_df
                for col_name, dtype in analytics_schema.items():
                    if col_name in self.analytics_df.columns:
                        try:
                            self.analytics_df = self.analytics_df.with_columns([
                                pl.col(col_name).cast(dtype).alias(col_name)
                            ])
                        except:
                            # Handle failed casting
                            pass
            except:
                self.analytics_df = pl.DataFrame(
                    {col: [] for col in analytics_schema.keys()},
                    schema=analytics_schema
                )
                self.analytics_df.write_csv(self.analytics_path)
        else:
            self.analytics_df = pl.DataFrame(
                {col: [] for col in analytics_schema.keys()},
                schema=analytics_schema
            )
            self.analytics_df.write_csv(self.analytics_path)
    
    def _load_settings(self):
        """Load bot settings from JSON file."""
        if os.path.exists(self.settings_path):
            with open(self.settings_path, 'r') as f:
                self.settings = json.load(f)
        else:
            # Default settings
            self.settings = {
                "welcome_message": """🎉 Welcome to the VFX-VIP Group! We’re thrilled to have you join our exclusive trading community. Here's everything you need to get started like a pro:
                                    🧑‍💼 1. Introduce Yourself

                We’d love to know who you are!
                📌 Share a few words about:

                    👤 Your name or nickname

                    💡 What brought you to the group

                    🤝 How you'd like to participate

                📜 2. Review & Follow the Rules

                🛡 Respect is the foundation of our group.
                Please review the pinned group rules carefully.
                🚫 Rule violations will result in a ban — no exceptions.
                ✅ Let’s keep this space clean, helpful, and professional.
                ✅ 3. Verify to Unlock Access

                🔒 For your safety and the group’s integrity, please complete the verification using the button below.
                🔓 Once verified, you’ll gain full access to all discussions and updates.
                💬 4. Engage & Connect

                Now that you're verified — welcome to the action!
                ❓ Ask questions
                📊 Share your trading insights
                👥 Network with fellow members

                🙌 We encourage active participation — your voice adds value!
                🎯 Let’s trade smart. Grow together. Win together.

                Thank you for being a part of VFX-VIP — we're excited for what lies ahead! 🚀""",
                "periodic_message": "📊 Remember to check our latest trading signals! Join our premium channel for exclusive access.",
                "private_welcome_message": "Thanks for reaching out! To better serve you, please answer a few questions:",
                "message_interval_hours": 0.5,
                "captcha_enabled": True,
                "max_auth_attempts": 3,
                "admin_ids": []
            }
            # Save default settings
            self._save_settings()
    
    def _save_settings(self):
        """Save current settings to JSON file."""
        with open(self.settings_path, 'w') as f:
            json.dump(self.settings, f, indent=4)
    
    def update_setting(self, key, value):
        """Update a specific setting."""
        if key in self.settings:
            self.settings[key] = value
            self._save_settings()
            return True
        return False
    
    def get_setting(self, key, default=None):
        """Get a specific setting value."""
        return self.settings.get(key, default)
    
    def add_user(self, user_data):
        """Add a new user to the database with enhanced type handling."""
        # Ensure we have user_id
        if 'user_id' not in user_data:
            print("Missing user_id in data")
            return False
        
        try:
            # Ensure user_id is an integer
            user_data['user_id'] = int(user_data['user_id'])
        except (ValueError, TypeError):
            print(f"Invalid user_id: {user_data['user_id']}")
            return False
        
        # ENHANCED: Clean and validate data types before storing
        cleaned_data = self._clean_user_data(user_data)
        
        # Check if user already exists
        try:
            existing = self.users_df.filter(pl.col("user_id") == cleaned_data['user_id'])
        except Exception as e:
            print(f"Error filtering dataframe: {e}")
            existing = pl.DataFrame(schema=self.users_df.schema)
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if existing.height > 0:
            # User exists, update information
            for key, value in cleaned_data.items():
                if key in self.users_df.columns:
                    try:
                        # Update column with proper type
                        self.users_df = self.users_df.with_columns([
                            pl.when(pl.col("user_id") == cleaned_data['user_id'])
                            .then(pl.lit(value))
                            .otherwise(pl.col(key))
                            .alias(key)
                        ])
                    except Exception as e:
                        print(f"Error updating {key} with value {value}: {e}")
            
            # Save changes
            try:
                self.users_df.write_csv(self.users_path)
                return True
            except Exception as e:
                print(f"Error saving CSV after update: {e}")
                return False
        else:
            # New user, add row with complete data
            complete_user = self._create_complete_user_record(cleaned_data, now)
            
            try:
                # Create a new dataframe with just this user
                user_df = pl.DataFrame([complete_user], schema=self.users_df.schema)
                
                # Concatenate with main dataframe
                self.users_df = pl.concat([self.users_df, user_df])
                
                # Save changes
                self.users_df.write_csv(self.users_path)
                return True
            except Exception as e:
                print(f"Error adding new user: {e}")
                return False

    def _clean_user_data(self, user_data):
        """Clean and validate user data types."""
        cleaned = {}
        
        for key, value in user_data.items():
            try:
                if key == "user_id":
                    cleaned[key] = int(value) if value is not None else 0
                    
                elif key in ["risk_appetite", "deposit_amount", "vip_granted_by"]:
                    # Integer fields
                    if value is None or value == "":
                        cleaned[key] = 0
                    else:
                        cleaned[key] = int(float(value)) if str(value).replace('.', '').isdigit() else 0
                        
                elif key in ["account_balance", "qualification_balance"]:
                    # Float fields  
                    if value is None or value == "":
                        cleaned[key] = 0.0
                    else:
                        cleaned[key] = float(value) if str(value).replace('.', '').replace('-', '').isdigit() else 0.0
                        
                elif key in ["is_verified", "banned", "copier_forwarded", "auto_welcomed", 
                            "registration_confirmed", "vip_access_granted", "vip_eligible", 
                            "vip_links_sent", "manual_vip_grant"]:
                    # Boolean fields
                    if isinstance(value, str):
                        cleaned[key] = value.lower() in ('true', 'yes', '1', 't', 'y')
                    elif value is None:
                        cleaned[key] = False
                    else:
                        cleaned[key] = bool(value)
                        
                else:
                    # String fields
                    cleaned[key] = str(value) if value is not None else ""
                    
            except Exception as e:
                print(f"Error cleaning {key}={value}: {e}")
                # Set safe defaults
                if key in ["risk_appetite", "deposit_amount", "vip_granted_by"]:
                    cleaned[key] = 0
                elif key in ["account_balance", "qualification_balance"]:
                    cleaned[key] = 0.0
                elif key in ["is_verified", "banned", "copier_forwarded", "auto_welcomed", 
                            "registration_confirmed", "vip_access_granted", "vip_eligible", 
                            "vip_links_sent", "manual_vip_grant"]:
                    cleaned[key] = False
                else:
                    cleaned[key] = ""
        
        return cleaned

    def _create_complete_user_record(self, cleaned_data, now):
        """Create a complete user record with all required fields."""
        complete_user = {}
        
        # Get schema from dataframe
        schema = self.users_df.schema
        
        for col_name, dtype in schema.items():
            if col_name in cleaned_data:
                complete_user[col_name] = cleaned_data[col_name]
            else:
                # Set appropriate defaults based on type
                if dtype == pl.Int64:
                    complete_user[col_name] = 0
                elif dtype == pl.Float64:
                    complete_user[col_name] = 0.0
                elif dtype == pl.Boolean:
                    complete_user[col_name] = False
                else:  # String/Utf8
                    if col_name == "join_date":
                        complete_user[col_name] = now
                    elif col_name == "last_active":
                        complete_user[col_name] = now
                    else:
                        complete_user[col_name] = ""
        
        return complete_user
    
    def get_user(self, user_id):
        """Get user information by user_id."""
        try:
            # Ensure user_id is an integer
            user_id = int(user_id)
            
            user = self.users_df.filter(pl.col("user_id") == user_id)
            if user.height > 0:
                # Convert to dict for easier use
                user_dict = {}
                for col in user.columns:
                    user_dict[col] = user[col][0]
                return user_dict
        except Exception as e:
            print(f"Error getting user {user_id}: {e}")
        
        return None
    
    def update_user_activity(self, user_id):
        """Update a user's last active timestamp."""
        try:
            # Ensure user_id is an integer
            user_id = int(user_id)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if user exists
            if self.get_user(user_id) is not None:
                # Update last_active field
                self.users_df = self.users_df.with_columns([
                    pl.when(pl.col("user_id") == user_id)
                    .then(pl.lit(now))
                    .otherwise(pl.col("last_active"))
                    .alias("last_active")
                ])
                
                # Save changes
                self.users_df.write_csv(self.users_path)
                return True
        except Exception as e:
            print(f"Error updating user activity for {user_id}: {e}")
        
        return False
    
    def add_to_group(self, user_id, is_admin=False):
        """Add a user to the group members table."""
        try:
            # Ensure user_id is an integer
            user_id = int(user_id)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if already in group
            existing = self.group_members_df.filter(pl.col("user_id") == user_id)
            
            if existing.height == 0:
                # Add new group member
                new_member = {
                    "user_id": user_id,
                    "join_date": now,
                    "is_admin": bool(is_admin),
                    "is_verified": False,
                    "last_message_date": now
                }
                
                # Create a new dataframe with just this member
                member_df = pl.DataFrame([new_member])
                
                # Ensure types match
                for col in self.group_members_df.columns:
                    if col in member_df.columns:
                        member_df = member_df.with_columns([
                            pl.col(col).cast(self.group_members_df.schema[col])
                        ])
                
                # Concatenate with main dataframe
                self.group_members_df = pl.concat([self.group_members_df, member_df])
                
                # Save changes
                self.group_members_df.write_csv(self.group_members_path)
                return True
        except Exception as e:
            print(f"Error adding user {user_id} to group: {e}")
        
        return False
    
    def add_to_channel(self, user_id, subscription_type="free"):
        """Add a user to the channel members table."""
        try:
            # Ensure user_id is an integer
            user_id = int(user_id)
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Set expiry based on subscription type
            expiry = None
            if subscription_type == "premium":
                # Set expiry to 30 days from now
                expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if already in channel
            existing = self.channel_members_df.filter(pl.col("user_id") == user_id)
            
            if existing.height == 0:
                # Add new channel member
                new_member = {
                    "user_id": user_id,
                    "join_date": now,
                    "subscription_type": subscription_type,
                    "expiry_date": expiry or ""
                }
                
                # Create a new dataframe with just this member
                member_df = pl.DataFrame([new_member])
                
                # Ensure types match
                for col in self.channel_members_df.columns:
                    if col in member_df.columns:
                        member_df = member_df.with_columns([
                            pl.col(col).cast(self.channel_members_df.schema[col])
                        ])
                
                # Concatenate with main dataframe
                self.channel_members_df = pl.concat([self.channel_members_df, member_df])
                
                # Save changes
                self.channel_members_df.write_csv(self.channel_members_path)
                return True
        except Exception as e:
            print(f"Error adding user {user_id} to channel: {e}")
        
        return False
    
    def mark_user_verified(self, user_id):
        """Mark a user as verified in both users and group members tables."""
        try:
            # Ensure user_id is an integer
            user_id = int(user_id)
            
            # Update users table
            self.users_df = self.users_df.with_columns([
                pl.when(pl.col("user_id") == user_id)
                .then(pl.lit(True))
                .otherwise(pl.col("is_verified"))
                .alias("is_verified")
            ])
            self.users_df.write_csv(self.users_path)
            
            # Update group members table
            self.group_members_df = self.group_members_df.with_columns([
                pl.when(pl.col("user_id") == user_id)
                .then(pl.lit(True))
                .otherwise(pl.col("is_verified"))
                .alias("is_verified")
            ])
            self.group_members_df.write_csv(self.group_members_path)
            return True
        except Exception as e:
            print(f"Error marking user {user_id} as verified: {e}")
            return False
    
    def update_analytics(self, date=None, new_users=0, active_users=0, messages_sent=0, commands_used=0):
        """Update analytics for a specific date."""
        try:
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # Ensure values are integers
            new_users = int(new_users)
            active_users = int(active_users)
            messages_sent = int(messages_sent)
            commands_used = int(commands_used)
            
            # Check if entry for this date already exists
            existing = self.analytics_df.filter(pl.col("date") == date)
            
            if existing.height > 0:
                # Update existing entry
                self.analytics_df = self.analytics_df.with_columns([
                    pl.when(pl.col("date") == date)
                    .then(pl.col("new_users") + new_users)
                    .otherwise(pl.col("new_users"))
                    .alias("new_users"),
                    
                    pl.when(pl.col("date") == date)
                    .then(pl.col("active_users") + active_users)
                    .otherwise(pl.col("active_users"))
                    .alias("active_users"),
                    
                    pl.when(pl.col("date") == date)
                    .then(pl.col("messages_sent") + messages_sent)
                    .otherwise(pl.col("messages_sent"))
                    .alias("messages_sent"),
                    
                    pl.when(pl.col("date") == date)
                    .then(pl.col("commands_used") + commands_used)
                    .otherwise(pl.col("commands_used"))
                    .alias("commands_used")
                ])
            else:
                # Create new entry
                new_entry = {
                    "date": date,
                    "new_users": new_users,
                    "active_users": active_users,
                    "messages_sent": messages_sent,
                    "commands_used": commands_used
                }
                
                # Create a new dataframe with just this entry
                entry_df = pl.DataFrame([new_entry])
                
                # Ensure types match
                for col in self.analytics_df.columns:
                    if col in entry_df.columns:
                        entry_df = entry_df.with_columns([
                            pl.col(col).cast(self.analytics_df.schema[col])
                        ])
                
                # Concatenate with main dataframe
                self.analytics_df = pl.concat([self.analytics_df, entry_df])
            
            # Save changes
            self.analytics_df.write_csv(self.analytics_path)
            return True
        except Exception as e:
            print(f"Error updating analytics: {e}")
            return False
    
    def get_active_users(self, days=7):
        """Get count of active users in the last X days."""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            active = self.users_df.filter(
                pl.col("last_active") >= cutoff_date
            )
            
            return active.height
        except Exception as e:
            print(f"Error getting active users: {e}")
            return 0
        
    def is_user_already_registered(self, user_id):
        """Check if user has already completed successful registration."""
        try:
            user_info = self.get_user(user_id)
            if not user_info:
                return False
            
            # Check multiple criteria for successful registration
            has_verified_account = user_info.get("is_verified", False)
            has_trading_account = bool(user_info.get("trading_account"))
            registration_confirmed = user_info.get("registration_confirmed", False)
            vip_access_granted = user_info.get("vip_access_granted", False)
            
            # User is considered "successfully registered" if they have:
            # 1. Verified trading account, OR
            # 2. Confirmed registration, OR  
            # 3. Been granted VIP access
            return (has_verified_account and has_trading_account) or registration_confirmed or vip_access_granted
            
        except Exception as e:
            print(f"Error checking registration status for user {user_id}: {e}")
            return False

    def get_user_registration_summary(self, user_id):
        """Get detailed registration status for user."""
        try:
            user_info = self.get_user(user_id)
            if not user_info:
                return None
                
            return {
                "user_id": user_id,
                "first_name": user_info.get("first_name", "Unknown"),
                "is_verified": user_info.get("is_verified", False),
                "trading_account": user_info.get("trading_account"),
                "registration_confirmed": user_info.get("registration_confirmed", False),
                "vip_access_granted": user_info.get("vip_access_granted", False),
                "join_date": user_info.get("join_date"),
                "last_active": user_info.get("last_active"),
                "registration_status": "completed" if self.is_user_already_registered(user_id) else "incomplete"
            }
        except Exception as e:
            print(f"Error getting registration summary for user {user_id}: {e}")
            return None   
        
        
        
        
        
    