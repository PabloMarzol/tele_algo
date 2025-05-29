from imports import *


# ============================ MySQL Functions ============================================== #
# ================================================================================================= #

async def test_mysql_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test MySQL database connection and functionality."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    # Test connection
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database connection failed")
        return
    
    # Test getting stats
    try:
        stats = mysql_db.get_account_stats()
        if stats:
            await update.message.reply_text(
                f"✅ <b>MySQL Connection Active</b>\n\n"
                f"📊 <b>Database Statistics:</b>\n"
                f"Total Accounts: {stats['total_accounts']:,}\n"
                f"Funded Accounts: {stats['funded_accounts']:,}\n"
                f"Active Accounts: {stats['active_accounts']:,}\n"
                f"Average Balance: ${stats['avg_balance']:,.2f}\n"
                f"Maximum Balance: ${stats['max_balance']:,.2f}\n"
                f"Total Balance: ${stats['total_balance']:,.2f}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("✅ Connected but couldn't retrieve stats")
    except Exception as e:
        await update.message.reply_text(f"❌ Error testing MySQL: {e}")

async def search_account_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for accounts in the MySQL database."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /searchaccount <account_number_or_name>")
        return
    
    search_term = " ".join(context.args)
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        results = mysql_db.search_accounts(search_term, limit=10)
        
        if results:
            message = f"🔍 Search Results for '{search_term}':\n\n"
            for account in results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account['email']}\n"
                message += f"<b>Balance:</b> ${account['balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Company:</b> {account['Company']}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts found for '{search_term}'")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error searching accounts: {e}")

async def recent_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recently registered accounts."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get accounts from last X days
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Try the original method first
        try:
            results = mysql_db.get_recent_registrations(days=days, limit=15)
        except Exception as e:
            print(f"Original method failed: {e}")
            # Fall back to the safer method
            results = mysql_db.get_recent_accounts(days=days, limit=15)
        
        if results:
            message = f"📅 <b>Accounts Registered in Last {days} Days:</b>\n\n"
            for account in results:
                reg_date = account.get('registration_date')
                if isinstance(reg_date, str):
                    # Parse string date
                    try:
                        from datetime import datetime
                        reg_dt = datetime.strptime(reg_date, '%Y-%m-%d %H:%M:%S')
                        formatted_date = reg_dt.strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_date = str(reg_date)
                elif reg_date:
                    # It's already a datetime object
                    formatted_date = reg_date.strftime('%Y-%m-%d %H:%M')
                else:
                    formatted_date = 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', account.get('email', 'N/A'))}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account.get('Status', 'Unknown')}\n"
                message += f"<b>Country:</b> {account.get('Country', 'Unknown')}\n"
                message += f"<b>Registered:</b> {formatted_date}\n"
                if 'days_ago' in account and account['days_ago'] is not None:
                    message += f"<b>Days Ago:</b> {account['days_ago']}\n"
                message += "\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts registered in the last {days} days")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def check_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the structure of the mt5_users table."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        structure = mysql_db.get_table_structure()
        
        if structure:
            message = "📋 MT5_USERS Table Structure:\n\n"
            for column in structure:
                message += f"Column: {column['Field']}\n"
                message += f"Type: {column['Type']}\n"
                message += f"Null: {column['Null']}\n"
                message += f"Key: {column['Key']}\n"
                message += f"Default: {column['Default']}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(message)
        else:
            await update.message.reply_text("❌ Could not retrieve table structure")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking table: {e}")

