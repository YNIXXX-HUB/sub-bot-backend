import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
import time
import random
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import Flask
import httplib2

# ======================================================
# 🛑 CONFIGURATION
# ======================================================
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_SECRET")

BOT_ACCOUNTS = [
    "1//049mP8dfOm1AECgYIARAAGAQSNQF-L9Irs_9dHdanUldtALZI-2mFcsLPfykh3qSfKZ8S5nqjjPUnjMRjt25j4WtMP4vxo4s2",
    "1//04iRGoOClh7V-CgYIARAAGAQSNwF-L9IrRFYJmhvg_Xfl7STK_rC9qUiopeZP62Owfh_XhcY109kn5gVX5c3WVRzzwkHo6REvWzs",
    "1//04rS1k-5MT6G_CgYIARAAGAQSNwF-L9IryPYJk4jux_hzN1P_eTiqAUeNAduTBIIoVGyAEbUodw5RPX57pWEwhIOqO3ERzJ4Ya34",
    "1//04s2A3Ucm7RyaCgYIARAAGAQSNwF-L9IrNXVv9saxtc3WTvrwhZS6E6y92J8Ofcxz8_Eid1QULm_Iu2uzM4yqQRbQ8VUYMPG5iNw",
    "1//04uvBHWSPOKzbCgYIARAAGAQSNwF-L9IrnaD9umWz6wX_8cCdLiPVe3rWSX4XphyuzgpnEgSJY--vxFjUIE5kAkMsSR88tbJ35a0"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.162 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]

MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================================================
# 🤖 YOUTUBE LOGIC
# ======================================================
def run_boost(channel_id):
    print(f"🚀 STARTING STEALTH BOOST FOR: {channel_id}")
    if not GOOGLE_CLIENT_ID: return

    indices = list(range(len(BOT_ACCOUNTS)))
    random.shuffle(indices)

    for i in indices:
        token = BOT_ACCOUNTS[i]
        fake_agent = USER_AGENTS[i % len(USER_AGENTS)]
        try:
            # RANDOM DELAY (30s - 90s)
            wait_time = random.randint(30, 90)
            time.sleep(wait_time)

            creds = Credentials(None, refresh_token=token, token_uri="https://oauth2.googleapis.com/token", client_id=GOOGLE_CLIENT_ID, client_secret=GOOGLE_CLIENT_SECRET)
            
            http = httplib2.Http()
            http = creds.authorize(http)
            http.headers = {'User-Agent': fake_agent}

            youtube = build('youtube', 'v3', http=http)
            youtube.subscriptions().insert(part="snippet", body={"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": channel_id}}}).execute()
            print(f"✅ Account {i+1} Subbed")
            
        except Exception:
            pass # Ignore errors to keep threads alive

# ======================================================
# 🌐 FAKE WEBSITE
# ======================================================
app = Flask(__name__)
@app.route('/')
def home(): return "Online"
def run_web(): app.run(host='0.0.0.0', port=10000, use_reloader=False)

# ======================================================
# 🎮 DISCORD COMMANDS
# ======================================================
@bot.event
async def on_ready():
    print(f'✅ LOGGED IN AS: {bot.user}')
    await bot.tree.sync()

@bot.tree.command(name="promote", description="Get 5 Bot Subs")
async def promote(interaction: discord.Interaction, link: str):
    # REPLY INSTANTLY TO PREVENT 404 ERRORS
    await interaction.response.defer()
    
    try:
        if "/channel/" in link:
            channel_id = link.split("/channel/")[1].split("/")[0].split("?")[0]
        else:
            await interaction.followup.send("❌ Link MUST contain `/channel/`")
            return

        user_id = str(interaction.user.id)
        user = users_col.find_one({"discord_id": user_id})

        if not user or user['points'] < 50:
            await interaction.followup.send("❌ Need 50 Points! Use `/register`")
            return

        users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
        threading.Thread(target=run_boost, args=(channel_id,)).start()
        
        embed = discord.Embed(title="🚀 Boost Queued!", description=f"Sending 5 Subscribers to:\n{link}", color=0x00ff00)
        embed.set_footer(text="⚠️ STEALTH MODE: Subs will arrive slowly (5-8 mins).")
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}")

@bot.tree.command(name="register", description="Create account")
async def register(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if users_col.find_one({"discord_id": user_id}):
        await interaction.response.send_message("Already registered!", ephemeral=True)
    else:
        users_col.insert_one({"discord_id": user_id, "points": 100})
        await interaction.response.send_message("✅ Registered! 100 Points added.", ephemeral=True)

@bot.command()
async def cheat(ctx):
    if ctx.author.guild_permissions.administrator:
        users_col.update_one({"discord_id": str(ctx.author.id)}, {"$set": {"points": 1000000}}, upsert=True)
        await ctx.send("✅ Cheat Activated.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
