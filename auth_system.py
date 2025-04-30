import os
import re
import polars as pl
import hashlib
import random
import string
from datetime import datetime, timedelta

class TradingAccountAuth:
    def __init__(self, db_path=None):
        """Initialize the authentication system with an optional database path."""
        self.verified_users = {}
        self.auth_attempts = {}
        self.max_attempts = 3
        self.db_path = db_path
        
        # If a database is provided, load verified accounts
        if db_path and os.path.exists(db_path):
            try:
                self.trading_accounts = pl.read_csv(db_path)
            except Exception as e:
                print(f"Error loading trading accounts database: {e}")
                self.create_empty_trading_accounts()
        else:
            # Create an empty DataFrame with the correct schema
            self.create_empty_trading_accounts()
    
    
    def create_empty_trading_accounts(self):
        """Create an empty trading accounts DataFrame with the correct schema."""
        self.trading_accounts = pl.DataFrame({
            "account_number": [],
            "user_id": [],
            "verified": [],
            "verification_date": []
        })
    
    def validate_account_format(self, account_number):
        """Check if the account number matches the expected format."""
        try:
            # First try to convert to integer to see if it's numeric
            account_int = int(account_number)
            
            # Now check if it's a valid account number format
            # For Vortex FX, accounts appear to be 6-digit numbers based on Accounts_List.csv
            if 100000 <= account_int <= 999999:
                print(f"Account {account_number} validation: SUCCESS")
                return True
            else:
                print(f"Account {account_number} validation: FAILED - not a valid account number")
                return False
        except ValueError:
            print(f"Account {account_number} validation: FAILED - not numeric")
            return False

    def verify_account(self, account_number, user_id):
        """Verify if the account number exists in the real Accounts_List.csv."""
        try:
            # Convert to integer
            account_int = int(account_number)
            
            # Load the accounts CSV
            try:
                accounts_df = pl.read_csv("./bot_data/Accounts_List.csv")
                
                # Check if account exists
                account_match = accounts_df.filter(pl.col("Account") == account_int)
                
                if account_match.height > 0:
                    # Account exists in the list
                    account_owner = account_match.select("Name")[0, 0]
                    print(f"Account {account_number} verified: belongs to {account_owner}")
                    
                    # Record verification in our system
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Initialize the trading_accounts DataFrame if it doesn't exist
                    if not hasattr(self, 'trading_accounts') or self.trading_accounts is None:
                        self.trading_accounts = pl.DataFrame({
                            "account_number": [account_number],
                            "user_id": [user_id],
                            "verified": [True],
                            "verification_date": [now]
                        })
                    else:
                        # Check if account already exists in our tracking dataframe
                        account_exists = self.trading_accounts.filter(pl.col("account_number") == account_number)
                        
                        if account_exists.height > 0:
                            # Update existing record
                            self.trading_accounts = self.trading_accounts.with_columns([
                                pl.when(pl.col("account_number") == account_number)
                                .then(pl.lit(user_id))
                                .otherwise(pl.col("user_id"))
                                .alias("user_id"),
                                
                                pl.when(pl.col("account_number") == account_number)
                                .then(pl.lit(True))
                                .otherwise(pl.col("verified"))
                                .alias("verified"),
                                
                                pl.when(pl.col("account_number") == account_number)
                                .then(pl.lit(now))
                                .otherwise(pl.col("verification_date"))
                                .alias("verification_date")
                            ])
                        else:
                            # Add new record
                            new_record = pl.DataFrame({
                                "account_number": [account_number],
                                "user_id": [user_id],
                                "verified": [True],
                                "verification_date": [now]
                            })
                            self.trading_accounts = pl.concat([self.trading_accounts, new_record])
                    
                    # Add to verified users dictionary for quick lookup
                    self.verified_users[user_id] = {
                        "account_number": account_number,
                        "verified_at": now,
                        "account_owner": account_owner
                    }
                    
                    return True
                else:
                    print(f"Account {account_number} not found in Accounts_List.csv")
                    return False
                    
            except Exception as e:
                print(f"Error loading or processing Accounts_List.csv: {e}")
                # Fall back to a more basic verification method
                print("Falling back to basic verification method")
                
                # Just record the attempt for now
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.verified_users[user_id] = {
                    "account_number": account_number,
                    "verified_at": now,
                    "verified": False
                }
                return False
                
        except ValueError:
            print(f"Could not convert account number to integer for verification")
            return False
    
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