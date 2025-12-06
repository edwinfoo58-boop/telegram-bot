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
    filters,
)

# -------------------------------------------------------
# DATABASE SETUP
# -------------------------------------------------------

# Store DB in project folder (Render free web services cannot use /data)
DB_PATH = "girlfriend.db"


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
# A. MOOD DETECTION + EMOJIS
# -------------------------------------------------------

def detect_mood(msg: str):
    msg = msg.lower()
    mood_map = {
        "tired": ["tired", "drained", "exhausted", "sleepy"],
        "sad": ["sad", "depressed", "down", "cry"],
        "angry": ["angry", "pissed", "frustrated", "mad"],
        "happy": ["happy", "excited", "shiok", "yay"],
    }

    for mood, keywords in mood_map.items():
        if any(word in msg for word in keywords):
            return mood
    return None


# -------------------------------------------------------
# B. SG-STYLE REPLY GENERATOR + EMOJIS
# -------------------------------------------------------

def sg_reply(text, your_name, her_name, mood):
    base = [
        f"Aiyo {your_name}, you so cute one leh 🥰",
        f"{her_name} miss you lah 😘",
        f"Wah {your_name}, you so sweet can melt already 💞",
        f"Got eat already or not? Don’t skip meals ah 🍚",
    ]

    emoji_map = {
        "tired": "😴",
        "sad": "🥺",
        "angry": "😡",
        "happy": "😄",
        None: "💖",
    }

    mood_reply = {
        "tired": "You worked hard today hor, go rest early ok? 😴",
        "sad": "Aiyo don’t sad la, {her_name} give you virtual hug 🤗",
        "angry": "Who make you angry? I help you scold them 😤",
        "happy": "Hehe so happy for you lah! ✨",
        None: "How you doing ah? 😊",
    }

    base_reply = random.choice(base)
    mood_text = mood_reply.get(mood, mood_reply[None]).format(her_name=her_name)
    return f"{base_reply}\n{mood_text} {emoji_map[mood]}"


# -------------------------------------------------------
# C. TIME-BASED REMINDERS
# -------------------------------------------------------

async def reminder_loop(app):
    while True:
        now = datetime.datetime.now(pytz.timezone("Asia/Singapore"))
        hour = now.hour
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if 7 <= hour < 9:
            message = "Good morning ☀️! Did you sleep well?"
        elif 12 <= hour < 14:
            message = "Lunch time already 🍱, go eat ok?"
        elif 22 <= hour < 23:
            message = "Time to rest already 😴, goodnight!"
        else:
            message = None

        if message:
            c.execute("SELECT chat_id FROM memory")
            chats = c.fetchall()
            for (chat_id,) in chats:
                await app.bot.send_message(chat_id=chat_id, text=message)

        conn.close()
        await asyncio.sleep(3600)


# -------------------------------------------------------
# COMMAND HANDLERS
# -------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("INSERT OR IGNORE INTO memory (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        "Hello dear 💖! I’m your SG-style girlfriend bot.\n"
        "Tell me your name with /setname <your_name> and I’ll remember it!"
    )


async def setname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Please provide a name, e.g. /setname Edwin")
        return

    your_name = " ".join(context.args)
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("UPDATE memory SET your_name = ? WHERE chat_id = ?", (your_name, chat_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"Okay {your_name}, I’ll remember you 💕")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    chat_id = update.effective_chat.id
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT your_name, her_name FROM memory WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()

    your_name = row[0] if row and row[0] else "dear"
    her_name = row[1] if row and row[1] else "baby"

    mood = detect_mood(msg)
    reply = sg_reply(msg, your_name, her_name, mood)
    await update.message.reply_text(reply)


# -------------------------------------------------------
# MAIN ENTRY
# -------------------------------------------------------

import asyncio

async def main():
    init_db()

    app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setname", setname))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start reminder loop
    asyncio.create_task(reminder_loop(app))

    print("Bot started successfully!")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
