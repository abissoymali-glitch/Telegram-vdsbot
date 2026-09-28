# buttons.py içeriklerini ve ana bot kodunu birleştiren tam sürüm

from telebot import types
import telebot
import subprocess
import os
import time
from datetime import datetime, timedelta
import sqlite3
import logging
import threading
import sys
import atexit
import signal

# ============ RENK SABİTLERİ ============
COLOR_STYLES = {
    "mavi": "primary",
    "yeşil": "success",
    "kırmızı": "danger",
}

COLOR_ALIASES = {
    "mavi": "mavi", "blue": "mavi",
    "yesil": "yeşil", "yeşil": "yeşil", "green": "yeşil",
    "kirmizi": "kırmızı", "kırmızı": "kırmızı", "red": "kırmızı",
}

COLOR_GLYPH = {"mavi": "🔵", "yeşil": "🟢", "kırmızı": "🔴"}


# ============ RENKLİ BUTON OLUŞTURUCU ============
def pbtn(text, callback_data=None, emoji_id=None, url=None, color=None):
    """
    Renkli + premium emoji destekli inline buton oluşturur.
    """
    if url:
        b = types.InlineKeyboardButton(text, url=url)
    else:
        b = types.InlineKeyboardButton(text, callback_data=callback_data)

    try:
        if color in COLOR_STYLES:
            b.style = COLOR_STYLES[color]
    except Exception:
        pass  

    try:
        if emoji_id:
            b.icon_custom_emoji_id = emoji_id
    except Exception:
        pass

    return b


def parse_color(token):
    """'yeşil', 'green', 'YESIL' gibi girdileri normalize eder."""
    if not token:
        return None
    return COLOR_ALIASES.get(str(token).strip().lower())

# Bot by @susgunum

TOKEN = '8823007730:AAE_7UWzga7Aqd6I6Xf7fvx3p7w8KH3x0Ck'
OWNER_ID = 8687183701
ADMIN_ID = 8687183701
ADMIN_USERNAME = '@YxceBerkkCx'

REQUIRED_CHANNEL = 'https://t.me/YxceBerrxk'
REQUIRED_CHANNEL_ID = -1004472784027

PREMIUM_PLANS = {
    'weekly': {
        'id': 'weekly',
        'name': '1 Haftalık',
        'price': 25,
        'price_star': '⭐ 25 Star',
        'duration_days': 7,
        'bot_limit': 10,
        'storage_mb': 500,
        'auto_approve': False,
        'description': '✅ 7/24 Aktif\n📦 500MB Depolama\n🤖 10 Bot Sınırı'
    },
    'monthly': {
        'id': 'monthly',
        'name': '1 Aylık',
        'price': 50,
        'price_star': '⭐ 50 Star',
        'duration_days': 30,
        'bot_limit': 25,
        'storage_mb': 1024,
        'auto_approve': True,
        'description': '✅ 7/24 Aktif\n📦 1GB Depolama\n🤖 25 Bot Sınırı\n⚡ Anında Onay'
    },
    'quarterly': {
        'id': 'quarterly',
        'name': '3 Aylık',
        'price': 125,
        'price_star': '⭐ 125 Star',
        'duration_days': 90,
        'bot_limit': float('inf'),
        'storage_mb': 2048,
        'auto_approve': True,
        'description': '✅ 7/24 Aktif\n📦 2GB Depolama\n♾️ Sınırsız Bot\n⚡ Anında Onay'
    }
}

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_BOTS_DIR = os.path.join(BASE_DIR, 'upload_bots')
IROTECH_DIR = os.path.join(BASE_DIR, 'inf')
DATABASE_PATH = os.path.join(IROTECH_DIR, 'bot_data.db')

os.makedirs(UPLOAD_BOTS_DIR, exist_ok=True)
os.makedirs(IROTECH_DIR, exist_ok=True)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot_activity.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS user_files
                 (user_id INTEGER, file_name TEXT, file_type TEXT,
                  status TEXT DEFAULT 'pending', upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  PRIMARY KEY (user_id, file_name))''')

    c.execute('''CREATE TABLE IF NOT EXISTS active_users
                 (user_id INTEGER PRIMARY KEY, join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

    c.execute('''CREATE TABLE IF NOT EXISTS premium_users
                 (user_id INTEGER PRIMARY KEY, plan_id TEXT,
                  expiry_date TIMESTAMP, bot_limit INTEGER, storage_mb INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS bot_stats
                 (stat_key TEXT PRIMARY KEY, stat_value TEXT)''')

    conn.commit()
    conn.close()

def load_data():
    global active_users, premium_users, user_files

    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()

    user_files = {}
    c.execute('SELECT user_id, file_name, file_type, status FROM user_files')
    for user_id, file_name, file_type, status in c.fetchall():
        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id].append((file_name, file_type, status))

    active_users = set()
    c.execute('SELECT user_id FROM active_users')
    for (user_id,) in c.fetchall():
        active_users.add(user_id)

    premium_users = {}
    c.execute('SELECT user_id, plan_id, expiry_date, bot_limit, storage_mb FROM premium_users')
    for user_id, plan_id, expiry_date, bot_limit, storage_mb in c.fetchall():
        try:
            expiry = datetime.fromisoformat(expiry_date)
            if expiry > datetime.now():
                premium_users[user_id] = {
                    'plan': plan_id,
                    'expires': expiry,
                    'bot_limit': bot_limit,
                    'storage_mb': storage_mb
                }
        except:
            pass

    conn.close()

