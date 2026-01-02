from flask import Flask, request, jsonify
from flask_cors import CORS
import pymongo
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app) # Allows your website to talk to this backend

# CONNECT TO DATABASE
# We will set the URL in Render settings later
MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users
links_col = db.links

@app.route('/')
def home():
    return "Backend is Active!"

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    user = users_col.find_one({"username": username})
    if not user:
        # Create new user
        users_col.insert_one({
            "username": username,
            "points": 50, # Starter points
            "timeout_until": datetime.now()
        })
    return jsonify({"status": "success"})

@app.route('/get_user', methods=['POST'])
def get_user():
    data = request.json
    user = users_col.find_one({"username": data['username']})
    # Check if timed out
    is_timed_out = False
    if user.get('timeout_until') > datetime.now():
        is_timed_out = True
    
    return jsonify({
        "points": user['points'],
        "is_timed_out": is_timed_out
    })

@app.route('/add_link', methods=['POST'])
def add_link():
    data = request.json
    username = data['username']
    url = data['url']
    
    user = users_col.find_one({"username": username})
    if user['points'] < 50:
        return jsonify({"error": "Not enough points! Need 50."})
    
    # Deduct points and add link
    users_col.update_one({"username": username}, {"$inc": {"points": -50}})
    links_col.insert_one({"url": url, "owner": username})
    return jsonify({"status": "success"})

@app.route('/get_links', methods=['GET'])
def get_links():
    # Get 10 random links
    links = list(links_col.aggregate([{"$sample": {"size": 10}}]))
    for link in links:
        link['_id'] = str(link['_id']) # Fix for JSON
    return jsonify(links)

@app.route('/verify_action', methods=['POST'])
def verify():
    data = request.json
    username = data['username']
    action_type = data['type'] # 'SUB' or 'UNSUB'

    user = users_col.find_one({"username": username})

    # CHECK TIMEOUT
    if user.get('timeout_until') > datetime.now():
        return jsonify({"error": "You are timed out!"})

    if action_type == "SUB":
        users_col.update_one({"username": username}, {"$inc": {"points": 10}})
        return jsonify({"msg": "Points Added!"})
    
    elif action_type == "UNSUB":
        # 20 Minute Timeout
        timeout_time = datetime.now() + timedelta(minutes=20)
        users_col.update_one({"username": username}, {"$set": {"timeout_until": timeout_time}})
        return jsonify({"msg": "TIMEOUT APPLIED"})

    return jsonify({"msg": "Action received"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
