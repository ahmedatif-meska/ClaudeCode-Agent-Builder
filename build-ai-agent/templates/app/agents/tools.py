"""Custom function tools.

Start empty. Add a tool only for something the model genuinely cannot do on its own:
reach a private system, run a deterministic computation, or take a real-world action.

Rules that make tools work well:
  * `async def` — a blocking tool stalls the whole event loop for every other request.
  * The docstring IS the tool description the model reads. Describe when to use it,
    not how it is implemented.
  * Type-annotate every argument; the SDK derives the JSON schema from the signature.
  * Return a short string or a small JSON-serializable object. Dumping a 50k-row
    payload into the transcript wrecks latency and cost.
  * Handle your own errors and return a message the model can act on.
"""

from agents import Tool, function_tool

# --- Example. Replace or delete. ---


@function_tool
async def get_order_status(order_id: str) -> str:
    """Look up the current status of a customer order.

    Args:
        order_id: The order identifier, e.g. "ORD-10432".
    """
    # await your real async client here (httpx.AsyncClient, asyncpg, ...).
    # If the only available client is synchronous, do not call it directly:
    #     return await asyncio.to_thread(blocking_lookup, order_id)
    raise NotImplementedError("Wire this to the real order system.")


# Registered tools. An empty list is the correct default for an agent that needs none.
CUSTOM_TOOLS: list[Tool] = []
