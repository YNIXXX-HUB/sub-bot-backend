import discord
from discord.ext import commands
from discord import app_commands
import pymongo
import os
import threading
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ======================================================
# 🛑 CONFIGURATION - FILL THIS IN!
# ======================================================

# We get these from Render now (Secure!)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_SECRET")
# I have formatted your tokens for you:
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
# 🤖 THE YOUTUBE BOOSTER LOGIC
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
                body={
                    "snippet": {
                        "resourceId": {
                            "kind": "youtube#channel",
                            "channelId": channel_id
                        }
                    }
                }
            ).execute()
            count += 1
            print(f"✅ Account {count} Subbed.")
        except Exception as e:
            print(f"⚠️ Account {count+1} Failed: {e}")

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

@bot.tree.command(name="register", description="Create an account")
async def register(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    if users_col.find_one({"discord_id": user_id}):
        await interaction.response.send_message("You are already registered!", ephemeral=True)
    else:
        # 100 Points = 2 Free Promotions (10 Subs)
        users_col.insert_one({"discord_id": user_id, "points": 100})
        await interaction.response.send_message("✅ Account Created! You have **100 Points**.\nUse `/promote` to get your 5 subs!", ephemeral=True)

@bot.tree.command(name="points", description="Check balance")
async def points(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})
    if not user:
        await interaction.response.send_message("Type `/register` first!", ephemeral=True)
    else:
        await interaction.response.send_message(f"💰 You have **{user['points']}** Points.")

@bot.tree.command(name="promote", description="Get 5 Bot Subs (Costs 50 Points)")
@app_commands.describe(link="YouTube Link (MUST be: youtube.com/channel/ID)")
async def promote(interaction: discord.Interaction, link: str):
    await interaction.response.defer()

    user_id = str(interaction.user.id)
    user = users_col.find_one({"discord_id": user_id})

    if not user:
        await interaction.followup.send("Type `/register` first!")
        return
    if user['points'] < 50:
        await interaction.followup.send("❌ You need **50 Points**!")
        return
    
    # Extract ID
    channel_id = ""
    try:
        # Supports https://www.youtube.com/channel/UC123456
        if "/channel/" in link:
            channel_id = link.split("/channel/")[1].split("/")[0].split("?")[0]
        else:
            await interaction.followup.send("❌ Invalid Link!\n**Your link MUST look like this:**\n`https://www.youtube.com/channel/UC...`\n\n(Go to your Channel -> About -> Share -> Copy Channel ID)")
            return
    except:
        await interaction.followup.send("❌ Could not read link.")
        return

    # Deduct Points
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})

    # Run Bot
    t = threading.Thread(target=run_boost, args=(channel_id,))
    t.start()

    embed = discord.Embed(title="🚀 Boost Started!", description=f"Sending 5 Subscribers to:\n{link}", color=0x00ff00)
    embed.set_footer(text="Please wait 2-5 minutes for YouTube to update the count.")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="admin_add", description="Give points")
async def admin_add(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Admin only.", ephemeral=True)
        return
    user_id = str(member.id)
    if not users_col.find_one({"discord_id": user_id}):
         users_col.insert_one({"discord_id": user_id, "points": 0})
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": amount}})
    await interaction.response.send_message(f"✅ Gave {amount} points to {member.mention}.")

bot.run(os.environ.get("DISCORD_TOKEN"))
