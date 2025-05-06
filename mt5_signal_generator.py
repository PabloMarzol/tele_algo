import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
import random
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='mt5_signal_generator.log'
)
logger = logging.getLogger('MT5SignalGenerator')

class MT5SignalGenerator:
    """
    Signal generator for trading systems using MetaTrader 5
    With enhanced features:
    - Multiple timeframes (15M, 30M)
    - Entry and stop loss ranges
    - Multiple indicator combinations
    """
    
    def __init__(self, username=None, password=None, server=None):
        """Initialize MT5 connection and signal parameters"""
        self.connected = False
        self.last_check_time = datetime.now() - timedelta(hours=12)  # Start ready to check
        self.signal_history = {}  # Store generated signals
        
        # Symbol settings
        self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "XAUUSD"]
        self.timeframes = {
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
        }
        self.default_timeframe = "M15"  # Changed from 1H to 15 min
        
        # Connect to MT5
        self.connect_to_mt5(username, password, server)
        
        # Signal settings
        self.signal_cooldown_hours = 1  # Min hours between signals for same symbol
        self.max_signals_per_day = 4  # Max signals per symbol per day
        self.enable_range_entries = True  # Use price ranges instead of exact prices
        
    def connect_to_mt5(self, username=None, password=None, server=None):
        """Connect to MetaTrader 5 terminal"""
        try:
            # Load from environment variables if not provided
            if not username:
                username = os.environ.get("MT5_USERNAME", "")
            if not password:
                password = os.environ.get("MT5_PASSWORD", "")
            if not server:
                server = os.environ.get("MT5_SERVER", "")
            
            # Initialize MT5 connection
            if not mt5.initialize():
                logger.error(f"MT5 initialization failed with error code {mt5.last_error()}")
                return False
            
            # Log in to MT5 account if credentials provided
            if username and password and server:
                login_result = mt5.login(username, password, server)
                if not login_result:
                    logger.error(f"MT5 login failed with error code {mt5.last_error()}")
                    return False
                logger.info(f"Connected to MT5 as {username} on {server}")
            else:
                logger.warning("No MT5 credentials provided, using existing terminal connection")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MT5: {e}")
            self.connected = False
            return False
    
    def disconnect_from_mt5(self):
        """Disconnect from MetaTrader 5 terminal"""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Disconnected from MT5")
    
    def fetch_data(self, symbol, timeframe_str=None, bars=200):
        """Fetch historical data for a symbol and timeframe"""
        if not self.connected:
            if not self.connect_to_mt5():
                return None
        
        if not timeframe_str:
            timeframe_str = self.default_timeframe
        
        timeframe = self.timeframes.get(timeframe_str, mt5.TIMEFRAME_M15)
        
        try:
            # Fetch the data from MT5
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
            
            if rates is None or len(rates) == 0:
                logger.error(f"Failed to fetch data for {symbol} on {timeframe_str}")
                return None
            
            # Convert to pandas DataFrame
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            return df
        
        except Exception as e:
            logger.error(f"Error fetching data for {symbol} on {timeframe_str}: {e}")
            return None
    
    def add_indicators(self, df):
        """Add multiple technical indicators to DataFrame"""
        if df is None or len(df) == 0:
            return None
        
        try:
            # RSI indicator
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=3).mean()
            avg_loss = loss.rolling(window=3).mean()
            
            rs = avg_gain / avg_loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # Multiple EMAs
            df['ema_fast'] = df['close'].ewm(span=9, adjust=False).mean()
            df['ema_medium'] = df['close'].ewm(span=21, adjust=False).mean()
            df['ema_slow'] = df['close'].ewm(span=50, adjust=False).mean()
            
            # Bollinger Bands
            df['sma_20'] = df['close'].rolling(window=20).mean()
            df['std_20'] = df['close'].rolling(window=20).std()
            df['bb_upper'] = df['sma_20'] + (df['std_20'] * 2)
            df['bb_lower'] = df['sma_20'] - (df['std_20'] * 2)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['sma_20']
            
            # Stochastic Oscillator
            n = 14  # Default %K period
            m = 3   # Default %K smoothing
            t = 3   # Default %D period
            
            # Calculate %K
            low_min = df['low'].rolling(window=n).min()
            high_max = df['high'].rolling(window=n).max()
            df['stoch_k'] = 100 * ((df['close'] - low_min) / (high_max - low_min))
            
            # Calculate %D
            df['stoch_d'] = df['stoch_k'].rolling(window=t).mean()
            
            return df
        
        except Exception as e:
            logger.error(f"Error adding indicators: {e}")
            return df
    
    def check_rsi_ema_signal(self, df, symbol):
        """Check for trading signals based on RSI and EMA strategy"""
        if df is None or len(df) < 50:
            return None
        
        # Get the most recent data
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Strategy 1: RSI crosses with EMA trend confirmation
        # BUY signal: RSI crosses above 10 (from oversold) and price is above EMA
        # SELL signal: RSI crosses below 95 (from overbought) and price is below EMA
        
        signal = None
        
        # BUY signal conditions
        if (previous['rsi'] < 10 and current['rsi'] > 10 and 
            current['close'] > current['ema_medium'] and
            current['ema_fast'] > current['ema_medium']):
            signal = {
                'symbol': symbol,
                'direction': 'BUY',
                'strategy': 'RSI_EMA',
                'timestamp': datetime.now()
            }
            
        # SELL signal conditions
        elif (previous['rsi'] > 95 and current['rsi'] < 95 and 
              current['close'] < current['ema_medium'] and
              current['ema_fast'] < current['ema_medium']):
            signal = {
                'symbol': symbol,
                'direction': 'SELL',
                'strategy': 'RSI_EMA',
                'timestamp': datetime.now()
            }
        
        if signal:
            # Generate entry and exit levels
            self.add_signal_levels(signal, df)
        
        return signal
    
    def check_bb_stoch_signal(self, df, symbol):
        """Check for trading signals based on Bollinger Bands and Stochastic strategy"""
        if df is None or len(df) < 50:
            return None
        
        # Get the most recent data
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Strategy 2: Bollinger Band Breakout with Stochastic confirmation
        # BUY signal: Price closes above upper BB and Stochastic K crosses above D in oversold territory
        # SELL signal: Price closes below lower BB and Stochastic K crosses below D in overbought territory
        
        signal = None
        
        # BUY signal conditions
        if (current['close'] > current['bb_upper'] and
            previous['stoch_k'] < previous['stoch_d'] and
            current['stoch_k'] > current['stoch_d'] and
            previous['stoch_k'] < 30):
            signal = {
                'symbol': symbol,
                'direction': 'BUY',
                'strategy': 'BB_STOCH',
                'timestamp': datetime.now()
            }
            
        # SELL signal conditions
        elif (current['close'] < current['bb_lower'] and
              previous['stoch_k'] > previous['stoch_d'] and
              current['stoch_k'] < current['stoch_d'] and
              previous['stoch_k'] > 70):
            signal = {
                'symbol': symbol,
                'direction': 'SELL',
                'strategy': 'BB_STOCH',
                'timestamp': datetime.now()
            }
        
        if signal:
            # Generate entry and exit levels
            self.add_signal_levels(signal, df)
        
        return signal
    
    def add_signal_levels(self, signal, df):
        """Add entry/exit levels to signal with price ranges instead of exact points"""
        try:
            current = df.iloc[-1]
            atr = self.calculate_atr(df, 14)  # 14-period ATR
            
            # Convert atr to price range percentage (roughly 0.5-1% of price for most forex)
            range_pct = min(max(atr / current['close'], 0.0015), 0.0050)
            
            if signal['direction'] == 'BUY':
                # For BUY signals
                signal['entry_price'] = current['close']
                
                # Entry range (slightly below to slightly above current price)
                signal['entry_range_low'] = round(current['close'] * (1 - range_pct), 5)
                signal['entry_range_high'] = round(current['close'] * (1 + range_pct * 0.5), 5)
                
                # Stop loss range (below recent low)
                recent_low = min(df['low'].iloc[-5:])
                sl_level = min(recent_low, current['close'] * (1 - range_pct * 3))
                signal['stop_loss'] = round(sl_level, 5)
                signal['stop_range_low'] = round(sl_level * (1 - range_pct * 0.5), 5)
                signal['stop_range_high'] = round(sl_level * (1 + range_pct * 0.5), 5)
                
                # Take profit levels (multiple targets)
                risk = current['close'] - sl_level
                signal['take_profit'] = round(current['close'] + risk * 1.5, 5)
                signal['take_profit2'] = round(current['close'] + risk * 2.5, 5)
                signal['take_profit3'] = round(current['close'] + risk * 4.0, 5)
                
            else:
                # For SELL signals
                signal['entry_price'] = current['close']
                
                # Entry range (slightly above to slightly below current price)
                signal['entry_range_low'] = round(current['close'] * (1 - range_pct * 0.5), 5)
                signal['entry_range_high'] = round(current['close'] * (1 + range_pct), 5)
                
                # Stop loss range (above recent high)
                recent_high = max(df['high'].iloc[-5:])
                sl_level = max(recent_high, current['close'] * (1 + range_pct * 3))
                signal['stop_loss'] = round(sl_level, 5)
                signal['stop_range_low'] = round(sl_level * (1 - range_pct * 0.5), 5)
                signal['stop_range_high'] = round(sl_level * (1 + range_pct * 0.5), 5)
                
                # Take profit levels (multiple targets)
                risk = sl_level - current['close']
                signal['take_profit'] = round(current['close'] - risk * 1.5, 5)
                signal['take_profit2'] = round(current['close'] - risk * 2.5, 5)
                signal['take_profit3'] = round(current['close'] - risk * 4.0, 5)
            
        except Exception as e:
            logger.error(f"Error adding signal levels: {e}")
            # Fallback to basic levels if calculation fails
            signal['entry_price'] = current['close']
            signal['stop_loss'] = current['close'] * (0.98 if signal['direction'] == 'BUY' else 1.02)
            signal['take_profit'] = current['close'] * (1.02 if signal['direction'] == 'BUY' else 0.98)
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range (ATR)"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        
        return atr
    
    def check_signal_cooldown(self, symbol):
        """Check if symbol is on cooldown after recent signal"""
        if symbol in self.signal_history:
            last_signal_time = self.signal_history[symbol]['timestamp']
            hours_since = (datetime.now() - last_signal_time).total_seconds() / 3600
            
            if hours_since < self.signal_cooldown_hours:
                return False
        
        return True
    
    def check_signals(self):
        """Check for signals across all symbols and strategies"""
        if not self.connected and not self.connect_to_mt5():
            return None
        
        # Don't check too frequently
        time_since_check = (datetime.now() - self.last_check_time).total_seconds() / 60
        if time_since_check < 5:  # Check at most every 5 minutes
            return None
        
        self.last_check_time = datetime.now()
        
        # Randomize symbol order to avoid always prioritizing the same symbols
        symbols = self.symbols.copy()
        random.shuffle(symbols)
        
        # Randomize timeframes to increase signal diversity
        timeframes = list(self.timeframes.keys())
        random.shuffle(timeframes)
        
        for symbol in symbols:
            # Check cooldown period
            if not self.check_signal_cooldown(symbol):
                continue
            
            for timeframe in timeframes:
                # Get historical data
                df = self.fetch_data(symbol, timeframe, 200)
                if df is None:
                    continue
                
                # Add technical indicators
                df = self.add_indicators(df)
                if df is None:
                    continue
                
                # Randomly select which strategy to check first for more variety
                strategies = ["rsi_ema", "bb_stoch"]
                random.shuffle(strategies)
                
                signal = None
                for strategy in strategies:
                    if strategy == "rsi_ema":
                        signal = self.check_rsi_ema_signal(df, symbol)
                    elif strategy == "bb_stoch":
                        signal = self.check_bb_stoch_signal(df, symbol)
                    
                    if signal:
                        # Add metadata to the signal
                        signal['timeframe'] = timeframe
                        
                        # Store in history
                        self.signal_history[symbol] = signal
                        
                        logger.info(f"New signal: {symbol} {signal['direction']} on {timeframe} - Strategy: {signal['strategy']}")
                        return signal
        
        return None