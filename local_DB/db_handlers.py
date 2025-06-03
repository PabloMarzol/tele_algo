from imports import *


# =========================================================================== #
# ======================= Local DB Functions
# =========================================================================== #
async def check_existing_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """
    Check if user has already completed registration successfully.
    Returns True if user should be blocked from re-registering.
    """
    try:
        # Check local database first
        if db.is_user_already_registered(user_id):
            registration_summary = db.get_user_registration_summary(user_id)
            
            # Send user their existing registration status
            existing_account = registration_summary.get("trading_account", "Unknown")
            join_date = registration_summary.get("join_date", "Unknown")
            
            await update.message.reply_text(
                f"<b>⚠️ Registration Already Completed</b>\n\n"
                f"<b>👤 Name:</b> {registration_summary.get('first_name', 'Unknown')}\n"
                f"<b>📊 Trading Account:</b> {existing_account}\n"
                f"<b>📅 Registered:</b> {join_date}\n"
                f"<b>✅ Status:</b> Account verified and active\n\n"
                f"<b>🎯 You already have access to our services!</b>\n\n"
                f"If you need assistance, please contact our support team.",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
                    [InlineKeyboardButton("📋 Check My Status", callback_data="check_my_status")]
                ])
            )
            
            # Notify admins of duplicate registration attempt
            await notify_admins_duplicate_attempt(context, user_id, registration_summary)
            
            return True  # Block re-registration
    
    except Exception as e:
        print(f"Error in check_existing_registration: {e}")
        # On error, allow registration to proceed (fail-open approach)
        return False
    
    return False

