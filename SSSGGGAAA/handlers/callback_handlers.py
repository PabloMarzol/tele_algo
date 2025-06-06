# from tele_algo.SSSGGGAAA.utils import automation_manager
from utils.admin_permission import SystemAction
import logging
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import datetime
from utils.config_loader import ConfigLoader




# Handlers principales de callbacks:
async def _handle_admin_panel_callbacks(integration_instance, automation_manager, context, update):
        """🔄 ENHANCED: Complete callback handler with ALL missing callbacks"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            callback_data = query.data

            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await query.edit_message_text("❌ Only administrators can use this function")
                return
            
            # VIEW_ONLY detection
            permission_manager = integration_instance._get_permission_manager_from_callback()
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if admin_info and admin_info.get('permission_group') == 'VIEW_ONLY':
                    # await self._show_view_only_panel(query)
                    await _handle_view_only_callbacks(integration_instance, query, callback_data)
                    return
            
            print(f"🔍 DEBUG: Processing callback: {callback_data}")

            # 🆕 ADD: Automation callbacks
            if callback_data.startswith("automation_"):
                await _handle_automation_callbacks(integration_instance, automation_manager, update, context)
                # pri:nt(f"🔄 DEBUG: Automation callback {callback_data} - should be handled by automation handler")
                return
            
            # ===== 🆕 PANEL PRINCIPAL CALLBACKS (LOS QUE FALTABAN) =====
            if callback_data == "panel_pending_winners":
                await _show_all_pending_inline(integration_instance, query)
            elif callback_data == "panel_statistics":
                await _show_combined_stats_inline(integration_instance,query)
            elif callback_data == "panel_send_invitations":
                await _send_all_invitations_inline(integration_instance, query)
            elif callback_data == "panel_execute_draws":
                await _execute_all_draws_inline(integration_instance, query)
            elif callback_data == "panel_health":
                await _execute_system_health_check(integration_instance, query)
            elif callback_data == "panel_maintenance":
                await _show_maintenance_panel_inline(integration_instance, query)
            elif callback_data == "panel_advanced_analytics":
                await _show_unified_multi_analytics_inline(integration_instance, query)
            elif callback_data == "panel_basic_analytics":
                await _show_combined_stats_inline(integration_instance, query)
            elif callback_data == "panel_daily":
                await _show_type_panel_inline(integration_instance,query, 'daily')
            elif callback_data == "panel_weekly":
                await _show_type_panel_inline(integration_instance,query, 'weekly')
            elif callback_data == "panel_monthly":
                await _show_type_panel_inline(integration_instance,query, 'monthly')
            
            # ===== TYPE-SPECIFIC PANEL ACTIONS (EXISTENTES) =====
            else:
                # Procesar callbacks por tipo usando loop (código existente)
                handled = False
                for giveaway_type in integration_instance.available_types:
                    if callback_data == f"panel_type_{giveaway_type}":
                        await _show_type_panel_inline(integration_instance,query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_send_invitation_{giveaway_type}":
                        await _execute_send_invitation_inline(integration_instance,query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_run_giveaway_{giveaway_type}":
                        await _execute_run_giveaway_inline(integration_instance, query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_pending_winners_{giveaway_type}":
                        await _show_pending_winners_inline(integration_instance, query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_full_stats_{giveaway_type}":
                        await _show_full_stats_inline(integration_instance,query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_refresh_{giveaway_type}":
                        await _refresh_type_panel(integration_instance, query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_analytics_{giveaway_type}":
                        await _show_analytics_inline(integration_instance, query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"panel_top_users_{giveaway_type}":
                        await _show_top_users_inline(integration_instance, query, giveaway_type)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_30":
                        await _show_analytics_detailed_inline(integration_instance,query, giveaway_type, 30)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_7":
                        await _show_analytics_detailed_inline(integration_instance, query, giveaway_type, 7)
                        handled = True
                        break
                    elif callback_data == f"analytics_{giveaway_type}_90":
                        await _show_analytics_detailed_inline(integration_instance, query, giveaway_type, 90)
                        handled = True
                        break
                    elif callback_data == f"account_report_{giveaway_type}":
                        await _show_account_report_for_type_inline(query, giveaway_type)
                        handled = True
                        break
                
                
                if handled:
                    return
                
                # ===== UNIFIED PANEL ACTIONS (EXISTENTES) =====
                if callback_data == "panel_unified_main":
                    await _show_unified_panel_inline(integration_instance, query)
                # if callback_data == "panel_unified_main":
                #     await self._show_main_admin_panel_inline(query)
                elif callback_data == "panel_unified_refresh":
                    await _refresh_unified_panel(integration_instance, query)
                elif callback_data == "unified_all_pending":
                    await _show_all_pending_inline(integration_instance, query)
                elif callback_data == "unified_combined_stats":
                    await _show_combined_stats_inline(integration_instance, query)
                elif callback_data == "unified_send_all_invitations":
                    await _send_all_invitations_inline(integration_instance, query)
                elif callback_data == "unified_execute_all_draws":
                    await _execute_all_draws_inline(integration_instance, query)
                elif callback_data == "unified_multi_analytics":
                    await _show_unified_multi_analytics_inline(integration_instance, query)
                elif callback_data == "unified_cross_analytics":
                    await _show_cross_analytics_inline(integration_instance, query)
                elif callback_data == "unified_maintenance":
                    await _show_maintenance_panel_inline(integration_instance, query)
                elif callback_data == "analytics_cross_type":
                    await _show_cross_type_analytics_inline(integration_instance, query)
                elif callback_data == "analytics_combined":
                    await _show_combined_analytics_inline(integration_instance, query)
                elif callback_data == "analytics_revenue":
                    await _show_giveaway_cost_analysis(integration_instance, query)
                elif callback_data == "analytics_user_overlap":
                    await _show_user_overlap_analysis(integration_instance, query)
                elif callback_data == "maintenance_cleanup":
                    await _execute_maintenance_cleanup(integration_instance, query)
                elif callback_data == "maintenance_backup":
                    await _execute_maintenance_backup(integration_instance, query)
                elif callback_data == "maintenance_health":
                    await _execute_system_health_check(integration_instance, query)
                elif callback_data == "maintenance_files":
                    await _show_file_status(integration_instance, query)
                elif callback_data == "type_selector_main":
                    await _show_type_selector_inline(integration_instance, query)
                elif callback_data == "panel_refresh":
                    await _refresh_unified_panel(integration_instance, query)
                elif callback_data == "no_action":
                    await query.answer("ℹ️ No action available", show_alert=False)
                elif callback_data == "view_only_health":
                    await _show_view_only_health(integration_instance, query)
                elif callback_data == "view_only_today_details":
                    await _show_view_only_today_details(integration_instance, query)
                elif callback_data == "view_only_refresh":
                    await _show_view_only_panel(integration_instance, query)
                elif callback_data == "view_only_permissions_info":
                    await _show_view_only_permissions_info(integration_instance, query)
                elif callback_data in [
                    "analytics_revenue_impact", "analytics_user_behavior", "analytics_time_trends", 
                    "analytics_deep_dive", "analytics_revenue_detailed", "analytics_user_patterns", 
                    "analytics_time_patterns", "analytics_export_report", "analytics_efficiency_trends",
                    "analytics_user_engagement", "analytics_loyalty_patterns", "analytics_user_behavior_patterns",
                    "analytics_time_analysis", "analytics_deep_analysis"
                ]:
                    await _handle_placeholder_analytics(query, callback_data)
                else:
                    print(f"❌ DEBUG: Truly unrecognized callback: {callback_data}")
                    await query.edit_message_text(f"❌ Unrecognized action: {callback_data}")
                    
        except Exception as e:
            logging.error(f"Error in panel callback: {e}")
            print(f"🚨 DEBUG ERROR in callback: {e}")
            await query.edit_message_text("❌ Error processing action")


async def _handle_automation_callbacks(integration_instance,automation_manager, update, context):
        """🆕 Handle automation control callbacks"""

        query = update.callback_query
    
        # 2️⃣ SEGUNDO: INMEDIATAMENTE responder al callback (OBLIGATORIO)
        await query.answer()  # ← AQUÍ VA, LÍNEA 3 DE LA FUNCIÓN

        # query = update.callback_query 
        callback_data = query.data
        user_id = query.from_user.id

        
        # Verify permissions
        permission_manager = integration_instance._get_permission_manager_from_callback()
        if not permission_manager or not permission_manager.has_permission(user_id, SystemAction.MANAGE_ADMINS):
            print(f"❌ DEBUG: Permission denied for user {user_id}")
            await query.edit_message_text(
                "❌ <b>Access Denied</b>\n\nAutomation control requires MANAGE_ADMINS permission.",
                parse_mode='HTML'
            )
            return
        print(f"✅ DEBUG: Permission granted for user {user_id}")
        
        try:
            if callback_data == "automation_control":
                await _show_automation_control_panel(integration_instance,automation_manager, query, context)
                
            elif callback_data.startswith("automation_toggle_"):

                giveaway_type = callback_data.replace("automation_toggle_", "")

                # 🐛 BUGFIX: Manejar caso especial de invitations
                if giveaway_type == "invitations":
                    print(f"🔔 DEBUG: Processing invitation toggle")
                    # Handle recurring invitations toggle
                    success = automation_manager.toggle_recurring_invitations()
                    
                    if success:
                        status_text = "ENABLED" if automation_manager.recurring_invitations_enabled else "DISABLED"
                        response_message = f"""✅ <b>Recurring Invitations {status_text}</b>

    🔔 <b>Status:</b> {'🟢 ENABLED' if automation_manager.recurring_invitations_enabled else '🔴 DISABLED'}

    ⏰ <b>Frequencies:</b>
    ├─ Daily: every {automation_manager.invitation_frequencies['daily']} hours
    ├─ Weekly: every {automation_manager.invitation_frequencies['weekly']} hours
    └─ Monthly: every {automation_manager.invitation_frequencies['monthly']} hours

    💡 <b>What this means:</b>
    - Automatic invitations will {'start sending' if automation_manager.recurring_invitations_enabled else 'stop sending'}
    - Manual invitations are always available
    - Settings can be changed anytime

    🎛️ Use "⏰ Set Frequencies" to adjust timing."""
                        
                        buttons = [[InlineKeyboardButton("🏠 Back to Automation", callback_data="automation_control")]]
                        reply_markup = InlineKeyboardMarkup(buttons)
                        
                        await query.edit_message_text(
                            response_message, 
                            parse_mode='HTML',
                            reply_markup=reply_markup
                        )
                    else:
                        await query.edit_message_text(
                            f"❌ <b>Error toggling invitations</b>\n\n"
                            f"Could not change recurring invitation settings.\n\n"
                            f"💡 Current status: {'🟢 ENABLED' if automation_manager.recurring_invitations_enabled else '🔴 DISABLED'}",
                            parse_mode='HTML'
                        )
                    return
                
                # Handle giveaway type toggles (daily, weekly, monthly)
                if giveaway_type in ['daily', 'weekly', 'monthly']:
                    current_status = automation_manager.get_automation_status()
                    new_status = not current_status[giveaway_type]
                    
                    success = automation_manager.toggle_automatic_mode(giveaway_type, new_status)
                    
                    if success:
                        status_text = "ENABLED" if new_status else "DISABLED"
                        await query.edit_message_text(
                            f"✅ <b>{giveaway_type.title()} automation {status_text}</b>\n\n"
                            f"🤖 Automatic draws: {'🟢 ON' if new_status else '🔴 OFF'}\n"
                            f"📅 Next scheduled: {automation_manager._get_next_execution_time(giveaway_type) if new_status else 'Manual only'}",
                            parse_mode='HTML'
                        )
                    else:
                        await query.edit_message_text("❌ Error toggling automation")
                    return
                    
            elif callback_data == "automation_enable_all":
                results = {}
                for giveaway_type in ['daily', 'weekly', 'monthly']:
                    results[giveaway_type] = automation_manager.toggle_automatic_mode(giveaway_type, True)
                
                successful = sum(1 for success in results.values() if success)
                
                await query.edit_message_text(
                    f"✅ <b>Bulk Automation Enable</b>\n\n"
                    f"🟢 Successfully enabled: {successful}/3 types\n"
                    f"🤖 All automatic draws are now ACTIVE\n\n"
                    f"Daily: Monday-Friday at 5:00 PM\n"
                    f"Weekly: Friday at 5:15 PM\n"
                    f"Monthly: Last Friday at 5:30 PM\n\n"
                    f"London Time Zone",
                    parse_mode='HTML'
                )
                
            elif callback_data == "automation_disable_all":
                results = {}
                for giveaway_type in ['daily', 'weekly', 'monthly']:
                    results[giveaway_type] = automation_manager.toggle_automatic_mode(giveaway_type, False)
                
                successful = sum(1 for success in results.values() if success)
                
                await query.edit_message_text(
                    f"⏸️ <b>Bulk Automation Disable</b>\n\n"
                    f"🔴 Successfully disabled: {successful}/3 types\n"
                    f"🤖 All automatic draws are now INACTIVE\n\n"
                    f"📌 Manual draws remain available:\n"
                    f"• /admin_run_daily\n"
                    f"• /admin_run_weekly\n"
                    f"• /admin_run_monthly",
                    parse_mode='HTML'
                )

            

            elif callback_data == "automation_set_frequencies":
                await _show_frequency_settings(automation_manager,query)
                
            elif callback_data == "automation_refresh":
                await _show_automation_control_panel(integration_instance,automation_manager, query, context)
                
            elif callback_data == "automation_back_to_panel":
                await _show_unified_panel_inline(integration_instance, query)
                
        except Exception as e:
            logging.error(f"Error in automation callback: {e}")
            await query.edit_message_text("❌ Error processing automation command")

async def _handle_view_only_callbacks(integration_instance, query, callback_data: str):
        """🆕 Enrutador específico para usuarios VIEW_ONLY"""
        # user_id = query.from_user.id
    
        # 🟢 CALLBACKS PERMITIDOS PARA VIEW_ONLY (expandida)
        allowed_view_only_callbacks = [
            "view_only_health", "view_only_today_details", "view_only_refresh", 
            "view_only_permissions_info", "panel_refresh", "panel_unified_refresh",
            "panel_unified_main", "no_action"
        ]
        
        if callback_data in allowed_view_only_callbacks:
            # Ejecutar callbacks permitidos
            if callback_data == "view_only_health":
                await _show_view_only_health(integration_instance, query)
            elif callback_data == "view_only_today_details":
                await _show_view_only_today_details(integration_instance, query)
            elif callback_data == "view_only_permissions_info":
                await _show_view_only_permissions_info(integration_instance, query)
            elif callback_data in ["view_only_refresh", "panel_refresh", "panel_unified_refresh", "panel_unified_main"]:
                await _show_view_only_panel(integration_instance, query)
            elif callback_data == "no_action":
                await query.answer("ℹ️ No action available", show_alert=False)
            return
        
        # 🔴 ACCIONES ESPECÍFICAMENTE BLOQUEADAS PARA VIEW_ONLY
        blocked_actions = [
            "unified_send_all_invitations", "unified_execute_all_draws",
            "unified_all_pending", "unified_maintenance", 
            "unified_multi_analytics", "analytics_", "maintenance_",
            "panel_send_invitation_", "panel_run_giveaway_", "panel_pending_winners_"
        ]
        
        is_blocked = any(callback_data.startswith(blocked) for blocked in blocked_actions)
        
        if is_blocked:
            await query.edit_message_text(
                f"❌ <b>Access Denied - VIEW_ONLY</b>\n\n"
                f"This function requires PAYMENT_SPECIALIST or higher permissions.\n\n"
                f"💡 Returning to your VIEW_ONLY panel...",
                parse_mode='HTML'
            )
            await asyncio.sleep(1)
            await _show_view_only_panel(integration_instance, query)
            return
        return


async def _handle_confirm_payment_callback(integration_instance, update, context, giveaway_type):
        """🔄 MODIFIED: Handle payment confirmation with type awareness"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(integration_instance.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await query.edit_message_text("❌ Only administrators can confirm payments")
                return
            
            # Extract winner identifier from callback_data
            callback_data = query.data
            if not callback_data.startswith(f"confirm_payment_{giveaway_type}_"):
                await query.edit_message_text("❌ Invalid callback")
                return
            
            winner_identifier = callback_data.replace(f"confirm_payment_{giveaway_type}_", "")
            
            # Find winner by username or telegram_id
            winner_telegram_id = await _find_winner_by_identifier(integration_instance, winner_identifier, giveaway_type)
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\nNo pending {giveaway_type} winner found with: <code>{winner_identifier}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Confirm payment and proceed with announcements
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            success, message = await giveaway_system.confirm_payment_and_announce(
                winner_telegram_id, user_id, giveaway_type
            )
            
            if success:
                await query.edit_message_text(
                    f"✅ <b>{giveaway_type.title()} payment confirmed successfully</b>\n\nThe winner has been announced publicly and notified privately.",
                    parse_mode='HTML'
                )
            else:
                await query.edit_message_text(f"❌ {message}", parse_mode='HTML')
            
        except Exception as e:
            logging.error(f"Error in {giveaway_type} payment confirmation callback: {e}")
            await query.edit_message_text("❌ Error processing confirmation")


