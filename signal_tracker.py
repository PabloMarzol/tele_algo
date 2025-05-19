import asyncio
import logging
import json
import os
import polars as pl
from datetime import datetime, timedelta
import MetaTrader5 as mt5

class SignalTracker:
    """Class for tracking active trading signals and their progress."""
    
    def __init__(self, storage_path="./bot_data/active_signals.json"):
        """
        Initialize the signal tracker.
        
        Args:
            storage_path (str): Path to store active signals
        """
        self.storage_path = storage_path
        self.logger = logging.getLogger('SignalTracker')
        self.active_signals = {}
        self.load_signals()
        
        # Track signal updates to avoid spamming users
        self.signal_updates = {}  # {signal_id: {last_update_time, last_update_pct}}
        
        # Initialize MT5 connection
        self.mt5_connected = False
        self.init_mt5()
        
        # Track milestones for each signal
        self.signal_milestones = {}
        
        # Important thresholds to track
        self.important_thresholds = [25, 50, 75, 90]
        
        # Minimum price change % to trigger an update
        self.min_price_change_pct = 5
        
        # Minimum time between updates for a single signal
        self.min_update_interval_minutes = 30
        
        # Is the price monitor running
        self.monitor_running = False
    
    def init_mt5(self):
        """Initialize connection to MetaTrader 5."""
        try:
            if not mt5.initialize():
                self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                self.mt5_connected = False
                return False
            
            # Check connection
            if mt5.terminal_info() is None:
                self.logger.error("Failed to get MT5 terminal info")
                self.mt5_connected = False
                return False
            
            self.logger.info("Successfully connected to MT5")
            self.mt5_connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Error connecting to MT5: {e}")
            self.mt5_connected = False
            return False
    
    def load_signals(self):
        """Load active signals from storage."""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r') as f:
                    self.active_signals = json.load(f)
                    
                    # Convert string timestamps back to datetime objects
                    for signal_id, signal in self.active_signals.items():
                        if 'timestamp' in signal and isinstance(signal['timestamp'], str):
                            try:
                                signal['timestamp'] = datetime.fromisoformat(signal['timestamp'])
                            except ValueError:
                                # If datetime string format is not ISO
                                signal['timestamp'] = datetime.strptime(signal['timestamp'], '%Y-%m-%d %H:%M:%S')
                
                self.logger.info(f"Loaded {len(self.active_signals)} active signals from {self.storage_path}")
            else:
                self.logger.info(f"No active signals file found at {self.storage_path}")
                self.active_signals = {}
        except Exception as e:
            self.logger.error(f"Error loading active signals: {e}")
            self.active_signals = {}
    
    def save_signals(self):
        """Save active signals to storage."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            
            # Convert datetime objects to strings for JSON serialization
            signals_to_save = {}
            for signal_id, signal in self.active_signals.items():
                signals_to_save[signal_id] = signal.copy()
                if 'timestamp' in signals_to_save[signal_id] and isinstance(signals_to_save[signal_id]['timestamp'], datetime):
                    signals_to_save[signal_id]['timestamp'] = signals_to_save[signal_id]['timestamp'].isoformat()
            
            with open(self.storage_path, 'w') as f:
                json.dump(signals_to_save, f, indent=2)
            
            self.logger.info(f"Saved {len(self.active_signals)} active signals to {self.storage_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving active signals: {e}")
            return False
    
    def add_signal(self, signal_data):
        """
        Add a new signal to track.
        
        Args:
            signal_data (dict): Signal data including symbol, direction, entry, stop loss, take profits
        
        Returns:
            str: Signal ID if successful, None otherwise
        """
        try:
            # Validate signal data
            required_fields = ["symbol", "direction", "entry_price"]
            for field in required_fields:
                if field not in signal_data:
                    self.logger.error(f"Signal missing required field: {field}")
                    return None
            
            # Create a signal ID
            timestamp = signal_data.get('timestamp', datetime.now())
            if isinstance(timestamp, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp)
                except ValueError:
                    timestamp = datetime.now()
            
            signal_id = f"{signal_data['symbol']}_{signal_data['direction']}_{timestamp.strftime('%Y%m%d%H%M%S')}"
            
            # Add timestamp if not provided
            if 'timestamp' not in signal_data:
                signal_data['timestamp'] = timestamp
            
            # Store the signal
            self.active_signals[signal_id] = signal_data
            
            # Initialize update tracking
            self.signal_updates[signal_id] = {
                'last_update_time': datetime.now() - timedelta(hours=1),  # Allow immediate update
                'last_update_pct': 0,
                'updates_sent': 0,
                'completed_tps': []
            }
            
            # Save to storage
            self.save_signals()
            
            self.logger.info(f"Added new signal: {signal_id}")
            # Initialize milestone tracking for this signal
            self.signal_milestones[signal_id] = {
                'last_pct': 0,
                'reached_milestones': set(),
                'last_update_time': datetime.now() - timedelta(hours=1),  # Allow immediate update
                'take_profits_hit': set(),
                'stop_loss_hit': False
            }
            
            # Start the monitor if not running
            if not self.monitor_running and hasattr(self, 'update_callback'):
                asyncio.create_task(self.continuous_price_monitor())
            
            return signal_id
                
            
        except Exception as e:
            self.logger.error(f"Error adding signal: {e}")
            return None
        
    async def continuous_price_monitor(self):
        """Continuously monitor prices for all active signals."""
        self.monitor_running = True
        self.logger.info("Starting continuous price monitor")
        
        try:
            while True:
                try:
                    signals_to_update = []
                    now = datetime.now()
                    
                    # Check each active signal
                    for signal_id, signal in list(self.active_signals.items()):
                        try:
                            # Skip if updated too recently
                            if signal_id in self.signal_milestones:
                                milestone_data = self.signal_milestones[signal_id]
                                last_update_time = milestone_data['last_update_time']
                                minutes_since_update = (now - last_update_time).total_seconds() / 60
                                
                                if minutes_since_update < self.min_update_interval_minutes:
                                    continue
                            
                            # Get current status
                            status = self.check_signal_status(signal_id)
                            if not status:
                                continue
                            
                            # Check for significant changes
                            update_needed = False
                            
                            # Get milestone data
                            if signal_id in self.signal_milestones:
                                milestone_data = self.signal_milestones[signal_id]
                                last_pct = milestone_data['last_pct']
                                reached_milestones = milestone_data['reached_milestones']
                                take_profits_hit = milestone_data['take_profits_hit']
                                stop_loss_hit = milestone_data['stop_loss_hit']
                                
                                current_pct = status['pct_to_tp1']
                                pct_change = abs(current_pct - last_pct)
                                
                                # Check stop loss hit
                                if status['stop_hit'] and not stop_loss_hit:
                                    update_needed = True
                                    milestone_data['stop_loss_hit'] = True
                                
                                # Check for take profits hit
                                for i, hit in enumerate(status['tps_hit']):
                                    if hit and i not in take_profits_hit:
                                        update_needed = True
                                        take_profits_hit.add(i)
                                
                                # Check for crossing thresholds
                                for threshold in self.important_thresholds:
                                    # Check if crossed threshold (in either direction)
                                    crossed_up = last_pct < threshold and current_pct >= threshold
                                    crossed_down = last_pct >= threshold and current_pct < threshold
                                    
                                    if crossed_up or crossed_down:
                                        if crossed_up:
                                            reached_milestones.add(threshold)
                                        elif crossed_down and threshold in reached_milestones:
                                            reached_milestones.remove(threshold)
                                        
                                        update_needed = True
                                        break
                                
                                # Check for significant movement
                                if pct_change >= self.min_price_change_pct:
                                    update_needed = True
                                
                                # If update needed, add to list
                                if update_needed:
                                    self.logger.info(f"Signal {signal_id} needs update: last {last_pct:.1f}%, current {current_pct:.1f}%")
                                    signals_to_update.append({
                                        "signal_id": signal_id,
                                        "signal": signal,
                                        "status": status
                                    })
                                    
                                    # Update tracking data
                                    milestone_data['last_pct'] = current_pct
                                    milestone_data['last_update_time'] = now
                            
                        except Exception as e:
                            self.logger.error(f"Error monitoring signal {signal_id}: {e}")
                    
                    # If there are signals to update, call the callback
                    if signals_to_update and hasattr(self, 'update_callback'):
                        asyncio.create_task(self.update_callback(signals_to_update))
                    
                    # Cleanup completed signals
                    await self.cleanup_completed_signals_async()
                    
                    # Sleep before next check
                    await asyncio.sleep(15)  # Check every 15 seconds
                    
                except Exception as e:
                    self.logger.error(f"Error in continuous monitor loop: {e}")
                    await asyncio.sleep(60)  # Longer sleep on error
            
        except asyncio.CancelledError:
            self.logger.info("Continuous price monitor cancelled")
            self.monitor_running = False
        except Exception as e:
            self.logger.error(f"Continuous price monitor crashed: {e}")
            self.monitor_running = False
    
    def remove_signal(self, signal_id):
        """
        Remove a signal from tracking.
        
        Args:
            signal_id (str): ID of the signal to remove
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if signal_id in self.active_signals:
                del self.active_signals[signal_id]
                if signal_id in self.signal_updates:
                    del self.signal_updates[signal_id]
                
                self.save_signals()
                self.logger.info(f"Removed signal: {signal_id}")
                return True
            else:
                self.logger.warning(f"Signal not found for removal: {signal_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error removing signal: {e}")
            return False
    
    def check_signal_status(self, signal_id):
        """
        Check the current status of a signal.
        
        Args:
            signal_id (str): ID of the signal to check
        
        Returns:
            dict: Status information including current price, percent to target, etc.
        """
        try:
            if signal_id not in self.active_signals:
                self.logger.warning(f"Signal not found for status check: {signal_id}")
                return None
            
            signal = self.active_signals[signal_id]
            symbol = signal["symbol"]
            
            # Get current price from MT5
            current_price = self.get_current_price(symbol)
            if current_price is None:
                self.logger.warning(f"Could not get current price for {symbol}")
                return None
            
            # Extract values, converting strings to float if needed
            direction = signal["direction"]
            entry_price = float(signal["entry_price"]) if isinstance(signal["entry_price"], str) else signal["entry_price"]
            stop_loss = float(signal["stop_loss"]) if "stop_loss" in signal and isinstance(signal["stop_loss"], str) else signal.get("stop_loss", 0)
            
            # Extract take-profit targets
            take_profits = []
            for i in range(1, 4):  # Look for TP1, TP2, TP3
                tp_key = f"take_profit{i}" if i > 1 else "take_profit"
                if tp_key in signal:
                    tp_value = signal[tp_key]
                    tp_value = float(tp_value) if isinstance(tp_value, str) else tp_value
                    take_profits.append(tp_value)
            
            # Calculate status based on direction
            if direction == "BUY":
                in_profit = current_price > entry_price
                profit_pips = self.calculate_pips(symbol, current_price - entry_price)
                
                # Calculate percentages to take profits
                pct_to_tps = []
                for tp in take_profits:
                    entry_to_tp = tp - entry_price
                    current_to_tp = tp - current_price
                    pct_complete = ((entry_price - current_price) / entry_to_tp) * -100 if entry_to_tp != 0 else 0
                    pct_to_tps.append(pct_complete)
                
                # Check if stop loss hit
                stop_hit = stop_loss > 0 and current_price <= stop_loss
                
                # Check if take profits hit
                tps_hit = [current_price >= tp for tp in take_profits]
                
            else:  # SELL signal
                in_profit = current_price < entry_price
                profit_pips = self.calculate_pips(symbol, entry_price - current_price)
                
                # Calculate percentages to take profits
                pct_to_tps = []
                for tp in take_profits:
                    entry_to_tp = entry_price - tp
                    current_to_tp = current_price - tp
                    pct_complete = ((entry_price - current_price) / entry_to_tp) * 100 if entry_to_tp != 0 else 0
                    pct_to_tps.append(pct_complete)
                
                # Check if stop loss hit
                stop_hit = stop_loss > 0 and current_price >= stop_loss
                
                # Check if take profits hit
                tps_hit = [current_price <= tp for tp in take_profits]
            
            # Create status object
            status = {
                "signal_id": signal_id,
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "current_price": current_price,
                "stop_loss": stop_loss,
                "take_profits": take_profits,
                "in_profit": in_profit,
                "profit_pips": profit_pips,
                "pct_to_tp1": pct_to_tps[0] if pct_to_tps else 0,
                "pct_to_tps": pct_to_tps,
                "stop_hit": stop_hit,
                "tps_hit": tps_hit
            }
            
            # Check if we should update last status
            if signal_id in self.signal_updates:
                self.signal_updates[signal_id]["last_status"] = status
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error checking signal status: {e}")
            return None
    def calculate_pips(self, symbol, price_difference):
        """
        Calculate pips based on the asset type.
        
        Args:
            symbol (str): Trading symbol
            price_difference (float): Raw price difference
        
        Returns:
            float: Value in pips
        """
        # For forex pairs (4 or 5 decimal places usually)
        if symbol in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD"]:
            return price_difference * 10000  # Convert to pips (4th decimal place)
        
        # For gold (2 decimal places usually)
        elif symbol == "XAUUSD":
            return price_difference * 10  # Gold is often measured in 0.1 increments
        
        # For indices (whole numbers or 1 decimal place)
        elif symbol in ["NAS100", "FRA40", "UK100", "US30", "US500"]:
            return price_difference  # Indices are often measured in whole points
        
        # Default for other symbols
        else:
            return price_difference * 100 
    def get_current_price(self, symbol):
        """
        Get current price from MT5.
        
        Args:
            symbol (str): Symbol to get price for
        
        Returns:
            float: Current price or None if error
        """
        try:
            # Check MT5 connection
            if not self.mt5_connected:
                if not self.init_mt5():
                    return None
            
            # Ensure symbol is selected
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to select symbol {symbol}: {mt5.last_error()}")
                return None
            
            # Get current tick
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self.logger.error(f"Failed to get tick for {symbol}: {mt5.last_error()}")
                return None
            
            # Return average of bid and ask
            return (tick.bid + tick.ask) / 2
            
        except Exception as e:
            self.logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def check_signals_for_updates(self, min_pct_change=5, min_update_interval_minutes=5):
        """
        Check all active signals for significant changes that warrant an update.
        
        Args:
            min_pct_change (float): Minimum percentage change to trigger update
            min_update_interval_minutes (int): Minimum minutes between updates
        
        Returns:
            list: Signals requiring updates
        """
        try:
            signals_to_update = []
            now = datetime.now()
            
            for signal_id, signal in self.active_signals.items():
                try:
                    # Skip if updated too recently
                    if signal_id in self.signal_updates:
                        last_update = self.signal_updates[signal_id]['last_update_time']
                        time_since_update = (now - last_update).total_seconds() / 60
                        
                        if time_since_update < min_update_interval_minutes:
                            continue
                    
                    # Check current status
                    status = self.check_signal_status(signal_id)
                    if not status:
                        continue
                    
                    # Get the last update percentage
                    last_pct = 0
                    if signal_id in self.signal_updates:
                        last_pct = self.signal_updates[signal_id].get('last_update_pct', 0)
                    
                    current_pct = status['pct_to_tp1']
                    pct_change = abs(current_pct - last_pct)
                    
                    # Check for significant changes
                    update_needed = False
                    
                    # Hitting take profits or stop loss
                    if any(status['tps_hit']) or status['stop_hit']:
                        update_needed = True
                    
                    # Significant movement toward TP1
                    elif pct_change >= min_pct_change:
                        update_needed = True
                    
                    # Crossing important thresholds (25%, 50%, 75%, 90%)
                    important_thresholds = [25, 50, 75, 90]
                    for threshold in important_thresholds:
                        if (last_pct < threshold and current_pct >= threshold) or (last_pct > threshold and current_pct <= threshold):
                            update_needed = True
                            break
                    
                    # Check for newly hit take profits
                    if signal_id in self.signal_updates:
                        completed_tps = self.signal_updates[signal_id].get('completed_tps', [])
                        for i, hit in enumerate(status['tps_hit']):
                            if hit and i not in completed_tps:
                                update_needed = True
                                completed_tps.append(i)
                                self.signal_updates[signal_id]['completed_tps'] = completed_tps
                    
                    if update_needed:
                        self.logger.info(f"Signal {signal_id} needs update: last {last_pct:.1f}%, current {current_pct:.1f}%")
                        signals_to_update.append({
                            "signal_id": signal_id,
                            "signal": signal,
                            "status": status
                        })
                        
                        # Update tracking data
                        if signal_id in self.signal_updates:
                            self.signal_updates[signal_id]['last_update_pct'] = current_pct
                            self.signal_updates[signal_id]['last_update_time'] = now
                            self.signal_updates[signal_id]['updates_sent'] += 1
                    
                except Exception as e:
                    self.logger.error(f"Error processing signal {signal_id}: {e}")
            
            return signals_to_update
            
        except Exception as e:
            self.logger.error(f"Error checking signals for updates: {e}")
            return []
    
    def cleanup_completed_signals(self, max_age_hours=72):
        """
        Remove signals that are completed or too old.
        
        Args:
            max_age_hours (int): Maximum age in hours for signals to be kept
        
        Returns:
            int: Number of signals removed
        """
        try:
            signals_to_remove = []
            now = datetime.now()
            
            for signal_id, signal in self.active_signals.items():
                try:
                    # Check age
                    timestamp = signal['timestamp']
                    if isinstance(timestamp, str):
                        try:
                            timestamp = datetime.fromisoformat(timestamp)
                        except ValueError:
                            timestamp = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    
                    age_hours = (now - timestamp).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        signals_to_remove.append(signal_id)
                        continue
                    
                    # Check status
                    status = self.check_signal_status(signal_id)
                    if not status:
                        continue
                    
                    # Remove if stop loss hit
                    if status['stop_hit']:
                        signals_to_remove.append(signal_id)
                        continue
                    
                    # Remove if all take profits hit
                    if all(status['tps_hit']):
                        signals_to_remove.append(signal_id)
                        continue
                    
                except Exception as e:
                    self.logger.error(f"Error checking signal {signal_id} for cleanup: {e}")
            
            # Remove signals
            for signal_id in signals_to_remove:
                self.remove_signal(signal_id)
            
            self.logger.info(f"Cleaned up {len(signals_to_remove)} completed signals")
            return len(signals_to_remove)
            
        except Exception as e:
            self.logger.error(f"Error cleaning up signals: {e}")
            return 0
    
    async def cleanup_completed_signals_async(self):
        """Async version of cleanup_completed_signals."""
        return self.cleanup_completed_signals()  
 
    def get_signal_history(self, days=7):
        """
        Get statistics on signal performance over time.
        
        Args:
            days (int): Number of days to look back
        
        Returns:
            dict: Statistics on signal performance
        """
        # This would typically query a database or logs, but for now we'll just return basic stats
        return {
            "total_signals": len(self.active_signals),
            "active_signals": len(self.active_signals),
            "successful_signals": 0,
            "failed_signals": 0
        }

    def register_update_callback(self, callback_function):
        """Register a callback function to be called when signals need updates"""
        self.update_callback = callback_function
        self.logger.info("Update callback registered")
    
    async def monitor_active_signals(self):
        """
        Monitor active signals for significant changes and trigger callback when needed
        """
        try:
            signals_to_update = self.check_signals_for_updates()
            
            # If there are signals that need updates and a callback is registered
            if signals_to_update and hasattr(self, 'update_callback'):
                self.logger.info(f"Calling update callback for {len(signals_to_update)} signals")
                await self.update_callback(signals_to_update)
                return len(signals_to_update)
            return 0
            
        except Exception as e:
            self.logger.error(f"Error monitoring active signals: {e}")
            return 0

# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    tracker = SignalTracker()
    
    # Add a test signal
    test_signal = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.0750,
        "stop_loss": 1.0720,
        "take_profit": 1.0800,
        "take_profit2": 1.0850,
        "take_profit3": 1.0900,
        "timestamp": datetime.now()
    }
    
    signal_id = tracker.add_signal(test_signal)
    
    if signal_id:
        print(f"Added signal: {signal_id}")
        
        # Check signal status
        status = tracker.check_signal_status(signal_id)
        if status:
            print(f"Signal status: {status}")
        
        # Check for updates
        updates = tracker.check_signals_for_updates()
        print(f"Signals needing updates: {len(updates)}")
        
        # Cleanup
        removed = tracker.cleanup_completed_signals()
        print(f"Removed {removed} signals")