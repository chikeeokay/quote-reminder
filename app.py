import os, json, random, threading, time, urllib.request, urllib.parse
import psycopg2, psycopg2.extras
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="require")

def init_db():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    author TEXT DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
        conn.commit()

def get_quotes():
    with get_db() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT id, text, author FROM quotes ORDER BY created_at ASC")
            return [dict(r) for r in cur.fetchall()]

def add_quote(text, author, qid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO quotes (id, text, author) VALUES (%s, %s, %s)",
                        (qid, text, author))
        conn.commit()

def delete_quote(qid):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM quotes WHERE id = %s", (qid,))
        conn.commit()

def get_config():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT key, value FROM config")
            rows = cur.fetchall()
            return {k: v for k, v in rows}

def set_config(key, value):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO config (key, value) VALUES (%s, %s)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """, (key, str(value)))
        conn.commit()

# Init DB on startup
try:
    init_db()
except Exception as e:
    print(f"DB init error: {e}")

# ── Telegram ─────────────────────────────────────────────────
def send_telegram(token, chat_id, text):
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())

# ── Background reminder thread ────────────────────────────────
state = {
    "running":    False,
    "thread":     None,
    "next_time":  None,
    "next_quote": None,
    "last_sent":  None,
}

def pick_next():
    quotes = get_quotes()
    if quotes:
        state["next_quote"] = random.choice(quotes)
    else:
        state["next_quote"] = None

def reminder_loop():
    while state["running"]:
        cfg     = get_config()
        token   = cfg.get("token", "")
        chat_id = cfg.get("chat_id", "")
        interval = int(cfg.get("interval", "60")) * 60

        q = state.get("next_quote")
        if q and token and chat_id:
            msg = f'💬 "{q["text"]}"'
            if q.get("author"):
                msg += f'\n\n— {q["author"]}'
            try:
                send_telegram(token, chat_id, msg)
                state["last_sent"] = q
            except Exception as e:
                state["last_sent"] = {"text": f"Send error: {e}", "author": ""}

        pick_next()
        state["next_time"] = time.time() + interval

        for _ in range(interval):
            if not state["running"]:
                break
            time.sleep(1)

def start_reminder():
    if state["running"]:
        return
    state["running"] = True
    pick_next()
    t = threading.Thread(target=reminder_loop, daemon=True)
    state["thread"] = t
    t.start()

def stop_reminder():
    state["running"]    = False
    state["next_time"]  = None
    state["next_quote"] = None

# Auto-resume if previously running
try:
    cfg0 = get_config()
    if cfg0.get("running") == "true" and cfg0.get("token") and cfg0.get("chat_id") and get_quotes():
        start_reminder()
except Exception as e:
    print(f"Auto-resume error: {e}")

# ── HTML ──────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Quote Reminder</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',sans-serif;background:#FAF9F6;color:#1A1916;padding:2rem 1rem 4rem}
.wrap{max-width:740px;margin:0 auto}
h1{font-size:22px;font-weight:700;letter-spacing:-.3px}
.sub{font-size:13px;color:#7A776F;margin-top:4px;margin-bottom:2rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:580px){.grid{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #E8E5DF;border-radius:12px;padding:1.25rem;margin-bottom:1rem}
.lbl{font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:#B0ADA6;margin-bottom:8px}
input,select,textarea{width:100%;font-size:14px;color:#1A1916;background:#FAF9F6;border:1px solid #E8E5DF;border-radius:8px;padding:8px 10px;outline:none;font-family:inherit;margin-bottom:8px}
textarea{min-height:64px;resize:vertical;font-style:italic}
input:focus,textarea:focus,select:focus{border-color:#2AABEE}
button{padding:8px 16px;font-size:13px;font-weight:600;border-radius:8px;border:none;cursor:pointer;font-family:inherit;transition:opacity .15s}
button:active{opacity:.75}
.btn-tg{background:#2AABEE;color:#fff}
.btn-dark{background:#1A1916;color:#fff}
.btn-green{background:#27AE60;color:#fff}
.btn-red{background:#E74C3C;color:#fff}
.btn-del{background:transparent;border:1px solid #E8E5DF;color:#E74C3C;font-size:12px;padding:4px 10px;border-radius:6px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot-on{background:#27AE60;box-shadow:0 0 0 3px #EAF7EF}
.dot-off{background:#B0ADA6}
.next-box{background:#EAF6FD;border:1px solid #BDE0F5;border-radius:8px;padding:10px 12px;font-size:13px;font-style:italic;line-height:1.5}
.last-box{background:#EAF7EF;border:1px solid #A8DFC0;border-radius:8px;padding:10px 12px;font-size:13px;font-style:italic;line-height:1.5}
.author{font-size:11px;color:#7A776F;margin-top:3px}
.quote-item{background:#FAF9F6;border:1px solid #E8E5DF;border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.qt{font-size:13px;font-style:italic;line-height:1.5;flex:1}
.qa{font-size:11px;color:#B0ADA6;margin-top:2px}
.muted{font-size:12px;color:#B0ADA6}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:#1A1916;color:#fff;padding:9px 18px;border-radius:999px;font-size:13px;opacity:0;pointer-events:none;transition:all .2s;white-space:nowrap;z-index:999}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
#toast.green{background:#27AE60}#toast.red{background:#E74C3C}
</style>
</head>
<body>
<div class="wrap">
  <h1>Quote Reminder</h1>
  <p class="sub">Running 24/7 · Reminders sent via Telegram</p>
  <div class="grid">

    <!-- LEFT -->
    <div>
      <div class="card">
        <div class="lbl">Telegram Setup</div>
        <input id="token" placeholder="Bot token" />
        <input id="chat_id" placeholder="Chat ID" />
        <button class="btn-tg" onclick="saveAndTest()">Save &amp; Test</button>
        <div id="testMsg" class="muted" style="margin-top:4px"></div>
      </div>

      <div class="card">
        <div class="lbl">Add a Quote</div>
        <textarea id="qtext" placeholder="Type your quote..."></textarea>
        <input id="qauthor" placeholder="Author (optional)" />
        <button class="btn-dark" onclick="addQuote()">Save Quote</button>
      </div>

      <div class="card">
        <div class="lbl">Reminder Schedule</div>
        <select id="interval" style="margin-bottom:12px">
          <option value="1">Every 1 min</option>
          <option value="5">Every 5 min</option>
          <option value="10">Every 10 min</option>
          <option value="15">Every 15 min</option>
          <option value="30">Every 30 min</option>
          <option value="60" selected>Every 1 hour</option>
          <option value="120">Every 2 hours</option>
          <option value="360">Every 6 hours</option>
        </select>
        <div class="row">
          <button class="btn-green" id="startBtn" onclick="startTimer()">▶ Start</button>
          <button class="btn-red" id="stopBtn" onclick="stopTimer()" style="display:none">■ Stop</button>
          <span class="muted" id="timerStatus">Not running</span>
        </div>
      </div>
    </div>

    <!-- RIGHT -->
    <div>
      <div class="card">
        <div class="lbl">Status</div>
        <div style="margin-bottom:12px">
          <span class="dot dot-off" id="dot"></span>
          <span id="statusText" style="font-size:13px;color:#7A776F">Not running</span>
        </div>
        <div class="lbl">Sending Next</div>
        <div class="next-box" id="nextQuote">—</div>
        <div class="author" id="nextAuthor"></div>
        <div class="lbl" style="margin-top:12px">Last Sent</div>
        <div class="last-box" id="lastSent" style="display:none"></div>
        <div class="author" id="lastAuthor"></div>
      </div>

      <div class="card">
        <div class="lbl">Saved Quotes (<span id="qcount">0</span>)</div>
        <div id="quotesList"><p class="muted">No quotes yet.</p></div>
      </div>
    </div>

  </div>
</div>
<div id="toast"></div>
<script>
function toast(msg, type='') {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'show ' + type;
  clearTimeout(el._t); el._t = setTimeout(() => el.className='', 2800);
}

async function api(path, body) {
  const res = await fetch(path, body ? {
    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)
  } : {});
  return res.json();
}

function esc(s){ return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

async function saveAndTest() {
  const token   = document.getElementById('token').value.trim();
  const chat_id = document.getElementById('chat_id').value.trim();
  if (!token || !chat_id) { toast('Enter token & chat ID first','red'); return; }
  const msg = document.getElementById('testMsg');
  msg.textContent = 'Saving...'; msg.style.color='#B0ADA6';
  await api('/api/config', {token, chat_id});
  msg.textContent = 'Testing...';
  const r = await api('/api/test');
  if (r.ok) { msg.textContent='✓ Connected! Check Telegram.'; msg.style.color='#27AE60'; toast('Connected!','green'); }
  else       { msg.textContent='✗ ' + r.error; msg.style.color='#E74C3C'; toast('Error: '+r.error,'red'); }
}

async function addQuote() {
  const text   = document.getElementById('qtext').value.trim();
  const author = document.getElementById('qauthor').value.trim();
  if (!text) { toast('Enter a quote first','red'); return; }
  await api('/api/quotes/add', {text, author});
  document.getElementById('qtext').value   = '';
  document.getElementById('qauthor').value = '';
  toast('Quote saved!','green');
  loadQuotes();
}

async function deleteQuote(id) {
  await api('/api/quotes/delete', {id});
  toast('Deleted'); loadQuotes();
}

async function startTimer() {
  const token   = document.getElementById('token').value.trim();
  const chat_id = document.getElementById('chat_id').value.trim();
  const interval = document.getElementById('interval').value;
  if (!token || !chat_id) { toast('Enter token & chat ID first','red'); return; }
  await api('/api/config', {token, chat_id, interval});
  const r = await api('/api/start');
  if (r.ok) { toast('Reminders started!','green'); pollStatus(); }
  else { toast('Error: ' + r.error,'red'); document.getElementById('timerStatus').textContent = r.error; }
}

async function stopTimer() {
  await api('/api/stop');
  toast('Reminders stopped'); pollStatus();
}

async function loadQuotes() {
  const r = await api('/api/quotes');
  const list = document.getElementById('quotesList');
  document.getElementById('qcount').textContent = r.quotes.length;
  if (!r.quotes.length) { list.innerHTML='<p class="muted">No quotes yet.</p>'; return; }
  list.innerHTML = r.quotes.slice().reverse().map(q => `
    <div class="quote-item">
      <div>
        <div class="qt">"${esc(q.text)}"</div>
        ${q.author ? `<div class="qa">— ${esc(q.author)}</div>` : ''}
      </div>
      <button class="btn-del" onclick="deleteQuote('${q.id}')">✕</button>
    </div>`).join('');
}

async function pollStatus() {
  const r = await api('/api/status');
  document.getElementById('dot').className       = 'dot ' + (r.running ? 'dot-on' : 'dot-off');
  document.getElementById('statusText').textContent = r.running ? 'Running' : 'Not running';
  document.getElementById('startBtn').style.display = r.running ? 'none' : '';
  document.getElementById('stopBtn').style.display  = r.running ? '' : 'none';
  if (r.running && r.next_in !== null) {
    const m = Math.floor(r.next_in/60), s = r.next_in%60;
    document.getElementById('timerStatus').textContent = `Next in ${m}:${String(s).padStart(2,'0')}`;
  } else {
    document.getElementById('timerStatus').textContent = r.running ? 'Running...' : 'Not running';
  }
  if (r.next_quote) {
    document.getElementById('nextQuote').textContent  = '"'+r.next_quote.text+'"';
    document.getElementById('nextAuthor').textContent = r.next_quote.author ? '— '+r.next_quote.author : '';
  } else {
    document.getElementById('nextQuote').textContent  = r.running ? 'Picking...' : '—';
    document.getElementById('nextAuthor').textContent = '';
  }
  const ls = document.getElementById('lastSent');
  if (r.last_sent) {
    ls.style.display = ''; ls.textContent = '"'+r.last_sent.text+'"';
    document.getElementById('lastAuthor').textContent = r.last_sent.author ? '— '+r.last_sent.author : '';
  } else { ls.style.display='none'; }
  if (r.interval) document.getElementById('interval').value = r.interval;
}

async function loadConfig() {
  const r = await api('/api/config/get');
  if (r.token)    document.getElementById('token').value    = r.token;
  if (r.chat_id)  document.getElementById('chat_id').value  = r.chat_id;
  if (r.interval) document.getElementById('interval').value = r.interval;
}

loadConfig(); loadQuotes(); pollStatus();
setInterval(pollStatus, 2000);
</script>
</body>
</html>"""

