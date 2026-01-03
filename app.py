# --- CRITICAL FIX: MUST BE THE FIRST TWO LINES ---
import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nexus_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE CONNECTION ---
MONGO_URL = os.environ.get("MONGO_URL")

try:
    if not MONGO_URL:
        print("❌ MONGO_URL MISSING")
    else:
        # connect=False prevents immediate connection, waiting for the first request
        # This helps prevent the recursion error during startup
        client = pymongo.MongoClient(MONGO_URL, connect=False) 
        db = client.get_database("sub_bot_db")
        users_col = db.users
        links_col = db.links
        print("✅ DATABASE CONFIG LOADED")
except Exception as e:
    print(f"❌ DATABASE SETUP ERROR: {str(e)}")

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        # Check if user exists
        if users_col.find_one({"username": data['username']}):
            return jsonify({"error": "Username taken"}), 400
        
        users_col.insert_one({
            "username": data['username'],
            "password": data['password'],
            "points": 50,
            "xp": 0
        })
        return jsonify({"success": True})
    except Exception as e:
        print(f"Signup Error: {e}")
        return jsonify({"error": "System Error. Try again."}), 500

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
        return jsonify({"error": "System Error. Try again."}), 500

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
