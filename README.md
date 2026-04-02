# Quote Reminder — Railway Deployment

## Files
- `app.py` — Flask web app + Telegram reminder background thread
- `requirements.txt` — Python dependencies
- `Procfile` — Railway start command

## Deploy Steps

### 1. Push to GitHub
Create a new GitHub repository and push these files:
```
git init
git add .
git commit -m "quote reminder"
git remote add origin https://github.com/YOUR_USERNAME/quote-reminder.git
git push -u origin main
```

### 2. Deploy on Railway
1. Go to https://railway.app and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your repository
4. Railway auto-detects Python and deploys

### 3. Add a Volume (for persistent quote storage)
1. In Railway dashboard, click your service
2. Go to **Volumes** tab → **Add Volume**
3. Mount path: `/data`
4. Railway will set `RAILWAY_VOLUME_MOUNT_PATH=/data` automatically

### 4. Open your app
Click the **Public URL** Railway gives you — open it in any browser, even on mobile!

## Usage
1. Paste your Telegram bot token + chat ID → **Save & Test**
2. Add your quotes
3. Set interval → **Start**
4. Runs 24/7, even when your PC is off
