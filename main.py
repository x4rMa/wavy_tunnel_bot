import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
from config import Config
from metatrader.connection import initialize_mt5, shutdown_mt5
from metatrader.data_retrieval import get_historical_data
from strategy.tunnel_strategy import (
    run_strategy, check_broker_connection, check_market_open,
    get_fresh_tick_data, manage_position, execute_trade, place_pending_order
)
from backtesting.backtest import run_backtest
from utils.logger import setup_logging
from utils.error_handling import handle_error
from utils.mt5_log_checker import start_log_checking, stop_log_checking
import logging
import argparse
import os
import time

def clear_log_file():
    with open("app.log", "w"):
        pass

def check_auto_trading_enabled():
    """Check if global auto trading is enabled and log the status."""
    global_autotrading_enabled = mt5.terminal_info().trade_allowed
    if not global_autotrading_enabled:
        logging.error("Global auto trading is disabled. Please enable it manually in the MetaTrader 5 terminal.")
    else:
        logging.info("Global auto trading is enabled.")

def run_backtest_func():
    try:
        logging.info("Initializing MetaTrader5...")
        if not initialize_mt5(Config.MT5_PATH):
            raise Exception("Failed to initialize MetaTrader5")
        logging.info("MetaTrader5 initialized successfully.")

        check_auto_trading_enabled()

        for symbol in Config.SYMBOLS:
            logging.info("Running backtest...")
            start_date = datetime(2024, 6, 12)
            end_date = datetime.now()
            initial_balance = 10000
            risk_percent = Config.RISK_PER_TRADE
            stop_loss_pips = 20
            pip_value = Config.PIP_VALUE

            backtest_data = get_historical_data(symbol, mt5.TIMEFRAME_H1, start_date, end_date)
            if backtest_data is not None and not backtest_data.empty:
                logging.info(f"Backtest data shape: {backtest_data.shape}")
                logging.info(f"Backtest data head:\n{backtest_data.head()}")
            else:
                logging.error(f"No historical data retrieved for {symbol} for backtesting")
                continue

            if len(backtest_data) < 20:
                logging.error(f"Not enough data for symbol {symbol} to perform backtest")
                continue

            backtest_data.loc[:, 'close'] = pd.to_numeric(backtest_data['close'], errors='coerce')

            try:
                run_backtest(
                    symbol=symbol,
                    data=backtest_data,
                    initial_balance=initial_balance,
                    risk_percent=risk_percent,
                    min_take_profit=Config.MIN_TP_PROFIT,
                    max_loss_per_day=Config.MAX_LOSS_PER_DAY,
                    starting_equity=Config.STARTING_EQUITY,
                    max_trades_per_day=Config.LIMIT_NO_OF_TRADES,
                    stop_loss_pips=stop_loss_pips,
                    pip_value=pip_value
                )
                logging.info("Backtest completed successfully.")
            except Exception as e:
                handle_error(e, f"An error occurred during backtesting for {symbol}")

    except Exception as e:
        error_code = mt5.last_error()
        error_message = str(e)
        handle_error(e, f"An error occurred in the run_backtest_func: {error_code} - {error_message}")

    finally:
        logging.info("Shutting down MetaTrader5...")
        shutdown_mt5()
        logging.info("MetaTrader5 connection gracefully shut down.")

