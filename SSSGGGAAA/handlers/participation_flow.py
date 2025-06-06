from datetime import datetime
from datetime import datetime
# from utils.async_manager import prevent_concurrent_participation

async def send_invitation(giveaway_system):
    """
    Send type-specific invitation with direct bot link
    
    Args:
        giveaway_system: GiveawaySystem instance
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        giveaway_type = giveaway_system.giveaway_type
        
        # Check if participation window is open
        if not giveaway_system.is_participation_window_open():
            giveaway_system.logger.warning(f"Attempted to send {giveaway_type} invitation outside participation window")
            return False
        
        bot_info = await giveaway_system.bot.get_me()
        bot_username = bot_info.username
        
        # Type-specific participation link
        participate_link = f"https://t.me/{bot_username}?start=participate_{giveaway_type}"
        
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [[InlineKeyboardButton(f"🎯 PARTICIPATE {giveaway_type.upper()}", url=participate_link)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = giveaway_system.message_manager.get_message("invitation")
        
        await giveaway_system.bot.send_message(
            chat_id=giveaway_system.channel_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        
        giveaway_system.logger.info(f"{giveaway_type.upper()} invitation with direct link sent to channel")
        return True
        
    except Exception as e:
        giveaway_system.logger.error(f"Error sending {giveaway_system.giveaway_type} invitation: {e}")
        return False

# @prevent_concurrent_participation()    
async def handle_participate_button( update, context, giveaway_system):
    """
    Handle participation button with type awareness
    
    Args:
        giveaway_system: GiveawaySystem instance with all services
        update: Telegram update
        context: Telegram context
    """
    try:
        query = update.callback_query
        await query.answer()
        
        user = query.from_user
        user_id = user.id
        
        # Access services through giveaway_system
        safety_manager = giveaway_system.safety_manager
        logger = giveaway_system.logger
        message_manager = giveaway_system.message_manager
        giveaway_type = giveaway_system.giveaway_type

        # PROTECCIÓN ADICIONAL MANUAL SI NECESITAS MÁS CONTROL
        operation_key = f"{user_id}_participate_{giveaway_type}"

        # Verificar si hay operación en progreso
        active_operations = safety_manager.get_active_operations()
        if operation_key in active_operations:
            await giveaway_system.bot.send_message(
                chat_id=user_id,
                text="⏳ Another participation is already in progress. Please wait...",
                parse_mode='HTML'
            )
            return
        
        # Check participation window
        if not giveaway_system.is_participation_window_open():
            window_status = giveaway_system.get_participation_window_status()
            message = message_manager.get_message(
                "participation_window_closed",
                next_window=window_status['next_open']
            )
            await giveaway_system.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode='HTML'
            )
            return
        
        # Check if already registered
        if giveaway_system._is_already_registered(user_id):
            message = message_manager.get_message("already_registered")
            await giveaway_system.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode='HTML'
            )
            return
        
        # Check if has pending registration
        if _has_pending_registration(user_id, context, giveaway_type):
            message = message_manager.get_message("registration_in_progress")
            await giveaway_system.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode='HTML'
            )
            return
        
        # Check channel membership
        if not await _check_channel_membership(giveaway_system, user_id):
            message = message_manager.get_message("not_channel_member")
            await giveaway_system.bot.send_message(
                chat_id=user_id, 
                text=message, 
                parse_mode='HTML'
            )
            return
        
        # Request MT5 account
        message = message_manager.get_message("request_mt5")
        await giveaway_system.bot.send_message(
            chat_id=user_id, 
            text=message, 
            parse_mode='HTML'
        )
        
        # Save state for this giveaway type
        context.user_data[f'awaiting_mt5_{giveaway_type}'] = True
        context.user_data[f'user_info_{giveaway_type}'] = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'giveaway_type': giveaway_type
        }
        
        logger.info(f"User {user_id} started {giveaway_type} participation process")
        
    except Exception as e:
        giveaway_system.logger.error(f"Error handling {giveaway_system.giveaway_type} participate button: {e}")
    
# @prevent_concurrent_participation()
async def handle_mt5_input(update, context, giveaway_system):
    """
    Handle MT5 input with type awareness
    
    Args:
        giveaway_system: GiveawaySystem instance
        update: Telegram update
        context: Telegram context
    """
    try:
        giveaway_type = giveaway_system.giveaway_type
        message_manager = giveaway_system.message_manager
        safety_manager = giveaway_system.safety_manager
        
        # Check if awaiting MT5 for this type
        if not context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
            return
        
        mt5_account = update.message.text.strip()
        user_info = context.user_data.get(f'user_info_{giveaway_type}')
        user_id = update.effective_user.id
        
        # 🔒 PROTECCIÓN ADICIONAL PARA MT5 INPUT
        mt5_operation_key = f"{user_id}_mt5_input_{giveaway_type}"
        
        # Verificar si hay procesamiento de MT5 en progreso
        if mt5_operation_key in safety_manager.get_active_operations():
            await update.message.reply_text(
                "⏳ Your MT5 account is being processed. Please wait...",
                parse_mode='HTML'
            )
            return
        
        # Initialize attempt counter for this type
        attempts_key = f'mt5_attempts_{giveaway_type}'
        if attempts_key not in context.user_data:
            context.user_data[attempts_key] = 0
        
        context.user_data[attempts_key] += 1
        max_attempts = 4
        remaining_attempts = max_attempts - context.user_data[attempts_key]
        
        # Validate format
        if not mt5_account.isdigit():
            if remaining_attempts > 0:
                retry_message = message_manager.get_message(
                    "invalid_format_retry",
                    remaining_attempts=remaining_attempts
                )
                await update.message.reply_text(retry_message, parse_mode='HTML')
                return
            else:
                await _handle_max_attempts_reached(giveaway_system, update, context, max_attempts)
                return
        
        # 🔒 USAR LOCK ESPECÍFICO PARA PROCESAMIENTO DE PARTICIPACIÓN
        async with safety_manager.acquire_operation_lock(mt5_operation_key):
            # Process participation with retry logic
            success = await process_participation_with_retry(
                giveaway_system, user_info, mt5_account, update, context, 
                remaining_attempts, max_attempts
            )
        
        
        # Clean state if successful or no attempts left
        if success or remaining_attempts <= 0:
            context.user_data.pop(f'awaiting_mt5_{giveaway_type}', None)
            context.user_data.pop(f'user_info_{giveaway_type}', None)
            context.user_data.pop(attempts_key, None)
        
    except Exception as e:
        giveaway_system.logger.error(f"Error processing {giveaway_system.giveaway_type} MT5 input: {e}")
        await update.message.reply_text(
            giveaway_system.message_manager.get_message("error_internal"),
            parse_mode='HTML'
        )
    
async def process_participation_with_retry(user_info, mt5_account, update, context, remaining_attempts, max_attempts, giveaway_system):
    """
    Process participation with retry logic and type awareness
    
    Args:
        giveaway_system: GiveawaySystem instance
        user_info: User information dict
        mt5_account: MT5 account number
        update: Telegram update
        context: Telegram context
        remaining_attempts: Remaining attempts
        max_attempts: Maximum attempts allowed
    
    Returns:
        bool: True if successful or should end process, False to continue retrying
    """
    try:
        user_id = user_info['id']
        giveaway_type = giveaway_system.giveaway_type
        message_manager = giveaway_system.message_manager
        safety_manager = giveaway_system.safety_manager
        
        # 🔒 LOCK ESPECÍFICO PARA VALIDACIÓN DE CUENTA
        validation_key = f"{user_id}_validate_{mt5_account}_{giveaway_type}"
        
        # Check if user already participated in this period
        async with safety_manager.acquire_operation_lock(validation_key):
            # Check if user already participated in this period
            already_participated, previous_account = giveaway_system._user_already_participated_today(user_id)
            if already_participated:
                period_name = {
                    'daily': 'day',
                    'weekly': 'week', 
                    'monthly': 'month'
                }.get(giveaway_type, 'period')
                
                await update.message.reply_text(
                    f"❌ <b>Already participated this {period_name}</b>\n\n"
                    f"You already participated in this {period_name}'s {giveaway_type.upper()} giveaway with MT5 account: <code>{previous_account}</code>\n\n"
                    f"💡 <b>Rule:</b> Only one participation per user per {giveaway_type} {period_name}, regardless of the MT5 account used.\n\n"
                    f"🎁 You can participate in the next {giveaway_type} {period_name}.",
                    parse_mode='HTML'
                )
                return True  # End process
        
        # Validation 1: User already registered for this type today?
        if giveaway_system._is_already_registered(user_id):
            message = message_manager.get_message("already_registered")
            await update.message.reply_text(message, parse_mode='HTML')
            return True
        
        # Validation 2: Account already used today for this type?
        account_used_today, other_user_id = giveaway_system._is_account_already_used_today(mt5_account)
        if account_used_today:
            if remaining_attempts > 0:
                retry_message = f"❌ <b>Account already registered today</b>\n\nThis MT5 account was already used today for the {giveaway_type} giveaway by another user.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Try with a different account:"
                await update.message.reply_text(retry_message, parse_mode='HTML')
                return False
            else:
                await _handle_max_attempts_reached(giveaway_system, update, context, max_attempts)
                return True
        
        # Validation 3: Account belongs to another user historically?
        is_other_user_account, owner_id, first_used = giveaway_system._is_account_owned_by_other_user(mt5_account, user_id)
        if is_other_user_account:
            if remaining_attempts > 0:
                retry_message = f"❌ <b>Account belongs to another user</b>\n\nThis MT5 account was previously registered by another participant.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use an MT5 account that is exclusively yours:"
                await update.message.reply_text(retry_message, parse_mode='HTML')
                return False
            else:
                await _handle_max_attempts_reached(giveaway_system, update, context, max_attempts)
                return True
        
        # Validation 4: Validate MT5 account with API
        validation_result = giveaway_system.validate_account_for_giveaway(mt5_account, user_id)
        
        if not validation_result['valid']:
            error_type = validation_result['error_type']
            
            if remaining_attempts > 0:
                if error_type == 'not_found':
                    retry_message = f"❌ <b>Account not found</b>\n\nMT5 account #{mt5_account} was not found in our records.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Verify the number and try again:"
                elif error_type == 'not_live':
                    retry_message = f"❌ <b>Invalid account</b>\n\nOnly MT5 LIVE accounts can participate in the giveaway.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use a LIVE account and try again:"
                elif error_type == 'insufficient_balance':
                    balance = validation_result.get('balance', 0)
                    retry_message = f"❌ <b>Insufficient balance</b>\n\nMinimum balance of $100 USD required\nYour current balance: <b>${balance}</b>\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Use an account with sufficient balance:"
                else:
                    retry_message = f"❌ <b>Verification error</b>\n\nWe couldn't verify your account at this time.\n\n🔄 Attempts remaining: <b>{remaining_attempts}</b>\n\n💡 Try with another account:"
                
                await update.message.reply_text(retry_message, parse_mode='HTML')
                return False
            else:
                await _handle_max_attempts_reached(giveaway_system, update, context, max_attempts)
                return True
        
        # Validation 5: Check channel membership
        if not await _check_channel_membership(giveaway_system, user_id):
            message = message_manager.get_message("not_channel_member")
            await update.message.reply_text(message, parse_mode='HTML')
            return True
        
        # ALL VALIDATIONS PASSED - Save participant
        participant_data = {
            'telegram_id': user_id,
            'username': user_info.get('username', ''),
            'first_name': user_info.get('first_name', ''),
            'mt5_account': mt5_account,
            'balance': validation_result['balance'],
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'active',
            'giveaway_type': giveaway_type
        }
        
        giveaway_system._save_participant(participant_data)
        
        # Get user history for personalized message
        user_history = giveaway_system.stats_manager.get_user_account_history(user_id)
        
        if len(user_history) > 1:
            unique_accounts = len(set(acc['mt5_account'] for acc in user_history))
            success_message = message_manager.get_message(
                "success_with_history",
                account=mt5_account,
                total_participations=len(user_history),
                unique_accounts=unique_accounts
            )
        else:
            success_message = message_manager.get_message("success_first_time")
        
        await update.message.reply_text(success_message, parse_mode='HTML')
        
        giveaway_system.logger.info(f"User {user_id} registered successfully for {giveaway_type} giveaway with account {mt5_account}")
        
        return True
        
    except Exception as e:
        giveaway_system.logger.error(f"Error processing {giveaway_system.giveaway_type} participation with retries: {e}")
        await update.message.reply_text(
            giveaway_system.message_manager.get_message("error_internal"),
            parse_mode='HTML'
        )
        return True
    
async def _handle_max_attempts_reached(update, context, max_attempts, giveaway_system):
    """Handle max attempts with type awareness"""
    try:
        giveaway_type = giveaway_system.giveaway_type
        message_manager = giveaway_system.message_manager
        
        max_attempts_message = message_manager.get_message(
            "max_attempts_reached",
            max_attempts=max_attempts
        )
        
        await update.message.reply_text(max_attempts_message, parse_mode='HTML')
        
        # Clean type-specific state
        context.user_data.pop(f'awaiting_mt5_{giveaway_type}', None)
        context.user_data.pop(f'user_info_{giveaway_type}', None)
        context.user_data.pop(f'mt5_attempts_{giveaway_type}', None)
        
        user_id = context.user_data.get(f'user_info_{giveaway_type}', {}).get('id', 'unknown')
        giveaway_system.logger.info(f"User {user_id} reached max attempts for {giveaway_type} giveaway")
        
    except Exception as e:
        giveaway_system.logger.error(f"Error handling max attempts for {giveaway_system.giveaway_type}: {e}")

async def _check_channel_membership(giveaway_system, user_id):
    """Check channel membership"""
    try:
        member = await giveaway_system.bot.get_chat_member(giveaway_system.channel_id, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        giveaway_system.logger.error(f"Error checking membership: {e}")
        return False
    
def _has_pending_registration(user_id, context, giveaway_type):
    """Check pending registration for specific type"""
    return (context.user_data.get(f'awaiting_mt5_{giveaway_type}') and 
            context.user_data.get(f'user_info_{giveaway_type}', {}).get('id') == user_id)

