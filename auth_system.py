import os
import re
import hashlib
import random
import string
from datetime import datetime, timedelta
from mysql_manager import get_mysql_connection

class TradingAccountAuth:
    def __init__(self, db_path=None):
        """Initialize the authentication system with MySQL support."""
        self.verified_users = {}
        self.auth_attempts = {}
        self.max_attempts = 3
        self.db_path = db_path
        
        # Initialize MySQL connection
        self.mysql_db = get_mysql_connection()
        
        # Test connection
        if self.mysql_db.is_connected():
            print("✅ MySQL authentication system initialized")
        else:
            print("⚠️ MySQL connection failed, falling back to CSV method")
    
    def validate_account_format(self, account_number):
        """Check if the account number matches the expected format."""
        try:
            # First try to convert to integer to see if it's numeric
            account_int = int(account_number)
            
            # For MT5 accounts, they're typically 6-7 digit numbers
            if 100000 <= account_int <= 9999999:  # Expanded range for MT5
                print(f"Account {account_number} validation: SUCCESS")
                return True
            else:
                print(f"Account {account_number} validation: FAILED - not a valid account number")
                return False
        except ValueError:
            print(f"Account {account_number} validation: FAILED - not numeric")
            return False

    def verify_account(self, account_number, user_id):
        """Verify if the account number exists in the real-time MySQL database."""
        try:
            print(f"Verifying account {account_number} against MySQL database")
            
            # First check if MySQL is available
            if not self.mysql_db or not self.mysql_db.is_connected():
                print("MySQL not available, falling back to CSV method")
                return self._verify_account_csv_fallback(account_number, user_id)
            
            # Verify account exists in MySQL
            verification_result = self.mysql_db.verify_account_exists(account_number)
            
            if verification_result['exists']:
                account_owner = verification_result['name']
                account_email = verification_result.get('email', '')
                account_balance = verification_result.get('balance', 0)
                account_group = verification_result.get('group', '')
                
                print(f"Account {account_number} verified: belongs to {account_owner} (Balance: ${account_balance})")
                
                # Record verification in our system
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Add to verified users dictionary for quick lookup
                self.verified_users[user_id] = {
                    "account_number": account_number,
                    "verified_at": now,
                    "account_owner": account_owner,
                    "account_email": account_email,
                    "account_balance": account_balance,
                    "account_group": account_group,
                    "verification_method": "mysql"
                }
                
                return True
            else:
                error_msg = verification_result.get('error', 'Account not found')
                print(f"Account {account_number} not found in MySQL database: {error_msg}")
                return False
                
        except Exception as e:
            print(f"Error verifying account against DataBase: {e}")
            # Fall back to CSV method
            return self._verify_account_csv_fallback(account_number, user_id)
    
    def _verify_account_csv_fallback(self, account_number, user_id):
        """Fallback method using CSV file if MySQL is unavailable."""
        try:
            import polars as pl
            
            # Load the accounts CSV as fallback
            accounts_df = pl.read_csv("./bot_data/Accounts_List.csv")
            
            # Convert account_number to integer for comparison
            account_int = int(account_number)
            account_match = accounts_df.filter(pl.col("Account") == account_int)
            
            if account_match.height > 0:
                account_owner = account_match.select("Name")[0, 0]
                print(f"Account {account_number} verified via CSV: belongs to {account_owner}")
                
                # Record verification
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.verified_users[user_id] = {
                    "account_number": account_number,
                    "verified_at": now,
                    "account_owner": account_owner,
                    "verification_method": "csv_fallback"
                }
                
                return True
            else:
                print(f"Account {account_number} not found in CSV")
                return False
                
        except Exception as e:
            print(f"CSV fallback verification also failed: {e}")
            return False
    
    def get_account_info(self, account_number):
        """Get detailed account information from MySQL."""
        if not self.mysql_db or not self.mysql_db.is_connected():
            return None
        
        try:
            account_int = int(account_number)
            return self.mysql_db.get_account_by_login(account_int)
        except Exception as e:
            print(f"Error getting account info: {e}")
            return None
    
    def is_user_verified(self, user_id):
        """Check if the user is already verified."""
        return user_id in self.verified_users
    
    def generate_captcha(self):
        """Generate a simple math CAPTCHA."""
        operations = [('+', lambda x, y: x + y), 
                     ('-', lambda x, y: x - y),
                     ('*', lambda x, y: x * y)]
        
        # Select random numbers and operation
        a = random.randint(1, 10)
        b = random.randint(1, 10)
        op_symbol, op_func = random.choice(operations)
        
        # For subtraction, ensure a > b to avoid negative results
        if op_symbol == '-' and a < b:
            a, b = b, a
        
        # For multiplication, use smaller numbers
        if op_symbol == '*':
            a = random.randint(1, 5)
            b = random.randint(1, 5)
        
        answer = op_func(a, b)
        question = f"What is {a} {op_symbol} {b}?"
        
        return question, answer
    
    def record_attempt(self, user_id, success):
        """Record authentication attempts to prevent brute-forcing."""
        now = datetime.now()
        
        if user_id not in self.auth_attempts:
            self.auth_attempts[user_id] = []
            
        self.auth_attempts[user_id].append({
            'timestamp': now,
            'success': success
        })
        
        # Clean up old attempts (older than 1 hour)
        self.auth_attempts[user_id] = [
            attempt for attempt in self.auth_attempts[user_id] 
            if now - attempt['timestamp'] < timedelta(minutes = 3)
        ]
    
    def can_attempt_auth(self, user_id):
        """Check if the user has not exceeded max failed attempts."""
        if user_id not in self.auth_attempts:
            return True
            
        recent_attempts = self.auth_attempts[user_id]
        recent_failures = sum(1 for a in recent_attempts if not a['success'])
        
        return recent_failures < self.max_attempts
    
    def save_to_database(self):
        """Save the updated user verification data to CSV."""
        if self.db_path:
            self.trading_accounts.write_csv(self.db_path)
            return True
        return False


# Example usage
if __name__ == "__main__":
    # Create auth system
    auth = TradingAccountAuth()
    
    # Example account number to validate
    test_account = "TR12345678"
    
    # Validate format
    if auth.validate_account_format(test_account):
        print(f"Account format is valid: {test_account}")
    else:
        print(f"Invalid account format: {test_account}")
    
    # Generate CAPTCHA
    question, answer = auth.generate_captcha()
    print(f"CAPTCHA: {question}, Answer: {answer}")
    
    
    
