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
    
    def __init__(self, username = None, password = None, server = None, risk_percent = 0.7, terminal_path = None):
        """Initialize the MT5 signal executor."""
        self.logger = logging.getLogger('MT5SignalExecutor')
        self.connected = False
        self.risk_percent = risk_percent  
        self.executed_signals = {}  # Track signals that have been executed
        self.initialized = False
        self.terminal_path = terminal_path
        
        # Connect to MT5
        self.initialize_mt5(username, password, server)
        
        # Parameters for signal execution
        self.max_spread_multiplier = 1.5  # Max allowed spread as multiplier of average
        self.slippage_pips = 3  
        self.use_limit_orders = True  
        self.retry_attempts = 3  
        self.retry_delay = 5  
        
        # Default lot sizing by symbol
        self.default_lot_sizes = {
            "EURUSD": 1.5,
            "GBPUSD": 1.5,
            "AUDUSD": 1.5,
            "USDCAD": 1.5,
            "XAUUSD": 0.3,
            "NAS100": 4.0,
            "US30": 4.0,
            "US500": 4.0,
            "FRA40": 4.0,
            "UK100": 4.0
        }
    
    def initialize_mt5(self, username=None, password=None, server=None):
        """Connect to MetaTrader5 terminal using the specified terminal path."""
        try:
            # Shutdown any existing MT5 instance first
            try:
                mt5.shutdown()
                self.logger.info("Shut down any existing MT5 connection")
            except:
                pass
            
            # Log terminal path being used
            if self.terminal_path:
                self.logger.info(f"Initializing MT5 using terminal path: {self.terminal_path}")
            else:
                self.logger.info("Initializing MT5 using default terminal path")
            
            # Initialize MT5 with the specified terminal path
            if not mt5.initialize(path=self.terminal_path):
                error_code = mt5.last_error()
                self.logger.error(f"❌ MT5 initialization failed: Error code {error_code}")
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
    
    # Add this function to the MT5SignalExecutor class
    def validate_price(self, symbol, price, direction):
        """
        Validate if the provided price is valid for the given symbol and direction.
        
        Args:
            symbol (str): Trading symbol
            price (float): The price to validate
            direction (str): Trade direction (BUY/SELL)
            
        Returns:
            tuple: (is_valid, adjusted_price) - boolean indicating if price is valid and adjusted price if needed
        """
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return False, price
            
            # Get current market price
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                self.logger.error(f"Failed to get tick data for {symbol}")
                return False, price
            
            # Get bid and ask prices
            bid = tick.bid
            ask = tick.ask
            
            # For BUY LIMIT orders, price must be below ASK
            # For SELL LIMIT orders, price must be above BID
            is_valid = True
            adjusted_price = price
            
            if direction == "BUY":
                if price >= ask:
                    # Price is too high for BUY LIMIT - adjust it
                    self.logger.warning(f"BUY LIMIT price {price:.5f} is >= current ASK {ask:.5f}, which is invalid")
                    # Set price slightly below current ask (about 1 point away)
                    adjusted_price = ask - (symbol_info.point * 2)
                    self.logger.info(f"Adjusted BUY LIMIT price to {adjusted_price:.5f}")
            else:  # SELL LIMIT
                if price <= bid:
                    # Price is too low for SELL LIMIT - adjust it
                    self.logger.warning(f"SELL LIMIT price {price:.5f} is <= current BID {bid:.5f}, which is invalid")
                    # Set price slightly above current bid (about 1 point away)
                    adjusted_price = bid + (symbol_info.point * 2)
                    self.logger.info(f"Adjusted SELL LIMIT price to {adjusted_price:.5f}")
            
            # Validate against symbol min/max prices if available
            if hasattr(symbol_info, "minprice") and hasattr(symbol_info, "maxprice"):
                if adjusted_price < symbol_info.minprice:
                    self.logger.warning(f"Price {adjusted_price:.5f} is below minimum allowed {symbol_info.minprice:.5f}")
                    adjusted_price = symbol_info.minprice
                elif adjusted_price > symbol_info.maxprice:
                    self.logger.warning(f"Price {adjusted_price:.5f} is above maximum allowed {symbol_info.maxprice:.5f}")
                    adjusted_price = symbol_info.maxprice
            
            # Check if price has expected number of decimal places
            decimals = len(str(adjusted_price).split('.')[-1])
            if decimals > symbol_info.digits:
                # Round to the correct number of decimal places
                adjusted_price = round(adjusted_price, symbol_info.digits)
                
            return is_valid, adjusted_price
        
        except Exception as e:
            self.logger.error(f"Error validating price: {e}")
            return False, price
    
    def validate_sl_tp(self, symbol, price, sl, tp, direction):
        """
        Validate and adjust stop loss and take profit levels to meet broker requirements.
        
        Args:
            symbol (str): Trading symbol
            price (float): Entry price
            sl (float): Stop loss price
            tp (float): Take profit price
            direction (str): Trade direction (BUY/SELL)
            
        Returns:
            tuple: (adjusted_sl, adjusted_tp)
        """
        try:
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return sl, tp
            
            # Get minimum stop level in points
            min_stop_level = symbol_info.trade_stops_level
            
            # Get current prices
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                self.logger.error(f"Failed to get tick data for {symbol}")
                return sl, tp
            
            bid = tick.bid
            ask = tick.ask
            
            # Calculate point value based on digits
            point = symbol_info.point
            
            # Calculate minimum distance in price
            min_distance = min_stop_level * point
            
            # Adjust SL and TP based on direction
            adjusted_sl = sl
            adjusted_tp = tp
            
            if direction == "BUY":
                # For BUY orders, SL must be below entry price and below current price
                current_price = ask
                
                # Calculate minimum SL level below current price
                min_sl = current_price - min_distance
                
                # If SL is too close, adjust it
                if sl > min_sl:
                    self.logger.warning(f"Stop loss {sl:.5f} too close to current price {current_price:.5f} (min distance: {min_distance:.5f})")
                    adjusted_sl = min_sl
                    self.logger.info(f"Adjusted stop loss to {adjusted_sl:.5f}")
                
                # For BUY orders, TP must be above entry price and current price
                # Calculate minimum TP level above current price
                min_tp = current_price + min_distance
                
                # If TP is too close, adjust it
                if tp < min_tp:
                    self.logger.warning(f"Take profit {tp:.5f} too close to current price {current_price:.5f} (min distance: {min_distance:.5f})")
                    adjusted_tp = min_tp
                    self.logger.info(f"Adjusted take profit to {adjusted_tp:.5f}")
            
            else:  # SELL
                # For SELL orders, SL must be above entry price and above current price
                current_price = bid
                
                # Calculate minimum SL level above current price
                min_sl = current_price + min_distance
                
                # If SL is too close, adjust it
                if sl < min_sl:
                    self.logger.warning(f"Stop loss {sl:.5f} too close to current price {current_price:.5f} (min distance: {min_distance:.5f})")
                    adjusted_sl = min_sl
                    self.logger.info(f"Adjusted stop loss to {adjusted_sl:.5f}")
                
                # For SELL orders, TP must be below entry price and current price
                # Calculate minimum TP level below current price
                min_tp = current_price - min_distance
                
                # If TP is too close, adjust it
                if tp > min_tp:
                    self.logger.warning(f"Take profit {tp:.5f} too close to current price {current_price:.5f} (min distance: {min_distance:.5f})")
                    adjusted_tp = min_tp
                    self.logger.info(f"Adjusted take profit to {adjusted_tp:.5f}")
            
            return adjusted_sl, adjusted_tp
        
        except Exception as e:
            self.logger.error(f"Error validating SL/TP: {e}")
            return sl, tp
    
        
    def execute_signal(self, signal_data):
        """
        Execute a trading signal on MT5 with multiple scaled entries, each with its own TP level.
        
        Args:
            signal_data (dict): Signal data including symbol, direction, entry range, stop loss, take profits
            
        Returns:
            dict: Result of the execution with order details or error information
        """
        if not self.connected or not self.initialized:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        # Extract signal ID
        signal_id = signal_data.get("signal_id", f"{signal_data['symbol']}_{signal_data['direction']}_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        
        # Log the unique signal ID
        self.logger.info(f"Processing signal with ID: {signal_id}")
        
        # Check if signal already executed - STRICT CHECK
        if signal_id in self.executed_signals:
            self.logger.info(f"Signal {signal_id} already executed - skipping duplicate execution")
            return {
                "success": False, 
                "error": "Signal already executed", 
                "order_details": self.executed_signals[signal_id]
            }
        
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
            
            # Determine number of entry points based on available take profits
            # We'll cap it to the number of TPs available to simplify position management
            num_entries = min(len(take_profits), 3)  # Maximum 3 entries
            
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
    
            # Define relative weights for distributing lots
            if direction == "BUY":
                # For BUY: more weight to lower prices
                raw_weights = [0.5, 0.3, 0.2] if num_entries == 3 else [0.7, 0.3] if num_entries == 2 else [1.0]
            else:
                # For SELL: more weight to higher prices
                raw_weights = [0.2, 0.3, 0.5] if num_entries == 3 else [0.3, 0.7] if num_entries == 2 else [1.0]
            
            # Get the minimum lot size and step
            min_lot = symbol_info.volume_min
            lot_step = symbol_info.volume_step
            
            # Calculate weighted lot sizes and ensure they meet minimums
            lot_sizes = []
            for i in range(num_entries):
                # Calculate proportional lot size
                lot_size = total_lot_size * raw_weights[i]
                
                # Round to nearest step
                lot_size = round(lot_size / lot_step) * lot_step
                
                # Ensure lot size meets minimum
                if lot_size < min_lot:
                    lot_size = min_lot
                
                # Ensure lot size doesn't exceed maximum
                if lot_size > symbol_info.volume_max:
                    lot_size = symbol_info.volume_max
                
                lot_sizes.append(lot_size)
            
            # Adjust if the sum exceeds maximum
            total_allocated = sum(lot_sizes)
            if total_allocated > total_lot_size * 1.05:  # Allow 5% tolerance for rounding
                # Scale back proportionally
                scale_factor = total_lot_size / total_allocated
                self.logger.warning(f"Total allocated lots ({total_allocated:.2f}) exceeds risk-based lot size ({total_lot_size:.2f}). Scaling by {scale_factor:.2f}")
                
                for i in range(num_entries):
                    lot_sizes[i] = max(min_lot, round((lot_sizes[i] * scale_factor) / lot_step) * lot_step)
            
            # Log the execution plan
            self.logger.info(f"Executing {signal_id} with {num_entries} entries:")
            for i in range(num_entries):
                self.logger.info(f"Entry {i+1}: Price {entry_prices[i]:.5f}, Lot Size {lot_sizes[i]:.2f}, TP {take_profits[i]:.5f}")
            
            # Select the order type based on direction
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if direction == "BUY" else mt5.ORDER_TYPE_SELL_LIMIT
            
            # Execute multiple entry orders
            executed_orders = []
            
            # Write comment for each strategy
            if "strategy" in signal_data:
                strategy_code = signal_data.get("strategy", "")
                # Map strategy codes to MT5 comment prefixes
                strategy_prefix = {
                    "MA_CROSS": "Momentum_",
                    "RSI_REV": "Mean_Rev_",
                    "SUP_RES": "SD_Inference_",
                    "VOL_HAWKES": "VOL_HAWKES_"
                }.get(strategy_code, "")
                
                # Use the strategy prefix in the comment
                _comment = f"VFX_{strategy_prefix}{direction}"
            else:
                # Fallback to original comment style if no strategy specified
                _comment = f"VFX{direction}"
            
            for i in range(num_entries):
                # For each entry point, we'll place a limit order
                entry_price = entry_prices[i]
                lot_size = lot_sizes[i]
                
                
                # Skip if lot size is invalid
                if lot_size < min_lot or lot_size <= 0:
                    self.logger.warning(f"Skipping order {i+1} - invalid lot size: {lot_size}")
                    continue
                
                # Calculate stop loss for this entry
                position_pct = i / (num_entries - 1) if num_entries > 1 else 0
                stop_loss = stop_low + (stop_high - stop_low) * position_pct
                
                # Assign take profit level to this entry
                take_profit = take_profits[i]
                
                # Validate and possibly adjust entry price
                is_valid_price, adjusted_entry_price = self.validate_price(symbol, entry_price, direction)
                if not is_valid_price:
                    self.logger.warning(f"Price validation issue for order {i+1} - using adjusted price: {adjusted_entry_price:.5f}")
                entry_price = adjusted_entry_price
                
                adjusted_sl, adjusted_tp = self.validate_sl_tp(symbol, entry_price, stop_loss, take_profit, direction)
                if adjusted_sl != stop_loss:
                    self.logger.info(f"Using adjusted stop loss: {adjusted_sl:.5f} (original: {stop_loss:.5f})")
                    stop_loss = adjusted_sl
                if adjusted_tp != take_profit:
                    self.logger.info(f"Using adjusted take profit: {adjusted_tp:.5f} (original: {take_profit:.5f})")
                    take_profit = adjusted_tp
                
                # Prepare the order request with the strategy-specific comment
                request = {
                    "action": mt5.TRADE_ACTION_PENDING,
                    "symbol": symbol,
                    "volume": lot_size,
                    "type": order_type,
                    "price": entry_price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "deviation": self.slippage_pips,
                    "magic": 123456 + i,
                    "comment": f"{_comment}{i+1}",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                
                # Log the order details
                self.logger.info(f"Sending order {i+1} for {symbol} {direction} at {entry_price:.5f} with TP at {take_profit:.5f}")
                
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
                            
                            if result.retcode == 10015:  # Invalid price error
                                self.logger.warning(f"Invalid price error for order {i+1}. Price was {entry_price:.5f}")
                                
                                # Get current market conditions
                                tick = mt5.symbol_info_tick(symbol)
                                if tick:
                                    bid = tick.bid
                                    ask = tick.ask
                                    self.logger.info(f"Current market prices - Bid: {bid:.5f}, Ask: {ask:.5f}")
                                
                                # Try to adjust the price based on direction
                                if direction == "BUY":
                                    # For BUY LIMIT, price must be below current ASK
                                    if tick and entry_price >= ask:
                                        entry_price = ask - (symbol_info.point * 5)  # 5 points below ASK
                                        self.logger.info(f"Adjusting BUY price to {entry_price:.5f} (below ASK)")
                                else:
                                    # For SELL LIMIT, price must be above current BID
                                    if tick and entry_price <= bid:
                                        entry_price = bid + (symbol_info.point * 5)  # 5 points above BID
                                        self.logger.info(f"Adjusting SELL price to {entry_price:.5f} (above BID)")
                                
                                # Update the request with new price
                                request["price"] = entry_price
                            
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
                        "take_profit": take_profit
                    })
            
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
                return self.default_lot_sizes.get(symbol, 0.01)
            
            account_balance = account_info.balance
            
            # Calculate risk amount (% of balance)
            risk_amount = account_balance * (self.risk_percent / 100)
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                self.logger.error(f"Failed to get symbol info for {symbol}")
                return self.default_lot_sizes.get(symbol, 0.01)
            
            # Log detailed symbol info for debugging
            self.logger.info(f"Symbol info for {symbol}: min_lot={symbol_info.volume_min}, max_lot={symbol_info.volume_max}, step={symbol_info.volume_step}")
            
            # Calculate stop loss distance in price terms
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
            
            # Get tick value (value of 1 point movement per lot)
            tick_value = symbol_info.trade_tick_value
            
            # Calculate pip value per lot (how much 1 pip is worth per 1 lot)
            pip_value = tick_value * (pip_size / point)
            
            # Calculate lot size based on risk
            if pip_distance > 0 and pip_value > 0:
                # Formula: risk_amount / (pip_distance * pip_value)
                lot_size = risk_amount / (pip_distance * pip_value)
                self.logger.info(f"Calculated raw lot size for {symbol}: {lot_size:.2f} (risk=${risk_amount:.2f}, pip_value=${pip_value:.2f})")
                
                # Safety check - verify calculation
                max_loss = lot_size * pip_distance * pip_value
                if abs(max_loss - risk_amount) > risk_amount * 0.1:  # 10% tolerance
                    self.logger.warning(f"Lot size calculation verification failed: {lot_size} lots with {pip_distance} pips SL = ${max_loss:.2f} risk (expected ${risk_amount:.2f})")
                    
                    # Re-calculate with explicit formula
                    lot_size = risk_amount / (pip_distance * pip_value)
                    self.logger.info(f"Re-calculated lot size: {lot_size:.2f}")
                
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
                
                # Final risk check - calculate actual risk with this lot size
                actual_risk = lot_size * pip_distance * pip_value
                self.logger.info(f"Final lot size: {lot_size:.2f}, actual risk: ${actual_risk:.2f} ({(actual_risk/account_balance)*100:.2f}% of balance)")
                
                return lot_size
            else:
                self.logger.warning(f"Invalid stop loss distance or pip value for {symbol}")
                return self.default_lot_sizes.get(symbol, 0.01)
                    
        except Exception as e:
            self.logger.error(f"Error calculating position size: {e}")
            return self.default_lot_sizes.get(symbol, 0.01)
    
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
    
    def apply_trailing_stop(self, signal_id=None, trailing_percent=None, min_profit_percent=None):
        """
        Apply trailing stop to active positions using instrument-specific scaling.
        
        Args:
            signal_id (str, optional): Specific signal ID to apply trailing stop to, or None for all active signals
            trailing_percent (float, optional): Distance to maintain between price and stop loss in percent of price
            min_profit_percent (float, optional): Minimum profit in percent before trailing stop activates
            
        Returns:
            dict: Results of trailing stop operations
        """
        if not self.connected or not self.initialized:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        # Define instrument-specific pip values and appropriate trailing distances
        instrument_settings = {
            # Format: "symbol": {"pip_multiplier": X, "min_profit_pips": Y, "trailing_pips": Z}
            # Where X is the multiplier to convert standard pips to appropriate size for this instrument
            "XAUUSD": {"pip_multiplier": 10.0, "min_profit_pips": 200, "trailing_pips": 500},  # Gold needs wider stops
            "BTCUSD": {"pip_multiplier": 100.0, "min_profit_pips": 5000, "trailing_pips": 10000},  # Bitcoin needs much wider stops
            "US30": {"pip_multiplier": 5.0, "min_profit_pips": 1100, "trailing_pips": 550},  # Dow Jones
            "US500": {"pip_multiplier": 5.0, "min_profit_pips": 950, "trailing_pips": 550},  # S&P 500
            "NAS100": {"pip_multiplier": 5.0, "min_profit_pips": 1150, "trailing_pips": 850},  # Nasdaq
            "UK100": {"pip_multiplier": 5.0, "min_profit_pips": 950, "trailing_pips": 550},  # FTSE 100
            "FRA40": {"pip_multiplier": 5.0, "min_profit_pips": 950, "trailing_pips": 550},  # CAC 40
            "GER40": {"pip_multiplier": 5.0, "min_profit_pips": 1100, "trailing_pips": 850},  # DAX
            "default": {"pip_multiplier": 1.0, "min_profit_pips": 5, "trailing_pips": 3}  # Default for forex pairs
        }
        
        # Set defaults if not provided
        default_trailing_pips = 50  # Default trailing stop distance for forex
        default_min_profit_pips = 20  # Default minimum profit before trailing activates for forex
        
        results = {
            "success": True,
            "positions_updated": 0,
            "positions_checked": 0,
            "details": []
        }
        
        try:
            # Get all signals or filter by signal_id
            signals_to_check = []
            if signal_id:
                if signal_id in self.executed_signals:
                    signals_to_check = [signal_id]
                else:
                    return {"success": False, "error": f"Signal {signal_id} not found"}
            else:
                signals_to_check = list(self.executed_signals.keys())
            
            # Process each signal
            for sig_id in signals_to_check:
                signal_info = self.executed_signals[sig_id]
                symbol = signal_info["symbol"]
                direction = signal_info["direction"]
                orders = signal_info.get("orders", [])
                
                # Get instrument-specific settings
                settings = instrument_settings.get(symbol, instrument_settings["default"])
                pip_multiplier = settings["pip_multiplier"]
                instrument_min_profit_pips = settings["min_profit_pips"]
                instrument_trailing_pips = settings["trailing_pips"]
                
                # Use provided values or instrument-specific defaults
                trailing_pips = trailing_percent if trailing_percent is not None else instrument_trailing_pips
                min_profit_pips = min_profit_percent if min_profit_percent is not None else instrument_min_profit_pips
                
                self.logger.info(f"Using instrument-specific settings for {symbol}: min_profit_pips={min_profit_pips}, trailing_pips={trailing_pips}, pip_multiplier={pip_multiplier}")
                
                # Check if the signal has associated orders
                if not orders:
                    continue
                
                # Process each order in the signal
                for order_idx, order in enumerate(orders):
                    order_id = order["order_id"]
                    
                    # Get current position info
                    position = None
                    positions = mt5.positions_get(ticket=order_id)
                    
                    # If not found by ticket, try by magic number
                    if not positions:
                        positions = mt5.positions_get(symbol=symbol)
                        if positions:
                            for pos in positions:
                                if pos.magic == 123456 + order_idx:
                                    position = pos
                                    break
                    else:
                        position = positions[0]
                    
                    if not position:
                        # Position might be closed already
                        continue
                    
                    results["positions_checked"] += 1
                    
                    # Get current market price
                    tick = mt5.symbol_info_tick(symbol)
                    if not tick:
                        self.logger.error(f"Failed to get tick data for {symbol}")
                        continue
                    
                    # Determine current price based on direction
                    current_price = tick.bid if direction == "BUY" else tick.ask
                    
                    # Get symbol info for pip calculations
                    symbol_info = mt5.symbol_info(symbol)
                    if not symbol_info:
                        self.logger.error(f"Failed to get symbol info for {symbol}")
                        continue
                    
                    # Calculate pip size based on symbol digits
                    point = symbol_info.point
                    digits = symbol_info.digits
                    
                    # For Forex, 1 pip is usually 0.0001 for 4-digit symbols, 0.00001 for 5-digit
                    if digits == 5 or digits == 3:  # 5-digit Forex or 3-digit indices/commodities
                        pip_size = point * 10
                    else:  # Standard 4-digit Forex or 2-digit indices
                        pip_size = point
                    
                    # Calculate current profit in pips
                    entry_price = position.price_open
                    if direction == "BUY":
                        profit_pips = (current_price - entry_price) / pip_size
                    else:  # SELL
                        profit_pips = (entry_price - current_price) / pip_size
                    
                    # Check if we have enough profit to activate trailing stop
                    if profit_pips < min_profit_pips:
                        self.logger.info(f"Position {order_id} profit ({profit_pips:.1f} pips) below minimum threshold ({min_profit_pips} pips)")
                        results["details"].append({
                            "order_id": order_id,
                            "symbol": symbol,
                            "direction": direction,
                            "profit_pips": profit_pips,
                            "min_profit_pips": min_profit_pips,
                            "updated": False,
                            "reason": "Profit below threshold"
                        })
                        continue
                    
                    # Calculate new stop loss based on trailing distance
                    current_sl = position.sl
                    current_tp = position.tp  # Store current take profit
                    
                    if direction == "BUY":
                        # For BUY, move stop loss up as price moves up
                        # Calculate new stop loss level
                        new_sl = current_price - (trailing_pips * pip_size)
                        
                        # Only move stop loss if it would move up (don't move it down)
                        if current_sl < new_sl:
                            self.logger.info(f"Updating trailing stop for BUY position {order_id}: {current_sl:.5f} -> {new_sl:.5f}")
                            
                            # Modify ONLY the stop loss, maintaining the current take profit
                            request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": symbol,
                                "position": position.ticket,
                                "sl": new_sl,  # New stop loss
                                "tp": current_tp  # Keep current take profit
                            }
                            
                            result = mt5.order_send(request)
                            
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                results["positions_updated"] += 1
                                results["details"].append({
                                    "order_id": order_id,
                                    "symbol": symbol,
                                    "direction": direction,
                                    "old_sl": current_sl,
                                    "new_sl": new_sl,
                                    "tp": current_tp,  # Include TP in the details
                                    "profit_pips": profit_pips,
                                    "trailing_pips": trailing_pips,
                                    "updated": True
                                })
                                
                                # Update stored order info
                                order["stop_loss"] = new_sl
                            else:
                                error_code = mt5.last_error() if not result else result.retcode
                                self.logger.error(f"Failed to modify BUY position {order_id}: {error_code}")
                                results["details"].append({
                                    "order_id": order_id,
                                    "symbol": symbol,
                                    "direction": direction,
                                    "profit_pips": profit_pips,
                                    "updated": False,
                                    "reason": f"Modify failed: {error_code}"
                                })
                        else:
                            results["details"].append({
                                "order_id": order_id,
                                "symbol": symbol,
                                "direction": direction,
                                "current_sl": current_sl,
                                "calculated_sl": new_sl,
                                "profit_pips": profit_pips,
                                "updated": False,
                                "reason": "Current SL already higher"
                            })
                    
                    else:  # SELL
                        # For SELL, move stop loss down as price moves down
                        # Calculate new stop loss level
                        new_sl = current_price + (trailing_pips * pip_size)
                        
                        # Only move stop loss if it would move down (don't move it up)
                        if current_sl > new_sl or current_sl == 0:
                            self.logger.info(f"Updating trailing stop for SELL position {order_id}: {current_sl:.5f} -> {new_sl:.5f}")
                            
                            # Modify ONLY the stop loss, maintaining the current take profit
                            request = {
                                "action": mt5.TRADE_ACTION_SLTP,
                                "symbol": symbol,
                                "position": position.ticket,
                                "sl": new_sl,  # New stop loss
                                "tp": current_tp  # Keep current take profit
                            }
                            
                            result = mt5.order_send(request)
                            
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                results["positions_updated"] += 1
                                results["details"].append({
                                    "order_id": order_id,
                                    "symbol": symbol,
                                    "direction": direction,
                                    "old_sl": current_sl,
                                    "new_sl": new_sl,
                                    "tp": current_tp,  # Include TP in the details
                                    "profit_pips": profit_pips,
                                    "trailing_pips": trailing_pips,
                                    "updated": True
                                })
                                
                                # Update stored order info
                                order["stop_loss"] = new_sl
                            else:
                                error_code = mt5.last_error() if not result else result.retcode
                                self.logger.error(f"Failed to modify SELL position {order_id}: {error_code}")
                                results["details"].append({
                                    "order_id": order_id,
                                    "symbol": symbol,
                                    "direction": direction,
                                    "profit_pips": profit_pips,
                                    "updated": False,
                                    "reason": f"Modify failed: {error_code}"
                                })
                        else:
                            results["details"].append({
                                "order_id": order_id,
                                "symbol": symbol,
                                "direction": direction,
                                "current_sl": current_sl,
                                "calculated_sl": new_sl,
                                "profit_pips": profit_pips,
                                "updated": False,
                                "reason": "Current SL already lower"
                            })
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in apply_trailing_stop: {e}")
            return {"success": False, "error": str(e)}
    
    def modify_position(self, signal_id, position_ticket=None, new_sl=None, new_tp=None):
        """
        Modify stop loss and/or take profit for a position.
        
        Args:
            signal_id (str): ID of the signal to modify
            position_ticket (int, optional): Specific position ticket to modify, or None to modify all positions for this signal
            new_sl (float, optional): New stop loss price, or None to keep current
            new_tp (float, optional): New take profit price, or None to keep current
            
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
            symbol = signal_info["symbol"]
            orders = signal_info.get("orders", [])
            
            if not orders:
                return {"success": False, "error": "No orders found for this signal"}
            
            # Track results
            results = {
                "success": True,
                "positions_modified": 0,
                "details": []
            }
            
            # Process each order in the signal
            for order_idx, order in enumerate(orders):
                order_id = order["order_id"]
                
                # Skip if we're targeting a specific position and this isn't it
                if position_ticket is not None and order_id != position_ticket:
                    continue
                
                # Check if the position is still open
                positions = mt5.positions_get(ticket=order_id)
                position = None
                
                if not positions:
                    # Try by symbol and magic
                    positions = mt5.positions_get(symbol=symbol)
                    if positions:
                        for pos in positions:
                            if pos.ticket == order_id or pos.magic == 123456 + order_idx:
                                position = pos
                                break
                else:
                    position = positions[0]
                
                if not position:
                    results["details"].append({
                        "order_id": order_id,
                        "symbol": symbol,
                        "modified": False,
                        "reason": "Position not found"
                    })
                    continue
                
                # Prepare modification request
                # Only include parameters that need to be modified
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": symbol,
                    "position": position.ticket
                }
                
                # Only add SL or TP to the request if they are changing
                if new_sl is not None:
                    request["sl"] = new_sl
                
                if new_tp is not None:
                    request["tp"] = new_tp
                
                # Skip if nothing to modify
                if "sl" not in request and "tp" not in request:
                    results["details"].append({
                        "order_id": order_id,
                        "symbol": symbol,
                        "modified": False,
                        "reason": "No changes requested"
                    })
                    continue
                
                # Send the modification request
                result = mt5.order_send(request)
                
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    self.logger.info(f"✅ Position {order_id} modified successfully")
                    
                    # Update executed signals record
                    if new_sl is not None:
                        order["stop_loss"] = new_sl
                    if new_tp is not None:
                        order["take_profit"] = new_tp
                    
                    results["positions_modified"] += 1
                    results["details"].append({
                        "order_id": order_id,
                        "symbol": symbol,
                        "modified": True,
                        "new_sl": new_sl if new_sl is not None else position.sl,
                        "new_tp": new_tp if new_tp is not None else position.tp
                    })
                else:
                    error_code = mt5.last_error() if not result else result.retcode
                    self.logger.error(f"❌ Failed to modify position with error code: {error_code}")
                    results["details"].append({
                        "order_id": order_id,
                        "symbol": symbol,
                        "modified": False,
                        "reason": f"Failed to modify position: {error_code}"
                    })
            
            # Determine overall success
            if results["positions_modified"] == 0 and position_ticket is not None:
                results["success"] = False
                results["error"] = "Failed to modify specified position"
            
            return results
            
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
    
    def generate_daily_stats(self):
        """
        Generate statistics for signals executed today.
        
        Returns:
            dict: Statistics about today's signals
        """
        if not self.connected or not self.initialized:
            if not self.initialize_mt5():
                return {"success": False, "error": "MT5 not connected"}
        
        try:
            # Get today's date
            today = datetime.now().date()
            today_str = today.strftime("%Y-%m-%d")
            
            # Get account info for balance calculations
            account_info = mt5.account_info()
            if not account_info:
                return {"success": False, "error": "Failed to get account info"}
            
            current_balance = account_info.balance
            start_balance = account_info.balance  # We'll adjust this if we find closed trades
            
            # Initialize statistics
            stats = {
                "date": today_str,
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
                "signal_details": []
            }
            
            # Find signals executed today
            today_signals = []
            for signal_id, signal_info in self.executed_signals.items():
                execution_time = signal_info.get("execution_time", "")
                if execution_time.startswith(today_str):
                    today_signals.append(signal_id)
                    stats["signals_executed"] += 1
                    stats["symbols_traded"].add(signal_info["symbol"])
            
            # Get history orders for today
            from_date = datetime(today.year, today.month, today.day)
            to_date = datetime(today.year, today.month, today.day, 23, 59, 59)
            
            # Convert to MT5 datetime format
            from_date = mt5.datetime_to_time(from_date)
            to_date = mt5.datetime_to_time(to_date)
            
            # Get history orders
            history_orders = mt5.history_orders_get(from_date, to_date)
            
            # Track orders specifically from our signals
            signal_orders = set()
            for signal_id in today_signals:
                signal_info = self.executed_signals[signal_id]
                for order in signal_info.get("orders", []):
                    signal_orders.add(order["order_id"])
            
            # Track closed positions
            closed_positions = []
            if history_orders:
                for order in history_orders:
                    # Check if it's our signal-generated order
                    if order.magic >= 123456 and order.magic < 123500:
                        # Check if this order opened a position that was later closed
                        if order.state == mt5.ORDER_STATE_FILLED and order.position_id > 0:
                            stats["positions_opened"] += 1
                            
                            # Get the deals related to this position
                            deals = mt5.history_deals_get(position=order.position_id)
                            
                            if deals:
                                # Find the closing deal
                                closing_deal = None
                                for deal in deals:
                                    if deal.entry == mt5.DEAL_ENTRY_OUT:
                                        closing_deal = deal
                                        break
                                
                                if closing_deal:
                                    # This position was closed today
                                    stats["positions_closed"] += 1
                                    
                                    # Calculate profit
                                    profit = closing_deal.profit
                                    stats["total_profit"] += profit
                                    
                                    # Determine win or loss
                                    if profit > 0:
                                        stats["wins"] += 1
                                    else:
                                        stats["losses"] += 1
                                    
                                    # Calculate pips
                                    symbol_info = mt5.symbol_info(order.symbol)
                                    if symbol_info:
                                        point = symbol_info.point
                                        digits = symbol_info.digits
                                        
                                        # For Forex, 1 pip is usually 0.0001 for 4-digit symbols, 0.00001 for 5-digit
                                        if digits == 5 or digits == 3:  # 5-digit Forex or 3-digit indices/commodities
                                            pip_size = point * 10
                                        else:  # Standard 4-digit Forex or 2-digit indices
                                            pip_size = point
                                        
                                        # Calculate price difference
                                        if order.type == mt5.ORDER_TYPE_BUY or order.type == mt5.ORDER_TYPE_BUY_LIMIT:
                                            pips = (closing_deal.price - order.price_open) / pip_size
                                        else:
                                            pips = (order.price_open - closing_deal.price) / pip_size
                                        
                                        stats["total_pips"] += pips
                                    
                                    # Add to closed positions list
                                    closed_position = {
                                        "position_id": order.position_id,
                                        "symbol": order.symbol,
                                        "type": "BUY" if order.type in [mt5.ORDER_TYPE_BUY, mt5.ORDER_TYPE_BUY_LIMIT] else "SELL",
                                        "open_price": order.price_open,
                                        "close_price": closing_deal.price,
                                        "profit": profit,
                                        "magic": order.magic
                                    }
                                    closed_positions.append(closed_position)
            
            # Check active positions
            active_positions = mt5.positions_get()
            if active_positions:
                for position in active_positions:
                    # Check if it's our signal-generated position
                    if position.magic >= 123456 and position.magic < 123500:
                        stats["active_positions"] += 1
                        
                        # Calculate unrealized profit for active positions
                        symbol_info = mt5.symbol_info(position.symbol)
                        if symbol_info:
                            point = symbol_info.point
                            digits = symbol_info.digits
                            
                            # For Forex, 1 pip is usually 0.0001 for 4-digit symbols, 0.00001 for 5-digit
                            if digits == 5 or digits == 3:  # 5-digit Forex or 3-digit indices/commodities
                                pip_size = point * 10
                            else:  # Standard 4-digit Forex or 2-digit indices
                                pip_size = point
                            
                            # Calculate pips for active positions
                            if position.type == 0:  # BUY
                                current_price = symbol_info.bid
                                unrealized_pips = (current_price - position.price_open) / pip_size
                            else:  # SELL
                                current_price = symbol_info.ask
                                unrealized_pips = (position.price_open - current_price) / pip_size
                            
                            # Find which signal this position belongs to
                            found_signal = False
                            for signal_id, signal_info in self.executed_signals.items():
                                for order in signal_info.get("orders", []):
                                    if order["order_id"] == position.ticket:
                                        # Found the signal
                                        found_signal = True
                                        signal_detail = {
                                            "signal_id": signal_id,
                                            "symbol": position.symbol,
                                            "direction": "BUY" if position.type == 0 else "SELL",
                                            "entry_price": position.price_open,
                                            "current_price": current_price,
                                            "unrealized_profit": position.profit,
                                            "unrealized_pips": unrealized_pips,
                                            "status": "ACTIVE",
                                            "lot_size": position.volume
                                        }
                                        stats["signal_details"].append(signal_detail)
                                        break
                                if found_signal:
                                    break
            
            # Add closed position details to signal details
            for position in closed_positions:
                # Find which signal this position belongs to
                for signal_id, signal_info in self.executed_signals.items():
                    for order in signal_info.get("orders", []):
                        if order["order_id"] == position["position_id"]:
                            # Found the signal
                            signal_detail = {
                                "signal_id": signal_id,
                                "symbol": position["symbol"],
                                "direction": position["type"],
                                "entry_price": position["open_price"],
                                "exit_price": position["close_price"],
                                "profit": position["profit"],
                                "status": "WIN" if position["profit"] > 0 else "LOSS"
                            }
                            stats["signal_details"].append(signal_detail)
                            break
            
            # Calculate win rate
            total_closed = stats["wins"] + stats["losses"]
            if total_closed > 0:
                stats["win_rate"] = (stats["wins"] / total_closed) * 100
            
            # Calculate return percentage
            if start_balance > 0:
                stats["return_percentage"] = (stats["total_profit"] / start_balance) * 100
            
            # Convert symbols_traded to list for serialization
            stats["symbols_traded"] = list(stats["symbols_traded"])
            
            return {"success": True, "stats": stats}
            
        except Exception as e:
            self.logger.error(f"Error generating daily stats: {e}")
            return {"success": False, "error": str(e)}
    
    def cleanup(self):
        """Clean up resources."""
        if self.initialized:
            mt5.shutdown()
            self.connected = False
            self.initialized = False
            self.logger.info("MT5 connection closed")