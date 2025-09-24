# bot.py
import asyncio
import random
import aiohttp
from telethon import TelegramClient, errors
from telethon.sessions import StringSession

# ----------------------------
# Hardcoded Config
# ----------------------------
API_ID = 27403368
API_HASH = "7cfc7759b82410f5d90641d6fc415f"
SESSION = "session"   # your session string or session.session file
GROUP_ID = -1003067016330  # group ID
DELAY_SECONDS = 10     # 10 seconds delay

HF_TOKEN = "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"
HF_MODEL = "gpt2"  # you can change to another HuggingFace model

# ----------------------------
# Telegram client
# ----------------------------
client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)

# ----------------------------
# HuggingFace text generation
# ----------------------------
async def generate_reply(prompt: str) -> str:
    url = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {"inputs": prompt, "max_length": 50, "temperature": 0.7}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status != 200:
                text = await resp.text()
                print(f"HF API error: {resp.status} - {text}")
                return "👍"
            data = await resp.json()
            if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                return data[0]["generated_text"].strip()
            return "👌"

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
                    print(f"Picked: {msg.text}")
                    reply_text = await generate_reply(msg.text)
                    try:
                        await client.send_message(GROUP_ID, reply_text, reply_to=msg.id)
                        print(f"Replied with: {reply_text}")
                    except errors.FloodWaitError as e:
                        print(f"Flood wait: Sleeping for {e.seconds} seconds")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print(f"Failed to send reply: {e}")
            await asyncio.sleep(DELAY_SECONDS)
        except Exception as e:
            print(f"Loop error: {e}")
            await asyncio.sleep(5)

async def run():
    async with client:
        await main()

# ----------------------------
# Run bot
# ----------------------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
