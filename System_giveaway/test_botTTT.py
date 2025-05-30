import logging
import asyncio
import os
import signal
import csv
from typing import Tuple
from datetime import datetime
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ga_integration import MultiGiveawayIntegration, setup_multi_giveaway_files, verify_multi_giveaway_configuration
from config_loader import ConfigLoader
from async_manager import prevent_concurrent_callback, setup_async_safety
from admin_permissions import AdminPermissionManager, SystemAction, PermissionGroup, setup_permission_system, get_permission_manager, require_permission, require_any_permission, require_draw_permission_with_time_check

# 🆕 NUEVOS IMPORTS - SISTEMA DE PERMISOS
from admin_permissions import (
    AdminPermissionManager, 
    SystemAction, 
    PermissionGroup,
    setup_permission_system,
    get_permission_manager,
    require_permission,
    require_any_permission,
    require_draw_permission_with_time_check
)

# ==================== MULTI-TYPE GIVEAWAY BOT ====================

class RealMT5API:
    """
    🔄 MODIFIED: Enhanced MT5 API for multi-type system
    Replace this with your real MT5 implementation
    """
    
    def get_account_info(self, account_number):
        """
        REPLACE WITH YOUR REAL MT5 API
        
        Should return:
        {
            'exists': True,
            'is_live': True,
            'balance': 150.50,
            'currency': 'USD'
        }
        or None if account doesn't exist
        """
        
        try:
            # 🧪 ENHANCED SIMULATION - Remove in production
            test_accounts = {
                # ✅ VALID ACCOUNTS FOR PARTICIPATION (LIVE + Balance >= $100)
                '1234': {'exists': True, 'is_live': True, 'balance': 150.50, 'currency': 'USD'},
                '8765': {'exists': True, 'is_live': True, 'balance': 250.75, 'currency': 'USD'},
                '3333': {'exists': True, 'is_live': True, 'balance': 300.00, 'currency': 'USD'},
                '4444': {'exists': True, 'is_live': True, 'balance': 125.25, 'currency': 'USD'},
                '5555': {'exists': True, 'is_live': True, 'balance': 500.00, 'currency': 'USD'},
                '6666': {'exists': True, 'is_live': True, 'balance': 199.99, 'currency': 'USD'},
                '7777': {'exists': True, 'is_live': True, 'balance': 1000.00, 'currency': 'USD'},
                '8888': {'exists': True, 'is_live': True, 'balance': 750.50, 'currency': 'USD'},
                '1010': {'exists': True, 'is_live': True, 'balance': 100.00, 'currency': 'USD'},
                '2020': {'exists': True, 'is_live': True, 'balance': 100.01, 'currency': 'USD'},
                
                # ❌ INSUFFICIENT BALANCE (< $100)
                '2222': {'exists': True, 'is_live': True, 'balance': 50.00, 'currency': 'USD'},
                '3030': {'exists': True, 'is_live': True, 'balance': 99.99, 'currency': 'USD'},
                '4040': {'exists': True, 'is_live': True, 'balance': 25.50, 'currency': 'USD'},
                '5050': {'exists': True, 'is_live': True, 'balance': 0.00, 'currency': 'USD'},
                
                # ❌ DEMO ACCOUNTS (Not valid for giveaway)
                '1111': {'exists': True, 'is_live': False, 'balance': 200.00, 'currency': 'USD'},
                '6060': {'exists': True, 'is_live': False, 'balance': 500.00, 'currency': 'USD'},
                '7070': {'exists': True, 'is_live': False, 'balance': 1000.00, 'currency': 'USD'},
                
                # ❌ NON-EXISTENT ACCOUNTS
                '9999': None,
                '0000': None,
                '9876': None,
                '1357': None,
                
                # 🧪 SPECIAL TESTING ACCOUNTS
                '8080': {'exists': True, 'is_live': True, 'balance': 100.50, 'currency': 'USD'},
                '9090': {'exists': True, 'is_live': True, 'balance': 200.25, 'currency': 'USD'},
            }
            
            result = test_accounts.get(account_number)
            if result is None:
                return None
                
            return {
                'exists': result['exists'],
                'is_live': result['is_live'], 
                'balance': result['balance'],
                'currency': result['currency']
            }
            
        except Exception as e:
            logging.error(f"Error querying MT5 API: {e}")
            return None

# =================== BOT COMMANDS CON PERMISOS ====================

# 🆕 RATE LIMITING SIMPLE
user_last_action = {}
RATE_LIMIT_SECONDS = 3

# # ================== COMANDOS BASICOS   ==========================
def is_user_rate_limited(user_id):
    """Simple rate limiting"""
    import time
    current_time = time.time()
    last_action = user_last_action.get(user_id, 0)
    
    if current_time - last_action < RATE_LIMIT_SECONDS:
        return True
    
    user_last_action[user_id] = current_time
    return False

