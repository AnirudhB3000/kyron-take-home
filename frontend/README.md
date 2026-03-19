# Frontend Setup

This frontend is a React and Vite web app that renders the patient chat experience, slot selection flow, workflow context cards, and the continue-by-phone trigger.

## Prerequisites

- Node.js 20+
- npm
- The backend running locally at `http://localhost:8000`

## Install Dependencies

From the `frontend` directory:

```powershell
npm install
```

## Backend Dependency

The frontend reads its API base URL from:

```text
VITE_API_BASE_URL
```

That value is defined through Vite environment variables in `src/lib/config.js`.

For local development, the frontend falls back to:

```text
http://localhost:8000/api
```

For Vercel production deploys, set:

```text
VITE_API_BASE_URL=https://<your-render-service>.onrender.com/api
```

Before starting the frontend, start the backend server from `backend/`:

```powershell
..\venv\Scripts\python -m uvicorn app.main:app --reload
```

## Start The Frontend Dev Server

From the `frontend` directory:

```powershell
npm run dev
```

The app runs at:

```text
http://localhost:5173
```

The backend already allows the Vite dev origins:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

## Build For Production

From the `frontend` directory:

```powershell
npm run build
```

To preview the production build locally:

```powershell
npm run preview
```

## Verify The Frontend

After both servers are running:

1. Open `http://localhost:5173`
2. Confirm the assistant intro message appears
3. Confirm chat messages send successfully
4. Confirm the app can create a conversation through the backend

If the backend is unavailable, the UI will show degraded status and scheduling requests will fail.

## Run Tests

### Unit Tests

From the `frontend` directory:

```powershell
npm test
```

These run with Vitest in a `jsdom` environment.

### End-To-End Tests

From the `frontend` directory:

```powershell
npm run test:e2e
```

Playwright specs live under `frontend/tests/e2e`.

## Frontend Notes

- The UI is chat-first and backend-driven.
- Intake, provider matching, slot listing, booking, and handoff actions all call backend APIs.
- The chat auto-scrolls to new messages.
- `Enter` sends a message and `Shift+Enter` keeps multi-line input.
- The continue-by-phone action becomes available after the patient phone number is captured.
