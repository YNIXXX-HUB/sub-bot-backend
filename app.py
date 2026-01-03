from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os
import time
from datetime import datetime

# --- SETUP ---
# template_folder='.' looks for index.html in the main folder
app = Flask(__name__, template_folder='.')
app.config['SECRET_KEY'] = 'mysecretkey123'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE CONNECTION ---
MONGO_URL = os.environ.get("MONGO_URL")

if not MONGO_URL:
    print("CRITICAL ERROR: MONGO_URL is missing from Render Settings!")
else:
    print("Database URL found. Connecting...")

try:
    client = pymongo.MongoClient(MONGO_URL)
    db = client.get_database("sub_bot_db")
    users_col = db.users
    links_col = db.links
    print("✅ Database Connected Successfully")
except Exception as e:
    print(f"❌ Database Connection Failed: {e}")

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({"error": "Missing username or password"}), 400
        
        # Check if user exists
        if users_col.find_one({"username": username}):
            return jsonify({"error": "Username already taken!"}), 400
            
        users_col.insert_one({
            "username": username,
            "password": password,
            "points": 50,
            "xp": 0,
            "joined_at": datetime.now()
        })
        return jsonify({"success": True})
    except Exception as e:
        print(f"Signup Error: {e}")
        return jsonify({"error": "Server Error. Check Render Logs."}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user = users_col.find_one({"username": data['username'], "password": data['password']})
        if user:
            return jsonify({
                "success": True, 
                "username": user['username'], 
                "points": user['points'],
                "xp": user['xp']
            })
        return jsonify({"error": "Wrong Username or Password"}), 401
    except Exception as e:
        print(f"Login Error: {e}")
        return jsonify({"error": "Server Error"}), 500

@app.route('/api/data', methods=['POST'])
def get_data():
    try:
        username = request.json.get('username')
        user = users_col.find_one({"username": username})
        if not user: return jsonify({"error": "User not found"})
        
        # Get recent links
        links = list(links_col.find().sort('_id', -1).limit(20))
        for link in links: 
            link['_id'] = str(link['_id'])
            link['timestamp'] = str(link.get('timestamp', ''))
        
        return jsonify({
            "points": user['points'],
            "xp": user['xp'],
            "links": links
        })
    except Exception as e:
        print(f"Data Error: {e}")
        return jsonify({"error": "Failed to load data"}), 500

@app.route('/api/promote', methods=['POST'])
def promote():
    try:
        data = request.json
        username = data.get('username')
        url = data.get('url')
        type_ = data.get('type') 
        cost = 50 if type_ == 'channel' else 30
        
        user = users_col.find_one({"username": username})
        if user['points'] < cost:
            return jsonify({"error": f"Not enough points! Need {cost}."})
            
        users_col.update_one({"username": username}, {"$inc": {"points": -cost}})
        
        new_link = {
            "url": url,
            "owner": username,
            "type": type_,
            "timestamp": datetime.now()
        }
        links_col.insert_one(new_link)
        
        new_link['_id'] = str(new_link['_id'])
        new_link['timestamp'] = str(new_link['timestamp'])
        socketio.emit('new_promotion', new_link)
        
        return jsonify({"success": True})
    except Exception as e:
        print(f"Promote Error: {e}")
        return jsonify({"error": "Failed to promote"}), 500

@app.route('/verify_action', methods=['POST'])
def verify():
    try:
        data = request.json
        username = data.get('username')
        action = data.get('type')

        user = users_col.find_one({"username": username})
        if not user: return jsonify({"error": "User not found"})

        if action == "SUB":
            users_col.update_one({"username": username}, {"$inc": {"points": 10, "xp": 50}})
            socketio.emit('update_stats', {"username": username, "points": 10}) 
            return jsonify({"msg": "Points Added"})
        
        if action == "UNSUB":
            users_col.update_one({"username": username}, {"$inc": {"points": -50}})
            return jsonify({"msg": "Punishment logged"})

        return jsonify({"msg": "Received"})
    except Exception as e:
        print(f"Verify Error: {e}")
        return jsonify({"error": "Server Error"}), 500

# --- SOCKET.IO ---
@socketio.on('send_message')
def handle_message(data):
    username = data['username']
    msg = data['message']
    users_col.update_one({"username": username}, {"$inc": {"xp": 1}})
    emit('receive_message', {'username': username, 'message': msg}, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
