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

# ==================== BOT COMMANDS ====================

async def start_command(update, context):
    """🔄 MODIFIED: Enhanced start command with multi-type participation detection"""

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
    """🔄 MODIFIED: Enhanced help with multi-type information"""
    
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

# ==================== ADMIN COMMANDS ====================

async def admin_send_giveaway(update, context):
    """🔄 MODIFIED: Admin giveaway command with type selection"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        print(f"🔍 Admin command executed by user: {user_id}")
        print(f"🔍 Attempting to send to channel: {channel_id}")
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        print(f"🔍 User status in channel: {member.status}")
        
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        print("✅ User verified as administrator")
        
        # Check if specific type requested
        requested_type = None
        if context.args and len(context.args) > 0:
            arg_type = context.args[0].lower()
            if arg_type in ['daily', 'weekly', 'monthly']:
                requested_type = arg_type
        
        if requested_type:
            # Send specific type invitation
            print(f"🔍 Sending {requested_type} invitation...")
            giveaway_system = multi_giveaway_integration.get_giveaway_system(requested_type)
            success = await giveaway_system.send_invitation(requested_type)
            
            if success:
                await update.message.reply_text(f"✅ {requested_type.title()} giveaway invitation sent to channel")
                print("✅ Specific invitation sent successfully")
            else:
                await update.message.reply_text(f"❌ Error sending {requested_type} invitation")
                print("❌ Error sending specific invitation")
        else:
            # Show type selection
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nWhich giveaway invitation do you want to send?"
            
            buttons = []
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                # Check if window is open
                is_open = giveaway_system.is_participation_window_open(giveaway_type)
                status = "🟢 OPEN" if is_open else "🔴 CLOSED"
                
                button_text = f"📢 {giveaway_type.title()} (${prize}) - {status}"
                callback_data = f"admin_send_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("📢 Send ALL invitations", callback_data="admin_send_all")])
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Error in admin command: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def admin_run_giveaway(update, context):
    """🔄 MODIFIED: Admin draw command with type selection"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        # Check if specific type requested
        requested_type = None
        if context.args and len(context.args) > 0:
            arg_type = context.args[0].lower()
            if arg_type in ['daily', 'weekly', 'monthly']:
                requested_type = arg_type
        
        if requested_type:
            # Execute specific type draw
            giveaway_system = multi_giveaway_integration.get_giveaway_system(requested_type)
            await giveaway_system.run_giveaway(requested_type)
            
            # Check results
            pending_winners = giveaway_system.get_pending_winners(requested_type)
            pending_count = len(pending_winners)
            
            if pending_count > 0:
                winner = pending_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                prize = giveaway_system.get_prize_amount(requested_type)
                
                response_message = f"""✅ <b>{requested_type.title()} draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
🎯 <b>Type:</b> {requested_type.upper()}

💡 Use `/admin_pending_{requested_type}` for details
💡 Use `/admin_panel` for full management"""
                
                await update.message.reply_text(response_message, parse_mode='HTML')
            else:
                await update.message.reply_text(f"✅ {requested_type.title()} draw executed - No eligible participants")
        else:
            # Show type selection for draw
            message = "🎲 <b>SELECT GIVEAWAY TYPE FOR DRAW</b>\n\nWhich giveaway draw do you want to execute?"
            
            buttons = []
            for giveaway_type in ['daily', 'weekly', 'monthly']:
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                participants = giveaway_system._get_period_participants_count(giveaway_type)
                
                button_text = f"🎲 {giveaway_type.title()} (${prize} - {participants} participants)"
                callback_data = f"admin_draw_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("🎲 Execute ALL draws", callback_data="admin_draw_all")])
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="admin_cancel")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
    except Exception as e:
        logging.error(f"Error in admin draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

async def stats_command(update, context):
    """🔄 MODIFIED: Enhanced stats with multi-type support"""
    try:
        user_id = update.effective_user.id
        
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can view statistics")
            return
        
        # Get combined stats
        combined_stats = multi_giveaway_integration.get_giveaway_stats()
        
        # Build stats message
        stats_text = f"""📊 <b>MULTI-GIVEAWAY STATISTICS</b>

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

        stats_text += f"\n\n💡 Use `/admin_panel` for advanced management"

        await update.message.reply_text(stats_text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error showing stats: {e}")
        await update.message.reply_text("❌ Error getting statistics")

# ==================== CALLBACK HANDLERS ====================

async def handle_admin_callbacks(update, context):
    """🆕 NEW: Handle admin action callbacks"""
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_id = query.from_user.id
        
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await query.edit_message_text("❌ Only administrators can use this function")
            return
        
        # Handle admin send invitations
        if callback_data.startswith("admin_send_"):
            giveaway_type = callback_data.replace("admin_send_", "")
            
            if giveaway_type == "all":
                # Send all invitations
                results = {}
                for gt in ['daily', 'weekly', 'monthly']:
                    giveaway_system = multi_giveaway_integration.get_giveaway_system(gt)
                    success = await giveaway_system.send_invitation(gt)
                    results[gt] = success
                
                successful = [gt for gt, success in results.items() if success]
                failed = [gt for gt, success in results.items() if not success]
                
                message = f"📢 <b>BULK INVITATION RESULTS</b>\n\n"
                message += f"✅ Successful: {', '.join(successful) if successful else 'None'}\n"
                message += f"❌ Failed: {', '.join(failed) if failed else 'None'}\n"
                message += f"\n📊 Summary: {len(successful)}/{len(results)} successful"
                
                await query.edit_message_text(message, parse_mode='HTML')
                
            elif giveaway_type in ['daily', 'weekly', 'monthly']:
                # Send specific type invitation
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                success = await giveaway_system.send_invitation(giveaway_type)
                
                if success:
                    message = f"✅ <b>{giveaway_type.title()} invitation sent</b>\n\nInvitation sent to channel successfully."
                else:
                    message = f"❌ <b>Error sending {giveaway_type} invitation</b>\n\nCould not send invitation to channel."
                
                await query.edit_message_text(message, parse_mode='HTML')
        
        # Handle admin draw executions
        elif callback_data.startswith("admin_draw_"):
            giveaway_type = callback_data.replace("admin_draw_", "")
            
            if giveaway_type == "all":
                # Execute all draws
                results = {}
                total_winners = 0
                
                for gt in ['daily', 'weekly', 'monthly']:
                    try:
                        giveaway_system = multi_giveaway_integration.get_giveaway_system(gt)
                        await giveaway_system.run_giveaway(gt)
                        
                        pending_winners = giveaway_system.get_pending_winners(gt)
                        winners_count = len(pending_winners)
                        total_winners += winners_count
                        
                        results[gt] = {
                            'success': True,
                            'winners': winners_count,
                            'winner_name': pending_winners[0].get('first_name', 'Unknown') if pending_winners else None
                        }
                    except Exception as e:
                        results[gt] = {'success': False, 'error': str(e)}
                
                message = f"🎲 <b>BULK DRAW RESULTS</b>\n\n"
                for gt, result in results.items():
                    if result['success']:
                        if result['winners'] > 0:
                            message += f"✅ {gt.title()}: {result['winner_name']} selected\n"
                        else:
                            message += f"✅ {gt.title()}: No eligible participants\n"
                    else:
                        message += f"❌ {gt.title()}: Error occurred\n"
                
                message += f"\n📊 Total new winners: {total_winners}"
                
                await query.edit_message_text(message, parse_mode='HTML')
                
            elif giveaway_type in ['daily', 'weekly', 'monthly']:
                # Execute specific type draw
                giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
                await giveaway_system.run_giveaway(giveaway_type)
                
                pending_winners = giveaway_system.get_pending_winners(giveaway_type)
                pending_count = len(pending_winners)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                if pending_count > 0:
                    winner = pending_winners[0]
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    winner_display = f"@{username}" if username else first_name
                    
                    message = f"""✅ <b>{giveaway_type.title()} draw executed</b>

🎯 <b>Winner:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
⏳ <b>Status:</b> Pending payment confirmation

💡 Check admin panel for details."""
                else:
                    message = f"✅ <b>{giveaway_type.title()} draw executed</b>\n\nNo eligible participants found."
                
                await query.edit_message_text(message, parse_mode='HTML')
        
        # Handle cancel
        elif callback_data == "admin_cancel":
            await query.edit_message_text("❌ Operation cancelled")
        
        else:
            await query.edit_message_text("❌ Unknown action")
            
    except Exception as e:
        logging.error(f"Error in admin callback: {e}")
        await query.edit_message_text("❌ Error processing action")

async def handle_user_callbacks(update, context):
    """🆕 NEW: Handle user callbacks (rules, etc.)"""
    try:
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        if callback_data == "show_rules":
            rules_text = """📋 <b>GIVEAWAY RULES & SCHEDULE</b>

⏰ <b>LONDON TIME SCHEDULE:</b>

🌅 <b>DAILY GIVEAWAY ($250):</b>
• Participation: Mon-Fri, 1:00 AM - 4:50 PM
• Draw: Mon-Fri at 5:00 PM
• Cooldown: 30 days after winning

📅 <b>WEEKLY GIVEAWAY ($500):</b>
• Participation: Mon 9:00 AM - Fri 5:00 PM
• Draw: Friday at 5:15 PM
• Cooldown: 60 days after winning

🗓️ <b>MONTHLY GIVEAWAY ($1000):</b>
• Participation: Day 1 - Last Friday of month
• Draw: Last Friday at 5:30 PM
• Cooldown: 90 days after winning

📋 <b>REQUIREMENTS:</b>
✅ MT5 LIVE account (minimum $100 balance)
✅ Channel membership
✅ One participation per type per period

🔄 You can participate in ALL types simultaneously!

💡 Use /start to participate in any giveaway."""
            
            await query.edit_message_text(rules_text, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in user callback: {e}")
        await query.edit_message_text("❌ Error loading information")

# ==================== DEBUG COMMANDS ====================

async def test_channel_command(update, context):
    """🔄 MODIFIED: Test channel command with config loading"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        print(f"🧪 Testing direct send to channel: {channel_id}")
        
        # Test message
        test_message = """✅ <b>MULTI-GIVEAWAY SYSTEM TEST</b>

🎯 If you see this message, the bot can send to the channel correctly.

🧪 System status: Operational
📡 Connection: Verified

🌟 Available giveaways: Daily, Weekly, Monthly"""
        
        # Direct send test
        sent_message = await context.bot.send_message(
            chat_id=channel_id,
            text=test_message,
            parse_mode='HTML'
        )
        
        await update.message.reply_text(f"✅ Test message sent to channel\nMessage ID: {sent_message.message_id}")
        print("✅ Test message sent successfully")
        
    except Exception as e:
        error_msg = f"Error testing channel: {e}"
        logging.error(error_msg)
        print(f"❌ {error_msg}")
        await update.message.reply_text(f"❌ Error: {e}")

async def get_channel_info_command(update, context):
    """🔄 MODIFIED: Channel info with config loading"""
    user_id = update.effective_user.id
    
    try:
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        # Get channel info
        chat_info = await context.bot.get_chat(channel_id)
        
        info_text = f"""📋 <b>CHANNEL INFORMATION</b>

🆔 <b>Chat ID:</b> <code>{chat_info.id}</code>
📛 <b>Title:</b> {chat_info.title}
🔗 <b>Username:</b> @{chat_info.username if chat_info.username else 'No username'}
📊 <b>Type:</b> {chat_info.type}
👥 <b>Members:</b> {getattr(chat_info, 'member_count', 'N/A')}
🤖 <b>Bot status:</b> {member.status}

🎯 <b>Multi-giveaway system:</b> Active
🌍 <b>Timezone:</b> Europe/London"""
        
        await update.message.reply_text(info_text, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting channel info: {e}")

async def debug_cleanup_command(update, context):
    """🆕 NEW: Debug cleanup for all giveaway types"""
    try:
        user_id = update.effective_user.id
        
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        message = "🔍 <b>MULTI-TYPE CLEANUP DEBUG</b>\n\n"
        
        for giveaway_type in ['daily', 'weekly', 'monthly']:
            giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
            debug_result = giveaway_system.debug_participant_cleanup(giveaway_type)
            
            if debug_result:
                message += f"🎯 <b>{giveaway_type.upper()}:</b>\n"
                message += f"├─ Current participants: {debug_result['current_participants']}\n"
                message += f"├─ Total history: {debug_result['total_history']}\n"
                message += f"└─ Pending winners: {debug_result['pending_winners']}\n\n"
        
        message += "💡 Detailed logs available in console"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        logging.error(f"Error in debug cleanup: {e}")
        await update.message.reply_text("❌ Error executing debug")

async def health_check_command(update, context):
    """🆕 NEW: Complete system health check"""
    try:
        user_id = update.effective_user.id
        
        config_loader = ConfigLoader()
        bot_config = config_loader.get_bot_config()
        channel_id = bot_config['channel_id']
        
        # Verify admin permissions
        member = await context.bot.get_chat_member(channel_id, user_id)
        if member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Only administrators can use this command")
            return
        
        # Run comprehensive health check
        health_report = multi_giveaway_integration.verify_all_systems_health()
        
        message = f"""🏥 <b>SYSTEM HEALTH CHECK</b>

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
        
    except Exception as e:
        logging.error(f"Error in health check: {e}")
        await update.message.reply_text("❌ Error running health check")

# ==================== ENHANCED SCHEDULER SYSTEM ====================

def setup_multi_type_scheduler(multi_giveaway_integration, mode="testing"):
    """
    🆕 NEW: Enhanced scheduler for multi-type giveaways with London time
    """
    scheduler = AsyncIOScheduler(timezone='Europe/London')
    
    # ✅ FUNCTION TO CREATE ASYNC TASKS
    def create_scheduled_task(coroutine_func):
        """Wrapper to execute async functions in scheduler"""
        def wrapper():
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(coroutine_func())
            except RuntimeError:
                try:
                    asyncio.run(coroutine_func())
                except Exception as run_error:
                    logging.error(f"Error executing scheduled task: {run_error}")
            except Exception as e:
                logging.error(f"Error in scheduled task: {e}")
        return wrapper
    
    if mode == "production":
        # ===== PRODUCTION MODE - LONDON TIME =====
        
        print("⏰ Configuring PRODUCTION scheduler with London time...")
        
        # 📢 DAILY INVITATIONS - 1:00 AM Monday to Friday
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_daily_invitation),
            trigger=CronTrigger(day_of_week='mon-fri', hour=1, minute=0),
            id='daily_invitation',
            name='Daily Invitation - 1:00 AM London Time',
            replace_existing=True
        )
        
        # 🎲 DAILY DRAWS - 5:00 PM Monday to Friday
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_daily_draw),
            trigger=CronTrigger(day_of_week='mon-fri', hour=17, minute=0),
            id='daily_draw',
            name='Daily Draw - 5:00 PM London Time',
            replace_existing=True
        )
        
        # 📢 WEEKLY INVITATIONS - 9:00 AM Monday
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_weekly_invitation),
            trigger=CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='weekly_invitation',
            name='Weekly Invitation - Monday 9:00 AM London Time',
            replace_existing=True
        )
        
        # 🎲 WEEKLY DRAWS - 5:15 PM Friday
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_weekly_draw),
            trigger=CronTrigger(day_of_week='fri', hour=17, minute=15),
            id='weekly_draw',
            name='Weekly Draw - Friday 5:15 PM London Time',
            replace_existing=True
        )
        
        # 📢 MONTHLY INVITATIONS - 9:00 AM Day 1 of month
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_monthly_invitation),
            trigger=CronTrigger(day=1, hour=9, minute=0),
            id='monthly_invitation',
            name='Monthly Invitation - Day 1, 9:00 AM London Time',
            replace_existing=True
        )
        
        # 🎲 MONTHLY DRAWS - 5:30 PM Last Friday of month (complex logic required)
        # Note: This needs custom logic to determine last Friday
        # For now, using a weekly check on Fridays to see if it's the last Friday
        scheduler.add_job(
            create_scheduled_task(lambda: check_and_run_monthly_draw(multi_giveaway_integration)),
            trigger=CronTrigger(day_of_week='fri', hour=17, minute=30),
            id='monthly_draw_check',
            name='Monthly Draw Check - Friday 5:30 PM London Time',
            replace_existing=True
        )
        
        # ⚠️ PENDING PAYMENT REMINDERS - 6:00 PM daily
        scheduler.add_job(
            create_scheduled_task(lambda: multi_giveaway_integration.notify_admin_pending_winners()),
            trigger=CronTrigger(hour=18, minute=0),
            id='pending_payment_reminder',
            name='Pending Payment Reminder - 6:00 PM London Time',
            replace_existing=True
        )
        
        # 🏥 SYSTEM HEALTH CHECK - 2:00 AM daily
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.emergency_system_check),
            trigger=CronTrigger(hour=2, minute=0),
            id='system_health_check',
            name='System Health Check - 2:00 AM London Time',
            replace_existing=True
        )
        
        # 🔧 MAINTENANCE ROUTINE - 3:00 AM Sunday
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_maintenance_routine),
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='maintenance_routine',
            name='Maintenance Routine - Sunday 3:00 AM London Time',
            replace_existing=True
        )
        
        logging.info("⏰ PRODUCTION Scheduler configured with London time")
        print("🌍 PRODUCTION Schedule (Europe/London timezone):")
        print("   📢 Daily invitations: Mon-Fri 1:00 AM")
        print("   🎲 Daily draws: Mon-Fri 5:00 PM")
        print("   📢 Weekly invitations: Monday 9:00 AM")
        print("   🎲 Weekly draws: Friday 5:15 PM")
        print("   📢 Monthly invitations: Day 1, 9:00 AM")
        print("   🎲 Monthly draws: Last Friday 5:30 PM")
        print("   ⚠️ Payment reminders: Daily 6:00 PM")
        print("   🏥 Health checks: Daily 2:00 AM")
        print("   🔧 Maintenance: Sunday 3:00 AM")
        
    else:  # mode == "testing"
        # ===== TESTING MODE - FREQUENT EXECUTION =====
        
        print("🧪 Configuring TESTING scheduler...")
        
        # 📢 INVITATIONS - Every 5 minutes alternating types
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_daily_invitation),
            trigger=CronTrigger(minute='*/15'),  # Every 15 minutes
            id='test_daily_invitation',
            name='Test Daily Invitation - Every 15 min',
            replace_existing=True
        )
        
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_weekly_invitation),
            trigger=CronTrigger(minute='5,20,35,50'),  # 5 min offset
            id='test_weekly_invitation',
            name='Test Weekly Invitation - Every 15 min +5',
            replace_existing=True
        )
        
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.send_monthly_invitation),
            trigger=CronTrigger(minute='10,25,40,55'),  # 10 min offset
            id='test_monthly_invitation',
            name='Test Monthly Invitation - Every 15 min +10',
            replace_existing=True
        )
        
        # 🎲 DRAWS - Every 30 minutes alternating types
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_daily_draw),
            trigger=CronTrigger(minute='*/30'),  # Every 30 minutes
            id='test_daily_draw',
            name='Test Daily Draw - Every 30 min',
            replace_existing=True
        )
        
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_weekly_draw),
            trigger=CronTrigger(minute='15,45'),  # 15 min offset
            id='test_weekly_draw',
            name='Test Weekly Draw - Every 30 min +15',
            replace_existing=True
        )
        
        # Monthly every hour
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.run_monthly_draw),
            trigger=CronTrigger(minute='0'),  # Every hour
            id='test_monthly_draw',
            name='Test Monthly Draw - Every hour',
            replace_existing=True
        )
        
        # ⚠️ REMINDERS - Every 10 minutes
        scheduler.add_job(
            create_scheduled_task(lambda: multi_giveaway_integration.notify_admin_pending_winners()),
            trigger=CronTrigger(minute='*/10'),
            id='test_pending_reminder',
            name='Test Pending Reminder - Every 10 min',
            replace_existing=True
        )
        
        # 🏥 HEALTH CHECK - Every 2 hours
        scheduler.add_job(
            create_scheduled_task(multi_giveaway_integration.emergency_system_check),
            trigger=CronTrigger(minute='0', hour='*/2'),
            id='test_health_check',
            name='Test Health Check - Every 2 hours',
            replace_existing=True
        )
        
        logging.info("⏰ TESTING Scheduler configured")
        print("🧪 TESTING Schedule:")
        print("   📢 Daily invitations: Every 15 min")
        print("   📢 Weekly invitations: Every 15 min (+5)")
        print("   📢 Monthly invitations: Every 15 min (+10)")
        print("   🎲 Daily draws: Every 30 min")
        print("   🎲 Weekly draws: Every 30 min (+15)")
        print("   🎲 Monthly draws: Every hour")
        print("   ⚠️ Reminders: Every 10 min")
        print("   🏥 Health checks: Every 2 hours")
    
    scheduler.start()
    return scheduler

async def check_and_run_monthly_draw(multi_giveaway_integration):
    """🆕 NEW: Check if today is last Friday of month and run monthly draw"""
    try:
        from datetime import datetime
        import calendar
        
        now = datetime.now()
        
        # Check if today is Friday
        if now.weekday() != 4:  # Friday = 4
            return
        
        # Get last day of current month
        last_day = calendar.monthrange(now.year, now.month)[1]
        last_date = datetime(now.year, now.month, last_day)
        
        # Find last Friday of month
        days_back = (last_date.weekday() - 4) % 7
        last_friday = last_date - timedelta(days=days_back)
        
        # Check if today is the last Friday
        if now.date() == last_friday.date():
            logging.info("Today is last Friday of month - Running monthly draw")
            await multi_giveaway_integration.run_monthly_draw()
        else:
            logging.info(f"Today is not last Friday (last Friday: {last_friday.date()})")
            
    except Exception as e:
        logging.error(f"Error checking monthly draw date: {e}")

# ==================== MAIN FUNCTION ====================

# Global variable for multi-giveaway integration
multi_giveaway_integration = None

async def main():
    """🔄 MODIFIED: Enhanced main function for multi-type giveaway system"""
    
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
    
    logging.info("Starting Multi-Type Giveaway Bot...")
    
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
    
    # Create MT5 API
    mt5_api = RealMT5API()
    
    # ===== INITIALIZE MULTI-GIVEAWAY SYSTEM =====
    multi_giveaway_integration = MultiGiveawayIntegration(
        application=app,
        mt5_api=mt5_api,
        config_file="config.json"
    )
    
    # ===== ADD COMMAND HANDLERS =====
    
    # 1️⃣ SYSTEM COMMANDS
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # 2️⃣ ADMIN COMMANDS
    app.add_handler(CommandHandler("admin_giveaway", admin_send_giveaway))
    app.add_handler(CommandHandler("admin_sorteo", admin_run_giveaway))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # 3️⃣ DEBUG COMMANDS
    app.add_handler(CommandHandler("test_channel", test_channel_command))
    app.add_handler(CommandHandler("channel_info", get_channel_info_command))
    app.add_handler(CommandHandler("debug_cleanup", debug_cleanup_command))
    app.add_handler(CommandHandler("health_check", health_check_command))
    
    # 4️⃣ CALLBACK HANDLERS
    app.add_handler(CallbackQueryHandler(handle_admin_callbacks, pattern="^admin_"))
    app.add_handler(CallbackQueryHandler(handle_user_callbacks, pattern="^show_"))
    
    logging.info("All command handlers configured")
    
    # ✅ CONFIGURE SCHEDULER
    scheduler_mode = "testing"  # Change to "production" for live deployment
    scheduler = setup_multi_type_scheduler(multi_giveaway_integration, mode=scheduler_mode)
    
    # System information
    print("🚀 Multi-Type Giveaway Bot Started Successfully")
    print(f"📢 Channel configured: {CHANNEL_ID}")
    print(f"👤 Admin configured: {ADMIN_ID} (@{ADMIN_USERNAME})")
    print(f"🤖 Bot token: {BOT_TOKEN[:10]}...")
    print(f"⏰ Scheduler mode: {scheduler_mode.upper()}")
    print("\n🎯 Available Giveaways:")
    
    # Show giveaway info
    for giveaway_type in ['daily', 'weekly', 'monthly']:
        giveaway_system = multi_giveaway_integration.get_giveaway_system(giveaway_type)
        prize = giveaway_system.get_prize_amount(giveaway_type)
        cooldown = giveaway_system.get_cooldown_days(giveaway_type)
        is_open = giveaway_system.is_participation_window_open(giveaway_type)
        status = "🟢 OPEN" if is_open else "🔴 CLOSED"
        print(f"   💰 {giveaway_type.title()}: ${prize} (cooldown: {cooldown}d) - {status}")
    
    print("\n📋 Commands available:")
    print("   👤 USERS:")
    print("      /start - Multi-type giveaway participation")
    print("      /help - Complete rules and schedule")
    print("   🔧 ADMINISTRATORS:")
    print("      /admin_giveaway [type] - Send invitations")
    print("      /admin_sorteo [type] - Execute draws")
    print("      /stats - Multi-type statistics")
    print("      /admin_panel - Complete admin panel")
    print("   🧪 DEBUG:")
    print("      /test_channel - Test channel connection")
    print("      /health_check - System health status")
    print("      /debug_cleanup - Debug cleanup status")
    print("\n✅ Multi-type bot ready for users!")
    
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
            print("\n🛑 Stopping multi-type bot...")
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
            
            # Stop scheduler
            if scheduler.running:
                scheduler.shutdown(wait=False)
                print("✅ Multi-type scheduler stopped")
            
            # Stop bot
            if app.updater.running:
                await app.updater.stop()
            await app.stop()
            await app.shutdown()
            logging.info("Multi-type bot finished correctly")
        except Exception as cleanup_error:
            logging.error(f"Error in cleanup: {cleanup_error}")

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    print("🎯 Multi-Type Giveaway Bot with London Time Scheduler")
    print("=" * 70)
    
    # Verify required files
    required_files = ['ga_manager.py', 'ga_integration.py', 'config_loader.py']
    missing_files = [f for f in required_files if not os.path.exists(f)]
    
    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        print("Make sure you have all giveaway system files")
        exit(1)
    
    print("✅ System files verified")
    
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
    
    print("\n🌍 TIMEZONE: Europe/London")
    print("⏰ SCHEDULER: Multi-type with independent schedules")
    print("🔄 COMPATIBILITY: Backward compatible with single-type bots")
    print("\n📱 COMMANDS TO TEST:")
    print("- /start (multi-type participation)")
    print("- /admin_giveaway (type selection)")
    print("- /admin_panel (unified management)")
    print("- /health_check (system status)")
    print("\nPress Ctrl+C to stop the bot")
    print("=" * 70)
    
    # Run bot
    asyncio.run(main())