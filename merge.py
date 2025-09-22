
# raid_bot_merged.py
import re
import os
import json
import time
import random
from datetime import datetime
from telethon import TelegramClient, events, functions, Button
from playwright.sync_api import sync_playwright

# ------------------ CONFIG ------------------
API_ID = 27403368
API_HASH = "7cfc7759b82410f5d90641d6a6fc415f"
SESSION = "session"               # session.session
WATCH_GROUPS = [-1002786329549]   # group id(s)
KNOWN_RAID_BOTS = ["raidar"]      # raid bot usernames
LOG_FILE = "raid_training_data.json"

TRIAL_REPLIES = [
    "Smash ✅🔥",
    "In! 🚀",
    "Let’s go fam 💯",
    "Replying as a test ⚡",
    "Trial reply — automated"
]

COOKIE_AUTH_TOKEN = os.environ.get("TW_COOKIE")  # cookie string, auth token, or cookies.json path
# --------------------------------------------

TWEET_RE = re.compile(
    r"(https?://(?:t\.co|(?:mobile\.)?twitter\.com|(?:www\.)?twitter\.com|x\.com)/[^\s]+/status(?:es)?/(\d+))",
    re.IGNORECASE
)

# ---------------- UTILS ----------------
def now_iso():
    return datetime.utcnow().isoformat() + "Z"

def save_json_append(path, entry):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump([], f)
    with open(path, "r+") as f:
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

def get_random_message(file_path="messages.txt"):
    if not os.path.exists(file_path):
        return random.choice(TRIAL_REPLIES)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
        if not lines:
            return random.choice(TRIAL_REPLIES)
        return random.choice(lines)
    except Exception:
        return random.choice(TRIAL_REPLIES)

def parse_cookie_input(cookie_input):
    if not cookie_input:
        return []
    if os.path.exists(cookie_input):
        with open(cookie_input, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []
    if "=" not in cookie_input:
        return [{"name": "auth_token", "value": cookie_input.strip(), "domain": ".x.com", "path": "/"}]
    cookies = []
    for p in cookie_input.split(";"):
        if "=" in p:
            name, val = p.split("=", 1)
            cookies.append({"name": name.strip(), "value": val.strip(), "domain": ".x.com", "path": "/"})
    return cookies

# ------------- Playwright Reply Function -------------
def send_twitter_reply(tweet_url, reply_message, headless=True):
    cookies = parse_cookie_input(COOKIE_AUTH_TOKEN)
    if not cookies:
        print("[❌] No valid cookies. Skipping tweet reply.")
        return

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context()
            context.add_cookies(cookies)

            page = context.new_page()
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.5)

            page.goto(tweet_url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.5)

            textbox_selectors = [
                "div[aria-label='Tweet text']",
                "div[role='textbox'][contenteditable='true']",
                "div[aria-label='Reply'] div[role='textbox']",
                "div[data-testid='tweetTextarea_0']",
            ]
            sel = None
            for s in textbox_selectors:
                try:
                    if page.query_selector(s):
                        sel = s
                        break
                except: continue

            if not sel:
                reply_buttons = ["div[data-testid='reply']", "div[role='button'][data-testid='reply']"]
                for rb in reply_buttons:
                    try:
                        if page.query_selector(rb):
                            page.click(rb)
                            time.sleep(1)
                            for s in textbox_selectors:
                                if page.query_selector(s):
                                    sel = s
                                    break
                    except: continue

            if not sel:
                print("[⚠️] Reply textbox not found. Skipping.")
                return

            page.click(sel)
            time.sleep(0.2)
            page.fill(sel, reply_message)
            time.sleep(0.3)

            send_selectors = [
                "div[data-testid='tweetButtonInline']",
                "div[data-testid='tweetButton']",
                "div[data-testid='replyButton']",
            ]
            sent = False
            for s in send_selectors:
                try:
                    btn = page.query_selector(s)
                    if btn:
                        btn.click()
                        sent = True
                        break
                except: continue

            if not sent:
                try:
                    page.keyboard.down("Control")
                    page.keyboard.press("Enter")
                    page.keyboard.up("Control")
                    sent = True
                except: pass

            if sent:
                print(f"[✔] Reply submitted to {tweet_url}")
            else:
                print("[❌] Failed to send reply")

            context.close()
            browser.close()
    except Exception as e:
        print(f"[❌] Exception in Playwright: {e}")

# ------------- Telegram Client -------------
client = TelegramClient(SESSION, API_ID, API_HASH)

async def click_inline_button(client, message, match_texts=("👊",)):
    buttons = getattr(message, "buttons", None) or getattr(message, "reply_markup", None)
    if not buttons: return {"clicked": False, "reason": "no_buttons"}

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
                except Exception as e:
                    return {"clicked": False, "button_text": lbl, "error": repr(e)}
    return {"clicked": False, "reason": "no_matching_label"}

@client.on(events.NewMessage(chats=WATCH_GROUPS, incoming=True))
async def handler(event):
    try:
        msg = event.message
        sender = await event.get_sender()
        sender_id = getattr(sender, "id", None)

        print(f"\n[DEBUG] chat_id={event.chat_id} | sender_id={sender_id} | message_id={msg.id}")

        if not sender_id or sender_id not in [5994885234]:
            return

        tweet_url, tweet_id = extract_tweet(msg.text or "")
        print(f"[🚨] RAID DETECTED | Tweet: {tweet_url}")

        click_result = await click_inline_button(client, msg, match_texts=("👊",))
        print("🔘 Button click result:", click_result)

        reply_message = get_random_message()
        if tweet_url:
            send_twitter_reply(tweet_url, reply_message)

        entry = {
            "time": now_iso(),
            "chat_id": event.chat_id,
            "message_id": msg.id,
            "tweet_url": tweet_url,
            "smash": click_result,
            "message": reply_message
        }
        save_json_append(LOG_FILE, entry)
    except Exception as e:
        print(f"[❌] Error in handler: {e}")

# ------------- Main -------------
def main():
    print("🚀 Starting raid_bot_merged...")
    client.start()
    print("✅ Connected to Telegram. Waiting for raids...")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
