import os
from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(script_dir)
dotenv_path = os.path.join(project_dir, '.env')

def reload_env():
    load_dotenv(dotenv_path, override=True)

reload_env()

class Config:
    MT5_LOGIN = os.getenv("MT5_LOGIN")
    MT5_PASSWORD = os.getenv("MT5_PASSWORD")
    MT5_SERVER = os.getenv("MT5_SERVER")
    MT5_PATH = os.getenv("MT5_PATH")
    MT5_LOT_SIZE = os.getenv("MT5_LOT_SIZE")
    SYMBOLS = os.getenv("SYMBOLS").split(",")
    MT5_TIMEFRAME = os.getenv("MT5_TIMEFRAME")
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_IDS = os.getenv("TELEGRAM_IDS").split(",")
    MIN_TP_PROFIT = os.getenv("MIN_TP_PROFIT")
    MAX_LOSS_PER_DAY = os.getenv("MAX_LOSS_PER_DAY")
    STARTING_EQUITY = os.getenv("STARTING_EQUITY")
    LIMIT_NO_OF_TRADES = os.getenv("LIMIT_NO_OF_TRADES")
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 0.01))
    PIP_VALUE = float(os.getenv("PIP_VALUE", 0.0001))

    @classmethod
    def validate(cls):
        required_vars = [
            'MT5_LOGIN', 'MT5_PASSWORD', 'MT5_SERVER', 'MT5_PATH',
            'MT5_LOT_SIZE', 'SYMBOLS', 'MT5_TIMEFRAME', 'RISK_PER_TRADE'
        ]
        for var in required_vars:
            if not getattr(cls, var, None):
                raise ValueError(f"Missing required environment variable: {var}")