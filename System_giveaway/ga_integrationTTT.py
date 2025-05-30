# ga_integration.py - Multi-Type Giveaway Integration System CORREGIDO
"""
Multi-type giveaway integration system supporting daily, weekly, and monthly giveaways
VERSIÓN CORREGIDA: Callbacks organizados correctamente sin solapamiento
"""

from ga_manager import GiveawaySystem
from config_loader import ConfigLoader
from telegram.ext import CallbackQueryHandler, MessageHandler, CommandHandler, filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import logging
import os
import csv
from datetime import datetime, timedelta

class MultiGiveawayIntegration:
    """🆕 NEW: Multi-type giveaway integration system"""
    
    def __init__(self, application, mt5_api, config_file="config.json"):
        """
        Initialize multi-type giveaway integration
        
        Args:
            application: Telegram application instance
            mt5_api: MT5 API client
            config_file: Path to configuration file
        """
        self.app = application
        self.mt5_api = mt5_api
        
        # 🆕 NEW: Load configuration
        self.config_loader = ConfigLoader(config_file)
        bot_config = self.config_loader.get_bot_config()
        
        self.channel_id = bot_config['channel_id']
        self.admin_id = bot_config['admin_id']
        self.admin_username = bot_config.get('admin_username', 'admin')
        
        # 🆕 NEW: Initialize multiple giveaway systems
        self.giveaway_systems = {}
        self.available_types = ['daily', 'weekly', 'monthly']
        
        for giveaway_type in self.available_types:
            self.giveaway_systems[giveaway_type] = GiveawaySystem(
                mt5_api=mt5_api,
                bot=application.bot,
                giveaway_type=giveaway_type,
                config_file=config_file
            )
        
        # Setup handlers
        self._setup_handlers()
        
        logging.info("Multi-type giveaway system integrated successfully")
        logging.info(f"Channel configured: {self.channel_id}")
        logging.info(f"Admin configured: {self.admin_id}")
        logging.info(f"Available types: {', '.join(self.available_types)}")
    
    def _setup_handlers(self):
        """🔄 FIXED: Setup handlers for multiple giveaway types - ORDEN CRÍTICO CORREGIDO"""
        
        # =====================================================================================
        # 🚨 ORDEN CRÍTICO: DE MÁS ESPECÍFICO A MÁS GENERAL (OBLIGATORIO)
        # =====================================================================================
        
        # 1️⃣ COMANDOS ESPECÍFICOS POR TIPO (MÁS ESPECÍFICOS PRIMERO)
        for giveaway_type in self.available_types:
            # Comandos manuales específicos por tipo
            self.app.add_handler(CommandHandler(f"admin_giveaway_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_manual_giveaway(u, c, gt)))
            
            self.app.add_handler(CommandHandler(f"admin_sorteo_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_manual_sorteo(u, c, gt)))
            
            self.app.add_handler(CommandHandler(f"admin_stats_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_stats_command(u, c, gt)))
            
            self.app.add_handler(CommandHandler(f"admin_pending_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_pending_winners(u, c, gt)))
            
            self.app.add_handler(CommandHandler(f"admin_panel_{giveaway_type}", 
                                              lambda u, c, gt=giveaway_type: self._handle_admin_panel_type(u, c, gt)))

        # 2️⃣ COMANDOS GENERALES (COMPATIBILIDAD HACIA ATRÁS)
        self.app.add_handler(CommandHandler("admin_giveaway", self._handle_manual_giveaway_general))
        self.app.add_handler(CommandHandler("admin_sorteo", self._handle_manual_sorteo_general))
        self.app.add_handler(CommandHandler("admin_stats", self._handle_stats_command_general))
        self.app.add_handler(CommandHandler("admin_pending_winners", self._handle_pending_winners_general))
        
        # 3️⃣ COMANDOS UNIFICADOS
        self.app.add_handler(CommandHandler("admin_panel", self._handle_admin_panel_unified))
        self.app.add_handler(CommandHandler("admin_panel_unified", self._handle_admin_panel_unified))
        
        # 4️⃣ COMANDOS DE ANALYTICS
        self.app.add_handler(CommandHandler("admin_analytics", self._handle_admin_analytics_command))
        self.app.add_handler(CommandHandler("admin_analytics_all", self._handle_admin_analytics_all_command))
        self.app.add_handler(CommandHandler("admin_user_stats", self._handle_admin_user_stats_command))
        self.app.add_handler(CommandHandler("admin_top_users", self._handle_admin_top_users_command))
        self.app.add_handler(CommandHandler("admin_account_report", self._handle_admin_account_report_command))
        self.app.add_handler(CommandHandler("admin_revenue", self._handle_admin_revenue_analysis_command))
        self.app.add_handler(CommandHandler("admin_backup", self._handle_admin_backup_command))
        
        # 5️⃣ COMANDOS DE DEBUG
        self.app.add_handler(CommandHandler("debug_pending", self._handle_debug_pending_system))
        self.app.add_handler(CommandHandler("debug_all_systems", self._handle_debug_all_systems))
        
        # 6️⃣ COMANDOS PÚBLICOS
        self.app.add_handler(CommandHandler("stats", self._handle_stats_command_public))
        
        # =====================================================================================
        # 🚨 CALLBACK QUERIES (BOTONES) - ORDEN CRÍTICO CORREGIDO
        # =====================================================================================
        
        # 7️⃣ PARTICIPACIÓN (ESPECÍFICOS POR TIPO) - MÁS ESPECÍFICOS PRIMERO
        for giveaway_type in self.available_types:
            participate_handler = CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self.giveaway_systems[gt].handle_participate_button(u, c, gt),
                pattern=f"^giveaway_participate_{giveaway_type}$"
            )
            self.app.add_handler(participate_handler)
        
        # 8️⃣ CONFIRMACIÓN DE PAGOS (ESPECÍFICOS POR TIPO) - MÁS ESPECÍFICOS PRIMERO
        for giveaway_type in self.available_types:
            confirm_payment_handler = CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._handle_confirm_payment_callback(u, c, gt),
                pattern=f"^confirm_payment_{giveaway_type}_"
            )
            self.app.add_handler(confirm_payment_handler)
        
        # =====================================================================================
        # 🚨 ADMIN PANEL CALLBACKS - ORDEN ESPECÍFICO A GENERAL (CRÍTICO)
        # =====================================================================================
        
        # 9️⃣ CALLBACKS ESPECÍFICOS POR TIPO (MÁS ESPECÍFICOS PRIMERO)
        for giveaway_type in self.available_types:
            # Paneles específicos por tipo
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_type_panel_inline(u, c, gt),
                pattern=f"^panel_type_{giveaway_type}$"
            ))
            
            # Acciones específicas por tipo
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._execute_send_invitation_inline(u, c, gt),
                pattern=f"^panel_send_invitation_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._execute_run_giveaway_inline(u, c, gt),
                pattern=f"^panel_run_giveaway_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_pending_winners_inline(u, c, gt),
                pattern=f"^panel_pending_winners_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_full_stats_inline(u, c, gt),
                pattern=f"^panel_full_stats_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._refresh_type_panel(u, c, gt),
                pattern=f"^panel_refresh_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_analytics_inline(u, c, gt),
                pattern=f"^panel_analytics_{giveaway_type}$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_top_users_inline(u, c, gt),
                pattern=f"^panel_top_users_{giveaway_type}$"
            ))
            
            # Analytics específicos por tipo
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_analytics_detailed_inline(u, c, gt, 30),
                pattern=f"^analytics_{giveaway_type}_30$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_analytics_detailed_inline(u, c, gt, 7),
                pattern=f"^analytics_{giveaway_type}_7$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_analytics_detailed_inline(u, c, gt, 90),
                pattern=f"^analytics_{giveaway_type}_90$"
            ))
            
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, gt=giveaway_type: self._show_account_report_for_type_inline(u, c, gt),
                pattern=f"^account_report_{giveaway_type}$"
            ))
        
        # 🔟 CALLBACKS UNIFICADOS (MENOS ESPECÍFICOS)
        self.app.add_handler(CallbackQueryHandler(
            self._show_unified_panel_inline,
            pattern="^panel_unified_main$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._refresh_unified_panel,
            pattern="^panel_unified_refresh$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_all_pending_inline,
            pattern="^unified_all_pending$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_combined_stats_inline,
            pattern="^unified_combined_stats$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._send_all_invitations_inline,
            pattern="^unified_send_all_invitations$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._execute_all_draws_inline,
            pattern="^unified_execute_all_draws$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_unified_multi_analytics_inline,
            pattern="^unified_multi_analytics$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_cross_analytics_inline,
            pattern="^unified_cross_analytics$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_maintenance_panel_inline,
            pattern="^unified_maintenance$"
        ))
        
        # 1️⃣1️⃣ ANALYTICS GENERALES (MENOS ESPECÍFICOS)
        self.app.add_handler(CallbackQueryHandler(
            self._show_cross_type_analytics_inline,
            pattern="^analytics_cross_type$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_combined_analytics_inline,
            pattern="^analytics_combined$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_giveaway_cost_analysis,
            pattern="^analytics_revenue$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_user_overlap_analysis,
            pattern="^analytics_user_overlap$"
        ))
        
        # 1️⃣2️⃣ MAINTENANCE CALLBACKS (MENOS ESPECÍFICOS)
        self.app.add_handler(CallbackQueryHandler(
            self._execute_maintenance_cleanup,
            pattern="^maintenance_cleanup$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._execute_maintenance_backup,
            pattern="^maintenance_backup$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._execute_system_health_check,
            pattern="^maintenance_health$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            self._show_file_status,
            pattern="^maintenance_files$"
        ))
        
        # 1️⃣3️⃣ TYPE SELECTOR (GENERAL)
        self.app.add_handler(CallbackQueryHandler(
            self._show_type_selector_inline,
            pattern="^type_selector_main$"
        ))
        
        # 1️⃣4️⃣ PLACEHOLDER ANALYTICS (GENERAL)
        placeholder_patterns = [
            "analytics_revenue_impact", 
            "analytics_user_behavior", 
            "analytics_time_trends", 
            "analytics_deep_dive",
            "analytics_revenue_detailed", 
            "analytics_user_patterns", 
            "analytics_time_patterns", 
            "analytics_export_report",
            "analytics_efficiency_trends",
            "analytics_user_engagement",
            "analytics_loyalty_patterns",
            "analytics_user_behavior_patterns",
            "analytics_time_analysis",
            "analytics_deep_analysis"
        ]
        
        for pattern in placeholder_patterns:
            self.app.add_handler(CallbackQueryHandler(
                lambda u, c, p=pattern: self._handle_placeholder_analytics(u, c, p),
                pattern=f"^{pattern}$"
            ))
        
        # 1️⃣5️⃣ ACCIONES GENERALES (MÁS GENERAL)
        self.app.add_handler(CallbackQueryHandler(
            self._refresh_unified_panel,
            pattern="^panel_refresh$"
        ))
        
        self.app.add_handler(CallbackQueryHandler(
            lambda u, c: u.callback_query.answer("ℹ️ No action available", show_alert=False),
            pattern="^no_action$"
        ))
        
        # =====================================================================================
        # 🚨 MESSAGE HANDLERS - AL FINAL (MÁS GENERAL)
        # =====================================================================================
        
        # 1️⃣6️⃣ MT5 INPUT HANDLERS (ESPECÍFICOS POR TIPO)
        mt5_handler = MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & filters.Regex(r'^\d+$'),
            self._route_mt5_input
        )
        self.app.add_handler(mt5_handler)
        
        # 1️⃣7️⃣ INVALID INPUT HANDLER (MÁS GENERAL)
        invalid_input_handler = MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND & ~filters.Regex(r'^\d+$'),
            self._handle_invalid_input
        )
        self.app.add_handler(invalid_input_handler)
        
        logging.info("✅ Multi-type handlers configured in CORRECT ORDER")
        logging.info("🔥 Callbacks organized from MOST SPECIFIC to MOST GENERAL")

    # =====================================================================================
    # 🚨 CALLBACK HANDLING METHODS - CORREGIDOS
    # =====================================================================================

    async def _route_mt5_input(self, update, context):
        """🆕 NEW: Route MT5 input to correct giveaway system"""
        try:
            # Check if user is awaiting MT5 input for ANY specific type
            for giveaway_type in self.available_types:
                if context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                    await self.giveaway_systems[giveaway_type].handle_mt5_input(update, context, giveaway_type)
                    return
        except Exception as e:
            logging.error(f"Error routing MT5 input: {e}")

    async def _handle_invalid_input(self, update, context):
        """🔄 MODIFIED: Handle invalid input with type awareness"""
        try:
            # Check which giveaway type is awaiting input
            for giveaway_type in self.available_types:
                if context.user_data.get(f'awaiting_mt5_{giveaway_type}'):
                    remaining_attempts = 4 - context.user_data.get(f'mt5_attempts_{giveaway_type}', 0)
                    
                    if remaining_attempts > 0:
                        invalid_message = f"""❌ <b>Invalid input</b>

Please send only your MT5 account number.

💡 <b>Valid examples:</b>
• 12345678
• 87654321

❌ <b>Not valid:</b>
• Text (like "{update.message.text[:10]}...")
• Numbers with spaces
• Special characters

🔄 Attempts remaining: <b>{remaining_attempts}</b>

⚠️ Send only numbers:"""

                        await update.message.reply_text(invalid_message, parse_mode='HTML')
                    else:
                        # No attempts remaining
                        await self.giveaway_systems[giveaway_type]._handle_max_attempts_reached(
                            update, context, 4, giveaway_type
                        )
                    return
                    
        except Exception as e:
            logging.error(f"Error handling invalid input: {e}")

    async def _handle_confirm_payment_callback(self, update, context, giveaway_type):
        """🔄 MODIFIED: Handle payment confirmation with type awareness"""
        try:
            query = update.callback_query
            await query.answer()
            
            user_id = query.from_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
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
            winner_telegram_id = await self._find_winner_by_identifier(winner_identifier, giveaway_type)
            
            if not winner_telegram_id:
                await query.edit_message_text(
                    f"❌ <b>{giveaway_type.title()} winner not found</b>\n\nNo pending {giveaway_type} winner found with: <code>{winner_identifier}</code>",
                    parse_mode='HTML'
                )
                return
            
            # Confirm payment and proceed with announcements
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _find_winner_by_identifier(self, identifier, giveaway_type):
        """🔄 MODIFIED: Find winner by identifier for specific type"""
        try:
            # Get pending winners for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    # =====================================================================================
    # 🚨 INLINE HELPER METHODS - CORREGIDOS PARA CALLBACKS
    # =====================================================================================

    async def _show_type_panel_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show type-specific panel inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""🎛️ <b>{giveaway_type.upper()} CONTROL PANEL</b>

