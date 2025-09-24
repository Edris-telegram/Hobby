# bot.py
import os
import asyncio
import random
import aiohttp
from telethon import TelegramClient, errors

# ----------------------------
# Config (yours filled in)
# ----------------------------
API_ID = 27403368  
API_HASH = "7cfc7759b82410f5d90641d6fc415f"  
SESSION_FILE = "session.session"   # make sure this file is uploaded to Railway
GROUP_ID = -1003067016330          # your group ID
DELAY_SECONDS = 10                 # reply interval

HF_TOKEN = "your_huggingface_token_here"   # 🔹 put your HF token here
HF_MODEL = "google/flan-t5-base"  # better free model than gpt2

if not HF_TOKEN:
    raise RuntimeError("Missing HuggingFace token (HF_TOKEN)")

client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

# ----------------------------
# HuggingFace text generation
# ----------------------------
async def generate_reply(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "max_length": 60, "temperature": 0.7}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            raw = await resp.text()
            print(f"[HF DEBUG] Status {resp.status} | Raw: {raw[:200]}")

            if resp.status != 200:
                return f"⚠️ HF API error {resp.status}"

            try:
                data = await resp.json()
            except Exception as e:
                print(f"[HF DEBUG] JSON parse error: {e}")
                return "⚠️ Parse error"

            # Handle list response
            if isinstance(data, list) and len(data) > 0:
                if "generated_text" in data[0]:
                    return data[0]["generated_text"].strip()
                if "summary_text" in data[0]:
                    return data[0]["summary_text"].strip()

            # Handle dict response
            if isinstance(data, dict):
                if "generated_text" in data:
                    return data["generated_text"].strip()
                if "summary_text" in data:
                    return data["summary_text"].strip()

            return "🤖 (no meaningful reply)"

# ----------------------------
# Telegram bot logic
# ----------------------------
async def main():
    while True:
        try:
            msgs = await client.get_messages(GROUP_ID, limit=5)
            if msgs:
                msg = random.choice(msgs)
                if msg.text:
                    print(f"[BOT] Picked message: {msg.text}")

                    reply_text = await generate_reply(msg.text)
                    print(f"[BOT] Generated reply: {reply_text}")

                    try:
                        await client.send_message(GROUP_ID, reply_text, reply_to=msg.id)
                        print(f"[BOT] ✅ Sent reply")
                    except errors.FloodWaitError as e:
                        print(f"[BOT] Flood wait: sleeping {e.seconds}s")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"[BOT] ❌ Failed to send reply: {e}")

            await asyncio.sleep(DELAY_SECONDS)
        except Exception as e:
            print(f"[BOT] Loop error: {e}")
            await asyncio.sleep(5)

async def run():
    async with client:
        await main()

# ----------------------------
# Run bot
# ----------------------------
if __name__ == "__main__":
    print("🚀 Bot starting...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
