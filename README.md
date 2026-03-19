# Kyron Patient Assistant Take-Home

This repository contains a conversation-first patient assistant for a physician practice. Patients can use a premium web chat UI to schedule appointments, ask for office information, request a prescription refill callback, and continue the same conversation over a phone call with a voice AI.

The product is intentionally built around a single backend-owned conversation state so chat and voice stay in sync. The backend handles workflow logic, provider matching, scheduling, safety enforcement, and notification triggers. The frontend is responsible for rendering the patient experience.

## What The App Does

- Introduces the assistant and collects scheduling intake data in chat.
- Validates first name, last name, DOB, phone number, email, and appointment reason.
- Matches the patient concern to a supported specialty using deterministic provider fixtures.
- Shows appointment slots for at least four providers across different specialties.
- Supports slot refinement by weekday, such as "Do you have something on Tuesday?"
- Requires explicit confirmation before booking.
- Sends booking notifications by email and, when the patient opts in, by SMS.
- Lets the patient continue the same conversation by phone through a voice handoff.
- Preserves safety boundaries by refusing medical advice and escalating emergency language.
- Answers office hours and office address questions without breaking the active scheduling step.
- Accepts prescription refill requests as a safe structured workflow stub.

## Product Scope

The primary workflow is appointment scheduling. The current MVP also includes:

- Office hours lookup
- Office address lookup
- Prescription refill request intake
- Chat-to-voice continuation
- Debug endpoints for voice transport and runtime configuration

Conversation and scheduling state are currently stored in memory. That keeps the MVP fast to run locally, but state is lost when the backend restarts.

## Tech Stack

### Frontend

- React 18
- Vite
- Vitest
- Playwright

### Backend

- FastAPI
- Uvicorn
- Pydantic Settings
- OpenAI Python SDK
- Twilio Python SDK
- WebSockets
- Pytest

### Shared Data

- `shared/providers/providers.json`
- `shared/fixtures/availability.json`

These fixtures drive deterministic provider matching and slot availability for the MVP.

## Architecture Summary

The system is conversation-centric:

- The frontend renders chat, slot selection, and the voice handoff trigger.
- The backend owns conversation state, patient intake state, workflow progression, provider matching, slot lookup, booking, notification triggers, handoff creation, and safety decisions.
- OpenAI is called only from the backend.
- The same backend conversation is reused when a patient moves from chat to voice.

Key backend entities include:

- `Conversation`
- `Message`
- `Patient`
- `Provider`
- `AvailabilitySlot`
- `Appointment`
- `Handoff`

More design notes live in [`ARCHITECTURE.md`](D:\bingbong\kyron-take-home\ARCHITECTURE.md).

## Repository Layout

```text
.
|-- backend/
|   |-- app/
|   |   |-- adapters/
|   |   |-- api/
|   |   |-- core/
|   |   |-- schemas/
|   |   `-- services/
|   `-- tests/
|-- frontend/
|   |-- src/
|   |   |-- app/
|   |   |-- components/
|   |   |-- features/
|   |   |-- lib/
|   |   |-- services/
|   |   |-- tests/
|   |   `-- types/
|   `-- tests/
|-- shared/
|   |-- fixtures/
|   `-- providers/
|-- AGENTS.md
|-- ARCHITECTURE.md
`-- README.md
```

## Prerequisites

- Python 3.12
- Node.js 20+
- npm
- A root `.env` file

Optional for full voice and notifications:

- OpenAI API credentials
- OpenAI Realtime SIP configuration
- Twilio account credentials and a Twilio phone number

## Environment Configuration

The backend reads runtime configuration from the root `.env` file.

Required for text assistant behavior:

```env
OPENAI_API_KEY=
```

Recommended defaults:

```env
OPENAI_REALTIME_MODEL=gpt-realtime
OPENAI_VOICE_NAME=alloy
```

Optional OpenAI settings:

```env
OPENAI_PROJECT_ID=
OPENAI_SIP_URI=
OPENAI_WEBHOOK_SECRET=
OPENAI_REALTIME_DEBUG_GREETING=false
```

Backward-compatible legacy variable:

```env
OPENAI_WEBOOK_SIGNING_SECRET=
```

