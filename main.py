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
    
    text = "💎 <b>AURUM-X PRO</b>\n\n"
    text += "Halo Bos! Sistem institusional sudah siap melayani. 😎\n\n"
    text += f"🟢 Pasar sedang <b>{status_pasar}</b>.\n"
    text += "Mode: <b>PAPER TRADING</b> (Aman).\n\n"
    text += "<b>📊 TRADING & ANALISA</b>\n"
    text += "🔹 /signal EURUSD — Minta analisa 1 pair\n"
    text += "🔹 /stats — Laporan performa trading\n"
    text += "🔹 /jadwal — Lihat jam analisa otomatis\n\n"
    text += "<b>📰 BERITA EKONOMI</b>\n"
    text += "🔹 /calendar — Jadwal rilis data\n"
    text += "🔹 /news — Radar berita high-impact\n\n"
    text += "<b>⚙️ SISTEM</b>\n"
    text += "🔹 /pause — Istirahatkan bot\n"
    text += "🔹 /resume — Bangunkan bot\n"
    text += "🔹 /status — Cek kesehatan bot\n\n"
    text += "<i>AURUM-X PRO siap mengawal trading Bos 24/5.</i> 🚀"
    
    await u.message.reply_text(text, parse_mode="HTML")

async def cmd_signal(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    
    if not c.args:
        await u.message.reply_text("⚠️ <b>Format salah.</b>\nContoh: <code>/signal EURUSD</code>", parse_mode="HTML")
        return
        
    pair = c.args[0].upper()
    if pair not in s.watchlist:
        await u.message.reply_text(f"⚠️ Pair <b>{pair}</b> tidak ada di watchlist Bos.", parse_mode="HTML")
        return
        
    await u.message.reply_text(f"⏳ <b>Meminta analisa manual untuk {pair}...</b>", parse_mode="HTML")
    res = await c.bot_data["scheduler"].manual_analysis(pair)
    if res not in ("SIGNAL_SENT", "NO_SIGNAL"):
        await u.message.reply_text(f"❌ {res}")

async def cmd_jadwal(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    
    text = "🗓️ <b>JADWAL & CARA KERJA</b>\n\n"
    text += "Sistem ini dirancang untuk <b>memantau pasar secara terus-menerus (real-time)</b>.\n\n"
    text += "⏱️ <b>Setiap 30 Menit:</b> Bot memindai 8 pair untuk mencari setup valid.\n"
    text += "⏱️ <b>Setiap 5 Menit:</b> Bot memantau harga untuk memastikan apakah TP/SL sudah tersentuh.\n\n"
    text += "🛑 <b>Rem Keamanan:</b>\n"
    text += "Meskipun bot memantau terus, bot <b>maksimal hanya mengirim 6 sinyal per hari</b> untuk mencegah Bos <i>overlot</i>.\n\n"
    text += "💡 Jika pasar sedang sepi, bot akan diam. Jika Bos ingin memaksa cek 1 pair, gunakan:\n"
    text += "<code>/signal PAIR</code>"
    
    await u.message.reply_text(text, parse_mode="HTML")

async def cmd_stats(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await u.message.reply_text(format_stats(c.bot_data["db"].get_stats()), parse_mode="HTML")

async def cmd_weekly(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    await u.message.reply_text(format_weekly(c.bot_data["db"].get_stats(7)), parse_mode="HTML")

async def cmd_calendar(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
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
    await u.message.reply_text("⏸ <b>AURUM-X PRO Dijeda.</b>\nSinyal otomatis dihentikan.", parse_mode="HTML")

async def cmd_resume(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s = c.bot_data["settings"]
    if not auth(u, s): return
    c.bot_data["db"].set_paused(False)
    await u.message.reply_text("▶️ <b>AURUM-X PRO Aktif Kembali.</b>", parse_mode="HTML")

async def cmd_status(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    s, db = c.bot_data["settings"], c.bot_data["db"]
    if not auth(u, s): return
    
    is_analyzing = db.get_state("is_analyzing", "0") == "1"
    status_analisa = "🧠 <b>Sedang Menganalisa Pasar...</b>" if is_analyzing else "💤 Standby (Menunggu Jadwal)"
    bot_status = "PAUSED" if db.is_paused() else "ACTIVE"
    
    text = f"⚙️ <b>STATUS SISTEM</b>\n\n"
    text += f"Bot: <b>{bot_status}</b>\n"
    text += f"Aktivitas: {status_analisa}\n"
    text += f"Market: <b>{'BUKA' if market_is_open() else 'TUTUP'}</b>\n"
    text += f"Sinyal hari ini: <b>{db.count_signals_today()}</b> / {s.max_signals_per_day}\n"
    text += f"Open trade: <b>{db.open_trades_count()}</b> / {s.max_open_trades}\n\n"
    text += "Gunakan /jadwal untuk melihat jam analisa."
    
    await u.message.reply_text(text, parse_mode="HTML")

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
    
    for cmd, fn in [
        ("start", cmd_start), ("signal", cmd_signal), ("jadwal", cmd_jadwal), 
        ("stats", cmd_stats), ("weekly", cmd_weekly), ("calendar", cmd_calendar), 
        ("news", cmd_news), ("pause", cmd_pause), ("resume", cmd_resume), ("status", cmd_status)
    ]:
        app.add_handler(CommandHandler(cmd, fn))
        
    app.add_error_handler(err_handler)
    logger.info("AURUM-X PRO starting polling...")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__": main()
