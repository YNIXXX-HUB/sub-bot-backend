import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import Flask
import traceback

# ======================================================
# 🛑 CONFIGURATION - PASTE CLIENT ID & SECRET HERE
# ======================================================
# You must paste these from your client_secret.json file!
GOOGLE_CLIENT_ID = "PASTE_YOUR_LONG_CLIENT_ID_HERE"
GOOGLE_CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET_HERE"

# I have inserted your 5 tokens here:
BOT_ACCOUNTS = [
    "1//049mP8dfOm1AECgYIARAAGAQSNQF-L9Irs_9dHdanUldtALZI-2mFcsLPfykh3qSfKZ8S5nqjjPUnjMRjt25j4WtMP4vxo4s2",
    "1//04iRGoOClh7V-CgYIARAAGAQSNwF-L9IrRFYJmhvg_Xfl7STK_rC9qUiopeZP62Owfh_XhcY109kn5gVX5c3WVRzzwkHo6REvWzs",
    "1//04rS1k-5MT6G_CgYIARAAGAQSNwF-L9IryPYJk4jux_hzN1P_eTiqAUeNAduTBIIoVGyAEbUodw5RPX57pWEwhIOqO3ERzJ4Ya34",
    "1//04s2A3Ucm7RyaCgYIARAAGAQSNwF-L9IrNXVv9saxtc3WTvrwhZS6E6y92J8Ofcxz8_Eid1QULm_Iu2uzM4yqQRbQ8VUYMPG5iNw",
    "1//04uvBHWSPOKzbCgYIARAAGAQSNwF-L9IrnaD9umWz6wX_8cCdLiPVe3rWSX4XphyuzgpnEgSJY--vxFjUIE5kAkMsSR88tbJ35a0"
]

# ======================================================
# 🔌 DATABASE & BOT
# ======================================================
MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================================================
# 🤖 THE YOUTUBE LOGIC (DEBUG MODE)
# ======================================================
def run_boost(channel_id):
    print(f"\n[DEBUG] 🚀 STARTING BOOST FOR: {channel_id}")
    
    # Safety Check
    if "PASTE" in GOOGLE_CLIENT_ID:
        print("[CRITICAL ERROR] You forgot to paste the Client ID in the code!")
        return

    success = 0
    fail = 0

    for i, token in enumerate(BOT_ACCOUNTS):
        try:
            print(f"[DEBUG] 🔄 Attempting Account {i+1}...")
            
            creds = Credentials(
                None,
                refresh_token=token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET
            )
            
            youtube = build('youtube', 'v3', credentials=creds)
            
            # The API Call
            youtube.subscriptions().insert(
                part="snippet",
                body={
                    "snippet": {
                        "resourceId": {
                            "kind": "youtube#channel",
                            "channelId": channel_id
                        }
                    }
                }
            ).execute()
            
            print(f"[SUCCESS] ✅ Account {i+1} Subscribed!")
            success += 1
            
        except Exception as e:
            error_msg = str(e)
            if "subscriptionDuplicate" in error_msg:
                print(f"[INFO] ⚠️ Account {i+1} is ALREADY subscribed.")
                # We count this as a success because the user got the sub previously
                success += 1 
            elif "quotaExceeded" in error_msg:
                print(f"[CRITICAL] ❌ Daily Quota Reached.")
            elif "channelNotFound" in error_msg:
                print(f"[CRITICAL] ❌ Channel ID is wrong.")
            elif "invalid_grant" in error_msg:
                 print(f"[CRITICAL] ❌ Token Expired. Needs new keys.")
            else:
                print(f"[ERROR] ❌ Account {i+1} Failed. Reason: {error_msg}")
            fail += 1

    print(f"[DEBUG] 🏁 FINISHED. Total Subs/Checks: {success}\n")

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
    await interaction.response.defer()
    
    # 1. EXTRACT ID
    channel_id = ""
    try:
        if "/channel/" in link:
            channel_id = link.split("/channel/")[1].split("/")[0].split("?")[0]
        else:
            await interaction.followup.send("❌ Link MUST contain `/channel/`")
            return
    except:
        await interaction.followup.send("❌ Link format error.")
        return

    # 2. RUN DEBUGGER
    print(f"[DEBUG] User {interaction.user} requested boost for {link}")
    t = threading.Thread(target=run_boost, args=(channel_id,))
    t.start()
    
    await interaction.followup.send(f"🚀 **Attempting Boost!**\nTarget ID: `{channel_id}`\n\n**CHECK RENDER LOGS TO SEE RESULTS**")

# INSTANT CHEAT
@bot.command()
async def cheat(ctx):
    if ctx.author.guild_permissions.administrator:
        users_col.update_one({"discord_id": str(ctx.author.id)}, {"$set": {"points": 1000000}}, upsert=True)
        await ctx.send("✅ Points added.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
