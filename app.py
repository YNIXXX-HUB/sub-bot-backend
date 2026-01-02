import discord
from discord.ext import commands
from flask import Flask, request, jsonify
from flask_cors import CORS
import pymongo
import threading
import os
import asyncio

# --- CONFIGURATION ---
MONGO_URL = os.environ.get("MONGO_URL")
# PASTE YOUR DISCORD TOKEN AT THE BOTTOM OF THE FILE!

# --- DATABASE SETUP ---
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users
links_col = db.links

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# --- FLASK API SETUP (For the Script) ---
app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return "Bot is Alive"

@app.route('/verify_action', methods=['POST'])
def verify():
    data = request.json
    discord_id = data.get('discord_id') # The script sends the User ID
    action = data.get('type')

    if not discord_id:
        return jsonify({"error": "No ID"})

    user = users_col.find_one({"discord_id": discord_id})
    if not user:
        return jsonify({"error": "User not found in Discord"})

    if action == "SUB":
        users_col.update_one({"discord_id": discord_id}, {"$inc": {"points": 10}})
        return jsonify({"msg": "Points Added"})
    
    if action == "UNSUB":
        # Deduct points or timeout logic here
        return jsonify({"msg": "Punishment logged"})

    return jsonify({"msg": "Received"})

# --- DISCORD COMMANDS ---

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # XP SYSTEM (Chatting gives 1 point)
    user_id = str(message.author.id)
    user = users_col.find_one({"discord_id": user_id})
    
    if not user:
        users_col.insert_one({"discord_id": user_id, "points": 0, "xp": 0})
    else:
        users_col.update_one({"discord_id": user_id}, {"$inc": {"xp": 1}})

    await bot.process_commands(message)

@bot.command()
async def points(ctx):
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    if not user:
        await ctx.send("You have 0 points.")
    else:
        await ctx.send(f"💳 You have **{user['points']}** points.")

@bot.command()
async def promote(ctx, url: str):
    user_id = str(ctx.author.id)
    user = users_col.find_one({"discord_id": user_id})
    
    if not user or user['points'] < 50:
        await ctx.send("❌ You need **50 Points** to promote! Install the script and sub to others first.")
        return

    # Deduct points
    users_col.update_one({"discord_id": user_id}, {"$inc": {"points": -50}})
    
    # Save link
    links_col.insert_one({"url": url, "owner": user_id})
    
    # Send Embed
    embed = discord.Embed(title="🌟 New Channel Promotion!", description=f"Check out this channel:\n{url}", color=0x00ff00)
    embed.set_footer(text="Click the link, sub, and earn points!")
    
    # Send to a specific channel (Optional: Replace CHANNEL_ID)
    await ctx.send(embed=embed)

@bot.command()
async def earn(ctx):
    # Get a random link
    pipeline = [{"$sample": {"size": 1}}]
    links = list(links_col.aggregate(pipeline))
    
    if len(links) == 0:
        await ctx.send("No links to promote yet!")
        return

    url = links[0]['url']
    await ctx.send(f"Go sub to this channel to earn 10 points:\n{url}\n\n*Make sure you have the Script installed!*")

# --- RUNNING BOTH AT ONCE ---
def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == '__main__':
    # Start Flask in a background thread
    t = threading.Thread(target=run_flask)
    t.start()
    
    # Start Discord Bot (PASTE TOKEN BELOW)
    # This tells the bot to get the password from Render's secret vault
bot.run(os.environ.get("DISCORD_TOKEN"))
