

import os
import sqlite3
import random
import datetime
import pytz
import re
import logging
from typing import Optional

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------
# Database path & init
# -----------------------------
# Use env var DB_PATH if provided; otherwise use a local file (no /data mkdir attempts).
DB_PATH = os.getenv("DB_PATH", "girlfriend.db")


def init_db() -> None:
    """Initialise DB if needed."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS memory (
            chat_id INTEGER PRIMARY KEY,
            your_name TEXT,
            her_name TEXT,
            mood TEXT
        )
        """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            keyword TEXT,
            message TEXT
        )
        """
    )

    conn.commit()
    conn.close()
    logger.info("Database initialised at %s", DB_PATH)


# -----------------------------
# Helper functions (DB)
# -----------------------------
def get_memory(chat_id: int) -> Optional[tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT your_name, her_name, mood FROM memory WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()
    conn.close()
    return row


def save_memory(chat_id: int, your_name=None, her_name=None, mood=None) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if get_memory(chat_id) is None:
        c.execute(
            "INSERT INTO memory (chat_id, your_name, her_name, mood) VALUES (?, ?, ?, ?)",
            (chat_id, your_name, her_name, mood),
        )
    else:
        if your_name:
            c.execute("UPDATE memory SET your_name = ? WHERE chat_id = ?", (your_name, chat_id))
        if her_name:
            c.execute("UPDATE memory SET her_name = ? WHERE chat_id = ?", (her_name, chat_id))
        if mood:
            c.execute("UPDATE memory SET mood = ? WHERE chat_id = ?", (mood, chat_id))

    conn.commit()
    conn.close()


def add_reminder(chat_id: int, keyword: str, message: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO reminders (chat_id, keyword, message) VALUES (?, ?, ?)", (chat_id, keyword.lower(), message))
    conn.commit()
    conn.close()


def get_keyword_reminders(chat_id: int, msg: str) -> Optional[str]:
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
def detect_mood(msg: str) -> Optional[str]:
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


# -----------------------------
# B. SG-Style Reply Generator + Emojis
# -----------------------------
def sg_reply(text: str, your_name: str, her_name: str, mood: Optional[str]) -> str:
    base = [
        f"Aiyo {your_name}, you so cute one leh 🥺💖",
        f"Don’t worry lah {your_name}, I’m here for you always ❤️",
        f"{your_name}, you make my heart so warm sia ☺️💕",
        "I miss you a bit already leh… 😳💞",
        "You okay anot? I care about you one you know 🥹",
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
        base.append("Wah you send me photo ah… I feel special sia 📸❤️")
    if "sleep" in text_lower:
        base.append("Go sleep a bit lah dear 😴❤️")

    return random.choice(base)


# -----------------------------
# C. Photo handler + Text handler
# -----------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Hi dear~ I'm your girlfriend bot. Talk to me ❤️")


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    row = get_memory(chat_id) or (None, None, None)
    your_name, her_name, mood = row
    replies = [
        f"Wah {your_name or 'dear'}, this photo damn nice leh 😳📸",
        "Aiyo you send me photo ah… I feel so touched sia 🥺💗",
        "Hehe cute photo, I save inside my heart already ☺️❤️",
    ]
    await update.message.reply_text(random.choice(replies))


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    msg = update.message.text.strip()

    # load memory
    mem = get_memory(chat_id)
    your_name, her_name, mood = (mem if mem is not None else (None, None, None))

    # Set her name: "call you X"
    match_her = re.search(r"call you (.+)", msg.lower())
    if match_her:
        new_name = match_her.group(1).strip().title()
        save_memory(chat_id, her_name=new_name)
        await update.message.reply_text(f"Okay dear~ you can call me {new_name} from now on ❤️")
        return

    # Set your name: "call me X"
    match_you = re.search(r"call me (.+)", msg.lower())
    if match_you:
        new_name = match_you.group(1).strip().title()
        save_memory(chat_id, your_name=new_name)
        await update.message.reply_text(f"Hehe okay~ I’ll call you {new_name} from now on 💕")
        return

    # Add reminder - simple syntax: "remind me when <keyword> => <message>"
    # Example: remind me when homework => Don't forget to do your homework!
    match_rem = re.search(r"remind me when (.+?) => (.+)", msg, flags=re.IGNORECASE)
    if match_rem:
        keyword = match_rem.group(1).strip().lower()
        message = match_rem.group(2).strip()
        add_reminder(chat_id, keyword, message)
        await update.message.reply_text(f"Okay I will remind you when '{keyword}' appears ☺️")
        return

    # Keyword reminder check
    keyword_message = get_keyword_reminders(chat_id, msg)
    if keyword_message:
        await update.message.reply_text(keyword_message)
        return

    # Mood detection
    mood_now = detect_mood(msg)
    if mood_now:
        save_memory(chat_id, mood=mood_now)

    # Compose reply
    reply = sg_reply(msg, your_name or "dear", her_name or "baby", mood_now or mood)
    await update.message.reply_text(reply)


# -----------------------------
# Scheduled messages
# -----------------------------
async def scheduled_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback to send occasional scheduled messages."""
    tz = pytz.timezone("Asia/Singapore")
    now = datetime.datetime.now(tz)
    hour = now.hour

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id, your_name FROM memory")
    rows = c.fetchall()
    conn.close()

    for chat_id, your_name in rows:
        try:
            if hour == 8:
                await context.bot.send_message(chat_id, f"Good morning {your_name or 'dear'} ☀️😊 Have a nice day hor~")
            if hour == 23:
                await context.bot.send_message(chat_id, f"Good night {your_name or 'dear'} 🌙💤 Rest well okay? ❤️")
            # random occasional message
            if random.random() < 0.03:
                await context.bot.send_message(chat_id, "I miss you a bit leh… 😳💞")
        except Exception as e:
            logger.exception("Failed sending scheduled message to %s: %s", chat_id, e)


# -----------------------------
# Main entry
# -----------------------------
async def main() -> None:
    # Initialize DB
    init_db()

    BOT_TOKEN = os.getenv("BOT_TOKEN")
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set in environment. Exiting.")
        return

    # Build application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Scheduled job: every hour
    # v20 job queue expects async callbacks; use run_repeating
    app.job_queue.run_repeating(scheduled_messages, interval=3600, first=10)

    logger.info("Starting Girlfriend bot (polling)...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling()  # v20 compatible way to start receiving updates
    await app.idle()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")
