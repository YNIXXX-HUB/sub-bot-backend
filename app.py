import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
import time
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from flask import Flask

# ======================================================
# 🛑 CONFIGURATION
# ======================================================
# PULLS FROM RENDER ENVIRONMENT (No need to paste here)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_SECRET")

# Your 5 Tokens
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
# 🤖 YOUTUBE LOGIC (WITH 5 SECOND DELAY)
# ======================================================
def run_boost(channel_id):
    print(f"🚀 STARTING BOOST FOR: {channel_id}")
    success = 0
    
    # Check if Render Variables are working
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        print("❌ CRITICAL ERROR: Google Keys missing from Render Environment!")
        return

    for i, token in enumerate(BOT_ACCOUNTS):
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
            
            print(f"✅ Account {i+1} Subbed.")
            success += 1
            
            # 5 SECOND DELAY (Fixes the +1 count issue)
            time.sleep(5) 
            
        except Exception as e:
            if "subscriptionDuplicate" in str(e):
                print(f"⚠️ Account {i+1} already subbed.")
                success += 1 
            else:
                print(f"❌ Account {i+1} Failed: {e}")

# ======================================================
# 🌐 FAKE WEBSITE (KEEPS BOT ONLINE)
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
    print(f'✅ LOGGED IN AS: {bot.user}')
    await bot.tree.sync()

@bot.tree.command(name="help", description="Show commands")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Commands", color=0x00ff00)
    embed.add_field(name="`/register`", value="Get 100 points", inline=False)
    embed.add_field(name="`/promote [link]`", value="Get 5 Subs (50 Points)", inline=False)
    embed.add_field(name="`!cheat`", value="Admin: Get 1M Points", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="register", description="Create account")
async def register(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if users_col.find_one({"discord_id": user_id}):
        await interaction.response.send_message("Already registered!", ephemeral=True)
    else:
        users_col.insert_one({"discord_id": user_id, "points": 100})
        await interaction.response.send_message("✅ Account Created! You have 100 Points.", ephemeral=True)

@bot.tree.command(name="points", description="Check balance")
async def points(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})
    if user: await interaction.response.send_message(f"💰 You have **{user['points']}** Points.")
    else: await interaction.response.send_message("Type `/register` first!", ephemeral=True)

@bot.tree.command(name="promote", description="Get 5 Subs (50 Points)")
async def promote(interaction: discord.Interaction, link: str):
    await interaction.response.defer()
    
    # Check Link
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

    # Check User
    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})
    if not user:
        await interaction.followup.send("Type `/register` first!")
        return
    if user['points'] < 50:
        await interaction.followup.send("❌ Need 50 Points!")
        return

    # Execute
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
    threading.Thread(target=run_boost, args=(channel_id,)).start()
    
    embed = discord.Embed(title="🚀 Boost Started!", description=f"Sending 5 Subscribers to:\n{link}", color=0x00ff00)
    embed.set_footer(text="Wait a few minutes for updates.")
    await interaction.followup.send(embed=embed)

# ADMIN CHEAT
@bot.command()
async def cheat(ctx):
    if ctx.author.guild_permissions.administrator:
        users_col.update_one({"discord_id": str(ctx.author.id)}, {"$set": {"points": 1000000}}, upsert=True)
        await ctx.send("✅ **CHEAT ACTIVATED:** You are now a Millionaire.")

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
