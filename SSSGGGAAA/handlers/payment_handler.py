# 🔄 MOVER desde ga_manager.py
import asyncio
from datetime import datetime
import time
from utils.async_manager import prevent_concurrent_callback
from utils.admin_permission import SystemAction
from utils.admin_permission import get_permission_manager
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging

# @require_giveaway_lock() _execute_payment_confirmation se FUSIONÓ con confirm_payment_and_announce en una sola función.
async def confirm_payment_and_announce(winner_telegram_id, confirmed_by_admin_id, giveaway_system):
    """
    Confirm payment and announce with complete async protection
    
    Args:
        giveaway_system: GiveawaySystem instance with safety_manager
        winner_telegram_id: Telegram ID of winner
        confirmed_by_admin_id: Admin ID who confirmed
    
    Returns:
        tuple: (success: bool, message: str)
    """
    giveaway_type = giveaway_system.giveaway_type
    safety_manager = giveaway_system.safety_manager
    
    # 🔒 PROTECCIÓN CONTRA CONCURRENCIA (reemplaza el current_task approach)
    payment_operation_key = f"payment_{giveaway_type}_{winner_telegram_id}"
    
    # Verificar si el pago ya está siendo procesado
    if payment_operation_key in safety_manager.get_active_operations():
        return False, "Payment confirmation already in progress"
    
    try:
        # 🔒 USAR LOCK ESPECÍFICO PARA PAGOS
        async with safety_manager.acquire_payment_lock(str(winner_telegram_id), giveaway_type):
            giveaway_system.logger.info(f"Starting protected {giveaway_type.upper()} payment confirmation for {winner_telegram_id}")
            
            # 1. Find pending winner data
            winner_data = giveaway_system._get_pending_winner_data(winner_telegram_id)
            if not winner_data:
                return False, f"No pending {giveaway_type} winner found or already processed"
            
            # Verificar estado actual antes de proceder
            current_status = giveaway_system._get_winner_current_status(winner_telegram_id)
            if current_status != 'pending_payment':
                return False, f"Winner {winner_telegram_id} is not in pending_payment status (current: {current_status})"
            
            # 2. Update status to payment_confirmed (ya protegido por @require_file_safety)
            update_success = giveaway_system._update_winner_status(
                winner_telegram_id, "payment_confirmed", confirmed_by_admin_id
            )
            if not update_success:
                return False, f"Error updating {giveaway_type} winner status"
            
            # 3. Save to definitive winners history (ya protegido por @require_file_safety)
            giveaway_system._save_confirmed_winner(winner_data)
            
            # 4. Public announcement
            await _announce_winner_public(giveaway_system, winner_data)
            
            # 5. Private congratulation
            await _congratulate_winner_private(giveaway_system, winner_data)
            
            # 6. Notify completion
            await _notify_completion(giveaway_system, confirmed_by_admin_id)
            
            giveaway_system.logger.info(f"{giveaway_type.upper()} payment confirmation completed successfully (protected)")
            return True, f"{giveaway_type.title()} payment confirmed and winner announced"
    
    except asyncio.TimeoutError:
        giveaway_system.logger.error(f"Payment confirmation timeout for {giveaway_type} winner {winner_telegram_id}")
        return False, "Payment confirmation timeout - please try again"
    
    except Exception as e:
        giveaway_system.logger.error(f"Error confirming {giveaway_type} payment: {e}")
        return False, f"Payment confirmation error: {e}"

