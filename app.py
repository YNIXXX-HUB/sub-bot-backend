import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import Flask

# ======================================================
# 🛑 CONFIGURATION - RE-PASTE YOUR KEYS HERE!
# ======================================================

# 1. From Google Cloud Console
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_ID") # Or paste directly if you prefer
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_SECRET") # Or paste directly if you prefer

# 2. Your 5 Refresh Tokens
BOT_ACCOUNTS = [
    "1//049mP8dfOm1AECgYIARAAGAQSNQF-L9Irs_9dHdanUldtALZI-2mFcsLPfykh3qSfKZ8S5nqjjPUnjMRjt25j4WtMP4vxo4s2",
    "1//04iRGoOClh7V-CgYIARAAGAQSNwF-L9IrRFYJmhvg_Xfl7STK_rC9qUiopeZP62Owfh_XhcY109kn5gVX5c3WVRzzwkHo6REvWzs",
    "1//04rS1k-5MT6G_CgYIARAAGAQSNwF-L9IryPYJk4jux_hzN1P_eTiqAUeNAduTBIIoVGyAEbUodw5RPX57pWEwhIOqO3ERzJ4Ya34",
    "1//04s2A3Ucm7RyaCgYIARAAGAQSNwF-L9IrNXVv9saxtc3WTvrwhZS6E6y92J8Ofcxz8_Eid1QULm_Iu2uzM4yqQRbQ8VUYMPG5iNw",
    "1//04uvBHWSPOKzbCgYIARAAGAQSNwF-L9IrnaD9umWz6wX_8cCdLiPVe3rWSX4XphyuzgpnEgSJY--vxFjUIE5kAkMsSR88tbJ35a0"
]

# ======================================================
# 🔌 DATABASE & BOT SETUP
# ======================================================
MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================================================
# 🌐 THE FAKE WEBSITE (KEEPS RENDER HAPPY)
# ======================================================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    # Runs a tiny web server on port 10000
    app.run(host='0.0.0.0', port=10000)

# ======================================================
# 🤖 THE YOUTUBE LOGIC
# ======================================================
def run_boost(channel_id):
    print(f"🚀 Boosting Channel: {channel_id}")
    count = 0
    for token in BOT_ACCOUNTS:
        try:
            creds = Credentials(
                None,
                refresh_token=token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET
            )
            youtube = build('youtube', 'v3', credentials=creds)
            youtube.subscriptions().insert(
                part="snippet",
                body={"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": channel_id}}}
            ).execute()
            count += 1
            print(f"✅ Account {count} Subbed.")
        except Exception as e:
            print(f"⚠️ Account Failed: {e}")

# ======================================================
# 🎮 DISCORD COMMANDS
# ======================================================
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        await bot.tree.sync()
        print("✅ Commands Synced")
    except Exception as e:
        print(e)

@bot.tree.command(name="register", description="Start your journey")
async def register(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if users_col.find_one({"discord_id": user_id}):
        await interaction.response.send_message("Already registered!", ephemeral=True)
    else:
        users_col.insert_one({"discord_id": user_id, "points": 100})
        await interaction.response.send_message("✅ Registered! You have 100 Points.", ephemeral=True)

@bot.tree.command(name="points", description="Check balance")
async def points(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})
    if user: await interaction.response.send_message(f"💰 Points: {user['points']}")
    else: await interaction.response.send_message("Type `/register` first!", ephemeral=True)

@bot.tree.command(name="promote", description="Get 5 Bot Subs (50 Points)")
async def promote(interaction: discord.Interaction, link: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})

    if not user:
        await interaction.followup.send("Type `/register` first!")
        return
    if user['points'] < 50:
        await interaction.followup.send("❌ Need 50 Points!")
        return
    
    channel_id = ""
    if "/channel/" in link:
        channel_id = link.split("/channel/")[1].split("/")[0].split("?")[0]
    else:
        await interaction.followup.send("❌ Invalid Link! Must be `youtube.com/channel/ID`")
        return

    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
    threading.Thread(target=run_boost, args=(channel_id,)).start()
    
    embed = discord.Embed(title="🚀 Boost Started!", description=f"Sending 5 Subs to:\n{link}", color=0x00ff00)
    await interaction.followup.send(embed=embed)

# ======================================================
# 🚀 START BOTH (WEB + BOT)
# ======================================================
if __name__ == "__main__":
    # Start the fake website in the background
    t = threading.Thread(target=run_web)
    t.start()
    
    # Start the Discord Bot
    bot.run(os.environ.get("DISCORD_TOKEN"))
