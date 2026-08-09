"""Vector store resolution.

ONE vector store for the whole knowledge base, created once and reused. Creating a store
per upload fragments the knowledge base — File Search can only search the stores you hand
it, so each new store would silently hide every earlier document.

Create isolated stores only if the requirements call for per-tenant/per-user knowledge
bases; then persist the mapping (user -> vector_store_id) and pass the right id at
request time.
"""

from app.config import get_settings


def get_vector_store_id() -> str:
    """Read the configured store id, failing with an actionable message if unset."""
    store_id = get_settings().vector_store_id
    if not store_id:
        raise RuntimeError(
            "VECTOR_STORE_ID is not set. Create the store once with "
            "`python -m scripts.create_vector_store` and put the printed id in .env"
        )
    return store_id
