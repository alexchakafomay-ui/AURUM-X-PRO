from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Tuple
from dotenv import load_dotenv
load_dotenv()

def _env_bool(n: str, d: bool = False) -> bool: return os.getenv(n, str(d)).strip().lower() in {"1","true","yes","y","on"}
def _env_float(n: str, d: float) -> float:
    try: return float(os.getenv(n, str(d)))
    except: return d
def _env_int(n: str, d: int) -> int:
    try: return int(os.getenv(n, str(d)))
    except: return d
def _env_list(n: str, d: Tuple[str, ...]) -> Tuple[str, ...]:
    r = os.getenv(n); return tuple(x.strip().upper() for x in r.split(",") if x.strip()) if r else d

@dataclass(frozen=True)
class Settings:
    telegram_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: int = field(default_factory=lambda: _env_int("TELEGRAM_CHAT_ID", 0))
    twelve_data_api_key: str = field(default_factory=lambda: os.getenv("TWELVE_DATA_API_KEY", ""))
    fxnewsbias_api_key: str = field(default_factory=lambda: os.getenv("FXNEWSBIAS_API_KEY", ""))
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    openrouter_model: str = field(default_factory=lambda: os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free"))
    ai_timeout: int = field(default_factory=lambda: _env_int("AI_TIMEOUT", 45))
    paper_trading: bool = field(default_factory=lambda: _env_bool("PAPER_TRADING", True))
    risk_percent: float = field(default_factory=lambda: _env_float("RISK_PERCENT", 1.5))
    max_signals_per_day: int = field(default_factory=lambda: _env_int("MAX_SIGNALS_PER_DAY", 6))
    max_open_trades: int = field(default_factory=lambda: _env_int("MAX_OPEN_TRADES", 2))
    max_daily_loss_pct: float = field(default_factory=lambda: _env_float("MAX_DAILY_LOSS_PCT", 3.0))
    min_confidence: int = field(default_factory=lambda: _env_int("MIN_CONFIDENCE", 65))
    signal_valid_hours: int = field(default_factory=lambda: _env_int("SIGNAL_VALID_HOURS", 2))
    db_path: str = field(default_factory=lambda: os.getenv("DB_PATH", "aurum_pro.db"))
    send_no_signal: bool = field(default_factory=lambda: _env_bool("SEND_NO_SIGNAL", True))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    watchlist: Tuple[str, ...] = field(default_factory=lambda: _env_list("WATCHLIST", ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "USDCHF", "XAUUSD")))
    session_hours_utc: Tuple[int, ...] = (7, 11, 15, 19)
    prealert_minutes: int = 2
    def validate(self) -> None:
        if not self.telegram_token or not self.telegram_chat_id: raise RuntimeError("Token/Chat ID kosong!")
