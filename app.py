import os, json, random, threading, time, urllib.request, urllib.parse
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

DATA_DIR    = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", ".")
DATA_FILE   = os.path.join(DATA_DIR, "quotes.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

# ── Persistence ─────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_quotes():   return load_json(DATA_FILE,   [])
def get_config():   return load_json(CONFIG_FILE, {"token": "", "chat_id": "", "interval": 60, "running": False})
def save_quotes(q): save_json(DATA_FILE,   q)
def save_config(c): save_json(CONFIG_FILE, c)

# ── Telegram ────────────────────────────────────────────────
def send_telegram(token, chat_id, text):
    url  = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    req  = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())

# ── Background reminder thread ───────────────────────────────
state = {"running": False, "thread": None, "next_time": None, "next_quote": None, "last_sent": None}

def pick_next(quotes):
    if not quotes:
        return None
    q = random.choice(quotes)
    state["next_quote"] = q
    return q

def reminder_loop():
    while state["running"]:
        cfg    = get_config()
        quotes = get_quotes()
        token  = cfg.get("token", "")
        chat_id = cfg.get("chat_id", "")
        interval = int(cfg.get("interval", 60)) * 60

        q = state.get("next_quote") or pick_next(quotes)
        if q and token and chat_id:
            msg = f'💬 "{q["text"]}"'
            if q.get("author"):
                msg += f'\n\n— {q["author"]}'
            try:
                send_telegram(token, chat_id, msg)
                state["last_sent"] = q
            except Exception as e:
                state["last_sent"] = {"text": f"Error: {e}", "author": ""}

        pick_next(get_quotes())
        state["next_time"] = time.time() + interval

        for _ in range(interval):
            if not state["running"]:
                break
            time.sleep(1)

def start_reminder():
    if state["running"]:
        return
    state["running"] = True
    pick_next(get_quotes())
    t = threading.Thread(target=reminder_loop, daemon=True)
    state["thread"] = t
    t.start()

def stop_reminder():
    state["running"]    = False
    state["next_time"]  = None
    state["next_quote"] = None
    state["thread"]     = None

# Auto-resume if config says running
cfg0 = get_config()
if cfg0.get("running") and cfg0.get("token") and cfg0.get("chat_id") and get_quotes():
    start_reminder()