Twilio settings:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
TWILIO_WEBHOOK_BASE_URL=
```

Notes:

- `OPENAI_PROJECT_ID` or `OPENAI_SIP_URI` is needed for SIP-based voice routing.
- `OPENAI_WEBHOOK_SECRET` is used to verify OpenAI SIP webhook signatures.
- `TWILIO_WEBHOOK_BASE_URL` should point to the public HTTPS base URL Twilio can call.`r`n- `FRONTEND_ORIGINS` can optionally add extra allowed browser origins for hosted frontend deployments.
- The frontend reads `VITE_API_BASE_URL` when provided and otherwise falls back to `http://localhost:8000/api`.

## Local Development

### 1. Create The Root `.env`

Add the environment variables listed above at the repository root.

### 2. Start The Backend

From the repository root:

```powershell
cd backend
..\venv\Scripts\python -m uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000/api`.

### 3. Start The Frontend

In a separate terminal:

```powershell
cd frontend
npm install
npm run dev
```

The web app will be available at `http://localhost:5173`.

For deployed frontend builds such as Vercel, set:

```text
VITE_API_BASE_URL=https://<your-render-service>.onrender.com/api
```

For a Render backend deploy, use this start command:

```text
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

If you want live Twilio voice callbacks against Render, set:

```text
TWILIO_WEBHOOK_BASE_URL=https://<your-render-service>.onrender.com
```

### 4. Open The App

Visit `http://localhost:5173` and start chatting with the assistant.

## How The Scheduling Flow Works

1. The assistant introduces itself and asks for the patient's first name.
2. Intake continues through last name, DOB, phone number, email, and appointment reason.
3. After a phone number is captured, the assistant explicitly asks whether the patient wants SMS updates.
4. Once intake is complete, the backend matches the appointment reason to a provider.
5. The backend returns available slots for the matched provider.
6. The patient can pick a slot directly or ask for a weekday-specific set of slots.
7. The assistant asks for explicit confirmation before booking.
8. On booking, the backend triggers notifications and marks the workflow complete.

## Supported Chat Detours

The assistant can handle these detours without losing the active intake step:

- Office hours
- Office address
- Prescription refill intake
- Clarification questions about the current intake prompt
- Safety fallback for medical advice or emergency language

## Voice Continuation

The app supports a chat-to-phone handoff so the patient can continue the same conversation as a voice interaction.

### Current Voice Behavior

- The handoff is created from the scheduling workflow.
- The handoff reuses the existing backend conversation context.
- Voice transcript turns are appended back into the shared conversation state.
- The default transport is SIP-backed OpenAI Realtime sideband control.
- A legacy Twilio Media Streams websocket fallback remains available at `/api/voice/media`.

### Main Voice Endpoints

- `POST /api/scheduling/conversations/{conversation_id}/handoff`
- `GET /api/scheduling/handoffs/{handoff_id}`
- `POST /api/voice/twiml`
- `POST /api/voice/status`
- `POST /api/voice/sip/session`
- `POST /api/voice/sip/events`
- `POST /api/voice/sip/transcript`
- `POST /api/voice/sip/finalize`
- `WS /api/voice/media`

### Voice Transport Notes

- SIP routing requires `OPENAI_PROJECT_ID` or `OPENAI_SIP_URI`.
- The TwiML path injects the handoff identifier into the SIP URI so OpenAI-side events can map back to the same in-memory handoff.
- OpenAI webhook signature verification is enforced when `OPENAI_WEBHOOK_SECRET` is configured.
- The media-stream fallback buffers early caller audio until OpenAI emits `session.updated`, with a capped startup buffer.

## API Summary

### Health And System

- `GET /api/health`
- `GET /api/system/config-status`
- `GET /api/system/office-hours`
- `GET /api/system/office-address`
- `POST /api/system/refill-request`

### Scheduling

- `POST /api/scheduling/conversations`
- `POST /api/scheduling/conversations/{conversation_id}/turn`
- `PATCH /api/scheduling/conversations/{conversation_id}/intake`
- `POST /api/scheduling/conversations/{conversation_id}/provider-match`
- `GET /api/scheduling/conversations/{conversation_id}/slots`
- `POST /api/scheduling/conversations/{conversation_id}/book`
- `POST /api/scheduling/conversations/{conversation_id}/handoff`
- `GET /api/scheduling/handoffs/{handoff_id}`

