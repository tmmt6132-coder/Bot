import telebot, asyncio, aiohttp, json, base64, random, re, os, string, time, uuid, hashlib, threading
from telebot.async_telebot import AsyncTeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import cv2
import ddddocr
import numpy as np
from datetime import datetime, timedelta, timezone
import sqlite3
from contextlib import contextmanager
import hashlib
import hmac

# --- DUAL LAYER PASSWORD SYSTEM ---
# Layer 1 Password: MAKKK
# Layer 2 Password: MAKK


class DualPasswordAuth:
    def __init__(self):
        self.layer1_hash = hashlib.sha256(b"MAKKK").hexdigest()
        self.layer2_hash = hashlib.sha256(b"MK").hexdigest()
        self.authenticated_users = {}  # user_id -> bool (True if fully authenticated)
        self.layer1_verified = {}      # user_id -> bool (True if layer 1 passed)
        self.pending_layer2 = {}       # user_id -> bool (waiting for layer 2)
    
    def verify_layer1(self, user_id, password):
        """Verify first layer password"""
        if hashlib.sha256(password.encode()).hexdigest() == self.layer1_hash:
            self.layer1_verified[user_id] = True
            self.pending_layer2[user_id] = True
            return True
        return False
    
    def verify_layer2(self, user_id, password):
        """Verify second layer password"""
        if not self.layer1_verified.get(user_id, False):
            return False
        if hashlib.sha256(password.encode()).hexdigest() == self.layer2_hash:
            self.authenticated_users[user_id] = True
            self.pending_layer2[user_id] = False
            return True
        return False
    
    def is_authenticated(self, user_id):
        """Check if user is fully authenticated"""
        return self.authenticated_users.get(user_id, False)
    
    def reset_auth(self, user_id):
        """Reset authentication state for a user"""
        self.authenticated_users.pop(user_id, None)
        self.layer1_verified.pop(user_id, None)
        self.pending_layer2.pop(user_id, None)

auth_system = DualPasswordAuth()

# --- Configuration ---
BOT_TOKEN = "8863468567:AAG5MSEVU8DS9rNR4yF6kExaU_LPfBXPhNc"
ADMIN_IDS = ["5633376180", "8320683349"]
FORWARD_CHANNEL = "@makkkkkkkkkkkbot"

# --- SPEED CONFIGURATION ---
MAX_CONCURRENT = 2000
BATCH_SIZE = 1000
CONNECTION_LIMIT = 30000
CONNECTION_PER_HOST = 15000
TIMEOUT = 25