async def _announce_winner_public(winner_data, giveaway_system):
    """Announce winner with protection against multiple announcements"""
    try:
        safety_manager = giveaway_system.safety_manager
        announce_key = f"announce_{giveaway_system.giveaway_type}_{winner_data['telegram_id']}"
        
        # Verificar si ya se anunció
        if announce_key in safety_manager.get_active_operations():
            giveaway_system.logger.warning(f"Winner announcement already in progress for {winner_data['telegram_id']}")
            return
        
        async with safety_manager.acquire_operation_lock(announce_key):
            username = winner_data.get('username', '')
            first_name = winner_data.get('first_name', 'Winner').strip()
            
            if username:
                winner_display = f"@{username}" if not username.startswith('@') else username
            else:
                winner_display = first_name
            
            total_participants = giveaway_system._get_period_participants_count()
            prize = giveaway_system.get_prize_amount()
            
            message = giveaway_system.message_manager.get_message(
                "winner_announcement",
                username=winner_display,
                prize=prize,
                account=winner_data['mt5_account'],
                total_participants=total_participants
            )
            
            await giveaway_system.bot.send_message(
                chat_id=giveaway_system.channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            giveaway_system.logger.info(f"{giveaway_system.giveaway_type.title()} winner announced publicly (protected)")
        
    except Exception as e:
        giveaway_system.logger.error(f"Error in protected winner announcement: {e}")
    
async def _congratulate_winner_private(winner_data, giveaway_system):
    """Send private congratulation with protection"""
    try:
        safety_manager = giveaway_system.safety_manager
        congratulate_key = f"congratulate_{giveaway_system.giveaway_type}_{winner_data['telegram_id']}"
        
        async with safety_manager.acquire_operation_lock(congratulate_key):
            prize = giveaway_system.get_prize_amount()
            
            message = giveaway_system.message_manager.get_message(
                "winner_private_congratulation",
                prize=prize,
                account=winner_data['mt5_account']
            )
            
            # Add admin contact info
            admin_username = await _get_admin_username(giveaway_system)
            if admin_username:
                message += f"\n\n📞 <b>To confirm receipt:</b>\nContact administrator: @{admin_username}"
            
            await giveaway_system.bot.send_message(
                chat_id=winner_data['telegram_id'],
                text=message,
                parse_mode='HTML'
            )
            
            giveaway_system.logger.info(f"Protected private congratulation sent to {giveaway_system.giveaway_type} winner")
        
    except Exception as e:
        giveaway_system.logger.error(f"Error in protected private congratulation: {e}")

async def _notify_admin_winner(winner, total_participants, giveaway_system, prize_amount=None):
    """
    Notify Main Administrator about new winner with protection
    
    Args:
        giveaway_system: GiveawaySystem instance
        winner: Winner data dict
        total_participants: Number of participants
        prize_amount: Prize amount (optional)
    """
    giveaway_type = giveaway_system.giveaway_type
    safety_manager = giveaway_system.safety_manager
    
    if prize_amount is None:
        prize_amount = giveaway_system.get_prize_amount()
    
    # 🔒 PROTECCIÓN PARA NOTIFICACIONES ADMIN
    notification_key = f"notify_admin_{giveaway_type}_{winner['telegram_id']}"
    
    try:
        async with safety_manager.acquire_operation_lock(notification_key):
            today = datetime.now().strftime('%Y-%m-%d')
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            
            if username:
                winner_display = f"@{username}"
                command_identifier = username
            else:
                winner_display = f"{first_name} (No username)"
                command_identifier = winner['telegram_id']
            
            # Get main admin ID
            main_admin_id = _get_main_admin_id(giveaway_system)
            
            # Personal message to main admin
            personal_message = f"""📱 <b>PERSONAL NOTIFICATION - {giveaway_type.upper()}</b>

🎉 <b>Winner Selected:</b> {first_name} ({winner_display})
💰 <b>Prize:</b> ${prize_amount} USD
📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
👥 <b>Total participants:</b> {total_participants}
📅 <b>Date:</b> {today}

ℹ️ <b>Next Steps:</b>
1️⃣ Admin channel has been notified for payment confirmation
2️⃣ Authorized payment admins will handle the transfer
3️⃣ You will receive confirmation when payment is completed

💡 <b>Status:</b> Winner selected, awaiting payment confirmation"""

            await giveaway_system.bot.send_message(
                chat_id=main_admin_id,
                text=personal_message,
                parse_mode='HTML'
            )
            
            # Message to admin channel with button
            await _notify_admin_channel(giveaway_system, winner, total_participants, prize_amount, command_identifier)
            
            giveaway_system.logger.info(f"Protected winner notifications sent for {giveaway_type}")
        
    except Exception as e:
        giveaway_system.logger.error(f"Error in protected admin notification for {giveaway_type}: {e}")

async def _notify_admin_channel(giveaway_system, winner, total_participants, prize_amount, command_identifier):
    """Notify admin channel with protection"""
    try:
        giveaway_type = giveaway_system.giveaway_type
        first_name = winner.get('first_name', 'N/A')
        username = winner.get('username', '').strip()
        winner_display = f"@{username}" if username else f"{first_name} (No username)"
        
        admin_config = giveaway_system.config_loader.get_all_config().get('admin_notifications', {})
        admin_channel_id = admin_config.get('admin_channel_id')
        
        if admin_channel_id:
            channel_message = f"""🔔 <b>{giveaway_type.upper()} WINNER - PAYMENT CONFIRMATION NEEDED</b>

🎯 <b>Winner:</b> {first_name} ({winner_display})
💰 <b>Prize:</b> ${prize_amount} USD
📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
👥 <b>Participants:</b> {total_participants}

⚠️ <b>ACTION REQUIRED:</b>
💸 Transfer ${prize_amount} USD to MT5 account: <code>{winner['mt5_account']}</code>
✅ Press button below after completing transfer

🎯 <b>Authorized for payment confirmation:</b>
- PAYMENT_SPECIALIST level admins
- FULL_ADMIN level admins"""

            # Create confirmation button
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            button_text = f"✅ Confirm ${prize_amount} Payment to {first_name}"
            callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
            keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await giveaway_system.bot.send_message(
                chat_id=admin_channel_id,
                text=channel_message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
    except Exception as e:
        giveaway_system.logger.error(f"Error notifying admin channel: {e}")

def _get_main_admin_id(giveaway_system):
    """Get main administrator ID"""
    try:
        # Try to get from permission manager if available
        if hasattr(giveaway_system.bot, 'application') and hasattr(giveaway_system.bot.application, 'bot_data'):
            permission_manager = giveaway_system.bot.application.bot_data.get('permission_manager')
            if permission_manager:
                main_admin_id = permission_manager.get_main_admin_id()
                if main_admin_id:
                    return main_admin_id
        
        # Fallback to config
        return giveaway_system.admin_id
    except:
        return giveaway_system.admin_id

async def _get_admin_username(giveaway_system):
    """Get administrator username"""
    try:
        admin_info = await giveaway_system.bot.get_chat(giveaway_system.admin_id)
        return admin_info.username
    except Exception as e:
        giveaway_system.logger.error(f"Error getting admin info: {e}")
        return None            

async def _notify_completion(giveaway_system, confirmed_by_admin_id):
    """Notify about payment completion"""
    try:
        main_admin_id = _get_main_admin_id(giveaway_system)
        completion_msg = f"✅ {giveaway_system.giveaway_type.title()} payment confirmed by admin {confirmed_by_admin_id}. Winner announced and congratulated."
        
        await giveaway_system.bot.send_message(chat_id=main_admin_id, text=completion_msg)
        
        # Also notify admin channel
        admin_config = giveaway_system.config_loader.get_all_config().get('admin_notifications', {})
        admin_channel_id = admin_config.get('admin_channel_id')
        if admin_channel_id:
            await giveaway_system.bot.send_message(chat_id=admin_channel_id, text=completion_msg)
            
    except Exception as e:
        giveaway_system.logger.error(f"Error notifying completion: {e}")

async def _execute_payment_confirmation(self, winner_telegram_id, confirmed_by_admin_id, giveaway_type=None):
        """
        🆕 NEW: Lógica completa de confirmación de pago extraída para protección
        Esta función contiene toda la implementación original de confirm_payment_and_announce
        """
        if giveaway_type is None:
            giveaway_type = self.giveaway_type

        # 🔒 SIMPLE CONCURRENCY CHECK
        operation_key = f"payment_{giveaway_type}_{winner_telegram_id}"
        
        if not hasattr(self, '_active_payments'):
            self._active_payments = set()
        # 🔧 ENHANCED: Check with timeout and forced cleanup
        if operation_key in self._active_payments:
            # Check if this is a stale lock (older than 30 seconds)
            if not hasattr(self, '_payment_timestamps'):
                self._payment_timestamps = {}
            
            # import time
            current_time = time.time()
            lock_time = self._payment_timestamps.get(operation_key, current_time)
            
            if current_time - lock_time > 30:  # 30 second timeout
                print(f"🧹 DEBUG: Cleaning stale payment lock for {operation_key}")
                self._active_payments.discard(operation_key)
                self._payment_timestamps.pop(operation_key, None)
            else:
                return False, "Payment confirmation already in progress"
        
        # Mark as active with timestamp
        self._active_payments.add(operation_key)
        if not hasattr(self, '_payment_timestamps'):
            self._payment_timestamps = {}
        self._payment_timestamps[operation_key] = time.time()
        
        try:
            print(f"🔍 DEBUG: ===== STARTING {giveaway_type.upper()} PAYMENT CONFIRMATION =====")
            print(f"🔍 DEBUG: Winner ID: {winner_telegram_id}")
            print(f"🔍 DEBUG: Confirmed by admin: {confirmed_by_admin_id}")
            
            # 1. Find pending winner data
            print(f"🔍 DEBUG: Step 1 - Finding winner data...")
            winner_data = self._get_pending_winner_data(winner_telegram_id, giveaway_type)
            if not winner_data:
                print(f"❌ DEBUG: No pending {giveaway_type} winner found with ID {winner_telegram_id}")
                return False, f"No pending {giveaway_type} winner found or already processed"
            
            print(f"✅ DEBUG: {giveaway_type.title()} winner found: {winner_data['first_name']} (MT5: {winner_data['mt5_account']})")
            
            # 2. Update status to payment_confirmed
            print(f"🔍 DEBUG: Step 2 - Updating status...")
            update_success = self._update_winner_status(winner_telegram_id, "payment_confirmed", confirmed_by_admin_id, giveaway_type)
            if not update_success:
                print(f"❌ DEBUG: ERROR updating {giveaway_type} winner status {winner_telegram_id}")
                return False, f"Error updating {giveaway_type} winner status"
            
            print(f"✅ DEBUG: {giveaway_type.title()} status updated successfully")
            
            # 3. Save to definitive winners history
            print(f"🔍 DEBUG: Step 3 - Saving to definitive history...")
            self._save_confirmed_winner(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} winner saved to definitive history")
            
            # 4. Public announcement
            print(f"🔍 DEBUG: Step 4 - Public announcement...")
            await self._announce_winner_public(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} public announcement sent")
            
            # 5. Private congratulation
            print(f"🔍 DEBUG: Step 5 - Private congratulation...")
            await self._congratulate_winner_private(winner_data, giveaway_type)
            print(f"✅ DEBUG: {giveaway_type.title()} private congratulation sent")

            # 🆕 SOLO AGREGAR ESTAS 2 LÍNEAS:
            # 6. Notify main admin of completion
            permission_manager = None
            try:
                if hasattr(self.bot, 'application') and hasattr(self.bot.application, 'bot_data'):
                    permission_manager = self.bot.application.bot_data.get('permission_manager')
            except:
                pass

            main_admin_id = None
            if permission_manager:
                main_admin_id = permission_manager.get_main_admin_id()  # Busca "Main Administrator"

            if not main_admin_id:
                main_admin_id = self.admin_id  # fallback

            completion_msg = f"✅ {giveaway_type.title()} payment confirmed by admin {confirmed_by_admin_id}. Winner announced and congratulated."
            await self.bot.send_message(chat_id=main_admin_id, text=completion_msg)  # 🎯 Ahora a tu cuenta profesional

            # 7. Notify admin channel of completion
            admin_config = self.config_loader.get_all_config().get('admin_notifications', {})
            admin_channel_id = admin_config.get('admin_channel_id')
            if admin_channel_id:
                await self.bot.send_message(chat_id=admin_channel_id, text=completion_msg)
            
            print(f"🔍 DEBUG: ===== {giveaway_type.upper()} CONFIRMATION COMPLETED =====")
            return True, f"{giveaway_type.title()} payment confirmed and winner announced"
            
        except Exception as e:
            self.logger.error(f"Error confirming {giveaway_type} payment: {e}")
            print(f"❌ DEBUG: EXCEPTION in {giveaway_type} payment confirmation: {e}")
            
            return False, f"Error: {e}"
        finally:
            # 🆕 CRITICAL: Always clean up the lock in finally block
            try:
                self._active_payments.discard(operation_key)
                if hasattr(self, '_payment_timestamps'):
                    self._payment_timestamps.pop(operation_key, None)
                print(f"🧹 DEBUG: Cleaned up payment lock for {operation_key}")
            except Exception as cleanup_error:
                print(f"⚠️ DEBUG: Error cleaning payment lock: {cleanup_error}")


# 🔄 MOVER desde la clase de ga_integration.py
# async def find_winner_by_identifier(self, winner_identifier, giveaway_type, giveaway_system):
#         """
#         🔍 Helper function to find winner by username or telegram_id
#         Esta función estaba en test_botTTT.py pero se usa en las funciones movidas
#         """
#         try:
#             pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
#             for winner in pending_winners:
#                 winner_username = winner.get('username', '').strip()
#                 winner_telegram_id = winner.get('telegram_id', '').strip()
#                 winner_first_name = winner.get('first_name', '').strip()
                
#                 # Search by different criteria
#                 if (
#                     winner_identifier == winner_telegram_id or
#                     winner_identifier.lower() == f"@{winner_username}".lower() or
#                     winner_identifier.lower() == winner_username.lower() or
#                     (not winner_username and winner_identifier.lower() == winner_first_name.lower())
#                 ):
#                     return winner_telegram_id
            
#             return None
            
#         except Exception as e:
#             logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
#             return None

async def admin_confirm_payment_universal(integration_instance, update, context, giveaway_type):
        """🌟 Confirmación universal de pagos - movido desde test_botTTT.py"""
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)
        admin_info = permission_manager.get_admin_info(user_id)
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
        
        # Configuración dinámica
        type_configs = {
            'daily': {
                'display_name': 'Daily',
                'command': '/admin_confirm_daily',
                'permission': SystemAction.CONFIRM_DAILY_PAYMENTS
            },
            'weekly': {
                'display_name': 'Weekly', 
                'command': '/admin_confirm_weekly',
                'permission': SystemAction.CONFIRM_WEEKLY_PAYMENTS
            },
            'monthly': {
                'display_name': 'Monthly',
                'command': '/admin_confirm_monthly',
                'permission': SystemAction.CONFIRM_MONTHLY_PAYMENTS
            }
        }
        
        config = type_configs.get(giveaway_type)
        if not config:
            await update.message.reply_text(f"❌ Invalid giveaway type: {giveaway_type}")
            return
        
        # Validación de parámetros
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                f"❌ <b>Incorrect usage for {config['display_name']} Payment</b>\n\n"
                f"<b>Format:</b> <code>{config['command']} &lt;username_or_telegram_id&gt;</code>\n\n"
                f"<b>Examples:</b>\n"
                f"• <code>{config['command']} @username</code>\n"
                f"• <code>{config['command']} 123456789</code>\n\n"
                f"💡 Use <code>/admin_pending_{giveaway_type}</code> to see pending {giveaway_type} winners",
                parse_mode='HTML'
            )
            return
        
        winner_identifier = context.args[0].strip()
        print(f"✅ {config['display_name']} payment confirmation authorized for: {admin_name} ({user_id})")
        
        try:
            # Usar sistema existente
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await update.message.reply_text(
                    f"❌ <b>{config['display_name']} giveaway system not available</b>",
                    parse_mode='HTML'
                )
                return
            
            # Buscar ganador                     find_winner_by_identifier
            winner_telegram_id = await integration_instance.find_winner_by_identifier(winner_identifier, giveaway_type, giveaway_system)
            
            if not winner_telegram_id:
                await update.message.reply_text(
                    f"❌ <b>{config['display_name']} winner not found</b>\n\n"
                    f"No pending {giveaway_type} winner found with: <code>{winner_identifier}</code>\n\n"
                    f"💡 Use <code>/admin_pending_{giveaway_type}</code> to see all pending {giveaway_type} winners",
                    parse_mode='HTML'
                )
                return
            
            # Confirmar pago
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                prize = giveaway_system.get_prize_amount(giveaway_type)
                response_message = f"""✅ <b>{config['display_name']} Payment Confirmed Successfully</b>

👤 <b>Confirmed by:</b> {admin_name}
🎯 <b>Winner:</b> {winner_identifier}
💰 <b>Prize:</b> ${prize} USD
🎲 <b>Giveaway Type:</b> {config['display_name']}
📅 <b>Confirmation Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ <b>Actions completed:</b>
├─ Winner announced publicly in channel
├─ Private congratulation sent to winner
├─ Payment status updated in system
└─ System prepared for next {giveaway_type} draw

💡 <b>Status:</b> Payment process complete ✓"""
                
                await update.message.reply_text(response_message, parse_mode='HTML')
                
                # Log de auditoría
                permission_manager.log_action(
                    user_id, 
                    config['permission'], 
                    f"{config['display_name']} payment confirmed for {winner_identifier} (${prize})"
                )
                
            else:
                await update.message.reply_text(
                    f"❌ <b>Error confirming {config['display_name']} payment</b>\n\n"
                    f"Reason: {message}\n\n"
                    f"💡 This usually means:\n"
                    f"• Winner was already processed\n"
                    f"• System error occurred\n"
                    f"• Invalid winner state\n\n"
                    f"Contact a FULL_ADMIN if the issue persists.",
                    parse_mode='HTML'
                )
                
                permission_manager.log_action(
                    user_id, 
                    config['permission'], 
                    f"Failed to confirm {giveaway_type} payment for {winner_identifier}: {message}"
                )
            
        except Exception as e:
            logging.error(f"Error in {giveaway_type} payment confirmation: {e}")
            await update.message.reply_text(
                f"❌ <b>System error during {config['display_name']} payment confirmation</b>\n\n"
                f"Please try again in a few moments or contact a FULL_ADMIN.",
                parse_mode='HTML'
            )

