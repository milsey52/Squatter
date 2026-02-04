# Railway Deployment Guide for MonopolyPerth

## Prerequisites
- GitHub account
- Railway account (sign up at https://railway.app)
- This repository pushed to GitHub

## Deployment Steps

### 1. Create a Railway Project

1. Go to https://railway.app and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Select your MonopolyPerth repository
5. Railway will auto-detect it's a Python project

### 2. Add PostgreSQL Database

1. In your Railway project, click "New" → "Database" → "Add PostgreSQL"
2. Railway will automatically create a `DATABASE_URL` environment variable
3. Your app will automatically connect to it (already configured in `app/db.py`)

### 3. Configure Environment Variables

In Railway project settings, add these environment variables:

**Required:**
- `DATABASE_URL` - (Auto-created by Railway PostgreSQL)
- `PORT` - (Auto-created by Railway)

**Optional:**
- `CORS_ORIGINS` - Add your Railway app URL once deployed
  - Example: `https://monopolyperth.up.railway.app`
  - You can add multiple: `https://app1.railway.app,https://app2.railway.app`
- `ENVIRONMENT` - Set to `production`

### 4. Run Database Migrations

After first deployment, run migrations in Railway terminal:
```bash
alembic upgrade head
```

Or use Railway's "Run Command" feature to execute this.

### 5. Update Frontend Environment Variable

Once your backend is deployed:

1. Get your Railway backend URL (e.g., `https://monopolyperth-production.up.railway.app`)
2. In Railway, add environment variable:
   - `VITE_API_BASE` = your backend URL
3. Railway will rebuild automatically

### 6. Update CORS

Add your Railway URL to CORS_ORIGINS:
```
CORS_ORIGINS=https://your-app.up.railway.app,http://localhost:5173
```

## Project Structure

```
MonopolyPerth/
├── main.py              # FastAPI app entry point
├── requirements.txt     # Python dependencies
├── Procfile            # Railway start command
├── railway.json        # Railway configuration
├── nixpacks.toml       # Build configuration
├── app/                # Backend API
│   ├── db.py          # Database configuration
│   ├── models.py      # SQLAlchemy models
│   └── api/           # API routes
├── web-client/         # React frontend
│   ├── src/           # React source
│   ├── dist/          # Built frontend (served by FastAPI)
│   └── package.json   # Node dependencies
└── alembic/           # Database migrations
```

## How It Works

1. Railway detects Python project and installs dependencies from `requirements.txt`
2. Builds React frontend with `npm run build` in web-client/
3. FastAPI serves the built React app from `web-client/dist/`
4. Single service handles both frontend and backend
5. PostgreSQL database runs as separate service

## Monitoring & Logs

- View logs in Railway dashboard
- Monitor resource usage
- Set up custom domains in Railway settings

## Custom Domain (Optional)

1. In Railway project settings, click "Settings" → "Domains"
2. Click "Generate Domain" for a free Railway subdomain
3. Or add your custom domain and configure DNS

## Estimated Costs

- **Hobby Plan**: $5/month (includes $5 credit)
- **Developer Plan**: $20/month (includes $20 credit)
- Typical usage for this app: ~$3-8/month depending on traffic

## Troubleshooting

**Build fails:**
- Check Railway build logs
- Verify all dependencies in `requirements.txt` and `package.json`

**Database connection errors:**
- Ensure `DATABASE_URL` environment variable is set
- Check PostgreSQL service is running

**CORS errors:**
- Add your Railway domain to `CORS_ORIGINS`
- Restart the service

**Frontend can't reach backend:**
- Update `VITE_API_BASE` in Railway environment variables
- Rebuild the frontend

## Rolling Back

Railway keeps deployment history:
1. Go to "Deployments" tab
2. Click on a previous successful deployment
3. Click "Rollback to this version"

## Local Development

```bash
# Backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd web-client
npm install
npm run dev
```

Set local environment variables:
- `DATABASE_URL=postgresql://localhost/monopolyperth`
- `CORS_ORIGINS=http://localhost:5173`

---

Need help? Check Railway docs: https://docs.railway.app
