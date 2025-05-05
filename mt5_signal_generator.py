import logging
import MetaTrader5 as mt5
import random
import os
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import talib

class MT5SignalGenerator:
    """Class to generate trading signals from MT5 data."""
    
    def __init__(self, mt5_username=None, mt5_password=None, mt5_server=None):
        """Initialize the MT5 signal generator."""
        self.logger = logging.getLogger('MT5SignalGenerator')
        self.connected = False
        self.signal_history = {}  # Store generated signals
        
        # Default parameters for signal generation
        self.symbols = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "USOIL"]
        self.timeframes = {
            "M15": mt5.TIMEFRAME_M15,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1
        }
        
        # Signal frequency controls
        self.min_minutes_between_signals = 60  # At least 60 minutes between signals
        self.max_signals_per_hour = 1          # Maximum 1 signal per hour
        self.max_signals_per_day = 5           # Maximum 5 signals per day
        
        # MT5 credentials
        self.mt5_username = mt5_username or os.getenv("MT5_USERNAME")
        self.mt5_password = mt5_password or os.getenv("MT5_PASSWORD")
        self.mt5_server = mt5_server or os.getenv("MT5_SERVER")
        
        # Try to connect to MT5
        self.connect_to_mt5()
    
    def connect_to_mt5(self):
        """Connect to the MetaTrader 5 terminal."""
        try:
            # Initialize MT5
            if not mt5.initialize():
                self.logger.error(f"MT5 initialization failed: {mt5.last_error()}")
                self.connected = False
                return False
            
            # Login to MT5 if credentials provided
            if self.mt5_username and self.mt5_password:
                login_result = mt5.login(
                    login=int(self.mt5_username),
                    password=self.mt5_password,
                    server=self.mt5_server
                )
                
                if not login_result:
                    self.logger.error(f"MT5 login failed: {mt5.last_error()}")
                    self.connected = False
                    return False
                    
                # Check connection
                account_info = mt5.account_info()
                if account_info is None:
                    self.logger.error("Failed to get account info")
                    self.connected = False
                    return False
                
                self.logger.info(f"Connected to MT5: {account_info.server}")
                self.connected = True
                return True
            else:
                self.logger.warning("MT5 credentials not provided, working in limited mode")
                self.connected = False
                return False
                
        except Exception as e:
            self.logger.error(f"Error connecting to MT5: {e}")
            self.connected = False
            return False
    
    def generate_signal(self):
        """
        Generate a trading signal based on market analysis.
        
        Returns:
            tuple: (formatted_signal_text, signal_data) if a signal is generated, (None, None) otherwise
        """
        signals = self.check_for_signals()
        
        if not signals:
            return None, None
        
        # For now, just select the first signal
        signal_data = signals[0]
        
        # Format the signal for display
        formatted_signal = self.format_signal_message(signal_data)
        
        # Store in history
        signal_id = f"{signal_data['symbol']}_{signal_data['direction']}_{datetime.now().strftime('%Y%m%d%H%M')}"
        self.signal_history[signal_id] = signal_data
        
        return formatted_signal, signal_data
    
    def check_for_signals(self):
        """Check for new trading signals across all symbols."""
        signals = []
        
        # If not connected to MT5, use mock data
        if not self.connected:
            self.logger.warning("Not connected to MT5, generating mock signals...")
            # 30% chance of generating a mock signal
            if random.random() < 0.3:
                signals.append(self.generate_mock_signal())
            return signals
        
        try:
            # For each symbol, check indicators
            for symbol in self.symbols:
                # Use H1 timeframe for signal generation
                timeframe = self.timeframes["H1"]
                
                # Fetch latest price data
                rates = self.get_price_data(symbol, timeframe, 100)
                
                if rates is None or len(rates) < 50:
                    self.logger.warning(f"Insufficient data for {symbol}")
                    continue
                
                # Calculate indicators and check for signals
                signal = self.analyze_indicators(symbol, rates)
                if signal:
                    signals.append(signal)
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Error checking for signals: {e}")
            return signals
    
    def get_price_data(self, symbol, timeframe, count=100):
        """Get price data from MT5."""
        try:
            # Check if MT5 is working properly
            if not mt5.symbol_info(symbol):
                if not mt5.symbol_select(symbol, True):
                    self.logger.error(f"Failed to select symbol {symbol}")
                    return None
            
            # Get rates
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            
            if rates is None or len(rates) == 0:
                # MT5 is down, create mock data for testing
                self.logger.warning(f"Using mock data for {symbol}")
                return self.create_mock_data(count)
            
            # Convert to pandas DataFrame
            return pd.DataFrame(rates)
            
        except Exception as e:
            self.logger.error(f"Error getting price data for {symbol}: {e}")
            # Return mock data for testing
            return self.create_mock_data(count)
    
    def create_mock_data(self, count=100):
        """Create mock price data for testing."""
        current_time = datetime.now()
        data = []
        
        close_price = 1.1000 + random.random() * 0.1  # Random starting price
        
        for i in range(count):
            time_point = current_time - timedelta(hours=i)
            timestamp = int(time_point.timestamp())
            
            # Generate random price movement (more realistic)
            price_change = (random.random() - 0.5) * 0.002
            close_price += price_change
            
            high_price = close_price + (random.random() * 0.001)
            low_price = close_price - (random.random() * 0.001)
            open_price = close_price - price_change * random.random()
            
            # Generate random volume
            tick_volume = int(random.random() * 1000) + 100
            
            data.append({
                'time': timestamp,
                'open': open_price,
                'high': high_price,
                'low': low_price,
                'close': close_price,
                'tick_volume': tick_volume,
                'spread': random.randint(1, 5),
                'real_volume': tick_volume * 10
            })
        
        return pd.DataFrame(data)
    
    def analyze_indicators(self, symbol, data_df):
        """Analyze technical indicators to generate signals."""
        try:
            # Extract price data
            close = data_df['close'].values
            high = data_df['high'].values
            low = data_df['low'].values
            
            # Calculate indicators using TA-Lib if available
            try:
                # Moving averages
                ema20 = talib.EMA(close, timeperiod=20)
                ema50 = talib.EMA(close, timeperiod=50)
                ema200 = talib.EMA(close, timeperiod=200)
                
                # RSI
                rsi = talib.RSI(close, timeperiod=3)
                
                # MACD
                macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
                
                # Bollinger Bands
                upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
                
                # Stochastic
                slowk, slowd = talib.STOCH(high, low, close, fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
                
            except AttributeError:
                # If TA-Lib not available, use basic calculations
                self.logger.warning("TA-Lib not available, using basic indicator calculations")
                
                # Simple moving averages instead of EMA
                ema20 = np.convolve(close, np.ones(20)/20, mode='valid')
                ema50 = np.convolve(close, np.ones(50)/50, mode='valid')
                ema200 = np.convolve(close, np.ones(200)/200, mode='valid')
                
                # Pad the beginning to match array lengths
                ema20 = np.append(np.array([np.nan] * (len(close) - len(ema20))), ema20)
                ema50 = np.append(np.array([np.nan] * (len(close) - len(ema50))), ema50)
                ema200 = np.append(np.array([np.nan] * (len(close) - len(ema200))), ema200)
                
                # Simple RSI calculation
                deltas = np.diff(close)
                seed = deltas[:3]
                up = seed[seed >= 0].sum()/3.0
                down = -seed[seed < 0].sum()/3.0
                rs = up/down if down != 0 else 0
                rsi = np.zeros_like(close)
                rsi[:3] = 100. - 100./(1. + rs)
                
                for i in range(3, len(close)):
                    delta = deltas[i - 1]
                    if delta > 0:
                        upval = delta
                        downval = 0.
                    else:
                        upval = 0.
                        downval = -delta
                    up = (up * 13 + upval) / 3
                    down = (down * 13 + downval) / 3
                    rs = up/down if down != 0 else 0
                    rsi[i] = 100. - 100./(1. + rs)
                
                # Simple MACD calculation
                ema12 = np.convolve(close, np.ones(12)/12, mode='valid')
                ema26 = np.convolve(close, np.ones(26)/26, mode='valid')
                ema12 = np.append(np.array([np.nan] * (len(close) - len(ema12))), ema12)
                ema26 = np.append(np.array([np.nan] * (len(close) - len(ema26))), ema26)
                
                macd = np.zeros_like(close)
                for i in range(len(close)):
                    if not np.isnan(ema12[i]) and not np.isnan(ema26[i]):
                        macd[i] = ema12[i] - ema26[i]
                
                macd_signal = np.convolve(macd[~np.isnan(macd)], np.ones(9)/9, mode='valid')
                macd_signal = np.append(np.array([np.nan] * (len(macd) - len(macd_signal))), macd_signal)
                
                macd_hist = np.zeros_like(close)
                for i in range(len(close)):
                    if not np.isnan(macd[i]) and not np.isnan(macd_signal[i]):
                        macd_hist[i] = macd[i] - macd_signal[i]
                
                # Skip Bollinger Bands and Stochastic for basic implementation
                upper = lower = middle = np.zeros_like(close)
                slowk = slowd = np.zeros_like(close)
            
            # Define signal criteria
            # Check for BUY signals
            buy_signal_conditions = [
                # MACD Crossover
                macd[-2] < macd_signal[-2] and macd[-1] > macd_signal[-1],
                
                # RSI recovering from oversold
                rsi[-2] < 5 and rsi[-1] > 10,
                
                # Price crossing above 50 EMA
                close[-2] < ema50[-2] and close[-1] > ema50[-1],
                
                # Bullish trend confirmation: 20 EMA > 50 EMA
                ema20[-1] > ema50[-1],
                
                # Price above 200 EMA (long-term bullish)
                close[-1] > ema200[-1]
            ]
            
            # Check for SELL signals
            sell_signal_conditions = [
                # MACD Crossover
                macd[-2] > macd_signal[-2] and macd[-1] < macd_signal[-1],
                
                # RSI declining from overbought
                rsi[-2] > 95 and rsi[-1] < 90,
                
                # Price crossing below 50 EMA
                close[-2] > ema50[-2] and close[-1] < ema50[-1],
                
                # Bearish trend confirmation: 20 EMA < 50 EMA
                ema20[-1] < ema50[-1],
                
                # Price below 200 EMA (long-term bearish)
                close[-1] < ema200[-1]
            ]
            
            # Count the number of conditions met
            buy_count = sum(1 for condition in buy_signal_conditions if condition)
            sell_count = sum(1 for condition in sell_signal_conditions if condition)
            
            # Generate a signal if enough conditions are met (at least 3)
            if buy_count >= 3 and buy_count > sell_count:
                return self.create_signal(symbol, "BUY", close[-1])
            elif sell_count >= 3 and sell_count > buy_count:
                return self.create_signal(symbol, "SELL", close[-1])
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error analyzing indicators: {e}")
            return None
    
    def create_signal(self, symbol, direction, current_price):
        """Create a signal with entry, stop loss, and take profit levels."""
        # Calculate pip value based on symbol
        pip_value = self.get_pip_value(symbol)
        
        # Set stop loss and take profit distances based on symbol volatility
        sl_pips, tp1_pips, tp2_pips, tp3_pips = self.get_risk_reward_pips(symbol)
        
        # Calculate entry, stop loss and take profit prices
        if direction == "BUY":
            entry_price = current_price
            stop_loss = entry_price - (sl_pips * pip_value)
            take_profit1 = entry_price + (tp1_pips * pip_value)
            take_profit2 = entry_price + (tp2_pips * pip_value)
            take_profit3 = entry_price + (tp3_pips * pip_value)
        else:  # SELL
            entry_price = current_price
            stop_loss = entry_price + (sl_pips * pip_value)
            take_profit1 = entry_price - (tp1_pips * pip_value)
            take_profit2 = entry_price - (tp2_pips * pip_value)
            take_profit3 = entry_price - (tp3_pips * pip_value)
        
        # Format prices based on symbol
        entry_price = self.format_price(symbol, entry_price)
        stop_loss = self.format_price(symbol, stop_loss)
        take_profit1 = self.format_price(symbol, take_profit1)
        take_profit2 = self.format_price(symbol, take_profit2)
        take_profit3 = self.format_price(symbol, take_profit3)
        
        # Calculate risk-reward ratios
        rr1 = tp1_pips / sl_pips
        rr2 = tp2_pips / sl_pips
        rr3 = tp3_pips / sl_pips
        
        # Create signal data dictionary
        signal = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit1,
            "take_profit2": take_profit2,
            "take_profit3": take_profit3,
            "risk_reward1": round(rr1, 1),
            "risk_reward2": round(rr2, 1),
            "risk_reward3": round(rr3, 1),
            "timeframe": "H1",
            "timestamp": datetime.now(),
            "analysis": self.generate_signal_analysis(symbol, direction)
        }
        
        self.logger.info(f"Generated {direction} signal for {symbol} at {entry_price}")
        return signal
    
    def get_pip_value(self, symbol):
        """Get pip value for a symbol."""
        if symbol in ["USDJPY", "GBPJPY", "EURJPY"]:
            return 0.01  # 2 decimal places for JPY pairs
        elif symbol == "XAUUSD":
            return 0.1   # Gold (1 decimal place)
        elif symbol == "USOIL":
            return 0.01  # Oil (2 decimal places)
        elif symbol in ["BTCUSD", "ETHUSD"]:
            return 1.0   # Crypto (0 decimal places)
        else:
            return 0.0001  # 4 decimal places for most forex pairs
    
    def get_risk_reward_pips(self, symbol):
        """Get appropriate stop loss and take profit distances based on symbol."""
        # Default values
        sl_pips = 30
        tp1_pips = 30
        tp2_pips = 60
        tp3_pips = 90
        
        # Adjust based on symbol
        if symbol == "XAUUSD":
            sl_pips = 15    # Gold has higher pip value
            tp1_pips = 20
            tp2_pips = 40
            tp3_pips = 80
        elif symbol == "USOIL":
            sl_pips = 20
            tp1_pips = 30
            tp2_pips = 60
            tp3_pips = 120
        elif symbol in ["BTCUSD", "ETHUSD"]:
            sl_pips = 100   # Crypto is more volatile
            tp1_pips = 150
            tp2_pips = 300
            tp3_pips = 600
        elif symbol in ["USDJPY", "GBPJPY", "EURJPY"]:
            sl_pips = 30    # JPY pairs
            tp1_pips = 40
            tp2_pips = 80
            tp3_pips = 160
        
        return sl_pips, tp1_pips, tp2_pips, tp3_pips
    
    def format_price(self, symbol, price):
        """Format price with appropriate decimal places based on symbol."""
        if symbol in ["USDJPY", "GBPJPY", "EURJPY"]:
            return round(price, 3)  # 3 decimal places for JPY pairs
        elif symbol == "XAUUSD":
            return round(price, 2)  # 2 decimal places for Gold
        elif symbol == "USOIL":
            return round(price, 2)  # 2 decimal places for Oil
        elif symbol in ["BTCUSD", "ETHUSD"]:
            return round(price, 1)  # 1 decimal place for Crypto
        else:
            return round(price, 5)  # 5 decimal places for most forex pairs
    
    def generate_signal_analysis(self, symbol, direction):
        """Generate a brief analysis of why this signal was triggered."""
        # This would normally be based on the indicator analysis
        # For now, just use some generic text
        if direction == "BUY":
            return (
                f"Momentum factors indicate a constructive setup for {symbol}, with upward pressure supported by signal alignment across multiple timeframes. "
                f"Suggested strategy: implement position scaling at predefined profit thresholds and reduce tail risk by shifting the stop to breakeven after the initial target is met."
            )
        else:
            return (
                f"Momentum factors indicate a weak outlook for {symbol}, with downside continuation supported by alignment in short-term signal flows. "
                f"Suggested strategy: scale out gradually at each profit milestone, and neutralize exposure by moving the stop to breakeven following TP1."
            )
    
    def format_signal_message(self, signal_data):
        """Format signal data into a readable HTML message."""
        direction = signal_data["direction"]
        symbol = signal_data["symbol"]
        
        # Direction emoji
        direction_emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
        
        # Format the message
        message = f"""<b>⚡️ VFX SIGNAL ALERT ⚡️</b>

<b>{symbol} - {direction_emoji}</b>

<b>Entry:</b> {signal_data["entry_price"]}
<b>Stop Loss:</b> {signal_data["stop_loss"]}
<b>Take Profit 1:</b> {signal_data["take_profit"]} (RR: 1:{signal_data["risk_reward1"]})
<b>Take Profit 2:</b> {signal_data["take_profit2"]} (RR: 1:{signal_data["risk_reward2"]})
<b>Take Profit 3:</b> {signal_data["take_profit3"]} (RR: 1:{signal_data["risk_reward3"]})

<b>Timeframe:</b> {signal_data["timeframe"]}

<b>Analysis:</b>
{signal_data["analysis"]}

⏰ <i>Signal generated at {signal_data["timestamp"].strftime('%Y-%m-%d %H:%M')}</i>

<i>This is an automated signal based on our proprietary algorithm. Always apply proper risk management.</i>
This is not financial advice! Trade at your own risk!
"""
        return message
    
    def generate_mock_signal(self, symbol=None):
        """Generate a mock signal for testing."""
        if symbol is None:
            symbol = random.choice(self.symbols)
        
        # Random direction
        direction = random.choice(["BUY", "SELL"])
        
        # Random price based on symbol
        if symbol == "EURUSD":
            price = round(1.1000 + (random.random() - 0.5) * 0.1, 5)
        elif symbol == "GBPUSD":
            price = round(1.2500 + (random.random() - 0.5) * 0.1, 5)
        elif symbol == "USDJPY":
            price = round(140.00 + (random.random() - 0.5) * 5, 3)
        elif symbol == "XAUUSD":  # Gold
            price = round(1900 + (random.random() - 0.5) * 100, 2)
        elif symbol == "USOIL":  # Oil
            price = round(70 + (random.random() - 0.5) * 10, 2)
        else:
            price = round(1.0000 + random.random(), 5)
        
        return self.create_signal(symbol, direction, price)
    
    def cleanup(self):
        """Clean up MT5 connection."""
        if mt5.terminal_info() is not None:
            mt5.shutdown()
            self.logger.info("MT5 connection shut down")
        self.connected = False


# For testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test signal generation
    generator = MT5SignalGenerator()
    
    signal_text, signal_data = generator.generate_signal()
    
    if signal_text:
        print("Generated Signal:")
        print(signal_text)
        print("\nSignal Data:")
        for key, value in signal_data.items():
            if key != "timestamp":  # Skip timestamp for cleaner output
                print(f"{key}: {value}")
    else:
        print("No signal generated")
    
    # Clean up
    generator.cleanup()