# Gotchas

Each of these is encoded in a template. Read the entry before "simplifying" the code that
handles it.

### 1. Probe the installed SDK; do not recall its API

`openai-agents` changes shape between minor versions. Verified on 0.19.4 / `openai` 2.53:

- `SQLiteSession` is importable from `agents` but does **not** appear in `dir(agents)` — a
  `dir()` check will wrongly tell you it is gone.
- `client.vector_stores.files.delete(file_id, *, vector_store_id=...)` — file id positional,
  store id keyword-only. The mirror-image call fails.
- The default model comes from `agents.models.default_models.get_default_model()`. Leave
  `AGENT_MODEL` unset rather than pinning a model string that may not exist on the account.

```bash
python -c "import inspect, agents; print(inspect.signature(agents.Runner.run))"
```

### 2. `app/mcp/` shadows the installed `mcp` package

Under pytest's default import mode the app directory can land on `sys.path`, and
`import mcp` then resolves to your package. Errors are baffling. The template uses
`app/mcp_servers/`.

### 3. MCP connect and cleanup must happen in the same task

MCP sessions use task-scoped cancel scopes. Connecting during startup and cleaning up from a
different task raises `Attempted to exit cancel scope in a different task`. The FastAPI
lifespan generator satisfies this; a background task that connects and a shutdown hook that
cleans up does not.

### 4. `TestClient` without `with` skips the lifespan

`app.state.agent` is then missing and every test fails with `AttributeError`. Always
`with TestClient(app) as client:`.

### 5. Tracing tries to phone home during tests

The SDK exports traces by default. `set_tracing_disabled(True)` in `tests/conftest.py`, and
set the fake key **before** importing the app — `get_settings()` is `lru_cache`d, so the
first import wins for the whole session.

### 6. `OpenAIConversationsSession.session_id` raises before first use

Constructed without a `conversation_id`, the id does not exist until a remote call happens.
Create the conversation explicitly with `start_openai_conversations_session(client)` and pass
the id in — the template does this so the id can be returned to the client on turn one.

### 7. Vector-store entries carry no filename

`VectorStoreFile` has `id, status, usage_bytes, last_error, attributes` — no filename. Store
it in `attributes={"filename": ...}` at attach time, or listing costs one extra API call per
file.

### 8. `UploadFile` needs `python-multipart`

Without it FastAPI raises at route-definition time with a message about form data. It is in
the template's dependencies.

### 9. One client, one event loop

A new `AsyncOpenAI` per request leaks connections and adds a TLS handshake to every call.
The template caches one and registers it with `set_default_openai_client(client,
use_for_tracing=True)` so the SDK's own calls use the same key and pool.

### 10. Sync calls block every concurrent request

An `async def` endpoint runs on the event loop. One blocking database or HTTP call inside it
stalls every other in-flight request. Use the async client, or
`await asyncio.to_thread(blocking_fn, ...)`.

### 11. Unbounded runs hang requests

Without `max_turns`, a tool that keeps returning "try again" runs until something times out.
Pass it on every `Runner.run` / `run_streamed` and return 504 on `MaxTurnsExceeded`.

### 12. Abandoned streams keep billing

If the browser disconnects mid-stream, the run continues. Call `result.cancel()` in a
`finally` when `not result.is_complete`.

### 13. `CORS_ORIGINS` is parsed as JSON

pydantic-settings parses list fields as JSON: `CORS_ORIGINS=["http://localhost:3000"]`.
`CORS_ORIGINS=http://localhost:3000` raises a validation error at startup.

### 14. Green tests do not mean a working agent

Every test in the template stubs the model. They prove wiring, validation and lifecycle
logic. Only a run against a real `OPENAI_API_KEY` proves the agent works.

### 15. A *bad* MCP token can fail worse than *no* token

Measured against Google's hosted Gmail MCP server (`gmailmcp.googleapis.com`):

| request | no `Authorization` header | invalid Bearer token |
|---|---|---|
| `initialize` | 200 | 200 |
| `tools/list` | 200 (full tool list) | **401** |
| `tools/call` | 401 | 401 |

Two traps. An anonymous `list_tools()` can succeed, so it verifies the transport and says
nothing about authorization — only a real `call_tool` does. And the 401 from a rejected
token surfaces through the MCP client as a bare `asyncio.CancelledError` ("Cancelled via
cancel scope 0x…") from inside anyio, with no mention of auth anywhere in the traceback.

Wrap `connect()` and translate it, or the symptom of an expired refresh token is an
unreadable stack trace:

```python
try:
    await server.connect()
    tools = await server.list_tools()
except (Exception, asyncio.CancelledError) as exc:   # startup-only path
    raise RuntimeError(f"Could not connect to {url} — check the credential. {exc}") from exc
```

Then make one real read call at startup, so a stale token fails at boot rather than as a
502 on the first user request.

### 16. Expiring OAuth tokens need `auth=`, not `headers=`

`headers={"Authorization": f"Bearer {token}"}` is fixed when the server object is
constructed. For any provider whose access tokens expire — Google's last about an hour —
the app works during testing and starts failing later. Pass an `httpx.Auth` on the params
instead; the MCP client applies it per request, so it can refresh:

```python
params={"url": url, "auth": MyRefreshingAuth(...)}
```
