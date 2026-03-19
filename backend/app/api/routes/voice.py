import asyncio
import json
import logging
from collections import deque
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, HTTPException, Query, Request, Response, WebSocket, WebSocketDisconnect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from app.core.config import get_settings
from app.core.dependencies import (
    handoff_service,
    openai_realtime_sideband_adapter,
    twilio_media_bridge,
    voice_sip_service,
)
from app.schemas.voice_sip import SipFinalizeRequest, SipSessionStartRequest, SipSessionStartResponse, SipTranscriptEvent

router = APIRouter()
logger = logging.getLogger(__name__)

STARTUP_BUFFER_MAX_EVENTS = 12


def _emit_voice_sip_trace(message: str) -> None:
    print(message, flush=True)
    logger.info(message)


def _loggable_headers(headers) -> dict[str, str]:
    header_dict = dict(headers)
    return {
        key: header_dict[key]
        for key in ("webhook-id", "webhook-timestamp", "user-agent", "content-type", "host")
        if key in header_dict
    }


def _payload_shape(payload: dict) -> dict[str, object]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return {
        "type": payload.get("type"),
        "keys": sorted(payload.keys()),
        "data_keys": sorted(data.keys()) if isinstance(data, dict) else [],
    }


def _voice_transport() -> str:
    return get_settings().openai_realtime_transport.lower()


def _nested_payload_values(payload: dict, key: str) -> list[object]:
    values: list[object] = []
    if payload.get(key) is not None:
        values.append(payload.get(key))
    data = payload.get("data")
    if isinstance(data, dict) and data.get(key) is not None:
        values.append(data.get(key))
    return values


def _candidate_header_groups(payload: dict) -> list[object]:
    groups: list[object] = []
    groups.extend(_nested_payload_values(payload, "sip_headers"))
    groups.extend(_nested_payload_values(payload, "headers"))
    for key in ("sip", "call", "data"):
        group = payload.get(key)
        if isinstance(group, dict) and group.get("headers") is not None:
            groups.append(group.get("headers"))
    return groups



