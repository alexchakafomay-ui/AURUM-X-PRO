from __future__ import annotations
import asyncio, logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from ai_analyzer import AIAnalyzer
from config import Settings
from data_fetcher import DataFetcher
from logger import Database
from news_filter import NewsFilter
from scheduler import AurumScheduler
from stats import format_stats, format_weekly
from telegram_sender import TelegramSender
from tracker import SignalTracker
from utils import market_is_open

logger = logging.getLogger(__name__)

def setup_logging(l: str) -> None:
    logging.basicConfig(format="%(asctime)s | %(levelname)s | %(name)s | %(message)s", level=getattr(logging, l.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)

def auth(u: Update, s: Settings) -> bool: 
    return bool(u.effective_chat and u.effective_chat.id == s.telegram_chat_id)

async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    
    status_pasar = "BUKA" if market_is_open() else "TUTUP"
    
    # Teks /start sudah diupdate (fitur /scan dihapus)
    text = (
        "💎 <b>AURUM-X PRO</b>\n\n"
        "Halo Bos! Sistem institusional sudah siap melayani. 😎\n\n"
        f"🟢 Pasar sedang <b>{status_pasar}</b>.\n"
        "Mode: <b>PAPER TRADING</b> (Aman).\n\n"
        "<b>📊 TRADING & ANALISA</b>\n"
        "🔹 /stats — Laporan performa trading\n\n"
        "<b>📰 BERITA EKONOMI</b>\n"
        "🔹 /calendar — Jadwal rilis data\n"
        parse "🔹 /news —_mode Radar berita high-impact\n\n=""
        "<b>HTML⚙️ SISTEM</b")

>\n"
        "🔹async /pause — Istirahatkan bot\n"
        "🔹 /resume — Bangunkan bot\n"
        "🔹 /status — Cek kesehatan bot\n\n"
        "<i>AURUM-X PRO siap mengawal trading Bos 24/5.</i> 🚀"
    )
    
    await u.message.reply_text(text, parse_mode="HTML")

# Fitur cmd_scan sudah dihapus total dari sini

async def cmd_stats(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await u.message.reply_text(format_stats(c.bot_data["db"].get_stats()), parse_mode="HTML")

async def cmd_weekly(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await u.message.reply_text(format_weekly(c.bot_data["db"].get_stats(7)), def cmd_calendar(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await c.bot_data["sender"].send_calendar(await asyncio.to_thread(c.bot_data["news"].upcoming, 48))

async def cmd_news(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await c.bot_data["sender"].send_major_news(await asyncio.to_thread(c.bot_data["news"].get_major_news, 7))

async def cmd_pause(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    c.bot_data["db"].set_paused(True)
    await u.message.reply_text("⏸ <b>AURUM-X PRO Dijeda.</b>\nSinyal baru tidak akan dikirim sampai /resume.", parse_mode="HTML")

async def cmd_resume(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    c.bot_data["db"].set_paused(False)
    await u.message.reply_text("▶️ <b>AURUM-X PRO Aktif Kembali.</b>\nSistem siap menganalisa pasar.", parse_mode="HTML")

async def cmd_status(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s, db = c.bot_data["settings"], c.bot_data["db"]
    if not auth(u, s): return
    await u.message.reply_text(f"⚙️ <b>STATUS SISTEM</b>\n\nBot: <b>{'PAUSED' if db.is_paused() else 'ACTIVE'}</b>\nMarket: <b>{'BUKA' if market_is_open() else 'TUTUP'}</b>\nSinyal hari ini: <b>{db.count_signals_today()}</b> / {s.max_signals_per_day}\nOpen trade: <b>{db.open_trades_count()}</b> / {s.max_open_trades}", parse_mode="HTML")

async def err_handler(u: object, c: ContextTypes.DEFAULT_TYPE) -> None: 
    logger.error("Error: %s", c.error)

async def post_init(app: Application) -> None:
    app.bot_data["scheduler"].schedule(app)
    logger.info("AURUM-X PRO scheduler aktif.")

def main() -> None:
    settings = Settings()
    setup_logging(settings.log_level)
    settings.validate()
    
    db, f, n, a = Database(settings.db_path), DataFetcher(settings), NewsFilter(settings), AIAnalyzer(settings)
    app = Application.builder().token(settings.telegram_token).post_init(post_init).build()
    
    snd = TelegramSender(app.bot, settings.telegram_chat_id)
    t = SignalTracker(db, f, snd)
    sch = AurumScheduler(settings, db, f, n, a, snd, t)
    
    app.bot_data.update({
        "settings": settings, "db": db, "fetcher": f, "news": n, 
        "analyzer": a, "sender": snd, "tracker": t, "scheduler": sch
    })
    
    # Daftar perintah (cmd_scan sudah dihapus dari list ini)
    for cmd, fn in [
        ("start", cmd_start), ("stats", cmd_stats), 
        ("weekly", cmd_weekly), ("calendar", cmd_calendar), ("news", cmd_news), 
        ("pause", cmd_pause), ("resume", cmd_resume), ("status", cmd_status)
    ]:
        app.add_handler(CommandHandler(cmd, fn))
        
    app.add_error_handler(err_handler)
    logger.info("AURUM-X PRO starting polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__": main()
