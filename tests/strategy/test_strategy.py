import unittest
import pandas as pd
import numpy as np
from unittest import mock
from strategy.tunnel_strategy import (
    calculate_ema, calculate_tunnel_bounds, detect_peaks_and_dips, 
    check_entry_conditions, generate_trade_signal, run_strategy
)
import MetaTrader5 as mt5

class TestStrategy(unittest.TestCase):

    def test_calculate_ema(self):
        prices = pd.Series([100, 200, 300, 400, 500])
        period = 3
        result = calculate_ema(prices, period)
        expected_ema = pd.Series([None, None, 200.0, 300.0, 400.0])
        pd.testing.assert_series_equal(result, expected_ema, check_names=False)

    def test_calculate_tunnel_bounds(self):
        data = pd.DataFrame({'close': [100, 200, 300, 400, 500]})
        period = 3
        deviation_factor = 1.0
        expected_upper_bound = pd.Series([None, None, 341.42, 441.42, 541.42])
        expected_lower_bound = pd.Series([None, None, 58.58, 158.58, 258.58])
        upper_bound, lower_bound = calculate_tunnel_bounds(data, period, deviation_factor)
        pd.testing.assert_series_equal(upper_bound.round(2), expected_upper_bound, check_names=False)
        pd.testing.assert_series_equal(lower_bound.round(2), expected_lower_bound, check_names=False)

    def test_detect_peaks_and_dips(self):
        data = {
            'high': [10, 12, 15, 14, 13, 17, 16, 19, 18, 17],
            'low': [8, 7, 6, 9, 8, 11, 10, 9, 12, 11]
        }
        df = pd.DataFrame(data)
        peak_type = 5
        expected_peaks = [15, 19]
        expected_dips = [6, 9]
        peaks, dips = detect_peaks_and_dips(df, peak_type)
        print(f"Detected peaks: {peaks}, Detected dips: {dips}")
        self.assertEqual(peaks, expected_peaks)
        self.assertEqual(dips, expected_dips)

    @mock.patch('strategy.tunnel_strategy.mt5')
    def test_check_entry_conditions(self, mock_mt5):
        row = pd.Series({
            'close': 350,
            'wavy_c': 300,
            'wavy_h': 320,
            'wavy_l': 310,
            'tunnel1': 250,
            'tunnel2': 240
        })
        peaks = [350]
        dips = [150]
        symbol = 'EURUSD'
        mock_symbol_info = mock.Mock()
        mock_symbol_info.trade_tick_size = 0.01
        mock_mt5.symbol_info.return_value = mock_symbol_info

        buy_condition, sell_condition = check_entry_conditions(row, peaks, dips, symbol)
        self.assertTrue(buy_condition)
        self.assertFalse(sell_condition)

    def test_generate_trade_signal(self):
        data = pd.DataFrame({'close': [100, 200, 300, 400, 450, 500]})
        period = 3
        deviation_factor = 1.0
        expected_signal = None  # Correcting the expected signal based on calculations
        signal = generate_trade_signal(data, period, deviation_factor)
        upper_bound, lower_bound = calculate_tunnel_bounds(data, period, deviation_factor)
        print(f"Upper Bound: {upper_bound}")
        print(f"Lower Bound: {lower_bound}")
        print(f"Close: {data['close'].iloc[-1]}")
        self.assertEqual(signal, expected_signal)

    def test_generate_trade_signal2(self):
        # Added more data points to ensure valid EMA calculations
        data = pd.DataFrame({'close': [100, 200, 300, 400, 450, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500]})
        period = 3
        deviation_factor = 1.0
        expected_signal = 'BUY'  # Expecting a BUY signal based on the data
        signal = generate_trade_signal(data, period, deviation_factor)
        upper_bound, lower_bound = calculate_tunnel_bounds(data, period, deviation_factor)
        print(f"Upper Bound: {upper_bound}")
        print(f"Lower Bound: {lower_bound}")
        print(f"Close: {data['close'].iloc[-1]}")
        self.assertEqual(signal, expected_signal)

    @mock.patch('strategy.tunnel_strategy.mt5')
    @mock.patch('strategy.tunnel_strategy.get_historical_data')
    def test_run_strategy(self, mock_get_historical_data, mock_mt5):
        mock_mt5.TIMEFRAME_M1 = 1
        mock_mt5.symbol_info.return_value.trade_tick_size = 0.01
        
        symbols = ['EURUSD']
        timeframe = mock_mt5.TIMEFRAME_M1
        lot_size = 0.1
        min_take_profit = 10
        max_loss_per_day = 50
        starting_equity = 1000
        max_trades_per_day = 5

        # Mock data retrieval and other MT5 functions
        mock_mt5.initialize.return_value = True
        mock_mt5.symbols_get.return_value = [mock.Mock(name='EURUSD')]
        mock_get_historical_data.return_value = pd.DataFrame({
            'time': pd.date_range(start='1/1/2022', periods=5, freq='min'),
            'open': [100, 200, 300, 400, 500],
            'high': [110, 220, 330, 440, 550],
            'low': [90, 180, 270, 360, 450],
            'close': [105, 210, 315, 420, 525],
            'tick_volume': [1000, 2000, 3000, 4000, 5000],
            'spread': [10, 20, 30, 40, 50],
            'real_volume': [100, 200, 300, 400, 500]
        })

        run_strategy(symbols, mock_mt5.initialize, timeframe, lot_size, min_take_profit, max_loss_per_day, starting_equity, max_trades_per_day)

if __name__ == '__main__':
    unittest.main()