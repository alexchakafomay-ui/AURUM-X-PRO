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
