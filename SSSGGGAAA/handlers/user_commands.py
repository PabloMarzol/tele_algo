from utils.admin_permission import   AdminPermissionManager,     SystemAction,     PermissionGroup,    setup_permission_system,    get_permission_manager,    require_permission,    require_any_permission,    require_draw_permission_with_time_check
from utils.utils import is_user_rate_limited
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
import datetime
import logging
import os

async def _handle_stats_command_public(integration_instance, update, context):
        """🔄 MODIFIED: Public stats command (admin only, shows all types)"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            # Get quick stats from all types
            message = "📊 <b>GIVEAWAY STATISTICS OVERVIEW</b>\n\n"
            
            total_today = 0
            total_pending = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
                message += f"├─ Today: {stats.get('today_participants', 0)} participants\n"
                message += f"├─ Pending: {pending_count} winners\n"
                message += f"└─ Total distributed: ${stats.get('total_prize_distributed', 0)}\n\n"
                
                total_today += stats.get('today_participants', 0)
                total_pending += pending_count
            
            message += f"📈 <b>COMBINED:</b> {total_today} today, {total_pending} pending"
            
            keyboard = [[InlineKeyboardButton("🏠 Admin panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing public stats: {e}")
            await update.message.reply_text("❌ Error getting statistics")  # Para usuarios VIEW_ONLY

async def show_view_only_panel_direct(self, update, context):
        """🆕 NUEVA: Panel VIEW_ONLY directo desde command (NO callback)"""
        user_id = update.effective_user.id
        
        try:
            # Verificar que efectivamente es VIEW_ONLY
            permission_manager = get_permission_manager(context)
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)

                if admin_info:
                    permission_group = admin_info.get('permission_group', 'Unknown')
                    print(f"🔍 DEBUG: User {user_id} has permission group: {permission_group}")
                    
                    # Solo verificar para VIEW_ONLY, pero continuar para otros si necesario
                    if permission_group != 'VIEW_ONLY':
                        print(f"⚠️ DEBUG: User {user_id} is not VIEW_ONLY ({permission_group}), but continuing...")
                        # NO retornar aquí - continuar mostrando panel básico
                else:
                    print(f"⚠️ DEBUG: No admin_info found for user {user_id}")
            else:
                print(f"⚠️ DEBUG: No permission_manager available")
            
            # Obtener estadísticas básicas
            basic_stats = {
                'total_today': 0,
                'active_windows': 0,
                'system_health': 'Operational'
            }
            
            type_details = []
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = self.get_giveaway_system(giveaway_type)
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Verificar ventana de participación
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    basic_stats['active_windows'] += 1
                
                basic_stats['total_today'] += today_count
                
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                type_details.append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
            admin_name = "VIEW_ONLY User"
            permission_level = "VIEW_ONLY"
            admin_info = permission_manager.get_admin_info(user_id)
            # Obtener nombre del admin
            if permission_manager and admin_info:
                admin_name = admin_info.get('name', 'VIEW_ONLY User')
                permission_level = admin_info.get('permission_group', 'VIEW_ONLY')
            
            print(f"🔍 DEBUG: Showing panel for {admin_name} ({permission_level})")
            
            message = f"""📊 <b>VIEW_ONLY DASHBOARD</b>
    🔒 <b>Access Level:</b> VIEW_ONLY
    👤 <b>Admin:</b> {admin_name}

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{basic_stats['total_today']}</b>
    ├─ Active participation windows: <b>{basic_stats['active_windows']}/{len(type_details)}</b>
    ├─ System status: <b>✅ {basic_stats['system_health']}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Giveaway Status:</b>"""

            for detail in type_details:
                message += f"""

    🎯 <b>{detail['type'].upper()} GIVEAWAY:</b>
    ├─ Prize Amount: <b>${detail['prize']} USD</b>
    ├─ Today's Participants: <b>{detail['participants']}</b>
    ├─ Participation Window: <b>{detail['window_status']}</b>
    ├─ Activity Level: <b>{detail['activity_level']}</b>
    └─ Status: {'✅ Active period' if detail['is_open'] else '⏸️ Outside participation hours'}"""

            message += f"""

    📈 <b>System Insights (Basic):</b>
    ├─ Most active type: <b>{max(type_details, key=lambda x: x['participants'])['type'].title()}</b>
    ├─ Current engagement: <b>{'Strong' if basic_stats['total_today'] > 15 else 'Moderate' if basic_stats['total_today'] > 5 else 'Building'}</b>
    └─ System load: <b>{'Normal' if basic_stats['total_today'] < 100 else 'High'}</b>

    💡 <b>Your VIEW_ONLY Permissions:</b>
    ✅ View today's participation statistics
    ✅ Check basic system health status  
    ✅ See participation window status
    ❌ Advanced analytics require PAYMENT_SPECIALIST+ permissions
    ❌ Pending winners require higher access levels

    🔄 Use the buttons below for more information or to refresh data."""

            # Botones corregidos para VIEW_ONLY
            buttons = [
                [
                    InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="view_only_refresh"),
                    InlineKeyboardButton("ℹ️ About Permissions", callback_data="view_only_permissions_info")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY panel direct: {e}")
            await update.message.reply_text("❌ Error loading VIEW_ONLY dashboard")  


# Comandos públicos
async def start_command(integration_instance, config_loader,update, context):
    """🔄 MANTENER IGUAL - Esta función no necesita permisos"""
    # Tu código existente sin cambios
    # global multi_giveaway_integration
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
            giveaway_system = integration_instance.get_giveaway_system(participation_type)
            
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
                # config_loader = ConfigLoader()
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
            
            # 🔄 MODIFIED: Dynamic requirements text based on config
            try:
                
                giveaway_configs = config_loader.get_giveaway_configs()
                
                requirements_text = f"""📋 <b>Requirements by Type:</b>
