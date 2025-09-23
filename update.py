# raid_auto_twitter.py
# -> Updated with background Twitter engagement loop using Hugging Face replies.
# Requirements: tweepy, telethon, requests, python-dotenv
# Install: pip install tweepy telethon requests python-dotenv

import re
import json
import os
import random
import requests
import time
import threading
from datetime import datetime
from telethon import TelegramClient, events, functions
import tweepy

# ------------------ TELEGRAM CONFIG ------------------
API_ID = "27403368"
API_HASH = "7cfc7759b82410f5d90641d6fc415f8"
SESSION = "session"               # session.session
RAID_BOT_IDS = [5994885234]       # allowed raid bot ID(s)
LOG_FILE = "raid_training_data.json"

# ------------------ GROUP CONFIG ------------------
CONFIG_FILE = "groups_config.json"
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        GROUPS_CONFIG = json.load(f)
else:
    GROUPS_CONFIG = {}

WATCH_GROUPS = [int(gid) for gid in GROUPS_CONFIG.keys()]

# ------------------ TWITTER CONFIG ------------------
API_KEY = os.getenv("API_KEY") or "OwRbI9wi8eglE4yAxeiJgdtBr"
API_SECRET = os.getenv("API_SECRET") or "HenKDXkitpno7Ciiql1FWuq1aDVuGamocqu2gswHfDMe7j6qjk"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or "1917680783331930112-VFp1mvpIqq5xYfxBbG3IiWLPbCJrc9"
ACCESS_TOKEN_SECRET = os.getenv("ACCESS_TOKEN_SECRET") or "TjIVuZrh0Re7KdkCCsKwuUtTmFSU18UNvuq4tBxSHhh3h"
BEARER_TOKEN = os.getenv("BEARER_TOKEN") or "AAAAAAAAAAAAAAAAAAAAAAALU24QEAAAAA%2BJgMXUnzs6YRb2w5iEw4E%2FXtgkM%3DVThVeUHqvPH4EAyEqXdTLYzlfOXD8bPBwoCx52xkflPJyf8Nop"

# ==== Authenticate Tweepy v2 client ====
twitter_client = tweepy.Client(
    bearer_token=BEARER_TOKEN,
    consumer_key=API_KEY,
    consumer_secret=API_SECRET,
    access_token=ACCESS_TOKEN,
    access_token_secret=ACCESS_TOKEN_SECRET,
    wait_on_rate_limit=True
)

# ------------------ HUGGING FACE CONFIG ------------------
HUGGINGFACE_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")
HF_MODEL = os.getenv("HF_MODEL", "pszemraj/flan-t5-small-instructiongen")
HF_API_URL = f"https://api-inference.huggingface.co/models/{HF_MODEL}"

TRIAL_REPLIES = [
    "Nice one 🚀",
    "Smash ✅🔥",
    "In fam 💯",
    "Solid point 👌"
]

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)
sent_tweet_ids = set()

def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w") as f:
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

def extract_tweet(text):
    if not text:
        return None, None
    m = TWEET_RE.search(text)
    if m:
        return m.group(1), m.group(2)
    return None, None

# ------------------ Hugging Face reply generator ------------------
def generate_reply_via_hf(tweet_text: str, max_chars=240) -> str:
    if not tweet_text:
        return random.choice(TRIAL_REPLIES)
    if not HUGGINGFACE_API_TOKEN:
        return random.choice(TRIAL_REPLIES)

    prompt = (
        "You are a friendly, concise social media commenter. "
        "Given the tweet below, write ONE short reply (<= 240 chars) that is positive, "
        "avoids links, avoids personal info, and may use light emoji.\n\n"
        f"Tweet: \"{tweet_text}\"\n\nReply:"
    )

    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}", "Accept": "application/json"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 64, "temperature": 0.7, "top_p": 0.9}}

    try:
        resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=20)
        if resp.status_code != 200:
            return random.choice(TRIAL_REPLIES)
        data = resp.json()
        text = None
        if isinstance(data, list):
            first = data[0]
            if isinstance(first, dict) and "generated_text" in first:
                text = first["generated_text"]
            elif isinstance(first, str):
                text = first
        if not text:
            return random.choice(TRIAL_REPLIES)
        text = " ".join(text.strip().splitlines())
        if len(text) > max_chars:
            text = text[: max_chars - 3].rstrip() + "..."
        return text
    except:
        return random.choice(TRIAL_REPLIES)