## Frontend Behavior

The frontend uses a chat-first two-panel shell with workflow context cards and premium motion. Key UX behavior includes:

- Auto-scroll to the latest transcript message
- `Enter` to send, `Shift+Enter` for multi-line messages
- Slot list rendering inside the scheduling flow
- A continue-by-phone trigger once the patient phone number is known
- UI behavior driven by backend scheduling state

Frontend API configuration currently lives in [`frontend/src/lib/config.js`](D:\bingbong\kyron-take-home\frontend\src\lib\config.js).

## Testing

### Backend Tests

From the repository root:

```powershell
cd backend
..\venv\Scripts\python -m pytest
```

### Frontend Unit Tests

From the `frontend` directory:

```powershell
npm test
```

### Frontend End-To-End Tests

From the `frontend` directory:

```powershell
npm run test:e2e
```

Backend tests live under `backend/tests`. Frontend unit tests live under `frontend/src/tests`. Playwright end-to-end specs live under `frontend/tests/e2e`.

## Fixtures And MVP Assumptions

- Provider matching is deterministic and based on fixture terms rather than LLM inference.
- Provider and availability data are hard-coded shared fixtures.
- Scheduling state is in memory.
- The assistant is designed to avoid medical advice and harmful claims.
- Prescription refill support is a request-intake stub, not a live refill-status integration.

## Debugging Tips

### Runtime Config

Use `GET /api/system/config-status` to confirm whether:

- OpenAI is configured
- Twilio is configured
- SIP routing is configured
- webhook signature verification is configured
- debug greeting mode is enabled

### Voice Debugging

Useful backend paths:

- `/api/voice/sip/session`
- `/api/voice/sip/events`
- `/api/voice/twiml`
- `/api/voice/status`
- `/api/voice/media`

Useful behavior:

- `/api/voice/twiml` logs the exact SIP URI built for each handoff.
- `/api/voice/status` logs the exact Twilio callback payload keys.
- `/api/voice/media` prints the raw first Twilio `start` event for payload inspection.
- `OPENAI_REALTIME_DEBUG_GREETING=true` can temporarily force a one-time assistant greeting after session setup.

### VS Code Debugging

The repo includes VS Code launch configurations for backend debugging. For websocket breakpoint work, prefer the no-reload backend launch variant because Uvicorn reload mode forks a child process.

## Current Limitations

- No persistent database
- No authentication layer
- No real EHR or scheduling system integration
- No production email delivery provider shown in this repo
- SMS depends on Twilio configuration and patient opt-in
- Voice depends on valid public webhook routing and external credentials

## Productionization Next Steps

- Move conversation, appointment, and handoff state into persistent storage.
- Add provider admin tooling instead of fixture-based scheduling.
- Add authenticated patient identity and consent flows.
- Replace stub refill handling with a real refill workflow or staff escalation queue.
- Add delivery status tracking and retries for notifications.
- Add deployment infrastructure for HTTPS hosting and public webhook routing.
- Add observability around drop-off, slot conversion, and voice handoff success.

## Relevant Files

- [`AGENTS.md`](D:\bingbong\kyron-take-home\AGENTS.md)
- [`ARCHITECTURE.md`](D:\bingbong\kyron-take-home\ARCHITECTURE.md)
- [`backend/app/main.py`](D:\bingbong\kyron-take-home\backend\app\main.py)
- [`backend/app/api/routes/scheduling.py`](D:\bingbong\kyron-take-home\backend\app\api\routes\scheduling.py)
- [`backend/app/api/routes/system.py`](D:\bingbong\kyron-take-home\backend\app\api\routes\system.py)
- [`backend/app/api/routes/voice.py`](D:\bingbong\kyron-take-home\backend\app\api\routes\voice.py)
- [`frontend/src/features/scheduling/useSchedulingChat.js`](D:\bingbong\kyron-take-home\frontend\src\features\scheduling\useSchedulingChat.js)
- [`frontend/src/lib/config.js`](D:\bingbong\kyron-take-home\frontend\src\lib\config.js)
- [`shared/providers/providers.json`](D:\bingbong\kyron-take-home\shared\providers\providers.json)
- [`shared/fixtures/availability.json`](D:\bingbong\kyron-take-home\shared\fixtures\availability.json)