✅ Active MT5 LIVE account
✅ Be a channel member
💵 <b>Minimum Balances:</b>
   • Daily: ${giveaway_configs['daily']['min_balance']} USD
   • Weekly: ${giveaway_configs['weekly']['min_balance']} USD  
   • Monthly: ${giveaway_configs['monthly']['min_balance']} USD"""
            except:
                requirements_text = """📋 <b>Requirements:</b>
✅ Active Vortex-FX MT5 LIVE account
✅ Minimum balance varies by type
✅ Be a channel member"""
            
            message = f"""🎁 <b>Hello {user.first_name}!</b>

Welcome to the VFX Trading Multi-Giveaway Bot.

🌟 <b>AVAILABLE GIVEAWAYS:</b>

💰 <b>DAILY:</b> $250 USD
⏰ Monday to Friday at 5:00 PM London Time

💰 <b>WEEKLY:</b> $500 USD  
⏰ Every Friday at 5:15 PM London Time

💰 <b>MONTHLY:</b> $2500 USD
⏰ Last Friday of each month at 5:30 PM London Time

{requirements_text}

🎯 <b>Choose which giveaway to participate in:</b>"""
            
            # Create participation buttons for each type
            buttons = []
            
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
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

async def help_command(config_loader, update, context):
    """🔄 MANTENER IGUAL - No necesita permisos específicos"""
    
    try:
        
        bot_config = config_loader.get_bot_config()
        giveaway_configs = config_loader.get_giveaway_configs()
        admin_username = bot_config.get('admin_username', 'admin')
    except:
        admin_username = 'admin'
        giveaway_configs = {
            'daily': {'prize': 250, 'min_balance': 50},
            'weekly': {'prize': 500, 'min_balance': 150}, 
            'monthly': {'prize': 2500, 'min_balance': 300}
        }
    
    help_text = f"""🆘 <b>MULTI-GIVEAWAY RULES</b>

🌟 <b>AVAILABLE GIVEAWAYS:</b>

💰 <b>DAILY GIVEAWAY - ${giveaway_configs['daily']['prize']} USD</b>
⏰ <b>Participation:</b> Monday-Friday, 1:00 AM - 16:50 PM London Time
🎯 <b>Draw:</b> Monday-Friday at 17:00 PM London Time
💵 <b>Min Balance:</b> ${giveaway_configs['daily']['min_balance']} USD

💰 <b>WEEKLY GIVEAWAY - $500 USD</b>
⏰ <b>Participation:</b> Monday 9:00 AM - Friday 16:55 PM London Time
🎯 <b>Draw:</b> Friday at 17:10 PM London Time
💵 <b>Min Balance:</b> ${giveaway_configs['weekly']['min_balance']} USD

💰 <b>MONTHLY GIVEAWAY - $2500 USD</b>
⏰ <b>Participation:</b> Day 1 - Last Friday of month 16:55 PM, London Time
🎯 <b>Draw:</b> Last Friday at 17:15 PM London Time
💵 <b>Min Balance:</b> ${giveaway_configs['monthly']['min_balance']} USD

📋 <b>REQUIREMENTS FOR ALL GIVEAWAYS:</b>
✅ Be a member of this channel
✅ Active Vortex-FX MT5 LIVE account (not demo)
✅ Minimum balance varies by giveaway type (see above)
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
DM administrator: @{admin_username}

⏰ <b>CURRENT LONDON TIME:</b>
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC

🎯 <b>Use /start to participate in any giveaway!</b>"""
    
    await update.message.reply_text(help_text, parse_mode='HTML')

@require_any_permission(
    SystemAction.VIEW_BASIC_STATS,
    SystemAction.VIEW_ADVANCED_STATS
)
async def stats_command(integration_instance,update, context):
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
            combined_stats = integration_instance.get_giveaway_stats()
            # ... código completo existente ...
        else:
            # 🆕 Mostrar solo estadísticas básicas para VIEW_ONLY
            basic_message = f"📊 <b>BASIC STATISTICS</b>\n"
            basic_message += f"🔒 <b>Access Level:</b> {permission_level}\n\n"
            
            total_today = 0
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
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
        combined_stats = integration_instance.get_giveaway_stats()
        
        # Build stats message
        stats_text = f"""📊 <b>MULTI-GIVEAWAY STATISTICS</b>
<i>Accessed by: {admin_name}</i>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participants: <b>{combined_stats['total_participants_all']}</b>
├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
├─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

📊 <b>BY GIVEAWAY TYPE:</b>"""

        for giveaway_type, stats in combined_stats['by_type'].items():
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
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


# Funciones helper de UI
async def show_rules_inline(config_loader,query):
    """Show complete rules inline when requested from button"""
    try:
        # Use existing help content but format for inline display
        try:
            # config_loader = ConfigLoader()
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

async def debug_directories(config_loader):
    """🔍 Verificar directorios del sistema"""
    try:
        # config_loader = ConfigLoader()
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