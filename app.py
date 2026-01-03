import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
import time
import random
import sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import Flask

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

MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ======================================================
# 🤖 YOUTUBE LOGIC (Clean & Robust)
# ======================================================
def run_boost(channel_id):
    print(f"\n[DEBUG] 🚀 STARTING JOB FOR: {channel_id}", flush=True)
    
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("[CRITICAL ERROR] ❌ GOOGLE_ID or GOOGLE_SECRET is missing!", flush=True)
        return

    # Shuffle to keep it random
    indices = list(range(len(BOT_ACCOUNTS)))
    random.shuffle(indices)

    for i in indices:
        token = BOT_ACCOUNTS[i]
        
        print(f"[DEBUG] 🔄 Preparing Account {i+1}...", flush=True)
        
        try:
            # 1. RANDOM SLEEP (The protection)
            # This separates the subs so they don't look like a bot swarm
            wait_time = random.randint(30, 60)
            print(f"⏳ Waiting {wait_time}s to avoid detection...", flush=True)
            time.sleep(wait_time)

            # 2. LOGIN
            creds = Credentials(
                None,
                refresh_token=token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=GOOGLE_CLIENT_ID,
                client_secret=GOOGLE_CLIENT_SECRET
            )
            
            # 3. BUILD SERVICE (Standard Method - No spoofing hacks that break)
            youtube = build('youtube', 'v3', credentials=creds)

            # 4. SUBSCRIBE
            youtube.subscriptions().insert(
                part="snippet",
                body={"snippet": {"resourceId": {"kind": "youtube#channel", "channelId": channel_id}}}
            ).execute()
            
            print(f"[SUCCESS] ✅ Account {i+1} Subscribed!", flush=True)
            
        except Exception as e:
            error_str = str(e)
            if "subscriptionDuplicate" in error_str:
                print(f"[INFO] ⚠️ Account {i+1} was ALREADY subscribed.", flush=True)
            elif "invalid_grant" in error_str:
                print(f"[FATAL] ❌ TOKEN EXPIRED. Generate new keys on PC.", flush=True)
            else:
                print(f"[ERROR] ❌ Account {i+1} Failed: {error_str}", flush=True)

    print("[DEBUG] 🏁 JOB FINISHED.", flush=True)

# ======================================================
# 🌐 FAKE WEBSITE
# ======================================================
app = Flask(__name__)
@app.route('/')
def home(): return "Bot Online"
def run_web(): app.run(host='0.0.0.0', port=10000, use_reloader=False)

# ======================================================
# 🎮 DISCORD COMMANDS
# ======================================================
@bot.event
async def on_ready():
    print(f'✅ LOGGED IN AS: {bot.user}', flush=True)
    await bot.tree.sync()

@bot.tree.command(name="promote", description="Get 5 Bot Subs")
async def promote(interaction: discord.Interaction, link: str):
    await interaction.response.defer()
    
    print(f"[CMD] Promote requested: {link}", flush=True)
    
    channel_id = ""
    try:
        if "/channel/" in link:
            channel_id = link.split("/channel/")[1].split("/")[0].split("?")[0]
        else:
            await interaction.followup.send("❌ Link MUST look like: `youtube.com/channel/UC...`")
            return
    except:
        await interaction.followup.send("❌ Invalid Link")
        return

    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})

    if not user or user['points'] < 50:
        await interaction.followup.send("❌ Need 50 Points! Use `!cheat` if admin.")
        return

    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
    
    threading.Thread(target=run_boost, args=(channel_id,)).start()
    
    embed = discord.Embed(title="🚀 Boost Queued!", description=f"Sending 5 Subscribers to:\n{link}", color=0x00ff00)
    embed.set_footer(text="CHECK RENDER LOGS FOR LIVE STATUS")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="register", description="Create account")
async def register(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if users_col.find_one({"discord_id": user_id}):
        await interaction.response.send_message("Already registered!", ephemeral=True)
    else:
        users_col.insert_one({"discord_id": user_id, "points": 100})
        await interaction.response.send_message("✅ Registered!", ephemeral=True)

@bot.command()
async def cheat(ctx):
    if ctx.author.guild_permissions.administrator:
        users_col.update_one({"discord_id": str(ctx.author.id)}, {"$set": {"points": 1000000}}, upsert=True)
        await ctx.send("✅ Cheat Activated.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