async def admin_view_pending_universal(integration_instance, update, context, giveaway_type):
        """Ver ganadores pendientes por tipo - movido desde test_botTTT.py"""
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)
        admin_info = permission_manager.get_admin_info(user_id)
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
        
        display_name = giveaway_type.title()
        
        try:
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await update.message.reply_text(f"❌ {display_name} giveaway system not available")
                return
            
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                next_draw_time = giveaway_system.get_next_draw_time(giveaway_type)
                next_draw_str = next_draw_time.strftime('%Y-%m-%d %H:%M') if next_draw_time else "Check schedule"
                
                await update.message.reply_text(
                    f"ℹ️ <b>No pending {giveaway_type} winners</b>\n\n"
                    f"All {giveaway_type} payments are up to date.\n\n"
                    f"🎯 <b>Next {giveaway_type} draw:</b> {next_draw_str}",
                    parse_mode='HTML'
                )
                return
            
            message = f"""📋 <b>PENDING {display_name.upper()} WINNERS ({len(pending_winners)})</b>
<i>Viewed by: {admin_name}</i>

"""
            
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    display_name_winner = f"@{username}"
                    command_identifier = f"@{username}"
                else:
                    display_name_winner = f"{first_name} (ID: {winner['telegram_id']})"
                    command_identifier = winner['telegram_id']
                
                message += f"""{i}. <b>{first_name}</b> ({display_name_winner})
   📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
   💰 <b>Prize:</b> ${winner['prize']} USD
   📅 <b>Selected:</b> {winner['selected_time']}
   💡 <b>Command:</b> <code>/admin_confirm_{giveaway_type} {command_identifier}</code>

"""
            
            message += f"""💡 <b>Payment Instructions:</b>
1️⃣ Transfer the prize amount to the corresponding MT5 account
2️⃣ Use the confirmation command shown above for each winner
3️⃣ Bot will automatically announce the winner and send congratulations

📊 <b>Total pending amount:</b> ${len(pending_winners) * prize} USD"""
            
            await update.message.reply_text(message, parse_mode='HTML')
            
            permission_manager.log_action(
                user_id, 
                SystemAction.VIEW_ALL_PENDING_WINNERS, 
                f"Viewed {len(pending_winners)} pending {giveaway_type} winners"
            )
            
        except Exception as e:
            logging.error(f"Error getting pending {giveaway_type} winners: {e}")
            await update.message.reply_text(f"❌ Error getting pending {giveaway_type} winners")

