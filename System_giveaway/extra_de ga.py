# def _initialize_files(self):
    #     """Crear archivos y directorios necesarios si no existen"""
    #     os.makedirs(self.data_dir, exist_ok=True)
        
    #     # Archivo de participantes diarios
    #     if not os.path.exists(self.participants_file):
    #         with open(self.participants_file, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
        
    #     # Archivo de ganadores histórico
    #     if not os.path.exists(self.winners_file):
    #         with open(self.winners_file, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['date', 'telegram_id', 'username', 'mt5_account', 'prize', 'giveaway_type'])
        
    #     # Archivo de historial permanente
    #     if not os.path.exists(self.history_file):
    #         with open(self.history_file, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'won_prize', 'prize_amount', 'giveaway_type'])
        
    #     # NUEVO: Archivo de ganadores pendientes de pago
    #     if not os.path.exists(self.pending_winners_file):
    #         with open(self.pending_winners_file, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by'])
    
    # def _load_messages(self):
    #     """Cargar plantillas de mensajes desde JSON"""
    #     try:
    #         if os.path.exists(self.messages_file):
    #             with open(self.messages_file, 'r', encoding='utf-8') as f:
    #                 self.messages = json.load(f)
    #             self.logger.info("Mensajes cargados desde archivo JSON")
    #         else:
    #             # Crear mensajes por defecto si no existe el archivo
    #             self._create_default_messages()
    #             self._save_messages()
    #             self.logger.info("Mensajes por defecto creados")
    #     except Exception as e:
    #         self.logger.error(f"Error cargando mensajes: {e}")
    #         self._create_default_messages()
    
    # def _create_default_messages(self):
    #     """Crear mensajes por defecto si no existe el archivo JSON"""
    #     self.messages = {
    #         "invitation": "🎁 <b>GIVEAWAY DIARIO $250 USD</b> 🎁\n\n💰 <b>Premio:</b> $250 USD\n⏰ <b>Sorteo:</b> Todos los días a las 5:00 PM\n\n<b>📋 Requisitos para participar:</b>\n✅ Cuenta MT5 LIVE activa\n✅ Saldo mínimo $100 USD\n✅ Ser miembro de este canal\n\n👆 Presiona el botón para participar",
    #         "success": "✅ <b>¡Registrado exitosamente!</b>\n\nEstás participando en el giveaway diario de $250 USD.\n\n🍀 ¡Buena suerte!\n\n⏰ El sorteo es todos los días a las 5:00 PM",
    #         "already_registered": "ℹ️ Ya estás registrado para el giveaway actual.\n\n🍀 ¡Buena suerte en el sorteo de hoy!",
    #         "insufficient_balance": "❌ <b>Saldo insuficiente</b>\n\nSe requiere un saldo mínimo de $100 USD\nTu saldo actual: <b>${balance}</b>\n\n💡 Deposita más fondos para poder participar en futuros giveaways.",
    #         "not_live": "❌ <b>Cuenta no válida</b>\n\nSolo cuentas MT5 LIVE pueden participar en el giveaway.\n\n💡 Verifica que hayas ingresado el número correcto de tu cuenta LIVE.",
    #         "account_not_found": "❌ <b>Cuenta no encontrada</b>\n\nLa cuenta MT5 #{account} no fue encontrada en nuestros registros.\n\n💡 Verifica que el número de cuenta sea correcto.",
    #         "not_channel_member": "❌ <b>No eres miembro del canal</b>\n\nDebe ser miembro del canal principal para participar.\n\n💡 Únete al canal y vuelve a intentar.",
    #         "winner_announcement": "🏆 <b>¡GANADOR DEL GIVEAWAY DIARIO!</b> 🏆\n\n🎉 Felicidades: @{username}\n💰 Premio: <b>${prize} USD \n👥 Total participantes: <b>{total_participants}</b>\n\n📅 Próximo sorteo: Mañana a las 5:00 PM\n\n🎁 ¡Participa tú también!",
    #         "no_eligible_participants": "⚠️ No hay participantes elegibles para el sorteo de hoy.\n\n📢 ¡Únete al próximo giveaway!",
    #         "request_mt5": "🔢 <b>Ingresa tu número de cuenta MT5</b>\n\nPor favor, envía el número de tu cuenta MT5 LIVE para verificar que cumples con los requisitos del giveaway.\n\n💡 Ejemplo: 12345678"
    #     }
    
    # def _save_messages(self):
    #     """Guardar mensajes en archivo JSON"""
    #     try:
    #         os.makedirs(os.path.dirname(self.messages_file), exist_ok=True)
    #         with open(self.messages_file, 'w', encoding='utf-8') as f:
    #             json.dump(self.messages, f, indent=2, ensure_ascii=False)
    #     except Exception as e:
    #         self.logger.error(f"Error guardando mensajes: {e}")

    # # ================== INVITACIÓN Y PARTICIPACIÓN ==================
    # # ================== INVITACIÓN Y PARTICIPACIÓN ==================
    
    # async def send_invitation(self):
    #     """Envía mensaje de invitación al giveaway con botón directo al bot"""
    #     try:
    #         bot_info = await self.bot.get_me()
    #         bot_username = bot_info.username
            
    #         # Enlace que abre chat privado automáticamente
    #         participate_link = f"https://t.me/{bot_username}?start=participate"
            
    #         keyboard = [[InlineKeyboardButton("🎯 PARTICIPAR AHORA", url=participate_link)]]
    #         reply_markup = InlineKeyboardMarkup(keyboard)
            
    #         message = self.messages.get("invitation", "Giveaway activo - Presiona PARTICIPAR")
            
    #         await self.bot.send_message(
    #             chat_id=self.channel_id,
    #             text=message,
    #             reply_markup=reply_markup,
    #             parse_mode='HTML'
    #         )
            
    #         self.logger.info("Mensaje de invitación con enlace directo enviado al canal")
    #         return True
            
    #     except Exception as e:
    #         self.logger.error(f"Error enviando invitación: {e}")
    #         return False
    
    # async def handle_participate_button(self, update, context):
    #     """Maneja cuando un usuario presiona el botón PARTICIPAR (callback query)"""
    #     try:
    #         query = update.callback_query
    #         await query.answer()
            
    #         user = query.from_user
    #         user_id = user.id
            
    #         # PRIMERA VERIFICACIÓN: ¿Ya está registrado HOY?
    #         if self._is_already_registered(user_id):
    #             await self.bot.send_message(
    #                 chat_id=user_id,
    #                 text=self.messages.get("already_registered", "Ya estás registrado"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # SEGUNDA VERIFICACIÓN: ¿Ya tiene proceso pendiente?
    #         if self._has_pending_registration(user_id, context):
    #             await self.bot.send_message(
    #                 chat_id=user_id,
    #                 text=self.messages.get("registration_in_progress", "Ya tienes un registro en proceso"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # TERCERA VERIFICACIÓN: Membresía del canal
    #         if not await self._check_channel_membership(user_id):
    #             await self.bot.send_message(
    #                 chat_id=user_id,
    #                 text=self.messages.get("not_channel_member", "No eres miembro del canal"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # Solicitar número de cuenta MT5
    #         await self.bot.send_message(
    #             chat_id=user_id,
    #             text=self.messages.get("request_mt5", "Ingresa tu número de cuenta MT5"),
    #             parse_mode='HTML'
    #         )
            
    #         # Guardar estado del usuario para el siguiente mensaje
    #         context.user_data['awaiting_mt5'] = True
    #         context.user_data['user_info'] = {
    #             'id': user.id,
    #             'username': user.username,
    #             'first_name': user.first_name
    #         }
            
    #     except Exception as e:
    #         self.logger.error(f"Error manejando botón participar: {e}")
    
    # async def handle_mt5_input(self, update, context):
    #     """Maneja cuando el usuario envía su número de cuenta MT5"""
    #     try:
    #         if not context.user_data.get('awaiting_mt5'):
    #             return
            
    #         mt5_account = update.message.text.strip()
    #         user_info = context.user_data.get('user_info')
            
    #         # NUEVO: Inicializar contador de intentos si no existe
    #         if 'mt5_attempts' not in context.user_data:
    #             context.user_data['mt5_attempts'] = 0
            
    #         # NUEVO: Incrementar contador de intentos
    #         context.user_data['mt5_attempts'] += 1
    #         max_attempts = 4  # Máximo 4 intentos
    #         remaining_attempts = max_attempts - context.user_data['mt5_attempts']
            
    #         # Validar formato de cuenta
    #         if not mt5_account.isdigit():
    #             # Si aún tiene intentos disponibles
    #             if remaining_attempts > 0:
    #                 retry_message = self.messages.get("invalid_format_retry", "❌ Formato inválido. Intentos restantes: {remaining_attempts}").format(
    #                     remaining_attempts=remaining_attempts
    #                 )
    #                 await update.message.reply_text(retry_message, parse_mode='HTML')
    #                 return  # MANTENER el estado awaiting_mt5 para siguiente intento
    #             else:
    #                 # Se acabaron los intentos
    #                 await self._handle_max_attempts_reached(update, context, max_attempts)
    #                 return
            
    #         # Procesar participación (formato válido)
    #         success = await self.process_participation_with_retry(user_info, mt5_account, update, context, remaining_attempts, max_attempts)
            
    #         # Si no fue exitoso y aún hay intentos, mantener el estado
    #         if not success and remaining_attempts > 0:
    #             return  # MANTENER awaiting_mt5 para siguiente intento
            
    #         # Limpiar estado solo si fue exitoso O se acabaron los intentos
    #         context.user_data.pop('awaiting_mt5', None)
    #         context.user_data.pop('user_info', None)
    #         context.user_data.pop('mt5_attempts', None)
            
    #     except Exception as e:
    #         self.logger.error(f"Error procesando entrada MT5: {e}")
    #         await update.message.reply_text(
    #             self.messages.get("error_internal", "❌ Error interno. Intenta nuevamente."),
    #             parse_mode='HTML'
    #         )

    # async def process_participation_with_retry(self, user_info, mt5_account, update, context, remaining_attempts, max_attempts):
    #     """Procesar participación con manejo de reintentos"""
    #     try:
    #         user_id = user_info['id']
            
    #         # VALIDACIÓN 1: ¿Usuario ya registrado HOY? (doble verificación)
    #         if self._is_already_registered(user_id):
    #             await update.message.reply_text(
    #                 self.messages.get("already_registered", "Ya estás registrado"),
    #                 parse_mode='HTML'
    #             )
    #             return True  # Exitoso (ya registrado)
            
    #         # VALIDACIÓN 2: ¿Cuenta MT5 ya usada HOY por otro usuario?
    #         account_used_today, other_user_id = self._is_account_already_used_today(mt5_account)
    #         if account_used_today:
    #             if remaining_attempts > 0:
    #                 retry_message = f"❌ <b>Cuenta ya registrada hoy</b>\n\nEsta cuenta MT5 ya fue usada hoy por otro usuario.\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Intenta con una cuenta diferente:"
    #                 await update.message.reply_text(retry_message, parse_mode='HTML')
    #                 return False  # No exitoso, pero puede reintentar
    #             else:
    #                 await self._handle_max_attempts_reached(update, context, max_attempts)
    #                 return True  # Terminar proceso
            
    #         # VALIDACIÓN 3: ¿Cuenta MT5 pertenece históricamente a otro usuario?
    #         is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(mt5_account, user_id)
    #         if is_other_user_account:
    #             if remaining_attempts > 0:
    #                 retry_message = f"❌ <b>Cuenta pertenece a otro usuario</b>\n\nEsta cuenta MT5 fue registrada anteriormente por otro participante.\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Usa una cuenta MT5 que sea exclusivamente tuya:"
    #                 await update.message.reply_text(retry_message, parse_mode='HTML')
    #                 return False  # No exitoso, pero puede reintentar
    #             else:
    #                 await self._handle_max_attempts_reached(update, context, max_attempts)
    #                 return True  # Terminar proceso
            
    #         # VALIDACIÓN 4: Validar cuenta MT5 con API
    #         validation_result = self.validate_mt5_account(mt5_account)
            
    #         if not validation_result['valid']:
    #             error_type = validation_result['error_type']
                
    #             if remaining_attempts > 0:
    #                 # Dar oportunidad de reintentar con mensaje específico
    #                 if error_type == 'not_found':
    #                     retry_message = f"❌ <b>Cuenta no encontrada</b>\n\nLa cuenta MT5 #{mt5_account} no fue encontrada en nuestros registros.\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Verifica el número e intenta nuevamente:"
    #                 elif error_type == 'not_live':
    #                     retry_message = f"❌ <b>Cuenta no válida</b>\n\nSolo cuentas MT5 LIVE pueden participar en el giveaway.\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Usa una cuenta LIVE e intenta nuevamente:"
    #                 elif error_type == 'insufficient_balance':
    #                     balance = validation_result.get('balance', 0)
    #                     retry_message = f"❌ <b>Saldo insuficiente</b>\n\nSe requiere un saldo mínimo de $100 USD\nTu saldo actual: <b>${balance}</b>\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Usa una cuenta con saldo suficiente:"
    #                 else:
    #                     retry_message = f"❌ <b>Error de verificación</b>\n\nNo pudimos verificar tu cuenta en este momento.\n\n🔄 Intentos restantes: <b>{remaining_attempts}</b>\n\n💡 Intenta con otra cuenta:"
                    
    #                 await update.message.reply_text(retry_message, parse_mode='HTML')
    #                 return False  # No exitoso, pero puede reintentar
    #             else:
    #                 # Sin intentos restantes
    #                 await self._handle_max_attempts_reached(update, context, max_attempts)
    #                 return True  # Terminar proceso
            
    #         # VALIDACIÓN 5: Verificar membresía del canal (seguridad adicional)
    #         if not await self._check_channel_membership(user_id):
    #             await update.message.reply_text(
    #                 self.messages.get("not_channel_member", "No eres miembro del canal"),
    #                 parse_mode='HTML'
    #             )
    #             return True  # Terminar proceso (no es problema de formato)
            
    #         # TODAS LAS VALIDACIONES PASARON - Guardar participante
    #         participant_data = {
    #             'telegram_id': user_id,
    #             'username': user_info.get('username', ''),
    #             'first_name': user_info.get('first_name', ''),
    #             'mt5_account': mt5_account,
    #             'balance': validation_result['balance'],
    #             'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    #             'status': 'active'
    #         }
            
    #         self._save_participant(participant_data)
            
    #         # Obtener historial de cuentas del usuario para mensaje personalizado
    #         user_history = self.get_user_account_history(user_id)
            
    #         if len(user_history) > 1:
    #             # Usuario tiene historial previo
    #             unique_accounts = len(set(acc['mt5_account'] for acc in user_history))
    #             success_message = self.messages.get("success_with_history", "Registrado exitosamente").format(
    #                 account=mt5_account,
    #                 total_participations=len(user_history),
    #                 unique_accounts=unique_accounts
    #             )
    #         else:
    #             # Primera vez del usuario
    #             success_message = self.messages.get("success_first_time", "¡Primera participación!")
            
    #         await update.message.reply_text(success_message, parse_mode='HTML')
            
    #         self.logger.info(f"Usuario {user_id} registrado exitosamente para giveaway con cuenta {mt5_account}. Intento: {context.user_data.get('mt5_attempts', 1)}")
            
    #         return True  # Exitoso
            
    #     except Exception as e:
    #         self.logger.error(f"Error procesando participación con reintentos: {e}")
    #         await update.message.reply_text(
    #             self.messages.get("error_internal", "Error interno. Intenta nuevamente."),
    #             parse_mode='HTML'
    #         )
    #         return True  # Terminar proceso por error

    # async def _handle_max_attempts_reached(self, update, context, max_attempts):
    #     """Manejar cuando se alcanza el máximo de intentos"""
    #     try:
    #         max_attempts_message = self.messages.get("max_attempts_reached", "❌ Máximo de intentos alcanzado").format(
    #             max_attempts=max_attempts
    #         )
            
    #         await update.message.reply_text(max_attempts_message, parse_mode='HTML')
            
    #         # Limpiar estado del usuario
    #         context.user_data.pop('awaiting_mt5', None)
    #         context.user_data.pop('user_info', None)
    #         context.user_data.pop('mt5_attempts', None)
            
    #         user_id = context.user_data.get('user_info', {}).get('id', 'unknown')
    #         self.logger.info(f"Usuario {user_id} alcanzó máximo de intentos MT5")
            
    #     except Exception as e:
    #         self.logger.error(f"Error manejando máximo de intentos: {e}")
    
    # async def process_participation(self, user_info, mt5_account, update):
    #     """Valida y registra la participación de un usuario"""
    #     try:
    #         user_id = user_info['id']
            
    #         # VALIDACIÓN 1: ¿Usuario ya registrado HOY? (doble verificación)
    #         if self._is_already_registered(user_id):
    #             await update.message.reply_text(
    #                 self.messages.get("already_registered", "Ya estás registrado"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # VALIDACIÓN 2: ¿Cuenta MT5 ya usada HOY por otro usuario?
    #         account_used_today, other_user_id = self._is_account_already_used_today(mt5_account)
    #         if account_used_today:
    #             await update.message.reply_text(
    #                 self.messages.get("account_already_used_today", "Cuenta ya registrada hoy"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # VALIDACIÓN 3: ¿Cuenta MT5 pertenece históricamente a otro usuario?
    #         is_other_user_account, owner_id, first_used = self._is_account_owned_by_other_user(mt5_account, user_id)
    #         if is_other_user_account:
    #             message = self.messages.get("account_owned_by_other_user", "Cuenta pertenece a otro usuario").format(
    #                 first_used=first_used[:10] if first_used else "fecha desconocida"
    #             )
    #             await update.message.reply_text(message, parse_mode='HTML')
    #             return
            
    #         # VALIDACIÓN 4: Validar cuenta MT5 con API
    #         validation_result = self.validate_mt5_account(mt5_account)
            
    #         if not validation_result['valid']:
    #             error_type = validation_result['error_type']
    #             message = ""
                
    #             if error_type == 'not_found':
    #                 message = self.messages.get("account_not_found", "Cuenta no encontrada").format(account=mt5_account)
    #             elif error_type == 'not_live':
    #                 message = self.messages.get("not_live", "Cuenta no es LIVE")
    #             elif error_type == 'insufficient_balance':
    #                 balance = validation_result.get('balance', 0)
    #                 message = self.messages.get("insufficient_balance", "Saldo insuficiente").format(balance=balance)
    #             else:
    #                 message = self.messages.get("api_error", "Error de verificación")
                
    #             await update.message.reply_text(message, parse_mode='HTML')
    #             return
            
    #         # VALIDACIÓN 5: Verificar membresía del canal (seguridad adicional)
    #         if not await self._check_channel_membership(user_id):
    #             await update.message.reply_text(
    #                 self.messages.get("not_channel_member", "No eres miembro del canal"),
    #                 parse_mode='HTML'
    #             )
    #             return
            
    #         # TODAS LAS VALIDACIONES PASARON - Guardar participante
    #         participant_data = {
    #             'telegram_id': user_id,
    #             'username': user_info.get('username', ''),
    #             'first_name': user_info.get('first_name', ''),
    #             'mt5_account': mt5_account,
    #             'balance': validation_result['balance'],
    #             'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    #             'status': 'active'
    #         }
            
    #         self._save_participant(participant_data)
            
    #         # Obtener historial de cuentas del usuario para mensaje personalizado
    #         user_history = self.get_user_account_history(user_id)
            
    #         if len(user_history) > 1:
    #             # Usuario tiene historial previo
    #             unique_accounts = len(set(acc['mt5_account'] for acc in user_history))
    #             success_message = self.messages.get("success_with_history", "Registrado exitosamente").format(
    #                 account=mt5_account,
    #                 total_participations=len(user_history),
    #                 unique_accounts=unique_accounts
    #             )
    #         else:
    #             # Primera vez del usuario
    #             success_message = self.messages.get("success_first_time", "¡Primera participación!")
            
    #         await update.message.reply_text(success_message, parse_mode='HTML')
            
    #         self.logger.info(f"Usuario {user_id} registrado exitosamente para giveaway con cuenta {mt5_account}. Historial: {len(user_history)} participaciones")
            
    #     except Exception as e:
    #         self.logger.error(f"Error procesando participación: {e}")
    #         await update.message.reply_text(
    #             self.messages.get("error_internal", "Error interno. Intenta nuevamente."),
    #             parse_mode='HTML'
    #         )

    # # ================== VALIDACIONES ==================
    # # ================== VALIDACIONES ==================

    # def validate_mt5_account(self, account_number):
    #     """Valida cuenta MT5 usando la API"""
    #     try:
    #         # Aquí usarías tu API real de MT5
    #         account_info = self._simulate_mt5_api(account_number)
            
    #          # VERIFICAR SI LA CUENTA EXISTE
    #         if account_info is None:
    #             print(f"❌ DEBUG: Cuenta {account_number} no existe")  # DEBUG
    #             return {
    #                 'valid': False,
    #                 'error_type': 'not_found',
    #                 'message': 'Cuenta no encontrada'
    #             }
            
    #         # VERIFICAR SI ES CUENTA LIVE
    #         if not account_info.get('is_live', False):
    #             print(f"❌ DEBUG: Cuenta {account_number} no es LIVE")  # DEBUG
    #             return {
    #                 'valid': False,
    #                 'error_type': 'not_live',
    #                 'message': 'Cuenta no es LIVE'
    #             }
            
    #         # VERIFICAR SALDO MÍNIMO
    #         balance = account_info.get('balance', 0)
    #         if balance < self.min_balance:
    #             print(f"❌ DEBUG: Cuenta {account_number} saldo insuficiente: ${balance}")  # DEBUG
    #             return {
    #                 'valid': False,
    #                 'error_type': 'insufficient_balance',
    #                 'balance': balance,
    #                 'message': f'Saldo insuficiente: ${balance}'
    #             }
            
    #         print(f"✅ DEBUG: Cuenta {account_number} VÁLIDA - Saldo: ${balance}")  # DEBUG
    #         return {
    #             'valid': True,
    #             'balance': balance,
    #             'message': 'Cuenta válida'
    #         }
            
    #     except Exception as e:
    #         self.logger.error(f"Error validando cuenta MT5: {e}")
    #         return {
    #             'valid': False,
    #             'error_type': 'api_error',
    #             'message': 'Error de validación'
    #         }
    
    # def _simulate_mt5_api(self, account_number):
    #     """SIMULACIÓN DE API MT5 - Reemplaza con tu API real"""
    #     test_accounts = {
    #             # ✅ CUENTAS VÁLIDAS PARA PARTICIPAR (LIVE + Saldo >= $100)
    #             '1234': {'exists': True, 'is_live': True, 'balance': 150.50, 'currency': 'USD'},
    #             '8765': {'exists': True, 'is_live': True, 'balance': 250.75, 'currency': 'USD'},
    #             '3333': {'exists': True, 'is_live': True, 'balance': 300.00, 'currency': 'USD'},
    #             '4444': {'exists': True, 'is_live': True, 'balance': 125.25, 'currency': 'USD'},
    #             '5555': {'exists': True, 'is_live': True, 'balance': 500.00, 'currency': 'USD'},
    #             '6666': {'exists': True, 'is_live': True, 'balance': 199.99, 'currency': 'USD'},
    #             '7777': {'exists': True, 'is_live': True, 'balance': 1000.00, 'currency': 'USD'},
    #             '8888': {'exists': True, 'is_live': True, 'balance': 750.50, 'currency': 'USD'},
    #             '1010': {'exists': True, 'is_live': True, 'balance': 100.00, 'currency': 'USD'},  # Justo el mínimo
    #             '2020': {'exists': True, 'is_live': True, 'balance': 100.01, 'currency': 'USD'},  # Apenas suficiente
                
    #             # ❌ CUENTAS CON SALDO INSUFICIENTE (< $100)
    #             '2222': {'exists': True, 'is_live': True, 'balance': 50.00, 'currency': 'USD'},
    #             '3030': {'exists': True, 'is_live': True, 'balance': 99.99, 'currency': 'USD'},
    #             '4040': {'exists': True, 'is_live': True, 'balance': 25.50, 'currency': 'USD'},
    #             '5050': {'exists': True, 'is_live': True, 'balance': 0.00, 'currency': 'USD'},
                
    #             # ❌ CUENTAS DEMO (No válidas para giveaway)
    #             '1111': {'exists': True, 'is_live': False, 'balance': 200.00, 'currency': 'USD'},
    #             '6060': {'exists': True, 'is_live': False, 'balance': 500.00, 'currency': 'USD'},
    #             '7070': {'exists': True, 'is_live': False, 'balance': 1000.00, 'currency': 'USD'},
                
    #             # ❌ CUENTAS QUE NO EXISTEN
    #             '9999': None,
    #             '0000': None,
    #             '9876': None,
    #             '1357': None,
                
    #             # 🧪 CUENTAS ESPECIALES PARA TESTING AVANZADO
    #             '8080': {'exists': True, 'is_live': True, 'balance': 100.50, 'currency': 'USD'},  # Para probar historial
    #             '9090': {'exists': True, 'is_live': True, 'balance': 200.25, 'currency': 'USD'},  # Para probar duplicados
    #         }
        
    #     return test_accounts.get(account_number, {'is_live': True, 'balance': 125.75})
    
    # def _is_already_registered(self, user_id):
    #     """Verificar si el usuario ya está registrado para el giveaway DE HOY"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         with open(self.participants_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 if (row['telegram_id'] == str(user_id) and 
    #                     row['registration_date'].startswith(today) and 
    #                     row['status'] == 'active'):
    #                     return True
    #         return False
    #     except Exception as e:
    #         self.logger.error(f"Error verificando registro: {e}")
    #         return False
    
    # def _has_pending_registration(self, user_id, context):
    #     """Verificar si el usuario ya tiene un proceso de registro pendiente"""
    #     if context.user_data.get('awaiting_mt5') and context.user_data.get('user_info', {}).get('id') == user_id:
    #         return True
    #     return False
    
    # def _is_account_already_used_today(self, mt5_account):
    #     """Verificar si una cuenta MT5 ya fue usada HOY por otro usuario"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         with open(self.participants_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 if (row['mt5_account'] == str(mt5_account) and 
    #                     row['registration_date'].startswith(today) and 
    #                     row['status'] == 'active'):
    #                     return True, row['telegram_id']
    #         return False, None
    #     except Exception as e:
    #         self.logger.error(f"Error verificando cuenta duplicada: {e}")
    #         return False, None
    
    # def _is_account_owned_by_other_user(self, mt5_account, current_user_id):
    #     """Verificar si una cuenta MT5 pertenece a otro usuario (históricamente)"""
    #     try:
    #         # Verificar en participantes actuales
    #         if os.path.exists(self.participants_file):
    #             with open(self.participants_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['mt5_account'] == str(mt5_account) and 
    #                         row['telegram_id'] != str(current_user_id) and 
    #                         row['status'] == 'active'):
    #                         return True, row['telegram_id'], row['registration_date']
            
    #         # Verificar en historial permanente
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['mt5_account'] == str(mt5_account) and 
    #                         row['telegram_id'] != str(current_user_id) and 
    #                         row['telegram_id'] != 'NO_PARTICIPANTS'):
    #                         return True, row['telegram_id'], row['date']
    #         return False, None, None
    #     except Exception as e:
    #         self.logger.error(f"Error verificando propiedad de cuenta: {e}")
    #         return False, None, None
    
    # async def _check_channel_membership(self, user_id):
    #     """Verificar si el usuario es miembro del canal"""
    #     try:
    #         member = await self.bot.get_chat_member(self.channel_id, user_id)
    #         return member.status in ['member', 'administrator', 'creator']
    #     except Exception as e:
    #         self.logger.error(f"Error verificando membresía: {e}")
    #         return False

    

    # # ================== SORTEO Y PROCESO DE PAGO ==================
    # # ================== SORTEO Y PROCESO DE PAGO ==================
    # # async def run_daily_giveaway(self):
    # #     """Ejecutar el sorteo diario - MODIFICADO para proceso de pago manual"""
    # #     try:
    # #         self.logger.info("Iniciando sorteo diario")
            
    # #         # Obtener participantes elegibles
    # #         eligible_participants = self._get_eligible_participants()
            
    # #         if not eligible_participants:
    # #             # Guardar día sin participantes en historial
    # #             await self._save_empty_day_to_history()
    # #             await self.bot.send_message(
    # #                 chat_id=self.channel_id,
    # #                 text=self.messages.get("no_eligible_participants", "No hay participantes elegibles"),
    # #                 parse_mode='HTML'
    # #             )
    # #             return
            
    # #         # Seleccionar ganador
    # #         winner = self._select_winner(eligible_participants)
            
    # #         if winner:
    # #             # 1. Guardar ganador en estado "pending_payment"
    # #             self._save_winner_pending_payment(winner)
                
    # #             # 2. NUEVO: Notificar al administrador (NO anunciar público)
    # #             await self._notify_admin_winner(winner, len(eligible_participants))
                
    # #             # 3. Guardar resultados del día completo en historial permanente
    # #             await self._save_daily_results_to_history(winner)
                
    # #             # 4. NO anunciar público hasta confirmación de pago
    # #             self.logger.info(f"Ganador seleccionado, esperando confirmación de pago: {winner['telegram_id']}")
            
    # #     except Exception as e:
    # #         self.logger.error(f"Error ejecutando sorteo: {e}")

    # async def run_giveaway(self, giveaway_type="daily", prize_amount=None):
    #     """
    #     NUEVA: Ejecutar giveaway genérico - reutilizable para daily/weekly/monthly
        
    #     Args:
    #         giveaway_type: 'daily', 'weekly', 'monthly'
    #         prize_amount: Override del premio (None = usar default)
    #     """
    #     try:
    #         period_names = {
    #             'daily': 'diario',
    #             'weekly': 'semanal',
    #             'monthly': 'mensual'
    #         }
            
    #         period_name = period_names.get(giveaway_type, 'diario')
    #         prize = prize_amount or self.daily_prize
            
    #         self.logger.info(f"Iniciando sorteo {period_name}")
    #         print(f"🎲 DEBUG: Ejecutando giveaway {giveaway_type} con premio ${prize}")
            
    #         # Obtener participantes elegibles
    #         eligible_participants = self._get_eligible_participants()
            
    #         if not eligible_participants:
    #             # Guardar día sin participantes en historial
    #             await self._save_empty_period_to_history(giveaway_type)
    #             await self.bot.send_message(
    #                 chat_id=self.channel_id,
    #                 text=self.messages.get("no_eligible_participants", "No hay participantes elegibles"),
    #                 parse_mode='HTML'
    #             )
                
    #             # ✅ LIMPIAR INCLUSO SIN PARTICIPANTES
    #             self._prepare_for_next_period(giveaway_type)
    #             return
            
    #         print(f"👥 DEBUG: {len(eligible_participants)} participantes elegibles encontrados")
            
    #         # Seleccionar ganador
    #         winner = self._select_winner(eligible_participants)
            
    #         if winner:
    #             print(f"🏆 DEBUG: Ganador seleccionado: {winner['telegram_id']}")
                
    #             # 1. Guardar ganador en estado "pending_payment"
    #             self._save_winner_pending_payment(winner, giveaway_type, prize)
                
    #             # 2. Notificar al administrador
    #             await self._notify_admin_winner(winner, len(eligible_participants), giveaway_type, prize)
                
    #             # 3. Guardar resultados del período completo en historial permanente
    #             await self._save_period_results_to_history(winner, giveaway_type)
                
    #             # 4. ✅ LIMPIAR PARTICIPANTES para próximo período
    #             self._prepare_for_next_period(giveaway_type)
                
    #             self.logger.info(f"Giveaway {period_name} completado. Ganador: {winner['telegram_id']}")
    #             print(f"✅ DEBUG: Sorteo {giveaway_type} completado y participantes limpiados")
            
    #     except Exception as e:
    #         self.logger.error(f"Error ejecutando sorteo {giveaway_type}: {e}")
    
    # async def _notify_admin_winner(self, winner, total_participants):
    #     """MODIFICADA: Notificar al administrador con username prominente"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         username = winner.get('username', '').strip()
    #         first_name = winner.get('first_name', 'N/A')
            
    #         # Preparar display del ganador
    #         if username:
    #             winner_display = f"@{username}"
    #             command_identifier = username
    #         else:
    #             winner_display = f"{first_name} (Sin username)"
    #             command_identifier = winner['telegram_id']
            
    #         admin_message = f"""🏆 <b>GANADOR SELECCIONADO - ACCIÓN REQUERIDA</b>

    # 🎉 <b>Ganador:</b> {first_name} ({winner_display})
    # 💰 <b>Premio:</b> ${self.daily_prize} USD
    # 📊 <b>Cuenta MT5:</b> <code>{winner['mt5_account']}</code>
    # 🆔 <b>Telegram ID:</b> <code>{winner['telegram_id']}</code>
    # 👥 <b>Total participantes:</b> {total_participants}
    # 📅 <b>Fecha:</b> {today}

    # ⚠️ <b>INSTRUCCIONES:</b>
    # 1️⃣ Realiza la transferencia de ${self.daily_prize} USD a la cuenta MT5: <code>{winner['mt5_account']}</code>
    # 2️⃣ Una vez completada, presiona el botón de confirmación

    # ⏳ <b>Estado:</b> Esperando transferencia manual"""
            
    #         # ✅ CREAR BOTÓN INLINE PARA CONFIRMACIÓN RÁPIDA
    #         button_text = f"✅ Confirmar pago a {first_name}"
    #         callback_data = f"confirm_payment_{command_identifier}"
            
    #         keyboard = [[InlineKeyboardButton(button_text, callback_data=callback_data)]]
    #         reply_markup = InlineKeyboardMarkup(keyboard)
            
    #         await self.bot.send_message(
    #             chat_id=self.admin_id,
    #             text=admin_message,
    #             parse_mode='HTML',
    #             reply_markup=reply_markup
    #         )
            
    #         self.logger.info(f"Administrador notificado sobre ganador: {winner['telegram_id']} (@{username})")
            
    #     except Exception as e:
    #         self.logger.error(f"Error notificando administrador: {e}")
    
    # async def confirm_payment_and_announce(self, winner_telegram_id, confirmed_by_admin_id):
    #     """NUEVA: Confirmar pago y proceder con anuncios"""
    #     try:
    #         # 1. Buscar datos del ganador
    #         print(f"🔍 DEBUG: ===== INICIANDO CONFIRMACIÓN DE PAGO =====")
    #         print(f"🔍 DEBUG: Ganador ID: {winner_telegram_id}")
    #         print(f"🔍 DEBUG: Confirmado por admin: {confirmed_by_admin_id}")
            
    #         # 1. Buscar datos del ganador PENDIENTE
    #         print(f"🔍 DEBUG: Paso 1 - Buscando datos del ganador...")
    #         winner_data = self._get_pending_winner_data(winner_telegram_id)
    #         if not winner_data:
    #             print(f"❌ DEBUG: No se encontró ganador pendiente con ID {winner_telegram_id}")
    #             return False, "Ganador no encontrado o ya procesado"
            
    #         print(f"✅ DEBUG: Ganador encontrado: {winner_data['first_name']} (MT5: {winner_data['mt5_account']})")
            
    #         # 2. Actualizar estado a "payment_confirmed"
    #         print(f"🔍 DEBUG: Paso 2 - Actualizando estado...")
    #         update_success = self._update_winner_status(winner_telegram_id, "payment_confirmed", confirmed_by_admin_id)
    #         if not update_success:
    #             print(f"❌ DEBUG: ERROR actualizando estado del ganador {winner_telegram_id}")
    #             return False, "Error actualizando estado del ganador"
            
    #         print(f"✅ DEBUG: Estado actualizado exitosamente")
            
    #         # 3. Guardar en historial de ganadores definitivo
    #         print(f"🔍 DEBUG: Paso 3 - Guardando en historial definitivo...")
    #         self._save_confirmed_winner(winner_data)
    #         print(f"✅ DEBUG: Ganador guardado en historial definitivo")
            
    #         # 4. Anunciar público
    #         print(f"🔍 DEBUG: Paso 4 - Anunciando público...")
    #         await self._announce_winner_public(winner_data)
    #         print(f"✅ DEBUG: Anuncio público enviado")
            
    #         # 5. Felicitar al ganador privadamente
    #         print(f"🔍 DEBUG: Paso 5 - Enviando felicitación privada...")
    #         await self._congratulate_winner_private(winner_data)
    #         print(f"✅ DEBUG: Felicitación privada enviada")
            
    #         # 6. Limpiar para siguiente día
    #         print(f"🔍 DEBUG: Paso 6 - Preparando para próximo día...")
    #         self._prepare_for_next_day()
    #         print(f"✅ DEBUG: Sistema preparado para próximo día")
            
    #         # 7. VERIFICACIÓN FINAL
    #         print(f"🔍 DEBUG: Paso 7 - Verificación final...")
    #         final_pending = self.get_pending_winners()
    #         print(f"🔍 DEBUG: Ganadores pendientes al final: {len(final_pending)}")
            
    #         print(f"🔍 DEBUG: ===== CONFIRMACIÓN COMPLETADA =====")
    #         return True, "Pago confirmado y ganador anunciado"
            
    #     except Exception as e:
    #         self.logger.error(f"Error confirmando pago: {e}")
    #         return False, f"Error: {e}"
    
    # async def _announce_winner_public(self, winner_data):
    #     """MODIFICADA: Anunciar el ganador en el canal (solo después de confirmación de pago)"""
    #     try:
    #         username = winner_data.get('username', '')
    #         if username and not username.startswith('@'):
    #             username = f"@{username}"
    #         elif not username:
    #             username = winner_data.get('first_name', 'Ganador')
            
    #         # Obtener total de participantes del día
    #         total_participants = self._get_daily_participants_count()
            
    #         message = self.messages.get("winner_announcement", "¡Ganador anunciado!").format(
    #             username=username,
    #             prize=self.daily_prize,
    #             account=winner_data['mt5_account'],
    #             total_participants=total_participants
    #         )
            
    #         await self.bot.send_message(
    #             chat_id=self.channel_id,
    #             text=message,
    #             parse_mode='HTML'
    #         )
            
    #         self.logger.info(f"Ganador anunciado públicamente: {winner_data['telegram_id']}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error anunciando ganador: {e}")
    
    # async def _congratulate_winner_private(self, winner_data):
    #     """NUEVA: Mensaje privado de felicitación al ganador"""
    #     try:
    #         # NUEVO: Obtener información del admin
    #         admin_username = await self._get_admin_username()
            
    #         congratulation_message = self.messages.get("winner_private_congratulation", "¡Felicidades!").format(
    #             prize=self.daily_prize,
    #             account=winner_data['mt5_account']
    #         )
            
    #         # AGREGAR información de contacto al admin
    #         if admin_username:
    #             congratulation_message += f"\n\n📞 <b>Para confirmar recibo:</b>\nContacta al administrador: @{admin_username}"
    #         else:
    #             congratulation_message += f"\n\n📞 <b>Para confirmar recibo:</b>\nResponde a este mensaje con la confirmación y foto."
            
    #         await self.bot.send_message(
    #             chat_id=winner_data['telegram_id'],
    #             text=congratulation_message,
    #             parse_mode='HTML'
    #         )
            
    #         self.logger.info(f"Felicitación privada enviada al ganador: {winner_data['telegram_id']}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error enviando felicitación privada: {e}")

    # async def _get_admin_username(self):
    #     """NUEVA: Obtener username del administrador"""
    #     try:
    #         admin_info = await self.bot.get_chat(self.admin_id)
    #         return admin_info.username
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo info del admin: {e}")
    #         return None

    # # ================== GESTIÓN DE GANADORES PENDIENTES ==================
    # # ================== GESTIÓN DE GANADORES PENDIENTES ==================
    # # def _save_winner_pending_payment(self, winner):
    # #     """NUEVA: Guardar ganador en estado pendiente de pago"""
    # #     try:
    # #         today = datetime.now().strftime('%Y-%m-%d')
    # #         now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # #         telegram_id = winner['telegram_id']
        
    # #         print(f"🔍 DEBUG: Intentando guardar ganador pendiente: {telegram_id}")
            
    # #         # VERIFICAR SI YA EXISTE COMO PENDIENTE HOY
    # #         if os.path.exists(self.pending_winners_file):
    # #             with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    # #                 reader = csv.DictReader(f)
    # #                 for row in reader:
    # #                     if (row['telegram_id'] == str(telegram_id) and 
    # #                         row['date'] == today and 
    # #                         row['status'] == 'pending_payment'):
    # #                         print(f"⚠️ DEBUG: Ganador {telegram_id} ya existe como pendiente hoy")
    # #                         return  # NO DUPLICAR
            
    # #         # Si llegamos aquí, es seguro agregar
    # #         with open(self.pending_winners_file, 'a', newline='', encoding='utf-8') as f:
    # #             writer = csv.writer(f)
    # #             writer.writerow([
    # #                 today,
    # #                 telegram_id,
    # #                 winner.get('username', ''),
    # #                 winner.get('first_name', ''),
    # #                 winner['mt5_account'],
    # #                 self.daily_prize,
    # #                 'pending_payment',
    # #                 now,
    # #                 '',  # confirmed_time vacío
    # #                 ''   # confirmed_by vacío
    # #             ])
                
    # #         print(f"✅ DEBUG: Ganador {telegram_id} guardado como pendiente de pago")
    # #         self.logger.info(f"Ganador guardado como pendiente de pago: {telegram_id}")
            
    # #     except Exception as e:
    # #         self.logger.error(f"Error guardando ganador pendiente: {e}")

    # def _save_winner_pending_payment(self, winner, giveaway_type="daily", prize_amount=None):
    #     """MEJORADA: Guardar ganador con tipo de giveaway"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #         telegram_id = winner['telegram_id']
    #         prize = prize_amount or self.daily_prize
            
    #         print(f"💾 DEBUG: Guardando ganador {telegram_id} para {giveaway_type} con premio ${prize}")
            
    #         # Verificar si ya existe como pendiente HOY
    #         if os.path.exists(self.pending_winners_file):
    #             with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['telegram_id'] == str(telegram_id) and 
    #                         row['date'] == today and 
    #                         row['status'] == 'pending_payment' and
    #                         row['giveaway_type'] == giveaway_type):
    #                         print(f"⚠️ DEBUG: Ganador {telegram_id} ya existe como pendiente para {giveaway_type} hoy")
    #                         return
            
    #         # Guardar con tipo de giveaway
    #         with open(self.pending_winners_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 today,
    #                 telegram_id,
    #                 winner.get('username', ''),
    #                 winner.get('first_name', ''),
    #                 winner['mt5_account'],
    #                 prize,
    #                 'pending_payment',
    #                 now,
    #                 '',  # confirmed_time vacío
    #                 '',  # confirmed_by vacío
    #                 giveaway_type  # NUEVO: Tipo de giveaway
    #             ])
                
    #         print(f"✅ DEBUG: Ganador {telegram_id} guardado como pendiente para {giveaway_type}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando ganador pendiente {giveaway_type}: {e}")
    
    # def _save_winner_pending_payment_with_type(self, winner, giveaway_type="daily", prize_amount=None):
    #     """NUEVA: Guardar ganador con tipo de giveaway"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #         telegram_id = winner['telegram_id']
    #         prize = prize_amount or self.daily_prize
            
    #         print(f"💾 DEBUG: Guardando ganador {telegram_id} para {giveaway_type} con premio ${prize}")
            
    #         # Verificar si ya existe como pendiente HOY
    #         if os.path.exists(self.pending_winners_file):
    #             with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['telegram_id'] == str(telegram_id) and 
    #                         row['date'] == today and 
    #                         row['status'] == 'pending_payment'):
    #                         print(f"⚠️ DEBUG: Ganador {telegram_id} ya existe como pendiente hoy")
    #                         return
            
    #         # Guardar con tipo de giveaway (usando archivo existente)
    #         with open(self.pending_winners_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 today,
    #                 telegram_id,
    #                 winner.get('username', ''),
    #                 winner.get('first_name', ''),
    #                 winner['mt5_account'],
    #                 prize,
    #                 'pending_payment',
    #                 now,
    #                 '',  # confirmed_time vacío
    #                 ''   # confirmed_by vacío
    #             ])
                
    #         print(f"✅ DEBUG: Ganador {telegram_id} guardado como pendiente para {giveaway_type}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando ganador pendiente {giveaway_type}: {e}")
    # def _get_pending_winner_data(self, telegram_id):
    #     """NUEVA: Obtener datos del ganador pendiente por ID"""
    #     try:
    #         if not os.path.exists(self.pending_winners_file):
    #             return None
                
    #         with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 if (row['telegram_id'] == str(telegram_id) and 
    #                     row['status'] == 'pending_payment'):
    #                     return row
    #         return None
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo datos del ganador: {e}")
    #         return None
    
    # def _update_winner_status(self, telegram_id, new_status, confirmed_by_admin_id):
    #     """NUEVA: Actualizar estado del ganador"""
    #     try:
    #         print(f"🔍 DEBUG: Iniciando actualización de status para {telegram_id}")
    #         print(f"🔍 DEBUG: Nuevo status: {new_status}")
    #         print(f"🔍 DEBUG: Archivo: {self.pending_winners_file}")
            
    #         if not os.path.exists(self.pending_winners_file):
    #             print(f"❌ DEBUG: Archivo no existe: {self.pending_winners_file}")
    #             return False
            
    #         # BACKUP del archivo original
    #         backup_file = f"{self.pending_winners_file}.backup"
    #         import shutil
    #         shutil.copy2(self.pending_winners_file, backup_file)
    #         print(f"✅ DEBUG: Backup creado: {backup_file}")
            
    #         rows = []
    #         updated = False
    #         target_found = False
            
    #         # Leer todas las filas
    #         with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 print(f"🔍 DEBUG: Revisando fila: ID={row['telegram_id']}, Status={row['status']}")
                    
    #                 if row['telegram_id'] == str(telegram_id):
    #                     target_found = True
    #                     print(f"🔍 DEBUG: Encontrado {telegram_id} con status '{row['status']}'")
                        
    #                     if row['status'] == 'pending_payment':
    #                         # ACTUALIZAR STATUS
    #                         row['status'] = new_status
    #                         row['confirmed_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #                         row['confirmed_by'] = str(confirmed_by_admin_id)
    #                         updated = True
    #                         print(f"✅ DEBUG: Status actualizado de 'pending_payment' a '{new_status}'")
    #                     else:
    #                         print(f"⚠️ DEBUG: Ganador ya tiene status '{row['status']}', no se actualiza")
                    
    #                 rows.append(row)
            
    #         if not target_found:
    #             print(f"❌ DEBUG: Telegram ID {telegram_id} NO encontrado en archivo")
    #             return False
            
    #         if not updated:
    #             print(f"❌ DEBUG: No se actualizó (status no era 'pending_payment')")
    #             return False
            
    #         # Escribir archivo actualizado
    #         temp_file = f"{self.pending_winners_file}.temp"
    #         with open(temp_file, 'w', newline='', encoding='utf-8') as f:
    #             fieldnames = ['date', 'telegram_id', 'username', 'first_name', 'mt5_account', 'prize', 'status', 'selected_time', 'confirmed_time', 'confirmed_by']
    #             writer = csv.DictWriter(f, fieldnames=fieldnames)
    #             writer.writeheader()
    #             writer.writerows(rows)
            
    #         # Reemplazar archivo original con archivo temporal
    #         os.replace(temp_file, self.pending_winners_file)
    #         print(f"✅ DEBUG: Archivo CSV actualizado exitosamente")
            
    #         # VERIFICAR inmediatamente el resultado
    #         pending_after = self.get_pending_winners()
    #         print(f"🔍 DEBUG: Ganadores pendientes después de actualización: {len(pending_after)}")
    #         for p in pending_after:
    #             print(f"   - ID: {p['telegram_id']}, Status: {p['status']}")
            
    #         return True
            
    #     except Exception as e:
    #         self.logger.error(f"Error actualizando estado del ganador: {e}")
    #         return False
    
    # def get_pending_winners(self):
    #     """NUEVA: Obtener lista de ganadores pendientes de pago"""
    #     try:
    #         pending_winners = []
            
    #         print(f"🔍 DEBUG: Obteniendo ganadores pendientes")
    #         print(f"🔍 DEBUG: Archivo: {self.pending_winners_file}")
            
    #         if not os.path.exists(self.pending_winners_file):
    #             print("🔍 DEBUG: Archivo pending_winners.csv NO EXISTE")
    #             return pending_winners
            
    #         with open(self.pending_winners_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             total_count = 0
    #             pending_count = 0
                
    #             for row in reader:
    #                 total_count += 1
    #                 print(f"🔍 DEBUG: Fila {total_count}: ID={row['telegram_id']}, Status='{row['status']}', Fecha={row['date']}")
                    
    #                 # SOLO incluir si el status es exactamente "pending_payment"
    #                 if row['status'].strip() == 'pending_payment':
    #                     pending_winners.append(row)
    #                     pending_count += 1
    #                     print(f"✅ DEBUG: Ganador {row['telegram_id']} agregado a lista pendiente")
    #                 else:
    #                     print(f"⏭️ DEBUG: Ganador {row['telegram_id']} omitido (status: '{row['status']}')")
            
    #         print(f"🔍 DEBUG: Total registros en archivo: {total_count}")
    #         print(f"🔍 DEBUG: Ganadores pendientes encontrados: {pending_count}")
            
    #         return pending_winners
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo ganadores pendientes: {e}")
    #         return []

    # async def _save_empty_period_to_history(self, giveaway_type="daily"):
    #     """MEJORADA: Guardar período sin participantes"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 today,
    #                 'NO_PARTICIPANTS',
    #                 'NO_PARTICIPANTS', 
    #                 'NO_PARTICIPANTS',
    #                 'NO_PARTICIPANTS',
    #                 0,
    #                 False,
    #                 0,
    #                 f'{giveaway_type}_empty'  # MEJORADO: Incluye tipo
    #             ])
            
    #         self.logger.info(f"Período {giveaway_type} sin participantes guardado en historial")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando período {giveaway_type} vacío: {e}")


    # # ================== GESTIÓN DE DATOS ==================
    # # ================== GESTIÓN DE DATOS ==================
    # def _save_participant(self, participant_data):
    #     """Guardar participante en CSV"""
    #     try:
    #         with open(self.participants_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 participant_data['telegram_id'],
    #                 participant_data['username'],
    #                 participant_data['first_name'],
    #                 participant_data['mt5_account'],
    #                 participant_data['balance'],
    #                 participant_data['registration_date'],
    #                 participant_data['status']
    #             ])
    #         self.logger.info(f"Participante {participant_data['telegram_id']} guardado")
    #     except Exception as e:
    #         self.logger.error(f"Error guardando participante: {e}")
    
    # def _save_confirmed_winner(self, winner_data):
    #     """NUEVA: Guardar ganador confirmado en historial definitivo"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         with open(self.winners_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 today,
    #                 winner_data['telegram_id'],
    #                 winner_data['username'],
    #                 winner_data['mt5_account'],
    #                 self.daily_prize,
    #                 'daily'
    #             ])
                
    #         self.logger.info(f"Ganador confirmado guardado: {winner_data['telegram_id']}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando ganador confirmado: {e}")
    
    # def _get_eligible_participants(self):
    #     """Obtener lista de participantes elegibles para el sorteo"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         eligible = []
            
    #         # Obtener participantes de hoy
    #         with open(self.participants_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 if (row['registration_date'].startswith(today) and 
    #                     row['status'] == 'active'):
    #                     eligible.append(row)
            
    #         # Filtrar ganadores recientes
    #         recent_winners = self._get_recent_winners()
    #         eligible = [p for p in eligible if p['telegram_id'] not in recent_winners]
            
    #         self.logger.info(f"Participantes elegibles: {len(eligible)}")
    #         return eligible
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo participantes elegibles: {e}")
    #         return []
    
    # def _get_recent_winners(self):
    #     """Obtener IDs de ganadores recientes (últimos 30 días)"""
    #     try:
    #         cutoff_date = datetime.now() - timedelta(days=self.winner_cooldown_days)
    #         recent_winners = set()
            
    #         if os.path.exists(self.winners_file):
    #             with open(self.winners_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     try:
    #                         win_date = datetime.strptime(row['date'], '%Y-%m-%d')
    #                         if win_date >= cutoff_date:
    #                             recent_winners.add(row['telegram_id'])
    #                     except ValueError:
    #                         continue
            
    #         return recent_winners
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo ganadores recientes: {e}")
    #         return set()
    
    # def _select_winner(self, participants):
    #     """Seleccionar ganador aleatorio de la lista de participantes"""
    #     if not participants:
    #         return None
    #     return random.choice(participants)
    
    # def _get_daily_participants_count(self):
    #     """NUEVA: Obtener número de participantes del día"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         count = 0
            
    #         if os.path.exists(self.participants_file):
    #             with open(self.participants_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if (row['registration_date'].startswith(today) and 
    #                         row['status'] == 'active'):
    #                         count += 1
    #         return count
    #     except Exception as e:
    #         self.logger.error(f"Error contando participantes diarios: {e}")
    #         return 0
    
    # async def _save_empty_day_to_history(self):
    #     """Guardar día sin participantes en historial"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow([
    #                 today, 'NO_PARTICIPANTS', 'NO_PARTICIPANTS', 'NO_PARTICIPANTS',
    #                 'NO_PARTICIPANTS', 0, False, 0, 'daily_empty'
    #             ])
            
    #         self.logger.info("Día sin participantes guardado en historial")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando día vacío: {e}")
    
    # async def _save_daily_results_to_history(self, winner_data):
    #     """Guardar todos los participantes del día en historial permanente"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         winner_id = winner_data['telegram_id'] if winner_data else None
            
    #         # Leer todos los participantes del día
    #         with open(self.participants_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             daily_participants = []
                
    #             for row in reader:
    #                 if row['registration_date'].startswith(today) and row['status'] == 'active':
    #                     daily_participants.append(row)
            
    #         if not daily_participants:
    #             self.logger.info("No hay participantes para guardar en historial")
    #             return
            
    #         # Guardar cada participante en historial permanente
    #         with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
                
    #             for participant in daily_participants:
    #                 # Determinar si ganó
    #                 won_prize = participant['telegram_id'] == winner_id
    #                 prize_amount = self.daily_prize if won_prize else 0
                    
    #                 writer.writerow([
    #                     today,
    #                     participant['telegram_id'],
    #                     participant['username'],
    #                     participant['first_name'],
    #                     participant['mt5_account'],
    #                     participant['balance'],
    #                     won_prize,
    #                     prize_amount,
    #                     'daily'
    #                 ])
            
    #         self.logger.info(f"Guardados {len(daily_participants)} participantes en historial permanente")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando en historial: {e}")
    
    # # def _prepare_for_next_day(self):
    # #     """Limpiar archivo diario para el próximo día"""
    # #     try:
    # #         # Recrear archivo de participantes vacío para mañana
    # #         with open(self.participants_file, 'w', newline='', encoding='utf-8') as f:
    # #             writer = csv.writer(f)
    # #             writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
            
    # #         self.logger.info("Archivo de participantes preparado para el próximo día")
            
    # #     except Exception as e:
    # #         self.logger.error(f"Error preparando archivo para mañana: {e}")

    # async def _save_period_results_to_history(self, winner_data, giveaway_type="daily"):
    #     """NUEVA: Guardar todos los participantes del período en historial permanente"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
    #         winner_id = winner_data['telegram_id'] if winner_data else None
            
    #         # Leer todos los participantes del período
    #         with open(self.participants_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             period_participants = []
                
    #             for row in reader:
    #                 if row['status'] == 'active':
    #                     period_participants.append(row)
            
    #         if not period_participants:
    #             self.logger.info("No hay participantes para guardar en historial")
    #             return
            
    #         # Guardar cada participante en historial permanente
    #         with open(self.history_file, 'a', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
                
    #             for participant in period_participants:
    #                 # Determinar si ganó
    #                 won_prize = participant['telegram_id'] == winner_id
    #                 prize_amount = self.daily_prize if won_prize else 0
                    
    #                 writer.writerow([
    #                     today,  # date
    #                     participant['telegram_id'],
    #                     participant['username'],
    #                     participant['first_name'],
    #                     participant['mt5_account'],
    #                     participant['balance'],
    #                     won_prize,  # won_prize (True/False)
    #                     prize_amount,  # prize_amount
    #                     giveaway_type  # giveaway_type: daily/weekly/monthly
    #                 ])
            
    #         self.logger.info(f"Guardados {len(period_participants)} participantes en historial permanente para {giveaway_type}")
            
    #     except Exception as e:
    #         self.logger.error(f"Error guardando en historial {giveaway_type}: {e}")

    # def _prepare_for_next_period(self, giveaway_type="daily"):
    #     """
    #     NUEVA: Limpiar archivo de participantes para el próximo período
    #     Flexible para daily/weekly/monthly giveaways
        
    #     Args:
    #         giveaway_type: 'daily', 'weekly', 'monthly'
    #     """
    #     try:
    #         # Recrear archivo de participantes vacío
    #         with open(self.participants_file, 'w', newline='', encoding='utf-8') as f:
    #             writer = csv.writer(f)
    #             writer.writerow(['telegram_id', 'username', 'first_name', 'mt5_account', 'balance', 'registration_date', 'status'])
            
    #         period_names = {
    #             'daily': 'próximo día',
    #             'weekly': 'próxima semana', 
    #             'monthly': 'próximo mes'
    #         }
            
    #         period_name = period_names.get(giveaway_type, 'próximo período')
    #         self.logger.info(f"Archivo de participantes preparado para el {period_name}")
            
    #         # Log adicional para debugging
    #         print(f"🧹 DEBUG: Participantes limpiados para {giveaway_type} giveaway")
    #         print(f"📁 DEBUG: Archivo {self.participants_file} ahora está vacío")
            
    #     except Exception as e:
    #         self.logger.error(f"Error preparando archivo para {giveaway_type}: {e}")

    # def debug_participant_cleanup(self):
    #     """NUEVA: Función de debug para verificar limpieza"""
    #     try:
    #         print("🔍 DEBUG: Verificando estado de archivos...")
            
    #         # Contar participantes actuales
    #         current_participants = 0
    #         if os.path.exists(self.participants_file):
    #             with open(self.participants_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 current_participants = len(list(reader))
            
    #         # Contar historial total
    #         total_history = 0
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 total_history = len(list(reader))
            
    #         # Contar pendientes
    #         pending_count = len(self.get_pending_winners())
            
    #         print(f"📊 DEBUG: Estado actual:")
    #         print(f"   Participantes actuales: {current_participants}")
    #         print(f"   Historial total: {total_history}")
    #         print(f"   Ganadores pendientes: {pending_count}")
            
    #         return {
    #             'current_participants': current_participants,
    #             'total_history': total_history,
    #             'pending_winners': pending_count
    #         }
            
    #     except Exception as e:
    #         print(f"❌ DEBUG: Error verificando archivos: {e}")
    #         return None

    # # ================== UTILIDADES Y ESTADÍSTICAS ==================
    # # ================== UTILIDADES Y ESTADÍSTICAS ==================

    # def get_user_participation_stats(self, user_id):
    #     """
    #     Obtener estadísticas detalladas de participación de un usuario específico
    #     """
    #     try:
    #         complete_history = self.get_user_complete_history(user_id)
            
    #         if not complete_history:
    #             return {
    #                 'total_participations': 0,
    #                 'unique_accounts': 0,
    #                 'total_wins': 0,
    #                 'total_prize_won': 0,
    #                 'first_participation': None,
    #                 'last_participation': None,
    #                 'accounts_used': [],
    #                 'win_rate': 0,
    #                 'average_balance': 0
    #             }
            
    #         unique_accounts = list(set(entry['mt5_account'] for entry in complete_history))
    #         total_wins = sum(1 for entry in complete_history if entry['won_prize'])
    #         total_prize = sum(entry['prize_amount'] for entry in complete_history)
    #         win_rate = (total_wins / len(complete_history)) * 100 if complete_history else 0
            
    #         # Calcular balance promedio
    #         balances = [float(entry['balance']) for entry in complete_history if entry['balance']]
    #         average_balance = sum(balances) / len(balances) if balances else 0
            
    #         return {
    #             'total_participations': len(complete_history),
    #             'unique_accounts': len(unique_accounts),
    #             'total_wins': total_wins,
    #             'total_prize_won': total_prize,
    #             'first_participation': complete_history[-1]['date'],  # Más antiguo
    #             'last_participation': complete_history[0]['date'],   # Más reciente
    #             'accounts_used': unique_accounts,
    #             'win_rate': round(win_rate, 2),
    #             'average_balance': round(average_balance, 2)
    #         }
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo estadísticas de usuario: {e}")
    #         return None
    
    # def get_giveaway_analytics(self, days_back=30):
    #     """
    #     Análisis completo de giveaways en un período específico
    #     """
    #     try:
    #         cutoff_date = datetime.now() - timedelta(days=days_back)
    #         cutoff_str = cutoff_date.strftime('%Y-%m-%d')
            
    #         analytics = {
    #             'period_days': days_back,
    #             'total_days_analyzed': 0,
    #             'total_participants': 0,
    #             'unique_users': set(),
    #             'unique_accounts': set(),
    #             'total_prizes_distributed': 0,
    #             'days_with_participants': 0,
    #             'days_without_participants': 0,
    #             'average_participants_per_day': 0,
    #             'top_participants': {},  # user_id: participation_count
    #             'account_usage': {},  # account: usage_count
    #             'daily_breakdown': {},  # date: participant_count
    #             'win_distribution': {},  # user_id: win_count
    #             'balance_stats': {
    #                 'total_balance': 0,
    #                 'average_balance': 0,
    #                 'min_balance': float('inf'),
    #                 'max_balance': 0
    #             }
    #         }
            
    #         if not os.path.exists(self.history_file):
    #             return analytics
            
    #         with open(self.history_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
                
    #             for row in reader:
    #                 if row['date'] >= cutoff_str:
    #                     date = row['date']
                        
    #                     # Contar días únicos
    #                     if date not in analytics['daily_breakdown']:
    #                         analytics['daily_breakdown'][date] = 0
    #                         analytics['total_days_analyzed'] += 1
                        
    #                     if row['telegram_id'] == 'NO_PARTICIPANTS':
    #                         analytics['days_without_participants'] += 1
    #                     else:
    #                         # Contar participantes
    #                         analytics['daily_breakdown'][date] += 1
    #                         analytics['total_participants'] += 1
    #                         analytics['unique_users'].add(row['telegram_id'])
    #                         analytics['unique_accounts'].add(row['mt5_account'])
                            
    #                         # Estadísticas por usuario
    #                         user_id = row['telegram_id']
    #                         analytics['top_participants'][user_id] = analytics['top_participants'].get(user_id, 0) + 1
                            
    #                         # Estadísticas por cuenta
    #                         account = row['mt5_account']
    #                         analytics['account_usage'][account] = analytics['account_usage'].get(account, 0) + 1
                            
    #                         # Estadísticas de balance
    #                         try:
    #                             balance = float(row['balance'])
    #                             analytics['balance_stats']['total_balance'] += balance
    #                             analytics['balance_stats']['min_balance'] = min(analytics['balance_stats']['min_balance'], balance)
    #                             analytics['balance_stats']['max_balance'] = max(analytics['balance_stats']['max_balance'], balance)
    #                         except (ValueError, TypeError):
    #                             pass
                            
    #                         # Premios y victorias
    #                         if row['won_prize'].lower() == 'true':
    #                             analytics['total_prizes_distributed'] += float(row['prize_amount'])
    #                             analytics['win_distribution'][user_id] = analytics['win_distribution'].get(user_id, 0) + 1
            
    #         # Calcular estadísticas derivadas
    #         analytics['days_with_participants'] = analytics['total_days_analyzed'] - analytics['days_without_participants']
    #         analytics['unique_users'] = len(analytics['unique_users'])
    #         analytics['unique_accounts'] = len(analytics['unique_accounts'])
            
    #         if analytics['days_with_participants'] > 0:
    #             analytics['average_participants_per_day'] = round(
    #                 analytics['total_participants'] / analytics['days_with_participants'], 2
    #             )
            
    #         if analytics['total_participants'] > 0:
    #             analytics['balance_stats']['average_balance'] = round(
    #                 analytics['balance_stats']['total_balance'] / analytics['total_participants'], 2
    #             )
            
    #         # Ajustar min_balance si no hubo participantes
    #         if analytics['balance_stats']['min_balance'] == float('inf'):
    #             analytics['balance_stats']['min_balance'] = 0
            
    #         return analytics
            
    #     except Exception as e:
    #         self.logger.error(f"Error generando análisis: {e}")
    #         return {}

    # def get_account_ownership_report(self):
    #     """
    #     Generar reporte de propiedad de cuentas MT5
    #     Útil para detectar intentos de usar cuentas de otros usuarios
    #     """
    #     try:
    #         account_owners = {}
            
    #         # Revisar historial permanente
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if row['telegram_id'] != 'NO_PARTICIPANTS':
    #                         account = row['mt5_account']
    #                         user_id = row['telegram_id']
    #                         username = row.get('username', 'N/A')
    #                         first_name = row.get('first_name', 'N/A')
    #                         date = row['date']
                            
    #                         if account not in account_owners:
    #                             account_owners[account] = {
    #                                 'owner_id': user_id,
    #                                 'owner_username': username,
    #                                 'owner_first_name': first_name,
    #                                 'first_used': date,
    #                                 'total_uses': 1,
    #                                 'last_used': date,
    #                                 'different_users': set([user_id])
    #                             }
    #                         else:
    #                             account_owners[account]['total_uses'] += 1
    #                             account_owners[account]['different_users'].add(user_id)
    #                             if date > account_owners[account]['last_used']:
    #                                 account_owners[account]['last_used'] = date
    #                             if date < account_owners[account]['first_used']:
    #                                 account_owners[account]['first_used'] = date
            
    #         # Convertir sets a listas para JSON serialization
    #         for account, data in account_owners.items():
    #             data['different_users'] = list(data['different_users'])
    #             data['user_count'] = len(data['different_users'])
            
    #         return account_owners
            
    #     except Exception as e:
    #         self.logger.error(f"Error generando reporte de propiedad: {e}")
    #         return {}

    # def get_top_participants_report(self, limit=10):
    #     """
    #     Obtener reporte de usuarios más activos
    #     """
    #     try:
    #         participant_stats = {}
            
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if row['telegram_id'] != 'NO_PARTICIPANTS':
    #                         user_id = row['telegram_id']
    #                         username = row.get('username', 'N/A')
    #                         first_name = row.get('first_name', 'N/A')
                            
    #                         if user_id not in participant_stats:
    #                             participant_stats[user_id] = {
    #                                 'username': username,
    #                                 'first_name': first_name,
    #                                 'participations': 0,
    #                                 'wins': 0,
    #                                 'total_prizes': 0,
    #                                 'accounts_used': set(),
    #                                 'first_participation': row['date'],
    #                                 'last_participation': row['date']
    #                             }
                            
    #                         stats = participant_stats[user_id]
    #                         stats['participations'] += 1
    #                         stats['accounts_used'].add(row['mt5_account'])
                            
    #                         if row['won_prize'].lower() == 'true':
    #                             stats['wins'] += 1
    #                             stats['total_prizes'] += float(row['prize_amount'])
                            
    #                         # Actualizar fechas
    #                         if row['date'] < stats['first_participation']:
    #                             stats['first_participation'] = row['date']
    #                         if row['date'] > stats['last_participation']:
    #                             stats['last_participation'] = row['date']
            
    #         # Convertir sets a listas y calcular win rate
    #         for user_id, stats in participant_stats.items():
    #             stats['accounts_used'] = list(stats['accounts_used'])
    #             stats['unique_accounts'] = len(stats['accounts_used'])
    #             stats['win_rate'] = round((stats['wins'] / stats['participations']) * 100, 2) if stats['participations'] > 0 else 0
            
    #         # Ordenar por número de participaciones
    #         sorted_participants = sorted(
    #             participant_stats.items(), 
    #             key=lambda x: x[1]['participations'], 
    #             reverse=True
    #         )
            
    #         return sorted_participants[:limit]
            
    #     except Exception as e:
    #         self.logger.error(f"Error generando reporte de top participantes: {e}")
    #         return []

    # def get_revenue_impact_analysis(self):
    #     """
    #     Análisis del impacto económico del sistema de giveaways
    #     """
    #     try:
    #         analysis = {
    #             'total_prizes_distributed': 0,
    #             'total_winners': 0,
    #             'total_giveaway_days': 0,
    #             'average_prize_per_day': 0,
    #             'days_without_winners': 0,
    #             'cost_efficiency': {
    #                 'cost_per_participant': 0,
    #                 'cost_per_unique_user': 0
    #             },
    #             'monthly_breakdown': {},
    #             'yearly_breakdown': {}
    #         }
            
    #         monthly_data = {}
    #         yearly_data = {}
    #         total_participants = 0
    #         unique_users = set()
            
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     date = row['date']
    #                     year_month = date[:7]  # YYYY-MM
    #                     year = date[:4]  # YYYY
                        
    #                     # Inicializar datos mensuales
    #                     if year_month not in monthly_data:
    #                         monthly_data[year_month] = {
    #                             'participants': 0,
    #                             'prizes': 0,
    #                             'unique_users': set(),
    #                             'winners': 0
    #                         }
                        
    #                     # Inicializar datos anuales
    #                     if year not in yearly_data:
    #                         yearly_data[year] = {
    #                             'participants': 0,
    #                             'prizes': 0,
    #                             'unique_users': set(),
    #                             'winners': 0
    #                         }
                        
    #                     if row['telegram_id'] != 'NO_PARTICIPANTS':
    #                         # Contar participantes
    #                         total_participants += 1
    #                         unique_users.add(row['telegram_id'])
    #                         monthly_data[year_month]['participants'] += 1
    #                         monthly_data[year_month]['unique_users'].add(row['telegram_id'])
    #                         yearly_data[year]['participants'] += 1
    #                         yearly_data[year]['unique_users'].add(row['telegram_id'])
                            
    #                         # Contar premios
    #                         if row['won_prize'].lower() == 'true':
    #                             prize_amount = float(row['prize_amount'])
    #                             analysis['total_prizes_distributed'] += prize_amount
    #                             analysis['total_winners'] += 1
    #                             monthly_data[year_month]['prizes'] += prize_amount
    #                             monthly_data[year_month]['winners'] += 1
    #                             yearly_data[year]['prizes'] += prize_amount
    #                             yearly_data[year]['winners'] += 1
    #                     else:
    #                         analysis['days_without_winners'] += 1
            
    #         # Contar días totales con giveaway
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 unique_dates = set(row['date'] for row in reader)
    #                 analysis['total_giveaway_days'] = len(unique_dates)
            
    #         # Calcular promedios
    #         if analysis['total_giveaway_days'] > 0:
    #             analysis['average_prize_per_day'] = round(
    #                 analysis['total_prizes_distributed'] / analysis['total_giveaway_days'], 2
    #             )
            
    #         # Calcular eficiencia de costos
    #         if total_participants > 0:
    #             analysis['cost_efficiency']['cost_per_participant'] = round(
    #                 analysis['total_prizes_distributed'] / total_participants, 2
    #             )
            
    #         if len(unique_users) > 0:
    #             analysis['cost_efficiency']['cost_per_unique_user'] = round(
    #                 analysis['total_prizes_distributed'] / len(unique_users), 2
    #             )
            
    #         # Preparar breakdown mensual y anual
    #         for month, data in monthly_data.items():
    #             data['unique_users'] = len(data['unique_users'])
    #             analysis['monthly_breakdown'][month] = data
            
    #         for year, data in yearly_data.items():
    #             data['unique_users'] = len(data['unique_users'])
    #             analysis['yearly_breakdown'][year] = data
            
    #         return analysis
            
    #     except Exception as e:
    #         self.logger.error(f"Error generando análisis de impacto: {e}")
    #         return {}

    # def get_user_account_history(self, user_id):
    #     """Obtener historial de cuentas MT5 que ha usado un usuario"""
    #     try:
    #         complete_history = self.get_user_complete_history(user_id)
            
    #         account_history = []
    #         for entry in complete_history:
    #             account_history.append({
    #                 'mt5_account': entry['mt5_account'],
    #                 'date': entry['date'],
    #                 'balance': entry['balance']
    #             })
            
    #         return account_history
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo historial de usuario: {e}")
    #         return []
    
    # def get_user_complete_history(self, user_id):
    #     """Obtener historial completo de un usuario desde el archivo permanente"""
    #     try:
    #         user_history = []
            
    #         if not os.path.exists(self.history_file):
    #             return user_history
            
    #         with open(self.history_file, 'r', encoding='utf-8') as f:
    #             reader = csv.DictReader(f)
    #             for row in reader:
    #                 if (row['telegram_id'] == str(user_id) and 
    #                     row['telegram_id'] != 'NO_PARTICIPANTS'):
    #                     user_history.append({
    #                         'date': row['date'],
    #                         'mt5_account': row['mt5_account'],
    #                         'balance': row['balance'],
    #                         'won_prize': row['won_prize'].lower() == 'true',
    #                         'prize_amount': float(row['prize_amount']) if row['prize_amount'] else 0,
    #                         'giveaway_type': row.get('giveaway_type', 'daily')
    #                     })
            
    #         # Ordenar por fecha (más reciente primero)
    #         user_history.sort(key=lambda x: x['date'], reverse=True)
    #         return user_history
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo historial completo: {e}")
    #         return []
    
    # def get_stats(self):
    #     """Obtener estadísticas del giveaway"""
    #     try:
    #         today = datetime.now().strftime('%Y-%m-%d')
            
    #         # Contar participantes de hoy
    #         today_participants = self._get_daily_participants_count()
            
    #         # Contar ganadores totales
    #         total_winners = 0
    #         if os.path.exists(self.winners_file):
    #             with open(self.winners_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 total_winners = sum(1 for row in reader)
            
    #         # Contar participantes históricos únicos
    #         unique_users = set()
    #         if os.path.exists(self.history_file):
    #             with open(self.history_file, 'r', encoding='utf-8') as f:
    #                 reader = csv.DictReader(f)
    #                 for row in reader:
    #                     if row['telegram_id'] != 'NO_PARTICIPANTS':
    #                         unique_users.add(row['telegram_id'])
            
    #         return {
    #             'today_participants': today_participants,
    #             'total_participants': len(unique_users),
    #             'total_winners': total_winners,
    #             'total_prize_distributed': total_winners * self.daily_prize,
    #             'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    #         }
            
    #     except Exception as e:
    #         self.logger.error(f"Error obteniendo estadísticas: {e}")
    #         return {}
        
    # def backup_history_file(self):
    #     """
    #     Crear backup del archivo de historial permanente
    #     """
    #     try:
    #         if not os.path.exists(self.history_file):
    #             return False
            
    #         timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    #         backup_name = f"{self.history_file}.backup_{timestamp}"
            
    #         import shutil
    #         shutil.copy2(self.history_file, backup_name)
            
    #         self.logger.info(f"Backup del historial creado: {backup_name}")
    #         return backup_name
            
    #     except Exception as e:
    #         self.logger.error(f"Error creando backup: {e}")
    #         return False