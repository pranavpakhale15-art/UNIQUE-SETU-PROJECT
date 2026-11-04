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

The frontend defaults to `http://127.0.0.1:8000/api/v1`. Set
`VITE_API_BASE_URL` in `.env.local` to use another backend URL.