# ── API Routes ────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/config", methods=["POST"])
def api_config():
    body = request.json
    for k in ("token","chat_id","interval"):
        if k in body:
            set_config(k, body[k])
    return jsonify({"ok": True})

@app.route("/api/config/get")
def api_config_get():
    return jsonify(get_config())

@app.route("/api/test")
def api_test():
    cfg = get_config()
    try:
        send_telegram(cfg["token"], cfg["chat_id"],
                      "👋 Quote Reminder connected! Running 24/7 on the cloud.")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/quotes")
def api_quotes():
    return jsonify({"quotes": get_quotes()})

@app.route("/api/quotes/add", methods=["POST"])
def api_quotes_add():
    body = request.json
    qid  = str(int(time.time() * 1000))
    add_quote(body["text"], body.get("author",""), qid)
    if state["running"]:
        pick_next()
    return jsonify({"ok": True})

@app.route("/api/quotes/delete", methods=["POST"])
def api_quotes_delete():
    delete_quote(request.json.get("id"))
    if state["running"]:
        pick_next()
    return jsonify({"ok": True})

@app.route("/api/start", methods=["POST"])
def api_start():
    cfg = get_config()
    if not cfg.get("token") or not cfg.get("chat_id"):
        return jsonify({"ok": False, "error": "Save token & chat ID first"})
    if not get_quotes():
        return jsonify({"ok": False, "error": "Add at least one quote first"})
    set_config("running", "true")
    start_reminder()
    return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    set_config("running", "false")
    stop_reminder()
    return jsonify({"ok": True})

@app.route("/api/status")
def api_status():
    cfg     = get_config()
    next_in = max(0, int(state["next_time"] - time.time())) if state["next_time"] else None
    return jsonify({
        "running":    state["running"],
        "next_in":    next_in,
        "next_quote": state.get("next_quote"),
        "last_sent":  state.get("last_sent"),
        "interval":   cfg.get("interval", "60"),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
