from pyrogram import Client, filters
from pyrogram.types import Message
from flask import Flask
import threading
import os
import random
import asyncio

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# 🔹 Pyrogram Bot
app = Client("quiz_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# 🔹 Flask App for Keep Alive
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "✅ Quiz Bot is Live!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

threading.Thread(target=run_flask).start()

# ✅ Load valid words
with open("words.txt", "r", encoding="utf-8") as f:
    VALID_WORDS = [w.strip().lower() for w in f if len(w.strip()) >= 4]

game_sessions = {}

# 🟢 /quiz to show rules & auto start
@app.on_message(filters.command("quiz") & filters.group)
async def show_rules_and_start(client, message: Message):
    chat_id = message.chat.id

    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        await message.reply("⚠️ Ek game already chal raha hai. /end likhkar band karo.")
        return

    game_sessions[chat_id] = {
        "active": True,
        "players": [],
        "scores": {},
        "turn": 0,
        "letter": "",
        "current_player": None,
        "start_timer": None
    }

    rules = (
        "🎯 *Word Quiz Game Rules:*\n"
        "1️⃣ 'join' likhkar game join karo\n"
        "2️⃣ 2+ players hone chahiye\n"
        "3️⃣ Aapko ek letter milega, us letter se shabd likhna hai\n"
        "4️⃣ Sahi jawab = 1 point 🎯\n"
        "5️⃣ Time limit: 20 sec\n\n"
        "✅ Join hone ke liye 'join' likho!"
    )
    await message.reply(rules)

    # Auto start after 30 sec if 2+ players
    async def auto_start():
        await asyncio.sleep(30)
        session = game_sessions.get(chat_id)
        if session and session["active"] and len(session["players"]) >= 2:
            await start_round(client, chat_id)
        elif session and session["active"]:
            await client.send_message(chat_id, "⏳ 30 sec ho gaye... 2 players nahi hue. Jab tayyar ho toh /go likho.")

    game_sessions[chat_id]["start_timer"] = asyncio.create_task(auto_start())

# ➕ Join Game
@app.on_message(filters.text & filters.group & filters.regex("(?i)^join$"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    session = game_sessions.get(chat_id)

    if not session or not session["active"]:
        return

    if user.id not in session["players"]:
        session["players"].append(user.id)
        session["scores"][user.id] = 0
        await message.reply(f"✅ {user.first_name} game me shamil ho gaye!")
    else:
        await message.reply("⏳ Aap already game me ho.")

# ▶ Manual Start /go
@app.on_message(filters.command("go") & filters.group)
async def start_game_now(client, message: Message):
    chat_id = message.chat.id
    session = game_sessions.get(chat_id)

    if not session or not session["active"]:
        await message.reply("❌ Abhi koi game nahi hai.")
        return

    if len(session["players"]) < 2:
        await message.reply("👥 2 players chahiye game ke liye.")
        return

    if session.get("start_timer"):
        session["start_timer"].cancel()

    await start_round(client, chat_id)

# 🔁 Turn Function
async def start_round(client, chat_id):
    session = game_sessions[chat_id]
    players = session["players"]
    session["turn"] = (session["turn"] + 1) % len(players)
    user_id = players[session["turn"]]
    session["current_player"] = user_id
    letter = random.choice("abcdefghijklmnopqrstuvwxyz")
    session["letter"] = letter

    user = await client.get_users(user_id)
    await client.send_message(
        chat_id,
        f"✏️ *{user.first_name}*, it's your turn!\nSend a word with **{letter.upper()}** (within 20 sec)..."
    )

    await asyncio.sleep(20)
    if session.get("current_player") == user_id:
        await client.send_message(chat_id, f"⏰ Time out! {user.first_name} ne jawab nahi diya.")
        session["current_player"] = None
        await start_round(client, chat_id)

# ✅ Word Checker
@app.on_message(filters.text & filters.group)
async def check_word(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user
    session = game_sessions.get(chat_id)

    if not session or not session["active"]:
        return
    if user.id != session.get("current_player"):
        return

    word = message.text.strip().lower()
    if word in VALID_WORDS and word.startswith(session["letter"]):
        session["scores"][user.id] += 1
        session["current_player"] = None
        await message.reply(f"✅ Sahi jawab! {user.first_name} ko 1 point 🎉")
        await show_scores(client, chat_id)
        await start_round(client, chat_id)
    else:
        await message.reply("❌ Galat ya invalid word!")

# 📊 Score (Auto)
async def show_scores(client, chat_id):
    scores = game_sessions[chat_id]["scores"]
    if not scores:
        return
    msg = "📊 *Scores:*\n\n"
    for uid, score in scores.items():
        user = await client.get_users(uid)
        msg += f"👤 {user.first_name}: {score} point(s)\n"
    await client.send_message(chat_id, msg)

# 🛑 End Game
@app.on_message(filters.command("end") & filters.group)
async def end_game(client, message: Message):
    chat_id = message.chat.id
    session = game_sessions.get(chat_id)
    if not session:
        await message.reply("❌ Koi active game nahi hai.")
        return

    scores = session["scores"]
    winner = max(scores, key=scores.get, default=None)
    if winner:
        user = await client.get_users(winner)
        await message.reply(f"🏆 *Game Over!*\n\n🎉 {user.first_name} wins with {scores[winner]} points!")
    else:
        await message.reply("Game khatam hua, koi winner nahi bana.")

    if session.get("start_timer"):
        session["start_timer"].cancel()

    del game_sessions[chat_id]

# ✅ Run Bot
app.run()