def run_live_trading_func():
    try:
        logging.info("Initializing MetaTrader5...")
        if not initialize_mt5(Config.MT5_PATH):
            raise Exception("Failed to initialize MetaTrader5")
        logging.info("MetaTrader5 initialized successfully.")

        check_auto_trading_enabled()

        account_info = mt5.account_info()
        if account_info is None:
            raise Exception("Failed to get account info")
        if account_info.server.endswith("demo"):
            logging.info("Trading on a demo account.")
        else:
            logging.info("Trading on a live account.")

        if not check_broker_connection():
            return

        if not check_market_open():
            return

        daily_trades = 0
        total_trades = 0
        total_profit = 0.0
        total_loss = 0.0
        max_drawdown_reached = False
        starting_balance = Config.STARTING_EQUITY
        current_balance = starting_balance

        start_time = time.time()
        max_duration = 1 * 1800  # 10 hours

        while time.time() - start_time < max_duration:
            if max_drawdown_reached:
                logging.info("Maximum drawdown reached. Stopping trading.")
                break

            current_day = datetime.now().date()
            if daily_trades >= Config.LIMIT_NO_OF_TRADES:
                logging.info("Maximum number of trades for the day reached. Stopping trading for today.")
                time.sleep(86400)
                daily_trades = 0
                continue

            for symbol in Config.SYMBOLS:
                logging.info(f"Running live trading for {symbol}...")

                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    logging.error(f"Symbol {symbol} is not available.")
                    continue

                if not symbol_info.visible:
                    logging.info(f"Symbol {symbol} is not visible, attempting to make it visible.")
                    if not mt5.symbol_select(symbol, True):
                        logging.error(f"Failed to select symbol {symbol}")
                        continue

                tick_data = []
                tick_start_time = time.time()

                while len(tick_data) < 200:
                    tick = mt5.symbol_info_tick(symbol)
                    if tick is None:
                        logging.warning(f"Failed to retrieve tick data for {symbol}.")
                        time.sleep(1)
                        continue

                    tick_data.append({
                        'time': datetime.fromtimestamp(tick.time),
                        'bid': tick.bid,
                        'ask': tick.ask,
                        'last': tick.last
                    })

                    time.sleep(1)

                tick_end_time = time.time()
                elapsed_time = tick_end_time - tick_start_time
                logging.info(f"Collected 200 ticks in {elapsed_time:.2f} seconds.")

                df = pd.DataFrame(tick_data)
                logging.info(f"Dataframe created with tick data: {df.tail()}")

                if 'high' not in df.columns or 'low' not in df.columns or 'close' not in df.columns:
                    df['high'] = df['bid']
                    df['low'] = df['ask']
                    df['close'] = df['last']

                std_dev = df['close'].rolling(window=20).std().iloc[-1]  # Calculate standard deviation

                order_request = {
                    'action': mt5.TRADE_ACTION_DEAL,
                    'symbol': symbol,
                    'volume': 0.01,
                    'price': tick.bid,
                    'sl': tick.bid - (20 * mt5.symbol_info(symbol).point),  # Example stop loss
                    'tp': tick.bid + (20 * mt5.symbol_info(symbol).point),  # Example take profit
                    'deviation': 10,
                    'magic': 12345,
                    'comment': 'Tunnel Strategy',
                    'type': mt5.ORDER_TYPE_BUY,
                    'type_filling': mt5.ORDER_FILLING_FOK,
                    'type_time': mt5.ORDER_TIME_GTC,
                }
                logging.info(f"Placing order with the following details: {order_request}")

                try:
                    result = execute_trade(order_request)
                    logging.info(f"Order send result: {result}")

                    if result is None:
                        logging.error("mt5.order_send returned None. This may indicate a silent failure or an internal error.")
                    elif result.retcode != mt5.TRADE_RETCODE_DONE:
                        logging.error(f"Order failed with retcode: {result.retcode}")

                        if Config.ENABLE_PENDING_ORDER_FALLBACK:
                            logging.info("Attempting to place a pending order due to market order failure...")
                            pending_order_result = place_pending_order(order_request)
                            if pending_order_result is not None:
                                logging.info("Pending order placed successfully.")
                            else:
                                logging.error("Failed to place pending order.")
                    else:
                        logging.info("Order placed successfully.")

                        total_profit += result.profit if hasattr(result, 'profit') else 0.0
                        current_balance += result.profit if hasattr(result, 'profit') else 0.0

                        daily_trades += 1
                        total_trades += 1
                        logging.info(f"Live trading iteration completed for {symbol}. Total trades today: {daily_trades}")
                        logging.info(f"Current Balance: {current_balance:.2f}")

                except Exception as e:
                    logging.error(f"An error occurred while running strategy for {symbol}: {e}")

                time.sleep(60)

            if time.time() - start_time >= max_duration:
                logging.info("Maximum duration reached. Stopping trading.")
                break

    except Exception as e:
        error_code = mt5.last_error()
        error_message = str(e)
        handle_error(e, f"An error occurred in the run_live_trading_func: {error_code} - {error_message}")

    finally:
        logging.info("Shutting down MetaTrader5...")
        shutdown_mt5()
        logging.info("MetaTrader5 connection gracefully shut down.")

        logging.info("Summary of Trading Session:")
        logging.info(f"Total trades: {total_trades}")
        logging.info(f"Starting balance: {starting_balance:.2f}")
        logging.info(f"Ending balance: {current_balance:.2f}")
        logging.info(f"Total profit: {total_profit:.2f}")
        logging.info(f"Total loss: {total_loss:.2f}")

def open_log_file():
    import subprocess
    log_file_path = os.path.abspath("app.log")
    if os.name == "nt":
        os.startfile(log_file_path)
    elif os.name == "posix":
        subprocess.call(["open", log_file_path])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="Run the UI")
    args = parser.parse_args()

    try:
        setup_logging()
        logging.info("STARTING APPLICATION")

        logging.info("LOGGING ALL THE CONFIG SETTINGS")
        Config.log_config()

        start_log_checking()

        if args.ui:
            run_ui(run_backtest_func, run_live_trading_func, clear_log_file, open_log_file)
        else:
            print("Choose an option:")
            print("1. Run Backtesting")
            print("2. Run Live Trading")
            choice = input("Enter your choice (1 or 2): ")

            if choice == "1":
                run_backtest_func()
            elif choice == "2":
                run_live_trading_func()
            else:
                print("Invalid choice. Exiting...")

    except Exception as e:
        error_code = mt5.last_error()
        error_message = str(e)
        handle_error(e, f"An error occurred in the main function: {error_code} - {error_message}")

    finally:
        stop_log_checking()

if __name__ == '__main__':
    main()
