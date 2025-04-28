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
        if db_path:
            try:
                self.trading_accounts = pl.read_csv(db_path)
            except:
                # Create an empty DataFrame if file doesn't exist
                self.trading_accounts = pl.DataFrame({
                    "account_number": [],
                    "user_id": [],
                    "verified": [],
                    "verification_date": []
                })
        else:
            # For testing, create a sample dataframe with some mock accounts
            self.trading_accounts = pl.DataFrame({
                "account_number": ["TR" + ''.join(random.choices(string.digits, k=8)) for _ in range(5)],
                "user_id": [None] * 5,
                "verified": [False] * 5,
                "verification_date": [None] * 5
            })
    
    def validate_account_format(self, account_number):
        """Check if the account number matches the expected format."""
        try:
            # First try to convert to integer to see if it's numeric
            account_int = int(account_number)
            
            # Now check if it's 6 digits (between 100000 and 999999)
            if 100000 <= account_int <= 999999:
                print(f"Account {account_number} validation: SUCCESS")
                return True
            else:
                print(f"Account {account_number} validation: FAILED - not 6 digits")
                return False
        except ValueError:
            print(f"Account {account_number} validation: FAILED - not numeric")
            return False
    
    def verify_account(self, account_number, user_id):
        """Verify if the account number exists in the database."""
        # Check if the account exists
        filtered = self.trading_accounts.filter(
            pl.col("account_number") == account_number
        )
        
        if filtered.height > 0:
            # Update the user_id for this account and mark as verified
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # In a real implementation, you'd update the actual database here
            # For now, we just update our in-memory DataFrame
            idx = self.trading_accounts.with_row_count().filter(
                pl.col("account_number") == account_number
            )["row_nr"][0]
            
            self.trading_accounts = self.trading_accounts.with_columns([
                pl.when(pl.col("account_number") == account_number)
                .then(user_id)
                .otherwise(pl.col("user_id"))
                .alias("user_id"),
                
                pl.when(pl.col("account_number") == account_number)
                .then(True)
                .otherwise(pl.col("verified"))
                .alias("verified"),
                
                pl.when(pl.col("account_number") == account_number)
                .then(now)
                .otherwise(pl.col("verification_date"))
                .alias("verification_date")
            ])
            
            # Add to verified users dictionary for quick lookup
            self.verified_users[user_id] = {
                "account_number": account_number,
                "verified_at": now
            }
            
            return True
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