# Claude Code — AI Agent Builder

A Claude Code skill that turns a plain-English description of an agent into a running
**Python + FastAPI** backend built on the **OpenAI Agents SDK**.

It is not a fixed template. The architecture is derived from what you describe: most agents
need a model, a prompt, and one or two tools, so RAG, MCP, extra agents, databases and
background jobs only appear when something you said actually calls for them.

Two capabilities are never added silently. If your description implies **MCP** or **RAG**, the
skill explains why, names the specific server or approach, and asks — before it searches for
anything, installs anything, or writes a line of code.

## Install

```bash
git clone https://github.com/ahmedatif-meska/ClaudeCode-Agent-Builder.git
cd ClaudeCode-Agent-Builder
./install.sh
```

`install.sh` symlinks the skill into `~/.claude/skills/`, so `git pull` updates your installed
copy. Start a new Claude Code session afterwards.

## Use

Describe the agent, or invoke the skill by name:

```
/build-ai-agent
```

```
I want an agent that answers customer questions from our product PDFs
and can look up order status in our internal API.
```

The skill then works through seven phases:

| Phase | What happens |
|---|---|
| **0 · Understand** | Asks what the agent should do, know, and reach. Nothing is built yet. |
| **1 · Analyze** | Emits a capability table — yes/no **plus the evidence** for tools, RAG, MCP, web search, structured output, memory, multi-agent, database, background jobs, auth. The *no* rows are what prevent scope creep. |
| **2 · Confirm** | Blocks on MCP and RAG. Explains, asks, waits. Only after a yes does it check whether the MCP is available. |
| **3 · Plan** | A plan short enough to correct in one reply. |
| **4 · Build** | Copies only the templates the confirmed capabilities need; deletes the rest. |
| **5 · Verify** | `pytest`, then a live run against a real API key. Green tests are explicitly *not* treated as proof the agent works. |
| **6 · Explain** | What was built, what was declined, how any MCP was verified, what config you still owe. |

## What ships

```
build-ai-agent/
├── SKILL.md                        # the seven-phase protocol and its guardrails
├── reference/
│   ├── requirements-analysis.md    # signal → capability mapping, sane defaults
│   ├── mcp.md                      # what to do only AFTER you say yes
│   ├── rag-file-search.md          # one vector store, per-file add and delete
│   ├── agents-sdk.md               # verified SDK surface, not recalled from memory
│   └── gotchas.md                  # 14 non-obvious failure modes
└── templates/                      # a working FastAPI app with 12 passing tests
```

### The generated app

```
Agent orchestration  →  Tools / MCP  →  Knowledge (File Search)  →  API  →  FastAPI
```

- `async def` throughout; blocking calls isolated with `asyncio.to_thread`.
- `POST /chat` and a streaming `POST /chat/stream` (SSE, with tool-activity events).
- `GET /health` reports the tools and MCP servers that *actually* loaded — the fastest way to
  catch a capability that silently failed to configure.
- Conversation memory via OpenAI Conversations, so there is no database to run.
- RAG, when confirmed, uses OpenAI-managed File Search: one vector store, reused; adding a
  file indexes only that file; deleting one removes only that file.
- Secrets stay server-side and never appear in a response model.
- Tracing is on by default — runs, model calls, tool calls and File Search are inspectable at
  [platform.openai.com/traces](https://platform.openai.com/traces).

### Never introduced

LangChain · LangGraph · LlamaIndex · Pinecone · Qdrant · Weaviate · Chroma · custom chunking ·
custom embeddings · custom similarity search · a background-job framework *for monitoring* ·
a database the requirements did not ask for.

The Agents SDK plus hosted File Search covers orchestration and retrieval. Anything above gets
added only when you ask for it by name.

## Verified against

`openai-agents 0.19.4` · `openai 2.53.0` · `fastapi 0.141.1` · Python 3.11+

Signatures in `reference/agents-sdk.md` were read off the installed packages rather than
recalled, and `reference/gotchas.md` records what that turned up — the keyword-only
`vector_store_id` on file deletion, the vector-store entry that carries no filename, the
`app/mcp/` directory that shadows the installed `mcp` package under pytest. The SDK moves
fast; probe before trusting any call the reference does not list.

The shipped templates boot under `uvicorn` and pass their test suite as-is. Those tests stub
the model, so they prove wiring and lifecycle, not agent behaviour — which is why Phase 5
insists on the live run.

## License

MIT
