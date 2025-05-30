import logging
import asyncio
import os
import signal
from datetime import datetime
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from ga_integration import MultiGiveawayIntegration, setup_multi_giveaway_files, verify_multi_giveaway_configuration
from config_loader import ConfigLoader

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

# ==================== BOT COMMANDS CON PERMISOS ====================

async def start_command(update, context):
    """🔄 MANTENER IGUAL - Esta función no necesita permisos"""
    # Tu código existente sin cambios
    global multi_giveaway_integration
    
    user = update.effective_user
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
            print(f"🎯 User {user.first_name} wants to participate in {participation_type} giveaway")
            
            # Get the specific giveaway system
            giveaway_system = multi_giveaway_integration.get_giveaway_system(participation_type)
            
            if not giveaway_system:
                await update.message.reply_text(
                    f"❌ <b>{participation_type.title()} giveaway not available</b>\n\nPlease try again later.",
                    parse_mode='HTML'
                )
                return
            
            # Check if participation window is open
            if not giveaway_system.is_participation_window_open(participation_type):
                window_status = giveaway_system.get_participation_window_status(participation_type)
                next_window = window_status.get('next_open', 'Soon')
                
                await update.message.reply_text(
                    f"⏰ <b>{participation_type.title()} participation closed</b>\n\nParticipation window is currently closed.\n\n🔄 <b>Next window opens:</b>\n{next_window}\n\n💡 Stay tuned for the next opportunity!",
                    parse_mode='HTML'
                )
                return
            
            # Check if already registered for this type TODAY
            if giveaway_system._is_already_registered(user.id, participation_type):
                prize = giveaway_system.get_prize_amount(participation_type)
                await update.message.reply_text(
                    f"ℹ️ <b>Already registered for {participation_type}</b>\n\nYou are already participating in today's {participation_type} giveaway (${prize}).\n\n🍀 Good luck in the draw!\n\n⏰ Draw: Check schedule",
                    parse_mode='HTML'
                )
                return
            
            # Check if has pending registration for this type
            if context.user_data.get(f'awaiting_mt5_{participation_type}'):
                await update.message.reply_text(
                    f"⏳ <b>{participation_type.title()} registration in progress</b>\n\nYou already have a {participation_type} registration pending.\n\nPlease send your MT5 account number to complete your participation.",
                    parse_mode='HTML'
                )
                return
            
            # Check channel membership
            try:
                config_loader = ConfigLoader()
                bot_config = config_loader.get_bot_config()
                channel_id = bot_config['channel_id']
                
                member = await context.bot.get_chat_member(channel_id, user.id)
                is_member = member.status in ['member', 'administrator', 'creator']
            except:
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
            print(f"✅ User {user.id} activated for {participation_type} registration")
            
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

