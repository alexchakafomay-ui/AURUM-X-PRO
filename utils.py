from __future__ import annotations
import html, json, math, re, threading, time
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import pandas as pd
UTC = timezone.utc

def utcnow() -> datetime: return datetime.now(UTC)
def market_is_open(dt: Optional[datetime] = None) -> bool:
    dt = dt or utcnow(); wd = dt.weekday()
    if wd == 4 and dt.hour >= 21: return False
    if wd in (5, 6): return False
    return True
def next_market_open(dt: Optional[datetime] = None) -> datetime:
    dt = dt or utcnow(); days = (0 - dt.weekday()) % 7
    cand = (dt + timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
    if cand <= dt: cand += timedelta(days=7)
    return cand
def weekend_remaining(dt: Optional[datetime] = None) -> tuple[int, int, int]:
    dt = dt or utcnow(); delta = next_market_open(dt) - dt
    ts = max(0, int(delta.total_seconds())); d, r = divmod(ts, 86400); h, r = divmod(r, 3600); m, _ = divmod(r, 60)
    return d, h, m
def pip_size(pair: str) -> float: return 0.01 if pair.upper().endswith("JPY") else (0.1 if pair.upper() == "XAUUSD" else 0.0001)
def price_decimals(pair: str) -> int: return 3 if pair.upper().endswith("JPY") else (2 if pair.upper() == "XAUUSD" else 5)
def fmt_price(pair: str, value: float) -> str:
    if value is None or math.isnan(value): return "-"
    return f"{value:.{price_decimals(pair)}f}"
def pips_between(pair: str, a: float, b: float) -> float: return abs(a - b) / pip_size(pair)
def rr(entry: float, sl: float, tp: float) -> float:
    risk = abs(entry - sl); return 0.0 if risk <= 0 else abs(tp - entry) / risk
def escape_html(text: Any) -> str: return html.escape(str(text), quote=False)
def extract_json(text: str) -> Optional[dict]:
    if not text: return None
    c = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE); c = re.sub(r"\s*```$", "", c)
    s, e = c.find("{"), c.rfind("}")
    if s == -1 or e == -1: return None
    try: return json.loads(c[s:e+1])
    except: return None
def to_db_ts(value: Any) -> str:
    ts = pd.Timestamp(value) if isinstance(value, (str, datetime)) else pd.Timestamp.now(tz="UTC")
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%d %H:%M:%S")
def parse_db_ts(value: str) -> pd.Timestamp:
    ts = pd.Timestamp(value); return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
class RateLimiter:
    def __init__(self, max_calls: int, period: float):
        self.max, self.period = max_calls, period; self._calls = deque(); self._lock = threading.Lock()
    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= self.period: self._calls.popleft()
                if len(self._calls) < self.max: self._calls.append(now); return
                st = self.period - (now - self._calls[0]) + 0.05
            time.sleep(max(0.05, st))
