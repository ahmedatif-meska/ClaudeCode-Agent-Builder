"""Create the knowledge base's ONE vector store. Run once, then put the id in .env.

    python -m scripts.create_vector_store

Re-running creates a second, empty store — the app would then search nothing.
"""

import asyncio

from app.openai_client import get_openai_client


async def main() -> None:
    store = await get_openai_client().vector_stores.create(name="agent-knowledge-base")
    print(f"VECTOR_STORE_ID={store.id}")
    print("Add that line to .env")


if __name__ == "__main__":
    asyncio.run(main())