async def debug_registrations_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug registration dates to see the actual data format."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get the most recent 10 accounts regardless of date
        query = """
        SELECT 
            Login as account_number,
            CONCAT(FirstName, ' ', LastName) as name,
            Registration as registration_date,
            NOW() as server_time,
            DATEDIFF(NOW(), Registration) as days_ago
        FROM mt5_users 
        ORDER BY Login DESC
        LIMIT 10
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "🔍 <b>Recent Accounts Debug Info:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                server_time = account['server_time']
                days_ago = account['days_ago']
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {reg_date}\n"
                message += f"<b>Server Time:</b> {server_time}\n"
                message += f"<b>Days Ago:</b> {days_ago}\n\n"
            
            # Split message if too long
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error debugging registrations: {e}")

async def check_my_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check specific account numbers with balance and essential details (fixed datetime issues)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "Usage: /checkmyaccounts <account1> <account2> ...\n\n"
            "Example: /checkmyaccounts 300666 300700 300800"
        )
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "🔍 <b>Account Details Report:</b>\n\n"
        
        for account_num in context.args:
            try:
                account_int = int(account_num)
                
                # Simplified query that avoids problematic datetime operations
                query = """
                SELECT 
                    Login,
                    CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                    FirstName,
                    LastName,
                    Email,
                    COALESCE(Balance, 0) as balance,
                    COALESCE(Credit, 0) as credit,
                    `Group` as account_group,
                    Status,
                    Country,
                    Company,
                    Registration as raw_registration,
                    LastAccess as raw_last_access,
                    Timestamp,
                    NOW() as server_time
                FROM mt5_users 
                WHERE Login = %s
                """
                
                results = mysql_db.execute_query(query, (account_int,))
                
                if results and len(results) > 0:
                    account = results[0]
                    
                    # Format balance with proper currency display
                    balance = float(account['balance']) if account['balance'] else 0.0
                    credit = float(account['credit']) if account['credit'] else 0.0
                    
                    # Color-code balance status
                    if balance > 0:
                        balance_status = "💰 Funded"
                        balance_emoji = "✅"
                    elif balance == 0:
                        balance_status = "⚪ Zero Balance"
                        balance_emoji = "⚠️"
                    else:
                        balance_status = "🔴 Negative"
                        balance_emoji = "❌"
                    
                    # Safe datetime processing
                    registration_display = "Unknown"
                    last_access_display = "Unknown"
                    account_age_display = "Unknown"
                    
                    # Process registration date safely
                    raw_reg = account.get('raw_registration')
                    if raw_reg and str(raw_reg) != '0000-00-00 00:00:00' and str(raw_reg) != 'None':
                        try:
                            if isinstance(raw_reg, str):
                                reg_date = datetime.strptime(raw_reg, '%Y-%m-%d %H:%M:%S')
                            else:
                                reg_date = raw_reg
                            registration_display = reg_date.strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Calculate age
                            age_days = (datetime.now() - reg_date).days
                            age_hours = (datetime.now() - reg_date).total_seconds() / 3600
                            account_age_display = f"{age_days} days ({int(age_hours)} hours)"
                        except:
                            registration_display = str(raw_reg)
                    
                    # Process last access safely
                    raw_access = account.get('raw_last_access')
                    if raw_access and str(raw_access) != '0000-00-00 00:00:00' and str(raw_access) != 'None':
                        try:
                            if isinstance(raw_access, str):
                                access_date = datetime.strptime(raw_access, '%Y-%m-%d %H:%M:%S')
                            else:
                                access_date = raw_access
                            last_access_display = access_date.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            last_access_display = str(raw_access)
                    
                    # Try to get creation date from timestamp if available
                    timestamp_display = "Not available"
                    if account.get('Timestamp') and account['Timestamp'] > 116444736000000000:
                        try:
                            # Convert FILETIME to readable datetime
                            timestamp_unix = (account['Timestamp'] - 116444736000000000) / 10000000
                            timestamp_date = datetime.fromtimestamp(timestamp_unix)
                            timestamp_display = timestamp_date.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            timestamp_display = f"Raw: {account['Timestamp']}"
                    
                    # Build the account info message
                    message += f"📊 <b>Account {account['Login']}</b> {balance_emoji}\n"
                    message += f"👤 <b>Name:</b> {account['name'] or 'Unknown'}\n"
                    message += f"📧 <b>Email:</b> {account['Email'] or 'Not provided'}\n"
                    message += f"🏢 <b>Company:</b> {account['Company'] or 'N/A'}\n"
                    message += f"🌍 <b>Country:</b> {account['Country'] or 'N/A'}\n\n"
                    
                    # Financial Information
                    message += f"💵 <b>FINANCIAL STATUS:</b>\n"
                    message += f"• Balance: ${balance:,.2f} ({balance_status})\n"
                    if credit != 0:
                        message += f"• Credit: ${credit:,.2f}\n"
                    message += f"• Group: {account['account_group'] or 'Default'}\n"
                    message += f"• Status: {account['Status'] or 'Unknown'}\n\n"
                    
                    # Account Timeline
                    message += f"⏰ <b>TIMELINE:</b>\n"
                    message += f"• Registration: {registration_display}\n"
                    message += f"• Last Access: {last_access_display}\n"
                    message += f"• Created (Timestamp): {timestamp_display}\n"
                    message += f"• Account Age: {account_age_display}\n"
                    message += f"• Server Time: {account['server_time']}\n"
                    
                    message += "\n" + "─" * 30 + "\n\n"
                    
                else:
                    message += f"❌ <b>Account {account_num}:</b> Not found in database\n\n"
                    
            except ValueError:
                message += f"❌ <b>Account {account_num}:</b> Invalid format (must be numeric)\n\n"
            except Exception as account_error:
                message += f"❌ <b>Account {account_num}:</b> Error - {str(account_error)[:100]}\n\n"
                print(f"Error processing account {account_num}: {account_error}")
        
        # Add summary if multiple accounts
        if len(context.args) > 1:
            try:
                # Get summary statistics using the same safe approach as quickbalance
                account_ints = [int(acc) for acc in context.args if acc.isdigit()]
                if account_ints:
                    summary_query = """
                    SELECT 
                        COUNT(*) as total_found,
                        COUNT(CASE WHEN COALESCE(Balance, 0) > 0 THEN 1 END) as funded_accounts,
                        SUM(COALESCE(Balance, 0)) as total_balance,
                        AVG(COALESCE(Balance, 0)) as avg_balance,
                        MAX(COALESCE(Balance, 0)) as max_balance,
                        MIN(COALESCE(Balance, 0)) as min_balance
                    FROM mt5_users 
                    WHERE Login IN ({})
                    """.format(','.join(['%s'] * len(account_ints)))
                    
                    summary_results = mysql_db.execute_query(summary_query, account_ints)
                    
                    if summary_results and len(summary_results) > 0:
                        summary = summary_results[0]
                        message += f"📈 <b>SUMMARY ({len(context.args)} accounts requested):</b>\n"
                        message += f"• Found in DB: {summary['total_found']}\n"
                        message += f"• Funded Accounts: {summary['funded_accounts']}\n"
                        message += f"• Total Balance: ${summary['total_balance']:,.2f}\n"
                        message += f"• Average Balance: ${summary['avg_balance']:,.2f}\n"
                        message += f"• Highest Balance: ${summary['max_balance']:,.2f}\n"
                        message += f"• Lowest Balance: ${summary['min_balance']:,.2f}\n"
                        
            except Exception as summary_error:
                print(f"Error generating summary: {summary_error}")
        
        # Split message if too long
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking accounts: {e}")
        print(f"Error in check_my_accounts_command: {e}")

async def quick_balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick balance check for specific accounts (simplified output)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /quickbalance <account1> <account2> ...")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "💰 <b>Quick Balance Check:</b>\n\n"
        total_balance = 0
        found_accounts = 0
        
        for account_num in context.args:
            try:
                account_int = int(account_num)
                
                # Simple balance query
                query = """
                SELECT 
                    Login,
                    CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                    COALESCE(Balance, 0) as balance,
                    Status
                FROM mt5_users 
                WHERE Login = %s
                """
                
                results = mysql_db.execute_query(query, (account_int,))
                
                if results and len(results) > 0:
                    account = results[0]
                    balance = float(account['balance'])
                    total_balance += balance
                    found_accounts += 1
                    
                    # Status emoji
                    if balance > 0:
                        emoji = "✅"
                    elif balance == 0:
                        emoji = "⚪"
                    else:
                        emoji = "❌"
                    
                    message += f"{emoji} <b>{account['Login']}</b>: ${balance:,.2f} ({account['name'] or 'Unknown'})\n"
                else:
                    message += f"❌ <b>{account_num}:</b> Not found\n"
                    
            except ValueError:
                message += f"❌ <b>{account_num}:</b> Invalid format\n"
        
        # Add totals
        if found_accounts > 0:
            message += f"\n📊 <b>Total:</b> {found_accounts} accounts, ${total_balance:,.2f}"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking balances: {e}")

async def simple_reg_check_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Simple check of registration dates."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Just get the registration dates without any fancy calculations
        query = """
        SELECT 
            Login,
            CONCAT(FirstName, ' ', LastName) as name,
            Registration
        FROM mt5_users 
        ORDER BY Login DESC
        LIMIT 15
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "📅 <b>Raw Registration Dates:</b>\n\n"
            for account in results:
                message += f"<b>{account['Login']}:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {account['Registration']}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def test_recent_fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test the recent accounts fix with multiple approaches."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    await update.message.reply_text("🔄 Testing different approaches to handle date issues...")
    
    # Test 1: Safe method
    try:
        safe_results = mysql_db.get_recent_accounts(days=15, limit=5)
        
        if safe_results:
            message = f"✅ <b>Safe Method Results (Last 15 Days):</b>\n\n"
            for account in safe_results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {account.get('registration_date', 'N/A')}\n"
                message += f"<b>Days Ago:</b> {account.get('days_ago', 'N/A')}\n\n"
                
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("✅ Safe method worked but found no recent results")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Safe method also failed: {e}")
        
    # Test 2: Very basic query
    try:
        basic_query = """
        SELECT 
            Login,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Registration
        FROM mt5_users 
        WHERE Login > 300000
        ORDER BY Login DESC
        LIMIT 10
        """
        
        basic_results = mysql_db.execute_query(basic_query)
        
        if basic_results:
            message = "✅ <b>Basic Query Results (Recent Logins):</b>\n\n"
            for account in basic_results:
                reg_date = account.get('Registration', 'N/A')
                if reg_date == '0000-00-00 00:00:00':
                    reg_date = 'Invalid Date'
                    
                message += f"<b>Account:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Registration:</b> {reg_date}\n\n"
                
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Basic query returned no results")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Basic query failed: {e}")

