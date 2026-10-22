from __future__ import annotations
import logging, time
from datetime import timedelta
from typing import Optional
import pandas as pd, requests
from config import Settings
from utils import utcnow
logger = logging.getLogger(__name__)
CURRENCIES = ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD")
C_MAP = {"US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY", "AU": "AUD", "CA": "CAD", "CH": "CHF", "NZ": "NZD", "DE": "EUR", "FR": "EUR", "IT": "EUR", "ES": "EUR"}
class NewsFilter:
    def __init__(self, s: Settings):
        self.s = s; self._sent = {}; self._st = 0.0; self._sttl = 10800; self._cal = []; self._ct = 0.0; self._cttl = 3600
    def _fetch_sent(self) -> dict[str, dict]:
        k = self.s.fxnewsbias_api_key
        if not k: return {c: {"score": 50, "bias": "Neutral"} for c in CURRENCIES}
        try:
            r = requests.get("https://fxnewsbias.com/api/v1/sentiment", headers={"Authorization": f"Bearer {k}"}, timeout=5); d = r.json(); res = {}
            for i in d.get("data", []):
                c = str(i.get("currency", "")).upper()
                if c: res[c] = {"score": int(i.get("score", 50)), "bias": i.get("bias", "Neutral")}
            for c in CURRENCIES: res.setdefault(c, {"score": 50, "bias": "Neutral"})
            return res
        except: return {}
    def sentiment(self) -> dict[str, dict]:
        n = time.time()
        if self._sent and n - self._st < self._sttl: return self._sent
        f = self._fetch_sent()
        if f: self._sent = f; self._st = n
        elif not self._sent: self._sent = {c: {"score": 50, "bias": "Neutral"} for c in CURRENCIES}
        return self._sent
    def _fetch_cal(self) -> list[dict]:
        try:
            r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=8); raw = r.json(); ev = []
            for i in raw:
                imp = str(i.get("impact", "")).strip().title()
                if imp not in {"High", "Medium"}: continue
                dt = pd.Timestamp(i.get("date")); dt = dt.tz_localize("UTC") if dt.tzinfo is None else dt.tz_convert("UTC")
                co = str(i.get("country", "")).upper(); ev.append({"title": i.get("title", ""), "currency": C_MAP.get(co, co), "datetime_utc": dt.to_pydatetime(), "impact": imp, "forecast": i.get("forecast", ""), "previous": i.get("previous", "")})
            ev.sort(key=lambda x: x["datetime_utc"]); return ev
        except: return []
    def calendar(self) -> list[dict]:
        n = time.time()
        if self._cal and n - self._ct < self._cttl: return self._cal
        f = self._fetch_cal()
        if f: self._cal = f; self._ct = n
        return self._cal
    def refresh(self) -> None: self.sentiment(); self.calendar()
    def high_impact_within(self, c: str, m: int = 30) -> Optional[dict]:
        n, l = utcnow(), utcnow() + timedelta(minutes=m)
        for e in self.calendar():
            if e["currency"] != c or e["impact"] != "High": continue
            dt = pd.Timestamp(e["datetime_utc"]); dt = dt.tz_localize("UTC") if dt.tzinfo is None else dt
            if n <= dt <= l: return e
        return None
    def gate(self, p: str, d: str) -> tuple[bool, str, dict]:
        b, q = p[:3].upper(), p[3:].upper(); s = self.sentiment(); bs, qs = s.get(b, {}).get("score", 50), s.get(q, {}).get("score", 50)
        nb = "Neutral"
        if bs >= 60 and qs <= 45: nb = "Bullish"
        elif bs <= 40 and qs >= 60: nb = "Bearish"
        meta = {"base_score": bs, "quote_score": qs, "news_bias": nb}
        for c in (b, q):
            e = self.high_impact_within(c, 30)
            if e: return False, f"News {c}", meta
        if d == "BUY" and (bs < 40 or qs > 65): return False, "Sentimen", meta
        if d == "SELL" and (bs > 60 or qs < 35): return False, "Sentimen", meta
        n = utcnow()
        for c in (b, q):
            if self.high_impact_within(c, 15): return False, "Spread", meta
        if n.weekday() == 4 and n.hour >= 19: return False, "Jumat", meta
        return True, "OK", meta
    def get_major_news(self, days: int = 7) -> list[dict]:
        kw = ["CPI", "PPI", "FOMC", "INTEREST RATE", "NFP", "NON-FARM", "PMI", "GDP", "UNEMPLOYMENT"]; n, l = utcnow(), utcnow() + timedelta(days=days); res = []
        for e in self.calendar():
            if e["impact"] != "High" or not any(k in e["title"].upper() for k in kw): continue
            dt = pd.Timestamp(e["datetime_utc"]); dt = dt.tz_localize("UTC") if dt.tzinfo is None else dt
            if n <= dt <= l: res.append(e)
        return res
    def upcoming(self, h: int = 48) -> list[dict]:
        n, l = utcnow(), utcnow() + timedelta(hours=h); res = []
        for e in self.calendar():
            dt = pd.Timestamp(e["datetime_utc"]); dt = dt.tz_localize("UTC") if dt.tzinfo is None else dt
            if n <= dt <= l: res.append(e)
        return res[:30]