async def start_command(update, context):
    """🔄 MANTENER IGUAL - Esta función no necesita permisos"""
    # Tu código existente sin cambios
    global multi_giveaway_integration
        # multi_giveaway_integration
    
    user = update.effective_user

    if is_user_rate_limited(user.id):
        await update.message.reply_text("⏳ Please wait a moment before trying again.")
        return

    chat_type = update.effective_chat.type
    args = context.args
    message_text = update.message.text if update.message else ""
    
    if chat_type == 'private':
        # 🆕 NEW: Detect giveaway type from participation URL
        participation_type = None
        is_participation = False
        
        if args and len(args) > 0:
            arg = args[0]
            if arg == 'participate':
                # Legacy format - default to daily
                participation_type = 'daily'
                is_participation = True
            elif arg.startswith('participate_'):
                # New format: participate_daily, participate_weekly, participate_monthly
                giveaway_type = arg.replace('participate_', '')
                if giveaway_type in ['daily', 'weekly', 'monthly']:
                    participation_type = giveaway_type
                    is_participation = True
        elif 'participate' in message_text:
            # Fallback detection
            participation_type = 'daily'
            is_participation = True
        
        if is_participation and participation_type:
            # ✅ DIRECT PARTICIPATION FOR SPECIFIC TYPE
            # ✅ DIRECT PARTICIPATION FOR SPECIFIC TYPE
            print(f"🎯 User {user.first_name} wants to participate in {participation_type} giveaway")
            
            # Get the specific giveaway system
            giveaway_system = multi_giveaway_integration.get_giveaway_system(participation_type)
            
            if not giveaway_system:
                await update.message.reply_text(
                    f"❌ <b>{participation_type.title()} giveaway not available</b>\n\nPlease try again later.",
                    parse_mode='HTML'
                )
                return
            
            # 🔍 DEBUG: Verificar directorio de datos
            file_paths = giveaway_system.get_file_paths(participation_type)
            print(f"🔍 DEBUG: Expected participants file: {file_paths['participants']}")
            
            # 🆕 VERIFICACIÓN 1: Check if already registered TODAY
            print(f"🔍 DEBUG: Checking existing registration for user {user.id}")
            if giveaway_system._is_already_registered(user.id, participation_type):
                prize = giveaway_system.get_prize_amount(participation_type)
                await update.message.reply_text(
                    f"ℹ️ <b>Already registered for {participation_type}</b>\n\nYou are already participating in today's {participation_type} giveaway (${prize}).\n\n🍀 Good luck in the draw!\n\n⏰ Draw: Check schedule",
                    parse_mode='HTML'
                )
                print(f"✅ DEBUG: User {user.id} already registered for {participation_type}")
                return
            
            # 🆕 VERIFICACIÓN 2: Check if participation window is open
            if not giveaway_system.is_participation_window_open(participation_type):
                window_status = giveaway_system.get_participation_window_status(participation_type)
                next_window = window_status.get('next_open', 'Soon')
                
                await update.message.reply_text(
                    f"⏰ <b>{participation_type.title()} participation closed</b>\n\nParticipation window is currently closed.\n\n🔄 <b>Next window opens:</b>\n{next_window}\n\n💡 Stay tuned for the next opportunity!",
                    parse_mode='HTML'
                )
                return
            
            # 🆕 VERIFICACIÓN 3: Check if has pending registration for this type
            if context.user_data.get(f'awaiting_mt5_{participation_type}'):
                await update.message.reply_text(
                    f"⏳ <b>{participation_type.title()} registration in progress</b>\n\nYou already have a {participation_type} registration pending.\n\nPlease send your MT5 account number to complete your participation.",
                    parse_mode='HTML'
                )
                return
            
            # 🆕 VERIFICACIÓN 4: Check channel membership
            try:
                config_loader = ConfigLoader()
                bot_config = config_loader.get_bot_config()
                channel_id = bot_config['channel_id']
                
                member = await context.bot.get_chat_member(channel_id, user.id)
                is_member = member.status in ['member', 'administrator', 'creator']
            except Exception as e:
                print(f"❌ DEBUG: Error checking membership: {e}")
                is_member = False
            
            if not is_member:
                await update.message.reply_text(
                    "❌ <b>Not a channel member</b>\n\nYou must be a member of the main channel to participate.\n\n💡 Join the channel and try again.",
                    parse_mode='HTML'
                )
                return
            
            # ✅ ALL CHECKS PASSED - REQUEST MT5 ACCOUNT
            prize = giveaway_system.get_prize_amount(participation_type)
            
            await update.message.reply_text(
                f"🎁 <b>Perfect {user.first_name}!</b>\n\n✅ You are a channel member\n✅ Ready to participate in {participation_type.upper()} giveaway\n\n💰 <b>Prize:</b> ${prize} USD\n\n🔢 <b>Send your MT5 account number:</b>\n\n💡 <b>Valid examples:</b>\n• 1234, 4444, 5555, 7777\n• 8765, 3333, 6666, 8888\n\n⚠️ <b>Only numbers, no spaces</b>",
                parse_mode='HTML'
            )
            
            # Activate waiting state for this specific type
            context.user_data[f'awaiting_mt5_{participation_type}'] = True
            context.user_data[f'mt5_attempts_{participation_type}'] = 0 
            context.user_data[f'user_info_{participation_type}'] = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'giveaway_type': participation_type
            }
            print(f"✅ DEBUG: User {user.id} activated for {participation_type} registration")
            print(f"✅ DEBUG: awaiting_mt5_{participation_type} = {context.user_data.get(f'awaiting_mt5_{participation_type}')}")
            
        else:
            # ✅ NORMAL /start - WELCOME MESSAGE WITH TYPE SELECTION
            bot_info = await context.bot.get_me()
            bot_username = bot_info.username
            
            message = f"""🎁 <b>Hello {user.first_name}!</b>

Welcome to the VFX Trading Multi-Giveaway Bot.

🌟 <b>AVAILABLE GIVEAWAYS:</b>

💰 <b>DAILY:</b> $250 USD
⏰ Monday to Friday at 5:00 PM London Time

💰 <b>WEEKLY:</b> $500 USD  
⏰ Every Friday at 5:15 PM London Time

💰 <b>MONTHLY:</b> $1000 USD
⏰ Last Friday of each month at 5:30 PM London Time

📋 <b>Requirements for all:</b>
✅ Active MT5 LIVE account
✅ Minimum balance $100 USD  
✅ Be a channel member

🎯 <b>Choose which giveaway to participate in:</b>"""
            
            # Create participation buttons for each type
            buttons = []
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                # Check if window is open
                is_open = giveaway_system.is_participation_window_open(giveaway_type)
                status_emoji = "🟢" if is_open else "🔴"
                
                button_text = f"{status_emoji} {giveaway_type.title()} (${prize})"
                participate_link = f"https://t.me/{bot_username}?start=participate_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, url=participate_link)])
            
            # Add info button
            buttons.append([InlineKeyboardButton("📋 View Rules & Schedule", callback_data="show_rules")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(
                message, 
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            print(f"✅ Multi-type welcome message sent to {user.first_name}")
            
    else:
        # Message for group/channel
        await update.message.reply_text(
            "🎁 <b>VFX Trading Multi-Giveaway Bot</b>\n\nTo participate in any giveaway, send me a private message with /start",
            parse_mode='HTML'
        )

async def help_command(update, context):
    """🔄 MANTENER IGUAL - No necesita permisos específicos"""
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        admin_username = bot_config.get('admin_username', 'admin')
    except:
        admin_username = 'admin'
    
    help_text = f"""🆘 <b>MULTI-GIVEAWAY RULES</b>

🌟 <b>AVAILABLE GIVEAWAYS:</b>

💰 <b>DAILY GIVEAWAY - $250 USD</b>
⏰ <b>Participation:</b> Monday-Friday, 1:00 AM - 4:50 PM London Time
🎯 <b>Draw:</b> Monday-Friday at 5:00 PM London Time
🔄 <b>Cooldown:</b> 30 days after winning

💰 <b>WEEKLY GIVEAWAY - $500 USD</b>
⏰ <b>Participation:</b> Monday 9:00 AM - Friday 5:00 PM London Time
🎯 <b>Draw:</b> Friday at 5:15 PM London Time
🔄 <b>Cooldown:</b> 60 days after winning

💰 <b>MONTHLY GIVEAWAY - $1000 USD</b>
⏰ <b>Participation:</b> Day 1 - Last Friday of month, London Time
🎯 <b>Draw:</b> Last Friday at 5:30 PM London Time
🔄 <b>Cooldown:</b> 90 days after winning

📋 <b>REQUIREMENTS FOR ALL GIVEAWAYS:</b>
✅ Be a member of this channel
✅ Active MT5 LIVE account (not demo)
✅ Minimum balance of $100 USD
✅ One participation per giveaway type per period

🔒 <b>IMPORTANT RULES:</b>
• Each MT5 account belongs to the first user who registers it
• You can participate in ALL giveaway types simultaneously
• Independent cooldowns for each giveaway type
• Must confirm receipt of prize if you win

❌ <b>COMMON ERRORS:</b>
• "Account not found" → Verify the number
• "Insufficient balance" → Deposit more than $100 USD
• "Account is not LIVE" → Use real account, not demo
• "Already registered" → Only one participation per type per period
• "Account belongs to another" → Use your own MT5 account

📞 <b>NEED HELP?</b>
Contact administrator: @{admin_username}

⏰ <b>CURRENT LONDON TIME:</b>
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

🎯 <b>Use /start to participate in any giveaway!</b>"""
    
    await update.message.reply_text(help_text, parse_mode='HTML')

# ==================== COMANDOS ADMIN BASICOS POR TIPO Y CON PERMISOS ====================

# 🎯 COMANDOS DE INVITACIONES POR TIPO

@require_permission(SystemAction.SEND_DAILY_INVITATION)
async def admin_send_daily_invitation(update, context):
    """🆕 NUEVO: Enviar invitación diaria (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Daily invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('daily')
        success = await giveaway_system.send_invitation('daily')
        
        if success:
            await update.message.reply_text("✅ Daily giveaway invitation sent to channel")
            permission_manager.log_action(user_id, SystemAction.SEND_DAILY_INVITATION, "Daily invitation sent successfully")
        else:
            await update.message.reply_text("❌ Error sending daily invitation")
            permission_manager.log_action(user_id, SystemAction.SEND_DAILY_INVITATION, "Failed to send daily invitation")
        
    except Exception as e:
        logging.error(f"Error in daily invitation: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_permission(SystemAction.SEND_WEEKLY_INVITATION)
async def admin_send_weekly_invitation(update, context):
    """🆕 NUEVO: Enviar invitación semanal (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Weekly invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('weekly')
        success = await giveaway_system.send_invitation('weekly')
        
        if success:
            await update.message.reply_text("✅ Weekly giveaway invitation sent to channel")
            permission_manager.log_action(user_id, SystemAction.SEND_WEEKLY_INVITATION, "Weekly invitation sent successfully")
        else:
            await update.message.reply_text("❌ Error sending weekly invitation")
            permission_manager.log_action(user_id, SystemAction.SEND_WEEKLY_INVITATION, "Failed to send weekly invitation")
        
    except Exception as e:
        logging.error(f"Error in weekly invitation: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_permission(SystemAction.SEND_MONTHLY_INVITATION)
async def admin_send_monthly_invitation(update, context):
    """🆕 NUEVO: Enviar invitación mensual (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Monthly invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('monthly')
        success = await giveaway_system.send_invitation('monthly')
        
        if success:
            await update.message.reply_text("✅ Monthly giveaway invitation sent to channel")
            permission_manager.log_action(user_id, SystemAction.SEND_MONTHLY_INVITATION, "Monthly invitation sent successfully")
        else:
            await update.message.reply_text("❌ Error sending monthly invitation")
            permission_manager.log_action(user_id, SystemAction.SEND_MONTHLY_INVITATION, "Failed to send monthly invitation")
        
    except Exception as e:
        logging.error(f"Error in monthly invitation: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

# 🎲 COMANDOS DE SORTEOS POR TIPO CON VERIFICACIÓN HORARIA

@require_draw_permission_with_time_check('daily')
async def admin_run_daily_draw(update, context):
    """🆕 NUEVO: Ejecutar sorteo diario (CON PERMISOS Y VERIFICACIÓN HORARIA)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)

    # 🆕 USAR la nueva función de verificación
    authorized, message = permission_manager.verify_time_restricted_action(
        user_id, SystemAction.EXECUTE_DAILY_DRAW, 'daily'
    )

    if not authorized:
        await update.message.reply_text(f"❌ {message}")
        return
    
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Daily draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('daily')
        await giveaway_system.run_giveaway('daily')
        
        # Check results
        pending_winners = giveaway_system.get_pending_winners('daily')
        pending_count = len(pending_winners)
        
        if pending_count > 0:
            winner = pending_winners[0]
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            prize = giveaway_system.get_prize_amount('daily')
            
            response_message = f"""✅ <b>Daily draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
👤 <b>Executed by:</b> {admin_name}

💡 Winner is pending payment confirmation
💡 Use `/admin_confirm_daily` for payment confirmation"""
            
            await update.message.reply_text(response_message, parse_mode='HTML')
            
            # 🆕 NUEVA: Notificar a otros admins con permisos de confirmación
            await multi_giveaway_integration.notify_payment_admins_new_winner(context, winner, 'daily', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_DAILY_DRAW, f"Daily draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Daily draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_DAILY_DRAW, "Daily draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in daily draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_draw_permission_with_time_check('weekly')
async def admin_run_weekly_draw(update, context):
    """🆕 NUEVO: Ejecutar sorteo semanal (CON PERMISOS Y VERIFICACIÓN HORARIA)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Weekly draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('weekly')
        await giveaway_system.run_giveaway('weekly')
        
        # Check results
        pending_winners = giveaway_system.get_pending_winners('weekly')
        pending_count = len(pending_winners)
        
        if pending_count > 0:
            winner = pending_winners[0]
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            prize = giveaway_system.get_prize_amount('weekly')
            
            response_message = f"""✅ <b>Weekly draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
👤 <b>Executed by:</b> {admin_name}

💡 Winner is pending payment confirmation
💡 Use `/admin_confirm_weekly` for payment confirmation"""
            
            await update.message.reply_text(response_message, parse_mode='HTML')
            
            # 🆕 NUEVA: Notificar a otros admins con permisos de confirmación
            await multi_giveaway_integration.notify_payment_admins_new_winner(context, winner, 'weekly', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_WEEKLY_DRAW, f"Weekly draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Weekly draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_WEEKLY_DRAW, "Weekly draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in weekly draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_draw_permission_with_time_check('monthly')
async def admin_run_monthly_draw(update, context):
    """🆕 NUEVO: Ejecutar sorteo mensual (CON PERMISOS Y VERIFICACIÓN HORARIA)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Monthly draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('monthly')
        await giveaway_system.run_giveaway('monthly')
        
        # Check results
        pending_winners = giveaway_system.get_pending_winners('monthly')
        pending_count = len(pending_winners)
        
        if pending_count > 0:
            winner = pending_winners[0]
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            winner_display = f"@{username}" if username else first_name
            prize = giveaway_system.get_prize_amount('monthly')
            
            response_message = f"""✅ <b>Monthly draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
👤 <b>Executed by:</b> {admin_name}

💡 Winner is pending payment confirmation
💡 Use `/admin_confirm_monthly` for payment confirmation"""
            
            await update.message.reply_text(response_message, parse_mode='HTML')
            
            # 🆕 NUEVA: Notificar a otros admins con permisos de confirmación
            await multi_giveaway_integration.notify_payment_admins_new_winner(context, winner, 'monthly', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, f"Monthly draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Monthly draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, "Monthly draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in monthly draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")



# ====================  COMANDOS UTILIDAD y DEBUG  CON PERMISOS ====================

# @require_permission(SystemAction.VIEW_ADVANCED_STATS)
@require_any_permission(
    SystemAction.VIEW_BASIC_STATS,
    SystemAction.VIEW_ADVANCED_STATS
)
async def stats_command(update, context):
    """🔄 MODIFICADA: Stats con niveles de permisos"""
    try:
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)

        admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'

        # 🆕 DETERMINAR nivel de acceso
        has_advanced = permission_manager and permission_manager.has_permission(user_id, SystemAction.VIEW_ADVANCED_STATS)
        permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'

        if has_advanced:
            # Mostrar estadísticas completas (código existente)
            combined_stats = multi_giveaway_integration.get_giveaway_stats()
            # ... código completo existente ...
        else:
            # 🆕 Mostrar solo estadísticas básicas para VIEW_ONLY
            basic_message = f"📊 <b>BASIC STATISTICS</b>\n"
            basic_message += f"🔒 <b>Access Level:</b> {permission_level}\n\n"
            
            total_today = 0
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                total_today += today_count
                
                basic_message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b> {today_count} today\n"
            
            basic_message += f"\n📊 <b>Total Today:</b> {total_today} participants"
            basic_message += f"\n\n💡 Advanced statistics require PAYMENT_SPECIALIST+ permissions"
            
            await update.message.reply_text(basic_message, parse_mode='HTML')
            return
        
        
        print(f"✅ Stats access authorized for: {admin_name} ({user_id})")
        
        # Get combined stats
        combined_stats = multi_giveaway_integration.get_giveaway_stats()
        
        # Build stats message
        stats_text = f"""📊 <b>MULTI-GIVEAWAY STATISTICS</b>
<i>Accessed by: {admin_name}</i>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participants: <b>{combined_stats['total_participants_all']}</b>
├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
├─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

📊 <b>BY GIVEAWAY TYPE:</b>"""

        for giveaway_type, stats in combined_stats['by_type'].items():
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            
            stats_text += f"""

🎯 <b>{giveaway_type.upper()} (${prize}):</b>
├─ Today: {stats.get('today_participants', 0)} participants
├─ Total: {stats.get('total_participants', 0)} participants  
├─ Winners: {stats.get('total_winners', 0)}
├─ Distributed: ${stats.get('total_prize_distributed', 0)}
└─ Pending: {pending_count}"""

        stats_text += f"\n\n💡 Use specific commands for detailed management"
        
        await update.message.reply_text(stats_text, parse_mode='HTML')
        
        permission_manager.log_action(user_id, SystemAction.VIEW_ADVANCED_STATS, "Advanced stats accessed")
        
    except Exception as e:
        logging.error(f"Error showing stats: {e}")
        await update.message.reply_text("❌ Error getting statistics")

@require_permission(SystemAction.HEALTH_CHECK)
async def health_check_command(update, context):
    """🔄 MODIFICADA: Health check con permisos"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Health check authorized for: {admin_name} ({user_id})")
    
    try:
        # Run comprehensive health check
        health_report = multi_giveaway_integration.verify_all_systems_health()
        
        message = f"""🏥 <b>SYSTEM HEALTH CHECK</b>
<i>Requested by: {admin_name}</i>

🌡️ <b>Overall Status:</b> {health_report['overall_status'].upper()}

💡 <b>System Status:</b>"""

        for giveaway_type, system_status in health_report['systems'].items():
            if system_status['status'] == 'healthy':
                message += f"""
✅ <b>{giveaway_type.upper()}:</b> Operational
├─ Prize: ${system_status['prize_amount']}
├─ Pending: {system_status['pending_count']}
└─ Files: {'✅' if system_status['files_accessible'] else '❌'}"""
            else:
                message += f"""
❌ <b>{giveaway_type.upper()}:</b> Error
└─ Issue: {system_status.get('error', 'Unknown')}"""

        if health_report.get('issues'):
            message += f"\n\n⚠️ <b>Issues detected:</b>\n"
            for issue in health_report['issues'][:3]:
                message += f"• {issue}\n"

        message += f"\n📅 <b>Checked:</b> {health_report['timestamp']}"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        permission_manager.log_action(user_id, SystemAction.HEALTH_CHECK, f"Health check completed - Status: {health_report['overall_status']}")
        
    except Exception as e:
        logging.error(f"Error in health check: {e}")
        await update.message.reply_text("❌ Error running health check")

@require_permission(SystemAction.MANAGE_ADMINS)
async def admin_security_audit(update, context):
    """🆕 NEW: Auditoría completa de seguridad del sistema"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    
    if not permission_manager:
        await update.message.reply_text("❌ Permission system not available")
        return
    
    # Ejecutar auditoría
    violations = permission_manager.audit_permission_violations()
    
    message = f"🔒 <b>SECURITY AUDIT REPORT</b>\n\n"
    
    if not violations:
        message += "✅ <b>No security violations detected</b>\n\n"
        message += "All admin permissions are properly configured."
    else:
        message += f"⚠️ <b>{len(violations)} violations detected:</b>\n\n"
        
        for violation in violations[:5]:  # Mostrar solo las primeras 5
            severity_emoji = "🚨" if violation['severity'] == 'CRITICAL' else "⚠️"
            message += f"{severity_emoji} {violation['violation']}\n"
        
        if len(violations) > 5:
            message += f"\n... and {len(violations) - 5} more violations"
    
    message += f"\n\n📅 Audit completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    await update.message.reply_text(message, parse_mode='HTML')

@require_permission(SystemAction.TEST_CONNECTIONS)
async def test_channel_command(update, context):
    """🔄 MODIFICADA: Test channel con permisos"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Test channel authorized for: {admin_name} ({user_id})")
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        print(f"🧪 Testing direct send to channel: {channel_id}")
        
        # Test message
        test_message = f"""✅ <b>MULTI-GIVEAWAY SYSTEM TEST</b>

🎯 If you see this message, the bot can send to the channel correctly.

🧪 System status: Operational
📡 Connection: Verified
👤 Tested by: {admin_name}

🌟 Available giveaways: Daily, Weekly, Monthly"""
        
        # Direct send test
        sent_message = await context.bot.send_message(
            chat_id=channel_id,
            text=test_message,
            parse_mode='HTML'
        )
        
        await update.message.reply_text(f"✅ Test message sent to channel\nMessage ID: {sent_message.message_id}")
        print("✅ Test message sent successfully")
        
        permission_manager.log_action(user_id, SystemAction.TEST_CONNECTIONS, f"Test channel successful - Message ID: {sent_message.message_id}")
        
    except Exception as e:
        error_msg = f"Error testing channel: {e}"
        logging.error(error_msg)
        print(f"❌ {error_msg}")
        await update.message.reply_text(f"❌ Error: {e}")
        permission_manager.log_action(user_id, SystemAction.TEST_CONNECTIONS, f"Test channel failed: {e}")

async def debug_directories():
    """🔍 Verificar directorios del sistema"""
    try:
        config_loader = ConfigLoader()
        db_config = config_loader.get_database_config()
        base_path = db_config.get('base_path', './System_giveaway/data')
        
        print(f"🔍 DEBUG: Configured base_path: {base_path}")
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            data_dir = f"{base_path}/{giveaway_type}"
            participants_file = f"{data_dir}/participants.csv"
            
            print(f"🔍 DEBUG: {giveaway_type} directory: {data_dir}")
            print(f"🔍 DEBUG: {giveaway_type} participants file: {participants_file}")
            print(f"🔍 DEBUG: Directory exists: {os.path.exists(data_dir)}")
            print(f"🔍 DEBUG: File exists: {os.path.exists(participants_file)}")
            
            if os.path.exists(participants_file):
                with open(participants_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"🔍 DEBUG: File size: {len(content)} characters")
                    print(f"🔍 DEBUG: File content preview: {content[:200]}...")
    
    except Exception as e:
        print(f"❌ DEBUG: Error checking directories: {e}")


# ====================  CALLBACKS ESPECIFICOS ==============================

async def handle_user_interface_callbacks(update, context):
    """
    🎯 SPECIFIC HANDLER: Solo callbacks de interfaz de usuario
    Maneja show_rules, user interface elements, etc.
    """
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        print(f"👤 DEBUG: User interface callback: {callback_data}")
        
        # Handle different user interface callbacks
        if callback_data == "show_rules":
            # Show complete rules using existing help function
            await show_rules_inline(query)
            
        elif callback_data.startswith("user_"):
            # Handle user-specific actions (future expansion)
            await query.edit_message_text(
                "ℹ️ <b>User function</b>\n\nThis user interface feature is being developed.\n\n💡 Use /help for complete information.",
                parse_mode='HTML'
            )
            
        elif callback_data.startswith("start_"):
            # Handle start menu actions (future expansion)
            await query.edit_message_text(
                "🎁 <b>Welcome!</b>\n\nUse /start to access the main participation menu.",
                parse_mode='HTML'
            )
            
        else:
            # Fallback for unknown user interface callbacks
            await query.edit_message_text(
                "ℹ️ <b>Interface element</b>\n\nThis interface element is not yet implemented.\n\n💡 Use /start for main menu.",
                parse_mode='HTML'
            )
            
    except Exception as e:
        logging.error(f"Error in user interface callback: {e}")
        print(f"❌ DEBUG: Error in user interface callback: {e}")
        await query.edit_message_text(
            "❌ Error processing interface element. Please try again.",
            parse_mode='HTML'
        )

# @prevent_concurrent_callback("payment_confirmation")
async def handle_payment_confirmations_only(update, context):
    """
    🎯 SPECIFIC HANDLER: Solo confirmaciones de pago
    Evita conflicto con ga_integration.py handlers
    """
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        callback_data = query.data
        
        print(f"💰 DEBUG: Payment confirmation callback: {callback_data} from user {user_id}")
        
        # Verify admin permissions
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator', 'Admin 1' ]:
            await query.edit_message_text("❌ Only administrators can confirm payments")
            return
        
        # Process ONLY payment confirmations
        if callback_data.startswith("confirm_payment_"):
            # Parse callback: confirm_payment_<type>_<identifier>
            parts = callback_data.split("_", 3)
            if len(parts) < 4:
                await query.edit_message_text("❌ Invalid payment callback format")
                return
            
            giveaway_type = parts[2]  # daily, weekly, monthly
            winner_identifier = parts[3]  # username or telegram_id
            
            print(f"💰 DEBUG: Parsed payment - Type: {giveaway_type}, Winner: {winner_identifier}")
            
            # Validate giveaway type
            if giveaway_type not in ['daily', 'weekly', 'monthly']:
                await query.edit_message_text("❌ Invalid giveaway type")
                return
            
            # Get giveaway system
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                await query.edit_message_text(f"❌ {giveaway_type.title()} system not available")
                return
            
            # Find winner using helper function
            winner_telegram_id = await multi_giveaway_integration.find_winner_by_identifier(winner_identifier, giveaway_type, giveaway_system)
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\n"
                    f"Winner '{winner_identifier}' not found in pending {giveaway_type} winners or already processed.\n\n"
                    f"💡 The winner may have been processed already.",
                    parse_mode='HTML'
                )
                return
            
            print(f"💰 DEBUG: Found winner {winner_telegram_id}, confirming payment...")
            
            # 💰 CONFIRM PAYMENT AND ANNOUNCE
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                # Get additional details for response
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                await query.edit_message_text(
                    f"✅ <b>{giveaway_type.title()} Payment Confirmed Successfully</b>\n\n"
                    f"🎉 Winner: {winner_identifier}\n"
                    f"💰 Prize: ${prize} USD\n"
                    f"👤 Confirmed by: {query.from_user.first_name}\n"
                    f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"✅ <b>Actions completed:</b>\n"
                    f"├─ Winner announced in channel\n"
                    f"├─ Private congratulation sent\n"
                    f"├─ Payment record updated\n"
                    f"└─ System ready for next {giveaway_type} draw\n\n"
                    f"🎯 <b>Status:</b> Payment process complete ✓",
                    parse_mode='HTML'
                )
                
                print(f"✅ DEBUG: {giveaway_type.title()} payment confirmed successfully")
                
            else:
                await query.edit_message_text(
                    f"❌ <b>Error confirming {giveaway_type} payment</b>\n\n"
                    f"<b>Reason:</b> {message}\n\n"
                    f"💡 <b>This usually means:</b>\n"
                    f"• Winner was already processed\n"
                    f"• System error occurred\n"
                    f"• Invalid winner state\n\n"
                    f"🔄 Please check pending winners list or contact FULL_ADMIN if issue persists.",
                    parse_mode='HTML'
                )
                print(f"❌ DEBUG: Payment confirmation failed: {message}")
        
        else:
            # This shouldn't happen due to pattern filter, but safety check
            await query.edit_message_text("❌ Invalid payment callback")
            
    except Exception as e:
        logging.error(f"Error in payment confirmation handler: {e}")
        print(f"❌ DEBUG: Exception in payment confirmation: {e}")
        await query.edit_message_text(
            f"❌ <b>Payment confirmation system error</b>\n\n"
            f"An unexpected error occurred while processing the payment confirmation.\n\n"
            f"💡 <b>Please try:</b>\n"
            f"• Use manual command: <code>/admin_confirm_payment &lt;winner&gt;</code>\n"
            f"• Contact FULL_ADMIN if problem persists\n\n"
            f"<i>Error reference: {str(e)[:50]}...</i>",
            parse_mode='HTML'
        )

async def show_rules_inline(query):
    """Show complete rules inline when requested from button"""
    try:
        # Use existing help content but format for inline display
        try:
            config_loader = ConfigLoader()
            bot_config = config_loader.get_bot_config()
            admin_username = bot_config.get('admin_username', 'admin')
        except:
            admin_username = 'admin'
        
        rules_text = f"""🆘 <b>MULTI-GIVEAWAY RULES</b>

🌟 <b>AVAILABLE GIVEAWAYS:</b>

💰 <b>DAILY GIVEAWAY - $250 USD</b>
⏰ <b>Participation:</b> Monday-Friday, 1:00 AM - 4:50 PM London Time
🎯 <b>Draw:</b> Monday-Friday at 5:00 PM London Time
🔄 <b>Cooldown:</b> 30 days after winning

💰 <b>WEEKLY GIVEAWAY - $500 USD</b>
⏰ <b>Participation:</b> Monday 9:00 AM - Friday 5:00 PM London Time
🎯 <b>Draw:</b> Friday at 5:15 PM London Time
🔄 <b>Cooldown:</b> 60 days after winning

💰 <b>MONTHLY GIVEAWAY - $1000 USD</b>
⏰ <b>Participation:</b> Day 1 - Last Friday of month, London Time
🎯 <b>Draw:</b> Last Friday at 5:30 PM London Time
🔄 <b>Cooldown:</b> 90 days after winning

📋 <b>REQUIREMENTS FOR ALL GIVEAWAYS:</b>
✅ Be a member of this channel
✅ Active MT5 LIVE account (not demo)
✅ Minimum balance of $100 USD
✅ One participation per giveaway type per period

🔒 <b>IMPORTANT RULES:</b>
• Each MT5 account belongs to the first user who registers it
• You can participate in ALL giveaway types simultaneously
• Independent cooldowns for each giveaway type
• Must confirm receipt of prize if you win

📞 <b>NEED HELP?</b>
Contact administrator: @{admin_username}

⏰ <b>CURRENT LONDON TIME:</b>
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC"""

        # Add back button
        keyboard = [[InlineKeyboardButton("🔙 Back to Start", callback_data="start_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            rules_text, 
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logging.error(f"Error showing rules inline: {e}")
        await query.edit_message_text(
            "❌ Error loading rules. Use /help for complete information.",
            parse_mode='HTML'
        )

# =================== HELPER FUNCTIONS BÁSICAS ==============================

@require_permission(SystemAction.VIEW_ADVANCED_STATS)
async def debug_my_permissions(update, context):
    """🔍 COMANDO TEMPORAL: Ver mis permisos actuales"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    
    if not permission_manager:
        await update.message.reply_text("❌ Permission system not loaded")
        return
    
    admin_info = permission_manager.get_admin_info(user_id)
    
    if not admin_info:
        await update.message.reply_text(f"❌ Tu ID {user_id} no está en la configuración de admins")
        return
    
    # Obtener permisos del grupo
    permission_group = admin_info.get('permission_group', 'None')
    group_permissions = permission_manager.permission_groups.get(permission_group, [])
    
    # Verificar permisos específicos
    test_permissions = [
        SystemAction.SEND_DAILY_INVITATION,
        SystemAction.EXECUTE_DAILY_DRAW,
        SystemAction.TEST_CONNECTIONS,
        SystemAction.HEALTH_CHECK,
        SystemAction.VIEW_ADVANCED_STATS
    ]
    
    message = f"""🔍 <b>DEBUG - TUS PERMISOS</b>

👤 <b>Tu Info:</b>
├─ ID: <code>{user_id}</code>
├─ Nombre: {admin_info.get('name', 'N/A')}
├─ Grupo: <code>{permission_group}</code>
├─ Activo: {admin_info.get('active', 'N/A')}
└─ Permisos en grupo: {len(group_permissions)}

🔍 <b>Permisos específicos:</b>"""

    for action in test_permissions:
        has_permission = permission_manager.has_permission(user_id, action)
        status = "✅" if has_permission else "❌"
        message += f"\n{status} {action.value}"

    message += f"""

📋 <b>Todos los permisos del grupo {permission_group}:</b>
{', '.join([p.value for p in group_permissions[:10]])}{'...' if len(group_permissions) > 10 else ''}

🔧 <b>Total permisos en tu grupo:</b> {len(group_permissions)}
🔧 <b>Total acciones disponibles:</b> {len(SystemAction)}"""

    await update.message.reply_text(message, parse_mode='HTML')

# 🆕 ADD: Installation check function
def check_automation_dependencies():
    """Check if required dependencies for automation are installed"""
    try:
        import apscheduler
        print("✅ APScheduler available")
        return True
    except ImportError:
        print("❌ APScheduler not found")
        print("💡 Install with: pip install apscheduler")
        return False

# ==================== NOTIFICACIÓN A ADMINS AUTORIZADOS ====================

async def notify_payment_confirmed_to_authorized_admins(context, winner_identifier, giveaway_type, confirmed_by, prize):
    """
    🔔 NOTIFICAR confirmación de pago solo a admins con permisos relevantes
    """
    permission_manager = get_permission_manager(context)
    
    # Determinar quién debe recibir la notificación
    relevant_permissions = [
        SystemAction.VIEW_PAYMENT_HISTORY,
        SystemAction.VIEW_ALL_PENDING_WINNERS,
        SystemAction.MANAGE_ADMINS  # FULL_ADMIN siempre debe saber
    ]
    
    # También incluir admins que pueden confirmar este tipo específico
    type_permission_map = {
        'daily': SystemAction.CONFIRM_DAILY_PAYMENTS,
        'weekly': SystemAction.CONFIRM_WEEKLY_PAYMENTS,
        'monthly': SystemAction.CONFIRM_MONTHLY_PAYMENTS
    }
    
    if giveaway_type in type_permission_map:
        relevant_permissions.append(type_permission_map[giveaway_type])
    
    # Obtener todos los admins autorizados (sin duplicados)
    authorized_admins = set()
    for permission in relevant_permissions:
        admins_with_permission = permission_manager.get_admins_with_permission(permission)
        authorized_admins.update(admins_with_permission)
    
    if not authorized_admins:
        logging.warning(f"No authorized admins found for {giveaway_type} payment confirmation notification")
        return
    
    # Mensaje de notificación
    notification_message = f"""✅ <b>{giveaway_type.upper()} PAYMENT CONFIRMED</b>

🏆 <b>Winner:</b> {winner_identifier}
💰 <b>Prize:</b> ${prize} USD
👤 <b>Confirmed by:</b> {confirmed_by}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ <b>Actions completed:</b>
├─ Winner announced in channel
├─ Private congratulation sent
└─ System updated for next {giveaway_type} draw

💡 <b>Status:</b> Payment process complete ✓"""
    
    # Enviar a cada admin autorizado
    success_count = 0
    for admin_id in authorized_admins:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification_message,
                parse_mode='HTML'
            )
            success_count += 1
        except Exception as e:
            logging.error(f"Error notifying admin {admin_id} about {giveaway_type} payment confirmation: {e}")
    
    logging.info(f"{giveaway_type.title()} payment confirmation sent to {success_count}/{len(authorized_admins)} authorized admins")

async def show_view_only_dashboard_simple(update, context, admin_info):
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
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
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


# ==================== 🔄 MAIN FUNCTION MODIFICADA ====================

# Global variable for multi-giveaway integration
multi_giveaway_integration = None

async def main():
    """🔄 MODIFICADA: Main function con integración del sistema de permisos"""
    
    global multi_giveaway_integration

    await debug_directories()
    
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler('multi_giveaway_bot.log'),
            logging.StreamHandler()
        ]
    )
    
    logging.info("Starting Multi-Type Giveaway Bot with Permission System...")
    
    # Verify configuration
    if not verify_multi_giveaway_configuration():
        print("❌ Configuration incomplete. Please check config.json")
        return
    
    # Load configuration
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        
        BOT_TOKEN = bot_config['token']
        CHANNEL_ID = bot_config['channel_id']
        ADMIN_ID = bot_config['admin_id']
        ADMIN_USERNAME = bot_config.get('admin_username', 'admin')
        
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return
    
    # Create Telegram application
    app = Application.builder().token(BOT_TOKEN).build()

    # 🆕 INICIALIZAR SAFETY MANAGER AQUÍ (después de crear app, antes de permisos)
    setup_async_safety(app)
    print("🔒 Async Safety Manager initialized")

    permission_manager = setup_permission_system(app, "admin_permissions.json")
    print("✅ Permission system initialized successfully")

    # Create MT5 API
    mt5_api = RealMT5API()

    
    
    # ===== 🆕 NUEVOS HANDLERS CON PERMISOS GRANULARES =====
    
    # SYSTEM COMMANDS (sin permisos - público)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # COMANDOS ADMIN ESPECÍFICOS POR TIPO
    app.add_handler(CommandHandler("admin_send_daily", admin_send_daily_invitation))
    app.add_handler(CommandHandler("admin_send_weekly", admin_send_weekly_invitation))
    app.add_handler(CommandHandler("admin_send_monthly", admin_send_monthly_invitation))
    
    app.add_handler(CommandHandler("admin_run_daily", admin_run_daily_draw))
    app.add_handler(CommandHandler("admin_run_weekly", admin_run_weekly_draw))
    app.add_handler(CommandHandler("admin_run_monthly", admin_run_monthly_draw))

    # COMANDOS EXISTENTES CON PERMISOS
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("test_channel", test_channel_command))
    app.add_handler(CommandHandler("health_check", health_check_command))
    app.add_handler(CommandHandler("debug_permissions", debug_my_permissions))

    # COMANDOS CRÍTICOS FALTANTES
    
    app.add_handler(CommandHandler("admin_security_audit", admin_security_audit))

    print("✅ test_botTTT.py commands registered FIRST")

    app.add_handler(CallbackQueryHandler(
        lambda update, context: handle_payment_confirmations_only(update, context),
        pattern="^confirm_payment_(daily|weekly|monthly)_[^_]+$"  # ← Más específico
    ))
    print("✅ test_botTTT.py specific callbacks registered")
    
    # 🎯 ONLY user interface (más específico)
    app.add_handler(CallbackQueryHandler(
        handle_user_interface_callbacks,
        # pattern="^(show_rules|start_main|user_)$"  # Solo estos específicos
        pattern="^(show_rules|start_main|user_)$"
    ))

    # app.add_handler(CallbackQueryHandler(
    #     handle_payment_confirmations_only,
    #     # pattern="^confirm_payment_[^_]+_[^_]+$"  # Más específico
    #     pattern="^confirm_payment_[^_]+_[^_]+$"
    # ))
    
    
    # INITIALIZE MULTI-GIVEAWAY INTEGRATION WITH AUTOMATION
    multi_giveaway_integration = MultiGiveawayIntegration(
        application=app,
        mt5_api=mt5_api,
        config_file="config.json"
    )
    # 🆕 ADD: Setup automatic draws
    multi_giveaway_integration.setup_automatic_draws()


    # 5️⃣ TODO: Callbacks y otros comandos se agregarán en próximas fases
    
    # ===== 🔧 CALLBACK HANDLERS - FIXED APPROACH =====
    
    
    
    
    mt5_handler = MessageHandler(
        filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.Regex(r'^\d+$'),
        multi_giveaway_integration._handle_mt5_input_universal

    )
    app.add_handler(mt5_handler)

    print("✅ All handlers configured in correct order")
    
    # Get automation status for startup info
    automation_status = multi_giveaway_integration.get_automation_status()
    enabled_types = [t for t, enabled in automation_status.items() 
                    if enabled and t not in ['scheduler_running', 'scheduler_available']]

    print("✅ MultiGiveawayIntegration initialized (handlers registered AFTER)")

    print("🤖 Automatic Draw System Initialized")
    print(f"   ├─ Scheduler: {'🟢 RUNNING' if automation_status['scheduler_available'] else '❌ FAILED'}")
    print(f"   ├─ Auto-enabled types: {', '.join(enabled_types) if enabled_types else 'None (manual mode)'}")
    print(f"   ├─ Manual override: ✅ Always available")
    print(f"   └─ Control panel: /admin_panel → Automation")
    
    logging.info("All command handlers configured successfully")
    
    
    
    logging.info("All command handlers configured WITHOUT conflicts")
    
    # ===== REST OF MAIN FUNCTION UNCHANGED =====
    
    print("🚀 Multi-Type Giveaway Bot with Automatization Started Successfully")
    print(f"📢 Channel: {CHANNEL_ID}")
    print(f"👤 Admin: {ADMIN_ID} (@{ADMIN_USERNAME})")
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    print(f"🔐 Permission system: ACTIVE")
    print(f"🤖 Automation system: {'ACTIVE' if automation_status['scheduler_available'] else 'FAILED (check dependencies)'}")
    
    print("\n🎯 Available Giveaways:")
    for giveaway_type in ['daily', 'weekly', 'monthly']:
        giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
        prize = giveaway_system.get_prize_amount(giveaway_type)
        cooldown = giveaway_system.get_cooldown_days(giveaway_type)
        is_open = giveaway_system.is_participation_window_open(giveaway_type)
        status = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"   💰 {giveaway_type.title()}: ${prize} (cooldown: {cooldown}d) - {status}")
    
    print("\n📋 System Architecture:")
    print("   🎯 Payment confirmations: test_botTTT.py")
    print("   🎯 User interface: test_botTTT.py") 
    print("   🎯 Admin panels & analytics: ga_integration.py")
    print("   🎯 Automatic draws: ga_integration.py")
    print("   🎯 Manual draws: test_botTTT.py")
    
    print(f"\n🕐 Automation Schedule (London Time):")
    print(f"   📅 Daily: Monday-Friday at 17:00 ({'🟢 ENABLED' if automation_status.get('daily') else '🔴 DISABLED'})")
    print(f"   📅 Weekly: Friday at 17:15 ({'🟢 ENABLED' if automation_status.get('weekly') else '🔴 DISABLED'})")
    print(f"   📅 Monthly: Last Friday at 17:30 ({'🟢 ENABLED' if automation_status.get('monthly') else '🔴 DISABLED'})")
    recurring_status = multi_giveaway_integration.recurring_invitations_enabled
    
    print(f"\n🔔 Recurring Invitations Schedule:")
    print(f"   📧 Auto-invitations: {'🟢 ENABLED' if recurring_status else '🔴 DISABLED'}")
    if recurring_status:
        print(f"   ├─ Daily invitations: every {multi_giveaway_integration.invitation_frequencies['daily']}h")
        print(f"   ├─ Weekly invitations: every {multi_giveaway_integration.invitation_frequencies['weekly']}h")
        print(f"   └─ Monthly invitations: every {multi_giveaway_integration.invitation_frequencies['monthly']}h")


    print(f"\n📱 Admin Controls:")
    print(f"   🎛️ Main panel: /admin_panel")
    print(f"   🤖 Automation: /admin_panel → Automation button")
    print(f"   👤 Manual draws: /admin_run_daily, /admin_run_weekly, /admin_run_monthly")
    print(f"   💳 Payment confirmation: /admin_confirm_daily, /admin_confirm_weekly, /admin_confirm_monthly")
    
    # Start bot (rest unchanged)
    try:
        await app.initialize()
        await app.start()
        
        await app.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        
        stop_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            print("\n🛑 Stopping multi-type bot...")
            stop_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        await stop_event.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logging.error(f"Error in bot: {e}")
    finally:
        try:
            print("🧹 Cleaning up resources...")
            # 🆕 ADD: Shutdown automation scheduler
            if multi_giveaway_integration and multi_giveaway_integration.scheduler:
                multi_giveaway_integration.shutdown_scheduler()
                print("✅ Automation scheduler shutdown")
            
            if app.updater.running:
                await app.updater.stop()
            await app.stop()
            await app.shutdown()
            logging.info("Bot finished correctly")
        except Exception as cleanup_error:
            logging.error(f"Error in cleanup: {cleanup_error}")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    print("🎯 Multi-Type Giveaway Bot with Automatic Draws - PHASE 2")
    print("=" * 70)
    
    # Check dependencies
    print("🔍 Checking dependencies...")
    automation_available = check_automation_dependencies()

    # Verify required files
    required_files = ['ga_manager.py', 'ga_integration.py', 'config_loader.py', 'admin_permissions.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        print("Make sure you have all giveaway system files")
        exit(1)
    
    print("✅ System files verified")
    
    # Check admin permissions config
    if not os.path.exists("admin_permissions.json"):
        print("⚠️ admin_permissions.json not found!")
        print("💡 Creating basic configuration...")
        from admin_permissions import create_your_specific_config
        create_your_specific_config()
        print("✅ Basic configuration created.")
        print("🔧 IMPORTANT: Edit admin_permissions.json and replace ID placeholders with real Telegram IDs")
        exit(0)
    
    print("✅ Permission configuration found")
    
    # Setup files if needed
    if not os.path.exists("config.json"):
        print("⚠️ Setting up multi-giveaway files...")
        setup_multi_giveaway_files()
        print("✅ Files created. Please configure config.json and run again.")
        exit(0)
    
    print("\n🔧 CURRENT CONFIGURATION:")
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        giveaway_configs = config_loader.get_giveaway_configs()
        automation_config = config_loader.get_all_config().get('automation', {})
        
        print(f"   🤖 Bot Token: {bot_config['token'][:10]}...")
        print(f"   📢 Channel ID: {bot_config['channel_id']}")
        print(f"   👤 Admin ID: {bot_config['admin_id']}")
        print(f"   🎯 Giveaway Types: {', '.join(giveaway_configs.keys())}")
        print(f"   🤖 Automation: {'✅ Enabled' if automation_config.get('enabled', False) else '⚠️ Disabled'}")
        
        # Show prizes
        for giveaway_type, config in giveaway_configs.items():
            auto_enabled = automation_config.get('default_auto_modes', {}).get(giveaway_type, False)
            auto_status = "🤖 AUTO" if auto_enabled else "👤 MANUAL"
            print(f"   💰 {giveaway_type.title()}: ${config['prize']} - {auto_status}")
            
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        exit(1)
    
    print("\n🔐 PERMISSION SYSTEM: ACTIVE")
    print("🌍 TIMEZONE: Europe/London")
    print("⏰ TIME RESTRICTIONS: Enabled for specified admins")
    print("📊 GRANULAR PERMISSIONS: By giveaway type")
    print(f"🤖 AUTOMATION: {'Available' if automation_available else 'Requires APScheduler'}")
    
    print("\n📝 AUTOMATION FEATURES:")
    print("✅ Dynamic on/off control per giveaway type")
    print("✅ Admin channel notifications")
    print("✅ Automatic winner selection and notification")
    print("✅ Manual override always available")
    print("✅ Duplicate draw protection")
    print("✅ Error handling and notifications")
    print("✅ Zero conflicts with manual operations")
    
    print("\n📱 TESTING COMMANDS:")
    print("- /admin_panel (then click 'Automation' button)")
    print("- /admin_run_daily (manual override)")
    print("- /admin_confirm_daily @username (payment confirmation)")
    print("- /health_check (system status)")
    
    if not automation_available:
        print("\n⚠️  IMPORTANT: Install APScheduler for automatic draws:")
        print("   pip install apscheduler")
        print("   The system will work in manual-only mode without it.")
    print("=" * 70)
    
    # Run bot
    asyncio.run(main())