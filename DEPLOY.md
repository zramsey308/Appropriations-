# Deployment Guide

This guide will help you deploy the TX-11 Appropriations Tracker with:
- **GitHub Pages** - Frontend (free)
- **Render** - Backend API (free tier)
- **Supabase** - PostgreSQL Database (free tier)
- **Google Sheets** - Backup/Export (optional, free)

---

## Step 1: Set Up Persistent Database (Required)

### Option A (Recommended): Render Managed PostgreSQL (`atlas-ops-db`)

This repo now includes a Render Blueprint database named `atlas-ops-db` in `render.yaml`.

When deployed via Blueprint:
- Render provisions `atlas-ops-db`
- `DATABASE_URL` is injected automatically from that DB connection string
- submissions persist across deploys/restarts (no re-upload needed)

### Option B: External Supabase PostgreSQL

1. Go to [supabase.com](https://supabase.com) and sign up/login
2. Click **New Project**
3. Enter project details:
   - Name: `tx11-appropriations`
   - Database Password: (save this!)
   - Region: Choose closest to your users
4. Wait for project to be created
5. Go to **Settings** → **Database**
6. Under "Connection string", copy the **URI** (starts with `postgresql://`)
7. Replace `[YOUR-PASSWORD]` in the URI with your database password

If using Supabase manually, your DATABASE_URL will look like:
```
postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
```

---

## Step 2: Set Up Google Sheets Backup (Optional but Recommended)

### Create a Google Cloud Service Account:

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a new project or select existing
3. Enable the **Google Sheets API** and **Google Drive API**:
   - Go to APIs & Services → Library
   - Search for and enable both APIs
4. Create a Service Account:
   - Go to APIs & Services → Credentials
   - Click **Create Credentials** → **Service Account**
   - Name it `appropriations-backup`
   - Click **Done**
5. Create a key for the service account:
   - Click on the service account you created
   - Go to **Keys** tab → **Add Key** → **Create new key**
   - Choose **JSON** and download the file
6. Copy the entire contents of the JSON file (you'll need this later)

### Create a Google Sheet:

1. Create a new Google Sheet
2. Name it "TX-11 Appropriations Backup"
3. Share the sheet with your service account email (found in the JSON file under `client_email`)
   - Give it **Editor** access
4. Copy the Sheet ID from the URL:
   - URL: `https://docs.google.com/spreadsheets/d/[SHEET_ID]/edit`
   - Copy the `[SHEET_ID]` part

---

## Step 3: Deploy Backend to Render

### If using Blueprint (recommended)
1. In Render, choose **New** → **Blueprint** and select this repository.
2. Confirm both resources are detected:
   - `atlas-ops-db` (PostgreSQL)
   - `tx11-appropriations-api` (Web Service)
3. Deploy. No manual `DATABASE_URL` entry is required.

### If creating Web Service manually

1. Go to [render.com](https://render.com) and sign up with GitHub
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Configure the service:
   - **Name**: `tx11-appropriations-api`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `alembic upgrade head && python -c "from app.seed_accounts import seed_accounts; seed_accounts()" && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

5. Add Environment Variables (click **Add Environment Variable**):

   | Key | Value |
   |-----|-------|
   | `DATABASE_URL` | DB connection string (from `atlas-ops-db` or Supabase) |
   | `GOOGLE_SHEETS_ENABLED` | `true` (or `false` to disable) |
   | `GOOGLE_SHEETS_ID` | Your Google Sheet ID from Step 2 |
   | `GOOGLE_SERVICE_ACCOUNT_JSON` | The entire JSON contents from Step 2 (paste as one line) |

6. Click **Create Web Service**
7. Wait for deployment (first deploy takes a few minutes)
8. Note your API URL: `https://tx11-appropriations-api.onrender.com`

---

## Step 4: Update Frontend API URL (if different)

If your Render URL is different from the default, update these files:

**submit.html** (around line 625):
```javascript
: 'https://YOUR-RENDER-URL.onrender.com';
```

**frontend.html** (around line 1188):
```javascript
: 'https://YOUR-RENDER-URL.onrender.com';
```

---

## Step 5: Enable GitHub Pages

1. Push all changes to your GitHub repository
2. Go to your repository on GitHub
3. Click **Settings** → **Pages**
4. Under "Source", select **Deploy from a branch**
5. Select **main** branch and **/ (root)** folder
6. Click **Save**
7. Wait a few minutes for deployment

---

## Your URLs After Deployment

| Page | URL |
|------|-----|
| **Landing Page** | `https://[username].github.io/Appropriations-/` |
| **Submit Form** (share this!) | `https://[username].github.io/Appropriations-/submit.html` |
| **Dashboard** | `https://[username].github.io/Appropriations-/frontend.html` |
| **API** | `https://tx11-appropriations-api.onrender.com` |
| **Google Sheet Backup** | Your Google Sheet URL |

---

## How It Works

1. **User submits a request** via the submit form
2. **Data is saved to PostgreSQL** (Render `atlas-ops-db` or Supabase)
3. **Data is backed up to Google Sheets** (if enabled)
4. **Dashboard shows all submissions** from PostgreSQL

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string (Render `atlas-ops-db` or Supabase) |
| `GOOGLE_SHEETS_ENABLED` | No | Set to `true` to enable Google Sheets backup |
| `GOOGLE_SHEETS_ID` | No* | Google Sheet ID (required if backup enabled) |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No* | Service account JSON (required if backup enabled) |

---

## Troubleshooting

### "Failed to connect to server" error
- Check if Render service is running (free tier sleeps after 15 min of inactivity)
- First request after sleep takes ~30 seconds

### Google Sheets not updating
- Verify service account has Editor access to the sheet
- Check Render logs for any errors
- Ensure `GOOGLE_SHEETS_ENABLED` is set to `true`

### Database errors
- Verify DATABASE_URL is correct
- Make sure you replaced `[YOUR-PASSWORD]` with actual password
- Check Supabase dashboard for connection issues

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set up local .env file
echo 'DATABASE_URL=sqlite:///./data/appropriations.db' > .env

# Initialize database
alembic upgrade head
python -m app.seed_accounts

# Start server
python run.py
```

Then open `http://localhost:8080` in your browser.
