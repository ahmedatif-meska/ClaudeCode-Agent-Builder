---
name: build-ai-agent
description: Use when someone describes an AI agent they want built or scaffolded — one that answers from their documents, calls their APIs, reaches external systems like Slack or Notion, or automates a task — and the backend is or can be Python + FastAPI + the OpenAI Agents SDK. Also use when adding tools, RAG, MCP, structured outputs, or multi-agent handoffs to an existing agent backend.
---

# Build an AI Agent (Python + FastAPI + OpenAI Agents SDK)

## Overview

Turns a natural-language description into a running FastAPI backend on the OpenAI Agents SDK.
**The architecture is derived from the description, never assumed.** Most agents need a model,
a prompt, and one or two tools. RAG, MCP, extra agents, databases and background jobs each
cost latency, failure modes and maintenance, and have to be earned by something the user said.

Two capabilities are never added silently: **MCP** and **RAG**. Both are explained and
confirmed before anything is searched for, installed, or built.

```
Description → Capability table → Confirm MCP/RAG → Plan → Build → Verify live → Explain
```

## When to use

"I want an agent that…", "build me a bot that…", or adding a tool / RAG / MCP / handoff /
structured output to an agent backend, on Python + FastAPI + `openai-agents`.

**Not for:** a plain one-shot LLM call with no tools, state or API surface; Next.js/TypeScript
document-Q&A apps (use `build-rag-app`); non-OpenAI orchestration layers.

## Phase 0 — Ask before anything else

Unless the description was already given in full, ask exactly this and stop:

> Describe what you want your agent to do, including the tasks it should perform, the
> information it should have access to, and any external systems it may need to interact with.

No scaffolding, searching, installing, or reading reference files until an answer arrives.

## Phase 1 — Capability table

Read `reference/requirements-analysis.md` for the signal → capability mapping, then output one
table: a **yes/no plus the evidence** for each of custom function tools, RAG, MCP, web search,
structured output, conversation memory, multiple agents, database, background jobs, auth.

| Capability | Needed? | Evidence from the description |
|---|---|---|
| RAG (File Search) | yes | "answer questions from our policy PDFs" |
| Database | no | not mentioned |

Include the **no** rows — they are what stops scope creep later. "Not mentioned" is valid
evidence and it means no. Ask about a genuine ambiguity; never resolve one by building.

## Phase 2 — Confirm MCP and RAG (blocking)

### MCP — explain, ask, *then* look

The order is fixed. Checking availability first makes the question a formality and starts
installs nobody agreed to.

```
Suspect an MCP helps
   → Explain: why, what capability, which server
   → Ask → WAIT
   → yes: check availability → connect → verify tools → use
   → no:  don't search for it; offer the alternative (direct API tool, webhook, drop it)
```

> Your agent needs access to <system> in order to <task from their description>. I recommend
> the <name> MCP because it provides <capability>. Do you want to use this MCP?

After a yes, follow `reference/mcp.md`. **Never call an MCP "connected" on the strength of a
config file — only on a successful `list_tools()`.**

### RAG — explain, ask, then build with File Search

> Based on your description, the agent needs to answer questions using <their documents>.
> I recommend a RAG knowledge base using OpenAI File Search, which lets the agent search
> those files without us building an embedding or vector-database pipeline. Do you want to
> add this RAG capability?

After a yes, build per `reference/rag-file-search.md`.

## Phase 3 — Plan

Short enough to correct in one reply: endpoints, tools, confirmed capabilities, files being
created, and what is deliberately left out.

## Phase 4 — Build

Copy from `templates/` — verified against `openai-agents 0.19.4` / `openai 2.53` /
`fastapi 0.141`, test suite green as shipped.

| Always | Only if confirmed |
|---|---|
| `pyproject.toml`, `.env.example`, `app/config.py`, `app/openai_client.py` | **RAG:** `app/rag/*`, `app/api/files.py`, `scripts/create_vector_store.py`, `tests/test_rag_files.py` |
| `app/agents/{factory,tools}.py`, `app/api/{health,chat}.py`, `app/models/schemas.py` | **MCP:** `app/mcp_servers/connection.py` |
| `app/main.py`, `tests/{conftest,test_health,test_chat}.py` | **Custom tools:** fill in `app/agents/tools.py` |

`main.py` and `factory.py` ship with optional wiring commented out — uncomment what was
confirmed and **delete the rest**; dead capability code gets re-enabled by accident.

Read `reference/agents-sdk.md` before writing agent code, `reference/gotchas.md` before
changing anything a template already handles. Non-negotiable: `async def` everywhere
(`asyncio.to_thread` for unavoidable blocking calls); secrets only in `app/config.py`, never
in a response model; `max_turns` on every run; one `AsyncOpenAI` client per process; one
vector store per knowledge base.

## Phase 5 — Verify

```bash
pytest -q
uvicorn app.main:app --reload    # then: curl localhost:8000/health
```

`/health` lists the tools and MCP servers that actually loaded — it should match the
capability table. Then run it live with a real `OPENAI_API_KEY`: one chat turn, one tool call,
and for RAG the whole upload → `completed` → grounded answer → delete → no longer answerable
loop. Traces land at platform.openai.com/traces. **Tests stub the model, so passing tests are
not evidence the agent works.** The live run is.

## Phase 6 — Explain

What was built · which capabilities were added **and which were declined** · any MCP connected
and how that was verified · whether RAG is on and how the knowledge base behaves · how to run
and test it · what configuration the user still owes (keys, tokens, vector store id).

## Never introduce

LangChain · LangGraph · LlamaIndex · Pinecone · Qdrant · Weaviate · Chroma · custom chunking ·
custom embeddings · custom similarity search · a background-job framework **for monitoring** ·
a database the requirements did not ask for.

The Agents SDK plus hosted File Search covers orchestration and retrieval. Add one of the
above only when the user asks for it by name.

## Rationalization table

| Excuse | Reality |
|---|---|
| "Clearly they need Slack, I'll just check if the MCP exists" | Checking comes *after* consent. Explain and ask first. |
| "The MCP is in the config, so it's connected" | Config is intent. `list_tools()` returning tools is connection. |
| "They said 'documents', RAG is obvious — building it" | Obvious inferences still get confirmed. It's one question. |
| "A vector DB is more flexible" | It's more infrastructure they must run. File Search unless they name an alternative. |
| "A new store per upload keeps things clean" | It hides every earlier document from File Search. One store, reused. |
| "Re-index everything after a delete, to be safe" | Deleting one file affects one file. Re-indexing burns time and money for nothing. |
| "Add web search too, it can't hurt" | Every unused tool costs latency, tokens, and wrong turns. |
| "This library is sync, I'll just call it" | It blocks the event loop for every concurrent request. `asyncio.to_thread`. |
| "Tests pass, it works" | The tests stub the model. Run it live first. |
| "I'll leave the RAG code in, just disabled" | Delete it. |

## Red flags — stop

- Searching or installing an MCP the user has not said yes to.
- Writing "connected" without having called `list_tools()`.
- Writing chunking, embedding, or similarity-search code.
- A capability in the build with no row in the capability table.
- A `def` doing I/O in a request path.
- Reporting the agent as working when only `pytest` has run.
