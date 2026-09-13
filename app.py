# ================================================================
# AIMAI KEY SERVER — RAILWAY DEPLOYMENT READY
# ================================================================
# Railway pe persistent storage auto-mount hoti hai /data pe
# ================================================================

from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
import sqlite3, os, json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "aimai_super_secret_key_2026_change_this")

# Railway persistent volume /data pe mount hota hai
DB_PATH = os.environ.get("DB_PATH", "/data/aimai_keys.db")
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/data/aimai_config.json")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "@no_one15_3&love")
TG_LINK = os.environ.get("TG_LINK", "https://t.me/no_one15_3")

# ================================================================
# CONFIG
# ================================================================
def load_config():
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except:
        return {"server_active": True}

def save_config(cfg):
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(cfg, f)
    except Exception as e:
        print(f"Config save error: {e}")

# ================================================================
# DATABASE
# ================================================================
def init_db():
    try:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    except:
        pass
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            active INTEGER DEFAULT 1,
            used INTEGER DEFAULT 0,
            created_at TEXT,
            activated_at TEXT,
            last_seen TEXT,
            ip TEXT,
            device TEXT,
            uses INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT,
            ip TEXT,
            device TEXT,
            action TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return wrapper

# ================================================================
# API — VERIFY
# ================================================================
@app.route("/api/verify", methods=["POST"])
def api_verify():
    cfg = load_config()
    if not cfg.get("server_active", True):
        return jsonify({"valid": False, "message": "Service temporarily unavailable"})
    
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    device = data.get("device", "unknown")

    if not key:
        return jsonify({"valid": False, "message": "Key is required"})

    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT * FROM keys WHERE key = ?", (key,)).fetchone()

    if not row:
        c.execute("INSERT INTO logs (key, ip, device, action, timestamp) VALUES (?,?,?,?,?)",
                  (key, ip, device, "INVALID_KEY", now()))
        conn.commit()
        conn.close()
        return jsonify({"valid": False, "message": "Invalid key"})

    if row["active"] != 1:
        c.execute("INSERT INTO logs (key, ip, device, action, timestamp) VALUES (?,?,?,?,?)",
                  (key, ip, device, "DISABLED_KEY", now()))
        conn.commit()
        conn.close()
        return jsonify({"valid": False, "message": "Key is disabled"})

    activated_at = row["activated_at"] or now()
    c.execute("""UPDATE keys SET used = 1, activated_at = ?, last_seen = ?, ip = ?, device = ?, uses = uses + 1
                 WHERE key = ?""", (activated_at, now(), ip, device, key))
    c.execute("INSERT INTO logs (key, ip, device, action, timestamp) VALUES (?,?,?,?,?)",
              (key, ip, device, "VALID", now()))
    conn.commit()
    conn.close()

    return jsonify({
        "valid": True,
        "message": "Access granted",
        "key": key,
        "activated_at": activated_at,
        "tg_link": TG_LINK
    })

# ================================================================
# API — HEARTBEAT
# ================================================================
@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    cfg = load_config()
    if not cfg.get("server_active", True):
        return jsonify({"ok": False})
    
    data = request.get_json(silent=True) or {}
    key = (data.get("key") or "").strip()
    if not key:
        return jsonify({"ok": False})

    conn = get_db()
    c = conn.cursor()
    row = c.execute("SELECT active FROM keys WHERE key = ?", (key,)).fetchone()
    if not row or row["active"] != 1:
        conn.close()
        return jsonify({"ok": False})

    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"
    c.execute("UPDATE keys SET last_seen = ?, ip = ? WHERE key = ?", (now(), ip, key))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

# ================================================================
# HEALTH
# ================================================================
@app.route("/health")
def health():
    cfg = load_config()
    return jsonify({
        "status": "running",
        "server_active": cfg.get("server_active", True),
        "time": now()
    })

@app.route("/")
def home():
    return jsonify({
        "name": "AimAi Key Server",
        "status": "online",
        "host": "railway",
        "endpoints": ["/api/verify", "/api/heartbeat", "/health", "/admin"]
    })