async def notify_payment_admins_new_winner(integration_instance, context, winner, giveaway_type, executed_by):
        """🔄 MODIFIED: Simplified notification - only main admin + channel"""
        try:
            logging.info(f"Sending {giveaway_type} winner notifications...")
            
            # 1️⃣ Notify main admin individually (detailed notification)
            await integration_instance._notify_main_admin_only(winner, giveaway_type, executed_by)
            
            # 2️⃣ Notify admin channel (group notification)
            await integration_instance._send_admin_channel_notification(integration_instance, giveaway_type, winner, 'winner')
            
            # ✅ SIMPLIFIED: No more individual spam to all admins
            logging.info(f"{giveaway_type.title()} notifications sent: Main admin + Admin channel")
            
        except Exception as e:
            logging.error(f"Error in simplified notification system: {e}")
    
async def _notify_main_admin_only(integration_instance, winner, giveaway_type, executed_by):
        """🆕 NEW: Send notification ONLY to main administrator"""
        try:
            # Get main admin ID from config
            main_admin_id = integration_instance.admin_id  # This is your ID from config
            
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            
            # Get prize amount
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # Create comprehensive notification for main admin
            main_admin_message = f"""🤖 <b>AUTOMATIC {giveaway_type.upper()} WINNER - MAIN ADMIN NOTIFICATION</b>

    🎉 <b>Winner Selected:</b> {first_name} ({winner_display})
    📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
    💰 <b>Prize:</b> ${prize} USD
    🎯 <b>Giveaway Type:</b> {giveaway_type.upper()}
    👤 <b>Executed by:</b> {executed_by}
    📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    ⚠️ <b>PAYMENT REQUIRED:</b>
    💸 Transfer ${prize} USD to MT5 account: <code>{winner['mt5_account']}</code>

    💡 <b>Confirmation Commands:</b>
    - <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code>
    - Or use the admin panel buttons

    🔔 <b>Notification Status:</b>
    ├─ Main Admin: ✅ You (individual notification)
    ├─ Admin Channel: ✅ Group notification sent
    └─ Other Admins: ❌ No individual spam

    🎯 <b>Next Steps:</b>
    1️⃣ Process payment to MT5 account
    2️⃣ Confirm using command or admin panel
    3️⃣ Winner will be announced automatically"""

            # Send only to main admin
            await integration_instance.app.bot.send_message(
                chat_id=main_admin_id,
                text=main_admin_message,
                parse_mode='HTML'
            )
            
            logging.info(f"Main admin notification sent for {giveaway_type} winner: {winner['telegram_id']}")
            
        except Exception as e:
            logging.error(f"Error notifying main admin: {e}")

