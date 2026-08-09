# RAG with OpenAI File Search

Only after the user has confirmed RAG. Everything here assumes OpenAI-managed retrieval.

## The division of labour

```
User ──upload──▶ FastAPI ──▶ Files API ──▶ Vector Store ──▶ OpenAI does:
                                                             parse · chunk · embed
                                                             index · store · rank

User ──ask────▶ FastAPI ──▶ Agent ──▶ FileSearchTool ──▶ Vector Store ──▶ grounded answer
```

**You own the lifecycle. OpenAI owns retrieval.** You never write a parser, a chunker, an
embedding call, a vector insert, or a similarity search. If you find yourself doing any of
those, the design took a wrong turn.

## Vector store: one, created once

```python
store = await client.vector_stores.create(name="agent-knowledge-base")   # once, ever
# persist store.id in .env as VECTOR_STORE_ID
```

The store outlives every file in it. File Search only searches the stores you pass to
`FileSearchTool(vector_store_ids=[...])`, so a store created per upload hides every earlier
document. Create separate stores **only** for genuinely isolated knowledge bases (per tenant,
per workspace) — then persist the `owner → store_id` mapping and pass the right id per request.

## Upload → attach → poll

```python
uploaded = await client.files.create(file=(filename, content), purpose="assistants")
entry = await client.vector_stores.files.create(
    vector_store_id=store_id,
    file_id=uploaded.id,
    attributes={"filename": filename},   # the store entry has no filename of its own
)
entry.status  # "in_progress" -> "completed" | "failed"
```

Attaching indexes **only the new file**. Nothing else in the store is touched, re-read, or
re-embedded. Return `in_progress` immediately and let the client poll
`GET /files`; blocking the request until indexing finishes makes uploads feel broken on large
PDFs. `client.vector_stores.files.upload_and_poll(...)` exists if a synchronous
upload genuinely suits the UX better.

Mark a document usable only at `completed`. Querying earlier returns nothing and looks like
a retrieval bug.

## Delete → detach, then remove

```python
await client.vector_stores.files.delete(file_id, vector_store_id=store_id)  # stops search
await client.files.delete(file_id)                                          # frees storage
```

Both steps. Detaching alone leaves the bytes and the bill; deleting alone can leave a broken
entry in the store. Nothing else is re-indexed — deletion is per file, always.

## Listing

```python
async for entry in client.vector_stores.files.list(vector_store_id=store_id):
    entry.id, entry.status, entry.usage_bytes, entry.attributes, entry.last_error
```

Async iteration paginates automatically. Read the filename back out of `attributes` rather
than making a `files.retrieve` call per row.

## Querying

```python
FileSearchTool(vector_store_ids=[store_id], max_num_results=8)
```

- `include_search_results=True` returns the retrieved chunks in the run output — useful for
  debugging retrieval quality and for building citations, at the cost of tokens.
- `filters=` narrows by the `attributes` you set at attach time (tenant, doc type, date).
- Instruct the agent to search once per question and to say when the documents do not cover
  something. Without that, tool-loops and confident invention are the two default failure modes.

## Application-side records

The vector store is queryable, so a database is optional. Add one only for things OpenAI does
not track: who uploaded what, per-tenant ownership, soft deletes, audit history. If you do,
the OpenAI ids stay the source of truth and your table stores references — never a copy of
the content.

## Verifying it actually works

With a real key, in order:

1. `python -m scripts.create_vector_store` → id in `.env`.
2. Upload a document containing a fact nothing else could know.
3. Poll `GET /files` until `completed`.
4. Ask for that fact → the answer contains it.
5. Delete the file → `GET /files` no longer lists it.
6. Ask again → the agent says it does not have that information.

Step 6 is the one people skip; it is the step that proves deletion actually removed the
document from retrieval.