# ------------------ Twitter helpers ------------------
def fetch_tweet_text(tweet_id: str) -> str:
    try:
        resp = twitter_client.get_tweet(id=int(tweet_id), tweet_fields=["text"])
        if resp and getattr(resp, "data", None):
            return resp.data.text or ""
    except:
        return ""
    return ""

def reply_on_twitter(tweet_id, reply_text):
    try:
        twitter_client.create_tweet(text=reply_text, in_reply_to_tweet_id=int(tweet_id))
        print(f"✅ Auto-replied to {tweet_id}: {reply_text}")
    except Exception as e:
        print("❌ Reply error:", e)

def like_tweet(tweet_id):
    try:
        twitter_client.like(int(tweet_id))
        print(f"👍 Liked tweet {tweet_id}")
    except Exception as e:
        print("❌ Like error:", e)

def retweet_tweet(tweet_id):
    try:
        twitter_client.retweet(int(tweet_id))
        print(f"🔁 Retweeted {tweet_id}")
    except Exception as e:
        print("❌ Retweet error:", e)

# ------------------ Background engagement loop ------------------
def engagement_loop():
    while True:
        try:
            # get your own user ID
            me = twitter_client.get_me()
            my_id = me.data.id

            # fetch accounts you follow
            following = twitter_client.get_users_following(my_id, max_results=50)
            if not following.data:
                time.sleep(1800)
                continue

            friend = random.choice(following.data)
            timeline = twitter_client.get_users_tweets(friend.id, max_results=5, tweet_fields=["text"])
            if not timeline.data:
                time.sleep(1800)
                continue

            tweet = random.choice(timeline.data)
            tweet_id = tweet.id
            tweet_text = tweet.text

            action = random.choices(["like", "retweet", "reply"], weights=[0.5, 0.2, 0.3])[0]

            if action == "like":
                like_tweet(tweet_id)
            elif action == "retweet":
                retweet_tweet(tweet_id)
            elif action == "reply":
                reply_text = generate_reply_via_hf(tweet_text)
                reply_on_twitter(tweet_id, reply_text)

        except Exception as e:
            print("❌ Engagement loop error:", e)

        # wait 30–60 minutes
        wait_time = random.randint(1800, 3600)
        print(f"⏳ Next engagement in {wait_time // 60} minutes...")
        time.sleep(wait_time)

# ------------------ TELEGRAM HANDLERS ------------------
client = TelegramClient(SESSION, API_ID, API_HASH)

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons:
        return {"clicked": False}

    for row in buttons:
        for btn in row:
            lbl = getattr(btn, "text", "") or ""
            if any(mt.lower() in lbl.lower() for mt in match_texts):
                try:
                    await client(functions.messages.GetBotCallbackAnswerRequest(
                        peer=message.to_id, msg_id=message.id, data=btn.data or b""
                    ))
                    return {"clicked": True, "button_text": lbl}
                except Exception as e:
                    return {"clicked": False, "error": repr(e)}
    return {"clicked": False}

@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)
        if not sender_id or sender_id not in RAID_BOT_IDS:
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        if not tweet_id:
            return

        tweet_text = fetch_tweet_text(tweet_id) or (msg.text or "")[:800]
        message_to_send = generate_reply_via_hf(tweet_text)

        if tweet_id not in sent_tweet_ids:
            sent_tweet_ids.add(tweet_id)
            reply_on_twitter(tweet_id, message_to_send)

        entry = {"time": now_iso(), "tweet_id": tweet_id, "reply": message_to_send}
        save_json_append(LOG_FILE, entry)
        time.sleep(random.uniform(2.0, 5.0))
    except Exception as e:
        print("❌ Handler error:", e)

# ------------------ MAIN ------------------
def main():
    print("🚀 Starting raid_auto_twitter with natural engagement...")
    # start background loop
    threading.Thread(target=engagement_loop, daemon=True).start()
    client.start()
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
