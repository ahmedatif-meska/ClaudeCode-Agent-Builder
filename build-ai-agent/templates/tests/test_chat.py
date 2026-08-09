"""Chat endpoint tests with the model call stubbed out — no network, no API key needed."""

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api.chat as chat_module
from app.main import app


@pytest.fixture
def stub_agent_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_session(conversation_id: str | None) -> Any:
        return SimpleNamespace(session_id=conversation_id or "conv_test")

    async def fake_run(agent: Any, message: str, **kwargs: Any) -> Any:
        assert kwargs["max_turns"] > 0, "requests must be bounded"
        return SimpleNamespace(final_output=f"echo: {message}")

    monkeypatch.setattr(chat_module, "_session", fake_session)
    monkeypatch.setattr(chat_module.Runner, "run", staticmethod(fake_run))


def test_chat_returns_a_reply_and_a_conversation_id(stub_agent_run: None) -> None:
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json() == {"reply": "echo: hello", "conversation_id": "conv_test"}


def test_chat_continues_an_existing_conversation(stub_agent_run: None) -> None:
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "again", "conversation_id": "conv_42"})

    assert response.json()["conversation_id"] == "conv_42"


def test_empty_message_is_rejected() -> None:
    with TestClient(app) as client:
        assert client.post("/chat", json={"message": ""}).status_code == 422


def test_stream_emits_the_conversation_id_first_then_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_session(conversation_id: str | None) -> Any:
        return SimpleNamespace(session_id="conv_stream")

    class FakeStream:
        is_complete = True

        async def stream_events(self) -> Any:
            for chunk in ("Hel", "lo"):
                yield SimpleNamespace(
                    type="raw_response_event",
                    data=_text_delta(chunk),
                )

        def cancel(self) -> None:  # pragma: no cover - only on client disconnect
            pass

    monkeypatch.setattr(chat_module, "_session", fake_session)
    monkeypatch.setattr(
        chat_module.Runner, "run_streamed", staticmethod(lambda *a, **kw: FakeStream())
    )

    with TestClient(app) as client:
        with client.stream("POST", "/chat/stream", json={"message": "hi"}) as response:
            assert response.status_code == 200
            body = "".join(response.iter_text())

    events = [line for line in body.splitlines() if line.startswith("data: ")]
    assert '"conversation"' in events[0], "client needs the id before the first delta"
    assert '"text": "Hel"' in events[1]
    assert '"done"' in events[-1]


def _text_delta(text: str) -> Any:
    from openai.types.responses import ResponseTextDeltaEvent

    return ResponseTextDeltaEvent(
        type="response.output_text.delta",
        delta=text,
        content_index=0,
        item_id="item_1",
        output_index=0,
        sequence_number=0,
        logprobs=[],
    )
