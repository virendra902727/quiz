from pyrogram import Client, filters
from pyrogram.types import Message
import os
import random
import asyncio

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client("quiz_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ✅ Load dictionary (minimum 4 letter words)
with open("words.txt", "r", encoding="utf-8") as f:
    VALID_WORDS = [w.strip().lower() for w in f if len(w.strip()) >= 4]

game_sessions = {}  # {chat_id: session_data}


# 🎮 /quiz command to show rules & start game
@app.on_message(filters.command("quiz") & filters.group)
async def show_rules_and_start(client, message: Message):
    chat_id = message.chat.id

    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        await message.reply("⚠️ Ek game already chal raha hai. /end likhkar use band karo.")
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
        "1️⃣ Sabhi players 'join' likhkar game me shamil ho sakte hain\n"
        "2️⃣ Kam se kam 2 players hone chahiye game ke liye\n"
        "3️⃣ Har player ko ek letter diya jaayega\n"
        "4️⃣ Aapko us letter se start hone wala ek valid word bhejna hoga\n"
        "5️⃣ Sahi jawab par 1 point milega, galat par kuch nahi\n"
        "6️⃣ 20 sec me jawab nahi diya to chance chala jayega\n\n"
        "✏️ *Game start hone ke liye minimum 2 players chahiye!*"
    )

    await message.reply(rules + "\n\n✅ Join hone ke liye 'join' likho!", quote=True)

    # Timer to auto-start if 2+ joined
    async def auto_start():
        await asyncio.sleep(30)
        session = game_sessions.get(chat_id)
        if session and session["active"] and len(session["players"]) >= 2:
            await start_round(client, chat_id)
        elif session and session["active"]:
            await client.send_message(chat_id, "⏳ 30 sec ho gaye... abhi tak 2 players nahi hue. Jab ready ho toh manually /go likho.")

    game_sessions[chat_id]["start_timer"] = asyncio.create_task(auto_start())


# ➕ Join command
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
        await message.reply(f"✅ {user.first_name} ne game join kar liya!")
    else:
        await message.reply("⏳ Aap already game me ho.")


# ▶ /go (manual start)
@app.on_message(filters.command("go") & filters.group)
async def start_game_now(client, message: Message):
    chat_id = message.chat.id
    session = game_sessions.get(chat_id)

    if not session or not session["active"]:
        await message.reply("❌ Abhi koi game shuru nahi hua hai. /quiz likho start karne ke liye.")
        return

    if len(session["players"]) < 2:
        await message.reply("👥 Kam se kam 2 players chahiye game ke liye.")
        return

    if session.get("start_timer"):
        session["start_timer"].cancel()

    await start_round(client, chat_id)


# 🔁 Start Round Logic
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
        f"🎯 *{user.first_name}*, it's your turn!\nType a valid word starting with **{letter.upper()}** (20 sec)..."
    )

    # Wait for 20 sec
    await asyncio.sleep(20)

    if session.get("current_player") == user_id:
        await client.send_message(chat_id, f"⏰ Time out! {user.first_name} ne jawab nahi diya.")
        session["current_player"] = None
        await start_round(client, chat_id)


# ✅ Word Check
@app.on_message(filters.text & filters.group)
async def check_word(client, message: Message):
    chat_id = message.chat.id
    session = game_sessions.get(chat_id)
    user = message.from_user

    if not session or not session["active"] or user.id != session.get("current_player"):
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


# 📊 Show Scores (Auto)
async def show_scores(client, chat_id):
    session = game_sessions[chat_id]
    scores = session["scores"]
    if not scores:
        return

    msg = "📊 *Scores:*\n"
    for uid, score in scores.items():
        user = await client.get_users(uid)
        msg += f"👤 {user.first_name}: {score} point(s)\n"

    await client.send_message(chat_id, msg)


# 🛑 /end to stop
@app.on_message(filters.command("end") & filters.group)
async def end_game(client, message: Message):
    chat_id = message.chat.id
    session = game_sessions.get(chat_id)

    if not session:
        await message.reply("❌ Abhi koi active game nahi hai.")
        return

    scores = session["scores"]
    winner_id = max(scores, key=scores.get, default=None)

    if winner_id:
        user = await client.get_users(winner_id)
        await message.reply(f"🏆 *Game Over!*\n\n🎉 Congratulations {user.first_name}!\nTotal Points: {scores[winner_id]}")
    else:
        await message.reply("Game khatam hua. Koi winner nahi bana.")

    if session.get("start_timer"):
        session["start_timer"].cancel()

    del game_sessions[chat_id]


# 📘 /rules command (optional)
@app.on_message(filters.command("rules") & filters.group)
async def show_rules(client, message: Message):
    rules = (
        "🎯 *Word Quiz Game Rules:*\n"
        "1️⃣ Sabhi players 'join' likhkar game me shamil ho sakte hain\n"
        "2️⃣ Kam se kam 2 players hone chahiye game ke liye\n"
        "3️⃣ Har player ko ek letter diya jaayega\n"
        "4️⃣ Aapko us letter se start hone wala ek valid word bhejna hoga\n"
        "5️⃣ Sahi jawab par 1 point milega, galat par kuch nahi\n"
        "6️⃣ 20 sec me jawab nahi diya to chance chala jayega\n\n"
        "⚠️ Game end karne ke liye /end likhein."
    )
    await message.reply(rules)


# ✅ Run the bot
app.run()
