# OpenAI Agents SDK (Python) — verified surface

Signatures below were read off an installed `openai-agents==0.19.4` with `openai==2.53.0`.
The SDK moves fast: before trusting any call not listed here, probe the installed package
rather than recalling it.

```bash
python -c "import inspect, agents; print(inspect.signature(agents.Runner.run))"
python -c "import agents; print([n for n in dir(agents) if not n.startswith('_')])"
```

## Agent

```python
from agents import Agent

agent = Agent(
    name="Assistant",
    instructions="...",          # str, or a callable for dynamic instructions
    model=None,                  # None => SDK default model
    tools=[],                    # hosted tools + @function_tool functions
    mcp_servers=[],              # connected MCPServer instances
    output_type=None,            # a Pydantic model => structured output
    handoffs=[],                 # other Agents this one can transfer to
    input_guardrails=[],
    output_guardrails=[],
    model_settings=None,         # ModelSettings(temperature=..., tool_choice=..., ...)
)
```

Constructor fields: `name, instructions, prompt, handoff_description, handoffs, model,
model_settings, tools, mcp_servers, mcp_config, input_guardrails, output_guardrails,
output_type, hooks, tool_use_behavior, reset_tool_choice`.

## Running

```python
from agents import Runner

result = await Runner.run(agent, "user message", session=session, max_turns=10)
result.final_output          # str, or an instance of output_type
result.to_input_list()       # full transcript, if you manage history yourself
```

`Runner.run(starting_agent, input, *, context=None, max_turns=10, hooks=None,
run_config=None, previous_response_id=None, conversation_id=None, session=None)`.
`Runner.run_streamed(...)` takes the same arguments and returns immediately.
`Runner.run_sync(...)` exists — never use it inside FastAPI.

## Streaming

```python
from openai.types.responses import ResponseTextDeltaEvent

result = Runner.run_streamed(agent, message, session=session, max_turns=10)
async for event in result.stream_events():
    if event.type == "raw_response_event" and isinstance(event.data, ResponseTextDeltaEvent):
        ...  # event.data.delta is the token text
    elif event.type == "run_item_stream_event":
        event.item.type  # "tool_call_item" | "tool_call_output_item" | "message_output_item"
    elif event.type == "agent_updated_stream_event":
        event.new_agent  # a handoff happened
```

`result.is_complete`, `result.cancel()`. Call `cancel()` when the client disconnects —
otherwise the run keeps going and keeps billing.

## Tools

```python
from agents import function_tool

@function_tool
async def lookup(order_id: str) -> str:
    """Look up an order's status.

    Args:
        order_id: The order identifier.
    """
```

The docstring becomes the description the model reads; annotations become the JSON schema.
Useful options: `name_override`, `is_enabled` (static or callable), `needs_approval`,
`timeout`, `failure_error_function`.

Hosted tools (run on OpenAI's side, no code from you):

| Tool | Signature highlights |
|---|---|
| `FileSearchTool` | `(vector_store_ids, max_num_results=None, include_search_results=False, ranking_options=None, filters=None)` |
| `WebSearchTool` | `(user_location=None, filters=None, search_context_size="medium")` |
| `CodeInterpreterTool`, `ImageGenerationTool`, `ComputerTool`, `ShellTool` | see `dir(agents)` |

## Structured output

```python
from pydantic import BaseModel

class Triage(BaseModel):
    category: str
    urgency: int
    summary: str

agent = Agent(name="Triage", instructions="...", output_type=Triage)
result = await Runner.run(agent, text)
result.final_output.category      # typed, already validated
```

Use it whenever anything other than a human reads the output. Keep the model flat and
required-by-default; optional unions make the schema harder for the model to satisfy.

## Sessions (conversation memory)

| Session | Storage | Use when |
|---|---|---|
| `OpenAIConversationsSession(conversation_id=..., openai_client=...)` | OpenAI Conversations | Default — no infrastructure to run |
| `SQLiteSession(session_id, db_path)` | local sqlite (blocking) | Single-process scripts only |
| `agents.extensions.memory.async_sqlite_session.AsyncSQLiteSession` | sqlite via `aiosqlite` | Local, async, needs the `aiosqlite` extra |
| `...memory.sqlalchemy_session` / `redis_session` / `mongodb_session` | your database | History must stay in your infrastructure |

Create a conversation id explicitly on the first turn:

```python
from agents.memory.openai_conversations_session import start_openai_conversations_session
conversation_id = await start_openai_conversations_session(client)
```

`OpenAIConversationsSession.session_id` raises if the session was constructed without an id
and has not made a call yet — pass the id in, as the template does.

## Multi-agent

```python
triage = Agent(name="Triage", instructions="...", handoffs=[billing_agent, support_agent])
```

`handoff(agent, tool_name_override=..., on_handoff=..., input_type=..., input_filter=...)`
for control over the transfer. Alternative shape, when the caller should stay in charge:

```python
tools=[research_agent.as_tool(tool_name="research", tool_description="Research a topic")]
```

Handoff = transfer control. As-tool = call and come back. Two agents are worth it only when
the jobs need different instructions or different tools; otherwise it is one agent.

## Guardrails

```python
from agents import GuardrailFunctionOutput, input_guardrail

@input_guardrail
async def block_pii(ctx, agent, user_input) -> GuardrailFunctionOutput:
    return GuardrailFunctionOutput(output_info=..., tripwire_triggered=bool(...))
```

A tripwire raises `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered` —
catch both at the API boundary and return 400.

## Tracing

Tracing is on by default and exports to platform.openai.com/traces using the configured key.

```python
from agents import trace
with trace("chat", group_id=conversation_id):
    result = await Runner.run(agent, message)
```

`group_id` links every run in one conversation. `custom_span()` for your own spans,
`set_tracing_disabled(True)` in tests. This is the observability layer — do not add a
background-job framework to get it.

## Errors worth catching

| Exception | Meaning |
|---|---|
| `MaxTurnsExceeded` | Hit `max_turns` — usually a tool loop |
| `InputGuardrailTripwireTriggered` / `OutputGuardrailTripwireTriggered` | Guardrail fired |
| `ModelBehaviorError` | Malformed tool call / unparseable output |
| `UserError` | The SDK was used wrongly — a bug in your code |
| `ToolTimeoutError` | A `@function_tool` exceeded its `timeout` |
