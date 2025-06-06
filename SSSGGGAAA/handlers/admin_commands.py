from utils.admin_permission import SystemAction
import handlers.payment_handler as payment_handler
from utils.admin_permission import require_draw_permission_with_time_check, require_permission, require_any_permission, get_permission_manager
import logging
from utils.config_loader import ConfigLoader
import os
import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update


# 🎯 COMANDOS ADMIN POR TIPO
async def _handle_manual_giveaway(integration_instance, update, context, giveaway_type):
        """🆕 NEW: Handle manual giveaway for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Send invitation for specific type
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            success = await giveaway_system.send_invitation(giveaway_type)
            
            # Create return button
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if success:
                await update.message.reply_text(
                    f"✅ {giveaway_type.title()} giveaway invitation sent to channel",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    f"❌ Error sending {giveaway_type} invitation",
                    reply_markup=reply_markup
                )
                
        except Exception as e:
            logging.error(f"Error in manual {giveaway_type} giveaway: {e}")
            await update.message.reply_text("❌ Internal error", parse_mode='HTML')

async def _handle_manual_sorteo(integration_instance, update, context, giveaway_type):
        """🆕 NEW: Handle manual draw for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Execute manual draw for specific type
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            await giveaway_system.run_giveaway(giveaway_type)
            
            # Check result and create return button
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            pending_count = len(pending_winners)
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if pending_count > 0:
                winner = pending_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    winner_display = f"@{username}"
                    command_reference = f"@{username}"
                else:
                    winner_display = f"{first_name} (ID: {winner['telegram_id']})"
                    command_reference = winner['telegram_id']
                
                prize = giveaway_system.get_prize_amount(giveaway_type)
                response_message = f"""✅ <b>{giveaway_type.title()} draw executed successfully</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
🎯 <b>Type:</b> {giveaway_type.upper()}
⏳ <b>Pending winners:</b> {pending_count}

📬 <b>Next steps:</b>
1️⃣ Check your private chat for complete details
2️⃣ Transfer to MT5 account: {winner['mt5_account']}
3️⃣ Use `/admin_confirm_payment_{giveaway_type} {command_reference}` to confirm

💡 Use `/admin_pending_{giveaway_type}` for complete details"""
                    
                await update.message.reply_text(response_message, parse_mode='HTML', reply_markup=reply_markup)
            else:
                await update.message.reply_text(
                    f"✅ {giveaway_type.title()} draw executed - No eligible participants today",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            
        except Exception as e:
            logging.error(f"Error in manual {giveaway_type} draw: {e}")
            await update.message.reply_text("❌ Internal error", parse_mode='HTML')

async def _handle_stats_command(integration_instance, update, context, giveaway_type):
        """🆕 NEW: Handle stats command for specific type"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            
            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = f"""📊 <b>{giveaway_type.upper()} GIVEAWAY STATISTICS</b>

👥 <b>Today's participants:</b> {stats.get('today_participants', 0)}
📈 <b>Total participants:</b> {stats.get('total_participants', 0)}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}
💰 <b>Money distributed:</b> ${stats.get('total_prize_distributed', 0)}
⏳ <b>Pending winners:</b> {pending_count}

⏰ Next draw: Check schedule

