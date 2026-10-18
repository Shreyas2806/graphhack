# GraphMind Production Deployment Guide

This guide walks you through deploying **GraphMind**:
1. **Frontend**: Next.js deployed on **Vercel**
2. **Database**: FalkorDB deployed on **Railway** or **Render** (with persistent disk)
3. **Backend**: FastAPI deployed on **Railway** or **Render** (using Dockerfile)

---

## Architecture Overview

```mermaid
graph LR
    User([User Browser]) -->|HTTPS| Vercel[Next.js on Vercel]
    Vercel -->|REST API (HTTPS)| Backend[FastAPI on Railway / Render]
    Backend -->|Private Network: 6379| FalkorDB[(FalkorDB + Volume)]
    Backend -->|Google GenAI API| Gemini[Google Gemini]
```

---

## Option A: Railway (Fastest for Docker & Private Networking)

Railway provides private networking between containers out-of-the-box, making FalkorDB + FastAPI connection effortless.

### Step 1: Deploy FalkorDB on Railway
1. Go to [Railway.app](https://railway.app/) and create a new project.
2. Click **+ New Service** → **Docker Image**.
3. Enter image name: `falkordb/falkordb:latest` and click deploy.
4. Go to service **Settings**:
   - Set service name to: `falkordb`
   - Under **Networking**, click **Enable Private Networking** (Railway assigns a private domain, typically `falkordb.railway.internal:6379`).
5. (Recommended for persistence): Under **Volumes**, click **Add Volume** and mount it to `/var/lib/falkordb/data`.

### Step 2: Deploy Backend on Railway
1. In the same Railway project, click **+ New Service** → **GitHub Repo**.
2. Select `Shreyas2806/graphhack`.
3. In service **Settings**:
   - Set **Root Directory** to: `/backend`
   - Set **Dockerfile Path** to: `Dockerfile`
4. Under **Variables**, add:
   ```env
   GEMINI_API_KEY=<your_gemini_api_key>
   GEMINI_MODEL=gemini-2.5-flash
   FALKORDB_HOST=falkordb.railway.internal
   FALKORDB_PORT=6379
   FALKORDB_GRAPH=graphmind
   ENABLE_CACHE=true
   ```
5. Under **Networking**, click **Generate Domain** (e.g. `https://graphmind-backend-production.up.railway.app`).
6. Test in your browser: `https://<your-backend-domain>/health` should return `{"status": "ok", ...}`.

---

## Option B: Render (Blueprint Infrastructure-as-Code)

You can deploy directly to [Render](https://render.com/) using the included `render.yaml` blueprint:

1. Push your code to GitHub.
2. In the Render Dashboard, click **New** → **Blueprint**.
3. Connect `Shreyas2806/graphhack`.
4. Render will detect `render.yaml` and configure:
   - `graphmind-backend` (Docker web service)
   - `graphmind-falkordb` (Private service with 10GB persistent disk)
5. Fill in the prompted secret:
   - `GEMINI_API_KEY`: your Gemini API key
6. Click **Apply**.
7. Once deployed, copy your backend URL: `https://graphmind-backend.onrender.com`.

---

## Deploying Frontend on Vercel

Once your backend is live and healthy, deploy the Next.js frontend:

1. Go to [Vercel](https://vercel.com/) and sign in with GitHub.
2. Click **Add New...** → **Project**.
3. Import the repository: `Shreyas2806/graphhack`.
4. In the configuration screen:
   - **Framework Preset**: `Next.js`
   - **Root Directory**: Click *Edit* and select `frontend`
5. Expand **Environment Variables** and add:
   ```env
   NEXT_PUBLIC_API_BASE_URL=https://<your-backend-railway-or-render-url>
   ```
   *(Important: Do not include a trailing slash, e.g. `https://graphmind-backend.up.railway.app`)*
6. Click **Deploy**.

---

## Verification Checklist

Once both services are deployed:

1. **Verify Backend Health**:
   Visit `https://<backend-url>/health`:
   ```json
   {
     "status": "ok",
     "falkordb": { "ok": true },
     "gemini": { "ok": true }
   }
   ```
2. **Verify Frontend**:
   Open your Vercel deployment URL (e.g. `https://graphhack.vercel.app`):
   - Check that the dashboard shows `System Status: Online`.
   - Go to `/memory`, submit a test statement: *"GraphMind is deployed on Vercel and Railway."*
   - Go to `/chat`, ask: *"Where is GraphMind deployed?"*
   - Verify the multi-agent trace and verification badge.