async def _send_admin_channel_notification(integration_instance, giveaway_type: str, winner=None, notification_type='winner' ,custom_message=None):
        """🆕 Send notification to admin channel if configured"""
        try:
            admin_config = integration_instance.config_loader.get_all_config().get('admin_notifications', {})
            admin_channel_id = admin_config.get('admin_channel_id')
            
            if not admin_channel_id  or admin_channel_id == "-1001234567890":
                logging.info("No admin channel configured, skipping group notification")
                return
                
            
            if custom_message:
                message = custom_message
            elif notification_type == 'winner' and winner:
                prize = integration_instance.get_giveaway_system(giveaway_type).get_prize_amount(giveaway_type)
                username = winner.get('username', '')
                username_display = f"@{username}" if username else "no_username"
                
                message = f"""🤖 <b>AUTOMATIC DRAW COMPLETED</b>

🎯 <b>Giveaway:</b> {giveaway_type.upper()} (${prize} USD)
🎉 <b>Winner:</b> {winner.get('first_name', 'N/A')} ({username_display})
📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ <b>PAYMENT REQUIRED</b> Pending manual transfer
💸 Transfer ${prize} USD to account <code>{winner['mt5_account']}</code>
📱 Confirm: <code>/admin_confirm_{giveaway_type} {username or winner['telegram_id']}</code>

🔔 Individual notifications sent to authorized payment admins.
🎯 Winner will receive private congratulation after payment confirmation."""
            else:
                return  # No message to send
            
            await integration_instance.app.bot.send_message(
                chat_id=admin_channel_id,
                text=message,
                parse_mode='HTML'
            )
            
            logging.info(f"✅ Admin channel notification sent for {giveaway_type} {notification_type}")
            
        except Exception as e:
            logging.error(f"Error sending admin channel notification: {e}")

