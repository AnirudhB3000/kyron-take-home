import json
from urllib.parse import urlencode

from app.core.config import Settings, get_settings
from app.schemas.voice import RealtimeVoiceSession


class OpenAIRealtimeAdapter:
    """Builds and manages OpenAI Realtime websocket session events."""

    def __init__(self, settings: Settings | None = None, connector=None) -> None:
        self.settings = settings or get_settings()
        self.connector = connector

    def build_connect_url(self, model: str | None = None) -> str:
        realtime_model = model or self.settings.openai_realtime_model
        return f"wss://api.openai.com/v1/realtime?{urlencode({'model': realtime_model})}"

    def build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

    async def connect(self, model: str | None = None):
        if self.connector is not None:
            return await self.connector(self.build_connect_url(model), self.build_headers())

        try:
            import websockets
        except ImportError as exc:
            raise RuntimeError("The websockets package is required for OpenAI Realtime voice bridging.") from exc

        return await websockets.connect(
            self.build_connect_url(model),
            additional_headers=self.build_headers(),
            open_timeout=5,
        )

    def build_session_update(self, session: RealtimeVoiceSession) -> dict:
        return {
            "type": "session.update",
            "session": {
                "voice": session.voice,
                "instructions": session.instructions,
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "turn_detection": {
                    "type": "server_vad",
                    "create_response": True,
                    "interrupt_response": True,
                    "silence_duration_ms": 500,
                },
                "modalities": ["audio", "text"],
            },
        }

    def build_response_create(self) -> dict:
        return {
            "type": "response.create",
            "response": {
                "modalities": ["audio", "text"],
            },
        }

    def build_audio_append(self, audio_payload: str) -> dict:
        return {
            "type": "input_audio_buffer.append",
            "audio": audio_payload,
        }

    def build_audio_commit(self) -> dict:
        return {"type": "input_audio_buffer.commit"}

    @staticmethod
    def build_twilio_media_event(stream_sid: str, audio_payload: str) -> dict:
        return {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": audio_payload,
            },
        }

    async def send_event(self, connection, event: dict) -> None:
        await connection.send(json.dumps(event))

    async def receive_event(self, connection) -> dict:
        message = await connection.recv()
        return json.loads(message)

    async def close(self, connection) -> None:
        await connection.close()
