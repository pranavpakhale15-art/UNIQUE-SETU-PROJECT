# Unique SETU frontend

This React/Vite application uses the FastAPI backend in `../backend`. Setup,
environment variables, MongoDB configuration, and API routes are documented in
the repository [README](../README.md) and
[frontend integration guide](../backend/docs/FRONTEND_INTEGRATION.md).

Run the backend from `backend/` and the frontend from this directory:

```powershell
npm install
npm run dev
```

Local development defaults to `http://127.0.0.1:8000/api/v1`; set
`VITE_API_BASE_URL` in `.env.local` to use another local backend URL. Production
builds use the same-origin `/api/v1` route so Vercel's `/api/:path*` rewrite
proxies requests and cookie-based authentication stays on the frontend origin.
Set the Vercel `VITE_API_BASE_URL` project variable to `/api/v1` (not the
backend's absolute URL) and redeploy; production builds use the proxy path even
if an old absolute value is still present.
