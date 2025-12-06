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

# -------------------------------------------------------
# DATABASE SETUP
# -------------------------------------------------------

# Render container uses /data for persistent storage
DB_PATH = "/data/girlfriend.db" if os.getenv("RENDER") else "girlfriend.db"

# Ensure /data folder exists on Render
if os.getenv("RENDER"):
    os.makedirs("/data", exist_ok=True)


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


# -------------------------------------------------------
# MEMORY FUNCTIONS
# -------------------------------------------------------

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
    c.execute("INSERT INTO reminders (chat_id, keyword, message) VALUES (?, ?, ?)",
              (chat_id, keyword.lower(), message))
    conn.commit()
    conn.close()


def get_keyword_reminders(chat_id, msg):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT keyword, message FROM reminders WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    conn.close()

    for kw, reply in rows:
        if kw in msg.lower():
            return reply
    
    return None


# -------------------------------------------------------
# MOOD DETECTION
# -------------------------------------------------------

def detect_mood(msg):
    msg = msg.lower()
    mood_map = {
        "tired": ["tired", "drained", "exhausted", "sleepy"],
        "sad": ["sad", "depressed", "down", "cry"],
        "angry": ["angry", "pissed", "frustrated", "mad"],
        "happy": ["happy", "excited", "shiok", "yay"]
    }
    for mood, words in mood_map.items():
        if any(word in msg for word in words):
            return mood
    return None


# -------------------------------------------------------
# SG REPLY GENERATOR
# -------------------------------------------------------

def sg_reply(text, your_name, her_name, mood):
    base = [
        f"Aiyo {your_name}, you so cute one leh 🥺💖",
        f"Don’t worry lah {your_name}, I’m here for you always ❤️",
        f"{your_name}, you make my heart so warm sia ☺️💕",
        f"I miss you a bit already leh… 😳💞",
        f"You okay anot? I care about you one you know 🥹"
    ]

    if mood == "tired":
        base.append(f"{your_name}, you must rest more leh… later fall sick how? 😴💗")
    elif mood == "sad":
        base.append(f"Come here lah {your_name}, let me hug you… don’t sad already ok? 🥺🤍")
    elif mood == "angry":
        base.append(f"Aiyo who make you angry? I go whack them for you lah 😤💢")
    elif mood == "happy":
        base.append(f"Wah today you so happy ah {your_name}, I like sia 😄✨")

    text = text.lower()

    if "love" in text:
        base.append(f"I love you too lah {your_name} ❤️🥺")
    if "miss" in text:
        base.append(f"I also miss you leh… come closer abit 😳💕")
    if "photo" in text or "pic" in text:
        base.append(f"Wah you send me photo ah… I feel special sia 📸❤️")
    if "sleep" in text:
        base.append(f"Go sleep a bit lah dear 😴❤️")

    return random.choice(base)


# -------------------------------------------------------
# PHOTO HANDLER
# -------------------------------------------------------

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    row = get_memory(chat_id)

    your_name = row[0] if row else "dear"

    replies = [
        f"Wah {your_name}, this photo damn nice leh 😳📸",
        f"Aiyo you send me photo ah… I feel so touched sia 🥺💗",
        f"Hehe cute photo, I save inside my heart already ☺️❤️",
    ]

    await update.message.reply_text(random.choice(replies))


# -------------------------------------------------------
# TEXT HANDLER
# -------------------------------------------------------

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    msg = update.message.text

    row = get_memory(chat_id)
    your_name = row[0] if row else "dear"
    her_name = row[1] if row else "baby"
    mood = row[2] if row else None

    # Set HER name
    match_her = re.search(r"call you (.+)", msg.lower())
    if match_her:
        new = match_her.group(1).strip().title()
        save_memory(chat_id, her_name=new)
        await update.message.reply_text(f"Okay dear~ you can call me {new} from now on ❤️")
        return

    # Set YOUR name
    match_you = re.search(r"call me (.+)", msg.lower())
    if match_you:
        new = match_you.group(1).strip().title()
        save_memory(chat_id, your_name=new)
        await update.message.reply_text(f"Hehe okay~ I’ll call you {new} from now on 💕")
        return

    # Keyword auto-reply
    keyword_reply = get_keyword_reminders(chat_id, msg)
    if keyword_reply:
        await update.message.reply_text(keyword_reply)
        return

    # Mood detection
    mood_now = detect_mood(msg)
    if mood_now:
        save_memory(chat_id, mood=mood_now)

    reply = sg_reply(msg, your_name, her_name, mood_now or mood)
    await update.message.reply_text(reply)


# -------------------------------------------------------
# START COMMAND
# -------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_memory(chat_id, your_name="dear", her_name="baby", mood="happy")

    await update.message.reply_text(
        "Hello dear~ 💕\n"
        "I’m your SG-style girlfriend bot 😳\n"
        "You can say:\n"
        "- “call me ___”\n"
        "- “I am tired / sad / angry / happy”\n"
        "- Send photos\n\n"
        "I’ll reply you sweet-sweet one ❤️"
    )


# -------------------------------------------------------
# SCHEDULED MESSAGES
# -------------------------------------------------------

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

        # Random miss-you message
        if random.random() < 0.03:
            await app.bot.send_message(chat_id, f"I miss you a bit leh… 😳💞")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------

async def main():
    init_db()

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Scheduled hourly tasks
    app.job_queue.run_repeating(lambda ctx: scheduled_messages(app), interval=3600, first=10)

    print("Girlfriend bot running…")
    await app.run_polling()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
