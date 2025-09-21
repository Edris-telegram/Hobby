#!/usr/bin/env python3
# beast.py
import os
import re
import json
import random
import threading
from datetime import datetime
from flask import Flask, jsonify
from telethon import TelegramClient, events, functions
import tweepy

# ------------------
# Environment / config (all from env)
# ------------------
def _csv_to_int_list(s):
    if not s:
        return []
    return [int(x.strip()) for x in s.split(",") if x.strip()]

# Telegram
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0") or 0)
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "session")
WATCH_GROUPS = _csv_to_int_list(os.getenv("WATCH_GROUPS", ""))  # comma separated
RAID_BOT_IDS = _csv_to_int_list(os.getenv("RAID_BOT_IDS", ""))  # comma separated
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
# Setup Twitter client (tweepy v4+)
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
    except Exception as e:
        print("[WARN] Failed to init tweepy client:", e)
else:
    print("[WARN] Twitter credentials not fully set. Twitter replies will be skipped.")

# ------------------
# Helpers
# ------------------
TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Trial reply — automated"
]

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

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
            except Exception:
                arr = []
            arr.append(entry)
            f.seek(0)
            json.dump(arr, f, indent=2)
            f.truncate()
    except Exception as e:
        print("[WARN] Could not write log:", e)

def extract_tweet(text):
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return None, None

def get_random_message(file_path="messages.txt"):
    if not os.path.exists(file_path):
        return random.choice(TRIAL_REPLIES)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return random.choice(TRIAL_REPLIES)
        return random.choice(lines)
    except Exception as e:
        print("[WARN] Error reading messages file:", e)
        return random.choice(TRIAL_REPLIES)

def reply_on_twitter(tweet_url, tweet_id, reply_text):
    if not twitter_client:
        print("[WARN] No twitter client: skipping reply")
        return None
    try:
        resp = twitter_client.create_tweet(text=reply_text, in_reply_to_tweet_id=tweet_id)
        print(f"[TWITTER] Replied to {tweet_url}: {reply_text}")
        return getattr(resp, "data", None)
    except Exception as e:
        print("[ERROR] Twitter reply failed:", e)
        return None

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        return {"clicked": False, "reason": "no_buttons"}
    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    # Attempt to call the bot callback
                    res = await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id,
                        msg_id=message.id,
                        data=btn.data or b""
                    ))
                    print(f"[🔘] Clicked inline button: {lbl}")
                    return {"clicked": True, "button_text": lbl, "callback_result": str(res)}
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

# ------------------
# Telegram client and handler
# ------------------
if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
    print("[ERROR] TELEGRAM_API_ID or TELEGRAM_API_HASH not set. Telegram functionality disabled.")
    client = None
else:
    client = TelegramClient(TELEGRAM_SESSION, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    @client.on(events.NewMessage(chats=WATCH_GROUPS or None, incoming=True))
    async def handler(event):
        try:
            msg = event.message
            sender = await event.get_sender()
            sender_id = getattr(sender, "id", None)

            if RAID_BOT_IDS and (not sender_id or sender_id not in RAID_BOT_IDS):
                # ignore messages not from allowed bot ids (if RAID_BOT_IDS set)
                return

            tweet_url, tweet_id = extract_tweet(msg.text or "")
            if not tweet_id:
                return

            print(f"\n🚨 [RAID DETECTED] Tweet: {tweet_url}")

            click_result = await click_inline_button(client, msg, match_texts=("👊", "smash", "SMASH"))
            message_to_send = get_random_message()

            twitter_data = None
            if tweet_id not in sent_tweet_ids:
                sent_tweet_ids.add(tweet_id)
                twitter_data = reply_on_twitter(tweet_url, tweet_id, message_to_send)
            else:
                print("[WARN] Already replied to tweet:", tweet_id)

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

        except Exception as e:
            print("[ERROR] Handler exception:", repr(e))

# ------------------
# Flask dummy app (keeps Render happy)
# ------------------
app = Flask(__name__)

@app.route("/")
def index():
    info = {
        "status": "ok",
        "service": "beast",
        "telegram_enabled": bool(client),
        "watch_groups": WATCH_GROUPS,
        "timestamp": now_iso()
    }
    return jsonify(info)

@app.route("/health")
def health():
    return "healthy", 200

@app.route("/metrics")
def metrics():
    # simple metric: number of tweets replied to in this process
    return jsonify({"sent_tweet_count": len(sent_tweet_ids)})

def start_telegram_client():
    if not client:
        print("[INFO] Telegram client not configured; skipping start.")
        return
    try:
        print("[TELEGRAM] Starting Telegram client...")
        client.start()
        print("[TELEGRAM] Connected. Now waiting for events...")
        client.run_until_disconnected()
    except Exception as e:
        print("[TELEGRAM] Client error:", e)

# ------------------
# Entrypoint
# ------------------
if __name__ == "__main__":
    # Start Telegram client in background thread so Flask can serve the port
    t = threading.Thread(target=start_telegram_client, daemon=True)
    t.start()

    # Start Flask (bind to PORT so Render detects an open port)
    print(f"[FLASK] Starting server on 0.0.0.0:{PORT}")
    app.run(host="0.0.0.0", port=PORT)