init_db()
load_data()

bot_scripts = {}
pending_approvals = {}
user_states = {}
temp_data = {}

def is_premium(user_id):
    if user_id in [OWNER_ID, ADMIN_ID]:
        return True
    if user_id not in premium_users:
        return False
    if premium_users[user_id]['expires'] < datetime.now():
        del premium_users[user_id]
        return False
    return True

def get_premium_info(user_id):
    if user_id not in premium_users:
        return None
    data = premium_users[user_id]
    remaining_days = (data['expires'] - datetime.now()).days
    return {
        'plan': data['plan'],
        'expires': data['expires'],
        'remaining_days': remaining_days,
        'bot_limit': data['bot_limit'],
        'storage_mb': data['storage_mb']
    }

def get_user_bot_limit(user_id):
    if user_id in [OWNER_ID, ADMIN_ID]:
        return float('inf')
    premium_info = get_premium_info(user_id)
    if premium_info:
        return premium_info['bot_limit']
    return 1

def get_user_storage_limit(user_id):
    if user_id in [OWNER_ID, ADMIN_ID]:
        return float('inf')
    premium_info = get_premium_info(user_id)
    if premium_info:
        return premium_info['storage_mb']
    return 100

def get_user_folder(user_id):
    user_folder = os.path.join(UPLOAD_BOTS_DIR, str(user_id))
    os.makedirs(user_folder, exist_ok=True)
    return user_folder

def get_user_file_count(user_id):
    return len(user_files.get(user_id, []))

def get_user_storage_used(user_id):
    user_folder = get_user_folder(user_id)
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(user_folder):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
        return total_size / (1024 * 1024)
    except:
        return 0

def save_user_file(user_id, file_name, file_type, status='pending'):
    try:
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO user_files (user_id, file_name, file_type, status) VALUES (?, ?, ?, ?)',
                  (user_id, file_name, file_type, status))
        conn.commit()
        conn.close()

        if user_id not in user_files:
            user_files[user_id] = []
        user_files[user_id] = [(fn, ft, st) for fn, ft, st in user_files[user_id] if fn != file_name]
        user_files[user_id].append((file_name, file_type, status))
        return True
    except Exception as e:
        logger.error(f"❌ Dosya kaydetme hatası: {e}")
        return False

def is_bot_running(user_id, file_name):
    script_key = f"{user_id}_{file_name}"
    script_info = bot_scripts.get(script_key)
    if script_info and script_info.get('process'):
        try:
            proc = script_info['process']
            return proc.poll() is None
        except:
            return False
    return False

