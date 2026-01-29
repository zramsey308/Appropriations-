# Deployment Guide

This guide will help you deploy the TX-11 Appropriations Tracker using GitHub Pages (frontend) and Render (backend).

## Quick Start

### Step 1: Deploy Backend to Render

1. Go to [render.com](https://render.com) and sign up/login with your GitHub account
2. Click **New** → **Web Service**
3. Connect your GitHub repository
4. Render will auto-detect the `render.yaml` configuration
5. Click **Create Web Service**
6. Wait for the deployment to complete (first deploy takes a few minutes)
7. Note your backend URL: `https://tx11-appropriations-api.onrender.com`

### Step 2: Enable GitHub Pages (Frontend)

1. Go to your repository on GitHub
2. Click **Settings** → **Pages**
3. Under "Source", select **Deploy from a branch**
4. Select **main** branch and **/ (root)** folder
5. Click **Save**
6. Wait a few minutes for deployment
7. Your site will be available at: `https://[username].github.io/Appropriations-/`

### Step 3: Update API URL (if needed)

If your Render backend URL is different from the default, update these files:

- `submit.html` - Line 624
- `frontend.html` - Line 1186

Change:
```javascript
: 'https://tx11-appropriations-api.onrender.com';
```

To your actual Render URL.

## URLs After Deployment

- **Landing Page**: `https://[username].github.io/Appropriations-/`
- **Submit Form** (share this with requesters): `https://[username].github.io/Appropriations-/submit.html`
- **Dashboard**: `https://[username].github.io/Appropriations-/frontend.html`
- **API**: `https://tx11-appropriations-api.onrender.com`

## Important Notes

### Free Tier Limitations

**Render Free Tier:**
- Service spins down after 15 minutes of inactivity
- First request after sleep takes ~30 seconds to wake up
- 750 hours/month of runtime

**GitHub Pages:**
- Completely free for public repositories
- No limitations for static hosting

### Custom Domain (Optional)

To use a custom domain with GitHub Pages:
1. Go to **Settings** → **Pages**
2. Add your custom domain
3. Update DNS records as instructed
4. Update CORS origins in `app/main.py` if using a custom domain

## Local Development

To run locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
alembic upgrade head
python -m app.seed_accounts

# Start server
python run.py
```

Then open `submit.html` or `frontend.html` in your browser.
