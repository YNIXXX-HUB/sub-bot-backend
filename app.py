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
settings_col = db.settings # New collection for server settings

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- FLASK API ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Community Bot is Alive"

@app.route('/verify_action', methods=['POST'])
def verify():
    data = request.json
    discord_id = data.get('discord_id')
    action = data.get('type') # 'SUB'

    if not discord_id: return jsonify({"error": "No ID"})

    user = users_col.find_one({"discord_id": discord_id})
    if not user: return jsonify({"error": "User not found"})

    if action == "SUB":
        # Give 10 Points + 50 XP for subbing
        users_col.update_one({"discord_id": discord_id}, {"$inc": {"points": 10, "xp": 50}})
        return jsonify({"msg": "Points Added"})
    
    if action == "UNSUB":
        # Deduct 50 Points for cheating
        users_col.update_one({"discord_id": discord_id}, {"$inc": {"points": -50}})
        return jsonify({"msg": "Punishment logged"})

    return jsonify({"msg": "Received"})

# --- HELPER FUNCTIONS ---
def get_level(xp):
    # Simple math: Level 1 = 0xp, Level 2 = 100xp, Level 3 = 200xp
    return int(xp / 100) + 1

# --- DISCORD COMMANDS ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    await bot.change_presence(activity=discord.Game(name="/help | Growing Channels"))

@bot.event
async def on_message(message):
    if message.author.bot: return

    # 1. CHECK IF CHANNEL IS THE CHAT CHANNEL
    setting = settings_col.find_one({"server_id": str(message.guild.id)})
    
    # Only give XP if Chat Channel is set and matches
    if setting and "chat_channel" in setting and message.channel.id == setting["chat_channel"]:
        
        user_id = str(message.author.id)
        user = users_col.find_one({"discord_id": user_id})
        
        current_time = time.time()
        
        if not user:
            # New user
            users_col.insert_one({
                "discord_id": user_id, 
                "points": 0, 
                "xp": 0, 
                "last_msg": current_time
            })
        else:
            # CHECK COOLDOWN (60 Seconds)
            last_msg = user.get('last_msg', 0)
            if current_time - last_msg > 60:
                # Add 5 XP and 1 Point
                users_col.update_one(
                    {"discord_id": user_id}, 
                    {"$inc": {"xp": 5, "points": 1}, "$set": {"last_msg": current_time}}
                )
                
                # LEVEL UP CHECK
                old_level = get_level(user.get('xp', 0))
                new_level = get_level(user.get('xp', 0) + 5)
                
                if new_level > old_level:
                    await message.channel.send(f"🎉 **LEVEL UP!** {message.author.mention} is now **Level {new_level}**!")

    await bot.process_commands(message)

# --- ADMIN COMMANDS ---
@bot.command()
@commands.has_permissions(administrator=True)
async def set_chat(ctx):
    """Sets the current channel as the XP earning channel"""
    settings_col.update_one(
        {"server_id": str(ctx.guild.id)}, 
        {"$set": {"chat_channel": ctx.channel.id}}, 
        upsert=True
    )
    await ctx.send(f"✅ **Setup Complete!** Users will now earn XP and Points by chatting in {ctx.channel.mention} (Max once per minute).")

@bot.command()
async def stats(ctx):
    """Check your Level and Points"""
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    if not user:
        await ctx.send("You are new! Chat to earn XP.")
    else:
        lvl = get_level(user.get('xp', 0))
        pts = user.get('points', 0)
        xp = user.get('xp', 0)
        await ctx.send(f"📊 **{ctx.author.name}'s Stats**\n💳 Credits: `{pts}`\n⭐ Level: `{lvl}` (XP: {xp})")

@bot.command()
async def promote_channel(ctx, url: str):
    """Promote a YouTube Channel (Cost: 50 Points)"""
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    
    if not user or user.get('points', 0) < 50:
        await ctx.send("❌ You need **50 Points**! Chat or Sub to others to earn.")
        return

    # Level Check (Must be Level 2 to promote)
    if get_level(user.get('xp', 0)) < 2:
         await ctx.send("🔒 **Locked!** You must be **Level 2** to promote. Keep chatting!")
         return

    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
    links_col.insert_one({"url": url, "owner": user_id, "type": "channel"})
    
    embed = discord.Embed(title="🔥 Channel Spotlight!", description=f"Go Sub to this channel:\n{url}", color=0xFF0000)
    embed.add_field(name="Reward", value="💰 10 Points + 50 XP")
    await ctx.send(embed=embed)

@bot.command()
async def promote_video(ctx, url: str):
    """Promote a YouTube Video (Cost: 30 Points)"""
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    
    if not user or user.get('points', 0) < 30:
        await ctx.send("❌ You need **30 Points**!")
        return
        
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -30}})
    links_col.insert_one({"url": url, "owner": user_id, "type": "video"})
    
    embed = discord.Embed(title="🎥 Watch This Video!", description=f"Check this out:\n{url}", color=0x0000FF)
    embed.add_field(name="Reward", value="💰 10 Points + 50 XP (If you Sub)")
    await ctx.send(embed=embed)

@bot.command()
async def earn(ctx):
    """Get a random link to support"""
    pipeline = [{"$sample": {"size": 1}}]
    links = list(links_col.aggregate(pipeline))
    
    if len(links) == 0:
        await ctx.send("No active promotions right now. Chat to earn points!")
        return

    url = links[0]['url']
    await ctx.send(f"🚀 **Mission:** Go Subscribe to this channel:\n{url}\n\n*Make sure you have the Script installed!*")

# --- RUNNER ---
def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    t = threading.Thread(target=run_flask)
    t.start()
    bot.run(os.environ.get("DISCORD_TOKEN"))
