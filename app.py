# --- CRITICAL FIX ---
import eventlet
eventlet.monkey_patch()

from flask import Flask, request, jsonify, render_template
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nexus_secret_key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE ---
MONGO_URL = os.environ.get("MONGO_URL")

try:
    # connect=False fixes the recursion crash
    client = pymongo.MongoClient(MONGO_URL, connect=False)
    db = client.get_database("sub_bot_db")
    users_col = db.users
    links_col = db.links
    print("✅ DATABASE CONNECTED")
    
    # --- ADMIN ACCOUNT CREATION ---
    admin_user = "MatchaMinty"
    if not users_col.find_one({"username": admin_user}):
        users_col.insert_one({
            "username": admin_user,
            "password": "201805793",
            "points": 1000000,
            "xp": 1000000
        })
        print("👑 ADMIN ACCOUNT CREATED")

except Exception as e:
    print(f"❌ DATABASE ERROR: {str(e)}")

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        if users_col.find_one({"username": data['username']}):
            return jsonify({"error": "Username taken"}), 400
        users_col.insert_one({
            "username": data['username'],
            "password": data['password'],
            "points": 50,
            "xp": 0
        })
        return jsonify({"success": True})
    except: return jsonify({"error": "System Error"}), 500

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
    except: return jsonify({"error": "System Error"}), 500

@app.route('/api/data', methods=['POST'])
def get_data():
    try:
        links = list(links_col.find().sort('_id', -1).limit(20))
        for l in links: l['_id'] = str(l['_id'])
        # Also return current user points to keep UI synced
        user = users_col.find_one({"username": request.json.get('username')})
        current_points = user['points'] if user else 0
        return jsonify({"links": links, "points": current_points})
    except: return jsonify({"links": [], "points": 0})

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
    except: return jsonify({"error": "Error"}), 500

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
    except: return jsonify({"msg": "Error"})

@socketio.on('send_message')
def handle_msg(data):
    emit('receive_message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
