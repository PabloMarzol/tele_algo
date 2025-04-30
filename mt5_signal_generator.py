import MetaTrader5 as mt5
import polars as pl
import numpy as np
import talib  # Still useful for technical indicators
import logging
from datetime import datetime, timedelta
import time


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Ensures output to terminal
    ]
)

class MT5SignalGenerator:
    def __init__(self, mt5_username=None, mt5_password=None, mt5_server=None):
        """Initialize connection to MetaTrader5 terminal"""
        self.logger = logging.getLogger('MT5SignalGenerator')
        self.connected = False
        self.initialize_mt5(mt5_username, mt5_password, mt5_server)
        
        # Define strategy parameters
        self.strategies = {
            'ma_crossover': {
                'symbols': ['XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100'],
                'timeframes': [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15],
                'params': {'fast_length': 9, 'slow_length': 21}
            },
            'rsi_reversal': {
                'symbols': ['XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100'],
                'timeframes': [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15],
                'params': {'rsi_length': 14, 'overbought': 70, 'oversold': 30}
            },
            'support_resistance': {
                'symbols': ['XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100'],
                'timeframes': [mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15],
                'params': {'lookback': 20, 'threshold': 0.001}
            }
        }
        
        # Track generated signals to avoid duplicates
        self.signal_history = {}
    
    def initialize_mt5(self, username=None, password=None, server=None):
        """Connect to MetaTrader5 terminal with detailed logging"""
        try:
            self.logger.info(f"Initializing MT5 connection...")
            
            # Log MT5 version 
            self.logger.info(f"MetaTrader5 package version: {mt5.__version__}")
            
            # Initialize MT5 connection
            init_result = mt5.initialize()
            if not init_result:
                error_code = mt5.last_error()
                self.logger.error(f"❌ MT5 initialization failed: Error code {error_code}")
                
                # Provide more context based on error code
                if error_code == 10007:
                    self.logger.error("MT5 DLL version error - may need to reinstall MT5")
                elif error_code == 10014:
                    self.logger.error("MT5 failed to connect - check if terminal is running")
                
                return False
            
            # Log successful initialization
            self.logger.info(f"✅ MT5 initialized successfully!")
            
            # Log terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info:
                self.logger.info(f"Connected to: {terminal_info.name} (build {terminal_info.build})")
                self.logger.info(f"MT5 directory: {terminal_info.path}")
            
            # Log in if credentials provided
            if username and password and server:
                self.logger.info(f"Logging in to server: {server}...")
                login_result = mt5.login(username, password, server)
                
                if not login_result:
                    error_code = mt5.last_error()
                    self.logger.error(f"❌ MT5 login failed: Error code {error_code}")
                    
                    # Context for login errors
                    if error_code == 10019:
                        self.logger.error("Authorization error - check credentials")
                    elif error_code == 10018:
                        self.logger.error("Network connection error to trade server")
                    
                    return False
                
                # Log successful login
                account_info = mt5.account_info()
                self.logger.info(f"✅ Logged in successfully: Account #{account_info.login} ({account_info.server})")
                self.logger.info(f"Account balance: {account_info.balance} {account_info.currency}")
            
            self.connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error in MT5 connection: {str(e)}")
            return False
    
    def get_price_data(self, symbol, timeframe, bars=100):
        """Fetch historical price data from MT5 and convert to Polars DataFrame"""
        if not self.connected:
            if not self.initialize_mt5():
                return None
        
        try:
            # Adjust symbol format if needed (some brokers use different conventions)
            mt5_symbol = symbol
            
            # Get price data
            rates = mt5.copy_rates_from_pos(mt5_symbol, timeframe, 0, bars)
            if rates is None or len(rates) == 0:
                self.logger.error(f"Failed to get price data for {symbol}: {mt5.last_error()}")
                return None
            
            # Convert to Polars DataFrame directly (much more efficient than going through pandas)
            df = pl.from_numpy(
                np.array(rates), 
                schema=[
                    "time", "open", "high", "low", "close", "tick_volume", 
                    "spread", "real_volume"
                ]
            )
            
            # Convert time from Unix timestamp to datetime
            df = df.with_columns(
                pl.from_epoch("time", time_unit="s").alias("time")
            )
            
            return df
        
        except Exception as e:
            self.logger.error(f"Error getting price data for {symbol}: {e}")
            return None
    
    def calculate_ma_crossover(self, symbol, timeframe, fast_length=9, slow_length=21):
        """Calculate Moving Average Crossover signal using Polars"""
        df = self.get_price_data(symbol, timeframe, bars=slow_length*2)
        if df is None or df.height < slow_length:
            return None
        
        # Calculate MAs using Polars rolling window operations
        df = df.with_columns([
            pl.col("close").rolling_mean(fast_length).alias("fast_ma"),
            pl.col("close").rolling_mean(slow_length).alias("slow_ma")
        ])
        
        # Polars efficient way to get the last two rows
        last_rows = df.tail(2)
        
        # Check for crossover
        prev_fast = last_rows["fast_ma"][0]
        prev_slow = last_rows["slow_ma"][0]
        curr_fast = last_rows["fast_ma"][1]
        curr_slow = last_rows["slow_ma"][1]
        
        # Buy signal: fast MA crosses above slow MA
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            return self.format_signal(symbol, "BUY", df)
            
        # Sell signal: fast MA crosses below slow MA
        elif prev_fast >= prev_slow and curr_fast < curr_slow:
            return self.format_signal(symbol, "SELL", df)
            
        return None
    
    def calculate_rsi_reversal(self, symbol, timeframe, rsi_length=14, overbought=70, oversold=30):
        """Calculate RSI reversal signal with Polars"""
        df = self.get_price_data(symbol, timeframe, bars=rsi_length*3)
        if df is None or df.height < rsi_length:
            return None
        
        # For RSI calculation, we'll use talib on the numpy array
        # (Polars doesn't have built-in RSI calculation)
        closes = df["close"].to_numpy()
        rsi_values = talib.RSI(closes, timeperiod=rsi_length)
        
        # Add RSI values back to the Polars DataFrame
        df = df.with_columns(pl.Series("rsi", rsi_values))
        
        # Get last two rows for comparison
        last_rows = df.tail(2)
        
        current_rsi = last_rows["rsi"][1]
        prev_rsi = last_rows["rsi"][0]
        
        # Buy signal: RSI crossing up from oversold
        if prev_rsi < oversold and current_rsi > oversold:
            return self.format_signal(symbol, "BUY", df)
            
        # Sell signal: RSI crossing down from overbought
        elif prev_rsi > overbought and current_rsi < overbought:
            return self.format_signal(symbol, "SELL", df)
            
        return None
    
    def calculate_support_resistance(self, symbol, timeframe, lookback=20, threshold=0.001):
        """Calculate support/resistance breakout signal using Polars"""
        df = self.get_price_data(symbol, timeframe, bars=lookback*2)
        if df is None or df.height < lookback:
            return None
        
        # Get recent data using Polars slicing
        recent_data = df.slice(df.height-lookback-1, lookback)
        last_row = df.tail(1)
        prev_row = df.slice(df.height-2, 1)
        
        # Find recent highs and lows with Polars expressions
        recent_high = recent_data["high"].max()
        recent_low = recent_data["low"].min()
        
        current_close = last_row["close"][0]
        prev_close = prev_row["close"][0]
        
        # Buy signal: breakout above resistance
        if prev_close < recent_high and current_close > recent_high:
            return self.format_signal(symbol, "BUY", df)
            
        # Sell signal: breakdown below support
        elif prev_close > recent_low and current_close < recent_low:
            return self.format_signal(symbol, "SELL", df)
            
        return None
    
    def format_signal(self, symbol, direction, price_data):
        """Format the signal according to our template"""
        # Get current price info - efficient way in Polars
        current_price = price_data.tail(1)["close"][0]
        
        # Format symbol for display
        if symbol == "XAUUSD":
            display_symbol = "🟡 GOLD (XAU/USD)"
        elif symbol == "US100":
            display_symbol = "💻 NASDAQ (NAS100)"
        else:
            display_symbol = f"💱 {symbol[:3]}/{symbol[3:]}"
        
        # Calculate entry zone (0.2% range for limit orders)
        if direction == "BUY":
            direction_emoji = "🔼"
            entry_type = "BUY LIMIT ORDERS"
            entry_low = current_price
            entry_high = round(current_price * 1.002, 
                              5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            
            # Calculate stop loss (0.6% below entry)
            sl_low = round(entry_low * 0.994, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            sl_high = round(entry_high * 0.994, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            
            # Calculate take profits
            tp1 = round(entry_high * 1.003, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            tp2 = round(entry_high * 1.006, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            tp3 = round(entry_high * 1.01, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            
        else:  # SELL
            direction_emoji = "🔻"
            entry_type = "SELL LIMIT ORDERS"
            entry_high = current_price
            entry_low = round(current_price * 0.998, 
                             5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            
            # Calculate stop loss (0.6% above entry)
            sl_low = round(entry_low * 1.006, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            sl_high = round(entry_high * 1.006, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            
            # Calculate take profits
            tp1 = round(entry_low * 0.997, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            tp2 = round(entry_low * 0.994, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
            tp3 = round(entry_low * 0.99, 5 if symbol in ["EURUSD", "GBPUSD"] else 2)
        
        # Format the signal according to template
        signal = f"""🔔 VFX TRADE SIGNAL 🔔
\n\nAsset: {display_symbol}
Direction: {direction_emoji}{entry_type}
\n\n📍 Entry Zone:  ➡️ {entry_low} — {entry_high} ⬅️
🛑 Stop Loss Range based on Avg Price Fill: ➡️ {sl_low} — {sl_high} ⬅️
\n\n🎯 Take Profit Levels:
TP1: {tp1}
TP2: {tp2}
TP3: {tp3}
\n\n📊 Risk management is key.
🚫 This is not financial advice. Trade at your own risk.
🧠 We're scaling in — stacking limit orders across the range to optimize entry and reduce slippage. This approach uses time & volume smartly, just like the pros.
Patience is key. Let price come to us. ✅"""

        # Create a key for this signal to track in history
        signal_key = f"{symbol}_{direction}_{datetime.now().strftime('%Y%m%d')}"
        self.signal_history[signal_key] = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'direction': direction,
            'entry_low': entry_low,
            'entry_high': entry_high
        }
        
        return signal
    
    def generate_signal(self):
        """Run all strategies on all symbols and return the first valid signal"""
        for strategy_name, config in self.strategies.items():
            for symbol in config['symbols']:
                for timeframe in config['timeframes']:
                    # Skip if we've already sent a similar signal today
                    if self.check_duplicate_signal(symbol, "BUY") and self.check_duplicate_signal(symbol, "SELL"):
                        continue
                        
                    # Choose strategy based on name
                    if strategy_name == 'ma_crossover':
                        signal = self.calculate_ma_crossover(
                            symbol, 
                            timeframe, 
                            config['params']['fast_length'],
                            config['params']['slow_length']
                        )
                    elif strategy_name == 'rsi_reversal':
                        signal = self.calculate_rsi_reversal(
                            symbol, 
                            timeframe,
                            config['params']['rsi_length'],
                            config['params']['overbought'],
                            config['params']['oversold']
                        )
                    elif strategy_name == 'support_resistance':
                        signal = self.calculate_support_resistance(
                            symbol, 
                            timeframe,
                            config['params']['lookback'],
                            config['params']['threshold']
                        )
                    
                    # If valid signal found, return it
                    if signal:
                        return signal
        
        # No signals found from any strategy
        return None
        
    def check_duplicate_signal(self, symbol, direction):
        """Check if we've already sent a similar signal recently"""
        # Create a key pattern for today
        date_str = datetime.now().strftime('%Y%m%d')
        signal_key = f"{symbol}_{direction}_{date_str}"
        
        # Check if this exact signal has been sent today
        if signal_key in self.signal_history:
            last_time = self.signal_history[signal_key]['timestamp']
            hours_ago = (datetime.now() - last_time).total_seconds() / 3600
            
            # If sent less than 8 hours ago, consider it a duplicate
            if hours_ago < 8:
                return True
        
        return False
        
    def cleanup(self):
        """Clean up MT5 connection when done"""
        mt5.shutdown()
        self.connected = False