# ================================================================
# ADMIN LOGIN
# ================================================================
LOGIN_HTML = """
<!DOCTYPE html><html><head><title>Admin Login</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{background:#0a0a0f;color:#fff;font-family:system-ui,Arial;display:flex;justify-content:center;align-items:center;height:100vh;margin:0}
.box{background:#1a1a2e;padding:40px;border-radius:16px;width:320px;border:1px solid #333;box-shadow:0 0 40px rgba(167,139,250,0.3)}
h2{text-align:center;color:#a78bfa;margin-bottom:24px}
input{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid #333;background:#0a0a0f;color:#fff;box-sizing:border-box;outline:none}
input:focus{border-color:#a78bfa}
button{width:100%;padding:12px;background:linear-gradient(135deg,#a78bfa,#6d28d9);color:#fff;border:none;border-radius:8px;font-weight:bold;cursor:pointer;margin-top:12px;font-size:15px}
button:hover{opacity:0.9}
.err{color:#f87171;text-align:center;margin-top:12px;font-size:14px}
.logo{text-align:center;font-size:48px;margin-bottom:10px}
</style></head><body>
<div class="box">
<div class="logo">🦆</div>
<h2>AimAi Admin</h2>
<form method="POST">
<input type="password" name="password" placeholder="Enter admin password" required autofocus>
<button type="submit">🔐 Login</button>
</form>
{% if error %}<div class="err">{{ error }}</div>{% endif %}
</div></body></html>
"""

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect(url_for("admin_panel"))
        return render_template_string(LOGIN_HTML, error="Wrong password")
    return render_template_string(LOGIN_HTML, error=None)

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

# ================================================================
# ADMIN PANEL
# ================================================================
PANEL_HTML = """
<!DOCTYPE html><html><head><title>Admin Panel</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{background:#0a0a0f;color:#fff;font-family:system-ui,Arial;margin:0;padding:20px}
h1{color:#a78bfa;margin:0;font-size:22px}
.top{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;margin-bottom:20px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-bottom:20px}
.stat{background:#1a1a2e;padding:16px 20px;border-radius:12px;border:1px solid #333}
.stat b{display:block;font-size:26px;color:#a78bfa;font-weight:bold}
.stat span{color:#888;font-size:12px;text-transform:uppercase;letter-spacing:1px}
table{width:100%;border-collapse:collapse;background:#1a1a2e;border-radius:12px;overflow:hidden;font-size:13px}
th,td{padding:10px;text-align:left;border-bottom:1px solid #222}
th{background:#222;color:#a78bfa;font-weight:600;text-transform:uppercase;font-size:11px;letter-spacing:1px}
tr:hover{background:#222}
tr:last-child td{border-bottom:none}
.btn{padding:6px 12px;border-radius:6px;text-decoration:none;font-size:12px;margin:2px;display:inline-block;border:none;cursor:pointer;font-weight:600}
.on{background:#22c55e;color:#000}
.off{background:#ef4444;color:#fff}
.del{background:#666;color:#fff}
input,button{padding:10px 14px;border-radius:8px;border:1px solid #333;background:#1a1a2e;color:#fff;outline:none;font-size:14px}
button{background:linear-gradient(135deg,#a78bfa,#6d28d9);color:#fff;font-weight:bold;cursor:pointer;border:none}
button:hover{opacity:0.9}
.add{margin:20px 0;display:flex;gap:10px;flex-wrap:wrap}
.key{font-family:'Courier New',monospace;color:#fbbf24;cursor:pointer;background:#2a2a1a;padding:3px 8px;border-radius:4px;user-select:all}
.key:hover{background:#3a3a2a}
.small{font-size:11px;color:#888}
.server-box{background:#1a1a2e;padding:20px;border-radius:12px;border:2px solid #a78bfa;margin-bottom:20px}
.server-active{border-color:#22c55e;box-shadow:0 0 20px rgba(34,197,94,0.3)}
.server-off{border-color:#ef4444;box-shadow:0 0 20px rgba(239,68,68,0.3)}
.toggle-btn{padding:12px 24px;border-radius:8px;font-weight:bold;font-size:14px;text-decoration:none;display:inline-block;margin-top:10px}
.toggle-on{background:#22c55e;color:#000}
.toggle-off{background:#ef4444;color:#fff}
.footer{margin-top:20px;text-align:center;font-size:12px;color:#555}
.footer a{color:#a78bfa;text-decoration:none}
.status-badge{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600}
.status-active{background:#22c55e;color:#000}
.status-disabled{background:#ef4444;color:#fff}
</style>
<script>
function copyKey(k) {
    navigator.clipboard.writeText(k).then(() => {
        alert('✅ Key copied: ' + k);
    }).catch(() => {
        const el = document.createElement('textarea');
        el.value = k;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        alert('✅ Key copied: ' + k);
    });
}
</script>
</head><body>

<div class="top">
<h1>🦆 AimAi Admin Panel · Railway</h1>
<a href="/admin/logout" class="btn off">Logout</a>
</div>

<!-- SERVER MASTER SWITCH -->
<div class="server-box {% if server_active %}server-active{% else %}server-off{% endif %}">
<h3 style="margin-top:0">{% if server_active %}🟢 Server ACTIVE{% else %}🔴 Server DISABLED{% endif %}</h3>
<p style="color:#aaa;font-size:13px;margin:8px 0">
{% if server_active %}
Saari keys kaam kar rahi hain. Heartbeat 60 sec mein check hoga.
{% else %}
SAARI KEYS OFF HAIN — koi bhi key kaam nahi karegi. Connected apps 60 sec mein band ho jayenge.
{% endif %}
</p>
<a href="/admin/toggle-server" class="toggle-btn {% if server_active %}toggle-off{% else %}toggle-on{% endif %}">
{% if server_active %}🛑 DISABLE SERVER{% else %}✅ ENABLE SERVER{% endif %}
</a>
</div>

<!-- STATS -->
<div class="stats">
<div class="stat"><b>{{ total }}</b><span>Total Keys</span></div>
<div class="stat"><b>{{ active }}</b><span>Active</span></div>
<div class="stat"><b>{{ used }}</b><span>Used</span></div>
<div class="stat"><b>{{ disabled }}</b><span>Disabled</span></div>
</div>

<!-- ADD KEY -->
<div class="add">
<form method="POST" action="/admin/add" style="display:flex;gap:10px;flex-wrap:wrap">
<input name="key" placeholder="Enter custom key (any characters)" required style="min-width:280px">
<button type="submit">➕ Add Key</button>
</form>
</div>

<!-- KEYS TABLE -->
<table>
<tr>
<th>ID</th>
<th>Key</th>
<th>Status</th>
<th>Uses</th>
<th>IP</th>
<th>Device</th>
<th>Activated</th>
<th>Last Seen</th>
<th>Actions</th>
</tr>
{% for k in keys %}
<tr>
<td>{{ k['id'] }}</td>
<td><span class="key" onclick="copyKey('{{ k['key'] }}')" title="Click to copy">{{ k['key'] }}</span></td>
<td>
{% if k['active'] %}
<span class="status-badge status-active">● ACTIVE</span>
{% else %}
<span class="status-badge status-disabled">● DISABLED</span>
{% endif %}
</td>
<td>{{ k['uses'] }}</td>
<td class="small">{{ k['ip'] or '-' }}</td>
<td class="small">{{ k['device'] or '-' }}</td>
<td class="small">{{ k['activated_at'] or '-' }}</td>
<td class="small">{{ k['last_seen'] or '-' }}</td>
<td>
<a href="/admin/toggle/{{ k['id'] }}" class="btn {% if k['active'] %}off{% else %}on{% endif %}">
{% if k['active'] %}Disable{% else %}Enable{% endif %}
</a>
<a href="/admin/delete/{{ k['id'] }}" class="btn del" onclick="return confirm('Delete key {{ k['key'] }}?')">Del</a>
</td>
</tr>
{% endfor %}
</table>

<div class="footer">
Powered by <a href="{{ tg }}" target="_blank">@no_one15_3</a> · Server time: {{ time }}
</div>

</body></html>
"""

