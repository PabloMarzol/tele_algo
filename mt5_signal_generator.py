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
    def __init__(self, username=None, password=None, server=None):
        """Initialize connection to MetaTrader5 terminal"""
        self.logger = logging.getLogger('MT5SignalGenerator')
        self.connected = False
        self.initialize_mt5(username, password, server)
        
        # Define strategy parameters with expanded asset list and lower timeframes
        self.strategies = {
            'ma_crossover': {
                'symbols': [
                    'XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100',
                    'AUDUSD', 'USDCAD', 'FRA40', 'UK100', 'US30', 'US500'
                ],
                'timeframes': [
                    mt5.TIMEFRAME_M5,
                    mt5.TIMEFRAME_M15,   
                    mt5.TIMEFRAME_M30  
                ],
                'params': {'fast_length': 9, 'slow_length': 21}
            },
            'rsi_reversal': {
                'symbols': [
                    'XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100',
                    'AUDUSD', 'USDCAD', 'FRA40', 'UK100', 'US30', 'US500'
                ],
                'timeframes': [
                    mt5.TIMEFRAME_M5,   
                    mt5.TIMEFRAME_M15,   
                    mt5.TIMEFRAME_M30   
                ],
                'params': {'rsi_length': 2, 'overbought': 95, 'oversold': 10}
            },
            'short_term_rsi': {
                'symbols': [
                    'XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100',
                    'AUDUSD', 'USDCAD', 'FRA40', 'UK100', 'US30', 'US500'
                ],
                'timeframes': [
                    mt5.TIMEFRAME_M5   
                ],
                'params': {'rsi_length': 7, 'overbought': 75, 'oversold': 25}  # Faster RSI with more extreme thresholds
            },
            'support_resistance': {
                'symbols': [
                    'XAUUSD', 'EURUSD', 'GBPUSD', 'NAS100',
                    'AUDUSD', 'USDCAD', 'FRA40', 'UK100', 'US30', 'US500'
                ],
                'timeframes': [
                    mt5.TIMEFRAME_M5,  
                    mt5.TIMEFRAME_M15,  
                    mt5.TIMEFRAME_M30
                ],
                'params': {'lookback': 20, 'threshold': 0.001}
            }
        }
        
        # Track generated signals to avoid duplicates
        self.signal_history = {}
        
        # Signal frequency control parameters
        self.max_signals_per_hour = 2   
        self.max_signals_per_day = 30    
        self.min_minutes_between_signals = 30
    
    def initialize_mt5(self, username=None, password=None, server=None):
        """Connect to MetaTrader5 terminal with detailed logging"""
        try:
            self.logger.info("Initializing MT5 connection...")
            self.logger.info(f"MetaTrader5 package version: {mt5.__version__}")
            
            # Initialize MT5
            if not mt5.initialize():
                self.logger.error(f"❌ MT5 initialization failed: Error code {mt5.last_error()}")
                return False
            
            self.logger.info("✅ MT5 initialized successfully!")
            
            # Get terminal info
            terminal_info = mt5.terminal_info()
            self.logger.info(f"Connected to: {terminal_info.name} (build {terminal_info.build})")
            self.logger.info(f"MT5 directory: {terminal_info.path}")
            
            # Login if credentials provided
            if username and password and server:
                self.logger.info(f"Logging in to server: {server}...")
                
                # Ensure proper types for login credentials
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
                return True
            
        except Exception as e:
            self.logger.error(f"❌ MT5 connection error: {e}")
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
        """Format the signal according to our template with enhanced styling"""
        # Get current price info
        current_price = price_data.tail(1)["close"][0]
        
        # Define volatility-based parameters for each instrument
        # Format: [entry_range_pct, sl_pct, tp1_pct, tp2_pct, tp3_pct]
        parameters = {
            # Original assets
            "XAUUSD": [0.15, 0.4, 0.2, 0.35, 0.5],    # Gold
            "NAS100": [0.12, 0.3, 0.15, 0.25, 0.4],    # Nasdaq
            "EURUSD": [0.05, 0.1, 0.07, 0.12, 0.2],   # EUR/USD
            "GBPUSD": [0.06, 0.12, 0.08, 0.15, 0.25], # GBP/USD
            
            # New assets
            "AUDUSD": [0.05, 0.1, 0.07, 0.12, 0.2],   # AUD/USD
            "USDCAD": [0.05, 0.1, 0.07, 0.12, 0.2],   # USD/CAD
            "FRA40": [0.1, 0.25, 0.12, 0.2, 0.35],    # CAC 40
            "UK100": [0.1, 0.25, 0.12, 0.2, 0.35],    # FTSE 100
            "US30": [0.1, 0.25, 0.12, 0.2, 0.35],     # Dow Jones
            "US500": [0.1, 0.25, 0.12, 0.2, 0.35]     # S&P 500
        }
        
        # Use default if symbol not in our parameters list
        default_params = [0.1, 0.25, 0.15, 0.3, 0.5]
        params = parameters.get(symbol, default_params)
        
        # Unpack parameters
        entry_range_pct, sl_pct, tp1_pct, tp2_pct, tp3_pct = params
        
        # Convert to multipliers
        entry_range = entry_range_pct / 100
        sl_range = sl_pct / 100
        tp1_range = tp1_pct / 100
        tp2_range = tp2_pct / 100
        tp3_range = tp3_pct / 100
        
        # Format symbol for display with emojis and proper names
        symbol_display = {
            "XAUUSD": "🟡 GOLD (XAU/USD)",
            "NAS100": "💻 NASDAQ (NAS100)",
            "EURUSD": "💱 EUR/USD",
            "GBPUSD": "💱 GBP/USD",
            "AUDUSD": "💱 AUD/USD",
            "USDCAD": "💱 USD/CAD",
            "FRA40": "🇫🇷 CAC 40 (FRA40)",
            "UK100": "🇬🇧 FTSE 100 (UK100)",
            "US30": "🇺🇸 DOW JONES (US30)",
            "US500": "🇺🇸 S&P 500 (US500)"
        }
        
        display_symbol = symbol_display.get(symbol, f"💱 {symbol[:3]}/{symbol[3:]}")
        
        # Decimal places to round to
        if symbol in ["EURUSD", "GBPUSD", "AUDUSD", "USDCAD"]:
            decimals = 5  # Forex pairs
        elif symbol == "XAUUSD":
            decimals = 2  # Gold
        elif symbol in ["NAS100", "FRA40", "UK100", "US30", "US500"]:
            decimals = 0  # Indices (whole numbers)
        else:
            decimals = 2  # Default
        
        # Calculate entry zone and levels based on direction
        if direction == "BUY":
            direction_emoji = "🔼"
            entry_type = "BUY LIMIT ORDERS"
            
            # Buy limit zone is slightly below current price
            entry_high = current_price
            entry_low = round(current_price * (1 - entry_range), decimals)
            
            # Stop loss is below entry
            sl_low = round(entry_low * (1 - sl_range), decimals)
            sl_high = round(entry_high * (1 - sl_range), decimals)
            
            # Take profits above entry
            tp1 = round(entry_high * (1 + tp1_range), decimals)
            tp2 = round(entry_high * (1 + tp2_range), decimals)
            tp3 = round(entry_high * (1 + tp3_range), decimals)
            
        else:  # SELL
            direction_emoji = "🔻"
            entry_type = "SELL LIMIT ORDERS"
            
            # Sell limit zone is slightly above current price
            entry_low = current_price
            entry_high = round(current_price * (1 + entry_range), decimals)
            
            # Stop loss is above entry
            sl_low = round(entry_low * (1 + sl_range), decimals)
            sl_high = round(entry_high * (1 + sl_range), decimals)
            
            # Take profits below entry
            tp1 = round(entry_low * (1 - tp1_range), decimals)
            tp2 = round(entry_low * (1 - tp2_range), decimals)
            tp3 = round(entry_low * (1 - tp3_range), decimals)
        
        # Format the signal with enhanced styling (bold text, better spacing)
        signal = f"""
    🔔 <b>VFX TRADE SIGNAL</b> 🔔

    <b>Asset:</b> {display_symbol}
    <b>Direction:</b> {direction_emoji} <b>{entry_type}</b>

    📍 <b>Entry Zone:</b>  ➡️ {entry_low} — {entry_high} ⬅️

    🛑 <b>Stop Loss Range:</b> ➡️ {sl_low} — {sl_high} ⬅️

    🎯 <b>Take Profit Levels:</b>
    • TP1: {tp1}
    • TP2: {tp2}
    • TP3: {tp3}

    📊 <b>Risk management is key.</b>

    🧠 We're scaling in — stacking limit orders across the range to optimize entry and reduce slippage. This approach uses time & volume smartly, just like the pros.

    ⏳ Patience is key. Let price come to us. ✅

    🚫 <i>This is not financial advice. Trade at your own risk.</i>
    """

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