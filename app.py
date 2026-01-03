from flask import Flask, request, jsonify, render_template_string
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import pymongo
import os
from datetime import datetime

# --- CONFIGURATION ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'nexus_secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# --- DATABASE CHECK ---
MONGO_URL = os.environ.get("MONGO_URL")
db_status = "Checking..."

if not MONGO_URL:
    db_status = "❌ ERROR: MONGO_URL missing in Render Settings"
else:
    try:
        client = pymongo.MongoClient(MONGO_URL)
        db = client.get_database("sub_bot_db")
        users_col = db.users
        links_col = db.links
        db_status = "✅ System Operational"
    except Exception as e:
        db_status = f"❌ Database Error: {str(e)}"

# --- THE WEBSITE (LIVING INSIDE PYTHON) ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nexus Growth</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg: #09090b; --panel: #18181b; --accent: #6366f1; --text: #fff; --red: #ef4444; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; height: 100vh; margin: 0; display: flex; flex-direction: column; }
        .hidden { display: none !important; }
        
        /* LOGIN */
        #auth { position: fixed; inset: 0; background: var(--bg); z-index: 10; display: flex; align-items: center; justify-content: center; }
        .box { background: var(--panel); padding: 40px; border-radius: 12px; border: 1px solid #27272a; width: 350px; text-align: center; }
        input { width: 100%; padding: 12px; margin: 10px 0; background: #27272a; border: 1px solid #3f3f46; color: white; border-radius: 6px; }
        button { width: 100%; padding: 12px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: bold; margin-top: 10px; }
        .stat-bar { padding: 5px; font-size: 0.8rem; color: #a1a1aa; margin-bottom: 10px; }
        
        /* APP */
        #app { display: none; height: 100vh; display: flex; }
        .sidebar { width: 250px; padding: 20px; background: var(--panel); border-right: 1px solid #27272a; }
        .feed { flex: 1; padding: 20px; overflow-y: auto; }
        .chat { width: 300px; background: var(--panel); border-left: 1px solid #27272a; display: flex; flex-direction: column; }
        .card { background: var(--panel); padding: 15px; border: 1px solid #27272a; margin-bottom: 10px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; }
        .chat-msgs { flex: 1; overflow-y: auto; padding: 15px; }
        .chat-input { padding: 15px; border-top: 1px solid #27272a; }
    </style>
</head>
<body>

    <!-- AUTH SCREEN -->
    <div id="auth">
        <div class="box">
            <h1 style="color:var(--accent)">Nexus 🚀</h1>
            <div class="stat-bar">{{ db_status }}</div>
            <p id="error" style="color:var(--red); font-size:0.9rem;"></p>
            
            <div id="l-form">
                <input id="user" placeholder="Username">
                <input id="pass" type="password" placeholder="Password">
                <button onclick="doLogin()">Login</button>
                <p style="margin-top:15px; font-size:0.9rem; cursor:pointer;" onclick="toggle()">Create Account</p>
            </div>
            
            <div id="s-form" class="hidden">
                <input id="s-user" placeholder="New Username">
                <input id="s-pass" type="password" placeholder="New Password">
                <button onclick="doSignup()">Sign Up</button>
                <p style="margin-top:15px; font-size:0.9rem; cursor:pointer;" onclick="toggle()">Back to Login</p>
            </div>
        </div>
    </div>

    <!-- MAIN DASHBOARD -->
    <div id="app">
        <div class="sidebar">
            <h2 style="color:var(--accent)">Nexus</h2>
            <div style="margin-top: 20px; padding: 15px; background: #27272a; border-radius: 8px;">
                <h3 id="d-user">User</h3>
                <p>Points: <span id="d-pts" style="color:var(--accent)">0</span></p>
            </div>
            <button style="background:#3f3f46; margin-top:20px;" onclick="location.reload()">Logout</button>
        </div>

        <div class="feed">
            <div style="background:#27272a; padding:20px; border-radius:8px; margin-bottom:20px;">
                <h3>Promote Channel (-50 pts)</h3>
                <input id="url" placeholder="https://youtube.com/..." style="margin-bottom:0;">
                <button onclick="promote()" style="width:auto; padding: 8px 20px;">Promote</button>
            </div>
            <h3>Active Promotions</h3>
            <div id="feed-list">Loading...</div>
        </div>

        <div class="chat">
            <div style="padding:15px; border-bottom:1px solid #27272a; font-weight:bold;">Live Chat</div>
            <div class="chat-msgs" id="chat-box"></div>
            <div class="chat-input">
                <input id="msg" placeholder="Type..." onkeypress="if(event.key==='Enter') send()">
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currUser = null;

        function toggle() { 
            document.getElementById('l-form').classList.toggle('hidden'); 
            document.getElementById('s-form').classList.toggle('hidden'); 
            document.getElementById('error').innerText = "";
        }

        async function doLogin() {
            const u = document.getElementById('user').value;
            const p = document.getElementById('pass').value;
            try {
                const res = await fetch('/api/login', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: u, password: p}) });
                const data = await res.json();
                if(data.success) {
                    currUser = data.username;
                    localStorage.setItem('nexus_user', currUser);
                    enterApp(data);
                } else document.getElementById('error').innerText = data.error;
            } catch(e) { document.getElementById('error').innerText = "Connection Failed"; }
        }

        async function doSignup() {
            const u = document.getElementById('s-user').value;
            const p = document.getElementById('s-pass').value;
            try {
                const res = await fetch('/api/signup', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: u, password: p}) });
                const data = await res.json();
                if(data.success) { alert("Created! Login now."); toggle(); }
                else document.getElementById('error').innerText = data.error;
            } catch(e) { document.getElementById('error').innerText = "Connection Failed"; }
        }

        function enterApp(data) {
            document.getElementById('auth').classList.add('hidden');
            document.getElementById('app').style.display = 'flex';
            document.getElementById('d-user').innerText = currUser;
            document.getElementById('d-pts').innerText = data.points;
            loadFeed();
        }

        async function promote() {
            const url = document.getElementById('url').value;
            const res = await fetch('/api/promote', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: currUser, url: url, type: 'channel'}) });
            const data = await res.json();
            if(data.success) alert("Promoted!"); else alert(data.error);
        }

        async function loadFeed() {
            const res = await fetch('/api/data', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username: currUser}) });
            const data = await res.json();
            const list = document.getElementById('feed-list');
            list.innerHTML = "";
            data.links.forEach(l => {
                list.innerHTML += `<div class="card"><div><b>${l.owner}</b></div><a href="${l.url}" target="_blank"><button style="margin:0; padding:5px 15px;">Visit</button></a></div>`;
            });
        }

        function send() {
            const msg = document.getElementById('msg').value;
            if(!msg) return;
            socket.emit('send_message', {username: currUser, message: msg});
            document.getElementById('msg').value = '';
        }

        socket.on('receive_message', (d) => {
            const box = document.getElementById('chat-box');
            box.innerHTML += `<div style="margin-bottom:5px;"><b>${d.username}:</b> ${d.message}</div>`;
            box.scrollTop = box.scrollHeight;
        });

        socket.on('new_promotion', () => loadFeed());
        socket.on('update_stats', (d) => { if(d.username === currUser) document.getElementById('d-pts').innerText = parseInt(document.getElementById('d-pts').innerText) + d.points; });
    </script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def home():
    # Use render_template_string to read the HTML variable above
    return render_template_string(HTML_PAGE, db_status=db_status)