# ==================== 🆕 COMANDOS ADMIN DIVIDIDOS POR TIPO Y CON PERMISOS ====================

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
            await notify_payment_admins_new_winner(context, winner, 'daily', admin_name)
            
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
            await notify_payment_admins_new_winner(context, winner, 'weekly', admin_name)
            
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
            await notify_payment_admins_new_winner(context, winner, 'monthly', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, f"Monthly draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Monthly draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, "Monthly draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in monthly draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

# extra================== 1. CONFIRMACIÓN DE PAGOS ==================

async def admin_confirm_payment(update, context):
    """🚨 CRÍTICO: Comando para confirmar pagos - AGREGAR a ga_test_bot.py"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verificar admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can confirm payments")
            return
        
        # Verificar formato del comando
        if not context.args or len(context.args) != 1:
            await update.message.reply_text(
                "❌ <b>Incorrect usage</b>\n\n"
                "<b>Format:</b> <code>/admin_confirm_payment &lt;telegram_id_or_username&gt;</code>\n\n"
                "<b>Examples:</b>\n"
                "• <code>/admin_confirm_payment 123456789</code>\n"
                "• <code>/admin_confirm_payment @username</code>\n\n"
                "💡 Use <code>/admin_pending_winners</code> to see pending winners",
                parse_mode='HTML'
            )
            return
        
        winner_identifier = context.args[0].strip()
        
        # Intentar confirmación para cada tipo de giveaway
        confirmed = False
        confirmation_message = ""
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            
            # Buscar ganador pendiente
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            winner_found = None
            
            for winner in pending_winners:
                winner_username = winner.get('username', '').strip()
                winner_telegram_id = winner.get('telegram_id', '').strip()
                
                # Verificar si coincide el identificador
                if (winner_identifier == winner_telegram_id or 
                    winner_identifier.lower() == f"@{winner_username}".lower() or
                    winner_identifier.lower() == winner_username.lower()):
                    winner_found = winner_telegram_id
                    break
            
            if winner_found:
                # Confirmar pago
                success, message = await giveaway_system.confirm_payment_and_announce(
                    winner_found, user_id, giveaway_type
                )
                
                if success:
                    confirmed = True
                    prize = giveaway_system.get_prize_amount(giveaway_type)
                    confirmation_message = f"✅ <b>{giveaway_type.title()} payment confirmed successfully</b>\n\n" \
                                         f"🎯 Winner: {winner.get('first_name', 'Unknown')}\n" \
                                         f"💰 Prize: ${prize} USD\n" \
                                         f"📊 MT5: {winner['mt5_account']}\n\n" \
                                         f"✅ Winner announced publicly\n" \
                                         f"📬 Private congratulation sent"
                    break
        
        if confirmed:
            await update.message.reply_text(confirmation_message, parse_mode='HTML')
        else:
            await update.message.reply_text(
                f"❌ <b>Winner not found</b>\n\n"
                f"No pending winner found with identifier: <code>{winner_identifier}</code>\n\n"
                f"💡 Use <code>/admin_pending_winners</code> to see all pending winners",
                parse_mode='HTML'
            )
        
    except Exception as e:
        logging.error(f"Error in payment confirmation: {e}")
        await update.message.reply_text("❌ Error processing payment confirmation")

# extra================== 2. GANADORES PENDIENTES ==================

async def admin_pending_winners(update, context):
    """🚨 CRÍTICO: Comando para ver ganadores pendientes - AGREGAR a ga_test_bot.py"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verificar admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can view pending winners")
            return
        
        # Obtener ganadores pendientes de todos los tipos
        all_pending = {}
        total_pending = 0
        total_amount = 0
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            pending = giveaway_system.get_pending_winners(giveaway_type)
            if pending:
                all_pending[giveaway_type] = pending
                total_pending += len(pending)
                
                # Calcular monto total
                prize = giveaway_system.get_prize_amount(giveaway_type)
                total_amount += len(pending) * prize
        
        if total_pending == 0:
            await update.message.reply_text(
                "ℹ️ <b>No pending winners</b>\n\nAll payments are up to date.\n\n🎯 Next draws will be automatically scheduled",
                parse_mode='HTML'
            )
            return
        
        # Formatear mensaje con todos los ganadores pendientes
        message = f"📋 <b>PENDING WINNERS ({total_pending})</b>\n"
        message += f"💰 <b>Total amount:</b> ${total_amount} USD\n\n"
        
        buttons = []
        
        for giveaway_type, pending_winners in all_pending.items():
            prize = multi_giveaway_integration.get_giveaway_system(giveaway_type).get_prize_amount(giveaway_type)
            message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    identifier = f"@{username}"
                    command_identifier = username
                    button_display = f"@{username}"
                else:
                    identifier = f"{first_name} (ID: {winner['telegram_id']})"
                    command_identifier = winner['telegram_id']
                    button_display = first_name
                
                message += f"  {i}. {identifier}\n"
                message += f"     💰 Prize: ${winner['prize']} USD\n"
                message += f"     📊 MT5: <code>{winner['mt5_account']}</code>\n"
                message += f"     📅 Selected: {winner['selected_time']}\n\n"
                
                # Crear botón de confirmación
                button_text = f"✅ Confirm {giveaway_type} - {button_display}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        message += f"💡 <b>Quick confirmation:</b> Press buttons below\n"
        message += f"💡 <b>Manual confirmation:</b> <code>/admin_confirm_payment &lt;id_or_username&gt;</code>"
        
        # Limitar botones para evitar overflow
        if len(buttons) > 10:
            buttons = buttons[:10]
            message += f"\n\n⚠️ Showing first 10 confirmation buttons only"
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Error getting pending winners: {e}")
        await update.message.reply_text("❌ Error getting pending winners")

# extra================== 3. PANEL ADMINISTRATIVO ==================

