# bot.py
import os
import asyncio
import threading
import random
from telethon import TelegramClient, errors
from telethon.sessions import StringSession
from flask import Flask

# ----------------------------
# Load environment variables
# ----------------------------
api_id = int(os.environ.get('API_ID', '0'))
api_hash = os.environ.get('API_HASH')
session_str = os.environ.get('SESSION')   # string session you will create
group = int(os.environ.get('GROUP_ID', '-1003067016330'))
messages_file = os.environ.get('MESSAGES_FILE', 'messages.txt')
delay_seconds = int(os.environ.get('DELAY_SECONDS', '10'))  # default 10s

if not api_id or not api_hash or not session_str:
    raise RuntimeError("Missing one of API_ID, API_HASH or SESSION environment variables")

client = TelegramClient(StringSession(session_str), api_id, api_hash)

# ----------------------------
# Telegram bot logic
# ----------------------------
async def main():
    with open(messages_file, 'r', encoding='utf-8') as f:
        replies = [line.strip() for line in f if line.strip()]

    if not replies:
        print("⚠️ No replies found in messages.txt")
        return

    print(f"✅ Loaded {len(replies)} possible replies")

    while True:
        try:
            # fetch latest 5 messages
            messages = await client.get_messages(group, limit=5)
            if not messages:
                print("⚠️ No recent messages found, waiting...")
                await asyncio.sleep(delay_seconds)
                continue

            print("\n📥 Recent messages:")
            for m in messages:
                print(f" - {m.sender_id}: {m.text}")

            # pick one random recent message
            target = random.choice(messages)
            reply_text = random.choice(replies)

            print(f"\n🎯 Picking message to reply: {target.id} | {target.text}")
            print(f"💬 Reply chosen: {reply_text}")

            await client.send_message(group, reply_text, reply_to=target.id)
            print("✅ Message sent successfully")

        except errors.FloodWaitError as e:
            print(f"⏳ Flood wait: Sleeping for {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            print(f"❌ Error: {e}")

        print(f"⏱️ Waiting {delay_seconds} seconds before next action...")
        await asyncio.sleep(delay_seconds)

async def run():
    async with client:
        await main()

# ----------------------------
# Flask web server (for Render)
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# ----------------------------
# Run bot and Flask together
# ----------------------------
if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
