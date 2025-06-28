from pyrogram import Client, filters
from pyrogram.types import Message
import os
import random
import asyncio

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")

app = Client("quiz_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ✅ Load word dictionary
with open("words.txt", "r", encoding="utf-8") as f:
    VALID_WORDS = [w.strip().lower() for w in f.readlines() if len(w.strip()) >= 4]

game_sessions = {}  # {chat_id: session_data}

# 🎮 Start quiz
@app.on_message(filters.command("quiz") & filters.group)
async def start_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id in game_sessions and game_sessions[chat_id]["active"]:
        await message.reply("⚠️ Ek game already chal raha hai. /end likh kar end karo.")
        return

    game_sessions[chat_id] = {
        "active": True,
        "players": [],
        "scores": {},
        "turn": 0,
        "letter": "",
        "current_player": None,
        "waiting_to_start": True
    }

    await message.reply(
        "🎉 *Word Quiz Game Start!* 🎲\n\nSabhi log *join* likhkar game me shamil ho jaayein! Minimum 2 players required.\n30 sec me game auto-start ho jaayega agar 2 ya usse zyada players ho gaye.\n📜 Rules padhne ke liye /rules likhein.",
        quote=True
    )

    await asyncio.sleep(30)
    session = game_sessions.get(chat_id)
    if session and session["waiting_to_start"] and len(session["players"]) >= 2:
        session["waiting_to_start"] = False
        await begin_round(client, message)
    elif session:
        await client.send_message(chat_id, "⏳ Players kam hain. Game abhi start nahi ho sakta. /quiz se dobara try karein.")
        del game_sessions[chat_id]

# 📜 Rules
@app.on_message(filters.command("rules") & filters.group)
async def show_rules(client, message):
    rules = (
        "📜 *Word Quiz Game Rules* 🎲\n\n"
        "1️⃣ Bot ek random letter choose karega aapke turn ke liye.\n"
        "2️⃣ Aapko us letter se start hone wala *valid English word* likhna hoga (kam se kam 4 letters ka).\n"
        "3️⃣ Aapke paas 20 seconds honge jawab dene ke liye.\n"
        "4️⃣ Sahi jawab par aapko 1 point milega.\n"
        "5️⃣ Game me sabki baari aati hai round-robin mein.\n"
        "6️⃣ Winner ko sabke saamne declare kiya jaata hai! 🏆\n\n"
        "📝 Game start karne ke liye: /quiz"
    )
    await message.reply(rules)

# ➕ Join game
@app.on_message(filters.text & filters.group & filters.regex("(?i)^join$"))
async def join_game(client, message: Message):
    chat_id = message.chat.id
    user = message.from_user

    if chat_id not in game_sessions or not game_sessions[chat_id]["active"]:
        return

    session = game_sessions[chat_id]

    if user.id not in session["players"]:
        session["players"].append(user.id)
        session["scores"][user.id] = 0
        await message.reply(f"✅ {user.first_name} game me shamil ho gaye!")
    else:
        await message.reply("⏳ Aap already game me ho.")

# ▶ Start Round (manually)
@app.on_message(filters.command("go") & filters.group)
async def begin_round(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_sessions or not game_sessions[chat_id]["active"]:
        await message.reply("❌ Koi game start nahi hai.")
        return

    session = game_sessions[chat_id]
    if len(session["players"]) < 2:
        await message.reply("👥 Kam se kam 2 players chahiye game ke liye.")
        return

    session["waiting_to_start"] = False
    await next_turn(client, chat_id)

# 🔁 Next Player Turn
async def next_turn(client, chat_id):
    session = game_sessions[chat_id]
    players = session["players"]
    session["turn"] = (session["turn"] + 1) % len(players)
    user_id = players[session["turn"]]
    session["current_player"] = user_id

    letter = random.choice("abcdefghijklmnopqrstuvwxyz")
    session["letter"] = letter

    try:
        user = await client.get_users(user_id)
        await client.send_message(
            chat_id,
            f"✏️ *{user.first_name}*, it's your turn!\nSend a valid word starting with **{letter.upper()}** (within 20 sec)..."
        )

        await asyncio.sleep(20)

        if session["current_player"] == user_id:
            await client.send_message(chat_id, f"⏰ Time out! {user.first_name} ne jawab nahi diya.")
            await next_turn(client, chat_id)

    except Exception as e:
        print(e)

# 📝 Word Check
@app.on_message(filters.text & filters.group)
async def check_word(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_sessions or not game_sessions[chat_id]["active"]:
        return

    session = game_sessions[chat_id]
    user = message.from_user

    if user.id != session.get("current_player"):
        return

    word = message.text.strip().lower()
    if word in VALID_WORDS and word.startswith(session["letter"]):
        session["scores"][user.id] += 1
        await message.reply(f"✅ Sahi jawab! {user.first_name} ko 1 point 🎉")
        session["current_player"] = None
        await next_turn(client, chat_id)
    else:
        await message.reply("❌ Galat ya invalid word!")

# 📊 Scoreboard
@app.on_message(filters.command("score") & filters.group)
async def show_scores(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_sessions:
        return

    scores = game_sessions[chat_id]["scores"]
    if not scores:
        await message.reply("📉 No scores yet.")
        return

    msg = "📊 *Current Scores:*\n\n"
    for uid, score in scores.items():
        user = await client.get_users(uid)
        msg += f"👤 {user.first_name}: {score} points\n"

    await message.reply(msg)

# 🛑 End Game
@app.on_message(filters.command("end") & filters.group)
async def end_game(client, message: Message):
    chat_id = message.chat.id
    if chat_id not in game_sessions:
        await message.reply("❌ Koi active game nahi hai.")
        return

    scores = game_sessions[chat_id]["scores"]
    winner = max(scores, key=scores.get, default=None)
    if winner:
        user = await client.get_users(winner)
        await message.reply(f"🏆 *Game Over!*\n\nCongratulations {user.first_name} 🎉 with {scores[winner]} points!")
    else:
        await message.reply("Game khatam hua. Koi winner nahi bana.")

    del game_sessions[chat_id]

# ✅ Run Bot
app.run()