async def admin_panel(update, context):
    """🚨 CRÍTICO: Panel administrativo completo - AGREGAR a ga_test_bot.py"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verificar admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can access admin panel")
            return
        
        # Obtener estadísticas rápidas del sistema
        total_pending = 0
        total_today = 0
        stats_summary = []
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)
            today_participants = stats.get('today_participants', 0)
            
            total_pending += pending_count
            total_today += today_participants
            
            # Verificar si ventana de participación está abierta
            is_open = giveaway_system.is_participation_window_open(giveaway_type)
            status_emoji = "🟢" if is_open else "🔴"
            
            stats_summary.append({
                'type': giveaway_type,
                'prize': prize,
                'today_participants': today_participants,
                'pending': pending_count,
                'total_winners': stats.get('total_winners', 0),
                'status_emoji': status_emoji,
                'is_open': is_open
            })
        
        # Construir mensaje del panel
        message = f"🎛️ <b>MULTI-GIVEAWAY ADMIN PANEL</b>\n\n"
        
        # Estado general
        message += f"📊 <b>System Status:</b>\n"
        message += f"├─ Today's participants: <b>{total_today}</b>\n"
        message += f"├─ Pending winners: <b>{total_pending}</b>\n"
        message += f"└─ System health: {'🟢 Operational' if total_pending < 10 else '⚠️ High pending'}\n\n"
        
        # Estado por tipo
        message += f"🎯 <b>Giveaway Types:</b>\n"
        for stat in stats_summary:
            message += f"{stat['status_emoji']} <b>{stat['type'].upper()}</b> (${stat['prize']}): "
            message += f"{stat['today_participants']} today, {stat['pending']} pending\n"
        
        message += f"\n🚀 <b>Quick Actions:</b>"
        
        # Crear botones del panel principal
        buttons = [
            # Fila 1: Acciones principales
            [
                InlineKeyboardButton("📢 Send Invitations", callback_data="panel_send_invitations"),
                InlineKeyboardButton("🎲 Execute Draws", callback_data="panel_execute_draws")
            ],
            # Fila 2: Gestión de ganadores
            [
                InlineKeyboardButton(f"👑 Pending ({total_pending})", callback_data="panel_pending_winners"),
                InlineKeyboardButton("📊 Statistics", callback_data="panel_statistics")
            ],
            # Fila 3: Acceso por tipo
            [
                InlineKeyboardButton("📅 Daily", callback_data="panel_daily"),
                InlineKeyboardButton("📅 Weekly", callback_data="panel_weekly"),
                InlineKeyboardButton("📅 Monthly", callback_data="panel_monthly")
            ],
            # Fila 4: Sistema
            [
                InlineKeyboardButton("🏥 Health Check", callback_data="panel_health"),
                InlineKeyboardButton("🔧 Maintenance", callback_data="panel_maintenance")
            ],
            # Fila 5: Refresh
            [
                InlineKeyboardButton("🔄 Refresh Panel", callback_data="panel_refresh")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Error in admin panel: {e}")
        await update.message.reply_text("❌ Error loading admin panel")

def add_missing_callback_patterns():
    """🚨 CRÍTICO: Patterns faltantes para handle_admin_callbacks()"""
    
    # AGREGAR al final de handle_admin_callbacks(), ANTES del else final:
    
    # Manejar confirmaciones de pago
    if callback_data.startswith("confirm_payment_"):
        parts = callback_data.split("_", 3)  # confirm_payment_<type>_<identifier>
        if len(parts) >= 4:
            giveaway_type = parts[2]
            winner_identifier = parts[3]
            
            if giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                
                # Buscar ganador por identificador
                pending_winners = giveaway_system.get_pending_winners(giveaway_type)
                winner_found = None
                
                for winner in pending_winners:
                    winner_username = winner.get('username', '').strip()
                    winner_telegram_id = winner.get('telegram_id', '').strip()
                    
                    if (winner_identifier == winner_telegram_id or 
                        winner_identifier == winner_username):
                        winner_found = winner_telegram_id
                        break
                
                if winner_found:
                    success, message = await giveaway_system.confirm_payment_and_announce(
                        winner_found, user_id, giveaway_type
                    )
                    
                    if success:
                        await query.edit_message_text(
                            f"✅ <b>{giveaway_type.title()} payment confirmed</b>\n\n"
                            f"Winner has been announced and notified.",
                            parse_mode='HTML'
                        )
                    else:
                        await query.edit_message_text(f"❌ {message}", parse_mode='HTML')
                else:
                    await query.edit_message_text(
                        f"❌ Winner not found or already processed",
                        parse_mode='HTML'
                    )
            else:
                await query.edit_message_text("❌ Invalid giveaway type")
        else:
            await query.edit_message_text("❌ Invalid callback format")
    
    # Manejar acciones del panel
    elif callback_data == "panel_pending_winners":
        # Mostrar ganadores pendientes
        await admin_pending_winners(update, context)
    
    elif callback_data == "panel_statistics":
        # Mostrar estadísticas combinadas
        combined_stats = multi_giveaway_integration.get_giveaway_stats()
        stats_message = f"""📊 <b>SYSTEM STATISTICS</b>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participants: <b>{combined_stats['total_participants_all']}</b>
├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
└─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

💡 Use /admin_panel for management options"""
        
        await query.edit_message_text(stats_message, parse_mode='HTML')
    
    elif callback_data == "panel_health":
        # Ejecutar health check
        health_report = multi_giveaway_integration.verify_all_systems_health()
        
        health_message = f"""🏥 <b>SYSTEM HEALTH CHECK</b>

🌡️ <b>Status:</b> {health_report['overall_status'].upper()}
📅 <b>Time:</b> {health_report['timestamp']}

💡 Use /health_check for detailed report"""
        
        await query.edit_message_text(health_message, parse_mode='HTML')
    
    elif callback_data == "panel_refresh":
        # Refrescar panel
        await admin_panel(update, context)
    
    elif callback_data.startswith("panel_"):
        await query.edit_message_text(
            f"🔧 <b>Panel function: {callback_data}</b>\n\n"
            f"This panel section is under development.\n\n"
            f"💡 Use /admin_panel to return to main panel",
            parse_mode='HTML'
        )



# 🆕 NUEVAS FUNCIONES DE NOTIFICACIÓN GRANULAR

async def notify_payment_admins_new_winner(context, winner, giveaway_type, executed_by):
    """🆕 NUEVA: Notificar a admins con permisos de confirmación de pagos"""
    permission_manager = get_permission_manager(context)
    
    # Mapear tipo de giveaway a acción de confirmación
    confirm_action_map = {
        'daily': SystemAction.CONFIRM_DAILY_PAYMENTS,
        'weekly': SystemAction.CONFIRM_WEEKLY_PAYMENTS,
        'monthly': SystemAction.CONFIRM_MONTHLY_PAYMENTS
    }
    
    required_permission = confirm_action_map.get(giveaway_type)
    if not required_permission:
        return
    
    # Obtener admins con permiso de confirmación para este tipo
    admins_who_can_confirm = permission_manager.get_admins_with_permission(required_permission)
    
    if not admins_who_can_confirm:
        logging.warning(f"No admins found with permission to confirm {giveaway_type} payments")
        return
    
    # Preparar información del ganador
    username = winner.get('username', '').strip()
    first_name = winner.get('first_name', 'N/A')
    winner_display = f"@{username}" if username else first_name
    
    notification_message = f"""🔔 <b>NEW {giveaway_type.upper()} WINNER - PAYMENT NEEDED</b>

