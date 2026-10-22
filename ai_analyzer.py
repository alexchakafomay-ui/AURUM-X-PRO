from __future__ import annotations
import json, logging
from datetime import timedelta
from typing import Optional
from config import Settings
from utils import extract_json, utcnow
logger = logging.getLogger(__name__)
SYS_P = """Kamu adalah AURUM-X PRO, Hedge Fund Manager AI Institusional.
Cari peluang Smart Money Concepts (Liquidity Sweep, FVG, OB).
Debat: Agen Bull vs Agen Bear, diputuskan Risk Manager.
Output JSON murni. Reasoning 4-6 kalimat narasi debat profesional."""
USR_P = """Format JSON: {{"bot":"AURUM-X PRO","timestamp_utc":"","pair":"","direction":"BUY"|"SELL"|"NO_SIGNAL","confidence":0,"entry":0,"sl":0,"tp1":0,"tp2":0,"risk_reward_tp1":0,"risk_reward_tp2":0,"news_bias":"","news_score":{{"base":0,"quote":0}},"tf_alignment":{{}},"key_levels":{{"support":0,"resistance":0}},"reasoning":"Laporan Debat: ...","valid_until":"","risk_note":"Risiko 1-2%."}}
SNAP: {s}
CAND: {c}
NEWS: {n}"""
class AIAnalyzer:
    def __init__(self, s: Settings): self.s = s
    def _call(self, url: str, k: str, m: str, msgs: list) -> str:
        from openai import OpenAI
        cl = OpenAI(base_url=url, api_key=k, timeout=self.s.ai_timeout)
        try: r = cl.chat.completions.create(model=m, messages=msgs, temperature=0.4, max_tokens=1500, response_format={"type": "json_object"})
        except: r = cl.chat.completions.create(model=m, messages=msgs, temperature=0.4, max_tokens=1500)
        return r.choices[0].message.content or ""
    def analyze(self, c: dict, s: dict, n: dict) -> dict:
        if c is None: return self.no_signal("-", "Tidak ada kandidat.")
        p = USR_P.format(s=json.dumps(s)[:18000], c=json.dumps(c)[:4000], n=json.dumps(n)[:2000])
        m = [{"role": "system", "content": SYS_P}, {"role": "user", "content": p}]; raw = ""
        try:
            if self.s.openrouter_api_key: raw = self._call("https://openrouter.ai/api/v1", self.s.openrouter_api_key, self.s.openrouter_model, m)
            else: return self.fallback(c, n)
        except Exception as e:
            logger.warning("AI err: %s", e); return self.fallback(c, n)
        pr = extract_json(raw)
        if not pr: return self.fallback(c, n)
        f = self.validate(pr, c, n)
        return f if f else self.fallback(c, n)
    def validate(self, d: dict, c: dict, n: dict) -> Optional[dict]:
        dr = str(d.get("direction", "")).upper()
        if dr == "NO_SIGNAL": return self.no_signal(c["pair"], str(d.get("reasoning", "AI NO_SIGNAL.")))
        if dr not in {"BUY", "SELL"} or dr != c["direction"] or str(d.get("pair", "")).upper() != c["pair"]: return None
        try: e, s, t1, t2 = float(d["entry"]), float(d["sl"]), float(d["tp1"]), float(d["tp2"]); cf = int(d.get("confidence", 0))
        except: return None
        if dr == "BUY" and not (s < e < t1 < t2): return None
        if dr == "SELL" and not (t2 < t1 < e < s): return None
        rk = abs(e - s)
        if rk <= 0: return None
        r1, r2 = abs(t1 - e) / rk, abs(t2 - e) / rk
        if r1 < 1.2 or r2 < 2.5 or cf < 65: return None
        nw = utcnow()
        return {"bot": "AURUM-X PRO", "timestamp_utc": nw.isoformat(), "pair": c["pair"], "direction": dr, "confidence": min(98, cf), "entry": e, "sl": s, "tp1": t1, "tp2": t2, "risk_reward_tp1": round(r1, 2), "risk_reward_tp2": round(r2, 2), "news_bias": d.get("news_bias", n.get("news_bias", "Neutral")), "news_score": d.get("news_score", {"base": n.get("base_score", 50), "quote": n.get("quote_score", 50)}), "tf_alignment": d.get("tf_alignment", c["tf_alignment"]), "key_levels": d.get("key_levels", c["key_levels"]), "reasoning": str(d.get("reasoning", c["reasoning"]))[:1500], "valid_until": (nw + timedelta(hours=self.s.signal_valid_hours)).isoformat(), "risk_note": "Risiko 1-2% per trade."}
    def fallback(self, c: dict, n: dict) -> dict:
        nw = utcnow()
        return {"bot": "AURUM-X PRO", "timestamp_utc": nw.isoformat(), "pair": c["pair"], "direction": c["direction"], "confidence": min(80, int(c["confidence"])), "entry": float(c["entry"]), "sl": float(c["sl"]), "tp1": float(c["tp1"]), "tp2": float(c["tp2"]), "risk_reward_tp1": float(c["risk_reward_tp1"]), "risk_reward_tp2": float(c["risk_reward_tp2"]), "news_bias": n.get("news_bias", "Neutral"), "news_score": {"base": n.get("base_score", 50), "quote": n.get("quote_score", 50)}, "tf_alignment": c["tf_alignment"], "key_levels": c["key_levels"], "reasoning": "Fallback: " + c["reasoning"], "valid_until": (nw + timedelta(hours=self.s.signal_valid_hours)).isoformat(), "risk_note": "Risiko 1-2% per trade."}
    @staticmethod
    def no_signal(p: str, r: str) -> dict:
        n = utcnow(); return {"bot": "AURUM-X PRO", "timestamp_utc": n.isoformat(), "pair": p, "direction": "NO_SIGNAL", "confidence": 0, "entry": None, "sl": None, "tp1": None, "tp2": None, "risk_reward_tp1": None, "risk_reward_tp2": None, "news_bias": "Neutral", "news_score": {"base": 50, "quote": 50}, "tf_alignment": {}, "key_levels": {}, "reasoning": r[:1500], "valid_until": n.isoformat(), "risk_note": "Risiko 1-2%."}