@app.route('/api/signup', methods=['POST'])
def signup():
    try:
        data = request.json
        if users_col.find_one({"username": data['username']}): return jsonify({"error": "Username Taken"}), 400
        users_col.insert_one({"username": data['username'], "password": data['password'], "points": 50, "xp": 0})
        return jsonify({"success": True})
    except: return jsonify({"error": "Database Error"}), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        user = users_col.find_one({"username": data['username'], "password": data['password']})
        if user: return jsonify({"success": True, "username": user['username'], "points": user['points']})
        return jsonify({"error": "Invalid Username/Password"}), 401
    except: return jsonify({"error": "Database Error"}), 500

@app.route('/api/data', methods=['POST'])
def get_data():
    links = list(links_col.find().sort('_id', -1).limit(20))
    for l in links: l['_id'] = str(l['_id'])
    return jsonify({"links": links})

@app.route('/api/promote', methods=['POST'])
def promote():
    data = request.json
    user = users_col.find_one({"username": data['username']})
    if user['points'] < 50: return jsonify({"error": "Need 50 points"})
    users_col.update_one({"username": data['username']}, {"$inc": {"points": -50}})
    new_link = {"url": data['url'], "owner": data['username'], "type": "channel"}
    links_col.insert_one(new_link)
    new_link['_id'] = str(new_link['_id'])
    socketio.emit('new_promotion', new_link)
    return jsonify({"success": True})

@app.route('/verify_action', methods=['POST'])
def verify():
    data = request.json
    username = data.get('username')
    action = data.get('type')
    if action == "SUB":
        users_col.update_one({"username": username}, {"$inc": {"points": 10}})
        socketio.emit('update_stats', {"username": username, "points": 10})
    return jsonify({"msg": "OK"})

@socketio.on('send_message')
def handle_msg(data):
    emit('receive_message', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=10000)
