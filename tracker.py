from __future__ import annotations
import asyncio, logging
from typing import Optional
import pandas as pd
from data_fetcher import DataFetcher
from logger import Database
from telegram_sender import TelegramSender
from utils import parse_db_ts, pip_size, utcnow
logger = logging.getLogger(__name__)
class SignalTracker:
    def __init__(self, db: Database, f: DataFetcher, s: TelegramSender): self.db, self.f, self.s = db, f, s
    async def run(self) -> None:
        for sig in self.db.get_open_signals():
            try:
                df = await asyncio.to_thread(self.f.fetch_yfinance, sig["pair"], "5m", "5d")
                res = self.evaluate(sig, df)
                if res and res[0] != sig["status"]:
                    self.db.update_status(sig["id"], res[0], res[1], res[2])
                    if res[0] in {"TP1", "TP2", "SL", "EXPIRED", "CANCELLED"}: await self.s.send_result(sig, res[0], res[1], res[2])
            except Exception: logger.exception("Track err %s", sig.get("id"))
    def evaluate(self, sig: dict, df: Optional[pd.DataFrame]) -> Optional[tuple[str, float, float]]:
        if df is None or df.empty: return None
        try: ts, val = parse_db_ts(sig["ts_utc"]), parse_db_ts(sig["valid_until"])
        except: return None
        df = df[df.index >= ts - pd.Timedelta(minutes=5)]
        if df.empty: return None
        e, s, t1 = float(sig["entry"]), float(sig["sl"]), float(sig["tp1"]); d, p, n, pip = sig["direction"], sig["pair"], pd.Timestamp(utcnow()), pip_size(sig["pair"])
        tch = (df["low"] <= e).any() if d == "BUY" else (df["high"] >= e).any()
        if not tch:
            if n > val: return ("EXPIRED", 0.0, 0.0)
            lc = float(df["close"].iloc[-1])
            if d == "BUY" and lc >= e + 0.5*(t1-e): return ("CANCELLED", 0.0, 0.0)
            if d == "SELL" and lc <= e - 0.5*(e-t1): return ("CANCELLED", 0.0, 0.0)
            return None
        mask = df["low"] <= e if d == "BUY" else df["high"] >= e
        after = df.loc[mask[mask].index[0]:]
        for _, b in after.iterrows():
            if d == "BUY":
                if b["low"] <= s: return ("SL", -abs(e-s)/pip, -1.0)
                if b["high"] >= t1: return ("TP1", abs(t1-e)/pip, float(sig["rr_tp1"]))
            else:
                if b["high"] >= s: return ("SL", -abs(s-e)/pip, -1.0)
                if b["low"] <= t1: return ("TP1", abs(e-t1)/pip, float(sig["rr_tp1"]))
        return ("ACTIVE", 0.0, 0.0)
