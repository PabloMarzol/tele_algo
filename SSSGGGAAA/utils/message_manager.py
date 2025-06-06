import json
import os

class MessageManager:
    """Gestión completa de mensajes para giveaways"""
    
    def __init__(self, shared_context):
        """
        Initialize MessageManager
        
        Args:
            shared_context: Diccionario con referencias compartidas
        """
        # ✅ REFERENCIAS PRINCIPALES
        self.giveaway_system = shared_context['giveaway_system']
        self.logger = shared_context['logger']
        self.config = shared_context['config']
        self.giveaway_type = shared_context['giveaway_type']
        
        # ✅ CONFIGURACIÓN PARA MENSAJES
        self.admin_username = shared_context['giveaway_system'].admin_username
        self.winner_cooldown_days = self.config['cooldown_days']
        
        # ✅ ALMACÉN DE MENSAJES
        self.messages = {}

        # 🆕 NUEVA RUTA UNIFICADA (reemplaza las dos anteriores)
        self.enhanced_messages_file = "./enhanced_messages_complete.json"

        # ✅ RUTAS DE MENSAJES
        # self.messages_file = f"./SSSGGGAAA/messagess/messages_{self.giveaway_type}.json"
        # self.messages_common_file = "./SSSGGGAAA/messagess/messages_common.json"
        
        self.logger.info(f"MessageManager initialized for {self.giveaway_type}")

    def load_messages(self):
        """Load type-specific and common messages"""
        try:
            # Cargar mensajes del archivo unificado
            if os.path.exists(self.enhanced_messages_file):
                with open(self.enhanced_messages_file, 'r', encoding='utf-8') as f:
                    all_messages = json.load(f)
                
                # Extraer mensajes específicos para este tipo de giveaway
                if self.giveaway_type in all_messages:
                    self.messages = all_messages[self.giveaway_type]
                    self.logger.info(f"Enhanced messages loaded for {self.giveaway_type} giveaway")
                else:
                    self.logger.warning(f"No messages found for {self.giveaway_type} in enhanced messages file")
                    self._create_default_messages()
            else:
                self.logger.warning(f"Enhanced messages file not found: {self.enhanced_messages_file}")
                self._create_default_messages()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in enhanced messages file: {e}")
            self._create_default_messages()    
        except Exception as e:
            self.logger.error(f"Error loading messages: {e}")
            self._create_default_messages()

    def get_message(self, key, **kwargs):
        """
        Get formatted message by key
        
        Args:
            key: Message key to retrieve
            **kwargs: Variables to format into the message
            
        Returns:
            str: Formatted message or fallback message
        """
        try:
            # Get raw message
            raw_message = self.messages.get(key)
            
            if raw_message is None:
                self.logger.warning(f"Message key '{key}' not found for {self.giveaway_type}")
                return f"Message '{key}' not available"
            
            # Format message with provided variables
            if kwargs:
                try:
                    formatted_message = raw_message.format(**kwargs)
                    return formatted_message
                except KeyError as e:
                    self.logger.error(f"Missing variable {e} for message '{key}'")
                    return raw_message  # Return unformatted if missing variables
                except Exception as e:
                    self.logger.error(f"Error formatting message '{key}': {e}")
                    return raw_message
            else:
                return raw_message
                
        except Exception as e:
            self.logger.error(f"Error getting message '{key}': {e}")
            return f"Error retrieving message '{key}'"  # helper para formatear    

    def _create_default_messages(self):
        """🔄 MODIFIED: Create type-specific default messages in English"""
        # 🆕 NEW: Don't override existing messages from JSON files
        if hasattr(self, 'messages') and self.messages:
            # Messages already loaded from files, don't override
            self.logger.info(f"Using existing messages for {self.giveaway_type}")
            return
        # Base messages for this giveaway type
        prize = self.config['prize']
        
        # if self.giveaway_type == 'daily':
        #     draw_schedule = "Monday to Friday at 5:00 PM London Time"
        #     next_draw = "Tomorrow at 5:00 PM London Time"
        # elif self.giveaway_type == 'weekly':
        #     draw_schedule = "Every Friday at 5:15 PM London Time"
        #     next_draw = "Next Friday at 5:15 PM London Time"
        # elif self.giveaway_type == 'monthly':
        #     draw_schedule = "Last Friday of each month at 5:30 PM London Time"
        #     next_draw = "Last Friday of next month at 5:30 PM London Time"

        # Schedule information based on type
        schedule_info = self._get_schedule_info()
        draw_schedule = schedule_info['draw_schedule']
        next_draw = schedule_info['next_draw']

        period_name = {
            'daily': 'day',
            'weekly': 'week',
            'monthly': 'month'
        }.get(self.giveaway_type, 'period')
        
        self.messages = {
            "invitation": f"🎁 <b>{self.giveaway_type.upper()} GIVEAWAY ${prize} USD</b> 🎁\n\n💰 <b>Prize:</b> ${prize} USD\n⏰ <b>Draw:</b> {draw_schedule}\n\n<b>📋 Requirements to participate:</b>\n✅ Active MT5 LIVE account\n✅ Minimum balance $100 USD\n✅ Be a channel member\n\n👆 Press the button to participate",
            
            "success": f"✅ <b>Successfully registered!</b>\n\nYou are participating in the {self.giveaway_type} giveaway of ${prize} USD.\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "success_with_history": f"✅ <b>Successfully registered!</b>\n\nYou are participating in the {self.giveaway_type} giveaway of ${prize} USD with account {{account}}.\n\n📊 <b>Your history:</b> You have participated {{total_participations}} times with {{unique_accounts}} different account(s).\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "success_first_time": f"✅ <b>Successfully registered!</b>\n\n🎉 This is your first participation! You are in the {self.giveaway_type} giveaway of ${prize} USD.\n\n🍀 Good luck!\n\n⏰ Draw: {draw_schedule}",
            
            "already_registered": f"ℹ️ <b>Already registered</b>\n\nYou are already participating in today's {self.giveaway_type} giveaway.\n\n🍀 Good luck in the draw!\n\n⏰ Draw: {draw_schedule}",

            "already_participated_period": f"❌ <b>Already participated this {period_name}</b>\n\nYou already participated in this {period_name}'s {self.giveaway_type.upper()} giveaway with MT5 account {{previous_account}}.\n\n💡 <b>Rule:</b> Only one participation per user per {self.giveaway_type} {period_name}, regardless of the MT5 account used.\n\n🎁 You can participate in the next {self.giveaway_type} {period_name}.",
            
            "registration_in_progress": "⏳ <b>Registration in progress</b>\n\nYou already have a pending registration.\n\nPlease send your MT5 account number to complete your participation.",
            
            "account_already_used_today": f"❌ <b>Account already registered today</b>\n\nThis MT5 account was already used today by another user.\n\n💡 <b>Rule:</b> Each account can only participate once per {self.giveaway_type} period.\n\n🎁 You can participate in the next {self.giveaway_type} giveaway with any valid account.",
            
            "account_owned_by_other_user": "❌ <b>Account belongs to another user</b>\n\nThis MT5 account was previously registered by another participant on {first_used}.\n\n💡 <b>Rule:</b> Each MT5 account belongs exclusively to the first user who registered it.\n\n🎯 Use an MT5 account that is exclusively yours.",
            
            "insufficient_balance": "❌ <b>Insufficient balance</b>\n\nMinimum balance of $100 USD required\nYour current balance: <b>${balance}</b>\n\n💡 Deposit more funds to participate in future giveaways.",
            
            "not_live": "❌ <b>Invalid account</b>\n\nOnly MT5 LIVE accounts can participate in the giveaway.\n\n💡 Verify that you entered the correct number of your LIVE account.",
            
            "account_not_found": "❌ <b>Account not found</b>\n\nMT5 account #{account} was not found in our records.\n\n💡 Verify that the account number is correct.",
            
            "not_channel_member": "❌ <b>Not a channel member</b>\n\nYou must be a member of the main channel to participate.\n\n💡 Join the channel and try again.",
            
            "request_mt5": "🔢 <b>Enter your MT5 account number</b>\n\nPlease send your MT5 LIVE account number to verify that you meet the giveaway requirements.\n\n💡 Example: 12345678\n\n⚠️ <b>Important:</b> You can only register ONE account per day.",
            
            "invalid_format_retry": "❌ <b>Invalid format</b>\n\nAccount number must contain only numbers.\n\n💡 Example: 12345678\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n⚠️ Try again:",
            
            "max_attempts_reached": "❌ <b>Maximum attempts reached</b>\n\nYou have tried {max_attempts} times without success.\n\n🔄 <b>To participate again:</b>\n1. Go to the main channel\n2. Press \"PARTICIPATE NOW\" again\n3. Send a valid MT5 account\n\n💡 Remember: Only LIVE accounts with balance ≥ $100 USD",
            
            "processing": "⏳ Verifying your MT5 account...\n\nThis may take a few seconds.",
            
            "api_error": "❌ <b>Verification error</b>\n\nWe couldn't verify your account at this time.\n\n💡 Try again in a few minutes.",
            
            "no_eligible_participants": f"⚠️ No eligible participants for today's {self.giveaway_type} giveaway.\n\n📢 Join the next giveaway!",
            
            "winner_announcement": f"🏆 <b>{self.giveaway_type.upper()} GIVEAWAY WINNER!</b> 🏆\n\n🎉 Congratulations: {{username}}\n💰 Prize: <b>${prize} USD</b>\n📊 MT5 Account: <b>{{account}}</b>\n👥 Total participants: <b>{{total_participants}}</b>\n\n📅 Next draw: {next_draw}\n\n🎁 Participate too!",
            
            "winner_private_congratulation": f"🎉 <b>CONGRATULATIONS!</b> 🎉\n\n🏆 <b>You won the {self.giveaway_type} giveaway of ${prize} USD!</b>\n\n💰 <b>Your MT5 account {{account}} has been credited</b>\n\n📸 <b>IMPORTANT - Confirmation required:</b>\n• Check your MT5 account\n• Confirm that you received the ${prize} USD\n• Send a screenshot as evidence\n\n🙏 This confirmation helps us improve the service",
            
            "participation_window_closed": f"⏰ <b>Participation window closed</b>\n\nThe {self.giveaway_type} giveaway participation is currently closed.\n\n🔄 <b>Next participation window:</b>\n{{next_window}}\n\n💡 Stay tuned for the next opportunity!",
            
            "error_internal": "❌ Internal error. Try again in a few minutes.",
            
            "help_main": f"🆘 <b>{self.giveaway_type.upper()} GIVEAWAY RULES</b>\n\n💰 <b>Prize:</b> ${prize} USD\n⏰ <b>Draw:</b> {draw_schedule}\n\n<b>📋 REQUIREMENTS TO PARTICIPATE:</b>\n✅ Be a member of this channel\n✅ Active MT5 LIVE account (not demo)\n✅ Minimum balance of $100 USD\n✅ One participation per user per {self.giveaway_type} period\n\n<b>🔒 IMPORTANT RULES:</b>\n• Each MT5 account belongs to the first user who registers it\n• You cannot win twice in {self.winner_cooldown_days} days\n• You must confirm receipt of prize if you win\n\n<b>❌ COMMON ERRORS:</b>\n• \"Account not found\" → Verify the number\n• \"Insufficient balance\" → Deposit more than $100 USD\n• \"Account is not LIVE\" → Use real account, not demo\n• \"Already registered\" → Only one participation per {self.giveaway_type} period\n• \"Account belongs to another\" → Use your own MT5 account\n\n<b>📞 NEED HELP?</b>\nContact administrator: @{self.admin_username}\n\n<b>⏰ NEXT DRAW:</b>\n{next_draw}"
        }
        self.logger.info(f"Default messages created for {self.giveaway_type}")

    def _get_schedule_info(self):
        """Get schedule information based on giveaway type"""
        if self.giveaway_type == 'daily':
            return {
                'draw_schedule': "Monday to Friday at 5:00 PM London Time",
                'next_draw': "Tomorrow at 5:00 PM London Time"
            }
        elif self.giveaway_type == 'weekly':
            return {
                'draw_schedule': "Every Friday at 5:15 PM London Time", 
                'next_draw': "Next Friday at 5:15 PM London Time"
            }
        elif self.giveaway_type == 'monthly':
            return {
                'draw_schedule': "Last Friday of each month at 5:30 PM London Time",
                'next_draw': "Last Friday of next month at 5:30 PM London Time"
            }
        else:
            return {
                'draw_schedule': "Check announcements for schedule",
                'next_draw': "Check announcements for next draw"
            }
    def _save_messages(self):
        """🔄 MODIFIED: Save type-specific messages"""
        try:
            os.makedirs(os.path.dirname(self.messages_file), exist_ok=True)
            with open(self.messages_file, 'w', encoding='utf-8') as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Messages saved for {self.giveaway_type}")
        except Exception as e:
            self.logger.error(f"Error saving messages: {e}")

    