<i>Updated: {stats.get('timestamp', 'N/A')}</i>"""

            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} statistics: {e}")
            await update.message.reply_text("❌ Error getting statistics")

async def _handle_pending_winners(integration_instance, update, context, giveaway_type):
        """🆕 NEW: Handle pending winners for specific type"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get pending winners for specific type
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    f"ℹ️ No pending {giveaway_type} winners", 
                    reply_markup=reply_markup
                )
                return
            
            # Format pending winners list
            pending_list = ""
            buttons = []
            
            for i, winner in enumerate(pending_winners, 1):
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                
                if username:
                    command_identifier = username
                    display_name = f"<b>{first_name}</b> (@{username})"
                else:
                    command_identifier = winner['telegram_id']
                    display_name = f"<b>{first_name}</b> (ID: {winner['telegram_id']})"
                
                pending_list += f"{i}. {display_name}\n"
                pending_list += f"   📊 MT5 Account: <code>{winner['mt5_account']}</code>\n"
                pending_list += f"   💰 Prize: ${winner['prize']} USD\n"
                pending_list += f"   🎯 Type: {giveaway_type.upper()}\n"
                pending_list += f"   📅 Selected: {winner['selected_time']}\n\n"
                
                # Create inline button for each winner
                button_text = f"✅ Confirm payment to {first_name}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add return button
            buttons.append([InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")])
            
            message = f"""📋 <b>{giveaway_type.upper()} PENDING WINNERS</b>

{pending_list}💡 <b>Instructions:</b>
1️⃣ Transfer to the MT5 account
2️⃣ Press the corresponding confirmation button
3️⃣ Bot will announce the winner automatically

⚡ <b>Quick buttons:</b>"""
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error getting {giveaway_type} pending winners: {e}")
            await update.message.reply_text("❌ Error getting pending winners")


# 🌐 COMANDOS ADMIN GENERALES

async def _handle_manual_giveaway_general(integration_instance, update, context):
        """🔄 MODIFIED: General manual giveaway with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Show type selection
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nWhich giveaway invitation do you want to send?"
            
            buttons = []
            for giveaway_type in integration_instance.available_types:
                prize = integration_instance.giveaway_systems[giveaway_type].get_prize_amount()
                button_text = f"📢 {giveaway_type.title()} (${prize})"
                callback_data = f"panel_send_invitation_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="panel_refresh")])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in general manual giveaway: {e}")
            await update.message.reply_text("❌ Internal error")

async def _handle_manual_sorteo_general(integration_instance, update, context):
        """🔄 MODIFIED: General manual draw with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Show type selection
            message = "🎲 <b>SELECT GIVEAWAY TYPE FOR DRAW</b>\n\nWhich giveaway draw do you want to execute?"
            
            buttons = []
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                prize = giveaway_system.get_prize_amount()
                participants = giveaway_system._get_period_participants_count()
                button_text = f"🎲 {giveaway_type.title()} (${prize} - {participants} participants)"
                callback_data = f"panel_run_giveaway_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="panel_refresh")])
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in general manual draw: {e}")
            await update.message.reply_text("❌ Internal error")

async def _handle_stats_command_general(integration_instance, update, context):
        """🔄 MODIFIED: General stats with type selection"""
        try:
            user_id = update.effective_user.id
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can view statistics")
                return
            
            # Show combined stats for all types
            all_stats = {}
            total_participants = 0
            total_winners = 0
            total_distributed = 0
            total_pending = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                all_stats[giveaway_type] = {
                    'today_participants': stats.get('today_participants', 0),
                    'total_participants': stats.get('total_participants', 0),
                    'total_winners': stats.get('total_winners', 0),
                    'total_distributed': stats.get('total_prize_distributed', 0),
                    'pending': pending_count
                }
                
                total_participants += stats.get('total_participants', 0)
                total_winners += stats.get('total_winners', 0)
                total_distributed += stats.get('total_prize_distributed', 0)
                total_pending += pending_count
            
            message = f"""📊 <b>MULTI-GIVEAWAY STATISTICS</b>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participants: <b>{total_participants}</b>
├─ Total winners: <b>{total_winners}</b>
├─ Money distributed: <b>${total_distributed}</b>
└─ Pending winners: <b>{total_pending}</b>

📋 <b>BY TYPE:</b>"""

            for giveaway_type, stats in all_stats.items():
                prize = integration_instance.giveaway_systems[giveaway_type].get_prize_amount()
                message += f"""

🎯 <b>{giveaway_type.upper()} (${prize}):</b>
├─ Today: {stats['today_participants']} participants
├─ Total: {stats['total_participants']} participants
├─ Winners: {stats['total_winners']}
├─ Distributed: ${stats['total_distributed']}
└─ Pending: {stats['pending']}"""

            keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing general statistics: {e}")
            await update.message.reply_text("❌ Error getting statistics")

async def _handle_pending_winners_general(integration_instance, update, context):
        """🔄 MODIFIED: General pending winners from all types"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get pending winners from all types
            all_pending = {}
            total_pending = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                pending = giveaway_system.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
                    total_pending += len(pending)
            
            if total_pending == 0:
                keyboard = [[InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("ℹ️ No pending winners in any giveaway type", reply_markup=reply_markup)
                return
            
            # Format message with all pending winners
            message = f"📋 <b>ALL PENDING WINNERS ({total_pending})</b>\n\n"
            buttons = []
            
            for giveaway_type, pending_winners in all_pending.items():
                message += f"🎯 <b>{giveaway_type.upper()} GIVEAWAY:</b>\n"
                
                for i, winner in enumerate(pending_winners, 1):
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    
                    if username:
                        command_identifier = username
                        display_name = f"<b>{first_name}</b> (@{username})"
                    else:
                        command_identifier = winner['telegram_id']
                        display_name = f"<b>{first_name}</b> (ID: {winner['telegram_id']})"
                    
                    message += f"{i}. {display_name}\n"
                    message += f"   📊 MT5: <code>{winner['mt5_account']}</code>\n"
                    message += f"   💰 Prize: ${winner['prize']} USD\n\n"
                    
                    # Create button for each winner
                    button_text = f"✅ Confirm {giveaway_type} - {first_name}"
                    callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Add navigation buttons
            buttons.extend([
                [InlineKeyboardButton("📊 View by type", callback_data="panel_pending_by_type")],
                [InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error getting all pending winners: {e}")
            await update.message.reply_text("❌ Error getting pending winners")



# 📊 COMANDOS ANALYTICS
async def _handle_admin_analytics_command(integration_instance, update, context):
        """🔄 MODIFIED: Enhanced analytics command with type selection"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check if specific type requested
            if len(context.args) > 0:
                requested_type = context.args[0].lower()
                if requested_type in integration_instance.available_types:
                    await integration_instance._show_analytics_for_type(update, requested_type)
                    return
            
            # Show analytics menu
            message = "📈 <b>ANALYTICS MENU</b>\n\nSelect which analytics to view:"
            
            buttons = []
            for giveaway_type in integration_instance.available_types:
                button_text = f"📊 {giveaway_type.title()} Analytics"
                callback_data = f"analytics_{giveaway_type}_30"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.extend([
                [InlineKeyboardButton("📈 Cross-type comparison", callback_data="analytics_cross_type")],
                [InlineKeyboardButton("🌟 Combined analytics", callback_data="analytics_combined")],
                [InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]
            ])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in analytics command: {e}")
            await update.message.reply_text("❌ Error loading analytics")

async def _handle_admin_analytics_all_command(integration_instance, update, context):
        """🆕 NEW: Analytics for all types combined"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get analytics for all types
            days_back = 30
            if context.args and len(context.args) > 0:
                try:
                    days_back = int(context.args[0])
                    days_back = max(1, min(days_back, 365))  # Limit between 1-365 days
                except ValueError:
                    days_back = 30
            
            combined_analytics = await integration_instance._get_combined_analytics(days_back)
            
            message = f"""📈 <b>COMBINED ANALYTICS ({days_back} days)</b>

🌟 <b>GLOBAL OVERVIEW:</b>
├─ Total participants: <b>{combined_analytics['total_participants']}</b>
├─ Unique users: <b>{combined_analytics['unique_users']}</b>
├─ Total winners: <b>{combined_analytics['total_winners']}</b>
├─ Money distributed: <b>${combined_analytics['total_distributed']}</b>
└─ Active days: <b>{combined_analytics['active_days']}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, data in combined_analytics['by_type'].items():
                message += f"""
🎯 <b>{giveaway_type.upper()}:</b>
├─ Participants: {data['participants']}
├─ Winners: {data['winners']}
├─ Distributed: ${data['distributed']}
└─ Avg/day: {data['avg_per_day']}"""

            message += f"\n\n💡 Use `/admin_analytics <type> <days>` for specific analytics"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in combined analytics: {e}")
            await update.message.reply_text("❌ Error getting combined analytics")

async def _handle_admin_user_stats_command(integration_instance, update, context):
        """🔄 MODIFIED: Enhanced user stats with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check parameters
            if not context.args or len(context.args) != 1:
                await update.message.reply_text(
                    "❌ <b>Incorrect usage</b>\n\n<b>Format:</b> <code>/admin_user_stats &lt;telegram_id&gt;</code>\n\n<b>Example:</b> <code>/admin_user_stats 123456789</code>",
                    parse_mode='HTML'
                )
                return
            
            target_user_id = context.args[0].strip()
            
            # Get multi-type user statistics
            multi_stats = await integration_instance._get_user_multi_type_stats(target_user_id)
            
            if not multi_stats or not any(stats['total_participations'] > 0 for stats in multi_stats['by_type'].values()):
                await update.message.reply_text(
                    f"❌ <b>User not found</b>\n\nNo participation found for ID: <code>{target_user_id}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Format multi-type message
            combined = multi_stats['combined']
            message = f"""👤 <b>MULTI-TYPE USER STATISTICS</b>

🆔 <b>Telegram ID:</b> <code>{target_user_id}</code>

🌟 <b>COMBINED TOTALS:</b>
├─ Total participations: <b>{combined['total_participations_all']}</b>
├─ Total wins: <b>{combined['total_wins_all']}</b>
├─ Total prizes: <b>${combined['total_prize_won_all']}</b>
├─ Unique accounts: <b>{combined['unique_accounts_all']}</b>
└─ Active types: <b>{len(combined['active_types'])}</b>

📊 <b>BY GIVEAWAY TYPE:</b>"""

            for giveaway_type in combined['active_types']:
                type_stats = multi_stats['by_type'][giveaway_type]
                message += f"""
🎯 <b>{giveaway_type.upper()}:</b>
├─ Participations: {type_stats['total_participations']}
├─ Wins: {type_stats['total_wins']} ({type_stats['win_rate']}%)
├─ Prizes won: ${type_stats['total_prize_won']}
└─ Accounts used: {type_stats['unique_accounts']}"""

            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in user stats command: {e}")
            await update.message.reply_text("❌ Error getting user statistics")

async def _handle_admin_top_users_command(integration_instance, update, context):
        """🔄 MODIFIED: Top users with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Parse parameters
            limit = 10
            giveaway_type = None
            
            if context.args:
                if len(context.args) >= 1:
                    try:
                        limit = int(context.args[0])
                        limit = max(1, min(limit, 50))  # Limit between 1-50
                    except ValueError:
                        if context.args[0].lower() in integration_instance.available_types:
                            giveaway_type = context.args[0].lower()
                
                if len(context.args) >= 2:
                    if context.args[1].lower() in integration_instance.available_types:
                        giveaway_type = context.args[1].lower()
                    else:
                        try:
                            limit = int(context.args[1])
                            limit = max(1, min(limit, 50))
                        except ValueError:
                            pass
            
            if giveaway_type:
                # Show top users for specific type
                await integration_instance._show_top_users_for_type(update, giveaway_type, limit)
            else:
                # Show combined top users menu
                await integration_instance._show_top_users_menu(update, limit)
                
        except Exception as e:
            logging.error(f"Error in top users command: {e}")
            await update.message.reply_text("❌ Error getting top users")

async def _handle_admin_account_report_command(integration_instance, update, context):
        """🔄 MODIFIED: Account report with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Check if specific type requested
            giveaway_type = None
            if context.args and len(context.args) > 0:
                if context.args[0].lower() in integration_instance.available_types:
                    giveaway_type = context.args[0].lower()
            
            if giveaway_type:
                await integration_instance._show_account_report_for_type(update, giveaway_type)
            else:
                await integration_instance._show_account_report_menu(update)
                
        except Exception as e:
            logging.error(f"Error in account report command: {e}")
            await update.message.reply_text("❌ Error getting account report")

async def _handle_admin_revenue_analysis_command(integration_instance, update, context):
        """🔄 MODIFIED: Revenue analysis with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Get combined revenue analysis
            revenue_analysis = await integration_instance._get_combined_revenue_analysis()
            
            message = f"""💰 <b>MULTI-TYPE REVENUE ANALYSIS</b>

🌟 <b>COMBINED TOTALS:</b>
├─ Total distributed: <b>${revenue_analysis['total_distributed_all']}</b>
├─ Total winners: <b>{revenue_analysis['total_winners_all']}</b>
├─ Total participants: <b>{revenue_analysis['total_participants_all']}</b>
├─ Average per winner: <b>${revenue_analysis['avg_per_winner']:.2f}</b>
└─ Cost per participant: <b>${revenue_analysis['cost_per_participant']:.2f}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, data in revenue_analysis['by_type'].items():
                message += f"""
🎯 <b>{giveaway_type.upper()} (${data['prize']}):</b>
├─ Distributed: ${data['distributed']}
├─ Winners: {data['winners']}
├─ ROI ratio: {data['roi_ratio']:.2f}%"""

            message += f"\n\n📈 <b>Efficiency metrics calculated across all giveaway types</b>"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in revenue analysis: {e}")
            await update.message.reply_text("❌ Error getting revenue analysis")

async def _handle_admin_backup_command(integration_instance, update, context):
        """🔄 MODIFIED: Backup command with multi-type support"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Create backups for all types
            backup_results = {}
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                backup_result = giveaway_system.backup_history_file(giveaway_type)
                backup_results[giveaway_type] = backup_result
            
            # Format results
            message = "💾 <b>MULTI-TYPE BACKUP RESULTS</b>\n\n"
            
            successful_backups = []
            failed_backups = []
            
            for giveaway_type, result in backup_results.items():
                if result:
                    successful_backups.append(giveaway_type)
                    message += f"✅ {giveaway_type.title()}: Backup created\n"
                else:
                    failed_backups.append(giveaway_type)
                    message += f"❌ {giveaway_type.title()}: Backup failed\n"
            
            message += f"\n📊 <b>Summary:</b> {len(successful_backups)} successful, {len(failed_backups)} failed"
            
            if successful_backups:
                message += f"\n\n💡 Backup files saved on server with timestamp"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in backup command: {e}")
            await update.message.reply_text("❌ Error creating backups")

    # ================== DEBUG AND MAINTENANCE ==================


# 🔍 COMANDOS DEBUG
async def _handle_debug_pending_system(integration_instance, update, context):
        """🔄 MODIFIED: Debug pending system for all types"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            message = "🔍 <b>DEBUG PENDING WINNERS SYSTEM</b>\n\n"
            
            total_pending = 0
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                total_pending += pending_count
                
                message += f"🎯 <b>{giveaway_type.upper()}:</b> {pending_count} pending\n"
                
                # Execute debug for each type
                debug_result = giveaway_system.debug_participant_cleanup(giveaway_type)
                if debug_result:
                    message += f"   📊 Current: {debug_result['current_participants']}\n"
                    message += f"   📜 History: {debug_result['total_history']}\n\n"
            
            message += f"📊 <b>Total pending across all types:</b> {total_pending}\n"
            message += f"📄 Check console for detailed debug output"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in debug pending system: {e}")
            await update.message.reply_text("❌ Error in debug system")

async def _handle_debug_all_systems(integration_instance, update, context):
        """🆕 NEW: Debug all giveaway systems"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            message = "🔧 <b>COMPLETE SYSTEM DEBUG</b>\n\n"
            
            # Check each giveaway system
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                
                # Basic health check
                try:
                    stats = giveaway_system.get_stats(giveaway_type)
                    pending = giveaway_system.get_pending_winners(giveaway_type)
                    prize = giveaway_system.get_prize_amount(giveaway_type)
                    
                    message += f"🎯 <b>{giveaway_type.upper()} (${prize}):</b>\n"
                    message += f"   ✅ System operational\n"
                    message += f"   👥 Today: {stats.get('today_participants', 0)}\n"
                    message += f"   ⏳ Pending: {len(pending)}\n"
                    message += f"   🏆 Total winners: {stats.get('total_winners', 0)}\n\n"
                    
                except Exception as e:
                    message += f"🎯 <b>{giveaway_type.upper()}:</b>\n"
                    message += f"   ❌ System error: {str(e)[:50]}...\n\n"
            
            # Configuration check
            try:
                config_status = "✅ Configuration loaded"
                timezone_info = integration_instance.config_loader.get_timezone()
                message += f"⚙️ <b>Configuration:</b> {config_status}\n"
                message += f"🌍 <b>Timezone:</b> {timezone_info}\n"
            except Exception as e:
                message += f"⚙️ <b>Configuration:</b> ❌ Error: {str(e)[:30]}...\n"
            
            message += f"\n🔍 Detailed logs available in console"
            
            keyboard = [[InlineKeyboardButton("🏠 Back to panel", callback_data="panel_refresh")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in debug all systems: {e}")
            await update.message.reply_text("❌ Error in system debug")


# 💳 COMANDOS CONFIRMACIÓN (desde test_botTTT.py)
@require_permission(SystemAction.CONFIRM_DAILY_PAYMENTS)
async def admin_confirm_daily_payment(self,update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago daily"""
        await self.admin_confirm_payment_universal(update, context, 'daily')

@require_permission(SystemAction.CONFIRM_WEEKLY_PAYMENTS)
async def admin_confirm_weekly_payment(self,update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago weekly"""
        await self.admin_confirm_payment_universal(update, context, 'weekly')

@require_permission(SystemAction.CONFIRM_MONTHLY_PAYMENTS)
async def admin_confirm_monthly_payment(self, update, context):
        """🎯 COMANDO ESPECÍFICO: Confirmar pago monthly"""
        await self.admin_confirm_payment_universal(update, context, 'monthly')

@require_any_permission(
        SystemAction.CONFIRM_DAILY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
async def admin_pending_daily(self, update, context):
        """📋 VER PENDIENTES: Daily winners"""
        await self.admin_view_pending_universal(update, context, 'daily')

@require_any_permission(
        SystemAction.CONFIRM_WEEKLY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
async def admin_pending_weekly(self, update, context):
        """📋 VER PENDIENTES: Weekly winners"""
        await self.admin_view_pending_universal(update, context, 'weekly')

@require_any_permission(
        SystemAction.CONFIRM_MONTHLY_PAYMENTS,
        SystemAction.VIEW_ALL_PENDING_WINNERS
    )
async def admin_pending_monthly(self, update, context):
        """📋 VER PENDIENTES: Monthly winners"""
        await self.admin_view_pending_universal(update, context, 'monthly')

    # ======================================================================
async def admin_pending_winners(self, update, context):
        """🚨 CRÍTICO: Comando para ver ganadores pendientes - AGREGAR a ga_test_bot.py"""
        user_id = update.effective_user.id

        # 🆕 AGREGAR: Verificación de permisos al INICIO
        permission_manager = get_permission_manager(context)
        if not permission_manager:
            await update.message.reply_text("❌ Permission system not initialized")
            return
        
        # 🆕 VERIFICAR permisos para ver ganadores pendientes
        if not permission_manager.has_permission(user_id, SystemAction.VIEW_ALL_PENDING_WINNERS):
            admin_info = permission_manager.get_admin_info(user_id)
            await update.message.reply_text(
                f"❌ <b>Access Denied</b>\n\n"
                f"Required: <code>{SystemAction.VIEW_ALL_PENDING_WINNERS.value}</code>\n"
                f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
                parse_mode='HTML'
            )
            return
        
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
                giveaway_system = self.get_giveaway_system(giveaway_type)
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
                prize = self.get_giveaway_system(giveaway_type).get_prize_amount(giveaway_type)
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

async def admin_confirm_payment(self, update, context):
        """🚨 CRÍTICO: Comando para confirmar pagos - VERSIÓN CORREGIDA ASYNC"""
        user_id = update.effective_user.id

        # 🆕 AGREGAR: Verificación de permisos al INICIO de la función
        permission_manager = get_permission_manager(context)
        if not permission_manager:
            await update.message.reply_text("❌ Permission system not initialized")
            return
        
        # 🆕 VERIFICAR si tiene ALGÚN permiso de confirmación
        has_confirm_permission = any([
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_DAILY_PAYMENTS),
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_WEEKLY_PAYMENTS),
            permission_manager.has_permission(user_id, SystemAction.CONFIRM_MONTHLY_PAYMENTS)
        ])
        
        if not has_confirm_permission:
            admin_info = permission_manager.get_admin_info(user_id)
            await update.message.reply_text(
                f"❌ <b>Access Denied</b>\n\n"
                f"Required: Payment confirmation permissions\n"
                f"Your access level: <code>{admin_info.get('permission_group', 'None') if admin_info else 'Not registered'}</code>",
                parse_mode='HTML'
            )
            return
        
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
                    "• <code>/admin_confirm_payment 123456</code>\n"
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
                giveaway_system = self.get_giveaway_system(giveaway_type)
                
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
                    # ✅ CORREGIDO: Llamada asíncrona correcta
                    success, message = await giveaway_system.confirm_payment_and_announce(
                        winner_found, user_id, giveaway_type
                    )
                    
                    if success:
                        confirmed = True
                        prize = giveaway_system.get_prize_amount(giveaway_type)
                        confirmation_message = f"✅ <b>{giveaway_type.title()} payment confirmed successfully</b>\n\n" \
                                            f"🎯 Winner: {winner.get('first_name', 'Unknown')}\n" \
                                            f"💰 Prize: ${prize} USD\n" \
                                            f"📊 Vortex-FX account: {winner['mt5_account']}\n\n" \
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


# From test_botTTT.py

# Comandos admin específicos por tipo
@require_permission(SystemAction.SEND_DAILY_INVITATION)
async def admin_send_daily_invitation(update, context, integration):
    """🆕 NUEVO: Enviar invitación diaria (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Daily invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('daily')
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
async def admin_send_weekly_invitation(update, context, integration):
    """🆕 NUEVO: Enviar invitación semanal (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Weekly invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('weekly')
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
async def admin_send_monthly_invitation(update, context, integration):
    """🆕 NUEVO: Enviar invitación mensual (CON PERMISOS)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Monthly invitation authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('monthly')
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
async def admin_run_daily_draw(update, context, integration):
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
    
    admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Daily draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('daily')
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
            await payment_handler.notify_payment_admins_new_winner(integration,context, winner, 'daily', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_DAILY_DRAW, f"Daily draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Daily draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_DAILY_DRAW, "Daily draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in daily draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_draw_permission_with_time_check('weekly')
async def admin_run_weekly_draw(update, context, integration):
    """🆕 NUEVO: Ejecutar sorteo semanal (CON PERMISOS Y VERIFICACIÓN HORARIA)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Weekly draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('weekly')
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
            await payment_handler.notify_payment_admins_new_winner(integration, context, winner, 'weekly', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_WEEKLY_DRAW, f"Weekly draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Weekly draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_WEEKLY_DRAW, "Weekly draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in weekly draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")

@require_draw_permission_with_time_check('monthly')
async def admin_run_monthly_draw(update, context, integration):
    """🆕 NUEVO: Ejecutar sorteo mensual (CON PERMISOS Y VERIFICACIÓN HORARIA)"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Monthly draw authorized for: {admin_name} ({user_id})")
    
    try:
        giveaway_system = integration.get_giveaway_system('monthly')
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
            await payment_handler.notify_payment_admins_new_winner(integration, context, winner, 'monthly', admin_name)
            
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, f"Monthly draw executed - Winner: {winner_display}")
        else:
            await update.message.reply_text("✅ Monthly draw executed - No eligible participants")
            permission_manager.log_action(user_id, SystemAction.EXECUTE_MONTHLY_DRAW, "Monthly draw executed - No participants")
        
    except Exception as e:
        logging.error(f"Error in monthly draw: {e}")
        await update.message.reply_text(f"❌ Error: {e}")



# Comandos de sistema y debug
@require_permission(SystemAction.HEALTH_CHECK)
async def health_check_command(update, context, integration):
    """🔄 MODIFICADA: Health check con permisos"""
    user_id = update.effective_user.id
    permission_manager = get_permission_manager(context)
    admin_info = permission_manager.get_admin_info(user_id)
    admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
    
    print(f"✅ Health check authorized for: {admin_name} ({user_id})")
    
    try:
        # Run comprehensive health check
        health_report = integration.verify_all_systems_health()
        
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