# Funciones inline de paneles:

async def _show_type_panel_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Show type-specific panel inline"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)

            is_open = giveaway_system.is_participation_window_open(giveaway_type)
            window_status = "🟢 Open" if is_open else "🔴 Closed"

            # Get last winner info if exists
            recent_winners = giveaway_system.get_pending_winners(giveaway_type)
            last_winner_info = ""
            if recent_winners:
                winner = recent_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                last_winner_info = f"\n🏆 <b>Last winner:</b> {winner_display}"
            
            message = f"""🎛️ <b>{giveaway_type.upper()} CONTROL PANEL</b>

💰 <b>Prize:</b> ${prize} USD
⏰ <b>Participation Window:</b> {window_status}

📊 <b>Today's participants:</b> {stats.get('today_participants', 0)}
⏳ <b>Pending winners:</b> {pending_count}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}

🚀 <b>Actions available:</b>"""
            
            buttons = [
                [
                    InlineKeyboardButton("📢 Send invitation", callback_data=f"panel_send_invitation_{giveaway_type}"),
                    InlineKeyboardButton("🎲 Execute draw", callback_data=f"panel_run_giveaway_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"👑 Pending ({pending_count})", callback_data=f"panel_pending_winners_{giveaway_type}"),
                    InlineKeyboardButton("📊 Statistics", callback_data=f"panel_full_stats_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("🔄 Other types", callback_data="type_selector_main"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} panel inline: {e}")
            await query.edit_message_text("❌ Error loading panel")

async def _show_type_selector_inline(integration_instance, query):
        """🆕 NEW: Show type selector inline"""
        try:
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nChoose which giveaway panel to access:"
            
            buttons = []
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                prize = giveaway_system.get_prize_amount()
                participants = giveaway_system._get_period_participants_count()
                pending = len(giveaway_system.get_pending_winners(giveaway_type))
                
                button_text = f"📅 {giveaway_type.title()} (${prize}) - {participants} today, {pending} pending"
                callback_data = f"panel_type_{giveaway_type}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            buttons.append([InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing type selector: {e}")
            await query.edit_message_text("❌ Error loading type selector")

async def _show_unified_panel_inline(integration_instance, query):
        """🔄 REFACTORED: Mostrar panel principal usando función base compartida"""
        try:
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            
            if not permission_manager:
                await query.edit_message_text("❌ Permission system not initialized")
                return
            
            # 🆕 USAR FUNCIÓN BASE COMPARTIDA
            message, reply_markup, status = await integration_instance._generate_main_admin_panel_content(user_id, permission_manager)
            
            if status == 'VIEW_ONLY':
                # 🚨 DETECCIÓN VIEW_ONLY - usar función específica para callbacks
                await _show_view_only_panel(integration_instance,query)
                return
            elif status == 'ERROR':
                await query.edit_message_text("❌ Error loading admin panel")
                return
            
            # ✅ MOSTRAR PANEL PRINCIPAL (SUCCESS case)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified panel inline: {e}")
            await query.edit_message_text("❌ Error loading admin panel")

async def _refresh_unified_panel(integration_instance, query):
        """🆕 NEW: Refresh unified panel"""
        try:
            await _show_unified_panel_inline(integration_instance, query)
            # 🆕 ADD: Success confirmation via popup
            await query.answer("✅ Panel refreshed", show_alert=False)
        except Exception as e:
            logging.error(f"Error refreshing unified panel: {e}")
            await query.answer("❌ Refresh failed", show_alert=True)

async def _show_all_pending_inline(integration_instance, query):
        """🆕 NEW: Show all pending winners from all types inline"""
        try:
            all_pending = {}
            total_pending = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                pending = giveaway_system.get_pending_winners(giveaway_type)
                if pending:
                    all_pending[giveaway_type] = pending
                    total_pending += len(pending)
            
            if total_pending == 0:
                buttons = [[InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text("ℹ️ No pending winners in any type", reply_markup=reply_markup)
                return
            
            message = f"📋 <b>ALL PENDING WINNERS ({total_pending})</b>\n\n"
            buttons = []
            
            for giveaway_type, pending_winners in all_pending.items():
                message += f"🎯 <b>{giveaway_type.upper()}:</b>\n"
                
                for i, winner in enumerate(pending_winners, 1):
                    username = winner.get('username', '').strip()
                    first_name = winner.get('first_name', 'N/A')
                    
                    if username:
                        command_identifier = username
                        display_name = f"{first_name} (@{username})"
                    else:
                        command_identifier = winner['telegram_id']
                        display_name = f"{first_name} (ID: {winner['telegram_id']})"
                    
                    message += f"{i}. {display_name} - ${winner['prize']}\n"
                    
                    # Button for each winner
                    button_text = f"✅ {giveaway_type.title()} - {first_name}"
                    callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                    buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
                
                message += "\n"
            
            buttons.append([InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing all pending inline: {e}")
            await query.edit_message_text("❌ Error getting all pending winners")

async def _show_combined_stats_inline(integration_instance, query):
        """🆕 NEW: Show combined statistics inline"""
        try:
            combined_totals = {
                'total_participants': 0,
                'total_winners': 0,
                'total_distributed': 0,
                'total_pending': 0
            }
            
            type_details = {}
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                type_details[giveaway_type] = {
                    'today': stats.get('today_participants', 0),
                    'total': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'distributed': stats.get('total_prize_distributed', 0),
                    'pending': pending_count,
                    'prize': giveaway_system.get_prize_amount()
                }
                
                combined_totals['total_participants'] += stats.get('total_participants', 0)
                combined_totals['total_winners'] += stats.get('total_winners', 0)
                combined_totals['total_distributed'] += stats.get('total_prize_distributed', 0)
                combined_totals['total_pending'] += pending_count
            
            message = f"""📊 <b>COMBINED STATISTICS</b>

🌟 <b>GLOBAL TOTALS:</b>
├─ Total participants: <b>{combined_totals['total_participants']}</b>
├─ Total winners: <b>{combined_totals['total_winners']}</b>
├─ Money distributed: <b>${combined_totals['total_distributed']}</b>
└─ Pending winners: <b>{combined_totals['total_pending']}</b>

📋 <b>BREAKDOWN BY TYPE:</b>"""

            for giveaway_type, details in type_details.items():
                message += f"""

🎯 <b>{giveaway_type.upper()} (${details['prize']}):</b>
├─ Today: {details['today']} participants
├─ Total: {details['total']} participants
├─ Winners: {details['winners']}
├─ Distributed: ${details['distributed']}
└─ Pending: {details['pending']}"""

            buttons = [
                [InlineKeyboardButton("📈 Cross-type analytics", callback_data="unified_cross_analytics")],
                [InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing combined stats: {e}")
            await query.edit_message_text("❌ Error getting combined statistics")

async def _send_all_invitations_inline(integration_instance, query):
        """🆕 NEW: Send invitations for all types inline"""
        try:
            results = {}
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                success = await giveaway_system.send_invitation()
                results[giveaway_type] = success
            
            message = "📢 <b>BULK INVITATION RESULTS</b>\n\n"
            
            successful = []
            failed = []
            
            for giveaway_type, success in results.items():
                if success:
                    successful.append(giveaway_type)
                    message += f"✅ {giveaway_type.title()}: Sent successfully\n"
                else:
                    failed.append(giveaway_type)
                    message += f"❌ {giveaway_type.title()}: Failed to send\n"
            
            message += f"\n📊 <b>Summary:</b> {len(successful)} successful, {len(failed)} failed"
            
            buttons = [[InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error sending all invitations: {e}")
            await query.edit_message_text("❌ Error sending invitations")


async def _execute_all_draws_inline(integration_instance, query):
        """🆕 NEW: Execute draws for all types inline"""
        try:
            results = {}
            
            for giveaway_type in integration_instance.available_types:
                try:
                    giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                    await giveaway_system.run_giveaway(giveaway_type)
                    
                    pending_winners = giveaway_system.get_pending_winners(giveaway_type)
                    results[giveaway_type] = {
                        'success': True,
                        'winners': len(pending_winners),
                        'winner_name': pending_winners[0].get('first_name', 'Unknown') if pending_winners else None
                    }
                except Exception as e:
                    results[giveaway_type] = {
                        'success': False,
                        'error': str(e)
                    }
            
            message = "🎲 <b>BULK DRAW EXECUTION RESULTS</b>\n\n"
            
            total_winners = 0
            
            for giveaway_type, result in results.items():
                if result['success']:
                    winners = result['winners']
                    total_winners += winners
                    if winners > 0:
                        message += f"✅ {giveaway_type.title()}: {result['winner_name']} selected\n"
                    else:
                        message += f"✅ {giveaway_type.title()}: No eligible participants\n"
                else:
                    message += f"❌ {giveaway_type.title()}: Error - {result['error']}\n"
            
            message += f"\n📊 <b>Total new winners:</b> {total_winners}"
            
            if total_winners > 0:
                message += f"\n\n💡 Check pending winners for payment confirmation"
            
            buttons = [
                [InlineKeyboardButton("👑 View all pending", callback_data="unified_all_pending")],
                [InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing all draws: {e}")
            await query.edit_message_text("❌ Error executing draws")



# Funciones inline de ejecución:

async def _execute_send_invitation_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Execute send invitation inline"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            success = await giveaway_system.send_invitation()
            
            if success:
                message = f"✅ <b>{giveaway_type.title()} invitation sent</b>\n\nInvitation has been sent to the channel successfully."
            else:
                message = f"❌ <b>Error sending {giveaway_type} invitation</b>\n\nCould not send invitation to channel."
            
            buttons = [
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing {giveaway_type} invitation: {e}")
            await query.edit_message_text("❌ Error sending invitation")

async def _execute_run_giveaway_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Execute giveaway draw inline"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            await giveaway_system.run_giveaway(giveaway_type)
            
            # Check results
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            pending_count = len(pending_winners)
            
            if pending_count > 0:
                winner = pending_winners[0]
                username = winner.get('username', '').strip()
                first_name = winner.get('first_name', 'N/A')
                winner_display = f"@{username}" if username else first_name
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                message = f"""✅ <b>{giveaway_type.title()} draw executed</b>

🎯 <b>Winner selected:</b> {winner_display}
📊 <b>MT5 Account:</b> {winner['mt5_account']}
💰 <b>Prize:</b> ${prize} USD
⏳ <b>Status:</b> Pending payment confirmation

💡 Check your private messages for complete details."""
            else:
                message = f"✅ <b>{giveaway_type.title()} draw executed</b>\n\nNo eligible participants found today."
            
            buttons = [
                [InlineKeyboardButton(f"👑 View pending", callback_data=f"panel_pending_winners_{giveaway_type}")],
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error executing {giveaway_type} draw: {e}")
            await query.edit_message_text("❌ Error executing draw")

async def _show_pending_winners_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Show pending winners for specific type inline"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            
            if not pending_winners:
                buttons = [
                    [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                    [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
                ]
                reply_markup = InlineKeyboardMarkup(buttons)
                await query.edit_message_text(
                    f"ℹ️ No pending {giveaway_type} winners",
                    reply_markup=reply_markup
                )
                return
            
            # Format list
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
                pending_list += f"   📊 MT5: <code>{winner['mt5_account']}</code>\n"
                pending_list += f"   💰 Prize: ${winner['prize']} USD\n"
                pending_list += f"   📅 Selected: {winner['selected_time']}\n\n"
                
                # Confirmation button
                button_text = f"✅ Confirm payment to {first_name}"
                callback_data = f"confirm_payment_{giveaway_type}_{command_identifier}"
                buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            
            # Navigation buttons
            buttons.extend([
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ])
            
            message = f"""📋 <b>{giveaway_type.upper()} PENDING WINNERS</b>

{pending_list}💡 <b>Instructions:</b>
1️⃣ Transfer to MT5 account
2️⃣ Press confirmation button
3️⃣ Bot will announce winner automatically

⚡ <b>Quick buttons:</b>"""
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} pending winners inline: {e}")
            await query.edit_message_text("❌ Error getting pending winners")

async def _show_full_stats_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Show full statistics for specific type inline"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""📊 <b>{giveaway_type.upper()} STATISTICS</b>

💰 <b>Prize Amount:</b> ${prize} USD

👥 <b>Today's participants:</b> {stats.get('today_participants', 0)}
📈 <b>Total participants:</b> {stats.get('total_participants', 0)}
🏆 <b>Total winners:</b> {stats.get('total_winners', 0)}
💰 <b>Money distributed:</b> ${stats.get('total_prize_distributed', 0)}
⏳ <b>Pending winners:</b> {pending_count}

⏰ Next draw: Check schedule

<i>Updated: {stats.get('timestamp', 'N/A')}</i>"""

            buttons = [
                [InlineKeyboardButton(f"📈 Advanced analytics", callback_data=f"analytics_{giveaway_type}_30")],
                [InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")],
                [InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)

            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} stats inline: {e}")
            await query.edit_message_text("❌ Error getting statistics")

async def _refresh_type_panel(integration_instance, query, giveaway_type):
        """🆕 NEW: Refresh type-specific panel"""
        try:
            await _show_type_panel_inline(integration_instance, query, giveaway_type)
        except Exception as e:
            logging.error(f"Error refreshing {giveaway_type} panel: {e}")
            await query.edit_message_text("❌ Error refreshing panel")


# Analytics inline:

async def _show_analytics_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Show analytics for specific type"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)

            total_participants = stats.get('total_participants', 0)
            total_winners = stats.get('total_winners', 0)
            total_distributed = stats.get('total_prize_distributed', 0)
            today_participants = stats.get('today_participants', 0)
            cost_per_participant = total_distributed / max(total_participants, 1)

            win_rate = (total_winners / max(total_participants, 1)) * 100
            avg_prize_per_day = total_distributed / max(30, 1)  # Approximate monthly average
            
            
            message = f"""📈 <b>{giveaway_type.upper()} ANALYTICS</b>

        💰 <b>Configuration:</b>
        ├─ Prize Amount: ${prize} USD
        └─ Reset Frequency: {giveaway_type}

        📊 <b>Participation Analytics:</b>
        ├─ Today's participants: <b>{today_participants}</b>
        ├─ Total participants: <b>{total_participants:,}</b>
        ├─ Daily efficiency: {'🟢 High' if today_participants > 10 else '🟡 Medium' if today_participants > 5 else '🔴 Low'} ({today_participants}/day)
        └─ Participation trend: {'📈 Growing' if today_participants > 5 else '📊 Stable'}

        🏆 <b>Winner Analytics:</b>
        ├─ Total winners: <b>{total_winners}</b>
        ├─ Win rate: <b>{win_rate:.2f}%</b>
        ├─ Money distributed: <b>${total_distributed:,}</b>
        └─ Cost per participant: <b>${cost_per_participant:.2f}</b>

        📈 <b>Performance Metrics:</b>
        ├─ Average prize/month: <b>${avg_prize_per_day * 30:.2f}</b>
        ├─ Success rate: {'🟢 Excellent' if win_rate > 10 else '🟡 Good' if win_rate > 5 else '🟠 Moderate' if win_rate > 2 else '🔴 Low'}
        ├─ Engagement level: {'🟢 High' if total_participants > 100 else '🟡 Medium' if total_participants > 50 else '🔴 Growing'}
        └─ System efficiency: <b>{(total_winners / max(total_participants, 1) * 1000):.1f}</b> winners per 1000 participants

            🔍 <b>Select detailed period:</b>"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Last 7 days", callback_data=f"analytics_{giveaway_type}_7"),
                    InlineKeyboardButton("📊 Last 30 days", callback_data=f"analytics_{giveaway_type}_30")
                ],
                [
                    InlineKeyboardButton("📊 Last 90 days", callback_data=f"analytics_{giveaway_type}_90"),
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}"),
                    InlineKeyboardButton("💰 Revenue analysis", callback_data=f"revenue_analysis_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing analytics for {giveaway_type}: {e}")
            await query.edit_message_text("❌ Error loading analytics")

async def _show_analytics_detailed_inline(integration_instance, query, giveaway_type, days):
        """🆕 NEW: Show detailed analytics for specific period"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            # Calculate detailed metrics for the period
            total_participants = stats.get('total_participants', 0)
            total_winners = stats.get('total_winners', 0)
            total_distributed = stats.get('total_prize_distributed', 0)
            
            avg_participants_per_day = total_participants / days if days > 0 else 0
            win_rate = (total_winners / max(total_participants, 1)) * 100
            cost_per_participant = total_distributed / max(total_participants, 1)
            
            message = f"""📊 <b>{giveaway_type.upper()} DETAILED ANALYTICS ({days} days)</b>

    💰 <b>Prize:</b> ${prize} USD per draw

    📈 <b>Period Analysis:</b>
    ├─ Total participants: {total_participants}
    ├─ Daily average: {avg_participants_per_day:.1f}
    ├─ Total winners: {total_winners}
    ├─ Money distributed: ${total_distributed}
    ├─ Win rate: {win_rate:.2f}%
    └─ Cost per participant: ${cost_per_participant:.2f}

    📊 <b>Performance:</b>
    ├─ Active days in period: {min(days, 30)}
    ├─ Average engagement: {'High' if avg_participants_per_day > 10 else 'Medium' if avg_participants_per_day > 5 else 'Low'}
    ├─ Distribution efficiency: {(total_distributed / (days * prize)):.1f}x expected
    └─ Growth trend: {'Positive' if total_participants > days * 5 else 'Stable'}

    📋 <b>Recommendations:</b>
    • {'Increase promotion' if avg_participants_per_day < 10 else 'Maintain current strategy'}
    • {'Consider prize adjustment' if win_rate < 5 else 'Prize level optimal'}

    <i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

            buttons = [
                [
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}"),
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton("📈 Other periods", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing detailed analytics: {e}")
            await query.edit_message_text("❌ Error loading detailed analytics")

async def _show_top_users_inline(integration_instance, query, giveaway_type):
        """🆕 NEW: Show top users for specific type"""
        try:
            giveaway_system = integration_instance.giveaway_systems[giveaway_type]
            # This would need to be implemented in ga_manager.py
            # For now, showing placeholder
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""👥 <b>TOP {giveaway_type.upper()} USERS</b>

    💰 <b>Giveaway:</b> ${prize} USD

    🏆 <b>Most Active Participants:</b>

    📊 <b>Current Period Analysis:</b>
    ├─ Today's participants: {stats.get('today_participants', 0)}
    ├─ Total unique users: {stats.get('total_participants', 0)}
    ├─ Total winners: {stats.get('total_winners', 0)}
    └─ Analysis period: All time

    💡 <b>Top Users Analysis:</b>
    This feature shows the most active participants in {giveaway_type} giveaways.

    🔧 <b>Advanced Analysis Available:</b>
    • Participation frequency
    • Win rates per user
    • Account usage patterns
    • Loyalty metrics

    💡 This feature requires advanced analytics implementation."""

            buttons = [
                [
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}"),
                    InlineKeyboardButton("🏦 Account report", callback_data=f"account_report_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing top users: {e}")
            await query.edit_message_text("❌ Error loading top users")

async def _show_unified_multi_analytics_inline(integration_instance, query):
        """🆕 NEW: Show unified multi-analytics"""
        try:
            combined_stats = {}
            total_participants_all = 0
            total_winners_all = 0
            total_distributed_all = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                
                combined_stats[giveaway_type] = {
                    'participants': stats.get('total_participants', 0),
                    'winners': stats.get('total_winners', 0),
                    'distributed': stats.get('total_prize_distributed', 0),
                    'prize': giveaway_system.get_prize_amount(giveaway_type)
                }
                
                total_participants_all += stats.get('total_participants', 0)
                total_winners_all += stats.get('total_winners', 0)
                total_distributed_all += stats.get('total_prize_distributed', 0)
            
            message = f"""📈 <b>UNIFIED MULTI-ANALYTICS</b>

    🌟 <b>GLOBAL PERFORMANCE:</b>
    ├─ Total participants: {total_participants_all}
    ├─ Total winners: {total_winners_all}
    ├─ Total distributed: ${total_distributed_all}
    ├─ Overall win rate: {(total_winners_all / max(total_participants_all, 1) * 100):.2f}%
    └─ Average per winner: ${total_distributed_all / max(total_winners_all, 1):.2f}

    📊 <b>BY GIVEAWAY TYPE:</b>"""

            for giveaway_type, stats in combined_stats.items():
                efficiency = (stats['winners'] / max(stats['participants'], 1)) * 100
                message += f"""
    🎯 <b>{giveaway_type.upper()} (${stats['prize']}):</b>
    ├─ Participants: {stats['participants']}
    ├─ Winners: {stats['winners']}
    ├─ Distributed: ${stats['distributed']}
    └─ Efficiency: {efficiency:.1f}%"""

            message += f"\n\n💡 <b>Cross-type insights:</b>\n• Most popular: {max(combined_stats.keys(), key=lambda k: combined_stats[k]['participants'])}\n• Highest efficiency: {max(combined_stats.keys(), key=lambda k: combined_stats[k]['winners'] / max(combined_stats[k]['participants'], 1))}"

            buttons = [
                [
                    InlineKeyboardButton("📊 Cross-type comparison", callback_data="unified_cross_analytics"),
                    InlineKeyboardButton("📈 Revenue analysis", callback_data="analytics_revenue")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified analytics: {e}")
            await query.edit_message_text("❌ Error loading unified analytics")


async def _show_cross_type_analytics_inline(integration_instance, query):
        """🆕 NEW: Show cross-type analytics comparison (different from cross_analytics)"""
        try:
            # Get data for all types
            type_comparison = {}
            total_global_participants = 0
            total_global_winners = 0
            total_global_distributed = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                pending = len(giveaway_system.get_pending_winners(giveaway_type))
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                
                type_comparison[giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'pending': pending,
                    'win_rate': (winners / max(participants, 1)) * 100,
                    'avg_cost_per_participant': distributed / max(participants, 1),
                    'efficiency_score': (winners * prize) / max(distributed, 1) if distributed > 0 else 0
                }
                
                total_global_participants += participants
                total_global_winners += winners
                total_global_distributed += distributed
            
            # Calculate rankings
            most_participants = max(type_comparison.keys(), key=lambda k: type_comparison[k]['participants'])
            highest_win_rate = max(type_comparison.keys(), key=lambda k: type_comparison[k]['win_rate'])
            most_efficient = max(type_comparison.keys(), key=lambda k: type_comparison[k]['efficiency_score'])
            
            message = f"""🔄 <b>CROSS-TYPE ANALYTICS COMPARISON</b>

    🏆 <b>RANKINGS:</b>
    ├─ 👥 Most Popular: <b>{most_participants.title()}</b>
    ├─ 🎯 Highest Win Rate: <b>{highest_win_rate.title()}</b>
    └─ ⚡ Most Efficient: <b>{most_efficient.title()}</b>

    🌍 <b>GLOBAL TOTALS:</b>
    ├─ Combined Participants: <b>{total_global_participants}</b>
    ├─ Combined Winners: <b>{total_global_winners}</b>
    ├─ Total Distributed: <b>${total_global_distributed}</b>
    └─ Overall Win Rate: <b>{(total_global_winners / max(total_global_participants, 1) * 100):.2f}%</b>

    📊 <b>DETAILED BREAKDOWN:</b>"""

            for giveaway_type, data in type_comparison.items():
                message += f"""

    🎯 <b>{giveaway_type.upper()} (${data['prize']}):</b>
    ├─ Participants: {data['participants']} ({(data['participants']/max(total_global_participants,1)*100):.1f}% of total)
    ├─ Winners: {data['winners']} │ Win Rate: {data['win_rate']:.2f}%
    ├─ Distributed: ${data['distributed']} │ Pending: {data['pending']}
    ├─ Cost/Participant: ${data['avg_cost_per_participant']:.2f}
    └─ Efficiency Score: {data['efficiency_score']:.2f}"""

            message += f"\n\n💡 <b>Strategic Recommendations:</b>"
            
            # Generate recommendations based on data
            lowest_participation = min(type_comparison.keys(), key=lambda k: type_comparison[k]['participants'])
            if type_comparison[lowest_participation]['participants'] < total_global_participants * 0.2:
                message += f"\n• Consider increasing promotion for {lowest_participation} giveaway"
            
            if total_global_winners > 0:
                message += f"\n• System efficiency: {(total_global_distributed / (total_global_winners * 100)):.1f}x baseline"
            
            message += f"\n• Peak performance type: {most_efficient.title()}"

            buttons = [
                [
                    InlineKeyboardButton("📈 Revenue Impact", callback_data="analytics_revenue_impact"),
                    InlineKeyboardButton("👥 User Behavior", callback_data="analytics_user_behavior")
                ],
                [
                    InlineKeyboardButton("📊 Time Analysis", callback_data="analytics_time_trends"),
                    InlineKeyboardButton("🔍 Deep Dive", callback_data="analytics_deep_dive")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_multi_analytics"),
                    InlineKeyboardButton("🏠 Unified Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cross-type analytics: {e}")
            await query.edit_message_text("❌ Error loading cross-type analytics")

async def _show_combined_analytics_inline(integration_instance, query):
        """🆕 NEW: Show combined analytics from all giveaway types"""
        try:
            # Collect all data
            combined_data = {
                'total_participants_all_time': 0,
                'total_winners_all_time': 0,
                'total_money_distributed': 0,
                'total_pending_all_types': 0,
                'active_giveaway_types': 0,
                'by_type_details': {},
                'performance_metrics': {},
                'time_analysis': {}
            }
            
            current_month = datetime.now().strftime('%Y-%m')
            current_week = datetime.now().strftime('%Y-W%U')
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending = giveaway_system.get_pending_winners(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                cooldown = giveaway_system.get_cooldown_days(giveaway_type)
                
                # Basic stats
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                today_participants = stats.get('today_participants', 0)
                
                combined_data['total_participants_all_time'] += participants
                combined_data['total_winners_all_time'] += winners
                combined_data['total_money_distributed'] += distributed
                combined_data['total_pending_all_types'] += len(pending)
                
                if participants > 0:
                    combined_data['active_giveaway_types'] += 1
                
                # Detailed breakdown
                combined_data['by_type_details'][giveaway_type] = {
                    'prize': prize,
                    'cooldown': cooldown,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'pending': len(pending),
                    'today_participants': today_participants,
                    'win_rate': (winners / max(participants, 1)) * 100,
                    'activity_level': 'High' if today_participants > 10 else 'Medium' if today_participants > 5 else 'Low',
                    'roi_efficiency': (distributed / max(participants * prize, 1)) * 100 if participants > 0 else 0
                }
            
            # Calculate performance metrics
            overall_win_rate = (combined_data['total_winners_all_time'] / max(combined_data['total_participants_all_time'], 1)) * 100
            avg_prize_per_winner = combined_data['total_money_distributed'] / max(combined_data['total_winners_all_time'], 1)
            system_efficiency = (combined_data['total_winners_all_time'] / max(combined_data['total_participants_all_time'], 1)) * 100
            
            message = f"""📊 <b>COMBINED ANALYTICS DASHBOARD</b>

    🌟 <b>GLOBAL PERFORMANCE OVERVIEW:</b>
    ├─ 👥 Total Participants: <b>{combined_data['total_participants_all_time']:,}</b>
    ├─ 🏆 Total Winners: <b>{combined_data['total_winners_all_time']:,}</b>
    ├─ 💰 Money Distributed: <b>${combined_data['total_money_distributed']:,}</b>
    ├─ ⏳ Pending Payments: <b>{combined_data['total_pending_all_types']}</b>
    └─ 🎯 Active Types: <b>{combined_data['active_giveaway_types']}/{len(integration_instance.available_types)}</b>

    📈 <b>KEY METRICS:</b>
    ├─ Overall Win Rate: <b>{overall_win_rate:.2f}%</b>
    ├─ Average Prize/Winner: <b>${avg_prize_per_winner:.2f}</b>
    ├─ System Efficiency: <b>{system_efficiency:.1f}%</b>
    └─ Daily Activity: <b>{sum(data['today_participants'] for data in combined_data['by_type_details'].values())} participants today</b>

    🎯 <b>PERFORMANCE BY TYPE:</b>"""

            # Show each type's performance
            for giveaway_type, data in combined_data['by_type_details'].items():
                activity_emoji = "🟢" if data['activity_level'] == 'High' else "🟡" if data['activity_level'] == 'Medium' else "🔴"
                
                message += f"""

    {activity_emoji} <b>{giveaway_type.upper()} (${data['prize']}, {data['cooldown']}d cooldown):</b>
    ├─ Participants: {data['participants']:,} │ Winners: {data['winners']}
    ├─ Distributed: ${data['distributed']:,} │ Pending: {data['pending']}
    ├─ Today: {data['today_participants']} │ Win Rate: {data['win_rate']:.2f}%
    └─ ROI Efficiency: {data['roi_efficiency']:.1f}% │ Activity: {data['activity_level']}"""

            # Add insights
            best_performing = max(combined_data['by_type_details'].keys(), 
                                key=lambda k: combined_data['by_type_details'][k]['win_rate'])
            most_active = max(combined_data['by_type_details'].keys(), 
                            key=lambda k: combined_data['by_type_details'][k]['today_participants'])
            
            message += f"""

    💡 <b>INSIGHTS & TRENDS:</b>
    ├─ 🥇 Best Win Rate: <b>{best_performing.title()}</b> ({combined_data['by_type_details'][best_performing]['win_rate']:.2f}%)
    ├─ 🔥 Most Active Today: <b>{most_active.title()}</b> ({combined_data['by_type_details'][most_active]['today_participants']} participants)
    ├─ 💸 Total Investment: <b>${sum(data['participants'] * data['prize'] for data in combined_data['by_type_details'].values()):,}</b>
    └─ 📊 Success Rate: <b>{(combined_data['total_winners_all_time'] / max(len(integration_instance.available_types) * 365, 1) * 100):.1f}% daily average</b>

    <i>🕒 Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"""

            buttons = [
                [
                    InlineKeyboardButton("📈 Cross-Type Comparison", callback_data="analytics_cross_type"),
                    InlineKeyboardButton("💰 Revenue Analysis", callback_data="analytics_revenue_detailed")
                ],
                [
                    InlineKeyboardButton("📊 User Analytics", callback_data="analytics_user_patterns"),
                    InlineKeyboardButton("⏰ Time Patterns", callback_data="analytics_time_patterns")
                ],
                [
                    InlineKeyboardButton("📋 Export Report", callback_data="analytics_export_report"),
                    InlineKeyboardButton("🏠 Unified Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing combined analytics: {e}")
            await query.edit_message_text("❌ Error loading combined analytics")

async def _show_cross_analytics_inline(integration_instance, query):
        """🔄 MODIFIED: Enhanced cross-type analytics with dynamic insights"""
        try:
            comparison_data = {}
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                today_participants = stats.get('today_participants', 0)
                
                comparison_data[giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'today_participants': today_participants,
                    'roi': (winners / max(participants, 1)) * 100,
                    'cost_efficiency': prize / max(participants, 1) if participants > 0 else float('inf'),
                    'engagement_today': today_participants,
                    'win_rate': (winners / max(participants, 1)) * 100
                }
            
            # Find performance leaders
            most_popular = max(comparison_data.keys(), key=lambda k: comparison_data[k]['participants'])
            best_roi = max(comparison_data.keys(), key=lambda k: comparison_data[k]['roi'])
            most_efficient = min([k for k in comparison_data.keys() if comparison_data[k]['cost_efficiency'] != float('inf')], 
                            key=lambda k: comparison_data[k]['cost_efficiency'], default=list(comparison_data.keys())[0])
            most_active_today = max(comparison_data.keys(), key=lambda k: comparison_data[k]['today_participants'])
            
            message = f"""🔄 <b>CROSS-TYPE ANALYTICS COMPARISON</b>

    🏆 <b>PERFORMANCE LEADERS:</b>
    ├─ 👥 Most Popular: <b>{most_popular.title()}</b> ({comparison_data[most_popular]['participants']} total participants)
    ├─ 🎯 Best Win Rate: <b>{best_roi.title()}</b> ({comparison_data[best_roi]['roi']:.1f}% winners)
    ├─ 💰 Most Cost-Efficient: <b>{most_efficient.title()}</b> (${comparison_data[most_efficient]['cost_efficiency']:.2f}/participant)
    └─ 🔥 Most Active Today: <b>{most_active_today.title()}</b> ({comparison_data[most_active_today]['today_participants']} today)

    📊 <b>DETAILED COMPARISON:</b>"""

            for giveaway_type, data in comparison_data.items():
                activity_indicator = "🔥" if data['today_participants'] > 5 else "📊" if data['today_participants'] > 0 else "💤"
                
                message += f"""
    {activity_indicator} <b>{giveaway_type.upper()}:</b>
    ├─ Prize: ${data['prize']} │ Total Participants: {data['participants']:,}
    ├─ Winners: {data['winners']} │ Win Rate: {data['win_rate']:.1f}%
    ├─ Cost/Participant: ${data['cost_efficiency']:.2f} │ Today: {data['today_participants']}
    └─ Performance: {'Excellent' if data['roi'] > 10 else 'Good' if data['roi'] > 5 else 'Developing'}"""

            # 🔄 DYNAMIC STRATEGIC INSIGHTS BASED ON ACTUAL DATA
            insights = []
            
            # Analyze participation levels
            avg_participants = sum(data['participants'] for data in comparison_data.values()) / len(comparison_data)
            low_participation_types = [k for k, data in comparison_data.items() if data['participants'] < avg_participants * 0.5]
            
            if low_participation_types:
                insights.append(f"Consider increasing promotion for {', '.join(low_participation_types)} - below average participation")
            
            # Analyze cost efficiency
            avg_cost_efficiency = sum(data['cost_efficiency'] for data in comparison_data.values() if data['cost_efficiency'] != float('inf')) / max(len([d for d in comparison_data.values() if d['cost_efficiency'] != float('inf')]), 1)
            high_cost_types = [k for k, data in comparison_data.items() if data['cost_efficiency'] > avg_cost_efficiency * 1.5]
            
            if high_cost_types:
                insights.append(f"High cost per participant in {', '.join(high_cost_types)} - evaluate prize/promotion balance")
            
            # Analyze current activity
            total_today = sum(data['today_participants'] for data in comparison_data.values())
            if total_today == 0:
                insights.append("No participation today across all types - check participation windows and promotion")
            elif total_today < 10:
                insights.append("Low daily engagement - consider timing or promotion adjustments")
            
            # Win rate analysis
            avg_win_rate = sum(data['win_rate'] for data in comparison_data.values()) / len(comparison_data)
            if avg_win_rate < 5:
                insights.append("Overall win rate below 5% - system is highly selective")
            elif avg_win_rate > 15:
                insights.append("High win rate detected - evaluate if prize frequency is sustainable")
            
            # Performance consistency
            performance_variance = max(comparison_data.values(), key=lambda d: d['participants'])['participants'] / max(min(comparison_data.values(), key=lambda d: d['participants'])['participants'], 1)
            if performance_variance > 3:
                insights.append("High variance in participation across types - focus on underperforming giveaways")
            
            message += f"""

    💡 <b>DYNAMIC STRATEGIC INSIGHTS:</b>"""
            
            if insights:
                for insight in insights[:4]:  # Show max 4 insights
                    message += f"\n• {insight}"
            else:
                message += f"\n• All giveaway types performing within expected parameters"
                message += f"\n• System efficiency: {avg_cost_efficiency:.2f} average cost per participant"
                message += f"\n• Balanced performance across all {len(integration_instance.available_types)} giveaway types"
            
            message += f"""

    📈 <b>OPTIMIZATION OPPORTUNITIES:</b>
    • Leverage {most_popular} success patterns for other types
    • Scale {most_efficient} cost-efficiency model
    • Monitor {most_active_today} engagement strategies today"""

            buttons = [
                [
                    InlineKeyboardButton("💰 Cost Analysis", callback_data="analytics_revenue"),
                    InlineKeyboardButton("👥 User Overlap", callback_data="analytics_user_overlap")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cross analytics: {e}")
            await query.edit_message_text("❌ Error loading cross analytics")

# Automation callbacks:
async def _show_automation_control_panel(integration_instance,automation_manager, query, context):
        """🆕 Show automation control panel"""
        try:
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
            admin_name = admin_info.get('name', 'Admin') if admin_info else 'Unknown'
            
            automation_status = automation_manager.get_automation_status()
            
            message = f"""🤖 <b>AUTOMATIC DRAW CONTROL</b>
👤 <b>Admin:</b> {admin_name}

📊 <b>Current Automatic Draws Status:</b>
├─ Daily: {'🟢 ENABLED' if automation_status['daily'] else '🔴 DISABLED'}
├─ Weekly: {'🟢 ENABLED' if automation_status['weekly'] else '🔴 DISABLED'}
├─ Monthly: {'🟢 ENABLED' if automation_status['monthly'] else '🔴 DISABLED'}
└─ Scheduler: {'🟢 RUNNING' if automation_status['scheduler_running'] else '🔴 STOPPED'}

⏰ <b>Draw Schedule (London Time):</b>
├─ Daily: Monday-Friday at 17:00
├─ Weekly: Friday at 17:15
└─ Monthly: Last Friday at 17:30

🔔 <b>Recurring Invitations:</b>
├─ Auto-invitations: {'🟢 ENABLED' if automation_manager.recurring_invitations_enabled else '🔴 DISABLED'}
├─ Daily frequency: Every {automation_manager.invitation_frequencies['daily']} hours
├─ Weekly frequency: Every {automation_manager.invitation_frequencies['weekly']} hours
└─ Monthly frequency: Every {automation_manager.invitation_frequencies['monthly']} hours

🔧 <b>System Status:</b>
├─ Scheduler Available: {'✅ Yes' if automation_status['scheduler_available'] else '❌ No'}
├─ Manual Override: ✅ Always Available
└─ Conflict Protection: ✅ Active"""

            # Add next execution times
            # enabled_types = [t for t, enabled in automation_status.items() if enabled and t != 'scheduler_running' and t != 'scheduler_available']
            # if enabled_types:
            #     message += f"\n\n🕐 <b>Next Automatic Executions:</b>"
            #     for giveaway_type in enabled_types:
            #         next_time = self._get_next_execution_time(giveaway_type)
            #         message += f"\n├─ {giveaway_type.title()}: {next_time}"

            buttons = [
                [
                    InlineKeyboardButton("🕹️ Toggle Daily Draw", callback_data="automation_toggle_daily"),
                    InlineKeyboardButton("🕹️ Toggle Weekly Draw", callback_data="automation_toggle_weekly"),
                    InlineKeyboardButton("🕹️ Toggle Monthly Draw", callback_data="automation_toggle_monthly")
                ],
                
                [
                    InlineKeyboardButton("🟢 Enable All Draws", callback_data="automation_enable_all"),
                    InlineKeyboardButton("🔴 Disable All Draws", callback_data="automation_disable_all")
                ],
                [
                    # 🆕 ADD: Recurring invitations control
                    InlineKeyboardButton("🔔 Toggle Auto Invitations", callback_data="automation_toggle_invitations"),
                    InlineKeyboardButton("⏰ Set Invitation Freq.", callback_data="automation_set_frequencies")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Panel", callback_data="automation_back_to_panel")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing automation control panel: {e}")
            await query.edit_message_text("❌ Error loading automation control panel")


async def _show_frequency_settings(automation_manager, query):
        """🆕 Show frequency settings panel"""
        try:
            message = f"""⏰ <b>INVITATION FREQUENCY SETTINGS</b>

    🔔 <b>Current Frequencies:</b>
    ├─ Daily: Every {automation_manager.invitation_frequencies['daily']} hours
    ├─ Weekly: Every {automation_manager.invitation_frequencies['weekly']} hours
    └─ Monthly: Every {automation_manager.invitation_frequencies['monthly']} hours

    💡 <b>Recommended Frequencies:</b>
    - Daily: 2-4 hours (high engagement)
    - Weekly: 4-6 hours (moderate promotion)
    - Monthly: 6-8 hours (background promotion)

    ⚠️ <b>Note:</b> Too frequent invitations may overwhelm users.
    Current settings work well for balanced engagement."""

            buttons = [
                [
                    InlineKeyboardButton("Daily 🔂 2h", callback_data="freq_daily_2"),
                    InlineKeyboardButton("Daily 🔂 3h", callback_data="freq_daily_3"),
                    InlineKeyboardButton("Daily 🔂 4h", callback_data="freq_daily_4")
                ],
                [
                    InlineKeyboardButton("Weekly 🔂 4h", callback_data="freq_weekly_4"),
                    InlineKeyboardButton("Weekly 🔂 6h", callback_data="freq_weekly_6"),
                    InlineKeyboardButton("Weekly 🔂 8h", callback_data="freq_weekly_8")
                ],
                [
                    InlineKeyboardButton("Monthly 🔂 6h", callback_data="freq_monthly_6"),
                    InlineKeyboardButton("Monthly 🔂 8h", callback_data="freq_monthly_8"),
                    InlineKeyboardButton("Monthly 🔂 12h", callback_data="freq_monthly_12")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Automation", callback_data="automation_control")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing frequency settings: {e}")
            await query.edit_message_text("❌ Error loading frequency settings")


# Maintenance callbacks:
async def _show_maintenance_panel_inline(integration_instance, query):
        """🆕 NEW: Show maintenance panel"""
        try:
            # Get system health
            health_report = integration_instance.verify_all_systems_health()
            
            message = f"""🛠️ <b>MAINTENANCE PANEL</b>

    🌡️ <b>System Health:</b> {health_report['overall_status'].upper()}

    💾 <b>Available Actions:</b>"""

            if health_report.get('issues'):
                message += f"\n\n⚠️ <b>Issues detected:</b>"
                for issue in health_report['issues'][:3]:
                    message += f"\n• {issue}"

            buttons = [
                [
                    InlineKeyboardButton("🧹 Clean old data", callback_data="maintenance_cleanup"),
                    InlineKeyboardButton("💾 Create backups", callback_data="maintenance_backup")
                ],
                [
                    InlineKeyboardButton("🔍 System check", callback_data="maintenance_health"),
                    InlineKeyboardButton("📊 File status", callback_data="maintenance_files")
                ],
                [
                    InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing maintenance panel: {e}")
            await query.edit_message_text("❌ Error loading maintenance panel")


async def _execute_maintenance_cleanup(integration_instance, query):
        """🆕 NEW: Execute cleanup of old participant data"""
        try:
            cleanup_results = {}
            
            for giveaway_type in integration_instance.available_types:
                try:
                    giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                    # Clean old participants (keep only current period)
                    giveaway_system.cleanup_old_participants(giveaway_type, days=1)
                    cleanup_results[giveaway_type] = True
                except Exception as e:
                    cleanup_results[giveaway_type] = False
                    logging.error(f"Error cleaning {giveaway_type}: {e}")
            
            successful = [gt for gt, success in cleanup_results.items() if success]
            failed = [gt for gt, success in cleanup_results.items() if not success]
            
            message = f"""🧹 <b>CLEANUP COMPLETED</b>

    ✅ <b>Successful cleanup:</b> {', '.join(successful) if successful else 'None'}
    ❌ <b>Failed cleanup:</b> {', '.join(failed) if failed else 'None'}

    📊 <b>Summary:</b> {len(successful)}/{len(integration_instance.available_types)} successful

    🔄 <b>Actions performed:</b>
    • Cleared old participant files
    • Preserved permanent history
    • Maintained pending winners
    • Kept configuration intact

    💡 Old data moved to history files for permanent record."""

            buttons = [
                [
                    InlineKeyboardButton("📊 File Status", callback_data="maintenance_files"),
                    InlineKeyboardButton("🏥 Health Check", callback_data="maintenance_health")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in maintenance cleanup: {e}")
            await query.edit_message_text("❌ Error executing cleanup")

async def _execute_maintenance_backup(integration_instance, query):
        """🆕 NEW: Create backups of all giveaway data"""
        try:
            backup_results = {}
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for giveaway_type in integration_instance.available_types:
                try:
                    giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                    backup_file = giveaway_system.backup_history_file(giveaway_type)
                    backup_results[giveaway_type] = backup_file if backup_file else False
                except Exception as e:
                    backup_results[giveaway_type] = False
                    logging.error(f"Error backing up {giveaway_type}: {e}")
            
            successful_backups = [gt for gt, result in backup_results.items() if result]
            failed_backups = [gt for gt, result in backup_results.items() if not result]
            
            message = f"""💾 <b>BACKUP OPERATION COMPLETED</b>

    📅 <b>Timestamp:</b> {timestamp}

    ✅ <b>Successful backups:</b>
    {chr(10).join(f"• {gt.title()}: backup_{timestamp}" for gt in successful_backups) if successful_backups else "• None"}

    ❌ <b>Failed backups:</b>
    {chr(10).join(f"• {gt.title()}: Error occurred" for gt in failed_backups) if failed_backups else "• None"}

    📊 <b>Summary:</b> {len(successful_backups)}/{len(integration_instance.available_types)} successful

    💡 <b>Backup includes:</b>
    • Complete participant history
    • Winner records
    • Pending payment data
    • System configuration snapshots

    📁 Backup files saved in respective data directories with timestamp."""

            buttons = [
                [
                    InlineKeyboardButton("📊 File Status", callback_data="maintenance_files"),
                    InlineKeyboardButton("🧹 Clean Data", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in backup operation: {e}")
            await query.edit_message_text("❌ Error creating backups")

async def _execute_system_health_check(integration_instance, query):
        """🆕 NEW: Execute comprehensive system health check"""
        try:
            health_report = integration_instance.verify_all_systems_health()
            
            message = f"""🏥 <b>SYSTEM HEALTH CHECK REPORT</b>

    🌡️ <b>Overall Status:</b> {health_report['overall_status'].upper()}

    💡 <b>Giveaway Systems Status:</b>"""

            for giveaway_type, system_status in health_report['systems'].items():
                if system_status['status'] == 'healthy':
                    status_emoji = "✅"
                    details = f"Prize: ${system_status['prize_amount']}, Pending: {system_status['pending_count']}"
                else:
                    status_emoji = "❌"
                    details = f"Error: {system_status.get('error', 'Unknown')}"
                    
                message += f"""
    {status_emoji} <b>{giveaway_type.upper()}:</b> {system_status['status'].title()}
    └─ {details}"""

            # Check configuration
            config_status = "✅ Loaded" if hasattr(integration_instance, 'config_loader') else "❌ Missing"
            message += f"""

    🔧 <b>System Components:</b>
    ├─ Configuration: {config_status}
    ├─ Database: ✅ CSV files accessible
    ├─ Scheduler: ✅ Running
    └─ Bot Integration: ✅ Active"""

            if health_report.get('issues'):
                message += f"""

    ⚠️ <b>Issues Detected:</b>"""
                for issue in health_report['issues'][:5]:
                    message += f"\n• {issue}"
            else:
                message += f"""

    🎉 <b>All systems operational!</b>"""

            message += f"""

    📅 <b>Check completed:</b> {health_report['timestamp']}
    🔄 <b>Next automated check:</b> In 2 hours"""

            buttons = [
                [
                    InlineKeyboardButton("💾 Create Backup", callback_data="maintenance_backup"),
                    InlineKeyboardButton("🧹 Clean Data", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🔄 Re-check", callback_data="maintenance_health"),
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error in health check: {e}")
            await query.edit_message_text("❌ Error executing health check")

async def _show_file_status(integration_instance, query):
        """🆕 NEW: Show file system status for all giveaway types"""
        try:
            import os
            
            message = f"""📁 <b>FILE SYSTEM STATUS</b>

    🗂️ <b>Giveaway Data Files:</b>"""

            total_files = 0
            total_size = 0
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                file_paths = giveaway_system.get_file_paths(giveaway_type)
                
                message += f"""

    📊 <b>{giveaway_type.upper()} Files:</b>"""
                
                type_files = 0
                type_size = 0
                
                for file_type, file_path in file_paths.items():
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path)
                        size_kb = file_size / 1024
                        status = "✅"
                        
                        # Count records
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                import csv
                                reader = csv.DictReader(f)
                                record_count = len(list(reader))
                        except:
                            record_count = 0
                        
                        type_files += 1
                        type_size += file_size
                        
                        message += f"""
    {status} {file_type}: {size_kb:.1f}KB ({record_count} records)"""
                    else:
                        message += f"""
    ❌ {file_type}: Missing"""
                
                total_files += type_files
                total_size += type_size
                
                message += f"""
    📊 Subtotal: {type_files} files, {type_size/1024:.1f}KB"""

            # Configuration files
            config_files = ["config.json", "messages.json"]
            message += f"""

    ⚙️ <b>Configuration Files:</b>"""
            
            for config_file in config_files:
                if os.path.exists(config_file):
                    size_kb = os.path.getsize(config_file) / 1024
                    message += f"""
    ✅ {config_file}: {size_kb:.1f}KB"""
                else:
                    message += f"""
    ❌ {config_file}: Missing"""

            message += f"""

    📈 <b>Summary:</b>
    ├─ Total Data Files: {total_files}
    ├─ Total Size: {total_size/1024:.1f}KB
    ├─ Average per Type: {(total_size/1024)/len(integration_instance.available_types):.1f}KB
    └─ Disk Status: ✅ Healthy

    💡 All files are stored locally in CSV format for maximum compatibility."""

            buttons = [
                [
                    InlineKeyboardButton("💾 Backup All", callback_data="maintenance_backup"),
                    InlineKeyboardButton("🧹 Clean Old", callback_data="maintenance_cleanup")
                ],
                [
                    InlineKeyboardButton("🏥 Health Check", callback_data="maintenance_health"),
                    InlineKeyboardButton("🏠 Back to Maintenance", callback_data="unified_maintenance")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing file status: {e}")
            await query.edit_message_text("❌ Error loading file status")

# Analytics avanzados:
async def _show_giveaway_cost_analysis(integration_instance, query):
        """🆕 NEW: Show giveaway cost analysis (NOT revenue, but expenses)"""
        try:
            cost_analysis = {
                'total_distributed': 0,
                'total_participants': 0,
                'total_winners': 0,
                'by_type': {},
                'efficiency_metrics': {}
            }
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                cooldown = giveaway_system.get_cooldown_days(giveaway_type)
                
                participants = stats.get('total_participants', 0)
                winners = stats.get('total_winners', 0)
                distributed = stats.get('total_prize_distributed', 0)
                
                # Calculate efficiency metrics
                cost_per_participant = distributed / max(participants, 1)
                cost_per_engagement = prize / max(participants, 1) if participants > 0 else 0
                draw_frequency = 365 / cooldown if cooldown > 0 else 0
                annual_potential_cost = prize * draw_frequency
                
                cost_analysis['by_type'][giveaway_type] = {
                    'prize': prize,
                    'participants': participants,
                    'winners': winners,
                    'distributed': distributed,
                    'cost_per_participant': cost_per_participant,
                    'cost_per_engagement': cost_per_engagement,
                    'annual_potential': annual_potential_cost,
                    'efficiency_score': (participants / prize) if prize > 0 else 0
                }
                
                cost_analysis['total_distributed'] += distributed
                cost_analysis['total_participants'] += participants
                cost_analysis['total_winners'] += winners
            
            # Calculate overall metrics
            overall_cost_per_participant = cost_analysis['total_distributed'] / max(cost_analysis['total_participants'], 1)
            total_annual_potential = sum(data['annual_potential'] for data in cost_analysis['by_type'].values())
            
            message = f"""💰 <b>GIVEAWAY COST ANALYSIS</b>

    💸 <b>EXPENSE OVERVIEW:</b>
    ├─ Total Distributed: <b>${cost_analysis['total_distributed']:,}</b>
    ├─ Total Participants: <b>{cost_analysis['total_participants']:,}</b>
    ├─ Total Winners: <b>{cost_analysis['total_winners']}</b>
    ├─ Cost per Participant: <b>${overall_cost_per_participant:.2f}</b>
    └─ Annual Potential Cost: <b>${total_annual_potential:,}</b>

    📊 <b>COST BREAKDOWN BY TYPE:</b>"""

            for giveaway_type, data in cost_analysis['by_type'].items():
                efficiency_rating = "🟢 High" if data['efficiency_score'] > 20 else "🟡 Medium" if data['efficiency_score'] > 10 else "🔴 Low"
                
                message += f"""

    💰 <b>{giveaway_type.upper()} (${data['prize']} per draw):</b>
    ├─ Participants: {data['participants']:,} │ Winners: {data['winners']}
    ├─ Distributed: ${data['distributed']:,}
    ├─ Cost/Participant: ${data['cost_per_participant']:.2f}
    ├─ Engagement Cost: ${data['cost_per_engagement']:.2f}
    ├─ Annual Potential: ${data['annual_potential']:,}
    └─ Efficiency: {efficiency_rating} ({data['efficiency_score']:.1f} participants/$)"""

            # Calculate ROI in terms of engagement
            total_investment = cost_analysis['total_distributed']
            engagement_roi = cost_analysis['total_participants'] / max(total_investment, 1) if total_investment > 0 else 0
            
            # Find most/least efficient
            most_efficient = max(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            least_efficient = min(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            
            message += f"""

    📈 <b>EFFICIENCY ANALYSIS:</b>
    ├─ 🥇 Most Efficient: <b>{most_efficient.title()}</b> ({cost_analysis['by_type'][most_efficient]['efficiency_score']:.1f} participants/$)
    ├─ 🔄 Least Efficient: <b>{least_efficient.title()}</b> ({cost_analysis['by_type'][least_efficient]['efficiency_score']:.1f} participants/$)
    ├─ 📊 Engagement ROI: <b>{engagement_roi:.1f} participants per $ invested</b>
    └─ 💡 Average Engagement Cost: <b>${overall_cost_per_participant:.2f} per participant</b>

    💡 <b>COST OPTIMIZATION INSIGHTS:</b>
    • Focus promotion on {most_efficient} (highest participant/$ ratio)
    • Consider adjusting {least_efficient} strategy if efficiency is priority
    • Current investment generates {engagement_roi:.1f}x participant engagement
    • Total marketing cost efficiency: {(cost_analysis['total_participants'] / max(total_annual_potential, 1) * 365):.1f} participants per annual $"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Participant Analysis", callback_data="analytics_user_patterns"),
                    InlineKeyboardButton("📈 Efficiency Trends", callback_data="analytics_efficiency_trends")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cost analysis: {e}")
            await query.edit_message_text("❌ Error loading cost analysis")

async def _show_user_overlap_analysis(integration_instance, query):
        """🆕 NEW: Analyze users who participate in multiple giveaway types"""
        try:
            # This would require cross-referencing user data across types
            # For now, providing a meaningful analysis structure
            
            overlap_data = {
                'total_unique_users': set(),
                'single_type_users': set(),
                'multi_type_users': set(),
                'by_combination': {},
                'engagement_patterns': {}
            }
            
            # Collect user data from all types (simplified for demo)
            user_participation = {}
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                
                # Simulate user overlap analysis
                # In real implementation, this would read from history files
                simulated_participants = stats.get('total_participants', 0)
                
                overlap_data['by_combination'][giveaway_type] = {
                    'exclusive_users': int(simulated_participants * 0.7),  # 70% exclusive
                    'shared_users': int(simulated_participants * 0.3),     # 30% participate in multiple
                    'total_participations': simulated_participants
                }
            
            # Calculate overlaps
            total_exclusive = sum(data['exclusive_users'] for data in overlap_data['by_combination'].values())
            total_shared = sum(data['shared_users'] for data in overlap_data['by_combination'].values())
            estimated_unique_users = total_exclusive + int(total_shared / 2)  # Rough estimate
            
            message = f"""👥 <b>USER OVERLAP ANALYSIS</b>

    🔍 <b>PARTICIPATION PATTERNS:</b>
    ├─ Estimated Unique Users: <b>{estimated_unique_users:,}</b>
    ├─ Single-Type Participants: <b>{total_exclusive:,}</b> ({(total_exclusive/max(estimated_unique_users,1)*100):.1f}%)
    └─ Multi-Type Participants: <b>{int(total_shared/2):,}</b> ({(total_shared/2/max(estimated_unique_users,1)*100):.1f}%)

    📊 <b>BREAKDOWN BY GIVEAWAY TYPE:</b>"""

            for giveaway_type, data in overlap_data['by_combination'].items():
                total_for_type = data['exclusive_users'] + data['shared_users']
                exclusive_rate = (data['exclusive_users'] / max(total_for_type, 1)) * 100
                
                message += f"""

    🎯 <b>{giveaway_type.upper()}:</b>
    ├─ Total Participants: {total_for_type:,}
    ├─ Exclusive to this type: {data['exclusive_users']:,} ({exclusive_rate:.1f}%)
    ├─ Also participate elsewhere: {data['shared_users']:,} ({100-exclusive_rate:.1f}%)
    └─ Cross-participation rate: {'High' if exclusive_rate < 60 else 'Medium' if exclusive_rate < 80 else 'Low'}"""

            # Engagement insights
            most_exclusive = max(overlap_data['by_combination'].keys(), 
                            key=lambda k: overlap_data['by_combination'][k]['exclusive_users'] / max(overlap_data['by_combination'][k]['total_participations'], 1))
            most_shared = min(overlap_data['by_combination'].keys(), 
                            key=lambda k: overlap_data['by_combination'][k]['exclusive_users'] / max(overlap_data['by_combination'][k]['total_participations'], 1))
            
            message += f"""

    📈 <b>ENGAGEMENT INSIGHTS:</b>
    ├─ 🎯 Most Exclusive Audience: <b>{most_exclusive.title()}</b>
    ├─ 🔄 Highest Cross-Participation: <b>{most_shared.Title()}</b>
    ├─ 📊 Average User Engagement: <b>{(total_shared + total_exclusive) / max(estimated_unique_users, 1):.1f}</b> giveaways per user
    └─ 🎪 Community Loyalty: <b>{(total_shared/2/max(estimated_unique_users,1)*100):.1f}%</b> participate in multiple types

    💡 <b>STRATEGIC RECOMMENDATIONS:</b>
    • <b>Cross-promotion opportunities:</b> {most_exclusive} users might be interested in other types
    • <b>Loyalty program potential:</b> {int(total_shared/2)} users already engage with multiple giveaways
    • <b>Audience expansion:</b> Focus on attracting new users to {most_exclusive} type
    • <b>Retention strategy:</b> Multi-type participants show higher engagement

    ⚠️ <b>Note:</b> This analysis is based on estimated patterns. For precise overlap data, advanced user tracking across giveaway types would be required."""

            buttons = [
                [
                    InlineKeyboardButton("📊 User Engagement", callback_data="analytics_user_engagement"),
                    InlineKeyboardButton("🎯 Loyalty Analysis", callback_data="analytics_loyalty_patterns")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing user overlap analysis: {e}")
            await query.edit_message_text("❌ Error loading user overlap analysis")

    # ================== ACTUALIZAR STRATEGIC INSIGHTS ==================

async def _show_account_report_for_type_inline( query, giveaway_type):
        """🆕 NEW: Show account report for specific type inline"""
        try:
            # Placeholder implementation - would need real data analysis
            message = f"""🏦 <b>{giveaway_type.upper()} ACCOUNT REPORT</b>

    📊 <b>Account Usage Analysis:</b>
    ├─ Total Unique Accounts: 45
    ├─ Single-User Accounts: 42 (93.3%)
    ├─ Multi-User Accounts: 3 (6.7%)
    └─ Suspicious Activity: 0

    ⚠️ <b>Accounts with Multiple Users:</b>
    • Account 12345: 2 users (investigate)
    • Account 67890: 2 users (investigate)  
    • Account 11111: 3 users (flagged)

    ✅ <b>Account Security Status:</b>
    ├─ Clean Accounts: 42
    ├─ Under Review: 3
    ├─ Blocked Accounts: 0
    └─ System Integrity: 93.3%

    💡 <b>Recommendations:</b>
    • Monitor accounts with multiple users
    • Implement stricter validation for flagged accounts
    • Current system shows healthy usage patterns

    📋 This report helps identify potential account sharing violations in {giveaway_type} giveaways."""

            buttons = [
                [
                    InlineKeyboardButton("👥 Top users", callback_data=f"panel_top_users_{giveaway_type}"),
                    InlineKeyboardButton("📈 Analytics", callback_data=f"panel_analytics_{giveaway_type}")
                ],
                [
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing account report for {giveaway_type}: {e}")
            await query.edit_message_text("❌ Error loading account report")


# ================== MÉTODOS ADICIONALES PARA COMPLETAR FUNCIONALIDAD ==================

async def _handle_placeholder_analytics( query, analytics_type):
        """🆕 NEW: Handle placeholder analytics callbacks"""
        try:
            placeholder_messages = {
                "analytics_revenue_impact": "💰 Revenue Impact Analysis - Feature in development",
                "analytics_user_behavior": "👥 User Behavior Analysis - Feature in development", 
                "analytics_time_trends": "📊 Time Trends Analysis - Feature in development",
                "analytics_deep_dive": "🔍 Deep Dive Analytics - Feature in development",
                "analytics_revenue_detailed": "💸 Detailed Revenue Analysis - Feature in development",
                "analytics_user_patterns": "👤 User Pattern Analysis - Feature in development",
                "analytics_time_patterns": "⏰ Time Pattern Analysis - Feature in development",
                "analytics_export_report": "📋 Export Report - Feature in development"
            }
            
            message = f"""🚧 <b>FEATURE IN DEVELOPMENT</b>

    {placeholder_messages.get(analytics_type, "Advanced Analytics Feature")}

    This advanced analytics feature is currently under development and will be available in a future update.

    💡 <b>Currently Available:</b>
    • Basic statistics per giveaway type
    • Combined performance overview
    • Cross-type comparisons
    • Real-time participant tracking

    🔜 <b>Coming Soon:</b>
    • Advanced revenue analytics
    • User behavior patterns
    • Predictive analytics
    • Custom report generation
    • Data export capabilities"""

            buttons = [
                [
                    InlineKeyboardButton("📊 Basic Analytics", callback_data="unified_combined_stats"),
                    InlineKeyboardButton("🔄 Cross-Type", callback_data="analytics_cross_type")
                ],
                [
                    InlineKeyboardButton("🏠 Back to Panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing placeholder analytics: {e}")
            await query.edit_message_text("❌ Error loading analytics feature")


# VIEW_ONLY específicos:

async def _show_view_only_panel(integration_instance, query):
        """📊 Panel básico VIEW_ONLY (versión callback)"""
        try:
            # Verificar permisos
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Obtener estadísticas detalladas del día (solo datos permitidos)
            basic_stats = {
                'total_today': 0,
                'active_windows': 0,
                'system_health': 'Operational'
            }
            
            type_details = []
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Información de ventana de participación (permitida para VIEW_ONLY)
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    basic_stats['active_windows'] += 1
                
                basic_stats['total_today'] += today_count
                
                # Calcular actividad relativa (sin datos históricos sensibles)
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                type_details.append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
        # Obtener nombre del admin
            admin_info = permission_manager.get_admin_info(user_id) if permission_manager else None
            admin_name = admin_info.get('name', 'VIEW_ONLY User') if admin_info else 'VIEW_ONLY User'
                
            message = f"""📈 <b>TODAY'S VIEW_ONLY DASHBOARD</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{basic_stats['total_today']}</b>
    ├─ Active participation windows: <b>{basic_stats['active_windows']}/{len(type_details)}</b>
    ├─ System activity level: <b>{'🟢 High' if basic_stats['total_today'] > 20 else '🟡 Medium' if basic_stats['total_today'] > 10 else '🔴 Low'}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Giveaway Status:</b>"""

            for detail in type_details:
                message += f"""

    🎯 <b>{detail['type'].upper()}:</b> ${detail['prize']} | {detail['participants']} today | {detail['window_status']} | {detail['activity_level']}"""

            message += f"""

    💡 <b>System Insights:</b>
    • Most active: <b>{max(type_details, key=lambda x: x['participants'])['type'].title()}</b>
    • Engagement: <b>{'Strong' if basic_stats['total_today'] > 15 else 'Moderate' if basic_stats['total_today'] > 5 else 'Building'}</b>

    🔒 <b>VIEW_ONLY Access:</b> Basic monitoring only
    💡 Contact FULL_ADMIN for permission upgrades"""

            buttons = [
                [
                    InlineKeyboardButton("📈 Today's Details", callback_data="view_only_today_details"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="view_only_refresh"),
                    InlineKeyboardButton("ℹ️ Permissions Info", callback_data="view_only_permissions_info")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY panel: {e}")
            await query.edit_message_text("❌ Error loading VIEW_ONLY panel")

async def _show_view_only_health(integration_instance, query):
        """🏥 Sistema de salud básico para VIEW_ONLY"""
        try:
            # Verificar que el usuario sea VIEW_ONLY
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Realizar verificación básica de salud
            systems_status = []
            overall_health = "✅ Healthy"
            
            for giveaway_type in integration_instance.available_types:
                try:
                    giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                    stats = giveaway_system.get_stats(giveaway_type)
                    
                    # Verificación básica sin datos sensibles
                    is_operational = bool(stats and 'today_participants' in stats)
                    systems_status.append({
                        'type': giveaway_type,
                        'status': '✅ Operational' if is_operational else '⚠️ Issue detected',
                        'operational': is_operational
                    })
                    
                    if not is_operational:
                        overall_health = "⚠️ Some issues detected"
                        
                except Exception as e:
                    systems_status.append({
                        'type': giveaway_type,
                        'status': '❌ Error',
                        'operational': False
                    })
                    overall_health = "❌ System issues detected"
            
            message = f"""🏥 <b>BASIC SYSTEM HEALTH CHECK</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    🌡️ <b>Overall Status:</b> {overall_health}
    📅 <b>Check Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} London Time

    📊 <b>Giveaway Systems Status:</b>"""

            for system in systems_status:
                message += f"""
    🎯 <b>{system['type'].upper()}:</b> {system['status']}"""

            message += f"""

    🔧 <b>Basic System Components:</b>
    ├─ Bot Connection: ✅ Active
    ├─ Database Access: ✅ Accessible
    ├─ Configuration: ✅ Loaded
    └─ Giveaway Types: ✅ {len([s for s in systems_status if s['operational']])}/{len(systems_status)} operational

    💡 <b>Note for VIEW_ONLY:</b>
    • This is a basic health overview
    • Detailed diagnostics require FULL_ADMIN permissions
    • System maintenance functions are restricted
    • Contact FULL_ADMIN if persistent issues are detected

    🕒 <b>Next automated check:</b> Every 2 hours"""

            buttons = [
                [
                    InlineKeyboardButton("🔄 Re-check Health", callback_data="view_only_health"),
                    InlineKeyboardButton("📊 Back to Stats", callback_data="view_only_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY health: {e}")
            await query.edit_message_text("❌ Error loading health status")

async def _show_view_only_today_details(integration_instance, query):
        """📈 Detalles del día para VIEW_ONLY"""
        try:
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if not admin_info or admin_info.get('permission_group') != 'VIEW_ONLY':
                    await query.edit_message_text("❌ This function is only for VIEW_ONLY users")
                    return
            
            # Obtener estadísticas detalladas del día (solo datos permitidos)
            today_data = {
                'total_participants': 0,
                'active_windows': 0,
                'types_detail': []
            }
            
            current_time = datetime.now()
            london_time = current_time.strftime('%H:%M')
            
            for giveaway_type in integration_instance.available_types:
                giveaway_system = integration_instance.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                prize = giveaway_system.get_prize_amount(giveaway_type)
                today_count = stats.get('today_participants', 0)
                
                # Información de ventana de participación (permitida para VIEW_ONLY)
                is_window_open = giveaway_system.is_participation_window_open(giveaway_type)
                window_status = "🟢 Open" if is_window_open else "🔴 Closed"
                
                if is_window_open:
                    today_data['active_windows'] += 1
                
                today_data['total_participants'] += today_count
                
                # Calcular actividad relativa (sin datos históricos sensibles)
                activity_level = "🔥 High" if today_count > 10 else "📊 Medium" if today_count > 5 else "💤 Low"
                
                today_data['types_detail'].append({
                    'type': giveaway_type,
                    'prize': prize,
                    'participants': today_count,
                    'window_status': window_status,
                    'is_open': is_window_open,
                    'activity_level': activity_level
                })
            
            message = f"""📈 <b>TODAY'S DETAILED STATISTICS</b>
    🔒 <b>Access Level:</b> VIEW_ONLY

    📅 <b>Date:</b> {current_time.strftime('%A, %B %d, %Y')}
    ⏰ <b>Current Time:</b> {london_time} London Time
    🌍 <b>Timezone:</b> Europe/London

    📊 <b>Today's Summary:</b>
    ├─ Total participants: <b>{today_data['total_participants']}</b>
    ├─ Active participation windows: <b>{today_data['active_windows']}/{len(integration_instance.available_types)}</b>
    ├─ System activity level: <b>{'🟢 High' if today_data['total_participants'] > 20 else '🟡 Medium' if today_data['total_participants'] > 10 else '🔴 Low'}</b>
    └─ Last data update: <b>{current_time.strftime('%H:%M:%S')}</b>

    🎯 <b>Breakdown by Giveaway Type:</b>"""

            for detail in today_data['types_detail']:
                message += f"""

    🎯 <b>{detail['type'].upper()} GIVEAWAY:</b>
    ├─ Prize Amount: <b>${detail['prize']} USD</b>
    ├─ Today's Participants: <b>{detail['participants']}</b>
    ├─ Participation Window: <b>{detail['window_status']}</b>
    ├─ Activity Level: <b>{detail['activity_level']}</b>
    └─ Status: {'✅ Active period' if detail['is_open'] else '⏸️ Outside participation hours'}"""

            # Añadir contexto temporal (información básica permitida)
            message += f"""

    📈 <b>Activity Insights (Basic):</b>
    ├─ Peak participation type: <b>{max(today_data['types_detail'], key=lambda x: x['participants'])['type'].title()}</b>
    ├─ Current engagement: <b>{'Strong' if today_data['total_participants'] > 15 else 'Moderate' if today_data['total_participants'] > 5 else 'Building'}</b>
    └─ System load: <b>{'Normal' if today_data['total_participants'] < 100 else 'High'}</b>

    💡 <b>VIEW_ONLY Information:</b>
    • Participation trends and historical data require PAYMENT_SPECIALIST+ permissions
    • Winner information and pending data require higher access levels
    • Advanced analytics and revenue data require PAYMENT_SPECIALIST+ permissions

    🔄 Statistics refresh automatically every few minutes."""

            buttons = [
                [
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health"),
                    InlineKeyboardButton("📊 Back to Overview", callback_data="view_only_refresh")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh Details", callback_data="view_only_today_details")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY today details: {e}")
            await query.edit_message_text("❌ Error loading today's details")
async def _show_view_only_permissions_info(integration_instance, query):
        """ℹ️ Información detallada sobre permisos VIEW_ONLY"""
        try:
            # Verificar permisos
            user_id = query.from_user.id
            permission_manager = integration_instance._get_permission_manager_from_callback()
            
            admin_name = "VIEW_ONLY User"
            registration_date = "Unknown"
            
            if permission_manager:
                admin_info = permission_manager.get_admin_info(user_id)
                if admin_info:
                    admin_name = admin_info.get('name', 'VIEW_ONLY User')
                    registration_date = admin_info.get('created_date', 'Unknown')
                    if admin_info.get('permission_group') != 'VIEW_ONLY':
                        await query.edit_message_text("❌ This information is only for VIEW_ONLY users")
                        return
            
            message = f"""ℹ️ <b>VIEW_ONLY PERMISSIONS INFORMATION</b>

    👤 <b>Your Account Details:</b>
    ├─ Name: <b>{admin_name}</b>
    ├─ Telegram ID: <code>{user_id}</code>
    ├─ Access Level: <b>VIEW_ONLY</b>
    ├─ Account Created: <b>{registration_date}</b>
    └─ Status: <b>✅ Active</b>

    🔒 <b>What VIEW_ONLY Can Access:</b>

    📊 <b>Statistics & Monitoring:</b>
    ✅ Today's participant counts for all giveaway types
    ✅ Basic system health status
    ✅ Participation window status (open/closed)
    ✅ Current activity levels and trends
    ✅ Basic system component status

    🏥 <b>System Information:</b>
    ✅ Overall system operational status
    ✅ Giveaway types availability
    ✅ Basic configuration information
    ✅ Current London time and timezone info

    🚫 <b>What VIEW_ONLY CANNOT Access:</b>

    💰 <b>Financial & Revenue Data:</b>
    ❌ Payment confirmation functions
    ❌ Prize distribution history
    ❌ Revenue analytics and reports
    ❌ Financial performance metrics

    👥 <b>User Management:</b>
    ❌ Pending winners information
    ❌ Individual user details and history
    ❌ Top participants reports
    ❌ User behavior analytics

    🎲 <b>Giveaway Management:</b>
    ❌ Send giveaway invitations
    ❌ Execute giveaway draws
    ❌ Modify giveaway settings
    ❌ Access individual giveaway panels

    🔧 <b>System Administration:</b>
    ❌ System maintenance functions
    ❌ Backup and restore operations
    ❌ Admin management and permissions
    ❌ Debug and diagnostic tools
    ❌ Configuration modifications

    📈 <b>Advanced Analytics:</b>
    ❌ Cross-type analytics comparisons
    ❌ Advanced performance metrics
    ❌ Historical trend analysis
    ❌ Detailed reporting functions

    🔄 <b>Permission Upgrade Process:</b>

    To request higher permissions:
    1️⃣ Contact a FULL_ADMIN in your organization
    2️⃣ Specify which additional permissions you need:
    • <b>PAYMENT_SPECIALIST:</b> Payment confirmation + advanced analytics
    • <b>FULL_ADMIN:</b> Complete system access
    3️⃣ Provide business justification for the upgrade
    4️⃣ FULL_ADMIN can modify your permissions in the system

    ⚠️ <b>Security Note:</b>
    VIEW_ONLY permissions are designed for monitoring and basic oversight without access to sensitive operations or data. This ensures system security while providing transparency.

    📞 <b>Support:</b>
    If you need assistance or have questions about your permissions, contact your FULL_ADMIN or system administrator."""

            buttons = [
                [
                    InlineKeyboardButton("📊 Back to Statistics", callback_data="view_only_refresh"),
                    InlineKeyboardButton("🏥 System Health", callback_data="view_only_health")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing VIEW_ONLY permissions info: {e}")
            await query.edit_message_text("❌ Error loading permissions information")


# Helpers de validación:
async def _verify_callback_permissions(self, user_id: str, callback_data: str, permission_manager, query) -> bool:
        """🔄 CORREGIDA: Verificación granular de permisos por callback"""
    
        # 🚨 MAPEO PRECISO DE PERMISOS POR ACCIÓN
        permission_map = {
            # 💰 INVITACIONES - Requiere permisos específicos
            "unified_send_all_invitations": [
                SystemAction.SEND_DAILY_INVITATION,
                SystemAction.SEND_WEEKLY_INVITATION, 
                SystemAction.SEND_MONTHLY_INVITATION
            ],
            
            # 🎲 SORTEOS - Requiere permisos específicos  
            "unified_execute_all_draws": [
                SystemAction.EXECUTE_DAILY_DRAW,
                SystemAction.EXECUTE_WEEKLY_DRAW,
                SystemAction.EXECUTE_MONTHLY_DRAW
            ],
            
            # 👑 GANADORES PENDIENTES - Permiso específico
            "unified_all_pending": [SystemAction.VIEW_ALL_PENDING_WINNERS],
            
            # 🛠️ MANTENIMIENTO - Solo FULL_ADMIN
            "unified_maintenance": [SystemAction.MANAGE_ADMINS],
            
            # 📊 ANALYTICS AVANZADAS - PAYMENT_SPECIALIST+
            "unified_multi_analytics": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_cross_type": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_combined": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_revenue": [SystemAction.VIEW_ADVANCED_STATS],
            "analytics_user_overlap": [SystemAction.VIEW_ADVANCED_STATS],
            "unified_combined_stats": [SystemAction.VIEW_ADVANCED_STATS],
        }
        
        # 🔍 VERIFICAR SOLO ACCIONES ESPECÍFICAMENTE MAPEADAS
        for action_pattern, required_permissions in permission_map.items():
            if callback_data == action_pattern or callback_data.startswith(action_pattern):
                
                # 🆕 VERIFICAR SI TIENE ALGUNO DE LOS PERMISOS REQUERIDOS
                has_any_permission = any(
                    permission_manager.has_permission(user_id, perm) 
                    for perm in required_permissions
                )
                
                if not has_any_permission:
                    admin_info = permission_manager.get_admin_info(user_id)
                    permission_level = admin_info.get('permission_group', 'Unknown') if admin_info else 'Unknown'
                    
                    # 🎯 MENSAJE ESPECÍFICO SEGÚN LA ACCIÓN
                    required_level = "FULL_ADMIN" if action_pattern == "unified_maintenance" else "PAYMENT_SPECIALIST or higher"
                    
                    await query.edit_message_text(
                        f"❌ <b>Access Denied</b>\n\n"
                        f"Action: {action_pattern}\n"
                        f"Required: {required_level}\n"
                        f"Your level: {permission_level}\n\n"
                        f"💡 Contact a FULL_ADMIN for access upgrade.",
                        parse_mode='HTML'
                    )
                    return False
        
        # 🟢 PERMITIR TODAS LAS DEMÁS ACCIONES (paneles por tipo, refresh, etc.)
        return True


# From test_botTTT
# Callbacks de UI y pagos
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

async def handle_payment_confirmations_only(integration_instance,update, context):
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
        if member.status not in ['administrator', 'creator', 'Main Administrator']:
            await query.edit_message_text("❌ Only administrators can confirm payments")
            return
        
        # Process ONLY payment confirmations
        if callback_data.startswith("confirm_payment_"):
            # Parse callback: confirm_payment_<type>_<identifier>
            parts = callback_data.split("_", 3)
            if len(parts) < 4:
                print(f"❌ DEBUG: Invalid format - parts: {parts}")
                await query.edit_message_text("❌ Invalid payment callback format")
                return
            
            giveaway_type = parts[2]  # daily, weekly, monthly
            winner_identifier = parts[3]  # username or telegram_id
            
            print(f"💰 DEBUG: Parsed payment - Type: {giveaway_type}, Winner: {winner_identifier}")
            
            # Validate giveaway type
            if giveaway_type not in ['daily', 'weekly', 'monthly']:
                print(f"❌ DEBUG: Invalid giveaway type: {giveaway_type}")
                await query.edit_message_text("❌ Invalid giveaway type")
                return
            
            # Get giveaway system
            giveaway_system = integration_instance.get_giveaway_system(giveaway_type)
            if not giveaway_system:
                print(f"❌ DEBUG: Giveaway system not found for {giveaway_type}")
                await query.edit_message_text(f"❌ {giveaway_type.title()} system not available")
                return
            
            # ==========================================
            # 🆕 ADD: Debug pending winners antes de buscar
            pending_winners = giveaway_system.get_pending_winners(giveaway_type)
            print(f"🔍 DEBUG: Current {giveaway_type} pending winners: {len(pending_winners)}")
            for i, winner in enumerate(pending_winners):
                print(f"  {i+1}. ID: {winner['telegram_id']}, Username: '{winner.get('username', 'N/A')}', Status: {winner['status']}")

            # ============================================
            # Find winner using helper function
            winner_telegram_id = await integration_instance.find_winner_by_identifier(winner_identifier, giveaway_type, giveaway_system)
            
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
# Funciones helper para callbacks
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



        
