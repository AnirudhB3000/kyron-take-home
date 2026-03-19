# PROBLEM STATEMENT

you will be creating a web app where the end user is a patient and can chat with an intelligent, human-like AI via a web chat-like interface. The patient should be guided through different workflows. For example, the patient may want to schedule an appointment, check in on a prescription refill, or simply check the address and hours of the physician practice's offices. (Imagine that this is a product that Kyron Medical is providing to a physician group to help serve patients). It needs to take in the first and last name, DOB, phone number, and email of the patient, as well as the reason for their appointment. After patient intake, it should offer some dates/times that are available for this particular reason, and allow the patient to choose what works for them. If the patient makes a particular ask (e.g. "do you have something on a Tuesday?"), the AI should be able to reply accordingly. Once an appointment is booked, the user should be emailed with details by the AI. Ideally, the user is texted as well (note that you may need to get them to opt in for this to work).

Importantly, the web app needs a button allowing the patient to opt for a phone call to their number to continue the chat as a voice conversation with the same AI, which must retain the context of the web chat.

For now, hard-code a set of availabilities for a set of at least four different doctors, each specializing in a different body part, for the following 30-60 days. Based on the body part the patient says they want treated, the AI should semantically match each patient to one of the providers, or state that the practice does not treat the given body part. The main feature we will test is appointment scheduling and the handoff between the chat and the voice AI, but you should also develop the other workflows depending on how much time you have.  For the voice AI itself, there will be safety testing to ensure it cannot provide medical advice or say anything harmful or misleading to the patient.

Importantly, this is a classic example of a large, multi-faceted ask with a tight deadline. We don't expect that you will have every feature done perfectly.  We want to see that you can ship error-free code for as many of these features as possible by the deadline, and that you know how to prioritize as you build, ensuring that even an "incomplete" build looks and feels complete to the end user. Always start with an MVP. You'll stand out if in addition to what is asked for, you pioneer one or two features that are not mentioned in this email and would be useful to the end user (as an idea, it would be very useful to allow the user to call the same AI number back, and have the AI remember the previous conversation and pick it up smoothly, in case the call gets disconnected).

Consider using AWS EC2 for hosting, and ensure the website receives traffic via HTTPS. You may want to compare different models like GPT, Claude, and Gemini for the core of your web app, and we encourage you not to try building the Voice AI stack from scratch. There are tons of end-to-end Voice AI companies that give you self-serve low-code or no-code solutions such that you can build something overnight. 

## Development Instructions