# --- Local Storage Setup ---
DB_PATH = "bot_data.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=10000")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY, 
                  user_id TEXT,
                  plan TEXT,
                  expires_at TEXT,
                  code_limit INTEGER DEFAULT 1000,
                  used_codes INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS results
                 (user_id TEXT PRIMARY KEY,
                  codes TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id TEXT PRIMARY KEY,
                  key TEXT,
                  registered_at TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_settings
                 (user_id TEXT PRIMARY KEY,
                  proxy_enabled INTEGER DEFAULT 1)''')
    
    conn.commit()
    conn.close()

init_db()

# --- In-memory caches ---
user_data = {}
approve = {}
scan_tasks = {}
success_messages = {}
success_texts = {}
limited_messages = {}
limited_texts = {}
captcha_state = {}
paid_users = {}
_voucher_sem = None
_start_time = time.monotonic()

# --- Proxy List (3 Proxies - ONLY for URL checking) ---
PROXY_LIST = [
    "gzsvv1pggl7k:3g9xpulazhkz2c2@65.111.5.6:3129",
    "y2g26w7t3tv4:p5ouenejkn07fvy@209.50.179.187:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.2.10:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.2.10:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.43.96:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.24.245:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.229.41:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.57.128:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.29.0:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.248.21:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.107:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.163.157:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.35.116:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.27.48:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.26.195:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.30.248:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.39.79:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.160.188:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.10.16:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.61.110:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.253.115:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.53.87:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.186.117:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.35.180:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.184.34:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@217.181.92.133:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.144:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.80:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.49.74:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.187.26:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.182.41:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.8.221:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.40.53:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.61.172:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.36.43:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.46:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.249.40:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.228.60:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.11.248:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.59.162:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.180.14:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.232.80:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.174.107:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.191.98:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.48.18:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.253:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.167.19.141:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.238.209:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.50.108:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.33.232:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.26.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.187.153:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.54.47:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.3.69:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.252.235:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@195.63.31.114:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.178.33:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.21.99:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.35.131:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.13.68:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.10.64:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.13.76:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.39.94:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.166.109:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.49.253:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.40.113:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.168.169:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.232.235:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.34.137:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.171.227:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.60.38:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.244.171:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.168.84:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.62.13:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.254.184:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.203:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.240.63:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.162.156:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.239.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.2.183:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.177.16:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.12.212:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.181.24:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.88:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.43.132:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@104.207.43.213:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.38.172:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.21.133:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.5.83:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.46.114:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.15.239:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@151.123.177.251:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.55.126:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.9.31:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.241.29:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@209.50.166.226:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.111:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@65.111.27.229:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.245.37:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.42.116:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@45.3.51.42:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@216.26.246.178:3129",
    "gdllkdvi6mhq:04l2fmxbv72tzkl@217.181.91.208:3129"
 ]

_proxy_index = 0
def get_next_proxy():
    global _proxy_index
    if not PROXY_LIST:
        return None
    proxy = PROXY_LIST[_proxy_index % len(PROXY_LIST)]
    _proxy_index += 1
    return f"http://{proxy}"

SUCCESS_CODE = asyncio.Queue()
bot = AsyncTeleBot(BOT_TOKEN)

# --- Helper Functions ---
def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

# --- Database Functions ---

@contextmanager
def get_db_cursor():
    conn = get_db_connection()
    try:
        yield conn.cursor()
        conn.commit()
    finally:
        conn.close()

def db_get_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys WHERE key = ?", (key,))
        result = c.fetchone()
        if result:
            return {
                "key": result[0],
                "user_id": result[1],
                "plan": result[2],
                "expires_at": result[3],
                "code_limit": result[4],
                "used_codes": result[5]
            }
    return None

def db_get_user(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return {
                "user_id": result[0],
                "key": result[1],
                "registered_at": result[2]
            }
    return None

def db_get_user_by_key(key):
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users WHERE key = ?", (key,))
        result = c.fetchone()
        if result:
            return {
                "user_id": result[0],
                "key": result[1],
                "registered_at": result[2]
            }
    return None

def db_get_results(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT codes FROM results WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return json.loads(result[0])
    return []

def db_save_results(user_id, codes):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO results (user_id, codes) VALUES (?, ?)",
                  (user_id, json.dumps(codes)))

def db_add_user(user_id, key):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO users (user_id, key, registered_at) VALUES (?, ?, ?)",
                  (user_id, key, datetime.now(timezone.utc).isoformat()))

def db_add_key(key, user_id, plan, expires_at, code_limit):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO keys (key, user_id, plan, expires_at, code_limit, used_codes) VALUES (?, ?, ?, ?, ?, ?)",
                  (key, user_id, plan, expires_at, code_limit, 0))

def db_delete_key(key):
    with get_db_cursor() as c:
        c.execute("DELETE FROM keys WHERE key = ?", (key,))

def db_update_used_codes(key, used_codes):
    with get_db_cursor() as c:
        c.execute("UPDATE keys SET used_codes = ? WHERE key = ?", (used_codes, key))

def db_get_all_keys():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM keys")
        results = c.fetchall()
        keys = {}
        for r in results:
            keys[r[0]] = {
                "user_id": r[1],
                "plan": r[2],
                "expires_at": r[3],
                "code_limit": r[4],
                "used_codes": r[5]
            }
        return keys

def db_get_all_users():
    with get_db_cursor() as c:
        c.execute("SELECT * FROM users")
        results = c.fetchall()
        return [r[0] for r in results]

def check_key_expiration(expires_at):
    try:
        if expires_at == "9999-12-31T23:59:59Z":
            return True
        exp_time = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < exp_time
    except:
        return False

def generate_expiry(plan):
    now = datetime.now(timezone.utc)
    plans = {
        "30m": timedelta(minutes=30),
        "1h": timedelta(hours=1),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
        "1m": timedelta(days=30),
        "1y": timedelta(days=365),
        "unlimited": None
    }
    if plan not in plans:
        return None
    if plan == "unlimited":
        return "9999-12-31T23:59:59Z"
    return (now + plans[plan]).isoformat()

def generate_random_key(length=12):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

# --- Proxy Settings Functions ---
def db_get_proxy_setting(user_id):
    with get_db_cursor() as c:
        c.execute("SELECT proxy_enabled FROM user_settings WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result:
            return bool(result[0])
    return True

def db_set_proxy_setting(user_id, enabled):
    with get_db_cursor() as c:
        c.execute("INSERT OR REPLACE INTO user_settings (user_id, proxy_enabled) VALUES (?, ?)",
                  (user_id, 1 if enabled else 0))

# --- Forward to Channel ---
async def forward_to_channel(message_text, parse_mode=None):
    try:
        await bot.send_message(FORWARD_CHANNEL, message_text, parse_mode=parse_mode)
    except Exception as e:
        print(f"Forward error: {e}")

# ==================== KEYBOARDS ====================

def get_main_keyboard(user_id=None):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    if user_id:
        proxy_enabled = db_get_proxy_setting(user_id)
        proxy_text = "🔴 Proxy OFF" if not proxy_enabled else "🟢 Proxy ON"
        proxy_callback = "menu_proxy_off" if proxy_enabled else "menu_proxy_on"
    else:
        proxy_text = "🟢 Proxy ON"
        proxy_callback = "menu_proxy_off"
    
    keyboard.add(
        InlineKeyboardButton("🎫 PAID USER", callback_data="menu_paid"),
        InlineKeyboardButton("🔗 STAR LINK Portal URL ထည့်ရန်", callback_data="menu_free_trial"),
        InlineKeyboardButton(proxy_text, callback_data=proxy_callback),
        InlineKeyboardButton("📋 Success Codes ကြည့်မည်", callback_data="menu_result"),
        InlineKeyboardButton("🔄 Recheck ပြန်လုပ်စစ်မည်", callback_data="menu_recheck"),
        InlineKeyboardButton("🛑 Scan ရပ်မည်", callback_data="menu_stop"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_voucher_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔢 VOUCHER 6 လုံး", callback_data="scan_6"),
        InlineKeyboardButton("🔢 VOUCHER 7 လုံး", callback_data="scan_7"),
        InlineKeyboardButton("🔢 VOUCHER 8 လုံး", callback_data="scan_8"),
        InlineKeyboardButton("🔤 VOUCHER ascii-lower", callback_data="scan_ascii-lower"),
        InlineKeyboardButton("🎲 VOUCHER all", callback_data="scan_all"),
        InlineKeyboardButton("🔤+🔢 MIXED 6လုံး", callback_data="scan_mixed"),
        InlineKeyboardButton("🔤+🔢 MIXED 8လုံး", callback_data="scan_mixed8"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_digit_keyboard(mode):
    keyboard = InlineKeyboardMarkup(row_width=5)
    buttons = []
    for i in range(10):
        buttons.append(InlineKeyboardButton(str(i), callback_data=f"digit_{mode}_{i}"))
    keyboard.add(*buttons)
    keyboard.add(InlineKeyboardButton("🎲 Random ဖြစ်ရှာရန်", callback_data=f"digit_{mode}_random"))
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return keyboard

def get_start_scam_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🚀 START SCAM", callback_data="menu_start_scam"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_paid_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("✅ KEY ထည့်ရန်", callback_data="menu_enter_key"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Back", callback_data="menu_back"))
    return keyboard

def get_scam_button_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🛑 STOP SCAM", callback_data="menu_stop"),
        InlineKeyboardButton("🔙 Back", callback_data="menu_back")
    )
    return keyboard

def get_auth_keyboard():
    """Keyboard for password authentication"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("🔐 Enter Layer 1 Password ", callback_data="auth_layer1"),
        InlineKeyboardButton("🔐 Enter Layer 2 Password ", callback_data="auth_layer2"),
        InlineKeyboardButton("🔄 Reset Authentication", callback_data="auth_reset")
    )
    return keyboard

# ==================== ADMIN PANEL KEYBOARDS ====================

def get_admin_main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔑 Generate Key", callback_data="admin_genkey"),
        InlineKeyboardButton("🗑️ Delete Key", callback_data="admin_delkey"),
        InlineKeyboardButton("📋 List Keys", callback_data="admin_listkeys"),
        InlineKeyboardButton("📊 Bot Stats", callback_data="admin_stats"),
        InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast"),
        InlineKeyboardButton("👥 Users List", callback_data="admin_users"),
        InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")
    )
    return keyboard

def get_admin_genkey_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⏱️ 30m", callback_data="admin_gen_30m"),
        InlineKeyboardButton("⏱️ 1h", callback_data="admin_gen_1h"),
        InlineKeyboardButton("📅 1d", callback_data="admin_gen_1d"),
        InlineKeyboardButton("📅 7d", callback_data="admin_gen_7d"),
        InlineKeyboardButton("📅 1m", callback_data="admin_gen_1m"),
        InlineKeyboardButton("📅 1y", callback_data="admin_gen_1y"),
        InlineKeyboardButton("♾️ Unlimited", callback_data="admin_gen_unlimited"),
        InlineKeyboardButton("🔙 Back", callback_data="admin_back")
    )
    return keyboard

def get_admin_back_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("🔙 Back to Admin Panel", callback_data="admin_back"))
    return keyboard

# =====
