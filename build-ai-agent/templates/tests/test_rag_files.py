"""RAG lifecycle tests. RAG builds only — delete alongside app/rag.

These lock in the two rules that are easiest to get wrong: adding or removing one
document must never touch the rest of the knowledge base, and the vector store is
never re-created.
"""

from types import SimpleNamespace
from typing import Any

import pytest
from openai import NotFoundError

from app.rag.files import FileValidationError, delete_file, upload_file, validate_upload

STORE_ID = "vs_existing"


class FakeVectorStoreFiles:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.deleted: list[tuple[str, str]] = []

    async def create(self, *, vector_store_id: str, file_id: str, **kwargs: Any) -> Any:
        self.created.append({"vector_store_id": vector_store_id, "file_id": file_id, **kwargs})
        return SimpleNamespace(
            id=file_id, status="in_progress", usage_bytes=0, last_error=None
        )

    async def delete(self, file_id: str, *, vector_store_id: str) -> Any:
        self.deleted.append((vector_store_id, file_id))
        return SimpleNamespace(deleted=True)


class FakeFiles:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.deleted: list[str] = []

    async def create(self, *, file: Any, purpose: str) -> Any:
        filename = file[0]
        self.created.append(filename)
        return SimpleNamespace(id=f"file_{len(self.created)}")

    async def delete(self, file_id: str) -> Any:
        self.deleted.append(file_id)
        return SimpleNamespace(deleted=True)


class FakeVectorStores:
    def __init__(self) -> None:
        self.files = FakeVectorStoreFiles()
        self.create_calls = 0

    async def create(self, **kwargs: Any) -> Any:
        self.create_calls += 1
        return SimpleNamespace(id="vs_new")


class FakeClient:
    def __init__(self) -> None:
        self.files = FakeFiles()
        self.vector_stores = FakeVectorStores()


async def test_upload_reuses_the_existing_store_and_indexes_only_the_new_file() -> None:
    client = FakeClient()

    record = await upload_file(client, STORE_ID, "handbook.pdf", b"%PDF-1.4 content")

    assert client.vector_stores.create_calls == 0, "must never create a second store"
    assert len(client.vector_stores.files.created) == 1, "only the new file is indexed"
    assert client.vector_stores.files.created[0]["vector_store_id"] == STORE_ID
    assert client.vector_stores.files.created[0]["attributes"] == {"filename": "handbook.pdf"}
    assert record.status == "in_progress"
    assert record.filename == "handbook.pdf"


async def test_delete_detaches_then_removes_only_that_file() -> None:
    client = FakeClient()

    deleted = await delete_file(client, STORE_ID, "file_1")

    assert deleted is True
    assert client.vector_stores.files.deleted == [(STORE_ID, "file_1")]
    assert client.files.deleted == ["file_1"]
    assert client.vector_stores.create_calls == 0, "deletion must not rebuild the store"


async def test_failed_attach_does_not_leave_an_orphaned_file() -> None:
    client = FakeClient()

    async def boom(**kwargs: Any) -> Any:
        raise RuntimeError("attach failed")

    client.vector_stores.files.create = boom  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await upload_file(client, STORE_ID, "notes.md", b"hello")

    assert client.files.deleted == ["file_1"]


async def test_missing_entries_are_tolerated_on_delete() -> None:
    client = FakeClient()

    async def missing(file_id: str, *, vector_store_id: str) -> Any:
        raise NotFoundError("gone", response=_fake_response(), body=None)

    client.vector_stores.files.delete = missing  # type: ignore[method-assign]

    assert await delete_file(client, STORE_ID, "file_x") is False


@pytest.mark.parametrize(
    ("filename", "size"),
    [("virus.exe", 10), ("empty.txt", 0), ("huge.pdf", 200 * 1024 * 1024)],
)
def test_validation_rejects_bad_uploads(filename: str, size: int) -> None:
    with pytest.raises(FileValidationError):
        validate_upload(filename, size)


def _fake_response() -> Any:
    import httpx

    return httpx.Response(404, request=httpx.Request("DELETE", "https://api.openai.com"))
