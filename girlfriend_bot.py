import os
import sqlite3
import random
import datetime
import pytz
import re

from telegram import Update
from telegram.ext import (
ApplicationBuilder,
MessageHandler,
CommandHandler,
ContextTypes,
filters
)

# -----------------------------
# Database
# -----------------------------
DB_PATH = "/data/girlfriend.db" if os.getenv("RENDER") else "girlfriend.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            chat_id INTEGER PRIMARY KEY,
            your_name TEXT,  
            her_name TEXT,
            mood TEXT
    )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            keyword TEXT,
            message TEXT
    )
    """)

    conn.commit()
    conn.close()

# -----------------------------
# Helper Functions
# -----------------------------
def get_memory(chat_id):
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT your_name, her_name, mood FROM memory WHERE chat_id = ?", (chat_id,))
row = c.fetchone()
conn.close()
return row

def save_memory(chat_id, your_name=None, her_name=None, mood=None):
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

if get_memory(chat_id) is None:
c.execute("INSERT INTO memory (chat_id, your_name, her_name, mood) VALUES (?, ?, ?, ?)",
(chat_id, your_name, her_name, mood))
else:
if your_name:
c.execute("UPDATE memory SET your_name = ? WHERE chat_id = ?", (your_name, chat_id))
if her_name:
c.execute("UPDATE memory SET her_name = ? WHERE chat_id = ?", (her_name, chat_id))
if mood:
c.execute("UPDATE memory SET mood = ? WHERE chat_id = ?", (mood, chat_id))

conn.commit()
conn.close()

def add_reminder(chat_id, keyword, message):
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("INSERT INTO reminders (chat_id, keyword, message) VALUES (?, ?, ?)", (chat_id, keyword.lower(), message))
conn.commit()
conn.close()

def get_keyword_reminders(chat_id, msg):
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT keyword, message FROM reminders WHERE chat_id = ?", (chat_id,))
rows = c.fetchall()
conn.close()

for kw, msg_response in rows:
if kw in msg.lower():
return msg_response
return None

# -----------------------------
# A. Mood Detection + Emojis
# -----------------------------
def detect_mood(msg):
msg = msg.lower()

mood_map = {
"tired": ["tired", "drained", "exhausted", "sleepy"],
"sad": ["sad", "depressed", "down", "cry"],
"angry": ["angry", "pissed", "frustrated", "mad"],
"happy": ["happy", "excited", "shiok", "yay"]
}

for mood, keywords in mood_map.items():
if any(word in msg for word in keywords):
return mood

return None

# -----------------------------
# B. SG-Style Reply Generator + Emojis
# -----------------------------
def sg_reply(text, your_name, her_name, mood):
base = [
f"Aiyo {your_name}, you so cute one leh 🥺💖",
f"Don’t worry lah {your_name}, I’m here for you always ❤️",
f"{your_name}, you make my heart so warm sia ☺️💕",
f"I miss you a bit already leh… 😳💞",
f"You okay anot? I care about you one you know 🥹"
]

# Mood-based reply with emojis
if mood == "tired":
base.append(f"{your_name}, you must rest more leh… later fall sick how? 😴💗")
elif mood == "sad":
base.append(f"Come here lah {your_name}, let me hug you… don’t sad already ok? 🥺🤍")
elif mood == "angry":
base.append(f"Aiyo who make you angry? I go whack them for you lah 😤💢")
elif mood == "happy":
base.append(f"Wah today you so happy ah {your_name}, I like sia 😄✨")

# Message content triggers
text_lower = text.lower()

if "love" in text_lower:
base.append(f"I love you too lah {your_name} ❤️🥺")
if "miss" in text_lower:
base.append(f"I also miss you leh… come closer abit 😳💕")
if "photo" in text_lower or "pic" in text_lower:
base.append(f"Wah you send me photo ah… I feel special sia 📸❤️")
if "sleep" in text_lower:
base.append(f"Go sleep a bit lah dear 😴❤️")

return random.choice(base)

# -----------------------------
# C. Photo Replies + Emojis
# -----------------------------
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
chat_id = update.effective_chat.id
your_name, her_name, mood = get_memory(chat_id)

replies = [
f"Wah {your_name}, this photo damn nice leh 😳📸",
f"Aiyo you send me photo ah… I feel so touched sia 🥺💗",
f"Hehe cute photo, I save inside my heart already ☺️❤️",
]

await update.message.reply_text(random.choice(replies))

# -----------------------------
# Main Message Handler
# -----------------------------
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
chat_id = update.effective_chat.id
msg = update.message.text

your_name, her_name, mood = get_memory(chat_id)

# Set her name
match_her = re.search(r"call you (.+)", msg.lower())
if match_her:
new_name = match_her.group(1).strip().title()
save_memory(chat_id, her_name=new_name)
await update.message.reply_text(f"Okay dear~ you can call me {new_name} from now on ❤️")
return

# Set your name
match_you = re.search(r"call me (.+)", msg.lower())
if match_you:
new_name = match_you.group(1).strip().title()
save_memory(chat_id, your_name=new_name)
await update.message.reply_text(f"Hehe okay~ I’ll call you {new_name} from now on 💕")
return

# Keyword reminder
keyword_message = get_keyword_reminders(chat_id, msg)
if keyword_message:
await update.message.reply_text(keyword_message)
return

# Mood detect
mood_now = detect_mood(msg)
if mood_now:
save_memory(chat_id, mood=mood_now)

# Generate reply
reply = sg_reply(msg, your_name or "dear", her_name or "baby", mood_now or mood)
await update.message.reply_text(reply)

# -----------------------------
# Scheduled Messages
# -----------------------------
async def scheduled_messages(app):
tz = pytz.timezone("Asia/Singapore")
now = datetime.datetime.now(tz)
hour = now.hour

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT chat_id, your_name FROM memory")
rows = c.fetchall()
conn.close()

for chat_id, your_name in rows:
if hour == 8:
await app.bot.send_message(chat_id, f"Good morning {your_name} ☀️😊 Have a nice day hor~")
if hour == 23:
await app.bot.send_message(chat_id, f"Good night {your_name} 🌙💤 Rest well okay? ❤️")
if random.random() < 0.03:
await app.bot.send_message(chat_id, f"I miss you a bit leh… 😳💞")

# -----------------------------
# MAIN
# -----------------------------
async def main():
init_db()

BOT_TOKEN = os.getenv("BOT_TOKEN")
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
app.add_handler(MessageHandler(filters.Entity("url"), text_handler))

# Scheduler every hour
app.job_queue.run_repeating(lambda ctx: scheduled_messages(app), interval=3600, first=10)

print("Girlfriend bot running…")
await app.run_polling()

if __name__ == "__main__":
import asyncio
asyncio.run(main())