def check_channel_membership(user_id):
    try:
        member = bot.get_chat_member(REQUIRED_CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def run_bot_with_log(user_id, file_name, file_path, file_type):
    def target():
        try:
            script_key = f"{user_id}_{file_name}"

            if script_key in bot_scripts:
                old_proc = bot_scripts[script_key].get('process')
                if old_proc and old_proc.poll() is None:
                    old_proc.terminate()
                    time.sleep(1)

            if file_type == 'py':
                proc = subprocess.Popen(
                    [sys.executable, file_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            else:
                logger.error(f"❌ Sadece .py dosyaları desteklenir: {file_type}")
                return

            bot_scripts[script_key] = {
                'process': proc,
                'file_name': file_name,
                'user_id': user_id,
                'file_type': file_type,
                'start_time': datetime.now()
            }

            logger.info(f"🚀 Bot başlatıldı: {script_key}")

        except Exception as e:
            logger.error(f"❌ Bot başlatma hatası: {e}")
            bot.send_message(user_id, f"❌ Bot başlatılamadı: {str(e)[:200]}")

    threading.Thread(target=target, daemon=True).start()

def get_all_users():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('SELECT user_id, join_date FROM active_users ORDER BY join_date DESC')
    users = c.fetchall()
    conn.close()
    return users

def get_total_bots():
    total = 0
    for files in user_files.values():
        total += len(files)
    return total

def get_running_bots():
    running = 0
    for script_info in bot_scripts.values():
        try:
            if script_info['process'].poll() is None:
                running += 1
        except:
            pass
    return running

def delete_message_safe(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

def create_main_keyboard(user_id, is_admin=False):
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if is_admin:
        buttons = [
            pbtn("📤 Yükle", callback_data="upload", color="yeşil"),
            pbtn("📁 Dosyalarım", callback_data="my_files", color="mavi"),
            pbtn("⚡ Hız Testi", callback_data="speed_test", color="mavi"),
            pbtn("📊 İstatistik", callback_data="stats", color="mavi"),
            pbtn("👑 Admin Paneli", callback_data="admin_panel", color="kırmızı"),
            pbtn("💎 Premium", callback_data="premium", color="yeşil"),
            pbtn("🔄 Yenile", callback_data="refresh", color="mavi"),
            pbtn("❓ Yardım", callback_data="help", color="mavi")
        ]
        for i in range(0, len(buttons), 2):
            if i+1 < len(buttons):
                keyboard.row(buttons[i], buttons[i+1])
            else:
                keyboard.row(buttons[i])
    else:
        buttons = [
            pbtn("📤 Yükle", callback_data="upload", color="yeşil"),
            pbtn("📁 Dosyalarım", callback_data="my_files", color="mavi"),
            pbtn("⚡ Hız Testi", callback_data="speed_test", color="mavi"),
            pbtn("📊 İstatistik", callback_data="stats", color="mavi"),
            pbtn("💎 Premium", callback_data="premium", color="yeşil"),
            pbtn("🔄 Yenile", callback_data="refresh", color="mavi"),
            pbtn("❓ Yardım", callback_data="help", color="mavi")
        ]
        for i in range(0, len(buttons), 2):
            if i+1 < len(buttons):
                keyboard.row(buttons[i], buttons[i+1])
            else:
                keyboard.row(buttons[i])

    return keyboard

def create_admin_panel_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    buttons = [
        pbtn("📢 Duyuru Gönder", callback_data="admin_announce", color="mavi"),
        pbtn("👥 Kullanıcılar", callback_data="admin_users", color="mavi"),
        pbtn("🎁 Premium Ver", callback_data="admin_give_premium", color="yeşil"),
        pbtn("❌ Premium Sil", callback_data="admin_remove_premium", color="kırmızı"),
        pbtn("🗑️ Dosya Sil", callback_data="admin_delete_file", color="kırmızı"),
        pbtn("📊 Detaylı İstatistik", callback_data="admin_stats", color="mavi"),
        pbtn("⚙️ Bot Yönetimi", callback_data="admin_bots", color="mavi"),
        pbtn("🔙 Geri", callback_data="back_main", color="kırmızı")
    ]
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            keyboard.row(buttons[i], buttons[i+1])
        else:
            keyboard.row(buttons[i])
    return keyboard

def create_premium_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    for plan_id, plan in PREMIUM_PLANS.items():
        keyboard.add(pbtn(f"{plan['name']} - {plan['price_star']}", callback_data=f"premium_{plan_id}", color="yeşil"))
    keyboard.add(pbtn("🔙 Geri", callback_data="back_main", color="kırmızı"))
    return keyboard

def create_files_keyboard(user_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    user_files_list = user_files.get(user_id, [])

    if not user_files_list:
        keyboard.add(pbtn("📭 Dosya Yok", callback_data="no_file", color="kırmızı"))
        keyboard.add(pbtn("🔙 Geri", callback_data="back_main", color="kırmızı"))
        return keyboard

    for file_name, file_type, status in user_files_list:
        if status == 'approved':
            is_running = is_bot_running(user_id, file_name)
            status_emoji = '🚀' if is_running else '⏸️'
            btn_color = "yeşil" if is_running else "mavi"
        elif status == 'pending':
            status_emoji = '⏳'
            btn_color = "mavi"
        else:
            status_emoji = '❌'
            btn_color = "kırmızı"

        display_name = file_name[:20] + '...' if len(file_name) > 20 else file_name
        keyboard.add(pbtn(
            f"{status_emoji} {display_name}",
            callback_data=f"file_{user_id}_{file_name}",
            color=btn_color
        ))

    keyboard.add(pbtn("🔙 Geri", callback_data="back_main", color="kırmızı"))
    return keyboard

def create_file_control_keyboard(user_id, file_name, status, is_running):
    keyboard = types.InlineKeyboardMarkup(row_width=2)

    if status == 'approved':
        if is_running:
            keyboard.row(
                pbtn("⏸️ Durdur", callback_data=f"stop_{user_id}_{file_name}", color="kırmızı"),
                pbtn("🔄 Yeniden Başlat", callback_data=f"restart_{user_id}_{file_name}", color="mavi")
            )
            keyboard.row(
                pbtn("📋 Loglar", callback_data=f"logs_{user_id}_{file_name}", color="mavi"),
                pbtn("🗑️ Sil", callback_data=f"delete_{user_id}_{file_name}", color="kırmızı")
            )
        else:
            keyboard.row(
                pbtn("🚀 Başlat", callback_data=f"start_{user_id}_{file_name}", color="yeşil"),
                pbtn("🗑️ Sil", callback_data=f"delete_{user_id}_{file_name}", color="kırmızı")
            )
    elif status == 'pending':
        keyboard.add(pbtn("⏳ Onay Bekleniyor", callback_data="no_action", color="mavi"))
    else:
        keyboard.add(pbtn("❌ Reddedildi", callback_data="no_action", color="kırmızı"))

    keyboard.add(pbtn("🔙 Geri", callback_data="my_files", color="kırmızı"))
    return keyboard

def create_approval_inline_keyboard(file_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        pbtn("✅ ONAYLA", callback_data=f"approve_{file_id}", color="yeşil"),
        pbtn("❌ REDDET", callback_data=f"reject_{file_id}", color="kırmızı")
    )
    return keyboard

def create_back_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(pbtn("🔙 Geri", callback_data="back_main", color="kırmızı"))
    return keyboard

@bot.message_handler(commands=['start', 'help'])
def command_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not check_channel_membership(user_id):
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(pbtn("📢 KANALA KATIL", url="https://t.me/+6K2JW4FQZH8xZjNh", color="yeşil"))
        bot.send_message(
            user_id,
            f"❌ <b>ZORUNLU KANAL</b>\n\nBotu kullanmak için aşağıdaki kanala katılmalısın:\n\n{REQUIRED_CHANNEL}\n\nKatıldıktan sonra /start yaz.",
            reply_markup=keyboard
        )
        return

    if user_id not in active_users:
        active_users.add(user_id)
        conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO active_users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()

    show_main_menu(message)

def show_main_menu(message):
    user_id = message.from_user.id
    user_name = message.from_user.first_name
    is_admin = user_id in [OWNER_ID, ADMIN_ID]

    current_files = get_user_file_count(user_id)
    bot_limit = get_user_bot_limit(user_id)
    storage_limit = get_user_storage_limit(user_id)
    storage_used = get_user_storage_used(user_id)

    if user_id == OWNER_ID:
        user_status = "👑 SAHİP"
    elif user_id == ADMIN_ID:
        user_status = "🔧 ADMIN"
    elif is_premium(user_id):
        premium_info = get_premium_info(user_id)
        user_status = f"💎 PREMİUM ({premium_info['plan']})"
    else:
        user_status = "👤 KULLANICI"

    text = f"""🌟 <b>ANA MENÜ</b> 🌟

👤 {user_name}
🎯 Seviye: {user_status}
📂 Dosyalar: {current_files}/{bot_limit if bot_limit != float('inf') else '∞'}
📦 Depolama: {storage_used:.1f}/{storage_limit if storage_limit != float('inf') else '∞'} MB

✨ Aşağıdaki butonlarla işlem yap!"""

    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=create_main_keyboard(user_id, is_admin)
        )
    except:
        bot.send_message(
            user_id,
            text,
            reply_markup=create_main_keyboard(user_id, is_admin)
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("premium_"))
def premium_callback(call):
    user_id = call.from_user.id
    data = call.data

    if data == "premium_back" or data == "back_main":
        show_main_menu(call.message)
        return

    plan_id = data.replace("premium_", "")
    plan = PREMIUM_PLANS.get(plan_id)

    if not plan:
        bot.answer_callback_query(call.id, "❌ Geçersiz plan!")
        return

    plan_text = f"""
💎 <b>{plan['name']} PAKETİ</b>

⭐ Fiyat: {plan['price_star']}
📅 Süre: {plan['duration_days']} gün

📋 <b>ÖZELLİKLER:</b>
{plan['description']}

🤖 Bot Limit: {plan['bot_limit'] if plan['bot_limit'] != float('inf') else '♾️ Sınırsız'}
📦 Depolama: {plan['storage_mb']} MB

💳 Satın almak için: {ADMIN_USERNAME}
    """

    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(pbtn("💳 SATIN AL", url=f"https://t.me/{ADMIN_USERNAME.replace('@', '')}", color="yeşil"))
    keyboard.add(pbtn("🔙 GERİ", callback_data="premium_back", color="kırmızı"))

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=plan_text,
        reply_markup=keyboard
    )

def show_premium_menu(message):
    user_id = message.from_user.id

    if is_premium(user_id):
        premium_info = get_premium_info(user_id)
        plan = PREMIUM_PLANS.get(premium_info['plan'])
        text = f"""
💎 <b>PREMIUM ÜYE</b>

👤 {message.from_user.first_name}
📅 Plan: {plan['name']}
⏳ Kalan Gün: {premium_info['remaining_days']}
🤖 Bot Limit: {premium_info['bot_limit']}
📦 Depolama: {premium_info['storage_mb']} MB
        """
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=create_back_keyboard()
        )
    else:
        text = "💎 <b>PREMIUM PAKETLER</b>\n\nPremium üyelik ile bot deneyimini zirveye taşı!\n\nAşağıdan plan seç:"
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=create_premium_keyboard()
        )

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id

    if not check_channel_membership(user_id):
        bot.reply_to(message, f"❌ Önce kanala katıl: {REQUIRED_CHANNEL}")
        return

    doc = message.document
    file_name = doc.file_name

    if not file_name:
        bot.reply_to(message, "❌ Dosya adı yok!")
        return

    file_ext = os.path.splitext(file_name)[1].lower()

    if file_ext != '.py':
        bot.reply_to(message, "❌ Sadece `.py` dosyaları kabul edilir!")
        return

    current_files = get_user_file_count(user_id)
    bot_limit = get_user_bot_limit(user_id)

    if bot_limit != float('inf') and current_files >= bot_limit:
        bot.reply_to(message, f"❌ Bot limiti doldu! ({current_files}/{int(bot_limit)})\n💡 Premium satın alarak limiti artır!")
        return

    storage_limit = get_user_storage_limit(user_id)
    storage_used = get_user_storage_used(user_id)

    if storage_limit != float('inf') and storage_used >= storage_limit:
        bot.reply_to(message, f"❌ Depolama alanı doldu! ({storage_used:.1f}/{storage_limit} MB)")
        return

    if doc.file_size > 20 * 1024 * 1024:
        bot.reply_to(message, "❌ Dosya çok büyük! Max 20MB")
        return

    try:
        bot.reply_to(message, f"📥 Yükleniyor: {file_name}")

        file_info = bot.get_file(doc.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        user_folder = get_user_folder(user_id)
        file_path = os.path.join(user_folder, file_name)

        with open(file_path, 'wb') as f:
            f.write(downloaded_file)

        file_type = 'py'
        auto_approve = is_premium(user_id) or user_id in [OWNER_ID, ADMIN_ID]
        status = 'approved' if auto_approve else 'pending'

        if save_user_file(user_id, file_name, file_type, status):
            if auto_approve:
                bot.reply_to(message, f"✅ <b>YÜKLENDİ VE ONAYLANDI!</b>\n\n<code>{file_name}</code>\n\n🚀 Botunu hemen başlatabilirsin!")
            else:
                file_id = f"{user_id}_{file_name}_{int(time.time())}"
                pending_approvals[file_id] = {
                    'user_id': user_id,
                    'user_name': message.from_user.first_name,
                    'file_name': file_name,
                    'file_type': file_type,
                    'file_path': file_path,
                    'upload_time': datetime.now()
                }

                admin_msg = f"📤 <b>YENİ DOSYA</b>\n\n👤 {message.from_user.first_name}\n🆔 {user_id}\n📄 {file_name}"

                with open(file_path, 'rb') as f:
                    bot.send_document(ADMIN_ID, f, caption=admin_msg, reply_markup=create_approval_inline_keyboard(file_id))

                bot.reply_to(message, f"✅ <b>YÜKLENDİ!</b>\n\n<code>{file_name}</code>\n\n⏳ Admin onayı bekleniyor...")

    except Exception as e:
        logger.error(f"❌ Dosya yükleme hatası: {e}")
        bot.reply_to(message, f"❌ Hata: {str(e)[:100]}")

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == "back_main":
        show_main_menu(call.message)
        return

    elif data == "refresh":
        show_main_menu(call.message)
        return

    elif data == "upload":
        current_files = get_user_file_count(user_id)
        bot_limit = get_user_bot_limit(user_id)

        if bot_limit != float('inf') and current_files >= bot_limit:
            bot.answer_callback_query(call.id, f"❌ Bot limiti doldu! ({current_files}/{int(bot_limit)})", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📤 <b>DOSYA YÜKLE</b>\n\nSadece <code>.py</code> dosyaları kabul edilir.\n📦 Max 20MB\n🤖 Limit: {current_files}/{bot_limit if bot_limit != float('inf') else '∞'}\n\n👇 Dosyanı gönder:",
            reply_markup=create_back_keyboard()
        )

    elif data == "my_files":
        show_files(call)
        return

    elif data == "speed_test":
        start_time = time.time()
        response_time = round((time.time() - start_time) * 1000, 2)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"⚡ <b>BOT HIZI</b>\n\n⏱️ Yanıt Süresi: <code>{response_time} ms</code>\n📊 Aktif Kullanıcı: <code>{len(active_users)}</code>",
            reply_markup=create_back_keyboard()
        )

    elif data == "stats":
        total_files = get_total_bots()
        running_bots = get_running_bots()

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📊 <b>İSTATİSTİKLER</b>\n\n👥 Kullanıcı: <code>{len(active_users)}</code>\n📂 Dosya: <code>{total_files}</code>\n🚀 Çalışan Bot: <code>{running_bots}</code>\n⏳ Bekleyen Onay: <code>{len(pending_approvals)}</code>",
            reply_markup=create_back_keyboard()
        )

    elif data == "premium":
        show_premium_menu(call.message)
        return

    elif data == "help":
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"📖 <b>YARDIM</b>\n\n📤 Yükle: .py bot yükle\n📁 Dosyalarım: Botlarını gör\n💎 Premium: Premium satın al\n\n📌 Admin: {ADMIN_USERNAME}\n📢 Kanal: {REQUIRED_CHANNEL}",
            reply_markup=create_back_keyboard()
        )

    elif data == "admin_panel":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="👑 <b>ADMIN PANELİ</b>\n\nAşağıdaki işlemleri yapabilirsin:",
            reply_markup=create_admin_panel_keyboard()
        )

    elif data == "admin_announce":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📢 <b>DUYURU GÖNDER</b>\n\nDuyuru mesajını yaz ve gönder.\n\n⏳ Mesajını bekliyorum...",
            reply_markup=create_back_keyboard()
        )
        user_states[user_id] = "waiting_announce"

    elif data == "admin_users":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        users = get_all_users()
        text = f"👥 <b>KULLANICILAR</b> ({len(users)})\n\n"
        for i, (uid, join_date) in enumerate(users[:20], 1):
            is_prem = "💎" if is_premium(uid) else "👤"
            text += f"{i}. {is_prem} <code>{uid}</code>\n"

        if len(users) > 20:
            text += f"\n... ve {len(users) - 20} daha"

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=create_back_keyboard()
        )

    elif data == "admin_give_premium":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🎁 <b>PREMIUM VER</b>\n\nKullanıcı ID ve Plan ID girin.\n\nFormat: <code>kullanici_id plan_id</code>\nPlanlar: weekly, monthly, quarterly\n\nÖrnek: <code>123456789 monthly</code>",
            reply_markup=create_back_keyboard()
        )
        user_states[user_id] = "waiting_give_premium"

    elif data == "admin_remove_premium":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="❌ <b>PREMIUM SİL</b>\n\nPremium üyeliği silinecek kullanıcının ID'sini girin.\n\nFormat: <code>kullanici_id</code>\n\nÖrnek: <code>123456789</code>",
            reply_markup=create_back_keyboard()
        )
        user_states[user_id] = "waiting_remove_premium"

    elif data == "admin_delete_file":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="🗑️ <b>DOSYA SİL</b>\n\nSilinecek dosyanın kullanıcı ID ve dosya adını girin.\n\nFormat: <code>kullanici_id dosya_adi.py</code>\n\nÖrnek: <code>123456789 main.py</code>",
            reply_markup=create_back_keyboard()
        )
        user_states[user_id] = "waiting_delete_file"

    elif data == "admin_stats":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        total_files = get_total_bots()
        running_bots = get_running_bots()
        premium_count = len(premium_users)
        total_users = len(active_users)

        premium_list = ""
        for uid, info in list(premium_users.items())[:10]:
            days = (info['expires'] - datetime.now()).days
            premium_list += f"• <code>{uid}</code> - {days}gün kaldı\n"

        text = f"""📊 <b>DETAYLI İSTATİSTİK</b>

👥 Toplam Kullanıcı: <code>{total_users}</code>
💎 Premium Üye: <code>{premium_count}</code>
📂 Toplam Dosya: <code>{total_files}</code>
🚀 Çalışan Bot: <code>{running_bots}</code>
⏳ Bekleyen Onay: <code>{len(pending_approvals)}</code>

<b>📋 Premium Kullanıcılar:</b>
{premium_list if premium_list else 'Henüz premium kullanıcı yok'}"""

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=create_back_keyboard()
        )

    elif data == "admin_bots":
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        text = "⚙️ <b>BOT YÖNETİMİ</b>\n\nÇalışan botlar:\n\n"
        if bot_scripts:
            for script_key, info in bot_scripts.items():
                try:
                    if info['process'].poll() is None:
                        text += f"🚀 <code>{info['file_name']}</code> (Kullanıcı: {info['user_id']})\n"
                except:
                    pass
            if text == "⚙️ <b>BOT YÖNETİMİ</b>\n\nÇalışan botlar:\n\n":
                text += "Hiç bot çalışmıyor."
        else:
            text += "Hiç bot çalışmıyor."

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=create_back_keyboard()
        )

    elif data.startswith("file_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        if user_id != uid:
            bot.answer_callback_query(call.id, "❌ Bu dosya size ait değil!", show_alert=True)
            return

        file_name = fname
        file_type = None
        status = None

        for fn, ft, st in user_files.get(user_id, []):
            if fn == file_name:
                file_type = ft
                status = st
                break

        if not file_type or not status:
            bot.answer_callback_query(call.id, "❌ Dosya bulunamadı!", show_alert=True)
            return

        if status == 'pending':
            text = f"⏳ <b>BEKLİYOR</b>\n\n<code>{file_name}</code>\n\nAdmin onayı bekleniyor..."
        elif status == 'rejected':
            text = f"❌ <b>REDDEDİLDİ</b>\n\n<code>{file_name}</code>"
        elif status == 'approved':
            is_running = is_bot_running(user_id, file_name)
            text = f"🚀 <b>ÇALIŞIYOR</b>\n\n<code>{file_name}</code>" if is_running else f"⏸️ <b>DURDU</b>\n\n<code>{file_name}</code>"
        else:
            text = f"❓ <b>BİLİNMİYOR</b>\n\n<code>{file_name}</code>"

        is_running = is_bot_running(user_id, file_name) if status == 'approved' else False
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            reply_markup=create_file_control_keyboard(user_id, file_name, status, is_running)
        )

    elif data.startswith("start_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        if user_id != uid and user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Bu dosya size ait değil!", show_alert=True)
            return

        user_folder = get_user_folder(uid)
        file_path = os.path.join(user_folder, fname)

        if os.path.exists(file_path):
            run_bot_with_log(uid, fname, file_path, 'py')
            bot.answer_callback_query(call.id, f"✅ Başlatıldı: {fname}")
            is_running = True
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_file_control_keyboard(uid, fname, 'approved', True)
            )
        else:
            bot.answer_callback_query(call.id, "❌ Dosya bulunamadı!", show_alert=True)

    elif data.startswith("stop_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        if user_id != uid and user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        script_key = f"{uid}_{fname}"
        if script_key in bot_scripts:
            try:
                proc = bot_scripts[script_key]['process']
                if proc and proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)
                bot.answer_callback_query(call.id, f"⏸️ Durduruldu: {fname}")
                bot.edit_message_reply_markup(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=create_file_control_keyboard(uid, fname, 'approved', False)
                )
            except Exception as e:
                logger.error(f"❌ Durdurma hatası: {e}")
                bot.answer_callback_query(call.id, "❌ Durdurma hatası!", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ Bot çalışmıyor!", show_alert=True)

    elif data.startswith("restart_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        if user_id != uid and user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        script_key = f"{uid}_{fname}"
        if script_key in bot_scripts:
            try:
                proc = bot_scripts[script_key]['process']
                if proc and proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)
                time.sleep(1)
            except:
                pass

        user_folder = get_user_folder(uid)
        file_path = os.path.join(user_folder, fname)

        if os.path.exists(file_path):
            run_bot_with_log(uid, fname, file_path, 'py')
            bot.answer_callback_query(call.id, f"🔄 Yeniden başlatıldı: {fname}")
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=create_file_control_keyboard(uid, fname, 'approved', True)
            )
        else:
            bot.answer_callback_query(call.id, "❌ Dosya bulunamadı!", show_alert=True)

    elif data.startswith("delete_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        if user_id != uid and user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        user_folder = get_user_folder(uid)
        file_path = os.path.join(user_folder, fname)

        script_key = f"{uid}_{fname}"
        if script_key in bot_scripts:
            try:
                proc = bot_scripts[script_key]['process']
                if proc and proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=3)
                del bot_scripts[script_key]
            except:
                pass

        try:
            if os.path.exists(file_path):
                os.remove(file_path)

            conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            c = conn.cursor()
            c.execute('DELETE FROM user_files WHERE user_id=? AND file_name=?', (uid, fname))
            conn.commit()
            conn.close()

            if uid in user_files:
                user_files[uid] = [(fn, ft, st) for fn, ft, st in user_files[uid] if fn != fname]

            bot.answer_callback_query(call.id, f"🗑️ Silindi: {fname}")
            show_files(call)
        except Exception as e:
            bot.answer_callback_query(call.id, f"❌ Hata: {str(e)[:50]}", show_alert=True)

    elif data.startswith("logs_"):
        _, uid, fname = data.split("_", 2)
        uid = int(uid)
        script_key = f"{uid}_{fname}"
        if script_key in bot_scripts:
            bot.answer_callback_query(call.id, "📋 Bot aktif çalışıyor!")
        else:
            bot.answer_callback_query(call.id, "📋 Bot çalışmıyor.")

    elif data.startswith("approve_") or data.startswith("reject_"):
        if user_id not in [OWNER_ID, ADMIN_ID]:
            bot.answer_callback_query(call.id, "❌ Yetkiniz yok!", show_alert=True)
            return

        action, file_id = data.split("_", 1)

        if file_id not in pending_approvals:
            bot.answer_callback_query(call.id, "✅ Zaten işlendi!")
            return

        file_info = pending_approvals[file_id]
        target_user_id = file_info['user_id']
        file_name = file_info['file_name']
        file_type = file_info['file_type']

        if action == "approve":
            if save_user_file(target_user_id, file_name, file_type, 'approved'):
                try:
                    bot.send_message(target_user_id, f"🎉 <b>DOSYAN ONAYLANDI!</b>\n\n<code>{file_name}</code>\n\nArtık botunu başlatabilirsin!")
                except:
                    pass

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"✅ <b>ONAYLANDI</b>\n👤 {file_info['user_name']}\n📄 {file_name}",
                    reply_markup=None
                )
                bot.answer_callback_query(call.id, "✅ Onaylandı!")

        elif action == "reject":
            user_folder = get_user_folder(target_user_id)
            file_path = os.path.join(user_folder, file_name)

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass

            try:
                conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
                c = conn.cursor()
                c.execute('DELETE FROM user_files WHERE user_id=? AND file_name=?', (target_user_id, file_name))
                conn.commit()
                conn.close()

                if target_user_id in user_files:
                    user_files[target_user_id] = [(fn, ft, st) for fn, ft, st in user_files[target_user_id] if fn != file_name]

                try:
                    bot.send_message(target_user_id, f"❌ <b>DOSYAN REDDEDİLDİ</b>\n\n<code>{file_name}</code>")
                except:
                    pass

                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=f"❌ <b>REDDEDİLDİ</b>\n👤 {file_info['user_name']}\n📄 {file_name}",
                    reply_markup=None
                )
                bot.answer_callback_query(call.id, "❌ Reddedildi!")
            except Exception as e:
                logger.error(f"❌ Reddetme hatası: {e}")
                bot.answer_callback_query(call.id, "❌ Hata oluştu!", show_alert=True)

        del pending_approvals[file_id]

    elif data == "no_action":
        bot.answer_callback_query(call.id, "⚠️ Bu dosya üzerinde işlem yapılamaz!")

