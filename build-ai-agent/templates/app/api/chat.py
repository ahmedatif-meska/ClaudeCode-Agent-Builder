"""Chat endpoints: one JSON round-trip, one SSE stream.

Keep both only if the frontend needs both. Streaming is what makes a tool-using agent
feel responsive; the JSON endpoint is what other services will call.
"""

import json
from collections.abc import AsyncIterator

from agents import (
    Agent,
    InputGuardrailTripwireTriggered,
    MaxTurnsExceeded,
    OpenAIConversationsSession,
    OutputGuardrailTripwireTriggered,
    Runner,
    trace,
)
from agents.memory.openai_conversations_session import start_openai_conversations_session
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent

from app.config import get_settings
from app.models.schemas import ChatRequest, ChatResponse
from app.openai_client import get_openai_client

router = APIRouter(tags=["chat"])


def _agent(request: Request) -> Agent:
    return request.app.state.agent


async def _session(conversation_id: str | None) -> OpenAIConversationsSession:
    """Conversation history lives in OpenAI Conversations — no database to run.

    Swap for SQLiteSession / SQLAlchemySession only if history must stay in your
    own infrastructure.
    """
    client = get_openai_client()
    if conversation_id is None:
        conversation_id = await start_openai_conversations_session(client)
    return OpenAIConversationsSession(
        conversation_id=conversation_id, openai_client=client
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    settings = get_settings()
    session = await _session(payload.conversation_id)

    try:
        with trace("chat", group_id=session.session_id):
            result = await Runner.run(
                _agent(request),
                payload.message,
                session=session,
                max_turns=settings.max_turns,
            )
    except MaxTurnsExceeded as exc:
        raise HTTPException(
            status_code=504, detail="The agent exceeded its turn limit."
        ) from exc
    except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered) as exc:
        raise HTTPException(status_code=400, detail="Request blocked by a guardrail.") from exc

    return ChatResponse(reply=str(result.final_output), conversation_id=session.session_id)


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    settings = get_settings()
    session = await _session(payload.conversation_id)
    agent = _agent(request)

    async def events() -> AsyncIterator[str]:
        # The client needs the id before the first turn finishes so it can continue
        # the conversation even if the stream is interrupted.
        yield _sse({"type": "conversation", "conversation_id": session.session_id})

        result = Runner.run_streamed(
            agent, payload.message, session=session, max_turns=settings.max_turns
        )
        try:
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    yield _sse({"type": "delta", "text": event.data.delta})
                elif event.type == "run_item_stream_event":
                    # Surface tool activity so the UI can show "searching…" instead of
                    # a silent pause while a tool runs.
                    if event.item.type == "tool_call_item":
                        yield _sse({"type": "tool_call"})
            yield _sse({"type": "done"})
        except MaxTurnsExceeded:
            yield _sse({"type": "error", "message": "The agent exceeded its turn limit."})
        except (InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered):
            yield _sse({"type": "error", "message": "Request blocked by a guardrail."})
        except Exception:  # noqa: BLE001 - never leak an internal error to the client
            yield _sse({"type": "error", "message": "The agent failed to complete."})
            raise
        finally:
            # If the browser goes away mid-stream, stop paying for the run.
            if not result.is_complete:
                result.cancel()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload)}\n\n"
