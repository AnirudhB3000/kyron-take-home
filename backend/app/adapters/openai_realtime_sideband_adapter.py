import logging

import httpx
from openai import OpenAI

from app.adapters.openai_realtime_adapter import OpenAIRealtimeAdapter
from app.schemas.voice import RealtimeVoiceSession


logger = logging.getLogger(__name__)


def _emit_sideband_trace(message: str) -> None:
    print(message, flush=True)
    logger.info(message)


class OpenAIRealtimeSidebandAdapter(OpenAIRealtimeAdapter):
    """Controls SIP-backed Realtime sessions over a server-side websocket connection."""

    def __init__(self, settings=None, connector=None, http_client_factory=None, webhook_client=None) -> None:
        super().__init__(settings=settings, connector=connector)
        self.http_client_factory = http_client_factory
        self.webhook_client = webhook_client

    def build_connect_url(self, model: str | None = None, call_id: str | None = None) -> str:
        url = super().build_connect_url(model)
        if call_id:
            return f"{url}&call_id={call_id}"
        return url

    def build_accept_call_url(self, call_id: str) -> str:
        return f"https://api.openai.com/v1/realtime/calls/{call_id}/accept"

    def build_accept_call_request(self, session: RealtimeVoiceSession) -> dict:
        return {
            "type": "realtime",
            "model": session.model,
            "voice": session.voice,
            "instructions": session.instructions,
        }

    def _build_webhook_client(self):
        if self.webhook_client is not None:
            return self.webhook_client
        return OpenAI(api_key=self.settings.openai_api_key)

    def verify_webhook(self, payload: bytes, headers) -> dict:
        webhook_secret = self.settings.openai_webhook_secret or getattr(self.settings, "openai_webook_signing_secret", None)
        header_dict = dict(headers)
        loggable_headers = {
            key: header_dict[key]
            for key in ("webhook-id", "webhook-timestamp", "user-agent", "content-type")
            if key in header_dict
        }
        _emit_sideband_trace(
            f"Voice SIP: verifying OpenAI webhook secret_configured={bool(webhook_secret)} payload_bytes={len(payload)} headers={loggable_headers}"
        )
        if not webhook_secret:
            event = httpx.Response(200, content=payload).json()
            _emit_sideband_trace(f"Voice SIP: accepted unsigned webhook payload_type={event.get('type')}")
            return event

        event = self._build_webhook_client().webhooks.unwrap(
            payload.decode("utf-8"),
            header_dict,
            webhook_secret,
        )
        _emit_sideband_trace("Voice SIP: webhook signature verified successfully")
        if hasattr(event, "model_dump"):
            return event.model_dump()
        return dict(event)

    async def connect(self, model: str | None = None, call_id: str | None = None):
        if self.connector is not None:
            return await self.connector(self.build_connect_url(model, call_id), self.build_headers())

        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("The websockets package is required for OpenAI Realtime sideband control.") from exc

        return await websockets.connect(
            self.build_connect_url(model, call_id),
            additional_headers=self.build_headers(),
            open_timeout=5,
        )

    async def accept_call(self, call_id: str, session: RealtimeVoiceSession) -> dict:
        request_body = self.build_accept_call_request(session)
        _emit_sideband_trace(
            f"Voice SIP: accepting OpenAI call call_id={call_id} model={session.model} voice={session.voice} instructions_chars={len(session.instructions)}"
        )
        if self.http_client_factory is not None:
            response = await self.http_client_factory().post(
                self.build_accept_call_url(call_id),
                headers=self.build_headers(),
                json=request_body,
            )
            if hasattr(response, "raise_for_status"):
                response.raise_for_status()
            payload = response.json()
            _emit_sideband_trace(
                f"Voice SIP: accept_call completed via injected client call_id={call_id} response_keys={sorted(payload.keys())}"
            )
            return payload

        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.post(
                self.build_accept_call_url(call_id),
                headers=self.build_headers(),
                json=request_body,
            )
            response.raise_for_status()
            payload = response.json()
            _emit_sideband_trace(
                f"Voice SIP: accept_call completed call_id={call_id} response_keys={sorted(payload.keys())}"
            )
            return payload

    async def send_session_update(self, connection, session: RealtimeVoiceSession) -> None:
        _emit_sideband_trace(
            f"Voice SIP: sending session.update handoff_id={session.handoff_id} openai_session_id={session.openai_session_id} recent_messages={len(session.recent_messages)}"
        )
        await self.send_event(connection, self.build_session_update(session))
