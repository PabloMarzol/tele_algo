from imports import *
from local_DB.db_handlers import check_existing_registration, handle_no_funds, handle_partial_funds, handle_sufficient_funds


# ---------------------------------------------------------------------------------------------------------- #
# -------------------------------------- Reg Flow Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

async def handle_auto_welcome_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """INTEGRATED: Handle all registration flow - buttons and text messages."""
    user_id = update.effective_user.id
    
    
    # SECURITY CHECK: Block duplicate registrations at any entry point
    if await check_existing_registration(update, context, user_id):
        return
    
    # HANDLE BUTTON CALLBACKS
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        callback_data = query.data
        
        print(f"Button callback: {callback_data} from user {user_id}")
        
        # RISK PROFILE BUTTONS
        if callback_data.startswith("risk_"):
            await handle_risk_selection(query, context, user_id, callback_data)
            return
            
        # INTEREST/SERVICE BUTTONS
        elif callback_data.startswith("interest_"):
            await handle_interest_selection(query, context, user_id, callback_data)
            return
            
        # DEPOSIT FLOW BUTTONS
        elif callback_data.startswith("deposit_exact_"):
            await handle_deposit_selection(query, context, user_id, callback_data)
            return
        
        elif callback_data == "start_guided":
            await start_guided_setup(query, context, user_id)
            return
            
        elif callback_data == "choose_deposit_amount":
            await show_deposit_amount_options(query, context, user_id)
            return
            
        elif callback_data == "custom_amount":
            await handle_custom_amount_request(query, context, user_id)
            return
            
        # VIP ACCESS REQUEST BUTTONS
        elif callback_data.startswith("request_vip_"):
            await handle_vip_request(query, context, user_id, callback_data)
            return
            
        # RESTART BUTTON
        elif callback_data == "restart_process":
            await restart_process(query, context, user_id)
            return
            
        # SPEAK TO ADVISOR BUTTON
        elif callback_data == "speak_advisor":
            await handle_advisor_request(query, context, user_id)
            return
            
        # BALANCE CHECK BUTTON
        elif callback_data == "check_balance_now":
            await check_balance(query, context, user_id)
            return
    
    # HANDLE TEXT MESSAGES
    elif update.message and update.message.text:
        message_text = update.message.text
        await handle_text_response(update, context, user_id, message_text)
        return
    
    # FALLBACK
    else:
        print(f"Unhandled update type from user {user_id}")



