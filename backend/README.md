# Backend Setup

This backend is a FastAPI server that owns conversation state, scheduling workflow logic, provider matching, booking, notifications, and chat-to-voice handoff behavior.

## Prerequisites

- Python 3.12
- A virtual environment at `..\venv` or another Python environment with the backend dependencies installed
- A root `.env` file at `D:\bingbong\kyron-take-home\.env`

## Install Dependencies

If your virtual environment is not already prepared:

```powershell
cd D:\bingbong\kyron-take-home\backend
..\venv\Scripts\python -m pip install -r requirements.txt
```

## Environment Variables

The backend reads its configuration from the repository root `.env`.

Minimum required:

```env
OPENAI_API_KEY=
```

Common settings:

```env
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_VOICE_NAME=alloy
OPENAI_REALTIME_DEBUG_GREETING=false
```

Optional OpenAI voice and SIP settings:

```env
OPENAI_PROJECT_ID=
OPENAI_SIP_URI=
OPENAI_WEBHOOK_SECRET=
OPENAI_WEBOOK_SIGNING_SECRET=
```

Optional Twilio settings:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WEBHOOK_BASE_URL=
```

Notes:

- `OPENAI_PROJECT_ID` or `OPENAI_SIP_URI` is needed for SIP-backed voice routing.
- `OPENAI_WEBHOOK_SECRET` is the preferred webhook verification variable.
- `OPENAI_WEBOOK_SIGNING_SECRET` is still supported for backward compatibility.
- `TWILIO_WEBHOOK_BASE_URL` must be a public HTTPS base URL for live Twilio callbacks.`r`n- `FRONTEND_ORIGINS` can optionally add comma-separated browser origins beyond the built-in localhost and deployed Vercel defaults.
- On Render, set `TWILIO_WEBHOOK_BASE_URL` to your public Render service URL or custom HTTPS domain.

## Start The Backend Server

From the `backend` directory:

```powershell
..\venv\Scripts\python -m uvicorn app.main:app --reload
```

For Render, use:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

The backend runs at:

```text
http://localhost:8000
```

The API prefix is:

```text
/api
```

## Verify The Server

Health check:

```text
GET http://localhost:8000/api/health
```

Config status:

```text
GET http://localhost:8000/api/system/config-status
```

If the backend is running correctly:

- `/api/health` returns `{"status":"ok"}`
- `/api/system/config-status` shows whether OpenAI, Twilio, SIP, and webhook settings are configured

## Main Local Endpoints

### Scheduling

- `POST /api/scheduling/conversations`
- `POST /api/scheduling/conversations/{conversation_id}/turn`
- `PATCH /api/scheduling/conversations/{conversation_id}/intake`
- `POST /api/scheduling/conversations/{conversation_id}/provider-match`
- `GET /api/scheduling/conversations/{conversation_id}/slots`
- `POST /api/scheduling/conversations/{conversation_id}/book`
- `POST /api/scheduling/conversations/{conversation_id}/handoff`
- `GET /api/scheduling/handoffs/{handoff_id}`

### System

- `GET /api/system/config-status`
- `GET /api/system/office-hours`
- `GET /api/system/office-address`
- `POST /api/system/refill-request`

### Voice

- `POST /api/voice/twiml`
- `POST /api/voice/status`
- `POST /api/voice/sip/session`
- `POST /api/voice/sip/events`
- `POST /api/voice/sip/transcript`
- `POST /api/voice/sip/finalize`
- `WS /api/voice/media`

## Run Tests

From the `backend` directory:

```powershell
..\venv\Scripts\python -m pytest
```

Tests live under `backend/tests`.

## Debugging

Useful checks while the server is running:

- `GET /api/system/config-status` for runtime configuration status
- backend logs for SIP webhook and Twilio callback traces
- `/api/voice/twiml`, `/api/voice/status`, `/api/voice/sip/events`, and `/api/voice/media` for voice troubleshooting

For websocket breakpoints in VS Code, prefer the no-reload backend launch variant because reload mode forks a child process.