async def debug_zero_dates_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to understand the zero date issue."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check how many records have zero dates
        debug_query = """
        SELECT 
            COUNT(*) as total_records,
            COUNT(CASE WHEN Registration = '0000-00-00 00:00:00' THEN 1 END) as zero_dates,
            COUNT(CASE WHEN Registration IS NULL THEN 1 END) as null_dates,
            COUNT(CASE WHEN Registration > '1970-01-01 00:00:00' THEN 1 END) as valid_dates,
            MIN(Registration) as min_date,
            MAX(Registration) as max_date
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(debug_query)
        
        if results and len(results) > 0:
            stats = results[0]
            message = f"📊 <b>Registration Date Analysis:</b>\n\n"
            message += f"<b>Total Records:</b> {stats['total_records']:,}\n"
            message += f"<b>Zero Dates:</b> {stats['zero_dates']:,}\n"
            message += f"<b>Null Dates:</b> {stats['null_dates']:,}\n"
            message += f"<b>Valid Dates:</b> {stats['valid_dates']:,}\n"
            message += f"<b>Min Date:</b> {stats['min_date']}\n"
            message += f"<b>Max Date:</b> {stats['max_date']}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Could not retrieve date statistics")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error analyzing dates: {e}")

async def check_mysql_mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check MySQL SQL mode and settings."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check SQL mode
        mode_results = mysql_db.execute_query("SELECT @@sql_mode as sql_mode")
        timezone_results = mysql_db.execute_query("SELECT @@time_zone as time_zone")
        version_results = mysql_db.execute_query("SELECT VERSION() as version")
        
        message = "⚙️ <b>MySQL Configuration:</b>\n\n"
        
        if mode_results:
            message += f"<b>SQL Mode:</b> {mode_results[0]['sql_mode']}\n\n"
        
        if timezone_results:
            message += f"<b>Time Zone:</b> {timezone_results[0]['time_zone']}\n\n"
            
        if version_results:
            message += f"<b>Version:</b> {version_results[0]['version']}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking MySQL configuration: {e}")

async def test_timestamp_approach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test using the Timestamp column instead of Registration."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Test the Timestamp column
        test_query = """
        SELECT 
            Login,
            Timestamp,
            FROM_UNIXTIME(Timestamp) as readable_timestamp,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Registration
        FROM mt5_users 
        WHERE Timestamp > 0
        ORDER BY Timestamp DESC
        LIMIT 10
        """
        
        results = mysql_db.execute_query(test_query)
        
        if results:
            message = "🕒 <b>Testing Timestamp Column:</b>\n\n"
            for account in results:
                timestamp = account['Timestamp']
                readable_time = account['readable_timestamp']
                message += f"<b>Account:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Timestamp:</b> {timestamp}\n"
                message += f"<b>Readable:</b> {readable_time}\n"
                message += f"<b>Registration:</b> {account['Registration']}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No results from timestamp test")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error testing timestamp: {e}")

async def recent_accounts_timestamp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get recent accounts using the safe Timestamp column."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Calculate Unix timestamp for X days ago
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp = int(cutoff_date.timestamp())
        
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Timestamp,
            FROM_UNIXTIME(Timestamp) as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            ROUND((UNIX_TIMESTAMP() - Timestamp) / 86400) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 0
        ORDER BY Timestamp DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(query, (cutoff_timestamp,))
        
        if results:
            message = f"📅 <b>Recent Accounts (Last {days} Days) - Using Timestamp:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                if reg_date:
                    formatted_date = reg_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(reg_date, 'strftime') else str(reg_date)
                else:
                    formatted_date = 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Created:</b> {formatted_date}\n"
                message += f"<b>Days Ago:</b> {account['days_ago']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts found in the last {days} days using Timestamp")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def recent_accounts_by_login_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get recent accounts using Login ID (simplest approach)."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get the number of recent accounts to show
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 20
        
        # Simple query using Login ID (higher = newer)
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            CASE 
                WHEN Registration != '0000-00-00 00:00:00' THEN Registration
                ELSE 'No valid date'
            END as registration_display
        FROM mt5_users 
        WHERE Login >= 300000
        ORDER BY Login DESC
        LIMIT %s
        """
        
        results = mysql_db.execute_query(query, (limit,))
        
        if results:
            message = f"📅 <b>Most Recent {limit} Accounts (by Login ID):</b>\n\n"
            for account in results:
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Registration:</b> {account['registration_display']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No recent accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def find_recent_login_threshold_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Find what Login ID represents 'recent' accounts."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Find Login ID ranges
        query = """
        SELECT 
            MIN(Login) as min_login,
            MAX(Login) as max_login,
            COUNT(*) as total_accounts,
            COUNT(CASE WHEN Login >= 300000 THEN 1 END) as accounts_over_300k,
            COUNT(CASE WHEN Login >= 300500 THEN 1 END) as accounts_over_300_5k,
            COUNT(CASE WHEN Login >= 300600 THEN 1 END) as accounts_over_300_6k,
            COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300_7k,
            COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300_8k
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(query)
        
        if results and len(results) > 0:
            stats = results[0]
            message = f"📊 <b>Login ID Analysis:</b>\n\n"
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login ID Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,000:</b> {stats['accounts_over_300k']:,}\n"
            message += f"<b>Accounts with Login >= 300,500:</b> {stats['accounts_over_300_5k']:,}\n"
            message += f"<b>Accounts with Login >= 300,600:</b> {stats['accounts_over_300_6k']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,700:</b> {stats['accounts_over_300_7k']:,}\n\n"
            message += f"<b>Accounts with Login >= 300,800:</b> {stats['accounts_over_300_8k']:,}\n\n"
            
            # Suggest threshold
            if stats['accounts_over_300_6k'] > 0:
                message += "💡 <b>Suggestion:</b> Use Login >= 300600 for very recent accounts\n"
            elif stats['accounts_over_300_5k'] > 0:
                message += "💡 <b>Suggestion:</b> Use Login >= 300500 for recent accounts\n"
            else:
                message += "💡 <b>Suggestion:</b> Use Login >= 300000 for recent accounts\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("Could not retrieve Login ID statistics")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error analyzing Login IDs: {e}")

async def diagnose_account_access_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Diagnose what accounts we can actually see."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Test 1: Check if we can see specific account you mentioned
        specific_accounts = [300790, 300800, 300666, 300665]
        
        message = "🔍 <b>Account Access Diagnostic:</b>\n\n"
        
        for account_id in specific_accounts:
            try:
                query = "SELECT Login, FirstName, LastName FROM mt5_users WHERE Login = %s"
                result = mysql_db.execute_query(query, (account_id,))
                
                if result:
                    message += f"<b>Account {account_id}:</b> ✅ Found - {result[0]['FirstName']} {result[0]['LastName']}\n"
                else:
                    message += f"<b>Account {account_id}:</b> ❌ Not found\n"
            except Exception as e:
                message += f"<b>Account {account_id}:</b> Error - {str(e)[:50]}\n"
        
        # Test 2: Check highest Login IDs we can actually see
        try:
            query = "SELECT Login FROM mt5_users ORDER BY Login DESC LIMIT 10"
            results = mysql_db.execute_query(query)
            
            if results:
                message += f"\n<b>🔝 Highest Login IDs visible:</b>\n"
                for result in results:
                    message += f"  {result['Login']}\n"
            else:
                message += f"\n<b>Highest Login IDs:</b> None found\n"
        except Exception as e:
            message += f"\n<b>Highest Login IDs:</b> Error - {e}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Diagnostic error: {e}")

async def test_safe_login_query_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Test a completely safe query that avoids datetime columns."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Ultra-safe query that completely avoids datetime columns
        safe_query = """
        SELECT 
            Login,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group`,
            Status,
            Country
        FROM mt5_users 
        WHERE Login >= 300000
        ORDER BY Login DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(safe_query)
        
        if results:
            message = f"✅ <b>Safe Query Results (No Datetime Columns):</b>\n\n"
            for account in results:
                message += f"<b>Login:</b> {account['Login']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Status:</b> {account['Status']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No results from safe query")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Safe query also failed: {e}")

async def decode_mt5_timestamp_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Try to decode the MT5 timestamp format."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get some timestamps to analyze
        query = """
        SELECT 
            Login,
            Timestamp,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
        FROM mt5_users 
        WHERE Timestamp > 0
        ORDER BY Login DESC
        LIMIT 5
        """
        
        results = mysql_db.execute_query(query)
        
        if results:
            message = "🕒 <b>MT5 Timestamp Analysis:</b>\n\n"
            
            for account in results:
                timestamp = account['Timestamp']
                
                # Try different timestamp interpretations
                try:
                    # Method 1: Treat as Windows FILETIME (100-nanosecond intervals since 1601-01-01)
                    # Convert to Unix timestamp: (filetime - 116444736000000000) / 10000000
                    unix_timestamp = (timestamp - 116444736000000000) / 10000000
                    if unix_timestamp > 0:
                        from datetime import datetime
                        converted_date = datetime.fromtimestamp(unix_timestamp)
                        filetime_result = converted_date.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        filetime_result = "Invalid"
                except:
                    filetime_result = "Error"
                
                # Method 2: Treat as microseconds since epoch
                try:
                    microsecond_timestamp = timestamp / 1000000
                    micro_date = datetime.fromtimestamp(microsecond_timestamp)
                    microsecond_result = micro_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    microsecond_result = "Error"
                
                # Method 3: Treat as milliseconds since epoch  
                try:
                    millisecond_timestamp = timestamp / 1000
                    milli_date = datetime.fromtimestamp(millisecond_timestamp)
                    millisecond_result = milli_date.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    millisecond_result = "Error"
                
                message += f"<b>Account {account['Login']}:</b> {account['name']}\n"
                message += f"<b>Raw Timestamp:</b> {timestamp}\n"
                message += f"<b>As FILETIME:</b> {filetime_result}\n"
                message += f"<b>As Microseconds:</b> {microsecond_result}\n"
                message += f"<b>As Milliseconds:</b> {millisecond_result}\n\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No timestamp data found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Timestamp analysis error: {e}")

async def check_user_permissions_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check what permissions our database user has."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Check current user and permissions
        queries = [
            ("Current User", "SELECT USER() as current_user"),
            ("Current Database", "SELECT DATABASE() as current_db"),
            ("User Grants", "SHOW GRANTS"),
            ("Table Count Check", "SELECT COUNT(*) as total_rows FROM mt5_users"),
        ]
        
        message = "🔐 <b>Database Permissions Check:</b>\n\n"
        
        for check_name, query in queries:
            try:
                results = mysql_db.execute_query(query)
                if results:
                    if check_name == "User Grants":
                        message += f"<b>{check_name}:</b>\n"
                        for grant in results:
                            grant_text = list(grant.values())[0]
                            message += f"  {grant_text}\n"
                        message += "\n"
                    else:
                        result_value = list(results[0].values())[0]
                        message += f"<b>{check_name}:</b> {result_value}\n"
                else:
                    message += f"<b>{check_name}:</b> No results\n"
            except Exception as e:
                message += f"<b>{check_name}:</b> Error - {str(e)[:100]}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Permissions check error: {e}")
        
async def recent_accounts_final_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Final working version - get recent accounts using FILETIME."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        days = int(context.args[0]) if context.args and context.args[0].isdigit() else 7
        
        # Use FILETIME timestamp for accurate recent account filtering
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_filetime = int((cutoff_date.timestamp() * 10000000) + 116444736000000000)
        
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Timestamp,
            FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            ROUND((UNIX_TIMESTAMP() * 10000000 + 116444736000000000 - Timestamp) / 864000000000) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 116444736000000000
        ORDER BY Timestamp DESC
        LIMIT 20
        """
        
        results = mysql_db.execute_query(query, (cutoff_filetime,))
        
        if results:
            message = f"📅 <b>Recent Accounts (Last {days} Days) - FINAL VERSION:</b>\n\n"
            for account in results:
                reg_date = account['registration_date']
                formatted_date = reg_date.strftime('%Y-%m-%d %H:%M:%S') if reg_date else 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Group:</b> {account['account_group']}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Country:</b> {account['Country']}\n"
                message += f"<b>Created:</b> {formatted_date}\n"
                message += f"<b>Days Ago:</b> {account['days_ago']}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No accounts created in the last {days} days")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting recent accounts: {e}")

async def newest_accounts_simple_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ultra-simple version - just get the newest accounts by Login ID."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        limit = int(context.args[0]) if context.args and context.args[0].isdigit() else 10
        
        # Completely safe query - no datetime columns at all
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as created_date
        FROM mt5_users 
        WHERE Timestamp > 116444736000000000
        ORDER BY Login DESC
        LIMIT %s
        """
        
        results = mysql_db.execute_query(query, (limit,))
        
        if results:
            message = f"📅 <b>Newest {limit} Accounts (by Login ID):</b>\n\n"
            for account in results:
                created_date = account['created_date']
                formatted_date = created_date.strftime('%Y-%m-%d %H:%M:%S') if created_date else 'Unknown'
                
                message += f"<b>Account:</b> {account['account_number']}\n"
                message += f"<b>Name:</b> {account['name']}\n"
                message += f"<b>Email:</b> {account.get('Email', 'N/A')}\n"
                message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                message += f"<b>Status:</b> {account['Status']}\n"
                message += f"<b>Created:</b> {formatted_date}\n\n"
            
            if len(message) > 4000:
                chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='HTML')
            else:
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No accounts found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting newest accounts: {e}")

async def show_all_tables_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all tables in the current database."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Show all tables in current database
        tables_query = "SHOW TABLES"
        results = mysql_db.execute_query(tables_query)
        
        if results:
            message = "📋 <b>All Tables in 'metatrader5' Database:</b>\n\n"
            
            for table in results:
                table_name = list(table.values())[0]  # Get the table name
                
                # Get row count for each table
                try:
                    count_query = f"SELECT COUNT(*) as count FROM `{table_name}`"
                    count_result = mysql_db.execute_query(count_query)
                    row_count = count_result[0]['count'] if count_result else 0
                    
                    message += f"📊 <b>{table_name}</b>: {row_count:,} rows\n"
                except Exception as e:
                    message += f"📊 <b>{table_name}</b>: Error counting - {str(e)[:50]}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No tables found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error showing tables: {e}")
        
async def show_all_databases_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show all databases available."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Show all databases
        databases_query = "SHOW DATABASES"
        results = mysql_db.execute_query(databases_query)
        
        if results:
            message = "🗄️ <b>All Available Databases:</b>\n\n"
            
            for db in results:
                db_name = list(db.values())[0]  # Get the database name
                
                # Check if we can access it
                try:
                    use_query = f"SELECT COUNT(*) as table_count FROM information_schema.tables WHERE table_schema = '{db_name}'"
                    table_count_result = mysql_db.execute_query(use_query)
                    table_count = table_count_result[0]['table_count'] if table_count_result else 0
                    
                    message += f"🗂️ <b>{db_name}</b>: {table_count} tables\n"
                except Exception as e:
                    message += f"🗂️ <b>{db_name}</b>: Access error\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No databases found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error showing databases: {e}")
                
async def search_user_tables_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search for tables that might contain user/account data."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Search for tables with user/account-related names
        search_query = """
        SELECT 
            table_schema as database_name,
            table_name,
            table_rows as estimated_rows
        FROM information_schema.tables 
        WHERE table_name LIKE '%user%' 
           OR table_name LIKE '%account%' 
           OR table_name LIKE '%mt5%'
           OR table_name LIKE '%client%'
           OR table_name LIKE '%trader%'
           OR table_name LIKE '%login%'
        ORDER BY table_schema, table_name
        """
        
        results = mysql_db.execute_query(search_query)
        
        if results:
            message = "🔍 <b>Tables That Might Contain Account Data:</b>\n\n"
            
            current_db = None
            for table in results:
                db_name = table['database_name']
                table_name = table['table_name']
                row_count = table['estimated_rows'] or 0
                
                if db_name != current_db:
                    message += f"\n📂 <b>Database: {db_name}</b>\n"
                    current_db = db_name
                
                message += f"  📊 {table_name}: ~{row_count:,} rows\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No user/account tables found")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error searching tables: {e}")
        
async def check_table_for_high_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check a specific table for high account numbers."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    # Get table name from command arguments
    if not context.args:
        await update.message.reply_text(
            "Usage: /checktable <table_name>\n\n"
            "Example: /checktable mt5_users\n"
            "Use /showtables first to see available tables"
        )
        return
    
    table_name = context.args[0]
    
    try:
        # First, check if table exists and has a Login column
        describe_query = f"DESCRIBE `{table_name}`"
        table_structure = mysql_db.execute_query(describe_query)
        
        if not table_structure:
            await update.message.reply_text(f"❌ Table '{table_name}' not found")
            return
        
        # Check if Login column exists
        columns = [col['Field'] for col in table_structure]
        if 'Login' not in columns:
            await update.message.reply_text(
                f"❌ Table '{table_name}' doesn't have a 'Login' column\n\n"
                f"Available columns: {', '.join(columns)}"
            )
            return
        
        # Check for high account numbers
        high_accounts_query = f"""
        SELECT 
            MIN(Login) as min_login,
            MAX(Login) as max_login,
            COUNT(*) as total_accounts,
            COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300700,
            COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300800
        FROM `{table_name}`
        """
        
        results = mysql_db.execute_query(high_accounts_query)
        
        if results:
            stats = results[0]
            message = f"📊 <b>Account Analysis for Table '{table_name}':</b>\n\n"
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n"
            message += f"<b>Accounts >= 300,700:</b> {stats['accounts_over_300700']:,}\n"
            message += f"<b>Accounts >= 300,800:</b> {stats['accounts_over_300800']:,}\n\n"
            
            # If we found high accounts, show some examples
            if stats['max_login'] > 300700:
                sample_query = f"""
                SELECT Login, 
                       CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
                FROM `{table_name}` 
                WHERE Login >= 300700 
                ORDER BY Login DESC 
                LIMIT 5
                """
                
                sample_results = mysql_db.execute_query(sample_query)
                if sample_results:
                    message += "<b>🎯 High Account Numbers Found:</b>\n"
                    for account in sample_results:
                        message += f"  {account['Login']}: {account['name']}\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text(f"No data found in table '{table_name}'")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking table '{table_name}': {e}")

async def compare_current_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show info about the current table we're using."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        message = "📋 <b>Current Table Information:</b>\n\n"
        message += f"<b>Database:</b> metatrader5\n"
        message += f"<b>Table:</b> mt5_users\n\n"
        
        # Get basic stats
        stats_query = """
        SELECT 
            COUNT(*) as total_accounts,
            MIN(Login) as min_login,
            MAX(Login) as max_login
        FROM mt5_users
        """
        
        results = mysql_db.execute_query(stats_query)
        if results:
            stats = results[0]
            message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
            message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n\n"
        
        message += "<b>This is the table that contains accounts up to 300666</b>\n"
        message += "<b>Accounts 300700+ might be in a different table</b>"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting current table info: {e}")

async def check_mt5_accounts_table_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check the mt5_accounts table structure and content."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # First, check the structure of mt5_accounts
        structure_query = "DESCRIBE mt5_accounts"
        structure_results = mysql_db.execute_query(structure_query)
        
        if structure_results:
            message = "📋 <b>MT5_ACCOUNTS Table Structure:</b>\n\n"
            for column in structure_results[:10]:  # Show first 10 columns
                message += f"<b>{column['Field']}</b>: {column['Type']}\n"
            
            if len(structure_results) > 10:
                message += f"... and {len(structure_results) - 10} more columns\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        
        # Check if it has a Login column and get stats
        columns = [col['Field'] for col in structure_results]
        if 'Login' in columns:
            stats_query = """
            SELECT 
                COUNT(*) as total_accounts,
                MIN(Login) as min_login,
                MAX(Login) as max_login,
                COUNT(CASE WHEN Login >= 300700 THEN 1 END) as accounts_over_300700,
                COUNT(CASE WHEN Login >= 300800 THEN 1 END) as accounts_over_300800
            FROM mt5_accounts
            """
            
            stats_results = mysql_db.execute_query(stats_query)
            
            if stats_results:
                stats = stats_results[0]
                message = f"📊 <b>MT5_ACCOUNTS Table Analysis:</b>\n\n"
                message += f"<b>Total Accounts:</b> {stats['total_accounts']:,}\n"
                message += f"<b>Login Range:</b> {stats['min_login']:,} to {stats['max_login']:,}\n"
                message += f"<b>Accounts >= 300,700:</b> {stats['accounts_over_300700']:,}\n"
                message += f"<b>Accounts >= 300,800:</b> {stats['accounts_over_300800']:,}\n\n"
                
                # Check if this table has higher accounts
                if stats['max_login'] > 300700:
                    message += "🎯 <b>FOUND IT! This table has higher account numbers!</b>\n\n"
                    
                    # Show some examples of high accounts
                    sample_query = """
                    SELECT Login, 
                           CONCAT(COALESCE(Name, ''), ' ', COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name
                    FROM mt5_accounts 
                    WHERE Login >= 300700 
                    ORDER BY Login DESC 
                    LIMIT 10
                    """
                    
                    sample_results = mysql_db.execute_query(sample_query)
                    if sample_results:
                        message += "<b>Sample High Account Numbers:</b>\n"
                        for account in sample_results:
                            message += f"  {account['Login']}: {account['name']}\n"
                else:
                    message += "❌ This table also only goes up to 300666\n"
                
                await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("❌ mt5_accounts table doesn't have a Login column")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error checking mt5_accounts table: {e}")

async def compare_users_vs_accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compare mt5_users vs mt5_accounts tables."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get structure of both tables
        users_structure = mysql_db.execute_query("DESCRIBE mt5_users")
        accounts_structure = mysql_db.execute_query("DESCRIBE mt5_accounts")
        
        message = "🔍 <b>MT5_USERS vs MT5_ACCOUNTS Comparison:</b>\n\n"
        
        # Compare column counts
        users_cols = len(users_structure) if users_structure else 0
        accounts_cols = len(accounts_structure) if accounts_structure else 0
        
        message += f"<b>MT5_USERS:</b> {users_cols} columns\n"
        message += f"<b>MT5_ACCOUNTS:</b> {accounts_cols} columns\n\n"
        
        # Check if both have Login column
        users_columns = [col['Field'] for col in users_structure] if users_structure else []
        accounts_columns = [col['Field'] for col in accounts_structure] if accounts_structure else []
        
        message += f"<b>MT5_USERS has Login column:</b> {'✅' if 'Login' in users_columns else '❌'}\n"
        message += f"<b>MT5_ACCOUNTS has Login column:</b> {'✅' if 'Login' in accounts_columns else '❌'}\n\n"
        
        # Show unique columns in each table
        if users_columns and accounts_columns:
            users_only = set(users_columns) - set(accounts_columns)
            accounts_only = set(accounts_columns) - set(users_columns)
            common = set(users_columns) & set(accounts_columns)
            
            message += f"<b>Common columns:</b> {len(common)}\n"
            message += f"<b>Only in MT5_USERS:</b> {len(users_only)}\n"
            message += f"<b>Only in MT5_ACCOUNTS:</b> {len(accounts_only)}\n\n"
            
            if accounts_only:
                message += f"<b>Unique to MT5_ACCOUNTS:</b>\n"
                for col in sorted(list(accounts_only)[:10]):  # Show first 10
                    message += f"  • {col}\n"
        
        await update.message.reply_text(message, parse_mode='HTML')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error comparing tables: {e}")

async def check_accounts_table_sample_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Get a sample of data from mt5_accounts table."""
    if update.effective_user.id not in ADMIN_USER_ID:
        await update.message.reply_text("This command is only available to admins.")
        return
    
    mysql_db = get_mysql_connection()
    
    if not mysql_db.is_connected():
        await update.message.reply_text("❌ MySQL database not available")
        return
    
    try:
        # Get structure first to see what columns are available
        structure_query = "DESCRIBE mt5_accounts"
        structure_results = mysql_db.execute_query(structure_query)
        
        if not structure_results:
            await update.message.reply_text("❌ Could not access mt5_accounts table")
            return
        
        columns = [col['Field'] for col in structure_results]
        
        # Build a safe query based on available columns
        select_columns = []
        if 'Login' in columns:
            select_columns.append('Login')
        if 'Name' in columns:
            select_columns.append('Name')
        if 'FirstName' in columns:
            select_columns.append('FirstName')
        if 'LastName' in columns:
            select_columns.append('LastName')
        if 'Balance' in columns:
            select_columns.append('COALESCE(Balance, 0) as Balance')
        if 'Group' in columns:
            select_columns.append('`Group`')
        if 'Status' in columns:
            select_columns.append('Status')
        
        if not select_columns:
            await update.message.reply_text("❌ No recognizable columns found in mt5_accounts")
            return
        
        # Get sample data
        sample_query = f"""
        SELECT {', '.join(select_columns)}
        FROM mt5_accounts 
        ORDER BY Login DESC 
        LIMIT 10
        """
        
        results = mysql_db.execute_query(sample_query)
        
        if results:
            message = "📊 <b>MT5_ACCOUNTS Sample Data (Top 10 by Login):</b>\n\n"
            
            for account in results:
                message += f"<b>Login:</b> {account.get('Login', 'N/A')}\n"
                
                # Build name from available fields
                name_parts = []
                if 'Name' in account and account['Name']:
                    name_parts.append(account['Name'])
                if 'FirstName' in account and account['FirstName']:
                    name_parts.append(account['FirstName'])
                if 'LastName' in account and account['LastName']:
                    name_parts.append(account['LastName'])
                
                name = ' '.join(name_parts) if name_parts else 'N/A'
                message += f"<b>Name:</b> {name}\n"
                
                if 'Balance' in account:
                    message += f"<b>Balance:</b> ${account['Balance']:.2f}\n"
                if 'Group' in account:
                    message += f"<b>Group:</b> {account.get('Group', 'N/A')}\n"
                if 'Status' in account:
                    message += f"<b>Status:</b> {account.get('Status', 'N/A')}\n"
                
                message += "\n"
            
            await update.message.reply_text(message, parse_mode='HTML')
        else:
            await update.message.reply_text("No data found in mt5_accounts table")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting sample from mt5_accounts: {e}")



