import os
import json
import threading
import time
import requests
from flask import Flask, Response, jsonify, render_template, request
from flask_cors import CORS
import telebot

# --- CONFIGURATION (Aapki Details) ---
BOT_TOKEN = "8551423875:AAG2f2IV4t-rvxZqGERGy2USymQ5sL1vwO4"
ADMIN_ID = 7415661180  # Sirf aap admin ho

app = Flask(__name__)
CORS(app)
bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE SYSTEM (Automatic JSON) ---
DB_FILE = "database.json"

# Default Channels (Agar DB naya bane to ye data rahega)
DEFAULT_DB = {
    "channels": {
        "sony-yay": {
            "name": "Sony YAY!",
            "url": "http://103.182.170.32:8888/play/a04m",
            "cat": "Kids"
        },
        "nick": {
            "name": "Nick India",
            "url": "http://103.182.170.32:8888/play/a04q",
            "cat": "Kids"
        }
    },
    "users": []  # Bot users ki list
}

# Database Load/Create Logic
def load_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w') as f:
            json.dump(DEFAULT_DB, f, indent=4)
        print("✅ New Database Created!")
        return DEFAULT_DB
    try:
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    except:
        return DEFAULT_DB

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Load data on startup
db = load_db()

# --- ADMIN PERMISSION CHECK ---
def is_admin(user_id):
    return user_id == ADMIN_ID

# --- TELEGRAM BOT COMMANDS (Admin Panel) ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    uid = message.from_user.id
    name = message.from_user.first_name
    
    # User ko DB me save karo (Broadcast ke liye)
    if uid not in db['users']:
        db['users'].append(uid)
        save_db(db)

    bot.reply_to(message, 
                 f"👋 **Hello {name}!**\n\n"
                 f"📺 **Shinmon Live Streaming Bot**\n"
                 f"🔗 Website Link: {request.host_url if request.host_url else 'Wait for Deploy'}\n\n"
                 f"🤖 _Powered by Python Backend_")

# 1. ADD CHANNEL (/add id|Name|Link|Category)
@bot.message_handler(commands=['add'])
def add_channel(message):
    if not is_admin(message.from_user.id):
        return bot.reply_to(message, "⛔ Sirf Admin ye kar sakta hai!")

    try:
        text = message.text.replace('/add ', '')
        # Format: id|Name|Link|Category
        cid, name, url, cat = text.split('|')
        
        db['channels'][cid.strip()] = {
            "name": name.strip(),
            "url": url.strip(),
            "cat": cat.strip()
        }
        save_db(db)
        bot.reply_to(message, f"✅ **Added Successfully!**\n\n🆔 ID: `{cid}`\n📺 Name: {name}", parse_mode='Markdown')
    except:
        bot.reply_to(message, "⚠️ **Wrong Format!**\nUse: `/add id|Name|URL|Category`")

# 2. DELETE CHANNEL (/del id)
@bot.message_handler(commands=['del'])
def delete_channel(message):
    if not is_admin(message.from_user.id): return
    
    cid = message.text.replace('/del ', '').strip()
    if cid in db['channels']:
        del db['channels'][cid]
        save_db(db)
        bot.reply_to(message, f"🗑️ **Channel Deleted:** `{cid}`")
    else:
        bot.reply_to(message, "❌ ID nahi mila.")

# 3. LIVE STATUS CHECK (/check id)
@bot.message_handler(commands=['check'])
def check_status(message):
    cid = message.text.replace('/check ', '').strip()
    if cid in db['channels']:
        url = db['channels'][cid]['url']
        bot.reply_to(message, f"🔄 Checking connection for **{cid}**...")
        try:
            r = requests.get(url, stream=True, timeout=5)
            if r.status_code == 200:
                bot.reply_to(message, f"✅ **ONLINE**\nServer responded with 200 OK.")
            else:
                bot.reply_to(message, f"⚠️ **ISSUE**\nStatus Code: {r.status_code}")
        except Exception as e:
            bot.reply_to(message, f"❌ **OFFLINE**\nError: {str(e)}")
    else:
        bot.reply_to(message, "❌ Channel ID not found.")

# 4. BROADCAST (/cast Message)
@bot.message_handler(commands=['cast'])
def broadcast(message):
    if not is_admin(message.from_user.id): return
    
    msg = message.text.replace('/cast ', '')
    sent = 0
    for uid in db['users']:
        try:
            bot.send_message(uid, f"📢 **Announcement:**\n\n{msg}")
            sent += 1
        except: pass
    
    bot.reply_to(message, f"✅ Sent to {sent} users.")

# 5. LIST ALL (/list)
@bot.message_handler(commands=['list'])
def list_all(message):
    if not is_admin(message.from_user.id): return
    
    msg = "📋 **Channel Database:**\n\n"
    for cid, data in db['channels'].items():
        msg += f"🔹 `{cid}` : {data['name']}\n"
    
    bot.reply_to(message, msg, parse_mode='Markdown')


# --- FLASK BACKEND (Streaming Core) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/channels')
def get_channels_api():
    return jsonify(db['channels'])

@app.route('/stream/<channel_id>')
def stream_video(channel_id):
    if channel_id not in db['channels']:
        return "Not Found", 404

    stream_url = db['channels'][channel_id]['url']
    
    # Headers to mimic a real browser (Prevents blocking)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    def generate():
        try:
            with requests.get(stream_url, headers=headers, stream=True, timeout=10) as r:
                r.raise_for_status()
                for chunk in r.iter_content(chunk_size=8192): # 8KB Chunks
                    yield chunk
        except Exception as e:
            print(f"Stream Error: {e}")

    return Response(generate(), mimetype='video/mp4', headers={
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": "no-cache"
    })

# --- RUNNER ---
def run_bot():
    bot.infinity_polling()

# Threading to run Bot & Server together
t = threading.Thread(target=run_bot)
t.daemon = True
t.start()

if __name__ == '__main__':
    # Render uses PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)