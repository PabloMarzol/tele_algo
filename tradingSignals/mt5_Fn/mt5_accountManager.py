import time
import json
import logging
import os

from datetime import datetime
from tradingSignals.mt5_Fn.mt5_signal_executor import MT5SignalExecutor

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
                risk_percent=config.get("risk_percent", 0.5),
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
    
    def generate_daily_stats(self):
        """
        Generate consolidated daily statistics across all accounts.
        Leverages individual account stats and aggregates them.
        """
        if not self.initialized:
            return {"success": False, "error": "MultiAccountExecutor not initialized"}
        
        try:
            # Initialize consolidated stats
            consolidated_stats = {
                "date": datetime.now().date().strftime("%Y-%m-%d"),
                "signals_executed": 0,
                "positions_opened": 0,
                "positions_closed": 0,
                "wins": 0,
                "losses": 0,
                "total_profit": 0.0,
                "total_pips": 0.0,
                "win_rate": 0.0,
                "return_percentage": 0.0,
                "active_positions": 0,
                "symbols_traded": set(),
                "signal_details": [],
                "account_breakdown": {},
                "total_accounts": len(self.accounts),
                "successful_accounts": 0,
                "total_balance": 0.0
            }
            
            # Collect stats from each account using their individual generators
            for account_name in self.accounts:
                account_info = self.executors[account_name]
                executor = account_info["executor"]
                
                if not executor.initialized:
                    consolidated_stats["account_breakdown"][account_name] = {
                        "success": False,
                        "error": "Account not initialized"
                    }
                    continue
                
                try:
                    # USE THE EXISTING SINGLE-ACCOUNT FUNCTION
                    account_stats_result = executor.generate_daily_stats()
                    
                    if account_stats_result["success"]:
                        account_stats = account_stats_result["stats"]
                        consolidated_stats["successful_accounts"] += 1
                        
                        # Aggregate the stats
                        self._aggregate_account_stats(consolidated_stats, account_stats, account_name)
                        
                        # Get account balance for breakdown
                        account_info_result = executor.get_account_info()
                        if account_info_result["success"]:
                            self._add_account_breakdown(consolidated_stats, account_stats, 
                                                     account_name, account_info_result["balance"])
                        
                    else:
                        consolidated_stats["account_breakdown"][account_name] = {
                            "success": False,
                            "error": account_stats_result.get("error", "Failed to generate stats")
                        }
                        
                except Exception as e:
                    consolidated_stats["account_breakdown"][account_name] = {
                        "success": False,
                        "error": str(e)
                    }
            
            # Calculate final consolidated metrics
            self._calculate_consolidated_metrics(consolidated_stats)
            
            return {"success": True, "stats": consolidated_stats}
            
        except Exception as e:
            self.logger.error(f"Error generating consolidated daily stats: {e}")
            return {"success": False, "error": str(e)}
    
    def _aggregate_account_stats(self, consolidated_stats, account_stats, account_name):
        """Helper method to aggregate individual account stats"""
        consolidated_stats["signals_executed"] += account_stats["signals_executed"]
        consolidated_stats["positions_opened"] += account_stats["positions_opened"]
        consolidated_stats["positions_closed"] += account_stats["positions_closed"]
        consolidated_stats["wins"] += account_stats["wins"]
        consolidated_stats["losses"] += account_stats["losses"]
        consolidated_stats["total_profit"] += account_stats["total_profit"]
        consolidated_stats["total_pips"] += account_stats["total_pips"]
        consolidated_stats["active_positions"] += account_stats["active_positions"]
        consolidated_stats["symbols_traded"].update(account_stats["symbols_traded"])
        
        # Add signal details with account info
        for detail in account_stats["signal_details"]:
            detail_copy = detail.copy()
            detail_copy["account"] = account_name
            consolidated_stats["signal_details"].append(detail_copy)
    
    def _add_account_breakdown(self, consolidated_stats, account_stats, account_name, balance):
        """Helper method to add account breakdown info"""
        consolidated_stats["total_balance"] += balance
        account_return_pct = (account_stats["total_profit"] / balance * 100) if balance > 0 else 0
        
        consolidated_stats["account_breakdown"][account_name] = {
            "success": True,
            "balance": balance,
            "profit": account_stats["total_profit"],
            "return_pct": account_return_pct,
            "wins": account_stats["wins"],
            "losses": account_stats["losses"],
            "win_rate": account_stats["win_rate"],
            "active_positions": account_stats["active_positions"],
            "symbols_traded": account_stats["symbols_traded"]
        }
    
    def _calculate_consolidated_metrics(self, consolidated_stats):
        """Helper method to calculate final consolidated metrics"""
        total_closed = consolidated_stats["wins"] + consolidated_stats["losses"]
        if total_closed > 0:
            consolidated_stats["win_rate"] = (consolidated_stats["wins"] / total_closed) * 100
        
        if consolidated_stats["total_balance"] > 0:
            consolidated_stats["return_percentage"] = (consolidated_stats["total_profit"] / consolidated_stats["total_balance"]) * 100
        
        consolidated_stats["symbols_traded"] = list(consolidated_stats["symbols_traded"])
    
    def generate_signal_breakdown_stats_multi_account(self, days_back=1):
        """
        Generate signal breakdown statistics across all accounts.
        
        Args:
            days_back (int): Number of days to look back
            
        Returns:
            dict: Multi-account signal breakdown statistics
        """
        if not self.initialized:
            return {"success": False, "error": "MultiAccountExecutor not initialized"}
        
        try:
            # Collect stats from all accounts
            all_signal_stats = {}
            successful_accounts = 0
            
            for account_name in self.accounts:
                account_info = self.executors[account_name]
                executor = account_info["executor"]
                
                if not executor.initialized:
                    continue
                
                # Get signal breakdown stats from this account
                account_result = executor.generate_signal_stats(days_back)
                
                if account_result["success"]:
                    successful_accounts += 1
                    account_breakdown = account_result["stats"]["signal_breakdown"]
                    
                    # Merge with overall stats
                    for signal_key, signal_stats in account_breakdown.items():
                        if signal_key not in all_signal_stats:
                            # First time seeing this signal
                            all_signal_stats[signal_key] = signal_stats.copy()
                            all_signal_stats[signal_key]['accounts'] = {account_name: signal_stats}
                        else:
                            # Aggregate with existing signal stats
                            existing_stats = all_signal_stats[signal_key]
                            existing_stats['total_trades'] += signal_stats['total_trades']
                            existing_stats['active_positions'] += signal_stats['active_positions']
                            existing_stats['wins'] += signal_stats['wins']
                            existing_stats['losses'] += signal_stats['losses']
                            existing_stats['total_profit'] += signal_stats['total_profit']
                            existing_stats['total_pips'] += signal_stats['total_pips']
                            existing_stats['orders_placed'] += signal_stats['orders_placed']
                            
                            # Store per-account breakdown
                            if 'accounts' not in existing_stats:
                                existing_stats['accounts'] = {}
                            existing_stats['accounts'][account_name] = signal_stats
                            
                            # Recalculate averages
                            total_closed = existing_stats['wins'] + existing_stats['losses']
                            if total_closed > 0:
                                existing_stats['win_rate'] = (existing_stats['wins'] / total_closed) * 100
                                existing_stats['avg_profit_per_trade'] = existing_stats['total_profit'] / total_closed
                                existing_stats['avg_pips_per_trade'] = existing_stats['total_pips'] / total_closed
            
            # Calculate overall metrics
            total_signals = len(all_signal_stats)
            total_profit = sum(stats['total_profit'] for stats in all_signal_stats.values())
            total_trades = sum(stats['total_trades'] for stats in all_signal_stats.values())
            
            return {
                "success": True,
                "stats": {
                    "date_range": f"Last {days_back} day(s)",
                    "accounts_analyzed": successful_accounts,
                    "total_signals_executed": total_signals,
                    "total_trades_all_signals": total_trades,
                    "total_profit_all_signals": total_profit,
                    "signal_breakdown": all_signal_stats
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error generating multi-account signal breakdown stats: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        """Clean up all MT5 connections."""
        for account_name in self.accounts:
            try:
                executor = self.executors[account_name]["executor"]
                self.logger.info(f"Cleaning up connection for account: {account_name}")
                executor.cleanup()
            except Exception as e:
                self.logger.error(f"Error cleaning up account {account_name}: {e}")