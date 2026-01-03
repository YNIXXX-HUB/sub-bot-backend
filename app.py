from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os
import time
from datetime import datetime

# --- SETUP ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'mysecretkey123'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE ---
MONGO_URL = os.environ.get("MONGO_URL")
client = pymongo.MongoClient(MONGO_URL)
db = client.get_database("sub_bot_db")
users_col = db.users
links_col = db.links
chat_col = db.chat_history

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.json
    username = data.get('username')
    password = data.get('password') # In a real app, hash this!
    
    if users_col.find_one({"username": username}):
        return jsonify({"error": "Username taken"}), 400
        
    users_col.insert_one({
        "username": username,
        "password": password,
        "points": 50, # Starter Bonus
        "xp": 0,
        "joined_at": datetime.now()
    })
    return jsonify({"success": True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = users_col.find_one({"username": data['username'], "password": data['password']})
    if user:
        return jsonify({
            "success": True, 
            "username": user['username'], 
            "points": user['points'],
            "xp": user['xp']
        })
    return jsonify({"error": "Invalid Login"}), 401

@app.route('/api/data', methods=['POST'])
def get_data():
    username = request.json.get('username')
    user = users_col.find_one({"username": username})
    if not user: return jsonify({"error": "User not found"})
    
    # Get recent links
    links = list(links_col.find().sort('_id', -1).limit(20))
    for link in links: link['_id'] = str(link['_id'])
    
    return jsonify({
        "points": user['points'],
        "xp": user['xp'],
        "links": links
    })

@app.route('/api/promote', methods=['POST'])
def promote():
    data = request.json
    username = data.get('username')
    url = data.get('url')
    type_ = data.get('type') # 'channel' or 'video'
    cost = 50 if type_ == 'channel' else 30
    
    user = users_col.find_one({"username": username})
    if user['points'] < cost:
        return jsonify({"error": "Not enough points!"})
        
    users_col.update_one({"username": username}, {"$inc": {"points": -cost}})
    
    new_link = {
        "url": url,
        "owner": username,
        "type": type_,
        "timestamp": datetime.now()
    }
    links_col.insert_one(new_link)
    
    # Notify all users via Socket
    new_link['_id'] = str(new_link['_id']) # Fix ID for JSON
    new_link['timestamp'] = str(new_link['timestamp'])
    socketio.emit('new_promotion', new_link)
    
    return jsonify({"success": True})

@app.route('/verify_action', methods=['POST'])
def verify():
    # This comes from Tampermonkey
    data = request.json
    username = data.get('username') # Script must send username now
    action = data.get('type')

    user = users_col.find_one({"username": username})
    if not user: return jsonify({"error": "User not found"})

    if action == "SUB":
        users_col.update_one({"username": username}, {"$inc": {"points": 10, "xp": 50}})
        socketio.emit('update_stats', {"username": username, "points": 10}) # Live update
        return jsonify({"msg": "Points Added"})
    
    if action == "UNSUB":
        users_col.update_one({"username": username}, {"$inc": {"points": -50}})
        return jsonify({"msg": "Punishment logged"})

    return jsonify({"msg": "Received"})

# --- SOCKET.IO (CHAT) ---
@socketio.on('send_message')
def handle_message(data):
    username = data['username']
    msg = data['message']
    
    # Reward XP for chatting (Max 1 per 5 secs handled on client or simple check here)
    users_col.update_one({"username": username}, {"$inc": {"xp": 1}})
    
    emit('receive_message', {'username': username, 'message': msg}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