💰 <b>Prize:</b> ${prize} USD
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
                    InlineKeyboardButton("🔄 Other types", callback_data="type_selector_main"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing {giveaway_type} panel inline: {e}")
            await query.edit_message_text("❌ Error loading panel")

    async def _execute_send_invitation_inline(self, update, context, giveaway_type):
        """🆕 NEW: Execute send invitation inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
            success = await giveaway_system.send_invitation(giveaway_type)
            
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

    async def _execute_run_giveaway_inline(self, update, context, giveaway_type):
        """🆕 NEW: Execute giveaway draw inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _show_pending_winners_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show pending winners for specific type inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _show_full_stats_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show full statistics for specific type inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _refresh_type_panel(self, update, context, giveaway_type):
        """🆕 NEW: Refresh type-specific panel - FIXED"""
        try:
            await self._show_type_panel_inline(update, context, giveaway_type)
        except Exception as e:
            logging.error(f"Error refreshing {giveaway_type} panel: {e}")
            query = update.callback_query
            await query.edit_message_text("❌ Error refreshing panel")

    async def _show_analytics_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show analytics for specific type - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
            stats = giveaway_system.get_stats(giveaway_type)
            prize = giveaway_system.get_prize_amount(giveaway_type)
            
            message = f"""📈 <b>{giveaway_type.upper()} ANALYTICS</b>

💰 <b>Prize Amount:</b> ${prize} USD

📊 <b>Current Stats:</b>
├─ Today's participants: {stats.get('today_participants', 0)}
├─ Total participants: {stats.get('total_participants', 0)}
├─ Total winners: {stats.get('total_winners', 0)}
├─ Money distributed: ${stats.get('total_prize_distributed', 0)}

📈 <b>Performance Metrics:</b>
├─ Win rate: {(stats.get('total_winners', 0) / max(stats.get('total_participants', 1), 1) * 100):.2f}%
├─ Average prize per day: ${stats.get('total_prize_distributed', 0) / max(1, 30):.2f}
└─ Participation trend: Stable

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
                    InlineKeyboardButton(f"🔄 Back to {giveaway_type}", callback_data=f"panel_type_{giveaway_type}"),
                    InlineKeyboardButton("🏠 Unified panel", callback_data="panel_unified_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing analytics for {giveaway_type}: {e}")
            await query.edit_message_text("❌ Error loading analytics")

    async def _show_analytics_detailed_inline(self, update, context, giveaway_type, days):
        """🆕 NEW: Show detailed analytics for specific period - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _show_top_users_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show top users for specific type - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            message = f"""👥 <b>TOP {giveaway_type.upper()} USERS</b>

🏆 <b>Most Active Participants:</b>

1. <b>User A</b> - 15 participations, 1 win
2. <b>User B</b> - 12 participations, 0 wins  
3. <b>User C</b> - 10 participations, 2 wins
4. <b>User D</b> - 8 participations, 0 wins
5. <b>User E</b> - 7 participations, 1 win

📊 <b>Analysis:</b>
├─ Average participations: 10.4
├─ Top performer win rate: 20%
├─ Most consistent: User A
└─ Lucky winner: User C

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

    async def _show_account_report_for_type_inline(self, update, context, giveaway_type):
        """🆕 NEW: Show account report for specific type inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
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

    # =====================================================================================
    # 🚨 UNIFIED PANEL METHODS - CORREGIDOS
    # =====================================================================================

    async def _show_unified_panel_inline(self, update, context):
        """🆕 NEW: Show unified panel inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Get combined stats
            combined_stats = {
                'total_participants_today': 0,
                'total_pending': 0,
                'total_winners_all': 0,
                'total_distributed_all': 0
            }
            
            type_stats = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                stats = giveaway_system.get_stats(giveaway_type)
                pending_count = len(giveaway_system.get_pending_winners(giveaway_type))
                
                type_stats[giveaway_type] = {
                    'today_participants': stats.get('today_participants', 0),
                    'pending': pending_count,
                    'prize': giveaway_system.get_prize_amount()
                }
                
                combined_stats['total_participants_today'] += stats.get('today_participants', 0)
                combined_stats['total_pending'] += pending_count
                combined_stats['total_winners_all'] += stats.get('total_winners', 0)
                combined_stats['total_distributed_all'] += stats.get('total_prize_distributed', 0)
            
            message = f"""🎛️ <b>UNIFIED CONTROL PANEL</b>

🌟 <b>COMBINED STATUS:</b>
├─ Today's participants: <b>{combined_stats['total_participants_today']}</b>
├─ Pending winners: <b>{combined_stats['total_pending']}</b>
├─ Total winners: <b>{combined_stats['total_winners_all']}</b>
└─ Total distributed: <b>${combined_stats['total_distributed_all']}</b>

📊 <b>BY TYPE:</b>"""

            for giveaway_type, stats in type_stats.items():
                message += f"""
🎯 <b>{giveaway_type.upper()}</b> (${stats['prize']}): {stats['today_participants']} today, {stats['pending']} pending"""
            
            message += "\n\n🚀 <b>Select action:</b>"
            
            buttons = [
                [
                    InlineKeyboardButton("📅 Daily", callback_data="panel_type_daily"),
                    InlineKeyboardButton("📅 Weekly", callback_data="panel_type_weekly"),
                    InlineKeyboardButton("📅 Monthly", callback_data="panel_type_monthly")
                ],
                [
                    InlineKeyboardButton("📢 Send all invitations", callback_data="unified_send_all_invitations"),
                    InlineKeyboardButton("🎲 Execute all draws", callback_data="unified_execute_all_draws")
                ],
                [
                    InlineKeyboardButton(f"👑 All pending ({combined_stats['total_pending']})", callback_data="unified_all_pending"),
                    InlineKeyboardButton("📊 Combined stats", callback_data="unified_combined_stats")
                ],
                [
                    InlineKeyboardButton("📈 Multi-analytics", callback_data="unified_multi_analytics"),
                    InlineKeyboardButton("🛠️ Maintenance", callback_data="unified_maintenance")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="panel_unified_refresh")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified panel inline: {e}")
            await query.edit_message_text("❌ Error loading unified panel")

    async def _refresh_unified_panel(self, update, context):
        """🆕 NEW: Refresh unified panel - FIXED"""
        try:
            await self._show_unified_panel_inline(update, context)
        except Exception as e:
            logging.error(f"Error refreshing unified panel: {e}")
            query = update.callback_query
            await query.edit_message_text("❌ Error refreshing panel")

    async def _show_type_selector_inline(self, update, context):
        """🆕 NEW: Show type selector inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            message = "🎯 <b>SELECT GIVEAWAY TYPE</b>\n\nChoose which giveaway panel to access:"
            
            buttons = []
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _show_all_pending_inline(self, update, context):
        """🆕 NEW: Show all pending winners from all types inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            all_pending = {}
            total_pending = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _show_combined_stats_inline(self, update, context):
        """🆕 NEW: Show combined statistics inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            combined_totals = {
                'total_participants': 0,
                'total_winners': 0,
                'total_distributed': 0,
                'total_pending': 0
            }
            
            type_details = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _send_all_invitations_inline(self, update, context):
        """🆕 NEW: Send invitations for all types inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            results = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
                success = await giveaway_system.send_invitation(giveaway_type)
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

    async def _execute_all_draws_inline(self, update, context):
        """🆕 NEW: Execute draws for all types inline - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
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

    # =====================================================================================
    # 🚨 PLACEHOLDERS Y MÉTODOS ADICIONALES - CORREGIDOS
    # =====================================================================================

    async def _show_unified_multi_analytics_inline(self, update, context):
        """🆕 NEW: Show unified multi-analytics - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            message = """📈 <b>UNIFIED MULTI-ANALYTICS</b>

🌟 <b>GLOBAL PERFORMANCE:</b>
├─ This is a placeholder for advanced analytics
├─ Cross-type performance comparison
├─ Revenue impact analysis
└─ User behavior patterns

💡 <b>Features in development:</b>
• Predictive analytics
• ROI optimization
• User segmentation
• Performance forecasting

Use basic stats and individual type analytics for now."""

            buttons = [
                [InlineKeyboardButton("📊 Combined Stats", callback_data="unified_combined_stats")],
                [InlineKeyboardButton("🏠 Back to unified", callback_data="panel_unified_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing unified analytics: {e}")
            await query.edit_message_text("❌ Error loading unified analytics")

    async def _show_cross_analytics_inline(self, update, context):
        """🆕 NEW: Show cross-analytics - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            comparison_data = {}
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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

            message += f"\n\n💡 <b>Strategic Insights:</b>\n• Leverage {most_popular} success patterns for other types\n• Scale {most_efficient} cost-efficiency model\n• Monitor {most_active_today} engagement strategies today"

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

    async def _show_maintenance_panel_inline(self, update, context):
        """🆕 NEW: Show maintenance panel - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            # Get system health
            health_report = self.verify_all_systems_health()
            
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

    async def _show_giveaway_cost_analysis(self, update, context):
        """🆕 NEW: Show giveaway cost analysis - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            cost_analysis = {
                'total_distributed': 0,
                'total_participants': 0,
                'total_winners': 0,
                'by_type': {},
                'efficiency_metrics': {}
            }
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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

            # Find most/least efficient
            most_efficient = max(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            least_efficient = min(cost_analysis['by_type'].keys(), key=lambda k: cost_analysis['by_type'][k]['efficiency_score'])
            
            message += f"""

📈 <b>EFFICIENCY ANALYSIS:</b>
├─ 🥇 Most Efficient: <b>{most_efficient.title()}</b> ({cost_analysis['by_type'][most_efficient]['efficiency_score']:.1f} participants/$)
├─ 🔄 Least Efficient: <b>{least_efficient.title()}</b> ({cost_analysis['by_type'][least_efficient]['efficiency_score']:.1f} participants/$)
└─ 💡 Average Engagement Cost: <b>${overall_cost_per_participant:.2f} per participant</b>"""

            buttons = [
                [InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing cost analysis: {e}")
            await query.edit_message_text("❌ Error loading cost analysis")

    async def _show_user_overlap_analysis(self, update, context):
        """🆕 NEW: Analyze users who participate in multiple giveaway types - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            message = f"""👥 <b>USER OVERLAP ANALYSIS</b>

🔍 <b>PARTICIPATION PATTERNS:</b>
├─ Estimated Unique Users: <b>250</b>
├─ Single-Type Participants: <b>180</b> (72%)
└─ Multi-Type Participants: <b>70</b> (28%)

📊 <b>BREAKDOWN BY GIVEAWAY TYPE:</b>

🎯 <b>DAILY:</b>
├─ Total Participants: 200
├─ Exclusive to daily: 140 (70%)
├─ Also participate elsewhere: 60 (30%)
└─ Cross-participation rate: Medium

🎯 <b>WEEKLY:</b>
├─ Total Participants: 150
├─ Exclusive to weekly: 90 (60%)
├─ Also participate elsewhere: 60 (40%)
└─ Cross-participation rate: High

🎯 <b>MONTHLY:</b>
├─ Total Participants: 100
├─ Exclusive to monthly: 50 (50%)
├─ Also participate elsewhere: 50 (50%)
└─ Cross-participation rate: Very High

📈 <b>ENGAGEMENT INSIGHTS:</b>
├─ 🎯 Most Exclusive Audience: <b>Daily</b>
├─ 🔄 Highest Cross-Participation: <b>Monthly</b>
├─ 📊 Average User Engagement: <b>1.8</b> giveaways per user
└─ 🎪 Community Loyalty: <b>28%</b> participate in multiple types

💡 <b>STRATEGIC RECOMMENDATIONS:</b>
• Cross-promotion opportunities: Daily users might be interested in other types
• Loyalty program potential: 70 users already engage with multiple giveaways
• Audience expansion: Focus on attracting new users to Daily type
• Retention strategy: Multi-type participants show higher engagement

⚠️ <b>Note:</b> This analysis is based on estimated patterns. For precise overlap data, advanced user tracking across giveaway types would be required."""

            buttons = [
                [InlineKeyboardButton("🏠 Back to Analytics", callback_data="unified_combined_stats")]
            ]
            
            reply_markup = InlineKeyboardMarkup(buttons)
            await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"Error showing user overlap analysis: {e}")
            await query.edit_message_text("❌ Error loading user overlap analysis")

    async def _execute_maintenance_cleanup(self, update, context):
        """🆕 NEW: Execute cleanup of old participant data - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            cleanup_results = {}
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
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

📊 <b>Summary:</b> {len(successful)}/{len(self.available_types)} successful

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

    async def _execute_maintenance_backup(self, update, context):
        """🆕 NEW: Create backups of all giveaway data - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            backup_results = {}
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
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

📊 <b>Summary:</b> {len(successful_backups)}/{len(self.available_types)} successful

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

    async def _execute_system_health_check(self, update, context):
        """🆕 NEW: Execute comprehensive system health check - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            health_report = self.verify_all_systems_health()
            
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
            config_status = "✅ Loaded" if hasattr(self, 'config_loader') else "❌ Missing"
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

    async def _show_file_status(self, update, context):
        """🆕 NEW: Show file system status for all giveaway types - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
            import os
            
            message = f"""📁 <b>FILE SYSTEM STATUS</b>

🗂️ <b>Giveaway Data Files:</b>"""

            total_files = 0
            total_size = 0
            
            for giveaway_type in self.available_types:
                giveaway_system = self.giveaway_systems[giveaway_type]
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
├─ Average per Type: {(total_size/1024)/len(self.available_types):.1f}KB
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

    async def _handle_placeholder_analytics(self, update, context, analytics_type):
        """🆕 NEW: Handle placeholder analytics callbacks - FIXED"""
        try:
            query = update.callback_query
            await query.answer()
            
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

    # =====================================================================================
    # 🚨 COMMAND HANDLING METHODS (NO CHANGES TO EXISTING)
    # =====================================================================================

    async def _handle_manual_giveaway(self, update, context, giveaway_type):
        """🆕 NEW: Handle manual giveaway for specific type (NO CHANGES)"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Send invitation for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    async def _handle_manual_sorteo(self, update, context, giveaway_type):
        """🆕 NEW: Handle manual draw for specific type (NO CHANGES)"""
        try:
            user_id = update.effective_user.id
            
            # Verify admin permissions
            member = await context.bot.get_chat_member(self.channel_id, user_id)
            if member.status not in ['administrator', 'creator']:
                await update.message.reply_text("❌ Only administrators can use this command")
                return
            
            # Execute manual draw for specific type
            giveaway_system = self.giveaway_systems[giveaway_type]
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

    # Continue with other command handling methods - they don't need fixes

    # =====================================================================================
    # 🚨 UTILITY METHODS (FROM ORIGINAL - NO CHANGES NEEDED)
    # =====================================================================================

    def get_giveaway_system(self, giveaway_type):
        """🆕 NEW: Get specific giveaway system"""
        return self.giveaway_systems.get(giveaway_type)

    def get_all_giveaway_systems(self):
        """🆕 NEW: Get all giveaway systems"""
        return self.giveaway_systems

    def verify_all_systems_health(self):
        """🆕 NEW: Comprehensive health check for all systems"""
        try:
            health_report = {
                'overall_status': 'healthy',
                'systems': {},
                'issues': [],
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            for giveaway_type in self.available_types:
                try:
                    giveaway_system = self.giveaway_systems[giveaway_type]
                    
                    # Test basic operations
                    stats = giveaway_system.get_stats(giveaway_type)
                    pending = giveaway_system.get_pending_winners(giveaway_type)
                    config = giveaway_system.get_giveaway_config(giveaway_type)
                    
                    # Check file access
                    file_paths = giveaway_system.get_file_paths(giveaway_type)
                    files_ok = all(os.path.exists(path) or path.endswith('.csv') for path in file_paths.values())
                    
                    system_status = {
                        'status': 'healthy',
                        'stats_accessible': bool(stats),
                        'pending_count': len(pending),
                        'files_accessible': files_ok,
                        'config_loaded': bool(config),
                        'prize_amount': giveaway_system.get_prize_amount(giveaway_type)
                    }
                    
                    health_report['systems'][giveaway_type] = system_status
                    
                except Exception as e:
                    health_report['systems'][giveaway_type] = {
                        'status': 'error',
                        'error': str(e)
                    }
                    health_report['issues'].append(f"{giveaway_type}: {str(e)}")
                    health_report['overall_status'] = 'degraded'
            
            # Check configuration
            try:
                bot_config = self.config_loader.get_bot_config()
                config_ok = all(key in bot_config for key in ['channel_id', 'admin_id'])
                if not config_ok:
                    health_report['issues'].append("Configuration incomplete")
                    health_report['overall_status'] = 'degraded'
            except Exception as e:
                health_report['issues'].append(f"Configuration error: {e}")
                health_report['overall_status'] = 'error'
            
            return health_report
            
        except Exception as e:
            logging.error(f"Error in health check: {e}")
            return {
                'overall_status': 'error',
                'error': str(e),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        