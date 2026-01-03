from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os
from datetime import datetime

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nexus_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE CONNECTION ---
MONGO_URL = os.environ.get("MONGO_URL")

# Try to connect immediately to test status
try:
    if not MONGO_URL:
        raise Exception("MONGO_URL Environment Variable is missing")
    
    client = pymongo.MongoClient(MONGO_URL)
    db = client.get_database("sub_bot_db")
    users_col = db.users
    links_col = db.links
    print("✅ MONGODB CONNECTED SUCCESSFULLY")
except Exception as e:
    print(f"❌ MONGODB CONNECTION FAILED: {str(e)}")
    # We do not crash the app, but DB functions will fail later

# --- ROUTES ---

@app.route('/')
def home():
    # Looks for templates/index.html
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        if users_col.find_one({"username": data['username']}):
            return jsonify({"error": "Username already taken"}), 400
        
        users_col.insert_one({
            "username": data['username'],
            "password": data['password'],
            "points": 50,
            "xp": 0
        })
        return jsonify({"success": True})
    except Exception as e:
        print(f"Signup Error: {e}")
        return jsonify({"error": "Database Error: Check Render Logs"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user = users_col.find_one({"username": data['username'], "password": data['password']})
        if user:
            return jsonify({
                "success": True, 
                "username": user['username'], 
                "points": user['points']
            })
        return jsonify({"error": "Invalid Username or Password"}), 401
    except Exception as e:
        print(f"Login Error: {e}")
        return jsonify({"error": "Database Connection Failed"}), 500

@app.route('/api/data', methods=['POST'])
def get_data():
    try:
        links = list(links_col.find().sort('_id', -1).limit(20))
        for l in links: l['_id'] = str(l['_id'])
        return jsonify({"links": links})
    except:
        return jsonify({"links": []})

@app.route('/api/promote', methods=['POST'])
def promote():
    try:
        data = request.json
        user = users_col.find_one({"username": data['username']})
        if user['points'] < 50: return jsonify({"error": "Need 50 points"})
        
        users_col.update_one({"username": data['username']}, {"$inc": {"points": -50}})
        
        new_link = {"url": data['url'], "owner": data['username'], "type": "channel"}
        links_col.insert_one(new_link)
        
        new_link['_id'] = str(new_link['_id'])
        socketio.emit('new_promotion', new_link)
        return jsonify({"success": True})
    except:
        return jsonify({"error": "Database Error"}), 500

@app.route('/verify_action', methods=['POST'])
def verify():
    # Endpoint for Tampermonkey Script
    try:
        data = request.json
        username = data.get('username')
        action = data.get('type')
        if action == "SUB":
            users_col.update_one({"username": username}, {"$inc": {"points": 10}})
            socketio.emit('update_stats', {"username": username, "points": 10})
        return jsonify({"msg": "OK"})
    except:
        return jsonify({"msg": "Error"})

@socketio.on('send_message')
def handle_msg(data):
    emit('receive_message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
