import numpy as np
import polars as pl
import logging

class HawkesProcess:
    """
    Implementation of a Hawkes Process for volatility modeling
    
    The Hawkes process captures volatility clustering by applying
    an exponential decay kernel to price ranges.
    """
    
    def __init__(self, kappa=0.1):
        """
        Initialize the Hawkes process
        
        Parameters:
        -----------
        kappa: float
            Decay parameter (controls memory of the process)
        """
        self.kappa = kappa
        self._alpha = np.exp(-kappa)
        self.logger = logging.getLogger('HawkesProcess')
    
    def process_data(self, data_series):
        """
        Apply the Hawkes process to a data series
        
        Parameters:
        -----------
        data_series: np.ndarray
            Input data series to process
        
        Returns:
        --------
        np.ndarray: Processed data with hawkes decay
        """
        if isinstance(data_series, list):
            data_series = np.array(data_series)
            
        output = np.zeros(len(data_series))
        output[0] = np.nan
        
        for i in range(1, len(data_series)):
            if np.isnan(output[i - 1]):
                output[i] = data_series[i]
            else:
                output[i] = output[i - 1] * self._alpha + data_series[i]
        
        return output * self.kappa

def calculate_hawkes_signal(df, atr_lookback=251, kappa=0.51, quantile_lookback=97):
    """
    Calculate trading signals based on Hawkes process volatility
    
    Parameters:
    -----------
    df: pl.DataFrame
        Price data with OHLC columns
    atr_lookback: int
        Period for ATR calculation
    kappa: float
        Decay parameter for the Hawkes process
    quantile_lookback: int
        Lookback period for quantile calculations
    
    Returns:
    --------
    tuple: (signal, hawkes_values, q05, q95)
        signal: 1 for buy, -1 for sell, 0 for no signal
        hawkes_values: array of hawkes process values
        q05: 5th percentile of hawkes values
        q95: 95th percentile of hawkes values
    """
    try:
        if df.height < max(atr_lookback, quantile_lookback) + 10:
            return 0, None, None, None
            
        # Calculate ATR
        true_range = pl.max_horizontal(
            (df["high"] - df["low"]),
            (df["high"] - df["close"].shift(1)).abs(),
            (df["low"] - df["close"].shift(1)).abs()
        )
        
        atr = true_range.rolling_mean(atr_lookback).fill_null(true_range)
        
        # Calculate normalized range (high-low) / atr
        norm_range = ((df["high"] - df["low"]) / atr).fill_null(0)
        
        # Apply Hawkes process
        hawkes = HawkesProcess(kappa=kappa)
        hawkes_values = hawkes.process_data(norm_range.to_numpy())
        
        # Calculate quantiles
        valid_values = hawkes_values[~np.isnan(hawkes_values)]
        if len(valid_values) < quantile_lookback:
            return 0, hawkes_values, None, None
            
        recent_values = valid_values[-quantile_lookback:]
        q05 = np.quantile(recent_values, 0.05)
        q95 = np.quantile(recent_values, 0.95)
        
        # Generate trading signal
        signal = 0
        last_below_idx = -1
        
        # Get the last few values for signal generation
        n = min(20, len(hawkes_values))
        recent_hawkes = hawkes_values[-n:]
        recent_prices = df["close"].tail(n).to_numpy()
        
        # Look for a low volatility point
        for i in range(n-1):
            if recent_hawkes[i] < q05:
                last_below_idx = i
                
        # Check for breakout after low volatility
        if last_below_idx >= 0:
            curr_idx = n - 1  # Last value
            prev_idx = n - 2  # Second-to-last value
            
            # Check if we just broke above the high threshold
            if recent_hawkes[prev_idx] <= q95 and recent_hawkes[curr_idx] > q95:
                # Determine direction based on price change from last low vol point
                price_change = recent_prices[curr_idx] - recent_prices[last_below_idx]
                
                if price_change > 0:
                    signal = 1  # Buy signal
                else:
                    signal = -1  # Sell signal
        
        return signal, hawkes_values, q05, q95
    except Exception as e:
        logging.error(f"Error in hawkes_strategy.calculate_hawkes_signal: {e}")
        return 0, None, None, None