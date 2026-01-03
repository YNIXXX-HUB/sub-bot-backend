import discord
from discord.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
import pymongo
import threading
import os
import time

# --- CONFIGURATION ---
MONGO_URL = os.environ.get("MONGO_URL")

# --- DATABASE SETUP ---
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users
links_col = db.links
settings_col = db.settings 

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)
bot.remove_command('help') # We will make our own better help command

# --- FLASK API ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Bot is Active"

@app.route('/verify_action', methods=['POST'])
def verify():
    data = request.json
    discord_id = data.get('discord_id')
    action = data.get('type') 

    if not discord_id: return jsonify({"error": "No ID"})

    user = users_col.find_one({"discord_id": discord_id})
    if not user: return jsonify({"error": "User not found"})

    if action == "SUB":
        # Give 10 Points + 50 XP
        users_col.update_one({"discord_id": discord_id}, {"$inc": {"points": 10, "xp": 50}})
        return jsonify({"msg": "Points Added"})
    
    if action == "UNSUB":
        users_col.update_one({"discord_id": discord_id}, {"$inc": {"points": -50}})
        return jsonify({"msg": "Punishment logged"})

    return jsonify({"msg": "Received"})

# --- HELPER: CALCULATE LEVEL ---
def get_level(xp):
    # Level 1 = 0-99 XP
    # Level 2 = 100+ XP
    return int(xp / 100) + 1

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="/help | Growing Channels"))

@bot.event
async def on_message(message):
    if message.author.bot: return

    # CHECK IF THIS IS THE CHAT CHANNEL
    setting = settings_col.find_one({"server_id": str(message.guild.id)})
    
    if setting and "chat_channel" in setting and message.channel.id == setting["chat_channel"]:
        user_id = str(message.author.id)
        user = users_col.find_one({"discord_id": user_id})
        current_time = time.time()
        
        if not user:
            users_col.insert_one({"discord_id": user_id, "points": 0, "xp": 0, "last_msg": current_time})
        else:
            # 60 Second Cooldown for XP
            last_msg = user.get('last_msg', 0)
            if current_time - last_msg > 60:
                old_level = get_level(user.get('xp', 0))
                
                # Give 1 Point and 15 XP (Faster leveling for testing)
                users_col.update_one(
                    {"discord_id": user_id}, 
                    {"$inc": {"xp": 15, "points": 1}, "$set": {"last_msg": current_time}}
                )
                
                # CHECK LEVEL UP
                updated_user = users_col.find_one({"discord_id": user_id})
                new_level = get_level(updated_user.get('xp', 0))
                
                if new_level > old_level:
                    await message.channel.send(f"🎉 **LEVEL UP!** {message.author.mention} reached **Level {new_level}**! 🚀")

    await bot.process_commands(message)

# --- USER COMMANDS ---

@bot.command()
async def help(ctx):
    """Shows the help menu"""
    embed = discord.Embed(title="🤖 Community Bot Commands", color=0x00ff00)
    embed.add_field(name="📈 Grow", value="`/promote_channel [url]` - Get Subs (50pts)\n`/promote_video [url]` - Get Views (30pts)", inline=False)
    embed.add_field(name="💰 Earn", value="`/earn` - Get a link to sub to\n`/stats` - Check points & level", inline=False)
    embed.add_field(name="⚙️ Admin", value="`/set_chat` - Set XP channel\n`/admin_points` - Give points\n`/admin_xp` - Give levels", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def stats(ctx):
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    if not user:
        await ctx.send("You have no profile yet. Chat in the general chat!")
    else:
        lvl = get_level(user.get('xp', 0))
        pts = user.get('points', 0)
        xp = user.get('xp', 0)
        await ctx.send(f"📊 **{ctx.author.name}**\n💳 Points: `{pts}`\n⭐ Level: `{lvl}` ({xp} XP)")

@bot.command()
async def promote_channel(ctx, url: str):
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    
    if not user: return await ctx.send("Chat first to create a profile!")

    # ADMIN BYPASS: If you are admin, skip checks
    is_admin = ctx.author.guild_permissions.administrator
    
    if not is_admin:
        if get_level(user.get('xp', 0)) < 2:
            return await ctx.send("🔒 **Locked!** Reach Level 2 to promote.")
        if user.get('points', 0) < 50:
            return await ctx.send("❌ Need 50 Points.")
        # Deduct points if not admin
        users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})

    links_col.insert_one({"url": url, "owner": user_id, "type": "channel"})
    
    embed = discord.Embed(title="🔥 SUBSCRIBE TO THIS!", description=f"{url}", color=0xFF0000)
    embed.set_footer(text="Use /earn to get points for subbing!")
    await ctx.send(embed=embed)

@bot.command()
async def promote_video(ctx, url: str):
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})

    if not user: return await ctx.send("Chat first to create a profile!")

    is_admin = ctx.author.guild_permissions.administrator

    if not is_admin:
        if user.get('points', 0) < 30:
            return await ctx.send("❌ Need 30 Points.")
        users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -30}})

    links_col.insert_one({"url": url, "owner": user_id, "type": "video"})
    
    embed = discord.Embed(title="🎥 WATCH THIS!", description=f"{url}", color=0x0000FF)
    await ctx.send(embed=embed)

@bot.command()
async def earn(ctx):
    pipeline = [{"$sample": {"size": 1}}]
    links = list(links_col.aggregate(pipeline))
    if len(links) == 0: return await ctx.send("No links yet!")
    await ctx.send(f"Go Sub/Watch: {links[0]['url']}\n(Script must be installed)")

# --- ADMIN CHEAT CODES ---

@bot.command()
@commands.has_permissions(administrator=True)
async def set_chat(ctx):
    settings_col.update_one({"server_id": str(ctx.guild.id)}, {"$set": {"chat_channel": ctx.channel.id}}, upsert=True)
    await ctx.send(f"✅ XP is now enabled in {ctx.channel.mention}")

@bot.command()
@commands.has_permissions(administrator=True)
async def admin_points(ctx, member: discord.Member, amount: int):
    """Gives points to a user"""
    user_id = str(member.id)
    # Ensure user exists
    if not users_col.find_one({"discord_id": user_id}):
         users_col.insert_one({"discord_id": user_id, "points": 0, "xp": 0})
         
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": amount}})
    await ctx.send(f"💰 Gave **{amount}** points to {member.name}.")

@bot.command()
@commands.has_permissions(administrator=True)
async def admin_xp(ctx, member: discord.Member, amount: int):
    """Gives XP (Levels) to a user"""
    user_id = str(member.id)
    if not users_col.find_one({"discord_id": user_id}):
         users_col.insert_one({"discord_id": user_id, "points": 0, "xp": 0})
         
    users_col.update_one({"discord_id": user_id}, {"$inc": {"xp": amount}})
    await ctx.send(f"⭐ Gave **{amount}** XP to {member.name}. Check /stats!")

# --- RUNNER ---
def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    time.sleep(3)
    try:
        bot.run(os.environ.get("DISCORD_TOKEN"))
    except discord.errors.HTTPException as e:
        if e.status == 429:
            print("RATE LIMITED. Clear Cache.")
            while True: time.sleep(3600)
        else: raise e