def show_files(call):
    user_id = call.from_user.id
    user_files_list = user_files.get(user_id, [])

    if not user_files_list:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="📭 <b>HENÜZ DOSYA YOK</b>\n\nYükle butonu ile bot yükle!",
            reply_markup=create_back_keyboard()
        )
        return

    text = f"📁 <b>DOSYALARIN</b> ({len(user_files_list)})\n\n"
    for file_name, file_type, status in user_files_list:
        if status == 'approved':
            is_running = is_bot_running(user_id, file_name)
            status_text = "🚀 ÇALIŞIYOR" if is_running else "⏸️ DURDU"
        elif status == 'pending':
            status_text = "⏳ BEKLİYOR"
        else:
            status_text = "❌ REDDEDİLDİ"

        text += f"• <code>{file_name}</code> - {status_text}\n"

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text,
        reply_markup=create_files_keyboard(user_id)
    )

@bot.message_handler(func=lambda message: True)
def handle_state_messages(message):
    user_id = message.from_user.id
    text = message.text

    if user_id in user_states:
        state = user_states[user_id]

        if state == "waiting_announce":
            if user_id not in [OWNER_ID, ADMIN_ID]:
                return

            users = get_all_users()
            success = 0
            fail = 0

            bot.send_message(user_id, f"📢 Duyuru gönderiliyor... ({len(users)} kullanıcı)")

            for uid, _ in users:
                try:
                    bot.send_message(uid, f"📢 <b>DUYURU</b>\n\n{text}")
                    success += 1
                    time.sleep(0.1)
                except:
                    fail += 1

            bot.send_message(
                user_id,
                f"✅ Duyuru tamamlandı!\n✅ Başarılı: {success}\n❌ Başarısız: {fail}"
            )
            del user_states[user_id]
            show_main_menu(message)
            return

        elif state == "waiting_give_premium":
            if user_id not in [OWNER_ID, ADMIN_ID]:
                return

            try:
                parts = text.split()
                if len(parts) < 2:
                    bot.reply_to(message, "❌ Format: <code>kullanici_id plan_id</code>")
                    return

                target_user = int(parts[0])
                plan_id = parts[1].lower()

                if plan_id not in PREMIUM_PLANS:
                    bot.reply_to(message, "❌ Geçersiz plan! Planlar: weekly, monthly, quarterly")
                    return

                plan = PREMIUM_PLANS[plan_id]
                expiry = datetime.now() + timedelta(days=plan['duration_days'])

                conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
                c = conn.cursor()
                c.execute('INSERT OR REPLACE INTO premium_users (user_id, plan_id, expiry_date, bot_limit, storage_mb) VALUES (?, ?, ?, ?, ?)',
                          (target_user, plan_id, expiry.isoformat(), plan['bot_limit'], plan['storage_mb']))
                conn.commit()
                conn.close()

                premium_users[target_user] = {
                    'plan': plan_id,
                    'expires': expiry,
                    'bot_limit': plan['bot_limit'],
                    'storage_mb': plan['storage_mb']
                }

                bot.reply_to(message, f"✅ Premium eklendi! Kullanıcı: <code>{target_user}</code> Plan: {plan['name']}")
                try:
                    bot.send_message(target_user, f"🎉 <b>PREMIUM ÜYE OLDU!</b>\n\nPlan: {plan['name']}\nSüre: {plan['duration_days']} gün")
                except:
                    pass
            except ValueError:
                bot.reply_to(message, "❌ Geçersiz kullanıcı ID!")

            del user_states[user_id]
            show_main_menu(message)
            return

        elif state == "waiting_remove_premium":
            if user_id not in [OWNER_ID, ADMIN_ID]:
                return

            try:
                target_user = int(text)

                if target_user in premium_users:
                    del premium_users[target_user]

                    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
                    c = conn.cursor()
                    c.execute('DELETE FROM premium_users WHERE user_id = ?', (target_user,))
                    conn.commit()
                    conn.close()

                    bot.reply_to(message, f"✅ Premium kaldırıldı: <code>{target_user}</code>")
                    try:
                        bot.send_message(target_user, "❌ Premium üyeliğin kaldırıldı.")
                    except:
                        pass
                else:
                    bot.reply_to(message, f"❌ Kullanıcı <code>{target_user}</code> premium üye değil!")
            except ValueError:
                bot.reply_to(message, "❌ Geçersiz kullanıcı ID!")

            del user_states[user_id]
            show_main_menu(message)
            return

        elif state == "waiting_delete_file":
            if user_id not in [OWNER_ID, ADMIN_ID]:
                return

            try:
                parts = text.split()
                if len(parts) < 2:
                    bot.reply_to(message, "❌ Format: <code>kullanici_id dosya_adi.py</code>")
                    return

                target_user = int(parts[0])
                file_name = parts[1]

                found = False
                if target_user in user_files:
                    for fn, ft, st in user_files[target_user]:
                        if fn == file_name:
                            found = True
                            break

                if not found:
                    bot.reply_to(message, f"❌ Dosya bulunamadı: <code>{file_name}</code>")
                    return

                user_folder = get_user_folder(target_user)
                file_path = os.path.join(user_folder, file_name)

                script_key = f"{target_user}_{file_name}"
                if script_key in bot_scripts:
                    try:
                        proc = bot_scripts[script_key]['process']
                        if proc and proc.poll() is None:
                            proc.terminate()
                            proc.wait(timeout=3)
                        del bot_scripts[script_key]
                    except:
                        pass

                if os.path.exists(file_path):
                    os.remove(file_path)

                conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
                c = conn.cursor()
                c.execute('DELETE FROM user_files WHERE user_id=? AND file_name=?', (target_user, file_name))
                conn.commit()
                conn.close()

                if target_user in user_files:
                    user_files[target_user] = [(fn, ft, st) for fn, ft, st in user_files[target_user] if fn != file_name]

                bot.reply_to(message, f"✅ Dosya silindi: <code>{file_name}</code>")
                try:
                    bot.send_message(target_user, f"🗑️ <b>DOSYAN SİLİNDİ</b>\n\n<code>{file_name}</code>\n\nAdmin tarafından silindi.")
                except:
                    pass
            except ValueError:
                bot.reply_to(message, "❌ Geçersiz kullanıcı ID!")
            except Exception as e:
                bot.reply_to(message, f"❌ Hata: {str(e)[:100]}")

            del user_states[user_id]
            show_main_menu(message)
            return

def cleanup():
    logger.info("🔴 Bot kapatılıyor...")
    for script_key, script_info in list(bot_scripts.items()):
        try:
            proc = script_info.get('process')
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=2)
        except:
            pass
    bot_scripts.clear()

atexit.register(cleanup)

if __name__ == '__main__':
    logger.info("="*50)
    logger.info("🚀 BOT BAŞLATILIYOR...")
    logger.info(f"👑 Owner: {OWNER_ID}")
    logger.info(f"📢 Zorunlu Kanal: {REQUIRED_CHANNEL}")
    logger.info("="*50)

    try:
        bot_info = bot.get_me()
        logger.info(f"🤖 Bot: @{bot_info.username}")
    except Exception as e:
        logger.error(f"❌ Bot bağlantı hatası: {e}")
        exit(1)

    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            logger.error(f"❌ Hata: {e}")
            time.sleep(10)

# Bot by @susgunum