@app.route("/admin/panel")
@admin_required
def admin_panel():
    cfg = load_config()
    conn = get_db()
    c = conn.cursor()
    keys = c.execute("SELECT * FROM keys ORDER BY id DESC").fetchall()
    total = len(keys)
    active = sum(1 for k in keys if k["active"])
    used = sum(1 for k in keys if k["used"])
    disabled = total - active
    conn.close()
    return render_template_string(
        PANEL_HTML,
        keys=keys, total=total, active=active, used=used, disabled=disabled,
        tg=TG_LINK, server_active=cfg.get("server_active", True), time=now()
    )

@app.route("/admin/add", methods=["POST"])
@admin_required
def admin_add():
    key = (request.form.get("key") or "").strip()
    if key:
        conn = get_db()
        c = conn.cursor()
        try:
            c.execute("INSERT INTO keys (key, active, created_at) VALUES (?, 1, ?)", (key, now()))
            conn.commit()
        except sqlite3.IntegrityError:
            pass
        conn.close()
    return redirect(url_for("admin_panel"))

@app.route("/admin/toggle/<int:kid>")
@admin_required
def admin_toggle(kid):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE keys SET active = CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id = ?", (kid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))

@app.route("/admin/delete/<int:kid>")
@admin_required
def admin_delete(kid):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM keys WHERE id = ?", (kid,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_panel"))

@app.route("/admin/toggle-server")
@admin_required
def admin_toggle_server():
    cfg = load_config()
    cfg["server_active"] = not cfg.get("server_active", True)
    save_config(cfg)
    return redirect(url_for("admin_panel"))

# ================================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)