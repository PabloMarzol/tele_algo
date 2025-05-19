import time
import json
import logging
import os

from mt5_signal_executor import MT5SignalExecutor

## --------------------------------------------------------------------------------------- ##
## --------------------------------------------------------------------------------------- ##


class MultiAccountExecutor:
    """Executes trading signals across multiple MT5 accounts."""
    
    def __init__(self, account_configs=None):
        """Initialize with multiple account configurations."""
        self.logger = logging.getLogger('MultiAccountExecutor')
        self.accounts = []
        self.executors = {}
        self.initialized = False
        
        # Load default accounts if none provided
        if account_configs is None:
            account_configs = self._load_default_accounts()
        
        self.logger.info(f"Initializing MultiAccountExecutor with {len(account_configs)} account configuration(s)")
        
        # Initialize all account executors
        successful_initializations = 0
        for config in account_configs:
            account_name = config.get("name", f"Account_{config.get('username', 'unknown')}")
            enabled = config.get("enabled", True)
            
            # Log account configuration (without password)
            safe_config = config.copy()
            if "password" in safe_config:
                safe_config["password"] = "********"
            self.logger.info(f"Account config for {account_name}: {safe_config}")
            
            if not enabled:
                self.logger.info(f"Skipping disabled account: {account_name}")
                continue
                
            # Create executor for this account
            executor = MT5SignalExecutor(
                username=config["username"],
                password=config["password"],
                server=config["server"],
                risk_percent=config.get("risk_percent", 1.0),
                terminal_path=config.get("terminal_path")
            )
            
            # Store the account and executor
            self.accounts.append(account_name)
            self.executors[account_name] = {
                "config": config,
                "executor": executor,
                "status": "initialized" if executor.initialized else "failed"
            }
            
            if executor.initialized:
                successful_initializations += 1
                self.logger.info(f"Successfully initialized executor for account: {account_name}")
            else:
                self.logger.error(f"Failed to initialize executor for account: {account_name}")
        
        # Set initialized status based on having at least one successful account connection
        self.initialized = successful_initializations > 0
        self.logger.info(f"MultiAccountExecutor initialized with {successful_initializations}/{len(account_configs)} accounts")
    
    def _load_default_accounts(self):
        """Load account configurations from environment or config file."""
        configs = []
        
        # Try to load from config file first
        try:
            config_path = os.getenv("MT5_ACCOUNTS_CONFIG", "./bot_data/mt5_accounts.json")
            self.logger.info(f"Looking for accounts configuration at: {config_path}")
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    configs = json.load(f)
                    self.logger.info(f"Loaded {len(configs)} account(s) from configuration file")
                    return configs
        except Exception as e:
            self.logger.error(f"Error loading account configs from file: {e}")
        
        # Fall back to environment variables if no config file found
        primary_username = os.getenv("MT5_USERNAME")
        primary_password = os.getenv("MT5_PASSWORD")
        primary_server = os.getenv("MT5_SERVER")
        primary_terminal = os.getenv("MT5_TERMINAL_PATH")
        
        if primary_username and primary_password and primary_server:
            configs.append({
                "name": "Primary",
                "username": primary_username,
                "password": primary_password,
                "server": primary_server,
                "risk_percent": float(os.getenv("MT5_RISK_PERCENT", "1.0")),
                "terminal_path": primary_terminal,
                "enabled": True
            })
            self.logger.info("Loaded primary account from environment variables")
        
        # Check if additional accounts are defined with numbered environment variables
        for i in range(2, 6):  # Support up to 5 accounts
            username = os.getenv(f"MT5_USERNAME_{i}")
            password = os.getenv(f"MT5_PASSWORD_{i}")
            server = os.getenv(f"MT5_SERVER_{i}")
            terminal = os.getenv(f"MT5_TERMINAL_PATH_{i}")
            
            if username and password and server:
                configs.append({
                    "name": f"Account {i}",
                    "username": username,
                    "password": password,
                    "server": server,
                    "risk_percent": float(os.getenv(f"MT5_RISK_PERCENT_{i}", "1.0")),
                    "terminal_path": terminal,
                    "enabled": True
                })
                self.logger.info(f"Loaded account {i} from environment variables")
        
        return configs
    
    def apply_trailing_stop(self, signal_id=None, trailing_percent=None, min_profit_percent=None):
        """
        Apply trailing stop to all accounts.
        
        Args:
            signal_id (str, optional): Specific signal ID to apply trailing stop to
            trailing_percent (float, optional): Distance to maintain between price and stop loss in percent
            min_profit_percent (float, optional): Minimum profit in percent before trailing activates
            
        Returns:
            dict: Results for each account
        """
        results = {
            "success": True,
            "accounts_updated": 0,
            "total_accounts": len(self.accounts),
            "details": {}
        }
        
        for account_name in self.accounts:
            account_info = self.executors[account_name]
            executor = account_info["executor"]
            
            # Skip accounts that aren't initialized
            if not executor.initialized:
                results["details"][account_name] = {
                    "success": False,
                    "error": "Executor not initialized"
                }
                continue
                
            try:
                # Apply trailing stop on this account
                result = executor.apply_trailing_stop(
                    signal_id=signal_id,
                    trailing_pips=trailing_percent,
                    min_profit_pips=min_profit_percent
                )
                
                # Store the result
                results["details"][account_name] = result
                
                if result["success"] and result.get("positions_updated", 0) > 0:
                    results["accounts_updated"] += 1
                    
            except Exception as e:
                self.logger.error(f"Error applying trailing stop on account {account_name}: {e}")
                results["details"][account_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def execute_signal(self, signal_data):
        """Execute signal across all enabled accounts with account-specific signal IDs."""
        results = {
            "success": True,
            "accounts_executed": 0,
            "total_accounts": len(self.accounts),
            "details": {}
        }
        
        for account_name in self.accounts:
            account_info = self.executors[account_name]
            executor = account_info["executor"]
            
            self.logger.info(f"Executing signal on account: {account_name}")
            
            try:
                # Create a copy of signal data with account-specific ID
                account_signal_data = signal_data.copy()
                original_id = account_signal_data.get("signal_id", "unknown")
                
                # Create a unique signal ID for this account
                account_signal_data["signal_id"] = f"{original_id}_{account_name}"
                
                self.logger.info(f"Using account-specific signal ID: {account_signal_data['signal_id']}")
                
                # Execute the signal on this account
                result = executor.execute_signal(account_signal_data)
                
                # Store the result
                results["details"][account_name] = result
                
                if result["success"]:
                    results["accounts_executed"] += 1
                    account_info["status"] = "active"
                    
                    # Wait a short time between executions
                    time.sleep(1)
                else:
                    self.logger.error(f"Failed to execute signal on account {account_name}: {result.get('error', 'Unknown error')}")
                    account_info["status"] = "error"
                    
            except Exception as e:
                self.logger.error(f"Error executing signal on account {account_name}: {e}")
                results["details"][account_name] = {
                    "success": False,
                    "error": str(e)
                }
                account_info["status"] = "error"
        
        # Determine overall success
        if results["accounts_executed"] == 0 and results["total_accounts"] > 0:
            results["success"] = False
            results["error"] = "Failed to execute signal on any account"
        
        return results
    
    def apply_trailing_stop(self, signal_id=None, trailing_percent=None, min_profit_percent=None):
        """Apply trailing stop to all accounts.
        
        Args:
            signal_id (str, optional): Specific signal ID to apply trailing stop to
            trailing_percent (float, optional): Distance to maintain between price and stop loss in percent
            min_profit_percent (float, optional): Minimum profit in percent before trailing activates
            
        Returns:
            dict: Results for each account
        """
        results = {
            "success": True,
            "accounts_updated": 0,
            "total_accounts": len(self.accounts),
            "details": {}
        }
        
        for account_name in self.accounts:
            account_info = self.executors[account_name]
            executor = account_info["executor"]
            
            try:
                # Apply trailing stop on this account
                result = executor.apply_trailing_stop(
                    signal_id=signal_id,
                    trailing_percent=trailing_percent,
                    min_profit_percent=min_profit_percent
                )
                
                # Store the result
                results["details"][account_name] = result
                
                if result["success"] and result.get("positions_updated", 0) > 0:
                    results["accounts_updated"] += 1
                    
            except Exception as e:
                self.logger.error(f"Error applying trailing stop on account {account_name}: {e}")
                results["details"][account_name] = {
                    "success": False,
                    "error": str(e)
                }
        
        return results
    
    def get_account_statuses(self):
        """Get status of all accounts.
        
        Returns:
            dict: Status information for each account
        """
        statuses = {}
        
        for account_name in self.accounts:
            account_info = self.executors[account_name]
            executor = account_info["executor"]
            
            try:
                # Get account info
                account_data = executor.get_account_info()
                
                if account_data["success"]:
                    statuses[account_name] = {
                        "status": account_info["status"],
                        "balance": account_data["balance"],
                        "equity": account_data["equity"],
                        "margin_level": account_data["margin_level"],
                        "connected": executor.connected
                    }
                else:
                    statuses[account_name] = {
                        "status": "error",
                        "error": account_data.get("error", "Unknown error"),
                        "connected": executor.connected
                    }
                    
            except Exception as e:
                statuses[account_name] = {
                    "status": "error",
                    "error": str(e),
                    "connected": False
                }
        
        return statuses
    
    def cleanup(self):
        """Clean up all MT5 connections."""
        for account_name in self.accounts:
            try:
                executor = self.executors[account_name]["executor"]
                self.logger.info(f"Cleaning up connection for account: {account_name}")
                executor.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up account {account_name}: {e}")