async def show_view_only_dashboard_simple(integration_instance, update, context, admin_info):
    """📊 Dashboard simple para VIEW_ONLY - VERSIÓN SIMPLIFICADA"""
    try:
        user_id = update.effective_user.id
        admin_name = admin_info.get('name', 'VIEW_ONLY User')
        
        print(f"🔍 DEBUG: Showing VIEW_ONLY dashboard for {admin_name} ({user_id})")
        
        # Obtener estadísticas básicas
        total_today = 0
        active_windows = 0
        giveaway_status = []
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            if giveaway_system:
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                is_open = giveaway_system.is_participation_window_open(giveaway_type)
                
                total_today += today_count
                if is_open:
                    active_windows += 1
                
                status_emoji = "🟢" if is_open else "🔴"
                giveaway_status.append(f"{status_emoji} <b>{giveaway_type.upper()}</b> (${prize}): {today_count} today")
        
        current_time = datetime.now()
        
        message = f"""📊 <b>VIEW_ONLY MONITORING DASHBOARD</b>

👤 <b>Admin:</b> {admin_name}
🔒 <b>Access Level:</b> VIEW_ONLY
📅 <b>Date:</b> {current_time.strftime('%Y-%m-%d %H:%M')} London Time

📊 <b>Today's Activity:</b>
├─ Total participants: <b>{total_today}</b>
├─ Active windows: <b>{active_windows}/3</b>
└─ System status: <b>✅ Operational</b>

🎯 <b>Giveaway Overview:</b>
{chr(10).join(giveaway_status)}

💡 <b>Your VIEW_ONLY Permissions:</b>
✅ Monitor daily participation statistics
✅ Check system operational status
✅ View participation window status
❌ Execute giveaways (requires PAYMENT_SPECIALIST+)
❌ View pending winners (requires PAYMENT_SPECIALIST+)
❌ System administration (requires FULL_ADMIN)

🔄 Use buttons below for more information."""

        # Botones simples y funcionales
        buttons = [
            [
                InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details"),
                InlineKeyboardButton("🏥 System Check", callback_data="view_only_health")
            ],
            [
                InlineKeyboardButton("🔄 Refresh Data", callback_data="view_only_refresh"),
                InlineKeyboardButton("ℹ️ Permissions", callback_data="view_only_permissions_info")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
        print(f"✅ DEBUG: VIEW_ONLY dashboard sent successfully to {admin_name}")
        
    except Exception as e:
        logging.error(f"Error showing VIEW_ONLY dashboard: {e}")
        print(f"❌ DEBUG: Error in VIEW_ONLY dashboard: {e}")
        await update.message.reply_text("❌ Error loading VIEW_ONLY dashboard")

# prueba
async def _handle_payment_from_admin_channel(integration_instance, update, context):
        """🆕 NEW: Handle payment confirmations from admin channel notifications"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            callback_data = query.data
            
            print(f"💰 DEBUG: Admin channel payment callback: {callback_data} from user {user_id}")
            
            # Verify admin permissions using permission manager
            permission_manager = integration_instance._get_permission_manager_from_callback()
            if not permission_manager:
                await query.edit_message_text("❌ Permission system not available")
                return
            
            # Check if user has payment confirmation permissions
            has_payment_permission = any([
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_WEEKLY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.CONFIRM_MONTHLY_PAYMENTS),
                permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS)
            ])
            
            if not has_payment_permission:
                admin_info = permission_manager.get_admin_info(user_id)
                await query.edit_message_text(
                    f"❌ <b>Payment Confirmation Access Denied</b>\n\n"
                    f"Required: PAYMENT_SPECIALIST+ permissions\n"
                    f"Your level: {admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}",
                    parse_mode='HTML'
                )
                return
            
            # Parse callback: confirm_payment_<type>_<identifier>
            parts = callback_data.split("_", 3)
            if len(parts) < 4:
                await query.edit_message_text("❌ Invalid payment callback format")
                return
            
            giveaway_type = parts[2]  # daily, weekly, monthly
            winner_identifier = parts[3]  # username or telegram_id
            
            # Validate giveaway type
            if giveaway_type not in ['daily', 'weekly', 'monthly']:
                await query.edit_message_text("❌ Invalid giveaway type")
                return
            
            # Get giveaway system
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await query.edit_message_text(f"❌ {giveaway_type.title()} system not available")
                return
            
            # Find winner using helper function from ga_integration
            winner_telegram_id = await integration_instance._find_winner_by_identifier_admin_channel(
                winner_identifier, giveaway_type, giveaway_system
            )
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\n"
                    f"Winner '{winner_identifier}' not found in pending {giveaway_type} winners.\n\n"
                    f"💡 The winner may have been processed already.",
                    parse_mode='HTML'
                )
                return
            
            # Confirm payment using existing system
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                prize = giveaway_system.get_prize_amount(giveaway_type)
                admin_info = permission_manager.get_admin_info(user_id)
                admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
                
                await query.edit_message_text(
                    f"✅ <b>{giveaway_type.title()} Payment Confirmed Successfully</b>\n\n"
                    f"🎉 Winner: {winner_identifier}\n"
                    f"💰 Prize: ${prize} USD\n"
                    f"👤 Confirmed by: {admin_name}\n"
                    f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ <b>Actions completed:</b>\n"
                    f"├─ Winner announced in channel\n"
                    f"├─ Private congratulation sent\n"
                    f"├─ Payment record updated\n"
                    f"└─ System ready for next {giveaway_type} draw",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(
                    f"❌ <b>Error confirming {giveaway_type} payment</b>\n\n"
                    f"<b>Reason:</b> {message}",
                    parse_mode='HTML'
                )
            
        except Exception as e:
            logging.error(f"Error in admin channel payment confirmation: {e}")
            await query.edit_message_text("❌ Error processing payment confirmation")

async def _find_winner_by_identifier_admin_channel( winner_identifier, giveaway_type, giveaway_system):
        """🆕 NEW: Find winner by identifier for admin channel confirmations"""
        try:
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                winner_first_name = winner.get('first_name', '').strip()
                
                # Search by different criteria
                if (
                    winner_identifier == winner_telegram_id or
                    winner_identifier.lower() == f"@{winner_username}".lower() or
                    winner_identifier.lower() == winner_username.lower() or
                    (not winner_username and winner_identifier.lower() == winner_first_name.lower())
                ):
                    return winner_telegram_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
            return None

async def _find_winner_by_identifier(integration_instance, identifier, giveaway_type):
        """🔄 MODIFIED: Find winner by identifier for specific type"""
        try:
            # Get pending winners for specific type
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                winner_first_name = winner.get('first_name', '').strip()
                
                # Search by different criteria
                if (
                    identifier == winner_telegram_id or
                    identifier.lower() == winner_username.lower() or
                    (not winner_username and identifier.lower() == winner_first_name.lower())
                ):
                    return winner_telegram_id
            
            return None
            
        except Exception as e:
            logging.error(f"Error finding {giveaway_type} winner by identifier: {e}")
            return None
