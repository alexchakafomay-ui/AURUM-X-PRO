from __future__ import annotations
import asyncio, logging
from typing import Optional
import pandas as pd
from telegram import Bot
from utils import escape_html, fmt_price, next_market_open, pips_between, utcnow, weekend_remaining
logger = logging.getLogger(__name__)
class TelegramSender:
    def __init__(self, bot: Bot, chat_id: int): self.bot, self.chat_id = bot, chat_id
    async def send_message(self, text: str, chat_id: Optional[int] = None) -> None:
        target = chat_id or self.chat_id
        for a in range(3):
            try: await self.bot.send_message(chat_id=target, text=text, parse_mode="HTML", disable_web_page_preview=True); return
            except Exception as e: logger.warning("TG err %s", e); await asyncio.sleep(2**a)
    async def send_greeting(self, sentiment: dict, events: list[dict]) -> None:
        lines = [f"{'🟢' if i['score']>=60 else ('🔴' if i['score']<=40 else '⚪')} {c} <code>{i['score']}</code> ({i['bias']})" for c, i in sentiment.items()]
        news = "\n".join(f"🔔 <b>{pd.Timestamp(e['datetime_utc']).strftime('%H:%M UTC')}</b> | {e['currency']} — {e['title']}" for e in events[:5]) or "✅ Tidak ada berita high-impact hari ini."
        await self.send_message(f"☀️ <b>AURUM-X PRO — SELAMAT PAGI, BOS!</b>\n━━━━━━━━━━━━━━━━━━━━\n\nPagi Bos! Sistem institusional aktif. 😎\n\n📊 <b>Watchlist:</b> <i>EURUSD · GBPUSD · USDJPY · XAUUSD</i>\n\n🌍 <b>Sentimen:</b>\n{' | '.join(lines)}\n\n📰 <b>Berita:</b>\n{escape_html(news)}\n\n━━━━━━━━━━━━━━━━━━━━\nMempersiapkan setup presisi tinggi... 🎯")
    async def send_prealert(self, bias: str = "Mixed") -> None:
        await self.send_message(f"🟡 <b>AURUM-X PRO — PERSIAPAN</b>\n━━━━━━━━━━━━━━━━━━━━\n\nAnalisa 6 TF selesai.\n🧭 Bias: <b>{escape_html(bias)}</b>\n⏳ Sinyal dalam <b>2 menit</b>.\n\nBersiap Bos. 🎯")
    async def send_signal(self, signal: dict) -> None:
        pair, d, e, s, t1, t2 = signal["pair"], signal["direction"], signal["entry"], signal["sl"], signal["tp1"], signal["tp2"]
        p = lambda x: pips_between(pair, e, x)
        marks = [f"{tf}:{'✅' if (signal.get('tf_alignment',{}).get(tf) == ('Bullish' if d=='BUY' else 'Bearish')) else ('⚠️' if signal.get('tf_alignment',{}).get(tf) == 'Neutral' else '❌')}" for tf in ("D1", "H4", "H1", "M30", "M15", "M5")]
        text = (f"🏛️ <b>AURUM-X PRO | INSTITUTIONAL SIGNAL</b> 🏛️\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"💎 <b>Pair</b>       : <code>{pair}</code>\n"
                f"🧭 <b>Arah</b>       : {'🟢' if d=='BUY' else '🔴'} <b>{d}</b>\n\n"
                f"🎯 <b>Entry</b>      : <code>{fmt_price(pair, e)}</code>\n"
                f"🛑 <b>Stop Loss</b>  : <code>{fmt_price(pair, s)}</code> <i>(-{p(s):.0f} pips)</i>\n"
                f"✅ <b>Target 1</b>   : <code>{fmt_price(pair, t1)}</code> <i>(+{p(t1):.0f} pips | RR 1:{signal['risk_reward_tp1']:.2f})</i>\n"
                f"🚀 <b>Target 2</b>   : <code>{fmt_price(pair, t2)}</code> <i>(+{p(t2):.0f} pips | RR 1:{signal['risk_reward_tp2']:.2f})</i>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>Confidence</b> : {signal['confidence']}%\n"
                f"🔍 <b>Alignment</b>  : {' · '.join(marks)}\n\n"
                f"🗣️ <b>LAPORAN DEBAT AI:</b>\n"
                f"<i>{escape_html(signal.get('reasoning', '-'))}</i>\n\n"
                "━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ <b>Valid hingga:</b> {signal.get('valid_until', '-')[:16].replace('T', ' ')} UTC\n"
                f"⚠️ <i>Risiko 1-2% per trade. Bukan jaminan profit.</i>")
        await self.send_message(text)
    async def send_no_signal(self, reason: str = "") -> None:
        await self.send_message(f"⚪ <b>AURUM-X PRO — PASAR SEPI</b>\n━━━━━━━━━━━━━━━━━━━━\n\nBos, sistem sudah memindai market. Belum ada Smart Money Concepts (FVG/OB) yang valid saat ini. Menunggu momen yang lebih baik. 👀\n\n💡 <i>{escape_html(reason[:500])}</i>")
    async def send_weekend(self) -> None:
        d, h, m = weekend_remaining(); dt = next_market_open().strftime("%A, %d %B %Y")
        await self.send_message(f"🌙 <b>AURUM-X PRO — MARKET CLOSED</b>\n━━━━━━━━━━━━━━━━━━━━\n\nHalo Bos! Pasar tutup.\n🕐 <b>Buka:</b> {dt} 00:00 UTC\n⏳ <b>Sisa:</b> {d}h {h}j {m}m\n\nGunakan waktu untuk evaluasi:\n/stats | /weekly | /calendar\n\nSantai dulu Bos. 🚀")
    async def send_result(self, signal: dict, status: str, pips: float, r: float) -> None:
        if status == "TP1": await self.send_message(f"✅ <b>AURUM-X — TP1 HIT! 🎉</b>\n━━━━━━━━━━━━━━━━━━━━\n💎 {signal['pair']} | {signal['direction']} | <b>{pips:+.1f} pips</b> | RR 1:{r:.2f}\n\nMantap Bos! /stats")
        elif status == "TP2": await self.send_message(f"🏆 <b>AURUM-X — TP2 HIT! 🔥</b>\n━━━━━━━━━━━━━━━━━━━━\n💎 {signal['pair']} | {signal['direction']} | <b>{pips:+.1f} pips</b> | RR 1:{r:.2f}\n\nFull target! /stats")
        elif status == "SL": await self.send_message(f"🔴 <b>AURUM-X — SL HIT</b>\n━━━━━━━━━━━━━━━━━━━━\n💎 {signal['pair']} | {signal['direction']} | <b>{pips:+.1f} pips</b>\n\nTenang Bos, ini proses. 💪")
        elif status == "EXPIRED": await self.send_message(f"⚪ <b>SINYAL EXPIRED</b>\n💎 {signal['pair']} | Tidak tersentuh 2 jam.")
    async def send_calendar(self, events: list[dict]) -> None:
        if not events: await self.send_message("📅 <b>KALENDER</b>\nTidak ada berita penting 48 jam ke depan."); return
        lines = ["📅 <b>KALENDER 48 JAM</b>\n━━━━━━━━━━━━━━━━━━━━\n"] + [f"{'🔴' if e['impact']=='High' else '🟡'} <b>{pd.Timestamp(e['datetime_utc']).strftime('%d/%m %H:%M')}</b> | <b>{e['currency']}</b> | {escape_html(e['title'])}" for e in events]
        await self.send_message("\n".join(lines))
    async def send_major_news(self, events: list[dict]) -> None:
        if not events: await self.send_message("📰 <b>RADAR BERITA</b>\nAman! Tidak ada berita raksasa minggu ini."); return
        lines = ["📰 <b>RADAR BERITA BESAR</b>", "━━━━━━━━━━━━━━━━━━━━\n"]; now = utcnow()
        for e in events:
            dt = pd.Timestamp(e["datetime_utc"]); dt = dt.tz_localize("UTC") if dt.tzinfo is None else dt
            delta = dt - now
            time_str = f"<b>HARI INI</b> {dt.strftime('%H:%M')}" if delta.days == 0 else (f"<b>BESOK</b> {dt.strftime('%H:%M')}" if delta.days == 1 else f"<b>{delta.days} hari lagi</b>")
            lines.append(f"🚨 {time_str} | <b>{e['currency']}</b> | {escape_html(e['title'])}\n")
        await self.send_message("\n".join(lines))