# --------------------------------------------- #
# ------------- Registration callback handlers --------------- #
# --------------------------------------------- #
async def start_guided_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Start Guided Setup' button click."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Start guided flow with risk profile buttons
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Let's get started with the guided setup!</b>\n\n"
        "What risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set state to risk_profile
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Notify admin
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🚀 User {user_id} started the guided setup process"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def risk_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle risk profile button selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    risk_option = query.data.replace("risk_", "")
    
    # Map text options to numeric values
    risk_values = {"low": 2, "medium": 5, "high": 8}
    risk_appetite = risk_values.get(risk_option, 5)
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "risk_appetite": risk_appetite,
        "risk_profile_text": risk_option,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Ask for deposit amount next
    keyboard = [
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.message.reply_text(
        f"<b>📊 Risk Profile: {risk_option.capitalize()}</b> ✅\n\n"
        f"<b>💰 Let's talk funding!</b>\n\n"
        f"How much capital are you planning to fund your account with? 📥\n\n"
        f"<b>Example:</b> 5000",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
        ])
    )
    
    # CRITICAL: Store state in bot_data, not user_data
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "deposit_amount"
    print(f"Set state for user {user_id} to deposit_amount in bot_data")
    
    # Also notify admin of the selection
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📊 User {user_id} selected risk profile: {risk_option.capitalize()}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def experience_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle previous experience button selection."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    experience = query.data.replace("experience_", "")
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "previous_experience": experience,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Ask for account number next
    keyboard = [
        [InlineKeyboardButton("↩️ Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"<b>Previous Experience:</b> {experience.capitalize()} ✅\n\nPlease provide your MT5 account number to continue.",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # IMPORTANT: Make sure we're setting the state in bot_data
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"
    print(f"Set state for user {user_id} to account_number in bot_data")
    
    # Notify admin of the selection
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📊 User {user_id} previous experience: {experience.capitalize()}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def speak_advisor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle speak to advisor button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'User') if user_info else 'User'
    
    # Notify admin that user wants to speak to an advisor
    for admin_id in ADMIN_USER_ID:
        try:
            keyboard = [
                [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 <b>ADVISOR REQUEST</b> 🔔\n\n"
                     f"User {user_name} (ID: {user_id}) has requested to speak with an advisor.\n\n"
                     f"Please respond to them as soon as possible.",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")
    
    await query.edit_message_text(
        "🔔 <b>Advisor Request Sent</b>\n\n"
        "Thank you for your request. One of our advisors will be in touch with you shortly.\n\n"
        "Please keep an eye on your messages for their response.",
        parse_mode='HTML'
    )

async def edit_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'Try Another Account' button click."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Reset account number state to ask for a new one
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"
    
    await query.edit_message_text(
        "<b>Account Number</b> ⚠️\n\n"
        "Please provide a different MT5 account number:",
        parse_mode='HTML'
    )
    
    # Notify admin
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 User {user_id} is trying another account number"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def generate_welcome_link_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a welcome message with a deep link for users with privacy settings."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    if callback_data.startswith("gen_welcome_"):
        user_id = int(callback_data.split("_")[2])
        
        # Get user info if available
        auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
        user_name = auto_welcoming_users.get(user_id, {}).get("name", "there")
        
        # Create "start bot" deep link
        bot_username = await context.bot.get_me()
        bot_username = bot_username.username
        start_link = f"https://t.me/{bot_username}?start=ref_{update.effective_user.id}"
        
        # Generate personalized welcome message
        welcome_template = (
    f"<b>Hello {user_name}! 👋</b>\n\n"
    f"🎉 <b>Thank you for your interest in VFX Trading solutions!</b>\n\n"
    f"🚀 <b>Ready to get started?</b>\n\n"
    f"To begin your account setup and access our premium trading services, please click the link below:\n\n"
    f"👉 <a href='{start_link}'>Connect with VFX - REGISTRATION</a>\n\n"
    f"<b>📋 Quick Setup Process:</b>\n\n"
    f"<b>1.</b> 🤖 Connect with our automated assistant\n"
    f"<b>2.</b> 📊 Answer quick questions about your trading preferences\n" 
    f"<b>3.</b> ✅ Verify your Vortex-FX MT5 account number\n\n"
    f"<b>🎯 What happens next?</b>\n"
    f"Our expert team will configure your account with optimal parameters based on your unique trading profile.\n\n"
    f"💬 <b>Questions? We're here to help!</b>\n\n"
    f"🔥 <b>Let's build your trading success together!</b> 📈"
)
        
        # Show the message with a copy button
        await query.edit_message_text(
            "✅ Here's your personalized welcome message to send to the user:\n\n"
            f"{welcome_template}\n\n"
            "Copy and paste this message to the user. After they click the link, "
            "they will be able to complete the registration process with the bot.",
            parse_mode='HTML'
        )

async def handle_privacy_welcome_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate welcome link for privacy-protected users."""
    query = update.callback_query
    await query.answer()
    
    user_name = context.user_data.get("privacy_user_name", "User")
    
    # Create the start link with admin referral
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    start_link = f"https://t.me/{bot_username}?start=ref_{query.from_user.id}"
    
    # Generate the copy-paste message
    welcome_template = (
        f"<b>Hello {user_name}! 👋</b>\n\n"
        f"🎉 <b>Thank you for your interest in VFX Trading solutions!</b>\n\n"
        f"🚀 <b>Ready to get started?</b>\n\n"
        f"To begin your account setup and access our premium trading services, please click the link below:\n\n"
        f"👉 <a href='{start_link}'>Connect with VFX - REGISTRATION</a>\n\n"
        f"<b>📋 Quick Setup Process:</b>\n\n"
        f"<b>1.</b> 🤖 Connect with our automated assistant\n"
        f"<b>2.</b> 📊 Answer quick questions about your trading preferences\n" 
        f"<b>3.</b> ✅ Verify your Vortex-FX MT5 account number\n\n"
        f"<b>🎯 What happens next?</b>\n"
        f"Our expert team will configure your account with optimal parameters based on your unique trading profile.\n\n"
        f"💬 <b>Questions? We're here to help!</b>\n\n"
        f"🔥 <b>Let's build your trading success together!</b> 📈"
    )
    
    await query.edit_message_text(
        f"✅ <b>Welcome Message Generated for {user_name}</b>\n\n"
        f"📋 Copy and paste this message to the user:\n\n"
        f"<code>{welcome_template}</code>\n\n"
        f"When they click the link, they'll be connected to the registration system automatically.",
        parse_mode='HTML'
    )

async def show_privacy_instructions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show instructions for handling privacy-protected users."""
    query = update.callback_query
    await query.answer()
    
    user_name = context.user_data.get("privacy_user_name", "User")
    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    
    instructions = (
        f"📋 <b>Instructions for {user_name}</b>\n\n"
        f"🔐 Since this user has privacy settings enabled:\n\n"
        f"<b>🎯 Option 1 (Recommended):</b>\n"
        f"• 🔗 Click 'Generate Welcome Link'\n"
        f"• 📋 Copy the generated message\n"
        f"• 💬 Paste it in your chat with {user_name}\n\n"
        f"<b>⚙️ Option 2 (Manual):</b>\n"
        f"• 🔍 Tell them to search @{bot_username}\n"
        f"• 🚀 Ask them to send /start\n"
        f"• 📝 They'll be guided through registration\n\n"
        f"<b>💡 The welcome link method is faster and more professional!</b> ⚡"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Generate Welcome Link", callback_data="gen_welcome_privacy")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(instructions, parse_mode='HTML', reply_markup=reply_markup)
    

# --------------------------------------------- #
# ------------- Manual Entry Functions --------------- #
# --------------------------------------------- #
async def manual_entry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the 'Record Info Manually' button callback for hidden users."""
    query = update.callback_query
    await query.answer()
    
    print(f"Received manual entry callback: {query.data}")
    callback_data = query.data
    
    if callback_data.startswith("manual_"):
        try:
            session_id = callback_data[7:]  # Remove 'manual_' prefix
            print(f"Starting manual entry for session: {session_id}")
            
            # Store the session ID for the conversation
            context.user_data["manual_entry_session"] = session_id
            
            # Get hidden user info
            if "hidden_users" in context.bot_data and session_id in context.bot_data["hidden_users"]:
                user_name = context.bot_data["hidden_users"][session_id]["name"]
                
                await query.edit_message_text(
                    text=f"📝 Manual profile entry for {user_name}\n\n"
                         f"You'll now be asked a series of questions to fill in their profile.\n\n"
                         f"First, what is their risk appetite (1-10)?"
                )
                
                return RISK_APPETITE_MANUAL
            else:
                await query.edit_message_text(
                    text="⚠️ User session information not found. Please try forwarding a new message."
                )
                return ConversationHandler.END
        except Exception as e:
            print(f"Error processing manual entry callback: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error starting manual entry: {e}"
            )
            return ConversationHandler.END

async def risk_appetite_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle risk appetite input for manual entry."""
    try:
        risk = int(update.message.text)
        if 1 <= risk <= 10:
            # Store in user_data for conversation
            if "manual_entry_data" not in context.user_data:
                context.user_data["manual_entry_data"] = {}
            context.user_data["manual_entry_data"]["risk_appetite"] = risk
            
            await update.message.reply_text(
                "Thanks! Now, what is their approximate deposit amount? (100-10,000)"
            )
            return DEPOSIT_AMOUNT_MANUAL
        else:
            await update.message.reply_text("Please enter a number between 1 and 10.")
            return RISK_APPETITE_MANUAL
    except ValueError:
        await update.message.reply_text("Please enter a valid number between 1 and 10.")
        return RISK_APPETITE_MANUAL

async def deposit_amount_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle deposit amount input for manual entry."""
    try:
        amount = int(update.message.text)
        if 100 <= amount <= 10000:
            # Store in user_data for conversation
            context.user_data["manual_entry_data"]["deposit_amount"] = amount
            
            await update.message.reply_text(
                "Great! Finally, what is their trading account number? (e.g. TR12345678)"
            )
            return TRADING_ACCOUNT_MANUAL
        else:
            await update.message.reply_text("Please enter an amount between 100 and 10,000.")
            return DEPOSIT_AMOUNT_MANUAL
    except ValueError:
        await update.message.reply_text("Please enter a valid amount between 100 and 10,000.")
        return DEPOSIT_AMOUNT_MANUAL

async def trading_account_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle trading account input for manual entry."""
    account_number = update.message.text.strip()
    
    # Validate account format
    if not auth.validate_account_format(account_number):
        await update.message.reply_text("Invalid account format. Please enter a valid trading account number (e.g., TR12345678).")
        return TRADING_ACCOUNT_MANUAL
    
    # Store in user_data
    context.user_data["manual_entry_data"]["trading_account"] = account_number
    
    # Get session info
    session_id = context.user_data["manual_entry_session"]
    user_name = context.bot_data["hidden_users"][session_id]["name"]
    
    # Create a virtual user entry in the database using the session ID as reference
    virtual_user_id = f"virtual_{session_id[:8]}"
    
    # Add to database with manual entry data
    user_data = {
        "user_id": virtual_user_id,
        "first_name": user_name,
        "last_name": "Hidden User",
        "username": None,
        "risk_appetite": context.user_data["manual_entry_data"]["risk_appetite"],
        "deposit_amount": context.user_data["manual_entry_data"]["deposit_amount"],
        "trading_account": account_number,
        "is_verified": True,  # Mark as verified since admin is entering data
        "notes": f"Manually entered by admin. Original name: {user_name}"
    }
    
    # Save to database
    db.add_user(user_data)
    
    # Format collected data for review
    report = (
        f"✅ Manual profile completed for {user_name}\n\n"
        f"Risk Appetite: {context.user_data['manual_entry_data']['risk_appetite']}/10\n"
        f"Deposit Amount: ${context.user_data['manual_entry_data']['deposit_amount']}\n"
        f"Trading Account: {account_number}\n"
        f"Reference ID: {virtual_user_id}\n\n"
        f"This profile has been saved and marked as verified."
    )
    
    await update.message.reply_text(report)
    
    # Clean up conversation data
    del context.user_data["manual_entry_session"]
    del context.user_data["manual_entry_data"]
    
    return ConversationHandler.END


# --------------------------------------------- #
# ------------- Authenctication & Verifications --------------- #
# --------------------------------------------- #
async def start_authentication(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Start authentication process for new users."""
    # Check if user is already verified
    user_data = db.get_user(user_id)
    if user_data and user_data["is_verified"]:
        # User is already verified
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Welcome back! You're already verified in our system."
        )
        return
    
    # Start authentication with a button
    keyboard = [
        [InlineKeyboardButton("Complete Authentication", callback_data=f"auth_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Please complete authentication to access all features.",
        reply_markup=reply_markup
    )

async def auth_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle authentication button callback."""
    query = update.callback_query
    await query.answer()
    
    # Extract user_id from callback data
    callback_data = query.data
    if callback_data.startswith("auth_"):
        user_id = int(callback_data.split("_")[1])
        
        # Check if user can attempt authentication
        if not auth.can_attempt_auth(user_id):
            await query.edit_message_text(
                text="Too many failed attempts. Please try again later or contact an admin."
            )
            return ConversationHandler.END
        
        # Generate CAPTCHA
        captcha_question, captcha_answer = auth.generate_captcha()
        
        # Store the answer and user ID in user_data
        context.user_data["captcha_answer"] = captcha_answer
        context.user_data["auth_user_id"] = user_id
        
        # Store the chat_id where the auth process started
        context.user_data["auth_chat_id"] = update.effective_chat.id
        
        await query.edit_message_text(
            text=f"Authentication: {captcha_question} Reply with the number."
        )
        
        # This is crucial - we're returning a state to the conversation handler
        return CAPTCHA_RESPONSE

async def handle_captcha_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's response to CAPTCHA."""
    print(f"Received captcha response: {update.message.text}")
    print(f"User data: {context.user_data}")
    
    if "captcha_answer" in context.user_data and "auth_user_id" in context.user_data:
        try:
            user_answer = int(update.message.text.strip())
            expected_answer = context.user_data["captcha_answer"]
            user_id = context.user_data["auth_user_id"]
            
            print(f"User answer: {user_answer}, Expected: {expected_answer}")
            
            if user_answer == expected_answer:
                # Correct answer
                await update.message.reply_text("CAPTCHA solved correctly! Now please enter your trading account number for verification.")
                
                # Record successful attempt
                auth.record_attempt(user_id, True)
                
                # Keep the user_id for the trading account verification step
                context.user_data["pending_account_verify"] = user_id
                del context.user_data["captcha_answer"]
                del context.user_data["auth_user_id"]
                
                return TRADING_ACCOUNT
            else:
                # Incorrect answer
                await update.message.reply_text("Incorrect answer. Please try again.")
                
                # Record failed attempt
                auth.record_attempt(user_id, False)
                
                # Generate new CAPTCHA
                captcha_question, captcha_answer = auth.generate_captcha()
                context.user_data["captcha_answer"] = captcha_answer
                
                await update.message.reply_text(f"New authentication challenge: {captcha_question}")
                return CAPTCHA_RESPONSE
        except ValueError:
            await update.message.reply_text("Please enter a valid number.")
            return CAPTCHA_RESPONSE
    
    # If we get here, there's no CAPTCHA data in context
    # This usually means this is a regular message, not part of CAPTCHA verification
    print("No captcha data found in context")
    return ConversationHandler.END

async def handle_account_verification(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle trading account verification."""
    if "pending_account_verify" in context.user_data:
        user_id = context.user_data["pending_account_verify"]
        account_number = update.message.text.strip()
        
        # Validate account format
        if not auth.validate_account_format(account_number):
            await update.message.reply_text("Invalid account format. Please enter a valid trading account number (e.g., TR12345678).")
            return TRADING_ACCOUNT
        
        # Verify the account
        if auth.verify_account(account_number, user_id):
            # Account verified successfully
            await update.message.reply_text("Trading account verified successfully! You now have full access to the group.")
            
            # Mark user as verified in database
            db.mark_user_verified(user_id)
            
            # Update user info
            db.add_user({
                "user_id": user_id,
                "enhanced_trading_account": account_number,
                "is_verified": True
            })
            
            # Clear verification data
            del context.user_data["pending_account_verify"]
            
            # End conversation
            return ConversationHandler.END
        else:
            # Account not found or already linked
            await update.message.reply_text("Account not found or already linked to another user. Please contact an admin for assistance.")
            
            # Clear verification data
            del context.user_data["pending_account_verify"]
            
            # End conversation
            return ConversationHandler.END
    else:
        # Regular message handling
        pass

async def enhanced_trading_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Enhanced trading account verification with real-time balance checking."""
    account_number = update.message.text.strip()
    user_id = update.effective_user.id
    
    print(f"===== ENHANCED ACCOUNT VERIFICATION =====")
    print(f"Account: {account_number}, User: {user_id}")
    
    # Get user's stated deposit intention from conversation context
    user_info = context.user_data.get("user_info", {})
    stated_amount = user_info.get("deposit_amount", 0)
    
    print(f"User stated deposit intention: ${stated_amount}")
    
    await update.message.reply_text("🔍 Verifying your account and checking balance...")
    
    # Validate account format first
    if not auth.validate_account_format(account_number):
        await update.message.reply_text(
            "❌ Invalid account format. Please enter a valid trading account number."
        )
        return TRADING_ACCOUNT
    
    # Connect to MySQL and verify account
    mysql_db = get_mysql_connection()
    if not mysql_db.is_connected():
        await update.message.reply_text(
            "⚠️ Unable to verify account at the moment. Please try again later."
        )
        return TRADING_ACCOUNT
    
    # Get real account information including balance
    try:
        account_int = int(account_number)
        account_info = mysql_db.verify_account_exists(account_number)

        if not account_info['exists']:
            # Account not found...
            return TRADING_ACCOUNT
        elif not account_info.get('is_real_account', False):
            # NEW: Handle demo account
            await update.message.reply_text(
                "❌ Demo accounts are not eligible for VIP services.\n\n"
                f"Account Type: {account_info.get('account_type', 'Demo')}\n"
                f"Group: {account_info.get('group', 'Unknown')}\n\n" 
                "Please provide a real/live Vortex-FX trading account number."
            )
            return TRADING_ACCOUNT
        
        # Extract account details
        real_balance = float(account_info.get('balance', 0))
        account_name = account_info.get('name', 'Unknown')
        account_status = account_info.get('status', 'Unknown')
        
        print(f"Account found: {account_name}, Balance: ${real_balance}, Status: {account_status}")
        
        # Store account info in context for later use
        context.user_data["verified_account"] = {
            "account_number": account_number,
            "name": account_name,
            "balance": real_balance,
            "status": account_status,
            "full_info": account_info
        }
        
        # Store in database
        db.add_user({
            "user_id": user_id,
            "trading_account": account_number,
            "account_owner": account_name,
            "account_balance": real_balance,
            "account_status": account_status,
            "is_verified": True,
            "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Decision logic based on balance vs stated amount
        if real_balance >= stated_amount:
            return await handle_sufficient_funds(update, context, account_info, stated_amount, real_balance)
        elif real_balance > 0:
            return await handle_partial_funds(update, context, account_info, stated_amount, real_balance)
        else:
            return await handle_no_funds(update, context, account_info, stated_amount)
            
    except Exception as e:
        print(f"Error verifying account: {e}")
        await update.message.reply_text(
            f"⚠️ Error verifying account: {e}\n\nPlease try again or contact support."
        )
        return TRADING_ACCOUNT


# --------------------------------------------- #
# ------------- Conversation state functions --------------- #
# --------------------------------------------- #
async def handle_grant_vip_access_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin granting VIP access."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("grant_vip_"):
        parts = callback_data.split("_")
        if len(parts) >= 4:
            service_type = parts[2]  # signals, strategy, or all
            user_id = int(parts[3])
            
            await grant_vip_access_to_user(query, context, user_id, service_type)

async def grant_vip_access_to_user(query, context, user_id, service_type):
    """Grant VIP access to user and send invite links."""
    user_info = db.get_user(user_id) or {}
    user_name = user_info.get("first_name", "User")
    
    try:
        # Service mapping
        service_configs = {
            "signals": {
                "name": "VIP Signals",
                "channel_id": SIGNALS_CHANNEL_ID,
                "emoji": "🔔"
            },
            "strategy": {
                "name": "VIP Strategy", 
                "channel_id": STRATEGY_CHANNEL_ID,
                "emoji": "📈"
            },
            "all": {
                "name": "All VIP Services",
                "channels": [
                    ("VIP Signals", SIGNALS_CHANNEL_ID, "🔔"),
                    ("VIP Strategy", STRATEGY_CHANNEL_ID, "📈"),
                    ("VIP Prop Capital", PROP_CHANNEL_ID, "💰")
                ]
            }
        }
        
        invite_links = []
        service_names = []
        
        if service_type == "all":
            # Grant access to all services
            for service_name, channel_id, emoji in service_configs["all"]["channels"]:
                try:
                    invite_link = await context.bot.create_chat_invite_link(
                        chat_id=channel_id,
                        member_limit=1,
                        name=f"{service_name} invite for {user_name}"
                    )
                    # Create clickable link
                    invite_links.append(f"<a href='{invite_link.invite_link}'>{emoji} {service_name}</a>")
                    service_names.append(service_name)
                except Exception as e:
                    print(f"Error creating invite for {service_name}: {e}")
        else:
            # Grant access to single service
            service_config = service_configs[service_type]
            try:
                invite_link = await context.bot.create_chat_invite_link(
                    chat_id=service_config["channel_id"],
                    member_limit=1,
                    name=f"{service_config['name']} invite for {user_name}"
                )
                # Create clickable link
                invite_links.append(f"<a href='{invite_link.invite_link}'>{service_config['emoji']} {service_config['name']}</a>")
                service_names.append(service_config['name'])
            except Exception as e:
                print(f"Error creating invite for {service_config['name']}: {e}")
        
        if invite_links:
            # Send access links to user
            user_message = (
                f"<b>🎉 VIP Access Granted!</b>\n\n"
                f"<b>Welcome to {', '.join(service_names)}!</b>\n\n"
                f"<b>📋 Your exclusive invite links:</b>\n\n"
            )
            
            # Add clickable links
            for link in invite_links:
                user_message += f"• {link}\n"
            
            user_message += (
                f"\n<b>📝 Important Instructions:</b>\n"
                f"• Click each link to join\n"
                f"• Links expire after one use\n"
                f"• Enable notifications for updates\n"
                f"• Read pinned messages for guidelines\n\n"
                f"<b>🚀 Welcome to VFX Trading VIP!</b>"
            )
            
            await context.bot.send_message(
                chat_id=user_id,
                text=user_message,
                parse_mode='HTML'  # Make sure this is set to HTML
            )
            
            # Update admin with success
            await query.edit_message_text(
                f"<b>✅ VIP Access Granted Successfully!</b>\n\n"
                f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
                f"<b>📋 Services:</b> {', '.join(service_names)}\n"
                f"<b>🕒 Granted:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"<b>📧 Invite links sent to user</b>",
                parse_mode='HTML'
            )
            
            # Update database
            db.add_user({
                "user_id": user_id,
                "vip_access_granted": True,
                "vip_services": service_type,
                "vip_granted_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "vip_request_status": "approved"
            })
            
        else:
            await query.edit_message_text(
                f"<b>❌ Error Granting Access</b>\n\n"
                f"Failed to create invite links for {user_name}.\n"
                f"Please try again or contact technical support.",
                parse_mode='HTML'
            )
    
    except Exception as e:
        await query.edit_message_text(
            f"<b>❌ Error Granting VIP Access</b>\n\n"
            f"Error: {str(e)[:200]}\n"
            f"Please try again or contact technical support.",
            parse_mode='HTML'
        )

async def send_vip_request_to_admin(context, user_id, service_name, service_type):
    """Send VIP access request to admins."""
    user_info = db.get_user(user_id) or {}
    user_name = user_info.get("first_name", "User")
    account_number = user_info.get("trading_account", "Unknown")
    account_balance = user_info.get("account_balance", 0)
    
    # Admin notification with action buttons
    admin_message = (
        f"<b>🎯 VIP ACCESS REQUEST</b>\n\n"
        f"<b>👤 User:</b> {user_name} (ID: {user_id})\n"
        f"<b>📊 Account:</b> {account_number}\n"
        f"<b>💰 Balance:</b> ${account_balance:,.2f}\n"
        f"<b>🎯 Requested:</b> {service_name}\n"
        f"<b>🕒 Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"<b>✅ User has sufficient funds and verified account</b>"
    )
    
    # Create appropriate buttons based on service type
    if service_type == "signals":
        keyboard = [
            [InlineKeyboardButton("✅ Grant VIP Signals Access", callback_data=f"grant_vip_signals_{user_id}")],
            [InlineKeyboardButton("💬 Contact User First", callback_data=f"start_conv_{user_id}")],
            [InlineKeyboardButton("👤 View Full Profile", callback_data=f"view_profile_{user_id}")]
        ]
    elif service_type == "strategy":
        keyboard = [
            [InlineKeyboardButton("✅ Grant VIP Strategy Access", callback_data=f"grant_vip_strategy_{user_id}")],
            [InlineKeyboardButton("💬 Contact User First", callback_data=f"start_conv_{user_id}")],
            [InlineKeyboardButton("👤 View Full Profile", callback_data=f"view_profile_{user_id}")]
        ]
    elif service_type == "all":
        keyboard = [
            [InlineKeyboardButton("✅ Grant Both VIP Services", callback_data=f"grant_vip_all_{user_id}")],
            [InlineKeyboardButton("💬 Contact User First", callback_data=f"start_conv_{user_id}")],
            [InlineKeyboardButton("👤 View Full Profile", callback_data=f"view_profile_{user_id}")]
        ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error sending VIP request to admin {admin_id}: {e}")
    
    # Store request in database
    db.add_user({
        "user_id": user_id,
        "vip_request_type": service_type,
        "vip_request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "vip_request_status": "pending"
    })


# --------------------------------------------- #
# ------------- Deposit Flow Functions --------------- #
# --------------------------------------------- #
async def handle_deposit_flow_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """FIXED: Simplified deposit flow - direct to VortexFX portal only."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user_id = query.from_user.id
    
    print(f"Deposit flow callback: {callback_data}")
    
    if callback_data.startswith("deposit_exact_"):
        # DIRECT TO VORTEXFX INSTRUCTIONS ONLY
        amount = float(callback_data.split("_")[2])
        
        user_info = db.get_user(user_id) or {}
        account_number = user_info.get("trading_account", "Unknown")
        account_name = user_info.get("account_owner", "Unknown")
        
        # SIMPLIFIED VORTEXFX INSTRUCTIONS
        message = (
            f"<b>💰 Deposit ${amount:,.0f} Instructions</b>\n\n"
            f"<b>📋 Your Account:</b>\n"
            f"• Account: <b>{account_number}</b>\n"
            f"• Holder: <b>{account_name}</b>\n\n"
            f"<b>🌐 VortexFX Client Portal Steps:</b>\n\n"
            f"<b>1.</b> Visit: <a href='https://clients.vortexfx.com/en/dashboard'>VortexFX Portal</a> 🔗\n\n"
            f"<b>2.</b> Login → <b>Funds</b> → <b>Deposit</b> 📥\n\n"
            f"<b>3.</b> Select account: <b>{account_number}</b> ✅\n\n"
            f"<b>4.</b> Amount: <b>${amount:,.0f}</b> → Choose payment method 💰\n\n"
            f"<b>5.</b> Complete deposit ✅\n\n"
            f"<b>⏰ Processing:</b> 5-30 minutes\n"
            f"<b>💡 Tip:</b> Screenshot confirmation!"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔄 Check Balance", callback_data="check_balance_now")],
            [InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")],
            [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
        # Store and schedule balance checks
        db.add_user({
            "user_id": user_id,
            "target_deposit_amount": amount,
            "vortexfx_instructions_shown": True,
            "instruction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        
    elif callback_data == "choose_deposit_amount":
        # Show amount options with restart button
        message = (
            f"<b>💰 Choose Your Deposit Amount</b>\n\n"
            f"Select the amount you'd like to deposit:"
        )
        
        keyboard = [
            [
                InlineKeyboardButton("$500", callback_data="deposit_exact_500"),
                InlineKeyboardButton("$1,000", callback_data="deposit_exact_1000")
            ],
            [
                InlineKeyboardButton("$2,500", callback_data="deposit_exact_2500"),
                InlineKeyboardButton("$5,000", callback_data="deposit_exact_5000")
            ],
            [
                InlineKeyboardButton("$10,000", callback_data="deposit_exact_10000"),
                InlineKeyboardButton("💬 Custom Amount", callback_data="custom_amount")
            ],
            [
                InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
        
    elif callback_data == "custom_amount":
        await query.edit_message_text(
            "<b>💰 Custom Deposit Amount</b>\n\n"
            "Please type the amount you'd like to deposit.\n\n"
            "<b>Example:</b> 3000\n\n"
            "<b>Range:</b> $100 - $50,000 💎\n\n"
            "Or restart if you made a mistake:",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
            ])
        )
        
        context.bot_data.setdefault("user_states", {})
        context.bot_data["user_states"][user_id] = "awaiting_custom_amount"
        
    elif callback_data == "restart_process":
        # ALWAYS allow restart
        await restart_process(query, context)
        
    elif callback_data == "speak_advisor":  
        # Fixed advisor request
        await handle_advisor_request(query, context)

async def show_broker_deposit_instructions(query, context, amount):
    """Show VortexFX client portal deposit instructions only."""
    user_id = query.from_user.id
    user_info = db.get_user(user_id) or {}
    account_number = user_info.get("trading_account", "Unknown")
    account_name = user_info.get("account_owner", "Unknown")
    
    message = (
        f"<b>💰 How to Deposit ${amount:,.0f}</b>\n\n"
        f"<b>📋 Account Details:</b>\n"
        f"• Account: <b>{account_number}</b>\n"
        f"• Holder: <b>{account_name}</b>\n\n"
        f"<b>🌐 VortexFX Client Portal Steps:</b>\n\n"
        f"<b>1.</b> Visit: <a href='https://clients.vortexfx.com/en/dashboard'>Vortex-FX</a> 🔗\n\n"
        f"<b>2.</b> Login to your account 🔑\n\n"
        f"<b>3.</b> Left panel/menu → <b>Funds</b> → <b>Deposit</b> 📥\n\n"
        f"<b>4.</b> Select your current account: <b>{account_number}</b> ✅\n\n"
        f"<b>5.</b> Select currency: <b>USD</b> 💵\n\n"
        f"<b>6.</b> Choose your preferred payment method 💳\n\n"
        f"<b>7.</b> Enter amount: <b>${amount:,.0f}</b> 💰\n\n"
        f"<b>8.</b> Complete the deposit process ✅\n\n"
        f"<b>⏰ Processing Time:</b> 5-30 minutes\n"
        f"<b>💡 Tip:</b> Take a screenshot of your deposit confirmation!\n\n"
        f"Once completed, click <b>'Check Balance'</b> to verify your deposit! 🔄"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check My Balance Now", callback_data="check_balance_now")],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Store deposit attempt
    db.add_user({
        "user_id": user_id,
        "target_deposit_amount": amount,
        "deposit_instructions_shown": True,
        "vortexfx_instructions_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    



# --------------------------------------------- #
# ------------- VIP Access Management --------------- #
# --------------------------------------------- #
async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """HTML styled deposit amount question."""
    try:
        amount = int(update.message.text)
        if 100 <= amount <= 10000:
            user_id = update.effective_user.id
            
            # Store in user_data for conversation
            context.user_data["user_info"]["deposit_amount"] = amount
            
            # Update in database
            db.add_user({
                "user_id": user_id,
                "deposit_amount": amount
            })
            
            # HTML styled experience question
            await update.message.reply_text(
                "<b>📢 Quick question!</b>\n\n"
                "Are you interested in VFX Signals, the VFX Automated Strategy, or both? 🤖📊✅",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔔 VFX Signals", callback_data="interest_signals"),
                        InlineKeyboardButton("🤖 Automated Strategy", callback_data="interest_strategy")
                    ],
                    [InlineKeyboardButton("✅ Both Services", callback_data="interest_all")]
                ])
            )
            
            return TRADING_INTEREST
        else:
            await update.message.reply_text(
                "<b>⚠️ Invalid Amount</b>\n\n"
                "Please enter an amount between <b>$100</b> and <b>$10,000</b>. 💰",
                parse_mode='HTML'
            )
            return DEPOSIT_AMOUNT
    except ValueError:
        await update.message.reply_text(
            "<b>⚠️ Invalid Format</b>\n\n"
            "Please enter a valid amount between <b>$100</b> and <b>$10,000</b>.\n\n"
            "<b>Example:</b> 2500 💰",
            parse_mode='HTML'
        )
        return DEPOSIT_AMOUNT

async def risk_appetite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """HTML styled risk appetite question."""
    try:
        risk = int(update.message.text)
        if 1 <= risk <= 10:
            user_id = update.effective_user.id
            
            # Store in user_data
            if "user_info" not in context.user_data:
                context.user_data["user_info"] = {}
            context.user_data["user_info"]["risk_appetite"] = risk
            
            # Update in database
            db.add_user({
                "user_id": user_id,
                "risk_appetite": risk
            })
            
            # HTML styled funding question
            await update.message.reply_text(
                "<b>💰 Let's talk funding!</b>\n\n"
                "How much capital are you planning to fund your account with? 📥\n\n"
                "<b>Example:</b> 5000",
                parse_mode='HTML'
            )
            return DEPOSIT_AMOUNT
        else:
            await update.message.reply_text(
                "<b>⚠️ Invalid Risk Level</b>\n\n" 
                "Please enter a number between <b>1</b> and <b>10</b>. 📊",
                parse_mode='HTML'
            )
            return RISK_APPETITE
    except ValueError:
        await update.message.reply_text(
            "<b>⚠️ Invalid Format</b>\n\n"
            "Please enter a valid number between <b>1</b> and <b>10</b>.\n\n"
            "<b>Example:</b> 7 📊",
            parse_mode='HTML'
        )
        return RISK_APPETITE

async def trading_interest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle selection of trading interests and route to appropriate VIP channels."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    callback_data = query.data
    interest = callback_data.replace("interest_", "")
    
    # Store the interest in user data
    if "user_info" not in context.user_data:
        context.user_data["user_info"] = {}
    context.user_data["user_info"]["trading_interest"] = interest
    
    # Update in database
    db.add_user({
        "user_id": user_id,
        "trading_interest": interest
    })
    
    # Map interests to appropriate VIP channels
    vip_channels = {
        "signals": {"name": "VIP Signals", "channel_id": SIGNALS_CHANNEL_ID, "group_id": SIGNALS_GROUP_ID},
        "strategy": {"name": "VIP Strategy", "channel_id": STRATEGY_CHANNEL_ID, "group_id": STRATEGY_GROUP_ID},
        "propcapital": {"name": "VIP Prop Capital", "channel_id": PROP_CHANNEL_ID, "group_id": PROP_GROUP_ID},
    }
    
    # Store assigned channels in user data for admin reference
    assigned_channels = []
    
    if interest == "all":
        for channel_info in vip_channels.values():
            assigned_channels.append(channel_info)
        # Update with list of all channel names
        interest_display = "All VIP Services (Signals, Strategy, Prop Capital)"
    else:
        assigned_channels.append(vip_channels[interest])
        # Get user-friendly name for display
        interest_display = f"VIP {interest.capitalize()}"
    
    # Store in user data for later reference
    context.user_data["user_info"]["assigned_channels"] = assigned_channels
    
    # Confirm selection to user with clear next steps
    await query.edit_message_text(
        f"Thanks for selecting {interest_display}! 🎯\n\n"
        f"Now, please enter your Vortex FX MT5 account number for verification."
    )
    
    return TRADING_ACCOUNT


# --------------------------------------------- #
# ------------- User Management System --------------- #
# --------------------------------------------- #
async def process_account_number_text(update, context, user_id, message_text):
    """Enhanced account processing with VortexFX registration help."""
    print(f"Processing account number: {message_text}")
    
    # Check if user needs to create an account first
    if message_text.lower() in ["no", "don't have", "need account", "create account", "new account"]:
        await handle_new_account_needed(update, context, user_id)
        return
    
    if message_text.isdigit() and len(message_text) == 6:
        account_number = message_text
        
        # Get user's stated deposit intention
        user_info = db.get_user(user_id)
        stated_amount = user_info.get("deposit_amount", 0) if user_info else 0
        
        print(f"===== ACCOUNT VERIFICATION =====")
        print(f"Account: {account_number}, User: {user_id}, Stated: ${stated_amount}")
        
        await update.message.reply_text(
            "<b>🔍 Verifying Your Account...</b>\n\n"
            "Please wait while we check your account details and balance... ⏳",
            parse_mode='HTML'
        )
        
        # Validate and verify account
        if not auth.validate_account_format(account_number):
            await update.message.reply_text(
                "<b>❌ Invalid Account Format</b>\n\n"
                "Please enter a valid 6-digit trading account number.\n\n"
                "<b>💡 Don't have an account yet?</b> Type 'new account' and I'll help you create one!",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🆕 Create New Account", callback_data="need_new_account")],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="restart_process")]
                ])
            )
            return
        
        # Connect to MySQL and verify
        mysql_db = get_mysql_connection()
        if not mysql_db.is_connected():
            await update.message.reply_text(
                "<b>⚠️ Connection Issue</b>\n\n"
                "Unable to verify account at the moment. Please try again later.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
                ])
            )
            return
        
        try:
            account_info = mysql_db.verify_account_exists(account_number)

            if not account_info['exists']:
                await handle_account_not_found(update, context, user_id, account_number)
                return
            elif not account_info.get('is_real_account', False):
                await handle_demo_account(update, context, user_id, account_number, account_info)
                return
            
            # Account exists and is real - proceed with balance check
            await handle_real_account_found(update, context, user_id, account_info, stated_amount)
            
        except Exception as e:
            print(f"Error in verification: {e}")
            await update.message.reply_text(
                f"<b>⚠️ Verification Error</b>\n\n"
                f"There was an issue verifying your account. Please try again or contact support.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
                    [InlineKeyboardButton("🔄 Try Again", callback_data="restart_process")]
                ])
            )
    else:
        await update.message.reply_text(
            "<b>⚠️ Invalid Format</b>\n\n"
            "Please provide a valid Vortex-FX MT5 account number.\n\n"
            "<b>💡 Examples:</b> 123456, 789012\n\n"
            "<b>🆕 Don't have an account?</b> I can help you create one!",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🆕 Create VortexFX Account", callback_data="need_new_account")],
                [InlineKeyboardButton("💬 Get Help", callback_data="speak_advisor")]
            ])
        )

async def handle_new_account_needed(update, context, user_id):
    """Guide user through creating a new VortexFX account."""
    user_info = db.get_user(user_id)
    user_name = user_info.get('first_name', 'there') if user_info else 'there'
    
    account_creation_guide = (
        f"<b>🆕 Let's Create Your VortexFX Account!</b>\n\n"
        f"Hi {user_name}! No worries - creating a VortexFX account is quick and free! 🎉\n\n"
        
        f"<b>📋 What You'll Need:</b>\n"
        f"• Valid email address\n"
        f"• Phone number\n"
        f"• 2-3 minutes of your time\n\n"
        
        f"<b>🚀 Quick Setup Process:</b>\n"
        f"1. Click the registration link below\n"
        f"2. Fill in your basic details\n"
        f"3. Verify your email\n"
        f"4. Get your Vortex-FX account number\n"
        f"5. Come back here and enter it!\n\n"
        
        f"<b>💰 Ready to start?</b>\n"
        f"Click below to create your FREE VortexFX account:"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔗 Create VortexFX Account (FREE)", 
                            url="https://clients.vortexfx.com/register?referral=0195a843-2b1c-7339-9088-57b56b4aa753")],
        [InlineKeyboardButton("✅ I Created My Account", callback_data="account_created")],
        [InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        account_creation_guide,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set state to waiting for new account
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "creating_new_account"

async def need_new_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'Create New Account' button."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    await handle_new_account_needed(query, context, user_id)

async def account_created_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle when user says they created their account."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "<b>🎉 Awesome! Welcome to VortexFX!</b>\n\n"
        
        "<b>📧 Check Your Email</b>\n"
        "VortexFX should have sent you a welcome email with your account details.\n\n"
        
        "<b>🔢 Find Your Account Number</b>\n"
        "Your Vortex-FX account number should be in:\n"
        "• The welcome email\n"
        "• Your VortexFX dashboard\n"
        "• MT5 platform login details\n\n"
        
        "<b>💡 Example:</b> If you see 'Login ID: 123456', then your account number is <code>123456</code>\n\n"
        
        "<b>✍️ Please type your account number below:</b>",
        parse_mode='HTML'
    )
    
    # Set state to waiting for account number
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"

async def handle_account_not_found(update, context, user_id, account_number):
    """Handle when account is not found in database."""
    not_found_message = (
        f"<b>❌ Account Not Found</b>\n\n"
        f"We couldn't find account <code>{account_number}</code> in our system.\n\n"
        
        f"<b>💡 Common Solutions:</b>\n\n"
        
        f"<b>1. Double-check the number:</b>\n"
        f"• Make sure all 6 digits are correct\n"
        f"• Check your VortexFX welcome email\n"
        f"• Log into your VortexFX dashboard\n\n"
        
        f"<b>2. Account might be very new:</b>\n"
        f"• Wait 1-5 minutes after creation\n"
        f"• Then try again\n\n"
        
        f"<b>3. Need to create an account?</b>\n"
        f"• Click below to register for free\n\n"
        
        f"<b>What would you like to do?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Try Different Number", callback_data="retry_account_number")],
        [InlineKeyboardButton("🆕 Create New Account", 
                            url="https://clients.vortexfx.com/register?referral=0195a843-2b1c-7339-9088-57b56b4aa753")],
        [InlineKeyboardButton("⏰ Wait & Try Again", callback_data="wait_and_retry")],
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        not_found_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def handle_demo_account(update, context, user_id, account_number, account_info):
    """Handle when user provides a demo account."""
    demo_message = (
        f"<b>⚠️ Demo Account Detected</b>\n\n"
        f"<b>Account:</b> <code>{account_number}</code>\n"
        f"<b>Type:</b> {account_info.get('account_type', 'Demo')}\n"
        f"<b>Group:</b> {account_info.get('group', 'Unknown')}\n\n"
        
        f"<b>🚫 Demo accounts cannot be used for VIP services.</b>\n\n"
        
        f"<b>💡 What you need:</b>\n"
        f"• A REAL/LIVE VortexFX trading account\n"
        f"• Minimum $100 deposit for VIP access\n\n"
        
        f"<b>🆕 Don't have a real account yet?</b>\n"
        f"No problem! Creating one is free and takes 2 minutes:\n\n"
        
        f"<b>What would you like to do?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🆕 Create Real Account (FREE)", 
                            url="https://clients.vortexfx.com/register?referral=0195a843-2b1c-7339-9088-57b56b4aa753")],
        [InlineKeyboardButton("🔢 Use Different Account", callback_data="retry_account_number")],
        [InlineKeyboardButton("💬 Get Help", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        demo_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def handle_real_account_found(update, context, user_id, account_info, stated_amount):
    """Handle when a real account is found and verified."""
    real_balance = float(account_info.get('balance', 0))
    account_name = account_info.get('name', 'Unknown')
    account_number = account_info.get('account_number', 'Unknown')
    
    print(f"Real account found: {account_name}, Balance: ${real_balance}")
    
    # Store account info
    db.add_user({
        "user_id": user_id,
        "trading_account": account_number,
        "account_owner": account_name,
        "account_balance": real_balance,
        "is_verified": True,
        "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Check balance status and guide user accordingly
    if real_balance >= 100:
        await handle_sufficient_balance(update, context, user_id, account_info, real_balance)
    elif real_balance > 0:
        await handle_partial_balance(update, context, user_id, account_info, real_balance, stated_amount)
    else:
        await handle_zero_balance(update, context, user_id, account_info, stated_amount)

async def handle_sufficient_balance(update, context, user_id, account_info, balance):
    """Handle user with sufficient balance for VIP access."""
    success_message = (
        f"<b>🎉 CONGRATULATIONS! 🎉</b>\n\n"
        
        f"<b>✅ Account Verified Successfully!</b>\n"
        f"<b>📊 Account:</b> {account_info['account_number']}\n"
        f"<b>👤 Owner:</b> {account_info['name']}\n"
        f"<b>💰 Balance:</b> ${balance:,.2f}\n\n"
        
        f"<b>🌟 You qualify for FULL VIP ACCESS! 🌟</b>\n\n"
        
        f"<b>🎯 What You Get:</b>\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 🤖 Automated Trading Strategy\n"
        f"• 📊 Professional Market Analysis\n"
        f"• 👨‍💼 Priority Customer Support\n"
        f"• 💰 Advanced Risk Management\n\n"
        
        f"<b>💡 Dashboard Access:</b>\n"
        f"Use <b>/myaccount</b> anytime to:\n"
        f"• Check your account status 📊\n"
        f"• Edit your profile settings ✏️\n"
        f"• View your VIP services 🌟\n"
        f"• Contact support 💬\n\n"
        
        f"<b>🚀 Ready to activate your VIP services?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔔 Activate VIP Signals", callback_data="request_vip_signals")],
        [InlineKeyboardButton("🤖 Activate Automated Trading", callback_data="request_vip_strategy")],
        [InlineKeyboardButton("✨ Activate BOTH Services", callback_data="request_vip_both_services")],
        [InlineKeyboardButton("📊 View My Dashboard", callback_data="back_to_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(success_message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Mark user as VIP eligible
    db.add_user({
        "user_id": user_id,
        "vip_eligible": True,
        "funding_status": "sufficient",
        "vip_access_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

async def handle_partial_balance(update, context, user_id, account_info, balance, target_amount):
    """Handle user with some balance but not enough for VIP."""
    needed = max(100 - balance, 0)
    percentage = (balance / 100) * 100
    
    partial_message = (
        f"<b>✅ Account Verified Successfully!</b>\n\n"
        
        f"<b>📊 Account:</b> {account_info['account_number']}\n"
        f"<b>👤 Owner:</b> {account_info['name']}\n"
        f"<b>💰 Current Balance:</b> ${balance:,.2f}\n"
        f"<b>🎯 VIP Requirement:</b> $100.00\n"
        f"<b>📈 You're {percentage:.1f}% there!</b>\n\n"
        
        f"<b>💡 Almost Ready for VIP Access!</b>\n\n"
        
        f"<b>To unlock VIP services, you need:</b>\n"
        f"• ${needed:,.2f} more in your account\n"
        f"• Then you get full access to all premium features!\n\n"
        
        f"<b>What would you like to do?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit ${needed:,.0f} Now", callback_data=f"deposit_exact_{needed}")],
        [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("📊 Use Current Balance", callback_data="proceed_with_current")],
        [InlineKeyboardButton("📋 View My Dashboard", callback_data="back_to_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(partial_message, parse_mode='HTML', reply_markup=reply_markup)

async def handle_zero_balance(update, context, user_id, account_info, target_amount):
    """Handle user with zero balance."""
    minimum_deposit = max(target_amount or 100, 100)
    
    zero_balance_message = (
        f"<b>✅ Account Verified Successfully!</b>\n\n"
        
        f"<b>📊 Account:</b> {account_info['account_number']}\n"
        f"<b>👤 Owner:</b> {account_info['name']}\n"
        f"<b>💰 Current Balance:</b> $0.00\n\n"
        
        f"<b>🚀 Ready to Start Your Trading Journey?</b>\n\n"
        
        f"<b>💎 To unlock VIP access:</b>\n"
        f"• Minimum deposit: $100\n"
        f"• Recommended: ${minimum_deposit:,} for better results\n\n"
        
        f"<b>🌟 What You'll Get:</b>\n"
        f"• Professional trading signals\n"
        f"• Automated trading strategies\n"
        f"• 24/7 market monitoring\n"
        f"• Expert support team\n\n"
        
        f"<b>How much would you like to deposit?</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("💳 Deposit $100", callback_data="deposit_exact_100")],
        [InlineKeyboardButton("💰 Deposit $500", callback_data="deposit_exact_500")],
        [InlineKeyboardButton("💎 Deposit $1000", callback_data="deposit_exact_1000")],
        [InlineKeyboardButton("🎯 Choose Custom Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("📋 View My Dashboard", callback_data="back_to_dashboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(zero_balance_message, parse_mode='HTML', reply_markup=reply_markup)

# Additional helper callbacks
async def retry_account_number_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Allow user to try a different account number."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    await query.edit_message_text(
        "<b>🔢 Enter Your Account Number</b>\n\n"
        "Please provide your VortexFX MT5 account number:\n\n"
        "<b>💡 Tips:</b>\n"
        "• Check your VortexFX welcome email\n"
        "• Look in your MT5 platform\n"
        "• Visit your VortexFX dashboard\n\n"
        "<b>📝 Type your account number:</b>",
        parse_mode='HTML'
    )
    
    # Set state back to account number entry
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "account_number"

async def wait_and_retry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle wait and retry for new accounts."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "<b>⏰ Account Processing...</b>\n\n"
        "If you just created your VortexFX account, it might take a few minutes "
        "to appear in our system.\n\n"
        "<b>⏳ Please wait 1-5 minutes, then try again.</b>\n\n"
        "In the meantime, make sure you:\n"
        "• Verified your email address\n"
        "• Completed the registration form\n"
        "• Have your Vortex-FX MT5 account number ready\n\n"
        "<b>Ready to try again?</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Try Again Now", callback_data="retry_account_number")],
            [InlineKeyboardButton("💬 Get Help", callback_data="speak_advisor")]
        ])
    )

async def show_deposit_instructions_enhanced(query, context, amount):
    """Enhanced deposit instructions with dashboard access."""
    user_id = query.from_user.id
    user_info = db.get_user(user_id) or {}
    account_number = user_info.get("trading_account", "Unknown")
    account_name = user_info.get("account_owner", "Unknown")
    
    message = (
        f"<b>💰 How to Deposit ${amount:,.0f}</b>\n\n"
        f"<b>📋 Account Details:</b>\n"
        f"• Account: <b>{account_number}</b>\n"
        f"• Holder: <b>{account_name}</b>\n\n"
        f"<b>🌐 VortexFX Client Portal Steps:</b>\n\n"
        f"<b>1.</b> Visit: <a href='https://clients.vortexfx.com/en/dashboard'>Vortex-FX</a> 🔗\n\n"
        f"<b>2.</b> Login → <b>Funds</b> → <b>Deposit</b> 📥\n\n"
        f"<b>3.</b> Select account → Amount: <b>${amount:,.0f}</b> 💰\n\n"
        f"<b>4.</b> Complete the deposit process ✅\n\n"
        f"<b>⏰ Processing Time:</b> 5-30 minutes\n\n"
        
        f"<b>💡 After Depositing:</b>\n"
        f"• Use <b>/myaccount</b> to check your updated balance\n"
        f"• Click 'Refresh Balance' to verify your deposit\n"
        f"• Request VIP access once verified! 🌟"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check My Balance", callback_data="check_balance_now")],
        [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
        [InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)


# -------------------------------------- HELPER Flow Functions ---------------------------------------------------- #
# ---------------------------------------------------------------------------------------------------------- #

async def start_guided_setup(query, context, user_id):
    """Start the guided setup process."""
    # Clear any existing state
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Start with risk profile selection
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>🚀 Guided Setup Started!</b>\n\n"
        "<b>Step 1 of 4: Risk Profile</b>\n\n"
        "What risk profile defines your trading style?\n\n"
        "💰 <b>Low Risk:</b> Conservative approach, steady growth\n"
        "📈 <b>Medium Risk:</b> Balanced strategy, moderate returns\n"
        "🚀 <b>High Risk:</b> Aggressive trading, maximum potential\n\n"
        "Choose your preferred risk level:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )    

async def handle_risk_selection(query, context, user_id, callback_data):
    """Handle risk profile button selection with progress indicator."""
    risk_option = callback_data.replace("risk_", "")
    
    # Map text options to numeric values
    risk_values = {"low": 2, "medium": 5, "high": 8}
    risk_appetite = risk_values.get(risk_option, 5)
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "risk_appetite": risk_appetite,
        "risk_profile_text": risk_option,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await query.edit_message_text(
        f"<b>✅ Step 1 Completed: Risk Profile</b>\n\n"
        f"<b>Selected:</b> {risk_option.capitalize()} Risk ✅\n\n"
        f"<b>Step 2 of 4: Funding Amount</b>\n\n"
        f"<b>💰 Let's talk funding!</b>\n\n"
        f"How much capital are you planning to fund your account with? 📥\n\n"
        f"<b>💡 Just type the amount (example: 5000)</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
        ])
    )
    
    # Update state
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "deposit_amount"
    
    # Notify admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📊 User {user_id} selected risk profile: {risk_option.capitalize()}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def handle_interest_selection(query, context, user_id, callback_data):
    """Handle trading interest/service selection with progress."""
    interest = callback_data.replace("interest_", "")
    
    # Store in database
    db.add_user({
        "user_id": user_id,
        "trading_interest": interest,
        "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Map interests for display
    interest_display = {
        "signals": "VFX Signals",
        "strategy": "VFX Automated Strategy", 
        "all": "Both VFX Services"
    }.get(interest, interest.capitalize())
    
    await query.edit_message_text(
        f"<b>✅ Step 3 Completed: Service Selection</b>\n\n"
        f"<b>Selected:</b> {interest_display} ✅\n\n"
        f"<b>Step 4 of 4: Account Verification</b>\n\n"
        f"<b>📊 Final Step!</b>\n\n"
        f"Please enter your <b>Vortex-FX MT5 account number</b> for verification:\n\n",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
        ])
    )
    
    # Update state
    context.bot_data["user_states"][user_id] = "account_number"
    
    # Notify admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🎯 User {user_id} selected service: {interest_display}"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def handle_deposit_selection(query, context, user_id, callback_data):
    """Handle deposit amount selection."""
    amount = float(callback_data.split("_")[2])
    
    user_info = db.get_user(user_id) or {}
    account_number = user_info.get("trading_account", "Unknown")
    account_name = user_info.get("account_owner", "Unknown")
    
    # DIRECT TO VORTEXFX INSTRUCTIONS
    message = (
        f"<b>💰 Deposit ${amount:,.0f} Instructions</b>\n\n"
        f"<b>📋 Your Account:</b>\n"
        f"• Account: <b>{account_number}</b>\n"
        f"• Holder: <b>{account_name}</b>\n\n"
        f"<b>🌐 VortexFX Client Portal Steps:</b>\n\n"
        f"<b>1.</b> Visit: <a href='https://clients.vortexfx.com/en/dashboard'>VortexFX Portal</a> 🔗\n\n"
        f"<b>2.</b> Login → <b>Funds</b> → <b>Deposit</b> 📥\n\n"
        f"<b>3.</b> Select account: <b>{account_number}</b> ✅\n\n"
        f"<b>4.</b> Amount: <b>${amount:,.0f}</b> → Choose payment method 💰\n\n"
        f"<b>5.</b> Complete deposit ✅\n\n"
        f"<b>⏰ Processing:</b> 5-30 minutes\n"
        f"<b>💡 Tip:</b> Screenshot confirmation!"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Check Balance", callback_data="check_balance_now")],
        [InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")],
        [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Store deposit target and schedule balance checks
    db.add_user({
        "user_id": user_id,
        "target_deposit_amount": amount,
        "vortexfx_instructions_shown": True,
        "instruction_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Update state
    context.bot_data["user_states"][user_id] = "deposit_instructions_shown"
    
async def show_deposit_amount_options(query, context, user_id):
    """Show deposit amount selection options."""
    message = (
        f"<b>💰 Choose Your Deposit Amount</b>\n\n"
        f"Select the amount you'd like to deposit:"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("$500", callback_data="deposit_exact_500"),
            InlineKeyboardButton("$1,000", callback_data="deposit_exact_1000")
        ],
        [
            InlineKeyboardButton("$2,500", callback_data="deposit_exact_2500"),
            InlineKeyboardButton("$5,000", callback_data="deposit_exact_5000")
        ],
        [
            InlineKeyboardButton("$10,000", callback_data="deposit_exact_10000"),
            InlineKeyboardButton("💬 Custom Amount", callback_data="custom_amount")
        ],
        [
            InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, parse_mode='HTML', reply_markup=reply_markup)

async def handle_custom_amount_request(query, context, user_id):
    """Handle request for custom deposit amount."""
    await query.edit_message_text(
        "<b>💰 Custom Deposit Amount</b>\n\n"
        "Please type the amount you'd like to deposit.\n\n"
        "<b>Example:</b> 3000\n\n"
        "<b>Range:</b> $100 - $50,000 💎\n\n"
        "Or restart if you made a mistake:",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
        ])
    )
    
    # Set state to await custom amount
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "awaiting_custom_amount"

async def handle_vip_request(query, context, user_id, callback_data):
    """Handle VIP access request."""
    service_type = callback_data.replace("request_vip_", "")
    
    # Map service types
    service_names = {
        "signals": "VIP Signals",
        "strategy": "VIP Strategy", 
        "both_services": "Both VIP Services"
    }
    
    service_name = service_names.get(service_type, service_type)
    service_db_type = "all" if service_type == "both_services" else service_type
    
    user_info = db.get_user(user_id) or {}
    user_name = user_info.get("first_name", "User")
    account_number = user_info.get("trading_account", "Unknown")
    account_balance = user_info.get("account_balance", 0)
    if account_number:
        mysql_db = get_mysql_connection()
        if mysql_db.is_connected():
            try:
                account_info = mysql_db.verify_account_exists(account_number)
                if account_info['exists']:
                    account_balance = float(account_info.get('balance', 0))
                else:
                    account_balance = 0
            except:
                account_balance = user_info.get("account_balance", 0)  # Fallback to stored
        else:
            account_balance = user_info.get("account_balance", 0)  # Fallback to stored
    else:
        account_balance = 0
    
    
    # User confirmation
    await query.edit_message_text(
        f"<b>✅ Request Submitted!</b>\n\n"
        f"<b>📋 Service Requested:</b> {service_name}\n"
        f"<b>📊 Account:</b> {account_number}\n"
        f"<b>💰 Balance:</b> ${account_balance:,.2f}\n\n"
        f"<b>🕒 Processing Time:</b> 5-15 minutes\n"
        f"<b>📧 You'll receive access links via this chat</b>\n\n"
        f"<b>💡 While You Wait:</b>\n"
        f"• Use <b>/myaccount</b> to check your dashboard\n"
        f"• Your request status will be updated there\n"
        f"• You can edit your profile anytime\n\n"
      
        f"Thank you for choosing VFX Trading! 🚀",
        parse_mode='HTML'
    )
    
    # Send request to admins
    await send_vip_request_to_admin(context, user_id, service_name, service_db_type)

async def restart_process(query, context, user_id):
    """Handle process restart."""
    # Clear ALL conversation states
    if "user_states" in context.bot_data and user_id in context.bot_data["user_states"]:
        del context.bot_data["user_states"][user_id]
    
    # Reset database state (but keep basic user info)
    try:
        user_info = db.get_user(user_id)
        if user_info:
            db.add_user({
                "user_id": user_id,
                "risk_appetite": None,
                "deposit_amount": None,
                "trading_account": None,
                "is_verified": False,
                "funding_status": "restarted",
                "vip_request_status": "cancelled",
                "restart_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        print(f"Error resetting user data: {e}")
    
    # Start fresh
    keyboard = [
        [
            InlineKeyboardButton("Low Risk", callback_data="risk_low"),
            InlineKeyboardButton("Medium Risk", callback_data="risk_medium"),
            InlineKeyboardButton("High Risk", callback_data="risk_high")
        ],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>🔄 Process Restarted!</b>\n\n"
        "Let's start fresh! What risk profile would you like on your account?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Set initial state
    context.bot_data.setdefault("user_states", {})
    context.bot_data["user_states"][user_id] = "risk_profile"
    
    # Notify admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🔄 User {user_id} restarted the registration process"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def handle_advisor_request(query, context, user_id):
    """Handle speak to advisor request."""
    user_info = db.get_user(user_id) or {}
    user_name = user_info.get("first_name", "User")
    account_number = user_info.get("trading_account", "Unknown")
    
    # User confirmation
    await query.edit_message_text(
        "<b>🔄 Connecting you with an advisor...</b>\n\n"
        "✅ <b>Your request has been sent to our team</b>\n"
        "✅ <b>An advisor will contact you shortly</b>\n"
        "✅ <b>Average response time: 5-15 minutes</b>\n\n"
        
        "<b>💡 While You Wait:</b>\n"
        "• Use <b>/myaccount</b> to check your profile\n"
        "• You can update your information anytime\n"
        "• Keep this chat open for their response 💬\n\n"
        
        "Please keep this chat open to receive their message! 📱",
        parse_mode='HTML'
    )
    
    # Send to admins
    admin_message = (
        f"<b>💬 ADVISOR REQUEST</b>\n\n"
        f"<b>👤 User:</b> {user_name}\n"
        f"<b>🆔 User ID:</b> {user_id}\n"
        f"<b>📊 Account:</b> {account_number}\n"
        f"<b>🕒 Time:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"<b>🎯 User wants to speak with an advisor</b>"
    )
    
    admin_keyboard = [
        [InlineKeyboardButton("💬 Start Conversation Now", callback_data=f"start_conv_{user_id}")],
        [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{user_id}")]
    ]
    admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=admin_reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")
    
    # Store request
    db.add_user({
        "user_id": user_id,
        "advisor_requested": True,
        "advisor_request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

async def check_balance(query, context, user_id):
    """Handle balance check request."""
    user_info = db.get_user(user_id)
    if not user_info or not user_info.get("trading_account"):
        await query.edit_message_text(
            "<b>⚠️ Account Information Missing</b>\n\n"
            "No account information found. Please complete verification first.\n\n"
            "<b>💡 Use /myaccount to check your registration status!</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
                [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
            ])
        )
        return
    
    account_number = user_info["trading_account"]
    
    # Show loading
    await query.edit_message_text(
        "<b>🔍 Checking Your Balance...</b>\n\n"
        "Please wait while we verify your current account balance...\n\n"
        "<b>💡 Tip:</b> You can always check your status with /myaccount",
        parse_mode='HTML'
    )
    
    # Check current balance (existing logic)
    mysql_db = get_mysql_connection()
    if not mysql_db.is_connected():
        await context.bot.send_message(
            chat_id=user_id,
            text="<b>⚠️ Connection Issue</b>\n\n"
                 "Unable to check balance at the moment. Please try again later.\n\n"
                 "<b>💡 Use /myaccount to access your dashboard!</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")]
            ])
        )
        return
    
    try:
        current_info = mysql_db.verify_account_exists(account_number)
        
        if not current_info['exists']:
            await context.bot.send_message(
                chat_id=user_id,
                text="<b>⚠️ Account Not Found</b>\n\n"
                     "Please contact support for assistance.\n\n"
                     "<b>💡 Use /myaccount to view your profile and contact support!</b>",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
                    [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
                ])
            )
            return
        
        current_balance = float(current_info.get('balance', 0))
        previous_balance = user_info.get("account_balance", 0)
        account_name = current_info.get('name', 'Unknown')
        
        # Check if balance increased
        if current_balance > previous_balance:
            balance_change = current_balance - previous_balance
            status_emoji = "📈"
            status_text = f"<b>Increased by ${balance_change:,.2f}!</b> 🎉"
        elif current_balance < previous_balance:
            balance_change = previous_balance - current_balance  
            status_emoji = "📉"
            status_text = f"<b>Decreased by ${balance_change:,.2f}</b>"
        else:
            status_emoji = "💰"
            status_text = "<b>No change since last check</b>"
        
        # Update stored balance
        db.add_user({
            "user_id": user_id,
            "account_balance": current_balance,
            "last_balance_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Format response with dashboard mention
        balance_message = (
            f"<b>{status_emoji} Balance Update</b>\n\n"
            f"<b>📋 Account:</b> {account_number}\n"
            f"<b>👤 Holder:</b> {account_name}\n"
            f"<b>💰 Current Balance:</b> ${current_balance:,.2f}\n"
            f"<b>📊 Status:</b> {status_text}\n"
            f"<b>🕒 Last Checked:</b> {datetime.now().strftime('%H:%M:%S')}\n\n"
            
            f"<b>💡 Dashboard Access:</b>\n"
            f"Use <b>/myaccount</b> to view your complete profile anytime! 📊\n\n"
        )
        
        # Add appropriate buttons
        target_amount = user_info.get("target_deposit_amount", 0) or user_info.get("deposit_amount", 0)
        if current_balance >= 100 and target_amount > 0:
            balance_message += "<b>🎉 You qualify for VIP access!</b>"
            keyboard = [
                [InlineKeyboardButton("🎯 Request VIP Access", callback_data="request_vip_both_services")],
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_balance_now")]
            ]
        elif target_amount > 0:
            remaining = max(100 - current_balance, 0)
            balance_message += f"<b>💡 ${remaining:,.2f} more needed for VIP access</b>"
            keyboard = [
                [InlineKeyboardButton("💳 Add Funds", callback_data="choose_deposit_amount")],
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_balance_now")]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_balance_now")],
                [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")]
            ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=balance_message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        print(f"Error in enhanced balance check: {e}")
        await context.bot.send_message(
            chat_id=user_id,
            text=f"<b>⚠️ Balance Check Error</b>\n\n"
                 f"Error checking balance. Please try again.\n\n"
                 f"<b>💡 Use /myaccount to access your dashboard!</b>",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 My Dashboard", callback_data="back_to_dashboard")]
            ])
        )


async def handle_text_response(update, context, user_id, message_text):
    """Handle all text message responses based on current state."""
    user_states = context.bot_data.get("user_states", {})
    current_step = user_states.get(user_id) or user_states.get(str(user_id))
    
    print(f"Text response from user {user_id}: '{message_text}', current_step: {current_step}")
    
    # Handle custom amount input
    if current_step == "awaiting_custom_amount":
        await handle_custom_amount_input(update, context, user_id, message_text)
        return
    
    # CRITICAL FIX: Handle deposit amount for users who started with /start
    if current_step == "deposit_amount":
        print(f"Processing deposit amount for user {user_id}")
        await process_deposit_amount_text(update, context, user_id, message_text)
        return
    
    # Handle account number processing
    if current_step == "account_number" or current_step == "service_selection":
        await process_account_number_text(update, context, user_id, message_text)
        return
    
    # Check if user is in auto_welcoming_users (for admin-forwarded users)
    auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
    if user_id in auto_welcoming_users:
        
        # STEP 1: DEPOSIT AMOUNT PROCESSING for auto-welcomed users
        if current_step == "deposit_amount":
            await process_deposit_amount_text(update, context, user_id, message_text)
            return
        
        # STEP 2: ACCOUNT NUMBER PROCESSING for auto-welcomed users
        elif current_step == "account_number" or current_step == "service_selection":
            await process_account_number_text(update, context, user_id, message_text)
            return
    
    # Handle users who are responding without a clear state
    # This could be users who started with /start but lost their state
    if message_text.isdigit():
        # If it's a number, try to determine context
        number = int(message_text)
        
        # Check if it looks like a deposit amount (100-100000)
        if 100 <= number <= 100000:
            print(f"Interpreting {number} as deposit amount for user {user_id}")
            # Set the state and process as deposit amount
            context.bot_data.setdefault("user_states", {})
            context.bot_data["user_states"][user_id] = "deposit_amount"
            await process_deposit_amount_text(update, context, user_id, message_text)
            return
        
        # Check if it looks like an account number (6 digits)
        elif len(message_text) == 6:
            print(f"Interpreting {message_text} as account number for user {user_id}")
            context.bot_data["user_states"][user_id] = "account_number"
            await process_account_number_text(update, context, user_id, message_text)
            return
    
    # DEFAULT RESPONSE - but make it more helpful
    print(f"No specific handler for user {user_id} in state {current_step}, providing guided setup")
    
    # Check if user has any progress in the database
    user_info = db.get_user(user_id)
    if user_info:
        risk_appetite = user_info.get("risk_appetite")
        deposit_amount = user_info.get("deposit_amount")
        
        if risk_appetite and not deposit_amount:
            # User has risk profile but no deposit amount
            await update.message.reply_text(
                f"<b>💰 Let's continue with your setup!</b>\n\n"
                f"You selected risk level {risk_appetite}/10. Great!\n\n"
                f"Now, how much capital are you planning to fund your account with?\n\n"
                f"<b>Example:</b> 5000",
                parse_mode='HTML'
            )
            context.bot_data.setdefault("user_states", {})
            context.bot_data["user_states"][user_id] = "deposit_amount"
            return
        
        elif risk_appetite and deposit_amount:
            # User has both, might need service selection
            await update.message.reply_text(
                f"<b>📢 Almost done!</b>\n\n"
                f"Which VFX service interests you most?",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔔 VFX Signals", callback_data="interest_signals"),
                        InlineKeyboardButton("🤖 Automated Strategy", callback_data="interest_strategy")
                    ],
                    [
                        InlineKeyboardButton("✨ Both Services", callback_data="interest_all"),
                        InlineKeyboardButton("🔄 Restart", callback_data="restart_process")
                    ]
                ])
            )
            context.bot_data["user_states"][user_id] = "service_selection"
            return
    
    # Truly default case - offer guided setup restart
    await update.message.reply_text(
        "<b>💬 I received your message!</b>\n\n"
        "It looks like we might have lost track of where you are in the setup process.\n\n"
        "<b>💡 Let's restart with our guided setup for the best experience! 🚀</b>",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🚀 Start Guided Setup", callback_data="risk_low"),
                InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")
            ],
            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
        ])
    )

async def handle_custom_amount_input(update, context, user_id, message_text):
    """Handle custom deposit amount input."""
    try:
        import re
        amount_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', message_text)
        if amount_match:
            amount_str = amount_match.group(1).replace(',', '')
            amount = float(amount_str)
            
            if 100 <= amount <= 100000:
                # Valid amount - show deposit instructions
                await update.message.reply_text(
                    f"<b>✅ Custom Amount Set: ${amount:,.0f}</b>\n\n"
                    f"Perfect! Here's how to deposit <b>${amount:,.0f}</b> to your account... 🚀",
                    parse_mode='HTML'
                )
                
                # Show VortexFX instructions
                user_info = db.get_user(user_id) or {}
                account_number = user_info.get("trading_account", "Unknown")
                account_name = user_info.get("account_owner", "Unknown")
                
                instructions_message = (
                    f"<b>💰 VortexFX Deposit Instructions</b>\n\n"
                    f"<b>📋 Amount:</b> ${amount:,.0f}\n"
                    f"<b>📊 Account:</b> {account_number}\n"
                    f"<b>👤 Holder:</b> {account_name}\n\n"
                    f"<b>🌐 Steps:</b>\n"
                    f"1. Visit: <a href='https://clients.vortexfx.com/en/dashboard'>VortexFX Client Portal</a> 🔗\n"
                    f"2. Login → <b>Funds</b> → <b>Deposit</b> 📥\n"
                    f"3. Select account → Currency → Amount: <b>${amount:,.0f}</b> 💰\n\n"
                    f"<b>⏰ Processing:</b> 5-30 minutes"
                )
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Check Balance", callback_data="check_balance_now")],
                    [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
                    [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    instructions_message, 
                    parse_mode='HTML', 
                    reply_markup=reply_markup
                )
                
                # Update database and schedule checks
                db.add_user({
                    "user_id": user_id,
                    "target_deposit_amount": amount,
                    "custom_amount_set": True,
                    "vortexfx_instructions_shown": True
                })
                
                context.bot_data["user_states"][user_id] = "deposit_instructions_shown"  
                
            else:
                await update.message.reply_text(
                    "<b>⚠️ Invalid Amount Range</b>\n\n"
                    "Please enter an amount between <b>$100</b> and <b>$100,000</b>.\n\n"
                    "<b>Example:</b> 1500 💰",
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
                    ])
                )
        else:
            await update.message.reply_text(
                "<b>⚠️ Invalid Format</b>\n\n"
                "Please enter a valid number.\n\n"
                "<b>Example:</b> 2500 💰",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
                ])
            )
    except ValueError:
        await update.message.reply_text(
            "<b>⚠️ Invalid Input</b>\n\n"
            "Please enter a valid amount.\n\n"
            "<b>Example:</b> 1000 💰",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
            ])
        )

async def process_deposit_amount_text(update, context, user_id, message_text):
    """Process deposit amount from text input with progress indicator."""
    import re
    amount_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', message_text)
    if amount_match:
        amount_str = amount_match.group(1).replace(',', '')
        try:
            amount = int(float(amount_str))
            
            # Store deposit amount
            db.add_user({
                "user_id": user_id,
                "deposit_amount": amount,
                "last_response": message_text,
                "last_response_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            # HTML styled service selection with progress
            keyboard = [
                [
                    InlineKeyboardButton("🔔 VFX Signals", callback_data="interest_signals"),
                    InlineKeyboardButton("🤖 Automated Strategy", callback_data="interest_strategy")
                ],
                [
                    InlineKeyboardButton("✨ Both Services", callback_data="interest_all"),
                    InlineKeyboardButton("🔄 Restart", callback_data="restart_process")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"<b>✅ Step 2 Completed: Funding Amount</b>\n\n"
                f"<b>Amount:</b> ${amount:,.0f} ✅\n\n"
                f"<b>Step 3 of 4: Service Selection</b>\n\n"
                f"<b>📢 Quick question!</b>\n\n"
                f"Which VFX service are you most interested in?\n\n"
                f"🔔 <b>VFX Signals:</b> Premium trading alerts\n"
                f"🤖 <b>Automated Strategy:</b> Hands-free trading\n"
                f"✨ <b>Both Services:</b> Complete trading solution",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
            # Update state
            context.bot_data.setdefault("user_states", {})
            context.bot_data["user_states"][user_id] = "service_selection"
            
            # Notify admin
            auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
            user_name = auto_welcoming_users.get(user_id, {}).get("name", "User")
            
            for admin_id in ADMIN_USER_ID:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"<b>💰 User Update</b>\n\n<b>{user_name}</b> (ID: {user_id}) indicated deposit amount: <b>${amount:,.0f}</b>",
                        parse_mode='HTML'
                    )
                except Exception as e:
                    print(f"Error notifying admin {admin_id}: {e}")
        except ValueError:
            await update.message.reply_text(
                "<b>⚠️ Invalid Amount</b>\n\n"
                "Sorry, I couldn't understand that amount. Please enter a numeric value.\n\n"
                "<b>Example:</b> 1000 💰",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
                ])
            )
    else:
        await update.message.reply_text(
            "<b>⚠️ Invalid Format</b>\n\n"
            "Please provide a valid deposit amount.\n\n"
            "<b>Example:</b> 1000 💰",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
            ])
        )

# async def process_account_number_text(update, context, user_id, message_text):
#     """Process MT5 account number from text input."""
#     print(f"Processing account number: {message_text}")
    
#     if message_text.isdigit() and len(message_text) == 6:
#         account_number = message_text
        
#         # Get user's stated deposit intention
#         user_info = db.get_user(user_id)
#         stated_amount = user_info.get("deposit_amount", 0) if user_info else 0
        
#         print(f"===== ACCOUNT VERIFICATION =====")
#         print(f"Account: {account_number}, User: {user_id}, Stated: ${stated_amount}")
        
#         await update.message.reply_text(
#             "<b>🔍 Verifying Account...</b>\n\n"
#             "Please wait while we verify your account and check balance... ⏳",
#             parse_mode='HTML'
#         )
        
#         # Validate and verify account
#         if not auth.validate_account_format(account_number):
#             await update.message.reply_text(
#                 "<b>❌ Invalid Account Format</b>\n\n"
#                 "Please enter a valid trading account number.\n\n"
#                 "<b>🔄 Try again or</b> <b>💬 speak to an advisor</b>",
#                 parse_mode='HTML',
#                 reply_markup=InlineKeyboardMarkup([
#                     [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                     [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
#                 ])
#             )
#             return
        
#         # Connect to MySQL and verify
#         mysql_db = get_mysql_connection()
#         if not mysql_db.is_connected():
#             await update.message.reply_text(
#                 "<b>⚠️ Connection Issue</b>\n\n"
#                 "Unable to verify account at the moment. Please try again later or speak to an advisor.",
#                 parse_mode='HTML',
#                 reply_markup=InlineKeyboardMarkup([
#                     [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                     [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
#                 ])
#             )
#             return
        
#         try:
#             account_info = mysql_db.verify_account_exists(account_number)

#             if not account_info['exists']:
#                 # Account not found message...
#                 return
#             elif not account_info.get('is_real_account', False):
#                 # NEW: Handle demo account
#                 await update.message.reply_text(
#                     f"<b>⚠️ Demo Account Detected</b>\n\n"
#                     f"<b>Account:</b> {account_number}\n"
#                     f"<b>Type:</b> {account_info.get('account_type', 'Demo')}\n"
#                     f"<b>Group:</b> {account_info.get('group', 'Unknown')}\n\n"
#                     f"<b>🚫 Demo accounts are not eligible for VIP services</b>\n\n"
#                     f"<b>💡 Please provide a real/live trading account number</b>\n",
#                     parse_mode='HTML',
#                     reply_markup=InlineKeyboardMarkup([
#                         [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                         [InlineKeyboardButton("🔄 Try Different Account", callback_data="restart_process")]
#                     ])
#                 )
#                 return
            
#             # Extract account details
#             real_balance = float(account_info.get('balance', 0))
#             account_name = account_info.get('name', 'Unknown')
#             account_status = account_info.get('status', 'Unknown')
            
#             print(f"Account found: {account_name}, Balance: ${real_balance}")
            
#             # Store account info
#             db.add_user({
#                 "user_id": user_id,
#                 "trading_account": account_number,
#                 "account_owner": account_name,
#                 "account_balance": real_balance,
#                 "account_status": account_status,
#                 "is_verified": True,
#                 "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#             })
            
#             # ENHANCED DECISION LOGIC - REQUEST ACCESS MODEL
#             if real_balance >= stated_amount and stated_amount > 0:
#                 # SUFFICIENT FUNDS - REQUEST ACCESS
#                 success_message = (
#                     f"<b>✅ Account Verified Successfully!</b>\n\n"
#                     f"<b>📋 Account:</b> {account_number}\n"
#                     f"<b>👤 Account Holder:</b> {account_name}\n"
#                     f"<b>💰 Current Balance:</b> ${real_balance:,.2f}\n"
#                     f"<b>🎯 Required:</b> ${stated_amount:,.2f}\n\n"
#                     f"<b>🎉 Excellent!</b> You have sufficient funds! 💎\n\n"
#                     f"<b>📋 What would you like to request access to?</b>"
#                 )
                
#                 # REQUEST ACCESS BUTTONS
#                 keyboard = [
#                     [
#                         InlineKeyboardButton("🔔 Request VIP Signals", callback_data="request_vip_signals"),
#                         InlineKeyboardButton("🤖 Request VIP Strategy", callback_data="request_vip_strategy")
#                     ],
#                     [
#                         InlineKeyboardButton("✨ Request Both Services", callback_data="request_vip_both_services"),
#                         InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")
#                     ],
#                     [
#                         InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")
#                     ]
#                 ]
#                 reply_markup = InlineKeyboardMarkup(keyboard)
                
#                 await update.message.reply_text(success_message, parse_mode='HTML', reply_markup=reply_markup)
                
#                 # Update status
#                 db.add_user({
#                     "user_id": user_id,
#                     "funding_status": "sufficient",
#                     "vip_eligible": True,
#                     "vip_access_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#                 })
                
#                 # Reset state
#                 context.bot_data["user_states"][user_id] = "requesting_access"
                
#                 # Notify admins
#                 await notify_admins_sufficient_funds(context, user_id, account_info, stated_amount, real_balance)
                
#             elif real_balance > 0 and stated_amount > 0:
#                 # PARTIAL FUNDS
#                 difference = stated_amount - real_balance
#                 percentage = (real_balance / stated_amount) * 100
                
#                 message = (
#                     f"<b>✅ Account Successfully Verified!</b>\n\n"
#                     f"<b>📋 Account:</b> {account_number}\n"
#                     f"<b>👤 Account Holder:</b> {account_name}\n"
#                     f"<b>💰 Current Balance:</b> ${real_balance:,.2f}\n"
#                     f"<b>🎯 Your Goal:</b> ${stated_amount:,.2f}\n"
#                     f"<b>📊 Remaining:</b> ${difference:,.2f}\n\n"
#                     f"<b>📈 You're {percentage:.1f}% there!</b> 🎯\n\n"
#                     f"<b>What would you like to do?</b>"
#                 )
                
#                 keyboard = [
#                     [InlineKeyboardButton(f"💳 Deposit ${difference:,.0f} Now", callback_data=f"deposit_exact_{difference}")],
#                     [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
#                     [InlineKeyboardButton("🚀 Start with Current Balance", callback_data="start_with_current")],
#                     [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                     [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
#                 ]
#                 reply_markup = InlineKeyboardMarkup(keyboard)
                
#                 await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
                
#                 # Update status
#                 db.add_user({
#                     "user_id": user_id,
#                     "funding_status": "partial",
#                     "funding_percentage": percentage,
#                     "remaining_amount": difference
#                 })
                
#                 context.bot_data["user_states"][user_id] = "partial_funding"
                
#             else:
#                 # NO FUNDS OR NO STATED AMOUNT
#                 target_amount = stated_amount if stated_amount > 0 else 1000
                
#                 message = (
#                     f"<b>✅ Account Successfully Verified!</b>\n\n"
#                     f"<b>📋 Account:</b> {account_number}\n"
#                     f"<b>👤 Account Holder:</b> {account_name}\n"
#                     f"<b>💰 Current Balance:</b> ${real_balance:,.2f}\n"
#                     f"<b>💡 Suggested Amount:</b> ${target_amount:,.2f}\n\n"
#                     f"<b>🚀 Ready to start your trading journey?</b>\n\n"
#                     f"<b>How would you like to proceed?</b>"
#                 )
                
#                 keyboard = [
#                     [InlineKeyboardButton(f"💳 Deposit ${target_amount:,.0f} Now", callback_data=f"deposit_exact_{target_amount}")],
#                     [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
#                     [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                     [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
#                 ]
#                 reply_markup = InlineKeyboardMarkup(keyboard)
                
#                 await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
                
#                 # Update status
#                 db.add_user({
#                     "user_id": user_id,
#                     "funding_status": "none",
#                     "target_amount": target_amount
#                 })
                
#                 context.bot_data["user_states"][user_id] = "needs_funding"
            
#         except Exception as e:
#             print(f"Error in verification: {e}")
#             await update.message.reply_text(
#                 f"<b>⚠️ Verification Error</b>\n\n"
#                 f"Error verifying account: {str(e)[:100]}\n\n"
#                 f"Please try again or contact support.",
#                 parse_mode='HTML',
#                 reply_markup=InlineKeyboardMarkup([
#                     [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")],
#                     [InlineKeyboardButton("🔄 Restart Process", callback_data="restart_process")]
#                 ])
#             )
#     else:
#         await update.message.reply_text(
#             "<b>⚠️ Invalid Account Format</b>\n\n"
#             "That doesn't look like a valid account number.\n\n"
#             "Please provide a <b>6-digit MT5 account number</b>. 📊",
#             parse_mode='HTML',
#             reply_markup=InlineKeyboardMarkup([
#                 [InlineKeyboardButton("💬 Need Help?", callback_data="speak_advisor")],
#                 [InlineKeyboardButton("🔄 Restart", callback_data="restart_process")]
#             ])
#         )

async def notify_admins_sufficient_funds(context, user_id, account_info, stated_amount, real_balance):
    """Notify admins when user has sufficient funds."""
    admin_message = (
        f"<b>💰 USER WITH SUFFICIENT FUNDS</b>\n\n"
        f"<b>👤 User ID:</b> {user_id}\n"
        f"<b>📊 Account:</b> {account_info['account_number']}\n"
        f"<b>🏷️ Account Holder:</b> {account_info['name']}\n"
        f"<b>💵 Current Balance:</b> ${real_balance:,.2f}\n"
        f"<b>🎯 Required Amount:</b> ${stated_amount:,.2f}\n"
        f"<b>✅ Status:</b> Sufficient funds verified\n\n"
        f"<b>📋 User will request specific VIP services</b>\n"
        f"<b>⏰ Expected request within next few minutes</b>"
    )
    
    keyboard = [
        [InlineKeyboardButton("👤 View User Profile", callback_data=f"view_profile_{user_id}")],
        [InlineKeyboardButton("💬 Contact User", callback_data=f"start_conv_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

