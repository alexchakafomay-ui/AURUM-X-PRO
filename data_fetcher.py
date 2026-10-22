from __future__ import annotations
import logging, time
from typing import Optional
import pandas as pd, requests
from config import Settings
from utils import RateLimiter
logger = logging.getLogger(__name__)
class DataFetcher:
    TD_URL = "https://api.twelvedata.com/time_series"
    TD_INTERVALS = {"D1": "1day", "H4": "4h", "H1": "1h", "M30": "30min", "M15": "15min", "M5": "5min"}
    def __init__(self, settings: Settings):
        self.settings = settings; self.rate_limiter = RateLimiter(8, 60); self._cache = {}; self._ttl = 300
    def td_symbol(self, p: str) -> str: return "XAU/USD" if p == "XAUUSD" else f"{p[:3]}/{p[3:]}"
    def yf_symbol(self, p: str) -> str: return "GC=F" if p == "XAUUSD" else f"{p}=X"
    def fetch_twelve(self, p: str, i: str, o: int = 5000) -> Optional[pd.DataFrame]:
        if not self.settings.twelve_data_api_key: return None
        pr = {"symbol": self.td_symbol(p), "interval": i, "outputsize": o, "apikey": self.settings.twelve_data_api_key, "format": "JSON", "timezone": "UTC"}
        for at in range(3):
            try:
                self.rate_limiter.acquire(); r = requests.get(self.TD_URL, params=pr, timeout=30); d = r.json()
                if d.get("status") == "error" or "values" not in d: raise RuntimeError(str(d)[:300])
                df = pd.DataFrame(d["values"]); df["datetime"] = pd.to_datetime(df["datetime"], utc=True); df = df.set_index("datetime").sort_index()
                for c in ["open", "high", "low", "close", "volume"]:
                    if c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
                    elif c == "volume": df["volume"] = 0.0
                return df.dropna(subset=["open", "high", "low", "close"])
            except Exception as e: logger.warning("TD err %s %s: %s", p, i, e); time.sleep(2**at)
        return None
    def fetch_yfinance(self, p: str, i: str = "1h", pd_val: str = "60d") -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf
            df = yf.download(self.yf_symbol(p), interval=i, period=pd_val, progress=False, auto_adjust=False, threads=False)
            if df is None or df.empty: return None
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df.rename(columns=str.lower); df.index = pd.to_datetime(df.index, utc=True); df = df.sort_index()
            for c in ["open", "high", "low", "close", "volume"]:
                if c not in df.columns: df[c] = 0.0
                df[c] = pd.to_numeric(df[c], errors="coerce")
            return df.dropna(subset=["open", "high", "low", "close"])
        except: return None
    @staticmethod
    def resample(df: pd.DataFrame, r: str) -> pd.DataFrame:
        if df is None or df.empty: return df
        return df.resample(r, label="right", closed="right").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open", "high", "low", "close"])
    def fetch_pair_bundle(self, p: str) -> Optional[dict[str, pd.DataFrame]]:
        n = time.time()
        if p in self._cache and n - self._cache[p][0] < self._ttl: return self._cache[p][1]
        h1 = self.fetch_twelve(p, self.TD_INTERVALS["H1"], 5000); m5 = self.fetch_twelve(p, self.TD_INTERVALS["M5"], 5000)
        if h1 is None or len(h1) < 250:
            d1 = self.fetch_yfinance(p, "1d", "2y"); h1 = self.fetch_yfinance(p, "1h", "60d")
            if d1 is None or h1 is None or len(h1) < 250: return None
            h4 = self.resample(h1, "4h")
        else: d1 = self.resample(h1, "1D"); h4 = self.resample(h1, "4h")
        if m5 is None or len(m5) < 100:
            m5 = self.fetch_yfinance(p, "5m", "5d")
            if m5 is None or len(m5) < 100: return None
        m15 = self.resample(m5, "15min"); m30 = self.resample(m5, "30min")
        b = {"D1": d1, "H4": h4, "H1": h1, "M30": m30, "M15": m15, "M5": m5}
        if len(d1) < 200 or len(h4) < 100 or len(m30) < 60: return None
        self._cache[p] = (n, b); return b
    def fetch_watchlist(self) -> dict[str, Optional[dict[str, pd.DataFrame]]]:
        return {p: self.fetch_pair_bundle(p) for p in self.settings.watchlist}
