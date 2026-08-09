# Requirements analysis: description → capabilities

Read the user's description once for **what the agent must be able to do**, and once for
**what it must be able to reach**. Everything below maps observable signals to a capability.
A signal that is absent means the capability is absent — silence is not ambiguity.

## Signal table

| Signal in the description | Capability | Confirm first? |
|---|---|---|
| "answer questions about", "from our docs/PDFs/handbook", "users upload files", "internal documentation" | RAG via File Search | **Yes** |
| A named third-party system (Slack, GitHub, Notion, Linear, Jira, Google Drive, a database UI) | MCP, or a direct API tool | **Yes** (MCP) |
| "look up", "fetch", "check the status of", "create a record in" against *their own* system | Custom function tool | No |
| "current", "latest", "today's", "news", "what's happening with" | `WebSearchTool` | No |
| "return JSON", "fill in this form", "extract these fields", downstream code consumes the output | `output_type=` Pydantic model | No |
| "remember", "follow-up questions", "conversation", "chat" | Session (conversation memory) | No |
| Two or more genuinely different jobs with different tools/instructions ("triage *then* draft") | Handoffs or agents-as-tools | No |
| "every morning", "when an email arrives", "runs for an hour", "process 10k rows" | Background execution / scheduling | No |
| "our users", "each customer sees only their own", "log in" | Auth + per-tenant scoping | No |
| "store", "history", "audit", "dashboard of past runs" | Database | No |
| Incoming events from an external system ("when someone posts in Slack…") | Webhook endpoint (in addition to, not instead of, the chat API) | No |

## MCP vs. a custom tool

Prefer MCP when the target is a well-known third-party system with a maintained server and
the agent needs several of its operations. Prefer a custom `@function_tool` when:

- The target is the user's own service or database.
- Only one or two narrow operations are needed (an MCP drags in dozens of tools).
- The call needs business logic, validation, or a permission check the agent must not bypass.

Either way, the MCP route requires confirmation before you go looking for a server.

## Questions worth asking, and questions that are not

Ask when the answer changes the architecture:

- Who uses this — one person, a team, or your customers? *(auth, per-tenant knowledge bases)*
- Should it hold a conversation, or answer one question at a time? *(sessions)*
- Does anything consume the output as data rather than prose? *(structured output)*
- Should it take actions, or only report? *(write tools, approvals)*
- Roughly how many documents, and do they change often? *(one store vs. per-tenant stores)*

Do not ask about anything you can pick a sane default for: model, chunk size, ranking
options, table layout, port numbers.

## Reasonable defaults

| Decision | Default | Change when |
|---|---|---|
| Model | Agents SDK default (leave `AGENT_MODEL` unset) | The user names a model, or needs a cheaper/faster tier |
| Memory | `OpenAIConversationsSession` — no infrastructure | History must stay in their infrastructure → SQLAlchemy/Redis session |
| `max_turns` | 10 | Deep tool chains need more; strict latency budgets need fewer |
| Vector stores | One, shared | Per-tenant isolation is required |
| Streaming | Provide `/chat/stream` when there is a UI | Service-to-service only → drop it |
| Deployment | `uvicorn` locally, the user's platform for prod | They name a target |
