from __future__ import annotations
import json, logging
from datetime import timedelta
from typing import Optional
from config import Settings
from utils import extract_json, utcnow

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Kamu adalah AURUM-X, sebuah HEDGE FUND MANAGER AI INSTITUSIONAL.
Tugasmu bukan sekadar memvalidasi, tapi mencari peluang terbaik (Smart Money Concepts).
Lakukan analisa mendalam: Liquidity Sweep, FVG (Fair Value Gap), Order Block, dan Market Structure.

PERDEBATAN INTERNAL:
- AGEN BULL: Cari alasan kuat untuk BUY.
- AGEN BEAR: Cari alasan kuat untuk SELL.
- RISK MANAGER: Pastikan RR minimal 1:1.2 dan SL logis tidak kena spread.

ATURAN OUTPUT:
Kembalikan JSON murni tanpa markdown.
Field "reasoning" WAJIB berisi narasi 4-6 kalimat yang menceritakan hasil debat Agen Bull, Agen Bear, dan Risk Manager. Jadikan bahasa Indonesia yang sangat profesional seperti laporan bank investasi.
"""

USER_PROMPT_TEMPLATE = """Validasi kandidat sinyal dari rule-engine.
FORMAT JSON WAJIB:
{{
  "bot": "AURUM-X PRO", "timestamp_utc": "ISO8601", "pair": "EURUSD", "direction": "BUY"|"SELL"|"NO_SIGNAL",
  "confidence": 0-100, "entry": number, "sl": number, "tp1": number, "tp2": number,
  "risk_reward_tp1": number, "risk_reward_tp2": number, "news_bias": "Bullish"|"Bearish"|"Neutral",
  "news_score": {{"base": number, "quote": number}},
  "tf_alignment": {{"D1": "...", "H4": "...", "H1": "...", "M30": "...", "M15": "...", "M5": "..."}},
  "key_levels": {{"support": number, "resistance": number}},
  "reasoning": "Laporan Debat: Agen Bull menyatakan... Agen Bear menyanggah... Risk Manager memvalidasi...",
  "valid_until": "ISO8601", "risk_note": "Risiko 1-2%. Bukan jaminan profit."
}}
SNAPSHOT DATA PASAR:
{snapshot}
KANDIDAT SINYAL:
{candidate}
NEWS META:
{news_meta}
"""

class AIAnalyzer:
    def __init__(self, settings: Settings): self.settings = settings

    def _call_api(self, url: str, key: str, model: str, messages: list) -> str:
        from openai import OpenAI
        client = OpenAI(base_url=url, api_key=key, timeout=self.settings.ai_timeout)
        try:
            res = client.chat.completions.create(model=model, messages=messages, temperature=0.4, max_tokens=1500, response_format={"type": "json_object"})
        except:
            res = client.chat.completions.create(model=model, messages=messages, temperature=0.4, max_tokens=1500)
        return res.choices[0].message.content or ""

    def analyze(self, candidate: dict, snapshot: dict, news_meta: dict) -> dict:
        if candidate is None: return self.no_signal("-", "Tidak ada kandidat yang memenuhi syarat rule-engine.")
        prompt = USER_PROMPT_TEMPLATE.format(snapshot=json.dumps(snapshot)[:18000], candidate=json.dumps(candidate)[:4000], news_meta=json.dumps(news_meta)[:2000])
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
        raw = ""
        try:
            if self.settings.openrouter_api_key:
                raw = self._call_api("https://openrouter.ai/api/v1", self.settings.openrouter_api_key, self.settings.openrouter_model, msgs)
            else: return self.fallback(candidate, news_meta)
        except Exception as e:
            logger.warning("AI gagal: %s", e); return self.fallback(candidate, news_meta)
        parsed = extract_json(raw)
        if not parsed: return self.fallback(candidate, news_meta)
        final = self.validate(parsed, candidate, news_meta)
        return final if final else self.fallback(candidate, news_meta)

    def validate(self, data: dict, candidate: dict, news_meta: dict) -> Optional[dict]:
        direction = str(data.get("direction", "")).upper()
        if direction == "NO_SIGNAL": return self.no_signal(candidate["pair"], str(data.get("reasoning", "AI memilih NO_SIGNAL.")))
        if direction not in {"BUY", "SELL"} or direction != candidate["direction"] or str(data.get("pair", "")).upper() != candidate["pair"]: return None
        try:
            entry, sl, tp1, tp2 = float(data["entry"]), float(data["sl"]), float(data["tp1"]), float(data["tp2"])
            confidence = int(data.get("confidence", 0))
        except: return None
        if direction == "BUY" and not (sl < entry < tp1 < tp2): return None
        if direction == "SELL" and not (tp2 < tp1 < entry < sl): return None
        risk = abs(entry - sl)
        if risk <= 0: return None
        rr1, rr2 = abs(tp1 - entry) / risk, abs(tp2 - entry) / risk
        if rr1 < 1.2 or rr2 < 2.5 or confidence < 65: return None
        now = utcnow()
        return {
            "bot": "AURUM-X PRO", "timestamp_utc": now.isoformat(), "pair": candidate["pair"], "direction": direction,
            "confidence": min(98, confidence), "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2,
            "risk_reward_tp1": round(rr1, 2), "risk_reward_tp2": round(rr2, 2),
            "news_bias": data.get("news_bias", news_meta.get("news_bias", "Neutral")),
            "news_score": data.get("news_score", {"base": news_meta.get("base_score", 50), "quote": news_meta.get("quote_score", 50)}),
            "tf_alignment": data.get("tf_alignment", candidate["tf_alignment"]), "key_levels": data.get("key_levels", candidate["key_levels"]),
            "reasoning": str(data.get("reasoning", candidate["reasoning"]))[:1500],
            "valid_until": (now + timedelta(hours=self.settings.signal_valid_hours)).isoformat(),
            "risk_note": "Risiko 1-2% per trade. Bukan jaminan profit."
        }

    def fallback(self, candidate: dict, news_meta: dict) -> dict:
        now = utcnow()
        return {
            "bot": "AURUM-X PRO", "timestamp_utc": now.isoformat(), "pair": candidate["pair"], "direction": candidate["direction"],
            "confidence": min(80, int(candidate["confidence"])), "entry": float(candidate["entry"]), "sl": float(candidate["sl"]),
            "tp1": float(candidate["tp1"]), "tp2": float(candidate["tp2"]), "risk_reward_tp1": float(candidate["risk_reward_tp1"]),
            "risk_reward_tp2": float(candidate["risk_reward_tp2"]), "news_bias": news_meta.get("news_bias", "Neutral"),
            "news_score": {"base": news_meta.get("base_score", 50), "quote": news_meta.get("quote_score", 50)},
            "tf_alignment": candidate["tf_alignment"], "key_levels": candidate["key_levels"],
            "reasoning": "Sistem Fallback (AI Offline): " + candidate["reasoning"], 
            "valid_until": (now + timedelta(hours=self.settings.signal_valid_hours)).isoformat(), "risk_note": "Risiko 1-2% per trade."
        }

    @staticmethod
    def no_signal(pair: str, reasoning: str) -> dict:
        now = utcnow()
        return {"bot": "AURUM-X PRO", "timestamp_utc": now.isoformat(), "pair": pair, "direction": "NO_SIGNAL", "confidence": 0, "entry": None, "sl": None, "tp1": None, "tp2": None, "risk_reward_tp1": None, "risk_reward_tp2": None, "news_bias": "Neutral", "news_score": {"base": 50, "quote": 50}, "tf_alignment": {}, "key_levels": {}, "reasoning": reasoning[:1500], "valid_until": now.isoformat(), "risk_note": "Risiko 1-2% per trade."}
