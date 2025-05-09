import MetaTrader5 as mt5
import logging
import os
from datetime import datetime
import time
import polars as pl
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MT5SignalExecutor:
    """Executes trading signals on the MetaTrader 5 platform."""
    
    def __init__(self, username=None, password=None, server=None, risk_percent=1.0):
        """Initialize the MT5 signal executor."""
        self.logger = logging.getLogger('MT5SignalExecutor')
        self.connected = False
        self.risk_percent = risk_percent  # Risk per trade (percentage of account balance)
        self.executed_signals = {}  # Track signals that have been executed
        self.initialized = False
        
        # Connect to MT5
        self.initialize_mt5(username, password, server)
        
        # Parameters for signal execution
        self.max_spread_multiplier = 1.5  # Max allowed spread as multiplier of average
        self.slippage_pips = 3  # Allowed slippage in pips
        self.use_limit_orders = True  # Whether to use limit orders (True) or market orders (False)
        self.retry_attempts = 3  # Number of retries for failed orders
        self.retry_delay = 5  # Delay between retries in seconds
        
        # Default lot sizing by symbol
        self.default_lot_sizes = {
            "EURUSD": 1.5,
            "GBPUSD": 1.5,
            "AUDUSD": 1.5,
            "USDCAD": 1.5,
            "XAUUSD": 0.1,
            "NAS100": 1.0,
            "US30": 1.0,
            "US500": 1.0,
            "FRA40": 1.0,
            "UK100": 1.0
        }
    
    def initialize_mt5(self, username=None, password=None, server=None):
        """Connect to MetaTrader5 terminal."""
        try:
            self.logger.info("Initializing MT5 connection for trade execution...")
            
            # Initialize MT5 if not already initialized
            if not mt5.initialize():
                self.logger.error(f"❌ MT5 initialization failed: Error code {mt5.last_error()}")
                return False
            
            self.logger.info("✅ MT5 initialized successfully!")
            
            # Login if credentials provided
            if username and password and server:
                try:
                    # Convert username to integer if it's a number
                    if isinstance(username, str) and username.isdigit():
                        username = int(username)
                    
                    login_result = mt5.login(
                        login=username, 
                        password=str(password),
                        server=str(server)
                    )
                    
                    if not login_result:
                        error_code = mt5.last_error()
                        self.logger.error(f"❌ MT5 login failed: Error code {error_code}")
                        return False
                    
                    # Get account info to confirm login
                    account_info = mt5.account_info()
                    if account_info:
                        self.logger.info(f"✅ Successfully logged in as {account_info.login} on {account_info.server}")
                        self.logger.info(f"Account: {account_info.name}, Balance: {account_info.balance} {account_info.currency}")
                        self.connected = True
                        self.initialized = True
                        return True
                    else:
                        self.logger.error("❌ MT5 login failed: Could not get account info")
                        return False
                except Exception as e:
                    self.logger.error(f"❌ MT5 login error: {e}")
                    return False
            else:
                self.logger.warning("⚠️ No login credentials provided - using terminal with current connection")
                self.connected = True
                self.initialized = True
                return True
        
        except Exception as e:
            self.logger.error(f"❌ MT5 connection error: {e}")
            return False
    
    def execute_signal(self, signal_data):
        """
        Execute a trading signal on MT5 with multiple scaled entries.
        
        Args:
            signal_data (dict): Signal data including symbol, direction, entry range, stop loss, take profits
            
        Returns:
            dict: Result of the execution with order details or error information
        """
        if not self.connected or not self.initialized:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        signal_id = signal_data.get("signal_id", f"{signal_data['symbol']}_{signal_data['direction']}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Check if signal already executed
        if signal_id in self.executed_signals:
            self.logger.info(f"Signal {signal_id} already executed")
            return {"success": False, "error": "Signal already executed", "order_details": self.executed_signals[signal_id]}
        
        try:
            # Extract signal details
            symbol = signal_data["symbol"]
            direction = signal_data["direction"]
            entry_low = float(signal_data.get("entry_range_low", 0))
            entry_high = float(signal_data.get("entry_range_high", 0))
            stop_low = float(signal_data.get("stop_range_low", 0))
            stop_high = float(signal_data.get("stop_range_high", 0))
            
            # Extract take profit levels
            take_profits = []
            for i in range(1, 4):
                tp_key = f"take_profit{i}" if i > 1 else "take_profit"
                if tp_key in signal_data and signal_data[tp_key]:
                    tp_value = float(signal_data[tp_key])
                    take_profits.append(tp_value)
            
            # Ensure we have at least one take profit
            if not take_profits:
                self.logger.error(f"No take profit levels found for signal {signal_id}")
                return {"success": False, "error": "No take profit levels found"}
            
            # Check if symbol is valid in MT5
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                self.logger.error(f"Symbol {symbol} not found in MT5!")
                return {"success": False, "error": f"Symbol {symbol} not found in MT5"}

            if not symbol_info.visible:
                self.logger.warning(f"Symbol {symbol} is not visible, trying to select it")
                if not mt5.symbol_select(symbol, True):
                    self.logger.error(f"Failed to select symbol {symbol}")
                    return {"success": False, "error": f"Failed to select symbol {symbol}"}
            
            # Log account trading status
            account_info = mt5.account_info()
            if account_info:
                self.logger.info(f"Account trade mode: {account_info.trade_mode}, Margin level: {account_info.margin_level}%")
            
            # Determine entry points - we'll use 3 entry points spread across the range
            num_entries = 3
            
            # Calculate step size between entries
            entry_step = (entry_high - entry_low) / (num_entries - 1) if num_entries > 1 else 0
            
            # Create list of entry prices
            entry_prices = []
            for i in range(num_entries):
                entry_price = entry_low + (entry_step * i)
                entry_prices.append(entry_price)
            
            # Calculate lot size based on risk management
            # We'll calculate the total position size and then divide it among our entries
            total_lot_size = self.calculate_position_size(symbol, (entry_low + entry_high) / 2, (stop_low + stop_high) / 2, direction)
            
            # Divide the total lot size among our entries
            # Use weighting: more lots at better prices (lower for buy, higher for sell)
            lot_weights = [1.5, 1.2, 1.0] if direction == "BUY" else [1.0, 1.2, 1.5]  # More weight to better prices
            
            # Get the minimum lot size and step
            min_lot = symbol_info.volume_min
            lot_step = symbol_info.volume_step
            
            # Calculate weighted lot sizes and ensure they meet minimums
            lot_sizes = []
            remaining_lots = total_lot_size
            
            for i in range(num_entries - 1):  # Process all except the last one
                # Calculate weighted lot size
                lot_size = total_lot_size * lot_weights[i]
                
                # Round to nearest step
                lot_size = round(lot_size / lot_step) * lot_step
                
                # Ensure minimum lot size
                if lot_size < min_lot:
                    lot_size = min_lot
                    
                # Don't allow lot size to exceed remaining lots
                if lot_size > remaining_lots:
                    lot_size = remaining_lots
                
                lot_sizes.append(lot_size)
                remaining_lots -= lot_size
            
            # Last entry gets any remaining lots
            last_lot = max(remaining_lots, min_lot)
            last_lot = round(last_lot / lot_step) * lot_step  # Ensure it matches step size
            lot_sizes.append(last_lot)
            
            # Log the execution plan
            self.logger.info(f"Executing {signal_id} with {num_entries} entries:")
            for i in range(num_entries):
                self.logger.info(f"Entry {i+1}: Price {entry_prices[i]:.5f}, Lot Size {lot_sizes[i]:.2f}")
            
            # Select the order type based on direction
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
            
            # Execute multiple entry orders
            executed_orders = []
            
            # Create a safe comment
            safe_comment = f"VFX{direction}"
            
            for i in range(num_entries):
                # For each entry point, we'll place a limit order
                entry_price = entry_prices[i]
                lot_size = lot_sizes[i]
                
                # Calculate stop loss for this entry - use proportional position in the range
                position_pct = i / (num_entries - 1) if num_entries > 1 else 0
                stop_loss = stop_low + (stop_high - stop_low) * position_pct
                
                # Prepare the order request
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": lot_size,
                    "type": order_type,
                    "price": entry_price,
                    "sl": stop_loss,
                    "tp": take_profits[0],  # Set first take profit level
                    "deviation": self.slippage_pips,
                    "magic": 123456 + i,  # Unique magic number for each entry
                    "comment": f"{safe_comment}{i+1}",
                    "type_time": mt5.ORDER_TIME_GTC,  # Good till canceled
                    "type_filling": mt5.ORDER_FILLING_IOC,  # Immediate or cancel
                }
                
                # Log the order details
                self.logger.info(f"Sending order {i+1} for {symbol} {direction} at {entry_price:.5f}")
                
                # Send the order with retries
                success = False
                order_id = None
                
                for attempt in range(self.retry_attempts):
                    try:
                        result = mt5.order_send(request)
                        
                        # Check if result is None (API failure)
                        if result is None:
                            error_code = mt5.last_error()
                            self.logger.warning(f"Order {i+1} returned None with error code: {error_code}. Attempt {attempt+1}/{self.retry_attempts}")
                            
                            # Handle specific errors
                            if str(error_code) == "10014":  # Invalid volume
                                if lot_size > min_lot:
                                    # Try with minimum lot size
                                    lot_size = min_lot
                                    request["volume"] = min_lot
                                    self.logger.info(f"Retrying order {i+1} with minimum lot size: {min_lot}")
                                    continue
                                else:
                                    # We're already at minimum lot size, so this won't work
                                    break
                            
                            if attempt < self.retry_attempts - 1:
                                time.sleep(self.retry_delay)
                                continue
                            else:
                                break
                        
                        # Now we know result is not None, check retcode
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            self.logger.info(f"✅ Order {i+1} executed successfully: {result.order}")
                            success = True
                            order_id = result.order
                            break
                        else:
                            # Handle specific error codes
                            if result.retcode == 10014:  # Invalid volume error
                                self.logger.warning(f"Invalid volume error for order {i+1}. Lot size was {lot_size}.")
                                
                                if lot_size > min_lot:
                                    # Try with minimum lot size
                                    lot_size = min_lot
                                    request["volume"] = min_lot
                                    self.logger.info(f"Retrying order {i+1} with minimum lot size: {min_lot}")
                                    continue
                                else:
                                    # We're already at minimum lot size, so this won't work
                                    break
                                    
                            self.logger.warning(f"Order {i+1} failed with error code: {result.retcode}. Attempt {attempt+1}/{self.retry_attempts}")
                            if attempt < self.retry_attempts - 1:
                                time.sleep(self.retry_delay)
                            else:
                                break
                    except Exception as e:
                        self.logger.warning(f"Exception during order_send for order {i+1}: {e}. Attempt {attempt+1}/{self.retry_attempts}")
                        if attempt < self.retry_attempts - 1:
                            time.sleep(self.retry_delay)
                        else:
                            break
                
                # Record the order result
                if success and order_id:
                    executed_orders.append({
                        "order_id": order_id,
                        "entry_price": entry_price,
                        "stop_loss": stop_loss,
                        "lot_size": lot_size,
                        "take_profit": take_profits[0]
                    })
                    
                    # If there are additional take profit levels, set them for this order
                    if len(take_profits) > 1:
                        self.set_partial_take_profits(order_id, symbol, direction, lot_size, take_profits)
            
            # Check if any orders were executed successfully
            if executed_orders:
                self.logger.info(f"Successfully executed {len(executed_orders)}/{num_entries} orders for signal {signal_id}")
                
                # Store the executed signal with all orders
                self.executed_signals[signal_id] = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_range": [entry_low, entry_high],
                    "stop_range": [stop_low, stop_high],
                    "take_profits": take_profits,
                    "orders": executed_orders,
                    "execution_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                return {
                    "success": True,
                    "order_count": len(executed_orders),
                    "orders": executed_orders,
                    "entry_prices": [order["entry_price"] for order in executed_orders],
                    "stop_losses": [order["stop_loss"] for order in executed_orders],
                    "take_profits": take_profits,
                    "lot_sizes": [order["lot_size"] for order in executed_orders],
                    "total_lot_size": sum(order["lot_size"] for order in executed_orders)
                }
            else:
                self.logger.error(f"❌ Failed to execute any orders for signal {signal_id}")
                return {"success": False, "error": "Failed to execute any orders"}
            
        except Exception as e:
            self.logger.error(f"Error executing signal: {e}")
            return {"success": False, "error": str(e)}
    
    def calculate_position_size(self, symbol, entry_price, stop_loss, direction):
        """
        Calculate position size based on risk management rules.
        
        Args:
            symbol (str): Trading symbol
            entry_price (float): Entry price
            stop_loss (float): Stop loss price
            direction (str): Trade direction (BUY/SELL)
            
        Returns:
            float: Position size in lots
        """
        try:
            # Get account information
            account_info = mt5.account_info()
            if not account_info:
                self.logger.error("Failed to get account info")
                return self.default_lot_sizes.get(symbol, 0.1)
            
            account_balance = account_info.balance
            
            # Calculate risk amount
            risk_amount = account_balance * (self.risk_percent / 100)
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return self.default_lot_sizes.get(symbol, 0.1)
            
            # Log detailed symbol info for debugging
            self.logger.info(f"Symbol info for {symbol}: min_lot={symbol_info.volume_min}, max_lot={symbol_info.volume_max}, step={symbol_info.volume_step}")
            
            # Calculate stop loss distance in pips
            if direction == "BUY":
                sl_distance = abs(entry_price - stop_loss)
            else:
                sl_distance = abs(stop_loss - entry_price)
                
            # Convert to pips based on symbol digits
            point = symbol_info.point
            digits = symbol_info.digits
            
            # For Forex, 1 pip is usually 0.0001 for 4-digit symbols, 0.00001 for 5-digit
            if digits == 5 or digits == 3:  # 5-digit Forex or 3-digit indices/commodities
                pip_size = point * 10
            else:  # Standard 4-digit Forex or 2-digit indices
                pip_size = point
                
            pip_distance = sl_distance / pip_size
            
            self.logger.info(f"SL distance for {symbol}: {sl_distance:.5f} ({pip_distance:.1f} pips)")
            
            # Calculate pip value (approximate - depends on account currency)
            # For major Forex pairs with USD as quote currency
            lot_size = 0.1  # Start with minimum standard lot
            
            if "USD" in symbol[-3:]:  # If USD is the quote currency
                pip_value = symbol_info.trade_tick_value * (pip_size / point)
            else:
                # For other symbols, use a simpler approximation
                pip_value = symbol_info.trade_tick_value
            
            # Calculate lot size based on risk
            if pip_distance > 0 and pip_value > 0:
                lot_size = risk_amount / (pip_distance * pip_value)
                self.logger.info(f"Calculated raw lot size for {symbol}: {lot_size:.2f} (risk=${risk_amount:.2f}, pip_value=${pip_value:.2f})")
                
                # Ensure lot size matches symbol's step size
                step = symbol_info.volume_step
                lot_size = round(lot_size / step) * step
                
                # Ensure lot size is within min and max limits
                min_lot = symbol_info.volume_min
                max_lot = symbol_info.volume_max
                
                if lot_size < min_lot:
                    self.logger.info(f"Increasing lot size to minimum: {min_lot}")
                    lot_size = min_lot
                    
                if lot_size > max_lot:
                    self.logger.info(f"Reducing lot size to maximum: {max_lot}")
                    lot_size = max_lot
                    
                # Double-check lot size is valid
                if lot_size % step != 0:
                    # Adjust to nearest valid step
                    lot_size = round(lot_size / step) * step
                    self.logger.info(f"Adjusted lot size to match step size: {lot_size}")
                    
                # For some brokers/accounts, test if the lot size is valid
                # by checking if it's between min and max, and a multiple of step
                is_valid = (min_lot <= lot_size <= max_lot) and (abs(lot_size % step) < 0.0001)
                if not is_valid:
                    self.logger.warning(f"Calculated lot size {lot_size} appears invalid! Falling back to default.")
                    return self.default_lot_sizes.get(symbol, min_lot)
                    
                return lot_size
            else:
                self.logger.warning(f"Invalid stop loss distance or pip value for {symbol}")
                return self.default_lot_sizes.get(symbol, 0.1)
                
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return self.default_lot_sizes.get(symbol, 0.1)
    
    def set_partial_take_profits(self, order_id, symbol, direction, lot_size, take_profits):
        """
        Set partial take profit orders for a position.
        
        Args:
            order_id (int): The ID of the original order
            symbol (str): Trading symbol
            direction (str): Trade direction (BUY/SELL)
            lot_size (float): Total position size
            take_profits (list): List of take profit levels
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Skip if there's only one take profit level (already set in the main order)
            if len(take_profits) <= 1:
                return True
            
            # Calculate partial lot sizes (dividing total lots by number of TPs)
            num_tps = len(take_profits)
            partial_lot = round(lot_size / num_tps, 2)
            
            # Ensure minimum lot size
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return False
                
            min_lot = symbol_info.volume_min
            if partial_lot < min_lot:
                partial_lot = min_lot
            
            # We've already set TP1 in the main order, so we'll set TP2 and beyond
            for i in range(1, len(take_profits)):
                tp_price = take_profits[i]
                
                # Determine order type based on direction
                order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "SELL" else mt5.ORDER_TYPE_SELL_LIMIT
                
                # This is a pending order that will trigger when the price reaches the TP level
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": partial_lot,
                    "type": order_type,
                    "price": tp_price,
                    "deviation": self.slippage_pips,
                    "magic": 123456 + i,  # Use different magic number for each TP
                    "comment": f"TP{i+1} for Order {order_id}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                # Send the order
                result = mt5.order_send(request)
                if result.retcode != mt5.TRADE_RETCODE_DONE:
                    self.logger.error(f"Failed to set TP{i+1} with error code: {result.retcode}")
            
            return True
                
        except Exception as e:
            self.logger.error(f"Error setting partial take profits: {e}")
            return False
    
    def check_signal_status(self, signal_id):
        """
        Check the status of an executed signal.
        
        Args:
            signal_id (str): ID of the signal to check
            
        Returns:
            dict: Current status of the signal
        """
        if not self.connected:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        if signal_id not in self.executed_signals:
            return {"success": False, "error": "Signal not found"}
        
        try:
            signal_info = self.executed_signals[signal_id]
            order_id = signal_info["order_id"]
            symbol = signal_info["symbol"]
            
            # Check if the position is still open
            positions = mt5.positions_get(symbol=symbol)
            if positions:
                for position in positions:
                    if position.ticket == order_id or position.magic == 123456:
                        # Position is still open
                        current_price = mt5.symbol_info_tick(symbol).bid if position.type == 0 else mt5.symbol_info_tick(symbol).ask
                        
                        # Calculate profit
                        profit = position.profit
                        profit_pips = position.profit / position.volume
                        
                        return {
                            "success": True,
                            "status": "open",
                            "symbol": symbol,
                            "direction": "BUY" if position.type == 0 else "SELL",
                            "entry_price": position.price_open,
                            "current_price": current_price,
                            "profit": profit,
                            "profit_pips": profit_pips,
                            "volume": position.volume
                        }
            
            # Check if the position is in history (closed)
            history_orders = mt5.history_orders_get(ticket=order_id)
            if history_orders:
                order = history_orders[0]
                
                # Check if the order was executed and closed
                if order.state == mt5.ORDER_STATE_FILLED:
                    history_deals = mt5.history_deals_get(position=order.position_id)
                    
                    if history_deals:
                        total_profit = sum(deal.profit for deal in history_deals)
                        exit_price = history_deals[-1].price
                        
                        return {
                            "success": True,
                            "status": "closed",
                            "symbol": symbol,
                            "direction": "BUY" if order.type == 0 else "SELL",
                            "entry_price": order.price_open,
                            "exit_price": exit_price,
                            "profit": total_profit,
                            "close_time": history_deals[-1].time
                        }
            
            # If we get here, the position is neither open nor closed
            return {
                "success": False,
                "error": "Position not found",
                "signal_info": signal_info
            }
            
        except Exception as e:
            self.logger.error(f"Error checking signal status: {e}")
            return {"success": False, "error": str(e)}
    
    def close_position(self, signal_id, partial_close=False, close_percent=50):
        """
        Close a position manually.
        
        Args:
            signal_id (str): ID of the signal to close
            partial_close (bool): Whether to close only part of the position
            close_percent (float): Percentage of the position to close (if partial_close is True)
            
        Returns:
            dict: Result of the close operation
        """
        if not self.connected:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        if signal_id not in self.executed_signals:
            return {"success": False, "error": "Signal not found"}
        
        try:
            signal_info = self.executed_signals[signal_id]
            order_id = signal_info["order_id"]
            symbol = signal_info["symbol"]
            
            # Check if the position is still open
            positions = mt5.positions_get(symbol=symbol)
            position = None
            
            if positions:
                for pos in positions:
                    if pos.ticket == order_id or pos.magic == 123456:
                        position = pos
                        break
            
            if not position:
                return {"success": False, "error": "Position not found"}
            
            # Calculate volume to close
            close_volume = position.volume
            if partial_close:
                close_volume = round(position.volume * (close_percent / 100), 2)
                
                # Ensure minimum lot size
                symbol_info = mt5.symbol_info(symbol)
                if close_volume < symbol_info.volume_min:
                    close_volume = symbol_info.volume_min
                
                # Ensure we don't try to close more than exists
                if close_volume > position.volume:
                    close_volume = position.volume
            
            # Prepare close request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": close_volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": mt5.symbol_info_tick(symbol).bid if position.type == 0 else mt5.symbol_info_tick(symbol).ask,
                "deviation": self.slippage_pips,
                "magic": 123456,
                "comment": f"Close signal {signal_id}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            # Send the close request
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ Position {signal_id} closed successfully")
                
                # Update executed signals if fully closed
                if not partial_close or close_volume >= position.volume:
                    self.executed_signals[signal_id]["status"] = "closed"
                    self.executed_signals[signal_id]["close_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    self.executed_signals[signal_id]["profit"] = result.profit
                
                return {
                    "success": True,
                    "closed_volume": close_volume,
                    "profit": result.profit
                }
            else:
                self.logger.error(f"❌ Failed to close position with error code: {result.retcode}")
                return {"success": False, "error": f"Failed to close position: {result.retcode}"}
            
        except Exception as e:
            self.logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}
    
    def modify_position(self, signal_id, new_sl=None, new_tp=None):
        """
        Modify stop loss and/or take profit for a position.
        
        Args:
            signal_id (str): ID of the signal to modify
            new_sl (float): New stop loss price, or None to keep current
            new_tp (float): New take profit price, or None to keep current
            
        Returns:
            dict: Result of the modification
        """
        if not self.connected:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        if signal_id not in self.executed_signals:
            return {"success": False, "error": "Signal not found"}
        
        try:
            signal_info = self.executed_signals[signal_id]
            order_id = signal_info["order_id"]
            symbol = signal_info["symbol"]
            
            # Check if the position is still open
            positions = mt5.positions_get(symbol=symbol)
            position = None
            
            if positions:
                for pos in positions:
                    if pos.ticket == order_id or pos.magic == 123456:
                        position = pos
                        break
            
            if not position:
                return {"success": False, "error": "Position not found"}
            
            # Use current values if new ones not provided
            sl = new_sl if new_sl is not None else position.sl
            tp = new_tp if new_tp is not None else position.tp
            
            # Prepare modification request
            request = {
                "action": mt5.TRADE_ACTION_MODIFY,
                "symbol": symbol,
                "position": position.ticket,
                "sl": sl,
                "tp": tp
            }
            
            # Send the modification request
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"✅ Position {signal_id} modified successfully")
                
                # Update executed signals
                if new_sl is not None:
                    self.executed_signals[signal_id]["stop_loss"] = new_sl
                if new_tp is not None:
                    self.executed_signals[signal_id]["take_profits"][0] = new_tp
                
                return {
                    "success": True,
                    "new_sl": sl,
                    "new_tp": tp
                }
            else:
                self.logger.error(f"❌ Failed to modify position with error code: {result.retcode}")
                return {"success": False, "error": f"Failed to modify position: {result.retcode}"}
            
        except Exception as e:
            self.logger.error(f"Error modifying position: {e}")
            return {"success": False, "error": str(e)}
    
    def get_account_info(self):
        """
        Get account information from MT5.
        
        Returns:
            dict: Account information
        """
        if not self.connected:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        try:
            account_info = mt5.account_info()
            if not account_info:
                return {"success": False, "error": "Failed to get account info"}
            
            return {
                "success": True,
                "balance": account_info.balance,
                "equity": account_info.equity,
                "margin": account_info.margin,
                "free_margin": account_info.margin_free,
                "margin_level": account_info.margin_level,
                "leverage": account_info.leverage,
                "currency": account_info.currency
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        """Clean up resources."""
        if self.initialized:
            mt5.shutdown()
            self.connected = False
            self.initialized = False
            self.logger.info("MT5 connection closed")