def _lookup_header_values(group: object, names: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    if isinstance(group, dict):
        for name in names:
            if group.get(name):
                values.append(group[name])
    elif isinstance(group, list):
        normalized = {name.lower() for name in names}
        for item in group:
            if not isinstance(item, dict):
                continue
            item_name = str(item.get("name", "")).lower()
            if item_name in normalized and item.get("value"):
                values.append(str(item["value"]))
    return values



def _extract_handoff_id_from_uri(value: str) -> str | None:
    if "?" not in value:
        return None
    query = parse_qs(urlsplit(value).query)
    return query.get("x-handoff-id", [None])[0] or query.get("handoff_id", [None])[0]



def _extract_sip_handoff_id(payload: dict) -> str | None:
    direct = payload.get("handoff_id") or (payload.get("data", {}).get("handoff_id") if isinstance(payload.get("data"), dict) else None)
    if direct:
        return direct
    for group in _candidate_header_groups(payload):
        direct_values = _lookup_header_values(group, ("x-handoff-id", "X-Handoff-Id", "handoff_id"))
        if direct_values:
            return direct_values[0]
        uri_values = _lookup_header_values(group, ("To", "Request-URI"))
        for uri_value in uri_values:
            handoff_id = _extract_handoff_id_from_uri(uri_value)
            if handoff_id:
                return handoff_id
    return None



def _extract_openai_session_id(payload: dict) -> str | None:
    for key in ("openai_session_id", "session_id", "call_id"):
        values = _nested_payload_values(payload, key)
        if values:
            return str(values[0])
    for key in ("session", "call"):
        value = payload.get(key)
        if isinstance(value, dict) and value.get("id"):
            return str(value["id"])
    return None



def _extract_call_sid(payload: dict) -> str | None:
    values = _nested_payload_values(payload, "call_sid")
    if values:
        return str(values[0])
    return payload.get("twilio_call_sid") or payload.get("CallSid")



def _extract_sip_call_id(payload: dict) -> str | None:
    for key in ("sip_call_id", "call_id"):
        values = _nested_payload_values(payload, key)
        if values:
            return str(values[0])
    sip = payload.get("sip")
    if isinstance(sip, dict) and sip.get("call_id"):
        return str(sip["call_id"])
    return None


async def _run_sideband_listener(handoff_id: str, connection: object) -> None:
    try:
        while True:
            event = await openai_realtime_sideband_adapter.receive_event(connection)
            logger.info(
                "Voice SIP: received OpenAI sideband event for handoff_id=%s event_type=%s",
                handoff_id,
                event.get("type"),
            )
            voice_sip_service.handle_openai_event(handoff_id, event)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Voice SIP: sideband listener failure for handoff_id=%s", handoff_id)
    finally:
        voice_sip_service.finalize_session(handoff_id)


async def _ensure_sideband_session(handoff_id: str, openai_session_id: str) -> None:
    if handoff_id in voice_sip_service.sideband_connections:
        logger.info(
            "Voice SIP: reusing existing sideband session for handoff_id=%s openai_session_id=%s",
            handoff_id,
            openai_session_id,
        )
        return
    logger.info(
        "Voice SIP: opening sideband session for handoff_id=%s openai_session_id=%s",
        handoff_id,
        openai_session_id,
    )
    session = voice_sip_service.build_sip_session(handoff_id)
    connection = await openai_realtime_sideband_adapter.connect(session.model, openai_session_id)
    logger.info(
        "Voice SIP: sideband websocket connected for handoff_id=%s openai_session_id=%s",
        handoff_id,
        openai_session_id,
    )
    await openai_realtime_sideband_adapter.send_session_update(connection, session)
    logger.info(
        "Voice SIP: sideband session.update completed for handoff_id=%s openai_session_id=%s",
        handoff_id,
        openai_session_id,
    )
    listener_task = asyncio.create_task(_run_sideband_listener(handoff_id, connection))
    voice_sip_service.register_sideband(handoff_id, connection, listener_task)
    logger.info(
        "Voice SIP: sideband listener registered for handoff_id=%s openai_session_id=%s",
        handoff_id,
        openai_session_id,
    )


@router.post("/twiml")
def voice_twiml(handoff_id: str = Query(...)) -> Response:
    try:
        handoff_service.get_handoff_context(handoff_id)
        transport = _voice_transport()
        _emit_voice_sip_trace(f"Voice routing: building TwiML for handoff_id={handoff_id} transport={transport}")
        if transport == "sip":
            twiml = voice_sip_service.build_twiml_response(handoff_id)
        else:
            twiml = twilio_media_bridge.build_twiml_response(handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return Response(content=twiml, media_type="application/xml")


@router.post("/status")
async def voice_status(request: Request, handoff_id: str = Query(default=None)) -> dict:
    payload = parse_qs((await request.body()).decode("utf-8"))
    call_sid = payload.get("CallSid", [None])[0]
    call_status = payload.get("CallStatus", [None])[0]

    _emit_voice_sip_trace(
        f"Voice routing: received Twilio status callback handoff_id={handoff_id} call_sid={call_sid} call_status={call_status} payload_keys={sorted(payload.keys())}"
    )

    if not call_sid or not call_status:
        raise HTTPException(status_code=400, detail="CallSid and CallStatus are required.")

    try:
        context = handoff_service.update_handoff_status(
            handoff_id=handoff_id,
            call_sid=call_sid,
            call_status=call_status,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc

    return {
        "ok": True,
        "handoff_id": context.handoff_id,
        "call_sid": call_sid,
        "call_status": call_status,
    }


@router.post("/sip/session", response_model=SipSessionStartResponse)
async def voice_sip_session(payload: SipSessionStartRequest) -> SipSessionStartResponse:
    _emit_voice_sip_trace(
        f"Voice SIP: session bootstrap requested handoff_id={payload.handoff_id} openai_session_id={payload.openai_session_id} call_sid={payload.call_sid} sip_call_id={payload.sip_call_id}"
    )
    try:
        handoff_service.get_handoff_context(payload.handoff_id)
        handoff_service.attach_voice_transport(payload.handoff_id, "sip")
        if payload.call_sid or payload.sip_call_id:
            voice_sip_service.attach_sip_call(payload.handoff_id, payload.sip_call_id, payload.call_sid)
        if payload.openai_session_id:
            voice_sip_service.attach_openai_session(payload.handoff_id, payload.openai_session_id)
            await _ensure_sideband_session(payload.handoff_id, payload.openai_session_id)
        response = voice_sip_service.build_sip_session_response(payload.handoff_id)
        _emit_voice_sip_trace(
            f"Voice SIP: session bootstrap completed handoff_id={response.handoff_id} openai_session_id={response.openai_session_id} sip_call_id={response.sip_call_id}"
        )
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sip/events")
async def voice_sip_events(request: Request) -> dict:
    raw_body = await request.body()
    _emit_voice_sip_trace(
        f"Voice SIP: received webhook request payload_bytes={len(raw_body)} headers={_loggable_headers(request.headers)}"
    )
    try:
        payload = openai_realtime_sideband_adapter.verify_webhook(raw_body, request.headers)
    except Exception:
        logger.exception("Voice SIP: webhook verification failed")
        raise HTTPException(status_code=400, detail="Invalid OpenAI webhook signature.") from None

    _emit_voice_sip_trace(f"Voice SIP: webhook payload summary={_payload_shape(payload)}")

    handoff_id = _extract_sip_handoff_id(payload)
    if not handoff_id:
        logger.error("Voice SIP: could not extract handoff_id from webhook payload=%s", _payload_shape(payload))
        raise HTTPException(status_code=400, detail="handoff_id is required.")

    try:
        handoff_service.get_handoff_context(handoff_id)
    except KeyError as exc:
        logger.error("Voice SIP: webhook referenced unknown handoff_id=%s", handoff_id)
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc

    call_sid = _extract_call_sid(payload)
    sip_call_id = _extract_sip_call_id(payload)
    openai_session_id = _extract_openai_session_id(payload)
    event_type = payload.get("type")

    _emit_voice_sip_trace(
        f"Voice SIP: received webhook event for handoff_id={handoff_id} event_type={event_type} openai_session_id={openai_session_id} sip_call_id={sip_call_id} call_sid={call_sid}"
    )

    if call_sid or sip_call_id:
        voice_sip_service.attach_sip_call(handoff_id, sip_call_id, call_sid)
    if openai_session_id:
        voice_sip_service.attach_openai_session(handoff_id, openai_session_id)

    accepted = False
    if event_type == "realtime.call.incoming":
        if not openai_session_id:
            logger.error("Voice SIP: incoming call event missing call_id for handoff_id=%s", handoff_id)
            raise HTTPException(status_code=400, detail="call_id is required for realtime.call.incoming events.")
        session = voice_sip_service.build_sip_session(handoff_id)
        _emit_voice_sip_trace(
            f"Voice SIP: accepting incoming call for handoff_id={handoff_id} openai_session_id={openai_session_id}"
        )
        try:
            accept_response = await openai_realtime_sideband_adapter.accept_call(openai_session_id, session)
            _emit_voice_sip_trace(
                f"Voice SIP: accept_call succeeded for handoff_id={handoff_id} openai_session_id={openai_session_id} response_keys={sorted(accept_response.keys())}"
            )
            await _ensure_sideband_session(handoff_id, openai_session_id)
        except Exception:
            logger.exception(
                "Voice SIP: accept/bootstrap failed for handoff_id=%s openai_session_id=%s",
                handoff_id,
                openai_session_id,
            )
            raise
        accepted = True
    elif openai_session_id:
        _emit_voice_sip_trace(
            f"Voice SIP: ensuring sideband session for non-incoming event handoff_id={handoff_id} openai_session_id={openai_session_id}"
        )
        await _ensure_sideband_session(handoff_id, openai_session_id)

    if event_type in {
        "response.output_audio_transcript.done",
        "response.output_text.done",
        "conversation.item.input_audio_transcription.completed",
    }:
        _emit_voice_sip_trace(f"Voice SIP: appending transcript event handoff_id={handoff_id} event_type={event_type}")
        voice_sip_service.handle_openai_event(handoff_id, payload)

    _emit_voice_sip_trace(
        f"Voice SIP: webhook handled successfully handoff_id={handoff_id} event_type={event_type} accepted={accepted}"
    )

    return {
        "ok": True,
        "handoff_id": handoff_id,
        "openai_session_id": openai_session_id,
        "sip_call_id": sip_call_id,
        "accepted": accepted,
    }


@router.post("/sip/transcript")
def voice_sip_transcript(payload: SipTranscriptEvent) -> dict:
    try:
        handoff_service.get_handoff_context(payload.handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc

    voice_sip_service.handle_openai_event(
        payload.handoff_id,
        {
            "type": "response.output_audio_transcript.done" if payload.role == "assistant" else "conversation.item.input_audio_transcription.completed",
            "transcript": payload.content,
        },
    )
    return {"ok": True, "handoff_id": payload.handoff_id}


@router.post("/sip/finalize")
async def voice_sip_finalize(payload: SipFinalizeRequest) -> dict:
    try:
        handoff_service.get_handoff_context(payload.handoff_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Handoff not found.") from exc

    voice_sip_service.finalize_session(payload.handoff_id)
    await voice_sip_service.close_sideband(payload.handoff_id, openai_realtime_sideband_adapter)
    return {"ok": True, "handoff_id": payload.handoff_id}


async def _forward_openai_event(websocket: WebSocket, handoff_id: str, event: dict) -> None:
    print(
        f"Voice media: received OpenAI realtime event for handoff_id={handoff_id} event_type={event.get('type')}",
        flush=True,
    )
    if event.get("type") == "error":
        print(
            f"Voice media: OpenAI realtime error payload for handoff_id={handoff_id}: {json.dumps(event)}",
            flush=True,
        )
    logger.info(
        "Voice media: received OpenAI realtime event for handoff_id=%s event_type=%s",
        handoff_id,
        event.get("type"),
    )
    for twilio_event in twilio_media_bridge.handle_openai_server_event(handoff_id, event):
        print(
            f"Voice media: sending event back to Twilio for handoff_id={handoff_id}: {json.dumps(twilio_event)}",
            flush=True,
        )
        await websocket.send_text(json.dumps(twilio_event))
        logger.info(
            "Voice media: forwarded event back to Twilio for handoff_id=%s stream_event=%s",
            handoff_id,
            twilio_event.get("event"),
        )


async def _handle_openai_receive_result(
    websocket: WebSocket,
    handoff_id: str | None,
    openai_task: asyncio.Task,
) -> tuple[bool, dict | None]:
    try:
        event = openai_task.result()
    except ConnectionClosedOK as exc:
        print(
            f"Voice media: OpenAI realtime connection closed cleanly for handoff_id={handoff_id}: code={exc.code} reason={exc.reason!r}",
            flush=True,
        )
        logger.warning(
            "Voice media: OpenAI realtime connection closed cleanly for handoff_id=%s code=%s reason=%s",
            handoff_id,
            exc.code,
            exc.reason,
        )
        await websocket.close(code=1011, reason="OpenAI realtime closed")
        return False, None
    except ConnectionClosedError as exc:
        print(
            f"Voice media: OpenAI realtime connection closed with error for handoff_id={handoff_id}: code={exc.code} reason={exc.reason!r}",
            flush=True,
        )
        logger.warning(
            "Voice media: OpenAI realtime connection closed with error for handoff_id=%s code=%s reason=%s",
            handoff_id,
            exc.code,
            exc.reason,
        )
        await websocket.close(code=1011, reason="OpenAI realtime closed with error")
        return False, None
    except ConnectionClosed as exc:
        print(
            f"Voice media: OpenAI realtime connection closed for handoff_id={handoff_id}: {exc!r}",
            flush=True,
        )
        logger.warning(
            "Voice media: OpenAI realtime connection closed for handoff_id=%s",
            handoff_id,
        )
        await websocket.close(code=1011, reason="OpenAI realtime closed")
        return False, None

    await _forward_openai_event(websocket, handoff_id, event)
    return True, event


async def _connect_openai_realtime(handoff_id: str, session: dict) -> object:
    print(
        f"Voice media: opening OpenAI realtime connection for handoff_id={handoff_id} model={session['model']} voice={session['voice']}",
        flush=True,
    )
    logger.info(
        "Voice media: opening OpenAI realtime connection for handoff_id=%s model=%s voice=%s",
        handoff_id,
        session["model"],
        session["voice"],
    )
    try:
        realtime_connection = await asyncio.wait_for(
            twilio_media_bridge.openai_realtime_adapter.connect(session["model"]),
            timeout=5,
        )
    except Exception as exc:
        print(f"Voice media: OpenAI realtime connect failed: {exc!r}", flush=True)
        logger.exception("Voice media: OpenAI realtime connect failed for handoff_id=%s", handoff_id)
        raise
    print(f"Voice media: OpenAI realtime connection established for handoff_id={handoff_id}", flush=True)
    logger.info("Voice media: OpenAI realtime connection established for handoff_id=%s", handoff_id)
    return realtime_connection


async def _send_openai_bootstrap_events(handoff_id: str, realtime_connection: object, openai_events: list[dict]) -> None:
    for openai_event in openai_events:
        print(
            f"Voice media: sending bootstrap event to OpenAI realtime for handoff_id={handoff_id}: {json.dumps(openai_event)}",
            flush=True,
        )
        await twilio_media_bridge.openai_realtime_adapter.send_event(
            realtime_connection,
            openai_event,
        )
        logger.info(
            "Voice media: sent bootstrap event to OpenAI realtime for handoff_id=%s event_type=%s",
            handoff_id,
            openai_event.get("type"),
        )


@router.websocket("/media")
async def voice_media(websocket: WebSocket) -> None:
    await websocket.accept()
    realtime_connection = None
    handoff_id = None
    twilio_task: asyncio.Task | None = None
    openai_task: asyncio.Task | None = None
    openai_session: dict | None = None
    openai_bootstrap_events: list[dict] = []
    buffered_openai_events: deque[dict] = deque(maxlen=STARTUP_BUFFER_MAX_EVENTS)
    openai_session_updated = False
    openai_server_error_retried = False
    logger.info("Voice media: websocket accepted")
    try:
        waiting_for_first_frame = True
        while True:
            if waiting_for_first_frame:
                try:
                    raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=5)
                except asyncio.TimeoutError:
                    logger.error("Voice media: timed out waiting for first Twilio stream event")
                    await websocket.close(code=1008, reason="first Twilio stream event timed out")
                    return
            elif realtime_connection is None:
                raw_message = await websocket.receive_text()
            else:
                if twilio_task is None:
                    twilio_task = asyncio.create_task(websocket.receive_text())
                if openai_task is None:
                    openai_task = asyncio.create_task(
                        twilio_media_bridge.openai_realtime_adapter.receive_event(realtime_connection)
                    )
                done, _pending = await asyncio.wait(
                    {twilio_task, openai_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if openai_task in done:
                    completed_openai_task = openai_task
                    openai_task = None
                    should_continue, openai_event = await _handle_openai_receive_result(
                        websocket,
                        handoff_id,
                        completed_openai_task,
                    )
                    if not should_continue:
                        break
                    if (
                        openai_event
                        and openai_event.get("type") == "session.updated"
                    ):
                        openai_session_updated = True
                        if buffered_openai_events:
                            for buffered_openai_event in buffered_openai_events:
                                print(
                                    f"Voice media: flushing buffered event to OpenAI realtime for handoff_id={handoff_id}: {json.dumps(buffered_openai_event)}",
                                    flush=True,
                                )
                                await twilio_media_bridge.openai_realtime_adapter.send_event(
                                    realtime_connection,
                                    buffered_openai_event,
                                )
                                logger.info(
                                    "Voice media: flushed buffered audio/control event to OpenAI realtime for handoff_id=%s event_type=%s",
                                    handoff_id,
                                    buffered_openai_event.get("type"),
                                )
                            buffered_openai_events.clear()
                    if (
                        openai_event
                        and openai_event.get("type") == "error"
                        and openai_event.get("error", {}).get("type") == "server_error"
                        and realtime_connection is not None
                        and openai_session is not None
                        and not openai_server_error_retried
                    ):
                        openai_server_error_retried = True
                        print(
                            f"Voice media: retrying OpenAI realtime session after server_error for handoff_id={handoff_id}",
                            flush=True,
                        )
                        logger.warning(
                            "Voice media: retrying OpenAI realtime session after server_error for handoff_id=%s",
                            handoff_id,
                        )
                        await twilio_media_bridge.openai_realtime_adapter.close(realtime_connection)
                        buffered_openai_events.clear()
                        openai_session_updated = False
                        realtime_connection = await _connect_openai_realtime(handoff_id, openai_session)
                        await _send_openai_bootstrap_events(
                            handoff_id,
                            realtime_connection,
                            openai_bootstrap_events,
                        )
                        if twilio_task not in done:
                            continue
                    if twilio_task not in done:
                        continue

                raw_message = twilio_task.result()
                twilio_task = None
            event = twilio_media_bridge.parse_event(raw_message)
            logger.info("Voice media: received Twilio stream event type=%s", event.get("event"))
            waiting_for_first_frame = False

            if handoff_id is None:
                if event.get("event") == "connected":
                    logger.info("Voice media: received Twilio connected prelude")
                    continue
                if event.get("event") == "start":
                    print(f"Voice media: raw Twilio start event payload: {json.dumps(event)}", flush=True)
                    logger.error(
                        "Voice media: raw Twilio start event payload: %s",
                        json.dumps(event),
                    )
                handoff_id = twilio_media_bridge.extract_handoff_id(event)
                if not handoff_id:
                    logger.error(
                        "Voice media: missing handoff_id in Twilio start payload: %s",
                        json.dumps(event),
                    )
                    await websocket.close(code=1008, reason="handoff_id is required")
                    return
                print(f"Voice media: resolved handoff_id={handoff_id}", flush=True)
                logger.info("Voice media: resolved handoff_id=%s", handoff_id)

            if event.get("event") == "media":
                print(
                    f"Voice media: received Twilio media frame for handoff_id={handoff_id} sequence={event.get('sequenceNumber')}",
                    flush=True,
                )
                logger.info(
                    "Voice media: received Twilio media frame for handoff_id=%s sequence=%s",
                    handoff_id,
                    event.get("sequenceNumber"),
                )

            result = twilio_media_bridge.handle_stream_event(handoff_id, event)

            if event.get("event") == "start":
                openai_session = result["session"]
                openai_bootstrap_events = list(result.get("openai_events", []))
                buffered_openai_events.clear()
                openai_session_updated = False
                openai_server_error_retried = False
                realtime_connection = await _connect_openai_realtime(handoff_id, openai_session)
                await _send_openai_bootstrap_events(
                    handoff_id,
                    realtime_connection,
                    openai_bootstrap_events,
                )
                continue

            if realtime_connection and result.get("openai_events"):
                if not openai_session_updated:
                    prior_buffer_count = len(buffered_openai_events)
                    buffered_openai_events.extend(result["openai_events"])
                    dropped_event_count = max(
                        0,
                        prior_buffer_count + len(result["openai_events"]) - STARTUP_BUFFER_MAX_EVENTS,
                    )
                    logger.info(
                        "Voice media: buffering %s audio/control events until session.updated for handoff_id=%s buffered_count=%s dropped_count=%s",
                        len(result["openai_events"]),
                        handoff_id,
                        len(buffered_openai_events),
                        dropped_event_count,
                    )
                else:
                    for openai_event in result["openai_events"]:
                        print(
                            f"Voice media: sending event to OpenAI realtime for handoff_id={handoff_id}: {json.dumps(openai_event)}",
                            flush=True,
                        )
                        await twilio_media_bridge.openai_realtime_adapter.send_event(
                            realtime_connection,
                            openai_event,
                        )
                        logger.info(
                            "Voice media: forwarded audio/control event to OpenAI realtime for handoff_id=%s event_type=%s",
                            handoff_id,
                            openai_event.get('type'),
                        )
            elif realtime_connection and result.get("openai_event"):
                if not openai_session_updated:
                    prior_buffer_count = len(buffered_openai_events)
                    buffered_openai_events.append(result["openai_event"])
                    dropped_event_count = max(
                        0,
                        prior_buffer_count + 1 - STARTUP_BUFFER_MAX_EVENTS,
                    )
                    logger.info(
                        "Voice media: buffering audio/control event until session.updated for handoff_id=%s event_type=%s buffered_count=%s dropped_count=%s",
                        handoff_id,
                        result["openai_event"].get("type"),
                        len(buffered_openai_events),
                        dropped_event_count,
                    )
                else:
                    print(
                        f"Voice media: sending event to OpenAI realtime for handoff_id={handoff_id}: {json.dumps(result['openai_event'])}",
                        flush=True,
                    )
                    await twilio_media_bridge.openai_realtime_adapter.send_event(
                        realtime_connection,
                        result["openai_event"],
                    )
                    logger.info(
                        "Voice media: forwarded audio/control event to OpenAI realtime for handoff_id=%s event_type=%s",
                        handoff_id,
                        result['openai_event'].get('type'),
                    )

            if result.get("twilio_event"):
                await websocket.send_text(json.dumps(result["twilio_event"]))
                logger.info(
                    "Voice media: forwarded event to Twilio for handoff_id=%s event_type=%s",
                    handoff_id,
                    result['twilio_event'].get('event'),
                )

            if event.get("event") == "stop":
                logger.info("Voice media: received stop event for handoff_id=%s", handoff_id)
                break
    except WebSocketDisconnect:
        if handoff_id is None:
            logger.error("Voice media: websocket disconnected before first Twilio stream event")
        else:
            logger.info("Voice media: websocket disconnected for handoff_id=%s", handoff_id)
        return
    except Exception:
        logger.exception("Voice media: relay failure", extra={"handoff_id": handoff_id})
        raise
    finally:
        pending_tasks = [task for task in (twilio_task, openai_task) if task is not None]
        for task in pending_tasks:
            task.cancel()
        if pending_tasks:
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        if realtime_connection is not None:
            await twilio_media_bridge.openai_realtime_adapter.close(realtime_connection)
            logger.info("Voice media: OpenAI realtime connection closed for handoff_id=%s", handoff_id)