# ── HTML UI ─────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" /><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Quote Reminder</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',sans-serif;background:#FAF9F6;color:#1A1916;padding:2rem 1rem 4rem;min-height:100vh}
.wrap{max-width:720px;margin:0 auto}
h1{font-size:22px;font-weight:700;letter-spacing:-0.3px}
.sub{font-size:13px;color:#7A776F;margin-top:4px;margin-bottom:2rem}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:560px){.grid{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid #E8E5DF;border-radius:12px;padding:1.25rem}
.label{font-size:11px;font-weight:600;letter-spacing:.07em;text-transform:uppercase;color:#B0ADA6;margin-bottom:8px}
input,select,textarea{width:100%;font-size:14px;color:#1A1916;background:#FAF9F6;border:1px solid #E8E5DF;border-radius:8px;padding:8px 10px;outline:none;font-family:inherit;margin-bottom:8px}
textarea{min-height:64px;resize:vertical;font-style:italic}
input:focus,textarea:focus,select:focus{border-color:#2AABEE}
button{padding:8px 16px;font-size:13px;font-weight:600;border-radius:8px;border:none;cursor:pointer;font-family:inherit;transition:opacity .15s}
button:active{opacity:.75}
.btn-tg{background:#2AABEE;color:#fff}
.btn-dark{background:#1A1916;color:#fff}
.btn-green{background:#27AE60;color:#fff}
.btn-red{background:#E74C3C;color:#fff}
.btn-ghost{background:transparent;border:1px solid #E8E5DF;color:#E74C3C;font-size:12px;padding:4px 10px}
.status-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px}
.dot-on{background:#27AE60;box-shadow:0 0 0 3px #EAF7EF}
.dot-off{background:#B0ADA6}
.quote-item{background:#FAF9F6;border:1px solid #E8E5DF;border-radius:8px;padding:10px 12px;margin-bottom:6px;display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.quote-body{font-size:13px;font-style:italic;color:#1A1916;line-height:1.5;flex:1}
.quote-author{font-size:11px;color:#B0ADA6;margin-top:2px}
.next-box{background:#EAF6FD;border:1px solid #BDE0F5;border-radius:8px;padding:10px 12px;font-size:13px;font-style:italic;color:#1A1916;line-height:1.5}
.next-author{font-size:11px;color:#7A776F;margin-top:2px}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px}
.muted{font-size:12px;color:#B0ADA6}
.last-sent{background:#EAF7EF;border:1px solid #A8DFC0;border-radius:8px;padding:10px 12px;font-size:13px;font-style:italic;color:#1A1916}
#toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%) translateY(20px);background:#1A1916;color:#fff;padding:9px 18px;border-radius:999px;font-size:13px;opacity:0;pointer-events:none;transition:all .2s;white-space:nowrap}
#toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
#toast.green{background:#27AE60}
#toast.red{background:#E74C3C}
</style>
</head>
<body>
<div class="wrap">
  <h1>Quote Reminder</h1>
  <p class="sub">Running 24/7 on Railway · Reminders via Telegram</p>

  <div class="grid">
    <!-- LEFT -->
    <div>
      <div class="card" style="margin-bottom:1rem">
        <div class="label">Telegram Setup</div>
        <input id="token" type="text" placeholder="Bot token" />
        <input id="chat_id" type="text" placeholder="Chat ID" />
        <button class="btn-tg" onclick="saveConfig()">Save & Test</button>
      </div>

      <div class="card" style="margin-bottom:1rem">
        <div class="label">Add a Quote</div>
        <textarea id="qtext" placeholder="Type your quote..."></textarea>
        <input id="qauthor" type="text" placeholder="Author (optional)" />
        <button class="btn-dark" onclick="addQuote()">Save Quote</button>
      </div>

      <div class="card">
        <div class="label">Reminder Schedule</div>
        <div class="row" style="margin-bottom:10px">
          <select id="interval">
            <option value="1">Every 1 min</option>
            <option value="5">Every 5 min</option>
            <option value="10">Every 10 min</option>
            <option value="15">Every 15 min</option>
            <option value="30">Every 30 min</option>
            <option value="60" selected>Every 1 hour</option>
            <option value="120">Every 2 hours</option>
            <option value="360">Every 6 hours</option>
          </select>
        </div>
        <div class="row">
          <button class="btn-green" id="startBtn" onclick="startTimer()">▶ Start</button>
          <button class="btn-red"   id="stopBtn"  onclick="stopTimer()" style="display:none">■ Stop</button>
          <span class="muted" id="timerStatus">Not running</span>
        </div>
      </div>
    </div>

    <!-- RIGHT -->
    <div>
      <div class="card" style="margin-bottom:1rem">
        <div class="label">Status</div>
        <div style="margin-bottom:10px">
          <span class="status-dot dot-off" id="statusDot"></span>
          <span id="statusText" style="font-size:13px;color:#7A776F">Not running</span>
        </div>
        <div class="label" style="margin-top:8px">Sending Next</div>
        <div class="next-box" id="nextQuote">—</div>
        <div class="next-author" id="nextAuthor"></div>
        <div class="label" style="margin-top:12px">Last Sent</div>
        <div class="last-sent" id="lastSent" style="display:none"></div>
        <div class="muted" id="lastAuthor"></div>
      </div>

      <div class="card">
        <div class="label">Saved Quotes (<span id="qcount">0</span>)</div>
        <div id="quotesList"><p class="muted">No quotes yet.</p></div>
      </div>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
let pollInterval;

async function api(path, body) {
  const res = await fetch(path, body ? {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)
  } : {});
  return res.json();
}

function toast(msg, type='') {
  const el = document.getElementById('toast');
  el.textContent = msg; el.className = 'show ' + type;
  clearTimeout(el._t); el._t = setTimeout(() => el.className = '', 2500);
}

async function saveConfig() {
  const token   = document.getElementById('token').value.trim();
  const chat_id = document.getElementById('chat_id').value.trim();
  const interval = document.getElementById('interval').value;
  if (!token || !chat_id) { toast('Enter token & chat ID', 'red'); return; }
  await api('/api/config', {token, chat_id, interval});
  const r = await api('/api/test');
  if (r.ok) toast('Connected! Check Telegram ✓', 'green');
  else toast('Error: ' + r.error, 'red');
}

async function addQuote() {
  const text   = document.getElementById('qtext').value.trim();
  const author = document.getElementById('qauthor').value.trim();
  if (!text) { toast('Enter a quote first', 'red'); return; }
  await api('/api/quotes/add', {text, author});
  document.getElementById('qtext').value   = '';
  document.getElementById('qauthor').value = '';
  toast('Quote saved!', 'green');
  loadQuotes();
}

async function deleteQuote(id) {
  await api('/api/quotes/delete', {id});
  toast('Deleted');
  loadQuotes();
}

async function startTimer() {
  const interval = document.getElementById('interval').value;
  await api('/api/config', {interval});
  const r = await api('/api/start');
  if (r.ok) { toast('Reminders started!', 'green'); pollStatus(); }
  else toast(r.error, 'red');
}

async function stopTimer() {
  await api('/api/stop');
  toast('Reminders stopped');
  pollStatus();
}

async function loadQuotes() {
  const r = await api('/api/quotes');
  const list = document.getElementById('quotesList');
  document.getElementById('qcount').textContent = r.quotes.length;
  if (!r.quotes.length) {
    list.innerHTML = '<p class="muted">No quotes yet.</p>'; return;
  }
  list.innerHTML = r.quotes.slice().reverse().map(q => `
    <div class="quote-item">
      <div>
        <div class="quote-body">"${esc(q.text)}"</div>
        ${q.author ? `<div class="quote-author">— ${esc(q.author)}</div>` : ''}
      </div>
      <button class="btn-ghost" onclick="deleteQuote('${q.id}')">✕</button>
    </div>
  `).join('');
}

async function pollStatus() {
  const r = await api('/api/status');
  const dot  = document.getElementById('statusDot');
  const text = document.getElementById('statusText');
  const startBtn = document.getElementById('startBtn');
  const stopBtn  = document.getElementById('stopBtn');
  const timerSt  = document.getElementById('timerStatus');

  if (r.running) {
    dot.className = 'status-dot dot-on';
    text.textContent = 'Running';
    startBtn.style.display = 'none';
    stopBtn.style.display  = '';
    const secs = Math.max(0, Math.round(r.next_in));
    const m = Math.floor(secs/60), s = secs%60;
    timerSt.textContent = `Next in ${m}:${String(s).padStart(2,'0')}`;
  } else {
    dot.className = 'status-dot dot-off';
    text.textContent = 'Not running';
    startBtn.style.display = '';
    stopBtn.style.display  = 'none';
    timerSt.textContent = 'Not running';
  }

  if (r.next_quote) {
    document.getElementById('nextQuote').textContent  = '"' + r.next_quote.text + '"';
    document.getElementById('nextAuthor').textContent = r.next_quote.author ? '— ' + r.next_quote.author : '';
  } else {
    document.getElementById('nextQuote').textContent  = '—';
    document.getElementById('nextAuthor').textContent = '';
  }

  if (r.last_sent) {
    const ls = document.getElementById('lastSent');
    ls.style.display = '';
    ls.textContent   = '"' + r.last_sent.text + '"';
    document.getElementById('lastAuthor').textContent = r.last_sent.author ? '— ' + r.last_sent.author : '';
  }

  // Sync interval selector
  if (r.interval) document.getElementById('interval').value = r.interval;
}

async function loadConfig() {
  const r = await api('/api/config/get');
  if (r.token)   document.getElementById('token').value   = r.token;
  if (r.chat_id) document.getElementById('chat_id').value = r.chat_id;
  if (r.interval) document.getElementById('interval').value = r.interval;
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// Init
loadConfig();
loadQuotes();
pollStatus();
pollInterval = setInterval(pollStatus, 2000);
</script>
</body>
</html>"""

# ── Routes ───────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/config", methods=["POST"])
def api_config():
    body = request.json
    cfg  = get_config()
    for k in ("token","chat_id","interval"):
        if k in body:
            cfg[k] = body[k]
    save_config(cfg)
    return jsonify({"ok": True})

@app.route("/api/config/get")
def api_config_get():
    return jsonify(get_config())

@app.route("/api/test")
def api_test():
    cfg = get_config()
    try:
        send_telegram(cfg["token"], cfg["chat_id"], "👋 Quote Reminder connected! Running 24/7 on Railway.")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/api/quotes")
def api_quotes():
    return jsonify({"quotes": get_quotes()})

@app.route("/api/quotes/add", methods=["POST"])
def api_quotes_add():
    body   = request.json
    quotes = get_quotes()
    quotes.append({"text": body["text"], "author": body.get("author",""), "id": str(int(time.time()*1000))})
    save_quotes(quotes)
    if state["running"]:
        pick_next(get_quotes())
    return jsonify({"ok": True})

@app.route("/api/quotes/delete", methods=["POST"])
def api_quotes_delete():
    qid    = request.json.get("id")
    quotes = [q for q in get_quotes() if q.get("id") != qid]
    save_quotes(quotes)
    if state["running"]:
        pick_next(quotes)
    return jsonify({"ok": True})

@app.route("/api/start", methods=["POST"])
def api_start():
    cfg = get_config()
    if not cfg.get("token") or not cfg.get("chat_id"):
        return jsonify({"ok": False, "error": "Set token & chat ID first"})
    if not get_quotes():
        return jsonify({"ok": False, "error": "Add at least one quote first"})
    cfg["running"] = True
    save_config(cfg)
    start_reminder()
    return jsonify({"ok": True})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    cfg = get_config()
    cfg["running"] = False
    save_config(cfg)
    stop_reminder()
    return jsonify({"ok": True})

@app.route("/api/status")
def api_status():
    next_in = max(0, state["next_time"] - time.time()) if state["next_time"] else 0
    cfg = get_config()
    return jsonify({
        "running":    state["running"],
        "next_in":    round(next_in),
        "next_quote": state.get("next_quote"),
        "last_sent":  state.get("last_sent"),
        "interval":   cfg.get("interval", 60),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
