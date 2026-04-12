# GateSmart — Railway Deployment

## Live Production URLs

Backend:  <https://backend-production-15e941.up.railway.app>
Frontend: <https://frontend-production-de916.up.railway.app>
Health:   <https://backend-production-15e941.up.railway.app/health>
API Docs: <https://backend-production-15e941.up.railway.app/docs>

Last deployed: April 2026

## Services

Create three services in Railway:

1. **backend** — connect to `/backend` directory
2. **frontend** — connect to `/frontend` directory
3. **Redis** — add via Railway Redis plugin (auto-provides `REDIS_URL`)

## Backend Environment Variables

| Variable | Value |
| --- | --- |
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `RACING_API_USERNAME` | TheRacingAPI username |
| `RACING_API_PASSWORD` | TheRacingAPI password |
| `TRACKSENSE_WEBHOOK_SECRET` | Shared HMAC secret with TrackSense |
| `REDIS_URL` | Auto-set by Railway Redis plugin |
| `REDIS_PASSWORD` | Auto-set by Railway Redis plugin |
| `CORS_ORIGINS` | Set to your frontend Railway URL after deploy |
| `ENVIRONMENT` | `production` |
| `SECRET_KEY` | Generate: `openssl rand -hex 32` |

## Frontend Environment Variables

| Variable | Value |
| --- | --- |
| `VITE_API_URL` | Set to your backend Railway URL |
| `VITE_GA_MEASUREMENT_ID` | `G-K6G74W27FD` |

## Deployment Steps

1. Push to GitHub (`wpf002/gate_smart`)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add **backend** service → select `/backend` folder
4. Add **frontend** service → select `/frontend` folder
5. Add Redis plugin (Railway Dashboard → New → Database → Redis)
6. Set all environment variables in the Railway dashboard
7. Deploy both services
8. Copy the frontend Railway URL → set as `CORS_ORIGINS` in backend
9. Copy the backend Railway URL → set as `VITE_API_URL` in frontend
10. Redeploy both services

## Health Check

```text
GET {backend_url}/health
→ { "status": "ok", "environment": "production", "redis": "connected", "version": "1.0.0" }
```

## Notes

- Railway auto-assigns `PORT` — both Dockerfiles use `${PORT:-default}` to handle this
- Redis plugin sets `REDIS_URL` automatically; set `REDIS_PASSWORD` to match if using auth
- The North America racing data requires the NA add-on on your TheRacingAPI account
- Rate limits: 10/min on AI analysis, 20/min on debrief, 30/min on chat
