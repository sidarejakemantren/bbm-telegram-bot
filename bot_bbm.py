import logging
import os
import sqlite3
import threading
from datetime import datetime
from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# --- 1. SET UP FLASK UNTUK RENDER WEB SERVICE ---
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Bot BBM Keluarga 24/7 Running Active!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host='0.0.0.0', port=port)

# --- 2. BOT TELEGRAM CODE ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# DAFTAR ID TELEGRAM KELUARGA (WHITELIST)
ALLOWED_USER_IDS = [
    8849388611,  # <--- Ganti/tambahkan ID Anda di sini
]

DB_NAME = 'bbm_mobil.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pengisian_bbm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            pengguna TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            odometer INTEGER NOT NULL,
            total_harga REAL NOT NULL,
            harga_per_liter REAL NOT NULL,
            liter REAL NOT NULL,
            biaya REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

TOKEN = '8849388611:AAEjQIUgp3laK1VMqPGIannlX-Hg4TTh5EY'

def cek_akses(update: Update) -> bool:
    return update.effective_user.id in ALLOWED_USER_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update):
        await update.message.reply_text("⛔ Maaf, bot ini privat untuk keluarga.")
        return
    user = update.effective_user.first_name
    pesan = (
        f"Halo {user}! Bot Catatan BBM Mobil Aktif.\n\n"
        "🚗 **Format Input:**\n`/isi [odometer] [total_harga] [harga_liter]`\n\n"
        "📌 **Perintah:**\n/riwayat | /rekap | /reset"
    )
    await update.message.reply_text(pesan, parse_mode='Markdown')

async def isi_bbm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update):
        return
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Format: `/isi [odometer] [total_harga] [harga_liter]`", parse_mode='Markdown')
        return
    try:
        odometer = int(args[0].replace('.', '').replace(',', ''))
        total_harga = float(args[1].replace('.', '').replace(',', ''))
        harga_per_liter = float(args[2].replace('.', '').replace(',', ''))

        user = update.effective_user
        nama_pengguna = user.first_name or user.username or "Pengguna"
        user_id = user.id
        liter = total_harga / harga_per_liter
        tanggal = datetime.now().strftime("%Y-%m-%d %H:%M")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT odometer FROM pengisian_bbm ORDER BY id DESC LIMIT 1')
        last_row = cursor.fetchone()
        
        cursor.execute('''
            INSERT INTO pengisian_bbm (tanggal, pengguna, user_id, odometer, total_harga, harga_per_liter, liter, biaya)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (tanggal, nama_pengguna, user_id, odometer, total_harga, harga_per_liter, liter, total_harga))
        conn.commit()
        conn.close()

        info_konsumsi = ""
        if last_row:
            jarak = odometer - last_row[0]
            if jarak > 0 and liter > 0:
                info_konsumsi = f"📈 Konsumsi: **{jarak / liter:.2f} km/L** (Jarak: {jarak} km)\n"

        pesan_sukses = (
            "✅ **Berhasil Dicatat!**\n\n"
            f"📅 Tanggal: {tanggal}\n👤 Pengisi: **{nama_pengguna}**\n"
            f"🚗 Odometer: {odometer:,} km\n💰 Total: Rp {total_harga:,.0f}\n"
            f"⛽ Liter: **{liter:.2f} L**\n{info_konsumsi}"
        )
        await update.message.reply_text(pesan_sukses, parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("⚠️ Gagal memproses angka. Pastikan format angka benar.")

async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT tanggal, pengguna, odometer, liter, biaya FROM pengisian_bbm ORDER BY id DESC LIMIT 5')
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📁 Belum ada data.")
        return
    teks = "📜 **5 Riwayat Terakhir:**\n\n"
    for r in rows:
        teks += f"📅 {r[0]} | 👤 **{r[1]}**\n🚗 {r[2]:,} km | ⛽ {r[3]:.2f} L | 💰 Rp {r[4]:,.0f}\n---\n"
    await update.message.reply_text(teks, parse_mode='Markdown')

async def rekap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*), SUM(liter), SUM(biaya), MIN(odometer), MAX(odometer) FROM pengisian_bbm')
    total_entri, total_liter, total_biaya, min_km, max_km = cursor.fetchone()
    conn.close()

    if not total_entri:
        await update.message.reply_text("📊 Belum ada data.")
        return

    jarak_tempuh = (max_km - min_km) if (max_km and min_km and max_km > min_km) else 0
    rata = (jarak_tempuh / total_liter) if (total_liter and total_liter > 0 and jarak_tempuh > 0) else 0

    teks = (
        "📊 **REKAP BBM MOBIL**\n\n"
        f"🔢 Pengisian: {total_entri} kali\n"
        f"⛽ Total BBM: {total_liter:.2f} Liter\n"
        f"💰 Total Pengeluaran: Rp {total_biaya:,.0f}\n"
        f"🛣️ Jarak: {jarak_tempuh:,} km\n"
        f"📈 Rata-rata: **{rata:.2f} km/L**"
    )
    await update.message.reply_text(teks, parse_mode='Markdown')

async def reset_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM pengisian_bbm')
    conn.commit()
    conn.close()
    await update.message.reply_text("🗑️ Data telah dibersihkan.")

if __name__ == '__main__':
    init_db()
    
    # Jalankan server web Flask di thread terpisah untuk Render
    threading.Thread(target=run_flask, daemon=True).start()

    # Jalankan Bot Telegram
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('isi', isi_bbm))
    app.add_handler(CommandHandler('riwayat', riwayat))
    app.add_handler(CommandHandler('rekap', rekap))
    app.add_handler(CommandHandler('reset', reset_data))

    print("Bot BBM (Web Service) Berjalan...")
    app.run_polling()
