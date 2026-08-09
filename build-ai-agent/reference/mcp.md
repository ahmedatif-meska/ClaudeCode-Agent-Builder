# MCP: checking, connecting, verifying

**Read this only after the user has said yes.** Everything here is a step that must not
happen before consent — searching for a server, reading credentials, installing anything.

Two different things get called "MCP" in this work, and confusing them wastes a lot of time:

| | What it is |
|---|---|
| **Claude Code's MCP servers** | Tools *you* (the builder) can call in this session. Useful as evidence of what the user already has configured and authenticated. |
| **The agent's MCP servers** | Tools the *built agent* calls at runtime, wired through `agents.mcp` or `HostedMCPTool`. This is what you are building. |

A server configured in Claude Code is not automatically available to the user's FastAPI app.

## 1. Check availability

In order, stopping at the first answer:

```bash
claude mcp list                  # already configured in this environment?
```

Then check whether a server exists at all for the target system: its official docs, the
vendor's own hosted MCP endpoint, or the public registry. Prefer, in order:

1. **A vendor-hosted remote MCP endpoint** (an HTTPS URL) — nothing to install or run.
2. **A maintained official server** run as a local process.
3. **A community server** — say so explicitly; the user is taking on the risk.

If nothing exists: say so plainly, and propose the alternative (a `@function_tool` over the
system's REST API, or a webhook). Do not invent a package name.

## 2. Choose the transport

| Transport | Class | Use when |
|---|---|---|
| Remote HTTP | `MCPServerStreamableHttp` | The server has an HTTPS URL. Default for a deployed backend. |
| Local process | `MCPServerStdio` | Only a local/npx/uvx server exists **and** you control the runtime that hosts it. Needs the binary inside the container. |
| OpenAI-hosted | `HostedMCPTool` | OpenAI should call the server directly — it must be publicly reachable, and your backend never sees the traffic. |
| Legacy SSE | `MCPServerSse` | The server predates streamable HTTP. |

```python
from agents.mcp import MCPServerStreamableHttp

server = MCPServerStreamableHttp(
    name="linear",
    params={"url": url, "headers": {"Authorization": f"Bearer {token}"}, "timeout": 30},
    cache_tools_list=True,
    client_session_timeout_seconds=30,
)
```

`HostedMCPTool` instead takes a config dict: `{"type": "mcp", "server_label": ...,
"server_url": ..., "require_approval": "never", "allowed_tools": [...]}`.

## 3. Connect and verify — this is the part that counts

```python
await server.connect()
tools = await server.list_tools()
print([t.name for t in tools])

# list_tools() alone is NOT proof of access — some servers list tools anonymously and only
# reject the actual call. Make one real, read-only call and look at what comes back.
print(await server.call_tool("<a read tool>", {...}))
```

The agent is only wired up once a real call returns real data. Until then:

- Do not say "connected".
- Do not say "the Slack MCP is set up".
- Do not proceed to write agent code that assumes a tool name.

If `connect()` fails or the list is empty or missing what you need, report the actual error
and what is missing — a token, a scope, a URL, a server that does not exist. **Never guess at
credentials, env var names, or OAuth scopes.** Ask.

## 4. Wire it into the app

- Connect once in the FastAPI lifespan, before `build_agent(...)`; clean up in the same task
  (MCP sessions use task-scoped cancel scopes — connecting in one task and cleaning up in
  another raises `Attempted to exit cancel scope in a different task`).
- `cache_tools_list=True`, or the SDK re-fetches the tool list on every single run.
- Filter the tools: `tool_filter=create_static_tool_filter(allowed_tool_names=[...])`. A
  server exposing 40 tools degrades tool selection and inflates every prompt.
- Gate destructive operations with `require_approval` rather than trusting the prompt.
- The token belongs in `app/config.py` from the environment. It never appears in a response.

`templates/app/mcp_servers/connection.py` implements all of the above. For a provider with
expiring tokens, pass an `httpx.Auth` on `params` rather than a static `headers` entry —
see gotchas #15 and #16.

## 5. When the user says no

Do not search for the server. Do not leave the code in place "for later". Offer the
alternative — a narrow custom tool over the system's API, a webhook, or dropping the
integration — and update the capability table to record the decision.
