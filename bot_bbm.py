import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# State untuk percakapan bot
CHOOSING_BBM, INPUT_DATA = range(2)

# --- 1. INISIALISASI DATABASE ---
def init_db():
    conn = sqlite3.connect('bbm_tracker.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bbm_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tanggal TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_rupiah REAL,
            harga_liter REAL,
            liter REAL,
            odometer REAL,
            jenis_bbm TEXT
        )
    ''')
    conn.commit()
    conn.close()

# --- 2. PERINTAH DASAR ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Selamat datang di Bot Pencatat BBM 🚗⛽\n\n"
        "Gunakan perintah /catat untuk mulai mencatat pengisian bensin."
    )

async def start_catat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Tombol pilihan jenis BBM
    keyboard = [
        [
            InlineKeyboardButton("Pertalite", callback_data='Pertalite'),
            InlineKeyboardButton("Pertamax", callback_data='Pertamax')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Pilih jenis BBM yang Anda isi:", reply_markup=reply_markup)
    return CHOOSING_BBM

async def bbm_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Simpan pilihan jenis BBM ke session
    context.user_data['jenis_bbm'] = query.data
    
    await query.edit_message_text(
        text=f"Anda memilih: **{query.data}**\n\n"
             f"Silakan kirimkan data dengan format (pisahkan dengan spasi):\n"
             f"`[Total Rupiah] [Harga per Liter] [KM Mobil]`\n\n"
             f"*Contoh:* `150000 13300 45250`",
        parse_mode='Markdown'
    )
    return INPUT_DATA

# --- 3. PEMROSESAN DATA & PERHITUNGAN OTOMATIS ---
async def process_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.split()
    
    if len(text) != 3:
        await update.message.reply_text(
            "⚠️ Format salah! Masukkan tepat 3 angka pisahkan dengan spasi.\n"
            "Contoh: `150000 13300 45250`", 
            parse_mode='Markdown'
        )
        return INPUT_DATA

    try:
        total_rupiah = float(text[0])
        harga_liter = float(text[1])
        odometer = float(text[2])
        jenis_bbm = context.user_data.get('jenis_bbm', 'Unknown')
        
        # Konversi Rupiah ke Liter otomatis
        liter = total_rupiah / harga_liter

        # Koneksi ke database untuk simpan dan cek riwayat sebelumnya
        conn = sqlite3.connect('bbm_tracker.db')
        cursor = conn.cursor()
        
        # Ambil Odometer dari pengisian terakhir user ini
        cursor.execute("SELECT odometer FROM bbm_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
        last_log = cursor.fetchone()
        
        # Simpan data pengisian baru ke database
        cursor.execute('''
            INSERT INTO bbm_logs (user_id, total_rupiah, harga_liter, liter, odometer, jenis_bbm)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, total_rupiah, harga_liter, liter, odometer, jenis_bbm))
        conn.commit()
        conn.close()

        # Hitung jarak dan konsumsi BBM jika ada riwayat sebelumnya
        analisis_text = ""
        if last_log:
            km_lama = last_log[0]
            jarak = odometer - km_lama
            if jarak > 0 and liter > 0:
                kml = jarak / liter
                analisis_text = (
                    f"\n📊 **Analisis Perjalanan:**\n"
                    f"• Jarak Tempuh: {jarak:,.1f} KM\n"
                    f"• Efisiensi BBM: **{kml:.2f} KM / Liter**"
                )
            elif jarak <= 0:
                analisis_text = "\n⚠️ *Catatan: KM saat ini lebih kecil atau sama dengan KM sebelumnya.*"

        # Susun pesan balasan ke Telegram
        response = (
            f"✅ **Pencatatan BBM Berhasil!**\n\n"
            f"• Jenis BBM: {jenis_bbm}\n"
            f"• Total Bayar: Rp {total_rupiah:,.0f}\n"
            f"• Harga/Liter: Rp {harga_liter:,.0f}\n"
            f"• Hasil Konversi: **{liter:.2f} Liter**\n"
            f"• Odometer: {odometer:,.0f} KM\n"
            f"{analisis_text}"
        )
        
        await update.message.reply_text(response, parse_mode='Markdown')
        return ConversationHandler.END

    except ValueError:
        await update.message.reply_text("⚠️ Mohon masukkan angka yang valid (gunakan angka saja)!")
        return INPUT_DATA

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pencatatan dibatalkan.")
    return ConversationHandler.END

# --- 4. MENJALANKAN BOT ---
if __name__ == '__main__':
    init_db()
    
    # Ganti teks di bawah ini dengan TOKEN asli dari BotFather
    TOKEN = "8849388611:AAEjQIUgp3laK1VMqPGIannlX-Hg4TTh5EY"
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('catat', start_catat)],
        states={
            CHOOSING_BBM: [CallbackQueryHandler(bbm_button_click)],
            INPUT_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_input)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv_handler)
    
    print("Bot BBM sedang berjalan...")
    app.run_polling()