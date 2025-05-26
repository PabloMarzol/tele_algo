import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

class MySQLManager:
    """MySQL database manager for real-time account verification."""
    
    def __init__(self):
        """Initialize MySQL connection."""
        self.logger = logging.getLogger('MySQLManager')
        self.connection = None
        self.cursor = None
        
        # Database connection parameters
        self.config = {
            'host': os.getenv('RDB_HOST', '77.68.73.142'),
            'port': int(os.getenv('RDB_PORT', 3306)),
            'database': os.getenv('RDB_DATABASE', 'metatrader5'),
            'user': os.getenv('RDB_USERNAME', 'vfxbot'),
            'password': os.getenv('RDB_PASSWORD', 'uVHK8u1$55w'),
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_unicode_ci',
            'autocommit': True,
            'raise_on_warnings': True,
            # Add SQL mode to handle zero dates properly
            'sql_mode': 'TRADITIONAL,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'
        }
        
        self.connect()
    
    def connect(self):
        """Establish connection to MySQL database."""
        try:
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor(dictionary=True)  # Returns rows as dictionaries
            
            # Set session variables to handle zero dates properly
            session_queries = [
                "SET SESSION sql_mode = 'TRADITIONAL,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'",
                "SET SESSION time_zone = '+00:00'"
            ]
            
            for query in session_queries:
                try:
                    self.cursor.execute(query)
                except Exception as e:
                    self.logger.warning(f"Could not set session variable: {query} - {e}")
                    
            self.logger.info("Successfully connected to MySQL database")
            print("✅ Connected to MySQL database")
            return True
        except Error as e:
            self.logger.error(f"Error connecting to MySQL: {e}")
            print(f"❌ Error connecting to MySQL: {e}")
            return False
    
    def is_connected(self):
        """Check if connection is active."""
        try:
            return self.connection and self.connection.is_connected()
        except:
            return False
    
    def reconnect(self):
        """Reconnect to database if connection is lost."""
        try:
            if self.connection:
                self.connection.close()
        except:
            pass
        
        return self.connect()
    
    def execute_query(self, query, params=None):
        """Execute a SELECT query and return results."""
        try:
            if not self.is_connected():
                self.reconnect()
            
            self.cursor.execute(query, params or ())
            results = self.cursor.fetchall()
            return results
        except Error as e:
            self.logger.error(f"Error executing query: {e}")
            print(f"❌ Query error: {e}")
            return None
    
    def get_account_by_login(self, login):
        """Get account information by login/account number."""
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            FirstName,
            LastName,
            MiddleName,
            Email as email,
            CASE 
                WHEN Registration IS NULL OR Registration = '0000-00-00 00:00:00' THEN NULL
                ELSE Registration 
            END as registration_date,
            CASE 
                WHEN LastAccess IS NULL OR LastAccess = '0000-00-00 00:00:00' THEN NULL
                ELSE LastAccess 
            END as last_access,
            COALESCE(Balance, 0) as balance,
            COALESCE(Credit, 0) as credit,
            COALESCE(InterestRate, 0) as interest_rate,
            `Group` as account_group,
            Company,
            Country,
            City,
            Phone,
            Status,
            COALESCE(Leverage, 0) as leverage,
            ClientID
        FROM mt5_users 
        WHERE Login = %s
        LIMIT 1
        """
        
        try:
            results = self.execute_query(query, (login,))
            if results and len(results) > 0:
                return results[0]
            return None
        except Exception as e:
            self.logger.error(f"Error getting account by login {login}: {e}")
            return None
    
    def search_accounts(self, search_term, limit=50):
        """Search for accounts by login, name, or email."""
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            FirstName,
            LastName,
            Email as email,
            CASE 
                WHEN Registration IS NULL OR Registration = '0000-00-00 00:00:00' THEN NULL
                ELSE Registration 
            END as registration_date,
            COALESCE(Balance, 0) as balance,
            `Group` as account_group,
            Status,
            Country,
            Company
        FROM mt5_users 
        WHERE Login LIKE %s 
           OR FirstName LIKE %s 
           OR LastName LIKE %s
           OR Email LIKE %s
           OR CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) LIKE %s
        ORDER BY Login DESC
        LIMIT %s
        """
        
        search_pattern = f"%{search_term}%"
        try:
            results = self.execute_query(query, (search_pattern, search_pattern, search_pattern, search_pattern, search_pattern, limit))
            return results or []
        except Exception as e:
            self.logger.error(f"Error searching accounts: {e}")
            return []
    
    def verify_account_exists(self, account_number):
        """Enhanced version that verifies account exists AND is a real/live account (not demo)."""
        try:
            account_int = int(account_number)
            
            # Safe query that avoids Registration column
            query = """
            SELECT 
                Login as account_number,
                CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                FirstName,
                LastName,
                Email,
                COALESCE(Balance, 0) as balance,
                `Group` as account_group,
                Status,
                Country,
                Company,
                COALESCE(Leverage, 0) as leverage,
                FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as creation_date
            FROM mt5_users 
            WHERE Login = %s
            LIMIT 1
            """
            
            results = self.execute_query(query, (account_int,))
            
            if results and len(results) > 0:
                account_info = results[0]
                account_group = account_info['account_group'] or ''
                
                # CHECK IF ACCOUNT IS REAL/LIVE (not demo)
                is_real_account = self._is_real_account(account_group)
                
                return {
                    'exists': True,
                    'account_number': str(account_info['account_number']),
                    'name': account_info['name'] or 'Unknown',
                    'first_name': account_info['FirstName'] or '',
                    'last_name': account_info['LastName'] or '',
                    'email': account_info['Email'] or '',
                    'balance': float(account_info['balance']),
                    'group': account_group,
                    'status': account_info['Status'] or '',
                    'country': account_info['Country'] or '',
                    'company': account_info['Company'] or '',
                    'leverage': account_info['leverage'],
                    'creation_date': account_info['creation_date'],
                    'is_real_account': is_real_account,  # NEW FIELD
                    'account_type': 'Real' if is_real_account else 'Demo'  # NEW FIELD
                }
            else:
                return {'exists': False}
                
        except ValueError:
            return {'exists': False, 'error': 'Invalid account number format'}
        except Exception as e:
            self.logger.error(f"Error verifying account {account_number}: {e}")
        return {'exists': False, 'error': str(e)}
    
    def _is_real_account(self, account_group):
        """Helper method to determine if account is real/live based on the group name."""
        if not account_group:
            return False
        
        account_group_lower = account_group.lower()
        
        # Check for demo indicators
        demo_indicators = ['demo', 'practice', 'test']
        if any(indicator in account_group_lower for indicator in demo_indicators):
            return False
        
        # Check for real indicators
        real_indicators = ['real', 'live', 'retail', 'vortex-retail']
        if any(indicator in account_group_lower for indicator in real_indicators):
            return True
        
        # If no clear indicators, assume demo for safety
        return False
    
    def get_account_stats(self):
        """Get overall account statistics."""
        query = """
        SELECT 
            COUNT(*) as total_accounts,
            COUNT(CASE WHEN COALESCE(Balance, 0) > 0 THEN 1 END) as funded_accounts,
            COUNT(CASE WHEN Status = 'active' THEN 1 END) as active_accounts,
            COUNT(CASE 
                WHEN Registration IS NOT NULL 
                AND Registration != '0000-00-00 00:00:00' 
                AND Registration > '1970-01-01 00:00:00' 
                THEN 1 
            END) as valid_registrations,
            AVG(COALESCE(Balance, 0)) as avg_balance,
            MAX(COALESCE(Balance, 0)) as max_balance,
            SUM(COALESCE(Balance, 0)) as total_balance
        FROM mt5_users
        """
        
        try:
            results = self.execute_query(query)
            if results and len(results) > 0:
                return results[0]
            return None
        except Exception as e:
            self.logger.error(f"Error getting account stats: {e}")
            return None
    
    def get_recent_registrations(self, days=7, limit=20):
        """Get recently registered accounts with proper date filtering."""
        # Use a safer approach that handles zero dates properly
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            CASE 
                WHEN Registration IS NULL OR Registration = '0000-00-00 00:00:00' THEN NULL
                ELSE Registration 
            END as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            CASE 
                WHEN Registration IS NULL OR Registration = '0000-00-00 00:00:00' THEN NULL
                ELSE DATEDIFF(NOW(), Registration)
            END as days_ago
        FROM mt5_users 
        WHERE Registration IS NOT NULL
        AND Registration != '0000-00-00 00:00:00'
        AND Registration > '1970-01-01 00:00:00'
        AND STR_TO_DATE(Registration, '%Y-%m-%d %H:%i:%s') >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY Registration DESC
        LIMIT %s
        """
        
        try:
            results = self.execute_query(query, (days, limit))
            if results:
                print(f"Found {len(results)} accounts registered in last {days} days")
                # Filter out any remaining problematic entries
                valid_results = []
                for result in results:
                    if result['registration_date'] and result['registration_date'] != '0000-00-00 00:00:00':
                        valid_results.append(result)
                return valid_results
            else:
                print(f"No accounts found in last {days} days")
                return []
        except Exception as e:
            self.logger.error(f"Error getting recent registrations: {e}")
            print(f"Error getting recent registrations: {e}")
            
            # Fallback query without date filtering
            try:
                fallback_query = """
                SELECT 
                    Login as account_number,
                    CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
                    Email,
                    CASE 
                        WHEN Registration IS NULL OR Registration = '0000-00-00 00:00:00' THEN 'Invalid Date'
                        ELSE Registration 
                    END as registration_date,
                    COALESCE(Balance, 0) as Balance,
                    `Group` as account_group,
                    Status,
                    Country,
                    999 as days_ago
                FROM mt5_users 
                WHERE Registration IS NOT NULL
                AND Registration != '0000-00-00 00:00:00'
                ORDER BY Login DESC
                LIMIT %s
                """
                
                fallback_results = self.execute_query(fallback_query, (limit,))
                print(f"Fallback query returned {len(fallback_results) if fallback_results else 0} results")
                return fallback_results or []
                
            except Exception as fallback_error:
                self.logger.error(f"Fallback query also failed: {fallback_error}")
                return []
    
    def get_table_structure(self):
        """Get the structure of the mt5_users table."""
        query = "DESCRIBE mt5_users"
        
        try:
            results = self.execute_query(query)
            return results
        except Exception as e:
            self.logger.error(f"Error getting table structure: {e}")
            return None
    
    def get_recent_accounts(self, days=7, limit=20):
        """Alternative method that completely avoids problematic date comparisons."""
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Registration as raw_registration,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country
        FROM mt5_users 
        ORDER BY Login DESC
        LIMIT %s
        """
        
        try:
            results = self.execute_query(query, (limit * 3,))  # Get more records to filter
            if not results:
                return []
            
            # Filter and process results in Python instead of SQL
            valid_results = []
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)
            
            for result in results:
                raw_date = result.get('raw_registration')
                if not raw_date or raw_date == '0000-00-00 00:00:00':
                    continue
                
                try:
                    # Try to parse the date
                    if isinstance(raw_date, str):
                        reg_date = datetime.strptime(raw_date, '%Y-%m-%d %H:%M:%S')
                    else:
                        reg_date = raw_date
                    
                    # Check if it's within our date range
                    if reg_date >= cutoff_date:
                        result['registration_date'] = reg_date.strftime('%Y-%m-%d %H:%M:%S')
                        result['days_ago'] = (datetime.now() - reg_date).days
                        valid_results.append(result)
                        
                        if len(valid_results) >= limit:
                            break
                            
                except (ValueError, TypeError) as date_error:
                    # Skip records with unparseable dates
                    continue
            
            return valid_results[:limit]
            
        except Exception as e:
            self.logger.error(f"Error in get_safe_recent_accounts: {e}")
            return []
    
    def get_recent_accounts_by_timestamp(self, days=7, limit=20):
        """Get recent accounts using the Timestamp column (Unix timestamp)."""
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
            DATEDIFF(NOW(), FROM_UNIXTIME(Timestamp)) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 0
        ORDER BY Timestamp DESC
        LIMIT %s
        """
        
        try:
            results = self.execute_query(query, (cutoff_timestamp, limit))
            return results or []
        except Exception as e:
            self.logger.error(f"Error getting recent accounts by timestamp: {e}")
            return []

    def get_recent_accounts_filetime(self, days=7, limit=20):
        """Get recent accounts using MT5's FILETIME timestamp format."""
        from datetime import datetime, timedelta
        
        # Calculate FILETIME for X days ago
        cutoff_date = datetime.now() - timedelta(days=days)
        # Convert to FILETIME: Unix timestamp to Windows FILETIME
        cutoff_filetime = int((cutoff_date.timestamp() * 10000000) + 116444736000000000)
        
        query = """
        SELECT 
            Login as account_number,
            CONCAT(COALESCE(FirstName, ''), ' ', COALESCE(LastName, '')) as name,
            Email,
            Timestamp,
            -- Convert FILETIME to readable datetime
            FROM_UNIXTIME((Timestamp - 116444736000000000) / 10000000) as registration_date,
            COALESCE(Balance, 0) as Balance,
            `Group` as account_group,
            Status,
            Country,
            -- Calculate days ago using FILETIME
            ROUND((UNIX_TIMESTAMP() * 10000000 + 116444736000000000 - Timestamp) / 864000000000) as days_ago
        FROM mt5_users 
        WHERE Timestamp > %s
        AND Timestamp > 116444736000000000
        ORDER BY Timestamp DESC
        LIMIT %s
        """
        
        try:
            results = self.execute_query(query, (cutoff_filetime, limit))
            return results or []
        except Exception as e:
            self.logger.error(f"Error getting recent accounts by FILETIME: {e}")
            return []
    def close(self):
        """Close database connection."""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection and self.connection.is_connected():
                self.connection.close()
                self.logger.info("MySQL connection closed")
        except Error as e:
            self.logger.error(f"Error closing connection: {e}")

# Global instance
mysql_db = None

def get_mysql_connection():
    """Get or create MySQL connection."""
    global mysql_db
    if mysql_db is None:
        mysql_db = MySQLManager()
    elif not mysql_db.is_connected():
        mysql_db.reconnect()
    return mysql_db