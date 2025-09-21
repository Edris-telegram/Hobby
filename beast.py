#!/usr/bin/env python3
import os
import re
import json
import random
import threading
import asyncio
from datetime import datetime
from flask import Flask, jsonify
from telethon import TelegramClient, events, functions
import tweepy

# ------------------
# Environment / config
# ------------------
def _csv_to_int_list(s):
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip()]

# Telegram
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "session")
WATCH_GROUPS = _csv_to_int_list(os.getenv("WATCH_GROUPS", ""))
RAID_BOT_IDS = _csv_to_int_list(os.getenv("RAID_BOT_IDS", ""))
LOG_FILE = os.getenv("LOG_FILE", "raid_training_data.json")

# Twitter
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# Flask / runtime
PORT = int(os.getenv("PORT", 10000))

# ------------------
# Setup Twitter client (optional)
# ------------------
twitter_client = None
if TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET:
    try:
        twitter_client = tweepy.Client(
            bearer_token=TWITTER_BEARER_TOKEN or None,
            consumer_key=TWITTER_API_KEY,
            consumer_secret=TWITTER_API_SECRET,
            access_token=TWITTER_ACCESS_TOKEN,
            access_token_secret=TWITTER_ACCESS_TOKEN_SECRET
        )
        print("[TWITTER] Client initialized")
    except Exception as e:
        print("[WARN] Twitter client init failed:", e)
else:
    print("[TWITTER] Credentials missing, skipping Twitter replies")

# ------------------
# Helpers
# ------------------
TRIAL_REPLIES = ["Smash ✅🔥", "In! 🚀", "Let’s go fam 💯", "Trial reply — automated"]
TWEET_RE = re.compile(r"(https?://(?:t\.co|twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))", re.IGNORECASE)
sent_tweet_ids = set()

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    try:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                json.dump([], f)
        with open(path, "r+", encoding="utf-8") as f:
            try:
                arr = json.load(f)
            except:
                arr = []
            arr.append(entry)
            f.seek(0)
            json.dump(arr, f, indent=2)
            f.truncate()
    except:
        pass

def extract_tweet(text):
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return None, None

def get_random_message():
    return random.choice(TRIAL_REPLIES)

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        return {"clicked": False, "reason": "no_buttons"}
    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except:
                    return {"clicked": False, "button_text": lbl, "error": "failed"}
    return {"clicked": False, "reason": "no_matching_label"}

def reply_on_twitter(tweet_url, tweet_id, reply_text):
    if not twitter_client:
        return None
    try:
        resp = twitter_client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        print(f"[TWITTER] Replied to {tweet_url}: {reply_text}")
        return getattr(resp, "data", None)
    except Exception as e:
        print("[ERROR] Twitter reply failed:", e)
        return None

# ------------------
# Telegram client
# ------------------
if TELEGRAM_API_ID and TELEGRAM_API_HASH:
    client = TelegramClient(TELEGRAM_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    @client.on(events.NewMessage(chats=WATCH_GROUPS or None, incoming=True))
    async def handler(event):
        try:
            msg = event.message
            sender = await event.get_sender()
            sender_id = getattr(sender, "id", None)
            if RAID_BOT_IDS and (not sender_id or sender_id not in RAID_BOT_IDS):
                return
            tweet_url, tweet_id = extract_tweet(msg.text or "")
            if not tweet_id:
                return
            click_result = await click_inline_button(client, msg)
            message_to_send = get_random_message()
            twitter_data = None
            if tweet_id not in sent_tweet_ids:
                sent_tweet_ids.add(tweet_id)
                twitter_data = reply_on_twitter(tweet_url, tweet_id, message_to_send)
            entry = {
                "time": now_iso(),
                "chat_id": getattr(event, "chat_id", None),
                "message_id": msg.id,
                "tweet_url": tweet_url,
                "tweet_id": tweet_id,
                "smash": click_result,
                "reply": message_to_send,
                "twitter_response": twitter_data
            }
            save_json_append(LOG_FILE, entry)
        except:
            pass
else:
    client = None
    print("[TELEGRAM] Missing API ID or HASH, skipping Telegram")

# ------------------
# Flask dummy server
# ------------------
app = Flask(__name__)

@app.route("/")
def index():
    return jsonify({"status": "ok", "service": "beast", "telegram_enabled": bool(client), "timestamp": now_iso()})

@app.route("/health")
def health():
    return "healthy", 200

# ------------------
# Start Telegram in background thread
# ------------------
def start_telegram_client():
    if not client:
        return
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(client.start())
    print("[TELEGRAM] Connected, waiting for events...")
    loop.run_until_complete(client.run_until_disconnected())

# ------------------
# Entrypoint
# ------------------
if __name__ == "__main__":
    t = threading.Thread(target=start_telegram_client, daemon=True)
    t.start()
    print(f"[FLASK] Starting server on 0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
