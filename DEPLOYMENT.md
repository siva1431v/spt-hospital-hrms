# SPT Hospital HRMS — Production Deployment Guide

This guide provides step-by-step instructions for deploying the **SPT Hospital HRMS** full-stack application.

---

## 🏗️ Architecture Overview

| Component | Technology | Default Port | Production Target |
| :--- | :--- | :--- | :--- |
| **Frontend** | Next.js 16 (App Router, Tailwind CSS, TypeScript) | 3000 | **Vercel** / Docker / Railway |
| **Backend** | FastAPI, Python 3.12/3.13, Uvicorn, Async SQLAlchemy | 8000 | **Render** / Railway / Docker |
| **Database** | SQLite (`spt_hrms.db`) or PostgreSQL 16 | 5432 (PG) | Persistent Disk (SQLite) or Managed PostgreSQL |

---

## 🚀 Option 1: Recommended Cloud Deployment (Vercel + Render)

This is the fastest, lowest-cost production setup.

### Step 1: Deploy Backend to Render

1. Log in to [Render](https://dashboard.render.com/).
2. Click **New +** → **Blueprint** and connect your GitHub repository, or create a **Web Service**:
   - **Name**: `spt-hospital-backend`
   - **Root Directory**: `backend`
   - **Runtime**: `Docker` (or `Python 3`)
   - **Health Check Path**: `/health`
3. If deploying manually as a Web Service, configure these **Environment Variables**:
   - `PORT`: `8000`
   - `JWT_SECRET`: `$(openssl rand -hex 32)` *(generate a strong 64+ char secret)*
   - `CORS_ORIGINS`: `http://localhost:3000,https://*.vercel.app`
   - `CORS_ORIGIN_REGEX`: `^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app|.*\.onrender\.com)(:\d+)?$`
   - `DATABASE_URL`:
     - *Using PostgreSQL*: Link a Render PostgreSQL instance (or paste connection string).
     - *Using SQLite*: Keep default (`sqlite+aiosqlite:///spt_hrms.db`) and attach a Persistent Disk mounted at `/app/uploads` and `/app/spt_hrms.db`.
4. Deploy the service. Once built, verify by opening `https://<YOUR-RENDER-BACKEND-URL>/health` in your browser. You should see:
   ```json
   {"status":"healthy","app":"SPT Hospital HRMS","version":"1.0.0"}
   ```

---

### Step 2: Deploy Frontend to Vercel

1. Log in to [Vercel](https://vercel.com/) and click **Add New...** → **Project**.
2. Select your repository.
3. **IMPORTANT — Root Directory Setting**:
   - In the configuration screen, click **Edit** next to **Root Directory**.
   - Select or type: `frontend`.
   - Leave Framework Preset as **Next.js**.
4. **Environment Variables**:
   - Add the following variable:
     - **Key**: `NEXT_PUBLIC_API_URL`
     - **Value**: `https://<YOUR-RENDER-BACKEND-URL>/api/v1`
       *(e.g., `https://spt-hospital-backend.onrender.com/api/v1`)*
     > **Note**: Even if you omit `/api/v1` or add a trailing slash, the frontend API client now automatically normalizes the URL to end with `/api/v1`.
   - Add:
     - **Key**: `NEXT_PUBLIC_APP_NAME`
     - **Value**: `SPT Hospital HRMS`
5. Click **Deploy**.
6. Once deployed, open your Vercel URL (e.g., `https://spt-hospital-hrms.vercel.app/login`).

---

## 🌐 Resolving the "Network Error in the Website"

If your Vercel deployment displays "network error":

1. **Check `NEXT_PUBLIC_API_URL` in Vercel Settings**:
   - Navigate to **Project Settings** → **Environment Variables** in Vercel.
   - Ensure `NEXT_PUBLIC_API_URL` points to your **public backend URL** (e.g., `https://spt-hospital-backend.onrender.com/api/v1`).
   - If it points to `http://localhost:8000`, the browser is trying to connect to the user's local computer instead of your cloud backend.
   - After updating environment variables in Vercel, you **must Redeploy** (Deployments → Three Dots → Redeploy) for Next.js to bake in the new public variable.
2. **CORS is Pre-Configured**:
   - The backend includes automatic CORS regex matching for all `*.vercel.app` domains (`CORS_ORIGIN_REGEX=^https?://(localhost|127\.0\.0\.1|.*\.vercel\.app)(:\d+)?$`).
   - If using a custom production domain (e.g., `https://hrms.spthospital.com`), add it to `CORS_ORIGINS` in your backend environment variables.

---

## 🐳 Option 2: 1-Click Docker Compose Deployment

Run the entire full-stack application (PostgreSQL, Redis, Backend, and Frontend) locally or on a single VPS (DigitalOcean, AWS EC2, Hetzner):

```bash
# 1. Clone the repository
git clone https://github.com/your-org/spt-hospital-hrms.git
cd spt-hospital-hrms

# 2. Configure environment variables (optional, defaults are pre-configured)
cp .env.example .env

# 3. Start all services
docker compose up -d --build
```

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **Backend Health Check**: http://localhost:8000/health
- **PostgreSQL**: `localhost:5432` (`spt_user` / `spt_password`, database `spt_hrms`)

To stop:
```bash
docker compose down
```

---

## 🗄️ Option 3: Migrating SQLite to PostgreSQL

If you started with the pre-populated SQLite database (`backend/spt_hrms.db`) and want to migrate all historical records (employees, shifts, attendance, payroll) to managed PostgreSQL:

```bash
cd backend
source venv/bin/activate

# Run data migration script
python -m scripts.migrate_sqlite_to_postgres \
  --sqlite spt_hrms.db \
  --postgres "postgresql://USER:PASSWORD@HOST:PORT/DBNAME"
```

The script:
1. Validates schema and reflects all SQLAlchemy models.
2. Transfers all records table-by-table in foreign-key dependency order.
3. Automatically converts SQLite integer booleans (`0`/`1`) to native Postgres booleans.
4. Updates PostgreSQL auto-increment sequences (`pg_get_serial_sequence`).
5. Prints row-count verification.

---

## 🔑 Initial Default Credentials

Once the database is initialized (either via `start.sh` or Docker):

| Role | Username | Email | Password |
| :--- | :--- | :--- | :--- |
| **Super Admin** | `admin` | `admin@spthospital.com` | `Admin@123` |
| **HR Admin** | `hr` | `hr@spthospital.com` | `HR@123` |

> ⚠️ **Security Warning**: Log in immediately upon deployment and change default administrator passwords via **Settings** → **Users**.