- All code or file edits must be approved by the user before being applied.
- All implemented or modified logic must include test coverage.
- User-authored changes must be respected. If the user changes code directly, those changes must not be overwritten, reverted, or ignored without explicit approval.
- All updates to the codebase must include any necessary updates to `AGENTS.md` so the working instructions remain aligned with how the codebase should be understood and modified.
- The frontend stack is React with Vite.
- The backend stack is FastAPI.
- The root `.env` file is the environment source for runtime configuration.
- Backend config currently accepts `OPENAI_API_KEY`, `OPENAI_REALTIME_MODEL`, `OPENAI_VOICE_NAME`, optional `OPENAI_PROJECT_ID`, optional `OPENAI_SIP_URI`, optional `OPENAI_WEBHOOK_SECRET`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, optional `TWILIO_WEBHOOK_BASE_URL`, and optional `FRONTEND_ORIGINS` from the root `.env`.
- For backward compatibility, voice webhook signing can also be loaded from the legacy typoed env name `OPENAI_WEBOOK_SIGNING_SECRET`, but new config should use `OPENAI_WEBHOOK_SECRET`.
- The realtime voice bridge should default to OpenAI's GA `gpt-realtime` model behavior, rely on `server_vad` turn detection to create responses, and avoid eager bootstrap `response.create` calls before the caller finishes speaking.
- Backend tests live under `backend/tests`.
- Frontend tests live under `frontend/src/tests`.
- Repo-local generated artifacts such as `pytest-cache-files-*`, backend runtime logs, Playwright/Vitest output folders, coverage output, and virtualenv or dependency directories should stay out of git via `.gitignore`.
- The root `README.md` should remain an accurate operator-facing guide for local setup, environment variables, scheduling workflows, voice handoff behavior, testing commands, and debugging entry points.
- The nested `backend/README.md` and `frontend/README.md` should stay narrowly focused on setup, server startup, local verification, environment expectations, and test commands for their respective applications.
- Frontend deployment-sensitive configuration such as the API base URL should remain environment-driven rather than hardcoded so local and hosted environments can coexist cleanly.
- Backend API routes are mounted under `/api` and backend code is organized into `api`, `core`, `services`, `adapters`, and `schemas`.
- Frontend code is organized into `app`, `components`, `features`, `services`, `lib`, `types`, and `tests`.
- Frontend UI should prioritize end-user polish, use a liquid glass visual style, align with Kyron Medical colors, and include premium motion that makes the product feel cutting-edge.
- The Phase 13 frontend shell is a chat-first two-panel layout with workflow context cards, premium loading and confirmation framing, and liquid-glass motion; future polish should preserve that structure rather than reverting to a plain form UI.
- The chat transcript should auto-scroll to the latest assistant or patient message by default, and the composer should submit on `Enter` while preserving `Shift+Enter` for multi-line input.
- Chat auto-scroll should be confined to the transcript container itself; frontend message updates must not call document-level scrolling APIs that reset the page scrollbar on desktop layouts with both page and transcript overflow.
- MVP provider and availability data are stored as structured shared fixtures under `shared/providers` and `shared/fixtures`.
- Provider matching is deterministic and driven by shared fixture terms rather than LLM inference at this stage.
- Conversation and scheduling workflow state are currently managed in-memory through backend service and schema layers until persistent storage is introduced.
- OpenAI is called only from the backend through adapters, and voice continuation now depends on an OpenAI Realtime bridge contract in addition to the existing text assistant adapter.
- Scheduling MVP routes live under `/api/scheduling` and currently support conversation creation, intake updates, provider matching, slot listing with optional weekday filtering, booking, and voice handoff.
- Live phone continuation now uses Twilio outbound calls plus `/api/voice/twiml` and `/api/voice/status`; the default transport is now SIP-backed OpenAI Realtime sideband control, while `/api/voice/media` remains as a legacy Twilio Media Streams fallback. Voice handoff responses and outbound-call traces should surface the exact `twiml_url` and `status_callback_url` used for each call so Twilio Console requests can be compared directly against backend state.
- Voice handoff state now tracks `voice_transport`, `openai_session_id`, and `sip_call_id` so SIP sessions can reuse the same shared conversation state and append transcript turns back into that conversation.
- The voice bridge must preserve the same backend conversation state and append voice transcript turns back into that shared conversation.
- The `/api/voice/media` relay must keep a pending OpenAI receive task alive while Twilio media frames continue arriving; recreating and cancelling that task per loop starves assistant audio under live caller speech.
- The `/api/voice/media` relay should attempt one fresh OpenAI Realtime reconnect/bootstrap cycle if the session returns an `error` event with `error.type == "server_error"` immediately after setup, since live calls have shown transient upstream failures after `session.updated`.
- The `/api/voice/media` relay must buffer early Twilio caller-audio frames until OpenAI emits `session.updated`, but the startup buffer must stay capped to a small rolling window of recent frames so the bridge does not burst-flush an unbounded backlog into OpenAI after session setup.
- Runtime voice debugging currently depends on `/api/system/config-status`, `/api/voice/sip/session`, `/api/voice/sip/events`, and structured backend logs from both the SIP sideband path and the legacy `/api/voice/media` fallback.
- `/api/voice/twiml` should log the exact SIP URI returned for each `handoff_id` so live-call debugging can confirm the Twilio leg is dialing the expected OpenAI SIP destination.
- For live voice debugging only, backend config may temporarily enable `OPENAI_REALTIME_DEBUG_GREETING` to force a one-time assistant audio greeting after session setup and isolate outbound-audio issues from VAD/input issues.
- For live voice troubleshooting, prefer the VS Code backend debug configuration in `.vscode/launch.json`; use the no-reload launch variant for websocket breakpoints because Uvicorn reload mode forks a child process. The `/api/voice/media` route also prints the raw first Twilio `start` event to the backend console so media-stream payload shape can be inspected even if logger formatting drops fields.
- The frontend scheduling experience is driven by backend scheduling APIs, and frontend workflow behavior should treat backend scheduling state as authoritative.
- Intake collection must remain resilient: invalid names, DOBs, phone numbers, emails, unsupported appointment reasons, off-topic questions, and alarming emergency language should keep the conversation safe and recoverable.
- Intake parsing should accept free-form patient messages and infer as many intake fields as possible from a single turn; names, DOB, phone, email, and appointment reason may arrive together, and the backend extraction path should capture validated fields before asking only for the remaining missing detail.
- The assistant must introduce itself before requesting patient data, route identity and site-clarification detours through the backend assistant layer, and require explicit confirmation before booking a chosen slot.
- Backend safety decisions are authoritative and categorized as safe, medical_advice, or emergency; chat and future voice flows should preserve the active intake step while using those categories to choose the correct fallback behavior.
- Local frontend development depends on backend CORS allowing the Vite dev origins `http://localhost:5173` and `http://127.0.0.1:5173`.
- Office hours and office address are structured backend-driven secondary workflows and should answer the question without derailing the active scheduling step.
- Prescription refill support is currently a structured backend-driven request-intake stub, not live refill-status lookup, and it must not drift into medication advice or derail the active scheduling step.
- After a patient provides a phone number, the chat flow should explicitly ask whether they want SMS updates; opting in should persist `sms_opt_in`, trigger an immediate Twilio SMS confirmation from the configured toll-free number when available, and continue to send booking SMS notifications only for opted-in patients.
- SIP routing requires `OPENAI_PROJECT_ID` or `OPENAI_SIP_URI`; TwiML injects `x-handoff-id` into the SIP URI so OpenAI-side webhook events can be mapped back to the in-memory handoff.
- `/api/voice/sip/events` must verify OpenAI webhook signatures when `OPENAI_WEBHOOK_SECRET` is configured, recover `handoff_id` from the SIP `To` header query string on `realtime.call.incoming`, call OpenAI's Realtime accept-call endpoint with the shared session instructions, and then open the sideband websocket using the webhook `call_id`.
- SIP troubleshooting logs should now include the webhook request header subset and payload size, payload key summary, extracted handoff/session/call identifiers, accept-call start/result, sideband websocket bootstrap milestones, TwiML transport choice, and Twilio status callback payload keys so live call failures can be narrowed to a single stage from backend logs alone.