🎉 <b>Winner:</b> {first_name} ({winner_display})
📊 <b>MT5 Account:</b> <code>{winner['mt5_account']}</code>
💰 <b>Prize:</b> ${winner['prize']} USD
👤 <b>Draw executed by:</b> {executed_by}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

⚠️ <b>ACTION REQUIRED:</b>
💸 Transfer ${winner['prize']} USD to account {winner['mt5_account']}
💡 Use <code>/admin_confirm_{giveaway_type} {username if username else winner['telegram_id']}</code> after transfer

🎯 <b>Your permission level allows you to confirm this payment.</b>"""
    
    # Enviar notificación a cada admin autorizado
    for admin_id in admins_who_can_confirm:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification_message,
                parse_mode='HTML'
            )
            print(f"✅ Payment notification sent to admin {admin_id}")
        except Exception as e:
            logging.error(f"Error sending notification to admin {admin_id}: {e}")

# ==================== 🔄 COMANDOS EXISTENTES MODIFICADOS ====================

@require_permission(SystemAction.VIEW_ADVANCED_STATS)
async def stats_command(update, context):
    """🔄 MODIFICADA: Stats con niveles de permisos"""
    try:
        user_id = update.effective_user.id
        permission_manager = get_permission_manager(context)
        admin_info = permission_manager.get_admin_info(user_id)
        admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
        
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

# ==================== DEBUG COMMANDS CON PERMISOS ====================

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

# ==================== 🆕 COMANDOS DE CONFIRMACIÓN DE PAGOS POR TIPO ====================

@require_permission(SystemAction.CONFIRM_DAILY_PAYMENTS)
async def admin_confirm_daily_payment(update, context):
    """🆕 NUEVO: Confirmar pago daily (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    # Verificar parámetros del comando
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(
            "❌ <b>Uso incorrecto</b>\n\n"
            "<b>Formato:</b> <code>/admin_confirm_daily &lt;username_o_telegram_id&gt;</code>\n\n"
            "<b>Ejemplos:</b>\n"
            "• <code>/admin_confirm_daily @username</code>\n"
            "• <code>/admin_confirm_daily 123456789</code>",
            parse_mode='HTML'
        )
        return
    
    winner_identifier = context.args[0].strip()
    
    print(f"✅ Daily payment confirmation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('daily')
        
        # Buscar ganador por username o ID
        winner_telegram_id = await find_winner_by_identifier(winner_identifier, 'daily', giveaway_system)
        
        if not winner_telegram_id:
            await update.message.reply_text(
                f"❌ <b>Daily winner not found</b>\n\n"
                f"No pending daily winner found with: <code>{winner_identifier}</code>\n\n"
                f"💡 Use <code>/admin_pending_daily</code> to see pending winners",
                parse_mode='HTML'
            )
            return
        
        # Confirmar pago
        success, message = await giveaway_system.confirm_payment_and_announce(
            winner_telegram_id, user_id, 'daily'
        )
        
        if success:
            response_message = f"""✅ <b>Daily payment confirmed successfully</b>

👤 <b>Confirmed by:</b> {admin_name}
🎯 <b>Winner:</b> {winner_identifier}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Winner announced publicly
📬 Private congratulation sent
📊 System updated for next daily draw

💡 <b>Status:</b> Complete ✓"""
            
            await update.message.reply_text(response_message, parse_mode='HTML')
            
            # Notificar a otros admins sobre la confirmación
            await notify_payment_confirmed(context, winner_identifier, 'daily', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS, 
                                        f"Daily payment confirmed for {winner_identifier}")
        else:
            await update.message.reply_text(f"❌ {message}", parse_mode='HTML')
            permission_manager.log_action(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS, 
                                        f"Failed to confirm daily payment for {winner_identifier}: {message}")
        
    except Exception as e:
        logging.error(f"Error in daily payment confirmation: {e}")
        await update.message.reply_text(f"❌ Error: {e}")


# ==================== FUNCIONES AUXILIARES ====================

async def find_winner_by_identifier(identifier, giveaway_type, giveaway_system):
    """🆕 NUEVA: Buscar ganador por username o telegram_id"""
    try:
        # Remover @ si está presente
        if identifier.startswith('@'):
            identifier = identifier[1:]
        
        pending_winners = giveaway_system.get_pending_winners(giveaway_type)
        
        for winner in pending_winners:
            winner_username = winner.get('username', '').strip()
            winner_telegram_id = winner.get('telegram_id', '').strip()
            
            # Buscar por username o telegram_id
            if (identifier.lower() == winner_username.lower() or 
                identifier == winner_telegram_id):
                return winner_telegram_id
        
        return None
        
    except Exception as e:
        logging.error(f"Error finding {giveaway_type} winner: {e}")
        return None

async def notify_payment_confirmed(context, winner_identifier, giveaway_type, confirmed_by):
    """🆕 NUEVA: Notificar confirmación de pago a otros admins"""
    permission_manager = get_permission_manager(context)
    
    # Obtener admins con permisos de ver pagos confirmados
    view_payments_action = SystemAction.VIEW_PAYMENT_HISTORY
    admins_to_notify = permission_manager.get_admins_with_permission(view_payments_action)
    
    notification_message = f"""✅ <b>{giveaway_type.upper()} PAYMENT CONFIRMED</b>

🏆 <b>Winner:</b> {winner_identifier}
👤 <b>Confirmed by:</b> {confirmed_by}
📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ Winner announced publicly
📬 Private congratulation sent
📊 System updated for next {giveaway_type} draw

💡 <b>Status:</b> Payment process complete ✓"""
    
    # Enviar notificación a admins autorizados
    for admin_id in admins_to_notify:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=notification_message,
                parse_mode='HTML'
            )
        except Exception as e:
            logging.error(f"Error notifying admin {admin_id} about payment confirmation: {e}")

# ==================== COMANDOS PARA VER PENDIENTES POR TIPO ====================

@require_any_permission(
    SystemAction.CONFIRM_DAILY_PAYMENTS,
    SystemAction.VIEW_ALL_PENDING_WINNERS
)
async def admin_pending_daily(update, context):
    """🆕 NUEVO: Ver ganadores daily pendientes"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    try:
        giveaway_system = multi_giveaway_integration.get_giveaway_system('daily')
        pending_winners = giveaway_system.get_pending_winners('daily')
        
        if not pending_winners:
            await update.message.reply_text(
                "ℹ️ <b>No pending daily winners</b>\n\n"
                "All daily payments are up to date.\n\n"
                "🎯 Next daily draw: Today at 5:00 PM",
                parse_mode='HTML'
            )
            return
        
        message = f"""📋 <b>PENDING DAILY WINNERS ({len(pending_winners)})</b>
<i>Viewed by: {admin_name}</i>

"""
        
        for i, winner in enumerate(pending_winners, 1):
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            
            display_name = f"@{username}" if username else f"{first_name} (ID: {winner['telegram_id']})"
            command_identifier = username if username else winner['telegram_id']
            
            message += f"""{i}. <b>{first_name}</b> ({display_name})
   📊 MT5: <code>{winner['mt5_account']}</code>
   💰 Prize: ${winner['prize']} USD
   📅 Selected: {winner['selected_time']}
   💡 Command: <code>/admin_confirm_daily {command_identifier}</code>

"""
        
        message += """💡 <b>Instructions:</b>
1️⃣ Transfer the amount to the MT5 account
2️⃣ Use the confirmation command shown above
3️⃣ Bot will announce the winner automatically"""
        
        await update.message.reply_text(message, parse_mode='HTML')
        
        permission_manager.log_action(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS, 
                                    f"Viewed {len(pending_winners)} pending daily winners")
        
    except Exception as e:
        logging.error(f"Error getting pending daily winners: {e}")
        await update.message.reply_text("❌ Error getting pending daily winners")



# ==================== 🔄 DEBUG PERMISSION FUNCTION ====================

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

# ==================== 🚀 COMANDOS DE CONFIRMACIÓN COMPLETAMENTE REUTILIZABLES ====================

# ==================== FUNCIÓN GENÉRICA MAESTRA ====================

async def admin_confirm_payment_universal(update, context, giveaway_type):
    """
    🌟 FUNCIÓN UNIVERSAL REUTILIZABLE para confirmación de pagos
    Aprovecha TODAS las funcionalidades existentes en ga_manager y ga_integration
    
    Args:
        update: Telegram update object
        context: Telegram context object  
        giveaway_type: 'daily', 'weekly', 'monthly' (100% extensible)
    """
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    # 🎯 CONFIGURACIÓN DINÁMICA (100% ESCALABLE)
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
    
    # ✅ VALIDACIÓN DE PARÁMETROS (UNIVERSAL)
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
        # 🎯 USAR SISTEMA EXISTENTE (ga_integration.py)
        giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
        if not giveaway_system:
            await update.message.reply_text(
                f"❌ <b>{config['display_name']} giveaway system not available</b>\n\n"
                f"Please contact a FULL_ADMIN to check system status.",
                parse_mode='HTML'
            )
            return
        
        # 🔍 BUSCAR GANADOR USANDO FUNCIÓN EXISTENTE (ga_integration.py)
        winner_telegram_id = await multi_giveaway_integration._find_winner_by_identifier(winner_identifier, giveaway_type)
        
        if not winner_telegram_id:
            await update.message.reply_text(
                f"❌ <b>{config['display_name']} winner not found</b>\n\n"
                f"No pending {giveaway_type} winner found with: <code>{winner_identifier}</code>\n\n"
                f"💡 Use <code>/admin_pending_{giveaway_type}</code> to see all pending {giveaway_type} winners\n"
                f"💡 Make sure to use exact username (with @) or telegram ID",
                parse_mode='HTML'
            )
            return
        
        # 💰 CONFIRMAR PAGO USANDO FUNCIÓN EXISTENTE (ga_manager.py)
        success, message = await giveaway_system.confirm_payment_and_announce(
            winner_telegram_id, user_id, giveaway_type
        )
        
        if success:
            # 🎯 OBTENER INFORMACIÓN ADICIONAL
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # ✅ MENSAJE DE ÉXITO DINÁMICO
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
            
            # 📢 NOTIFICAR A OTROS ADMINS CON PERMISOS
            await notify_payment_confirmed_to_authorized_admins(
                context, winner_identifier, giveaway_type, admin_name, prize
            )
            
            # 📝 LOG DE AUDITORÍA
            permission_manager.log_action(
                user_id, 
                config['permission'], 
                f"{config['display_name']} payment confirmed for {winner_identifier} (${prize})"
            )
            
        else:
            # ❌ ERROR EN CONFIRMACIÓN
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
            f"Please try again in a few moments or contact a FULL_ADMIN.\n\n"
            f"<i>Error reference: {str(e)[:50]}...</i>",
            parse_mode='HTML'
        )

# ==================== COMANDOS ESPECÍFICOS (SIMPLE WRAPPER) ====================

@require_permission(SystemAction.CONFIRM_DAILY_PAYMENTS)
async def admin_confirm_daily_payment(update, context):
    """🎯 COMANDO ESPECÍFICO: Confirmar pago daily"""
    await admin_confirm_payment_universal(update, context, 'daily')

@require_permission(SystemAction.CONFIRM_WEEKLY_PAYMENTS)
async def admin_confirm_weekly_payment(update, context):
    """🎯 COMANDO ESPECÍFICO: Confirmar pago weekly"""
    await admin_confirm_payment_universal(update, context, 'weekly')

@require_permission(SystemAction.CONFIRM_MONTHLY_PAYMENTS)
async def admin_confirm_monthly_payment(update, context):
    """🎯 COMANDO ESPECÍFICO: Confirmar pago monthly"""
    await admin_confirm_payment_universal(update, context, 'monthly')

# ==================== FUNCIÓN PARA VER PENDIENTES (TAMBIÉN REUTILIZABLE) ====================

async def admin_view_pending_universal(update, context, giveaway_type):
    """
    🌟 FUNCIÓN UNIVERSAL para ver ganadores pendientes
    Usa las funciones existentes de ga_manager.py
    """
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    # Configuración dinámica
    display_name = giveaway_type.title()
    
    try:
        # 🎯 USAR FUNCIÓN EXISTENTE (ga_integration.py)
        giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
        if not giveaway_system:
            await update.message.reply_text(f"❌ {display_name} giveaway system not available")
            return
        
        # 📋 OBTENER PENDIENTES USANDO FUNCIÓN EXISTENTE (ga_manager.py)
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
        
        # 📝 GENERAR LISTA DETALLADA
        message = f"""📋 <b>PENDING {display_name.upper()} WINNERS ({len(pending_winners)})</b>
<i>Viewed by: {admin_name}</i>

"""
        
        prize = giveaway_system.get_prize_amount(giveaway_type)
        
        for i, winner in enumerate(pending_winners, 1):
            username = winner.get('username', '').strip()
            first_name = winner.get('first_name', 'N/A')
            
            # Determinar display name y comando
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
        
        # 📝 LOG
        permission_manager.log_action(
            user_id, 
            SystemAction.VIEW_ALL_PENDING_WINNERS, 
            f"Viewed {len(pending_winners)} pending {giveaway_type} winners"
        )
        
    except Exception as e:
        logging.error(f"Error getting pending {giveaway_type} winners: {e}")
        await update.message.reply_text(f"❌ Error getting pending {giveaway_type} winners")

# ==================== COMANDOS PARA VER PENDIENTES ====================

@require_any_permission(
    SystemAction.CONFIRM_DAILY_PAYMENTS,
    SystemAction.VIEW_ALL_PENDING_WINNERS
)
async def admin_pending_daily(update, context):
    """📋 VER PENDIENTES: Daily winners"""
    await admin_view_pending_universal(update, context, 'daily')

@require_any_permission(
    SystemAction.CONFIRM_WEEKLY_PAYMENTS,
    SystemAction.VIEW_ALL_PENDING_WINNERS
)
async def admin_pending_weekly(update, context):
    """📋 VER PENDIENTES: Weekly winners"""
    await admin_view_pending_universal(update, context, 'weekly')

@require_any_permission(
    SystemAction.CONFIRM_MONTHLY_PAYMENTS,
    SystemAction.VIEW_ALL_PENDING_WINNERS
)
async def admin_pending_monthly(update, context):
    """📋 VER PENDIENTES: Monthly winners"""
    await admin_view_pending_universal(update, context, 'monthly')

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


def add_payment_confirmation_handlers(app):
    """
    🔧 AGREGAR todos los handlers de confirmación de pagos al bot
    """
    
    # Comandos de confirmación por tipo
    app.add_handler(CommandHandler("admin_confirm_daily", admin_confirm_daily_payment))
    app.add_handler(CommandHandler("admin_confirm_weekly", admin_confirm_weekly_payment))
    app.add_handler(CommandHandler("admin_confirm_monthly", admin_confirm_monthly_payment))
    
    # Comandos para ver pendientes por tipo
    app.add_handler(CommandHandler("admin_pending_daily", admin_pending_daily))
    app.add_handler(CommandHandler("admin_pending_weekly", admin_pending_weekly))
    app.add_handler(CommandHandler("admin_pending_monthly", admin_pending_monthly))
    
    print("✅ Payment confirmation handlers added successfully")
    print("   💰 Confirmation commands: /admin_confirm_daily, /admin_confirm_weekly, /admin_confirm_monthly")
    print("   📋 Pending commands: /admin_pending_daily, /admin_pending_weekly, /admin_pending_monthly")

# ==================== 🔄 MAIN FUNCTION MODIFICADA ====================

# Global variable for multi-giveaway integration
multi_giveaway_integration = None

async def main():
    """🔄 MODIFICADA: Main function con integración del sistema de permisos"""
    
    global multi_giveaway_integration
    
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
    
    # 🆕 CRÍTICO: Setup del sistema de permisos ANTES que todo
    print("🔐 Initializing Permission System...")
    try:
        permission_manager = setup_permission_system(app, "admin_permissions.json")
        print("✅ Permission system initialized successfully")
        
        # Verificar que hay al least un FULL_ADMIN configurado
        full_admins = permission_manager.get_admins_with_permission(SystemAction.MANAGE_ADMINS)
        if not full_admins:
            print("⚠️ WARNING: No FULL_ADMIN found in configuration!")
            print("⚠️ Make sure to replace ID placeholders with real Telegram IDs")
        else:
            print(f"✅ Found {len(full_admins)} FULL_ADMIN(s) configured")
        
    except Exception as e:
        print(f"❌ Error initializing permission system: {e}")
        print("❌ Make sure admin_permissions.json exists and is properly configured")
        return
    
    # Create MT5 API
    mt5_api = RealMT5API()
    
    # ===== INITIALIZE MULTI-GIVEAWAY SYSTEM =====
    multi_giveaway_integration = MultiGiveawayIntegration(
        application=app,
        mt5_api=mt5_api,
        config_file="config.json"
    )
    
    # ===== 🆕 NUEVOS HANDLERS CON PERMISOS GRANULARES =====
    
    # 1️⃣ SYSTEM COMMANDS (sin permisos - público)
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # 2️⃣ 🆕 COMANDOS ADMIN ESPECÍFICOS POR TIPO
    
    # Invitaciones por tipo
    app.add_handler(CommandHandler("admin_send_daily", admin_send_daily_invitation))
    app.add_handler(CommandHandler("admin_send_weekly", admin_send_weekly_invitation))
    app.add_handler(CommandHandler("admin_send_monthly", admin_send_monthly_invitation))
    
    # Sorteos por tipo (con verificación horaria automática)
    app.add_handler(CommandHandler("admin_run_daily", admin_run_daily_draw))
    app.add_handler(CommandHandler("admin_run_weekly", admin_run_weekly_draw))
    app.add_handler(CommandHandler("admin_run_monthly", admin_run_monthly_draw))

    # Comandos de confirmación por tipo
    app.add_handler(CommandHandler("admin_confirm_daily", admin_confirm_daily_payment))
    app.add_handler(CommandHandler("admin_confirm_weekly", admin_confirm_weekly_payment))
    app.add_handler(CommandHandler("admin_confirm_monthly", admin_confirm_monthly_payment))
    
    # Comandos para ver pendientes por tipo
    app.add_handler(CommandHandler("admin_pending_daily", admin_pending_daily))
    app.add_handler(CommandHandler("admin_pending_weekly", admin_pending_weekly))
    app.add_handler(CommandHandler("admin_pending_monthly", admin_pending_monthly))
    
    print("✅ Payment confirmation handlers added")
    
    # 3️⃣ COMANDOS EXISTENTES CON PERMISOS
    app.add_handler(CommandHandler("stats", stats_command))
    
    # 4️⃣ DEBUG COMMANDS CON PERMISOS
    app.add_handler(CommandHandler("test_channel", test_channel_command))
    app.add_handler(CommandHandler("health_check", health_check_command))
    app.add_handler(CommandHandler("debug_permissions", debug_my_permissions))


    # 🆕 COMANDOS CRÍTICOS FALTANTES
    app.add_handler(CommandHandler("admin_confirm_payment", admin_confirm_payment))
    app.add_handler(CommandHandler("admin_pending_winners", admin_pending_winners))
    app.add_handler(CommandHandler("admin_panel", admin_panel))

    add_payment_confirmation_handlers(app)
    
    # 5️⃣ TODO: Callbacks y otros comandos se agregarán en próximas fases
    
    logging.info("All command handlers with permissions configured")
    
    # System information
    print("🚀 Multi-Type Giveaway Bot with Permissions Started Successfully")
    print(f"📢 Channel configured: {CHANNEL_ID}")
    print(f"👤 Admin configured: {ADMIN_ID} (@{ADMIN_USERNAME})")
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    print(f"🔐 Permission system: ACTIVE")
    
    print("\n🎯 Available Giveaways:")
    
    # Show giveaway info
    for giveaway_type in ['daily', 'weekly', 'monthly']:
        giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
        prize = giveaway_system.get_prize_amount(giveaway_type)
        cooldown = giveaway_system.get_cooldown_days(giveaway_type)
        is_open = giveaway_system.is_participation_window_open(giveaway_type)
        status = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"   💰 {giveaway_type.title()}: ${prize} (cooldown: {cooldown}d) - {status}")
    
    print("\n📋 🆕 NEW Permission-Based Commands:")
    print("   🔐 INVITATIONS:")
    print("      /admin_send_daily - Send daily invitation (requires SEND_DAILY_INVITATION)")
    print("      /admin_send_weekly - Send weekly invitation (requires SEND_WEEKLY_INVITATION)")
    print("      /admin_send_monthly - Send monthly invitation (requires SEND_MONTHLY_INVITATION)")
    print("   🔐 DRAWS (with time restrictions):")
    print("      /admin_run_daily - Execute daily draw (requires EXECUTE_DAILY_DRAW + time check)")
    print("      /admin_run_weekly - Execute weekly draw (requires EXECUTE_WEEKLY_DRAW + time check)")
    print("      /admin_run_monthly - Execute monthly draw (requires EXECUTE_MONTHLY_DRAW + time check)")
    print("   🔐 MONITORING:")
    print("      /stats - View statistics (requires VIEW_ADVANCED_STATS)")
    print("      /test_channel - Test channel (requires TEST_CONNECTIONS)")
    print("      /health_check - System health (requires HEALTH_CHECK)")
    
    print("\n📋 👤 USERS (no permissions needed):")
    print("      /start - Multi-type giveaway participation")
    print("      /help - Complete rules and schedule")
    
    print("\n✅ Multi-type bot with permissions ready!")
    print("💡 NOTE: Make sure to replace ID placeholders in admin_permissions.json with real Telegram IDs")
    
    # Start bot (infinite loop)
    try:
        # Initialize application
        await app.initialize()
        await app.start()
        
        # Start polling
        await app.updater.start_polling(
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True
        )
        
        # Keep bot running until interruption
        stop_event = asyncio.Event()
        
        def signal_handler(signum, frame):
            print("\n🛑 Stopping multi-type bot with permissions...")
            stop_event.set()
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Wait for stop signal
        await stop_event.wait()
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        logging.error(f"Error in bot: {e}")
    finally:
        # Clean up resources
        try:
            print("🧹 Cleaning up resources...")
            
            # Stop bot
            if app.updater.running:
                await app.updater.stop()
            await app.stop()
            await app.shutdown()
            logging.info("Multi-type bot with permissions finished correctly")
        except Exception as cleanup_error:
            logging.error(f"Error in cleanup: {cleanup_error}")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    print("🎯 Multi-Type Giveaway Bot with Granular Permissions - PHASE 2")
    print("=" * 70)
    
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
        
        print(f"   🤖 Bot Token: {bot_config['token'][:10]}...")
        print(f"   📢 Channel ID: {bot_config['channel_id']}")
        print(f"   👤 Admin ID: {bot_config['admin_id']}")
        print(f"   🎯 Giveaway Types: {', '.join(giveaway_configs.keys())}")
        
        # Show prizes
        for giveaway_type, config in giveaway_configs.items():
            print(f"   💰 {giveaway_type.title()}: ${config['prize']}")
            
    except Exception as e:
        print(f"   ❌ Configuration error: {e}")
        exit(1)
    
    print("\n🔐 PERMISSION SYSTEM: ACTIVE")
    print("🌍 TIMEZONE: Europe/London")
    print("⏰ TIME RESTRICTIONS: Enabled for specified admins")
    print("📊 GRANULAR PERMISSIONS: By giveaway type")
    print("\n📝 PHASE 2 FEATURES:")
    print("✅ Permission decorators on all admin commands")
    print("✅ Time-based restrictions for draws")
    print("✅ Granular notifications by permission level")
    print("✅ Complete audit logging")
    print("✅ Separate commands by giveaway type")
    
    print("\n📱 COMMANDS TO TEST:")
    print("- /admin_send_daily (test permission system)")
    print("- /admin_run_daily (test time restrictions)")
    print("- /stats (test stats permissions)")
    print("- /health_check (test health check permissions)")
    print("\nPress Ctrl+C to stop the bot")
    print("=" * 70)
    
    # Run bot
    asyncio.run(main())