async def check_my_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle check my status button."""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    registration_summary = db.get_user_registration_summary(user_id)
    
    if not registration_summary:
        await query.edit_message_text(
            "<b>⚠️ No Registration Found</b>\n\n"
            "No registration information found in our system.",
            parse_mode='HTML'
        )
        return
    
    # Format detailed status
    status_message = (
        f"<b>📋 Your Registration Status</b>\n\n"
        f"<b>👤 Name:</b> {registration_summary.get('first_name', 'Unknown')}\n"
        f"<b>🆔 User ID:</b> {user_id}\n"
        f"<b>📊 Trading Account:</b> {registration_summary.get('trading_account', 'Not provided')}\n"
        f"<b>✅ Account Verified:</b> {'Yes' if registration_summary.get('is_verified') else 'No'}\n"
        f"<b>🎯 VIP Access:</b> {'Granted' if registration_summary.get('vip_access_granted') else 'Pending'}\n"
        f"<b>📅 Member Since:</b> {registration_summary.get('join_date', 'Unknown')}\n"
        f"<b>🕒 Last Active:</b> {registration_summary.get('last_active', 'Unknown')}\n\n"
        f"<b>Overall Status:</b> {registration_summary.get('registration_status', 'Unknown').upper()}\n\n"
        f"<b>🏠 Your Control Center:</b>\n"
        f"<b>/myaccount</b> - Your personal dashboard 📊\n"
        f"• View your complete profile\n"
        f"• Edit your settings anytime\n"
        f"• Check account status\n"
        f"• Track VIP services\n"
        f"• Contact support directly\n\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("💬 Contact Support", callback_data="speak_advisor")],
        [InlineKeyboardButton("🔄 Refresh Status", callback_data="check_my_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        status_message,
        parse_mode='HTML',
        reply_markup=reply_markup
    )

async def notify_admins_duplicate_attempt(context, user_id, registration_summary):
    """Notify admins when user attempts duplicate registration."""
    admin_message = (
        f"<b>🔒 DUPLICATE REGISTRATION ATTEMPT</b>\n\n"
        f"<b>👤 User:</b> {registration_summary.get('first_name', 'Unknown')} (ID: {user_id})\n"
        f"<b>📊 Existing Account:</b> {registration_summary.get('trading_account', 'Unknown')}\n"
        f"<b>📅 Original Registration:</b> {registration_summary.get('join_date', 'Unknown')}\n"
        f"<b>🕒 Attempt Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"<b>🚫 Registration blocked - user already verified</b>"
    )
    
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def view_profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'View User Profile' button callback."""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    if callback_data.startswith("view_profile_"):
        try:
            user_id = int(callback_data.split("_")[2])
            print(f"Viewing profile for user ID: {user_id}")
            
            # Get user info from database with error handling
            try:
                user_info = db.get_user(user_id)
                print(f"Retrieved user info: {user_info}")
            except Exception as e:
                print(f"Error getting user from database: {e}")
                user_info = None
                
            # If user not found in our db, check if they're in auto_welcoming_users
            if not user_info:
                print(f"User {user_id} not found in database, checking auto_welcoming_users")
                auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
                
                if user_id in auto_welcoming_users:
                    user_name = auto_welcoming_users[user_id].get("name", "Unknown User")
                    
                    # Create a basic profile with the info we have
                    profile = f"👤 USER PROFILE (Partial Info): {user_name}\n\n"
                    profile += f"User ID: {user_id}\n"
                    profile += f"Source: {auto_welcoming_users[user_id].get('source_channel', 'Unknown')}\n"
                    profile += f"WARNING: Complete profile not found in database\n\n"
                    
                    # Add action buttons
                    keyboard = [
                        [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")],
                        [InlineKeyboardButton("View Auto Welcoming Info", callback_data=f"view_welcoming_{user_id}")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await query.edit_message_text(
                        text=profile,
                        reply_markup=reply_markup
                    )
                    return
                else:
                    await query.edit_message_text(
                        text=f"⚠️ User {user_id} not found in database or auto-welcoming lists"
                    )
                    return
            
            # Now format user profile with available info
            profile = f"👤 USER PROFILE: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n\n"
            profile += f"User ID: {user_id}\n"
            profile += f"Username: @{user_info.get('username', 'None')}\n"
            profile += f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            profile += f"Risk Profile: {user_info.get('risk_profile_text', 'Not specified')}\n"
            profile += f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            profile += f"Trading Account: {user_info.get('trading_account', 'Not provided')}\n"
            profile += f"Account Verified: {'✅ Yes' if user_info.get('is_verified') else '❌ No'}\n"
            profile += f"Join Date: {user_info.get('join_date', 'Unknown')}\n"
            profile += f"Last Active: {user_info.get('last_active', 'Unknown')}\n"
            profile += f"Last Response: {user_info.get('last_response', 'None')}\n\n"
            
            # Add action buttons
            keyboard = [
                [InlineKeyboardButton("Start Conversation", callback_data=f"start_conv_{user_id}")],
                [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
                [InlineKeyboardButton("Add to VIP Strategy", callback_data=f"add_vip_strategy_{user_id}")],
                [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text=profile,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            print(f"Error viewing user profile: {e}")
            await query.edit_message_text(
                text=f"⚠️ Error viewing user profile: {e}"
            )

async def confirm_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation of registration."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Mark registration as confirmed in database
    db.add_user({
        "user_id": user_id,
        "registration_confirmed": True,
        "registration_confirmed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    await query.edit_message_text(
        "✅ <b>Registration Confirmed!</b>\n\n"
        "Thank you for confirming your information. Our team will be in touch soon to complete your setup.\n\n"
        "If you have any questions in the meantime, feel free to ask!",
        parse_mode='HTML'
    )
    
    # Send profile summary to admins
    await send_profile_summary_to_admins(context, user_id)
    
    # Notify admin of confirmation
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"✅ User {user_id} has confirmed their registration"
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def edit_registration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle edit registration button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Provide options for what to edit
    keyboard = [
        [InlineKeyboardButton("Risk Profile", callback_data="edit_risk")],
        [InlineKeyboardButton("Deposit Amount", callback_data="edit_deposit")],
        [InlineKeyboardButton("MT5 Account", callback_data="edit_account")],
        [InlineKeyboardButton("↩️ Back to Summary", callback_data="view_summary")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "<b>Edit Registration</b>\n\nWhat information would you like to update?",
        parse_mode='HTML',
        reply_markup=reply_markup
    )


# =========================================================================== #
# ======================= Analytics & Reporting Functions 
# =========================================================================== #
async def send_daily_signup_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a daily report of new sign-ups to the admin team."""
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get users who joined today
        # This assumes the join_date column is in the format "YYYY-MM-DD HH:MM:SS"
        today_users = db.users_df.filter(pl.col("join_date").str.contains(today))
        
        if today_users.height == 0:
            # No new users today
            report = f"📊 DAILY SIGNUP REPORT - {today} 📊\n\nNo new users registered today."
        else:
            # Format report
            report = f"📊 DAILY SIGNUP REPORT - {today} 📊\n\n"
            report += f"Total New Users: {today_users.height}\n\n"
            
            # Add details for each user
            report += "NEW USER DETAILS:\n\n"
            
            for i in range(min(today_users.height, 10)):  # Limit to 10 users to avoid message length issues
                user_id = today_users["user_id"][i]
                first_name = today_users["first_name"][i] if today_users["first_name"][i] else "Unknown"
                last_name = today_users["last_name"][i] if today_users["last_name"][i] else ""
                risk = today_users["risk_appetite"][i]
                deposit = today_users["deposit_amount"][i]
                account = today_users["trading_account"][i] if today_users["trading_account"][i] else "Not provided"
                verified = "✅" if today_users["is_verified"][i] else "❌"
                
                report += (
                    f"{i+1}. {first_name} {last_name} (ID: {user_id})\n"
                    f"   Risk: {risk}/10 | Deposit: ${deposit}\n"
                    f"   Account: {account} | Verified: {verified}\n\n"
                )
            
            if today_users.height > 10:
                report += f"... and {today_users.height - 10} more users"
        
        # Send report to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report
                )
                print(f"Successfully sent daily signup report to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send report to admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error generating daily signup report: {e}")

async def send_daily_response_report(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a daily report of user responses to the admin team."""
    try:
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Get users who responded today (based on last_response_time)
        today_responders = db.users_df.filter(pl.col("last_response_time").str.contains(today))
        
        if today_responders.height == 0:
            # No responses today
            report = f"📊 DAILY USER RESPONSE REPORT - {today} 📊\n\nNo user responses recorded today."
        else:
            # Format report
            report = f"📊 DAILY USER RESPONSE REPORT - {today} 📊\n\n"
            report += f"Total User Responses: {today_responders.height}\n\n"
            
            # Add details for each user
            report += "USER RESPONSE DETAILS:\n\n"
            
            for i in range(min(today_responders.height, 10)):  # Limit to 10 users
                user_id = today_responders["user_id"][i]
                first_name = today_responders["first_name"][i] if today_responders["first_name"][i] else "Unknown"
                last_name = today_responders["last_name"][i] if today_responders["last_name"][i] else ""
                risk = today_responders["risk_appetite"][i]
                risk_text = today_responders["risk_profile_text"][i] if "risk_profile_text" in today_responders.columns and today_responders["risk_profile_text"][i] else "Not specified"
                deposit = today_responders["deposit_amount"][i]
                account = today_responders["trading_account"][i] if today_responders["trading_account"][i] else "Not provided"
                verified = "✅" if today_responders["is_verified"][i] else "❌"
                last_response = today_responders["last_response"][i] if "last_response" in today_responders.columns and today_responders["last_response"][i] else "No response"
                source_channel = today_responders["source_channel"][i] if "source_channel" in today_responders.columns and today_responders["source_channel"][i] else "Unknown"
                source_emoji = "📊" if source_channel == "signals_channel" else "📢" if source_channel == "main_channel" else "❓"
                
                report += (
                    f"{i+1}. {first_name} {last_name} (ID: {user_id}) {source_emoji}\n"
                    f"   Source: {source_channel}\n"
                    f"   Risk: {risk}/10 ({risk_text}) | Deposit: ${deposit}\n"
                    f"   Account: {account} | Verified: {verified}\n"
                    f"   Last Response: \"{last_response[:50]}...\"\n\n"
                )
            
            if today_responders.height > 10:
                report += f"... and {today_responders.height - 10} more users"
        
        # Send report to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=report
                )
                print(f"Successfully sent daily response report to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send report to admin {admin_id}: {e}")
                
    except Exception as e:
        print(f"Error generating daily response report: {e}")

async def show_summary(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    """Show summary of collected information and completion options."""
    # Get user data from database
    user_info = db.get_user(user_id)
    
    if not user_info:
        await context.bot.send_message(
            chat_id=user_id,
            text="⚠️ Error retrieving your information. Please use <b>/myaccount</b> to check your status.",
            parse_mode='HTML'
        )
        return
    
    # Format enhanced summary
    summary = f"""<b>📋 Your Registration Summary</b>

Thank you for providing your information! Here's what we've got:

<b>✅ Profile Complete:</b>
<b>Risk Profile:</b> {user_info.get('risk_profile_text', 'Not specified').capitalize()}
<b>Deposit Amount:</b> ${user_info.get('deposit_amount', 'Not specified')}
<b>Trading Interest:</b> {user_info.get('trading_interest', 'Not specified')}
<b>MT5 Account:</b> {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

<b>🎯 What's Next?</b>
Our team will review your information and set up your account for our premium services. You should receive confirmation within the next 24 hours.

<b>💡 Your Personal Dashboard:</b>
Use <b>/myaccount</b> anytime to:
• Check your account status 📊
• Edit your profile settings ✏️
• View verification progress 🔍
• Contact our support team 💬
• Track your VIP access 🌟

<b>📱 Bookmark this command for quick access!</b>

If you need to make any changes or have questions, just use your dashboard or contact us below! 👇"""

    # Enhanced buttons with dashboard access
    keyboard = [
        [InlineKeyboardButton("📊 Open My Dashboard", callback_data="back_to_dashboard")],
        [InlineKeyboardButton("✅ Confirm Information", callback_data="confirm_registration")],
        [InlineKeyboardButton("✏️ Edit Information", callback_data="edit_registration")],
        [InlineKeyboardButton("👨‍💼 Speak to an Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=summary,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Update conversation state
    context.user_data["response_step"] = "summary_shown"
    
    # Notify admin of completion
    for admin_id in ADMIN_USER_ID:
        try:
            admin_summary = f"""📋 <b>USER REGISTRATION COMPLETED</b>

User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}
ID: {user_id}
Source: {user_info.get('source_channel', 'Unknown')}

<b>Collected Information:</b>
- Risk Profile: {user_info.get('risk_profile_text', 'Not specified').capitalize()}
- Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}
- Previous Experience: {user_info.get('previous_experience', 'Not specified')}
- MT5 Account: {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

Registration completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""

            # Add action buttons for admin
            admin_keyboard = [
                [InlineKeyboardButton("View Full Profile", callback_data=f"view_profile_{user_id}")],
                [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
                [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
            ]
            admin_reply_markup = InlineKeyboardMarkup(admin_keyboard)
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_summary,
                parse_mode='HTML',
                reply_markup=admin_reply_markup
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

async def send_profile_summary_to_admins(context, user_id):
    """Send a summary of the user's profile to all admins."""
    print(f"Attempting to send profile summary for user {user_id} to admins")
    
    # Try multiple methods to get user info
    user_info = None
    error_messages = []
    
    # Method 1: Try db.get_user
    try:
        print("Attempting to retrieve user via db.get_user")
        user_info = db.get_user(user_id)
        if user_info:
            print(f"Successfully retrieved user via db.get_user: {user_info}")
    except Exception as e:
        error_msg = f"db.get_user error: {e}"
        print(error_msg)
        error_messages.append(error_msg)
    
    # Method 2: Try direct dataframe access if db.get_user failed
    if not user_info:
        try:
            print("Attempting to retrieve user via direct dataframe access")
            user_df = db.users_df.filter(pl.col("user_id") == user_id)
            if user_df.height > 0:
                print(f"Found user in dataframe, creating dict")
                user_info = {}
                for col in user_df.columns:
                    user_info[col] = user_df[col][0]
                print(f"Created user_info dict: {user_info}")
        except Exception as e:
            error_msg = f"Dataframe access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    # Method 3: Try to use auto_welcoming_users dict if available
    if not user_info:
        try:
            print("Attempting to retrieve from auto_welcoming_users")
            auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
            if user_id in auto_welcoming_users:
                print(f"User found in auto_welcoming_users")
                # Create a basic info dict
                user_info = {
                    "user_id": user_id,
                    "first_name": auto_welcoming_users[user_id].get("name", "Unknown"),
                    "source_channel": auto_welcoming_users[user_id].get("source_channel", "Unknown")
                }
                # Add any conversation state info
                user_states = context.bot_data.get("user_states", {})
                if user_id in user_states:
                    user_info["current_state"] = user_states[user_id]
        except Exception as e:
            error_msg = f"Auto_welcoming access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    if not user_info:
        # User could not be found - notify admins of the issue
        error_details = "\n".join(error_messages) if error_messages else "No detailed error information"
        
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"⚠️ Could not generate summary for user {user_id}:\n\n{error_details}\n\n"
                         f"The user may need to be manually processed."
                )
                print(f"Sent error report to admin {admin_id}")
            except Exception as e:
                print(f"Error sending error report to admin {admin_id}: {e}")
        return
    
    # We have some user info - generate summary
    summary = f"""📋 <b>USER REGISTRATION COMPLETED</b>

User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}
ID: {user_id}
Source: {user_info.get('source_channel', 'Unknown')}

<b>Collected Information:</b>
- Risk Profile: {user_info.get('risk_profile_text', 'Not specified').capitalize() if user_info.get('risk_profile_text') else f"{user_info.get('risk_appetite', 0)}/10"}
- Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}
- Previous Experience: {user_info.get('previous_experience', 'Not specified').capitalize() if user_info.get('previous_experience') else 'Not specified'}
- MT5 Account: {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}

Registration completed at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
    
    # Add action buttons for admin
    keyboard = [
        [InlineKeyboardButton("View Full Profile", callback_data=f"view_profile_{user_id}")],
        [InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")],
        [InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=summary,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            print(f"Sent profile summary to admin {admin_id}")
        except Exception as e:
            print(f"Error sending profile summary to admin {admin_id}: {e}")

async def view_summary_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle view profile summary button."""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    print(f"View summary requested by user ID: {user_id}")
    
    # Try multiple methods to get user info
    user_info = None
    error_messages = []
    
    # Method 1: Try db.get_user
    try:
        print("Attempting to retrieve user via db.get_user")
        user_info = db.get_user(user_id)
        if user_info:
            print(f"Successfully retrieved user via db.get_user: {user_info}")
    except Exception as e:
        error_msg = f"db.get_user error: {e}"
        print(error_msg)
        error_messages.append(error_msg)
    
    # Method 2: Try auto_welcoming_users dict
    if not user_info:
        try:
            print("Attempting to retrieve from auto_welcoming_users")
            auto_welcoming_users = context.bot_data.get("auto_welcoming_users", {})
            if user_id in auto_welcoming_users:
                print(f"User found in auto_welcoming_users")
                # Create a basic info dict
                user_info = {
                    "user_id": user_id,
                    "first_name": auto_welcoming_users[user_id].get("name", "Unknown"),
                    "source_channel": auto_welcoming_users[user_id].get("source_channel", "Unknown")
                }
                
                # Check if we have risk profile and deposit amount in our state tracking
                user_states = context.bot_data.get("user_states", {})
                if user_id in user_states:
                    user_info["current_state"] = user_states[user_id]
                
                # Add trading account info if we have it
                if hasattr(auth, 'verified_users') and user_id in auth.verified_users:
                    print(f"Found user in auth.verified_users")
                    user_info["trading_account"] = auth.verified_users[user_id].get("account_number", "")
                    user_info["is_verified"] = True
                    user_info["account_owner"] = auth.verified_users[user_id].get("account_owner", "")
        except Exception as e:
            error_msg = f"Auto_welcoming access error: {e}"
            print(error_msg)
            error_messages.append(error_msg)
    
    # Collect profile information from multiple sources if needed
    if user_info:
        # Try to get risk profile from context if not in user_info
        if ("risk_appetite" not in user_info or not user_info["risk_appetite"]) and "risk_profile" in context.user_data:
            user_info["risk_profile_text"] = context.user_data["risk_profile"]
            
        # Try to get trading account from auth system if not in user_info
        if "trading_account" not in user_info and hasattr(auth, 'verified_users'):
            if user_id in auth.verified_users:
                user_info["trading_account"] = auth.verified_users[user_id].get("account_number", "")
                user_info["is_verified"] = True
    
    if not user_info:
        # If we still don't have user_info, create a minimal one
        user_info = {
            "user_id": user_id,
            "retrieval_errors": error_messages
        }
    
    # Format summary with whatever info we have
    summary = f"""<b>📋 Your Registration Summary</b>

Thank you for providing your information! Here's what we've got:

<b>Risk Profile:</b> {user_info.get('risk_profile_text', 'Not specified').capitalize() if user_info.get('risk_profile_text') else f"{user_info.get('risk_appetite', 0)}/10"}
<b>Deposit Amount:</b> ${user_info.get('deposit_amount', 'Not specified')}
<b>Previous Experience:</b> {user_info.get('previous_experience', 'Not specified').capitalize() if user_info.get('previous_experience') else 'Not specified'}
<b>MT5 Account:</b> {user_info.get('trading_account', 'Not specified')} {' ✅' if user_info.get('is_verified') else ''}
"""

    # Additional profile info if verified
    if user_info.get('is_verified') and user_info.get('account_owner'):
        summary += f"<b>Account Owner:</b> {user_info.get('account_owner')}\n"
    
    summary += """
<b>What's Next?</b>
Our team will review your information and set up your account for our signals service. You should receive confirmation within the next 24 hours.

If you need to make any changes or have questions, please let us know!"""

    # Add buttons for edit or confirm
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Information", callback_data="confirm_registration")],
        [InlineKeyboardButton("✏️ Edit Information", callback_data="edit_registration")],
        [InlineKeyboardButton("👨‍💼 Speak to an Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        summary,
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    
    # Force send a summary to admin
    try:
        asyncio.create_task(send_profile_summary_to_admins(context, user_id))
    except Exception as e:
        print(f"Error sending profile summary to admins: {e}")




# =============================================================================
# =============  NOTIFICATION FUNCTIONS
# =============================================================================
async def send_registration_notification(context, user_id, account_number, account_verified):
    """Send detailed notification about new registration to admin team."""
    try:
        # Get user info from database
        user_info = db.get_user(user_id)
        print(f"Retrieved user info from DB for notification: {user_info}")
        
        if not user_info:
            print(f"WARNING: User {user_id} not found in database for notification")
            return
        
        # Get user's selected interests
        trading_interest = user_info.get('trading_interest', 'Not specified')
        
        # Format interest for display
        if trading_interest == 'all':
            interest_display = "All VIP Services (Signals, Strategy, Prop Capital)"
        elif trading_interest:
            interest_display = f"VIP {trading_interest.capitalize()}"
        else:
            interest_display = "Not specified"
        
        # Set verification status emoji
        verify_status = "✅ Verified" if account_verified else "⚠️ Not Verified"
        
        # Build detailed report
        report = (
            f"🔔 NEW USER REGISTRATION 🔔\n\n"
            f"User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"Username: @{user_info.get('username', 'None')}\n"
            f"User ID: {user_id}\n\n"
            f"📊 PROFILE DETAILS 📊\n"
            f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            f"Trading Interest: {interest_display}\n"
            f"Trading Account: {account_number}\n"
            f"Account Status: {verify_status}\n\n"
            f"Registered: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )
        
        # Add action buttons for admin
        keyboard = []
        
        # Add VIP channel buttons based on interest
        if trading_interest == 'signals' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Signals", callback_data=f"add_vip_signals_{user_id}")])
        
        if trading_interest == 'strategy' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Strategy", callback_data=f"add_vip_strategy_{user_id}")])
        
        if trading_interest == 'propcapital' or trading_interest == 'all':
            keyboard.append([InlineKeyboardButton("Add to VIP Prop Capital", callback_data=f"add_vip_propcapital_{user_id}")])
        
        # Add button for forwarding to copier team
        keyboard.append([InlineKeyboardButton("Forward to Copier Team", callback_data=f"forward_copier_{user_id}")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Send to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(
                    chat_id=admin_id, 
                    text=report,
                    reply_markup=reply_markup
                )
                print(f"Successfully sent registration notification to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {e}")
    except Exception as e:
        print(f"Error in send_registration_notification: {e}")

async def send_account_notification(context, user_id, account_number):
    """Send notification about new account separately to avoid blocking the main flow."""
    try:
        # Get user info from database instead of context
        user_info = db.get_user(user_id)
        print(f"Retrieved user info from DB: {user_info}")
        
        if not user_info:
            print(f"WARNING: User {user_id} not found in database")
            return
        
        # Build minimal report
        report = (
            f"📊 New User Profile 📊\n"
            f"User: {user_info.get('first_name', 'Unknown')} {user_info.get('last_name', '')}\n"
            f"Risk Appetite: {user_info.get('risk_appetite', 'Not specified')}/10\n"
            f"Deposit Amount: ${user_info.get('deposit_amount', 'Not specified')}\n"
            f"Trading Account: {account_number}\n"
            f"User ID: {user_id}\n\n"
            f"This user needs to be added to VIP channels based on their interests."
        )
        
        # Send to all admins
        for admin_id in ADMIN_USER_ID:
            try:
                await context.bot.send_message(chat_id=admin_id, text=report)
                print(f"Successfully sent notification to admin {admin_id}")
            except Exception as e:
                print(f"Failed to send notification to admin {admin_id}: {e}")
    except Exception as e:
        print(f"Error in send_account_notification: {e}")

async def notify_admins_success(context, user_id, account_info, stated_amount, real_balance):
    """Notify admins of successful verification with sufficient funds."""
    
    admin_message = (
        f"<b>🎉 USER VERIFIED WITH SUFFICIENT FUNDS 🎉</b>\n\n"
        f"<b>User ID:</b> {user_id}\n"
        f"<b>Account:</b> {account_info['account_number']}\n"
        f"<b>Account Holder:</b> {account_info['name']}\n"
        f"<b>Stated Amount:</b> ${stated_amount:,.2f}\n"
        f"<b>Actual Balance:</b> ${real_balance:,.2f}\n"
        f"<b>Status:</b> ✅ VIP Access Granted\n\n"
        f"User has been automatically granted VIP access to all services."
    )
    
    # Send to all admins
    for admin_id in ADMIN_USER_ID:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=admin_message,
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Error notifying admin {admin_id}: {e}")

def schedule_followup_messages(context, user_id):
    """Schedule follow-up messages for users who defer deposits."""
    
    # Schedule follow-up messages at different intervals
    followup_times = [
        (24, "Thanks for verifying your account! Ready to start trading with us?"),
        (72, "Don't miss out on today's trading opportunities! Your account is ready for funding."),
        (168, "Weekly market wrap-up! See what profits our VIP members made this week."),
    ]
    
    for hours, message in followup_times:
        context.job_queue.run_once(
            lambda context, msg=message: send_followup_message(context, user_id, msg),
            when=hours * 3600,  # Convert hours to seconds
            name=f"followup_{user_id}_{hours}h"
        )

async def send_followup_message(context, user_id, message):
    """Send a follow-up message to user."""
    try:
        keyboard = [
            [InlineKeyboardButton("💳 Ready to Deposit", callback_data="ready_to_deposit")],
            [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await context.bot.send_message(
            chat_id=user_id,
            text=message,
            reply_markup=reply_markup
        )
    except Exception as e:
        print(f"Error sending follow-up message to user {user_id}: {e}")

async def handle_sufficient_funds(update, context, account_info, stated_amount, real_balance):
    """Handle users who already have sufficient balance."""
    print(f"User has sufficient funds: ${real_balance} >= ${stated_amount}")
    
    success_message = (
        f"<b>✅ Account Verified Successfully! ✅</b>\n\n"
        f"<b>Account:</b> {account_info['account_number']}\n"
        f"<b>Account Holder:</b> {account_info['name']}\n"
        f"<b>Current Balance:</b> ${real_balance:,.2f} 💰\n"
        f"<b>Required:</b> ${stated_amount:,.2f}\n\n"
        f"<b>🎉 Excellent!</b> You have sufficient funds to access all our VIP services!\n\n"
        f"<b>You now have access to:</b>\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 📈 Advanced Trading Strategies\n"
        f"• 💰 Prop Capital Opportunities\n"
        f"• 👨‍💼 Personal Trading Support\n"
        f"• 📞 Priority Customer Service\n\n"
        f"Our team will set up your VIP access within the next few minutes!"
    )
    
    # Create VIP access buttons
    keyboard = [
        [
            InlineKeyboardButton("🔔 Access VIP Signals", callback_data="access_vip_signals"),
            InlineKeyboardButton("📈 Access VIP Strategy", callback_data="access_vip_strategy")
        ],
        [
            InlineKeyboardButton("💰 Access Prop Capital", callback_data="access_vip_propcapital"),
            InlineKeyboardButton("👨‍💼 Speak to Advisor", callback_data="speak_advisor")
        ],
        [InlineKeyboardButton("📋 View My Profile", callback_data="view_summary")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(success_message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Mark user as fully verified and funded
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "sufficient",
        "vip_eligible": True,
        "vip_access_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    
    # Notify admins of successful verification
    await notify_admins_success(context, update.effective_user.id, account_info, stated_amount, real_balance)
    
    return ConversationHandler.END

async def handle_partial_funds(update, context, account_info, stated_amount, real_balance):
    """Handle users with some funds but less than stated amount."""
    difference = stated_amount - real_balance
    percentage = (real_balance / stated_amount) * 100
    
    print(f"User has partial funds: ${real_balance} of ${stated_amount} ({percentage:.1f}%)")
    
    message = (
        f"<b>✅ Account Successfully Verified!</b>\n\n"
        f"<b>Account:</b> {account_info['account_number']}\n"
        f"<b>Account Holder:</b> {account_info['name']}\n"
        f"<b>Current Balance:</b> ${real_balance:,.2f}\n"
        f"<b>Your Goal:</b> ${stated_amount:,.2f}\n"
        f"<b>Remaining:</b> ${difference:,.2f}\n\n"
        f"<b>📊 You're {percentage:.1f}% of the way there!</b> 🎯\n\n"
        f"<b>What would you like to do?</b>"
    )
    
    # Create action buttons
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit ${difference:,.0f} Now", callback_data=f"deposit_exact_{difference}")],
        [InlineKeyboardButton(f"💰 Choose Deposit Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("🚀 Start with Current Balance", callback_data="start_with_current")],
        [InlineKeyboardButton("⏰ I'll Deposit Later", callback_data="deposit_later")],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Store partial funding status
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "partial",
        "funding_percentage": percentage,
        "remaining_amount": difference
    })
    
    return AWAITING_DEPOSIT_DECISION

async def handle_no_funds(update, context, account_info, stated_amount):
    """Handle users with empty accounts."""
    print(f"User has no funds, needs ${stated_amount}")
    
    message = (
        f"<b>✅ Account Successfully Verified!</b>\n\n"
        f"<b>Account:</b> {account_info['account_number']}\n"
        f"<b>Account Holder:</b> {account_info['name']}\n"
        f"<b>Current Balance:</b> $0.00\n"
        f"<b>Target Amount:</b> ${stated_amount:,.2f}\n\n"
        f"<b>🚀 Ready to start your trading journey?</b>\n\n"
        f"To access our VIP services, you'll need to fund your account with ${stated_amount:,.2f}.\n\n"
        f"<b>Once funded, you'll get:</b>\n"
        f"• 🔔 Premium Trading Signals\n"
        f"• 📈 Advanced Strategies\n"
        f"• 💰 Prop Capital Access\n"
        f"• 👨‍💼 Personal Support\n\n"
        f"<b>How would you like to proceed?</b>"
    )
    
    # Create funding options
    keyboard = [
        [InlineKeyboardButton(f"💳 Deposit ${stated_amount:,.0f} Now", callback_data=f"deposit_exact_{stated_amount}")],
        [InlineKeyboardButton("💰 Choose Different Amount", callback_data="choose_deposit_amount")],
        [InlineKeyboardButton("💬 Speak to Advisor", callback_data="speak_advisor")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, parse_mode='HTML', reply_markup=reply_markup)
    
    # Store no funding status
    db.add_user({
        "user_id": update.effective_user.id,
        "funding_status": "none",
        "target_amount": stated_amount
    })
    
    return AWAITING_DEPOSIT_DECISION
