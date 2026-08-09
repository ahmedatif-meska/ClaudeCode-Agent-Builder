"""Knowledge-base file lifecycle against OpenAI-managed File Search.

OpenAI does the parsing, chunking, embedding, indexing and retrieval. This module only
manages the lifecycle: upload -> attach -> report status -> detach/delete.

Adding a file indexes ONLY that file. Deleting a file removes ONLY that file. Never
re-upload or re-index the rest of the knowledge base on either path.
"""

from openai import AsyncOpenAI, NotFoundError

from app.models.schemas import FileRecord

# File Search accepts many text/document types; keep an explicit allowlist so a wrong
# upload fails fast with a clear message instead of failing later during indexing.
ALLOWED_EXTENSIONS = {
    ".pdf", ".txt", ".md", ".markdown", ".docx", ".pptx", ".html", ".json",
    ".csv", ".c", ".cpp", ".cs", ".go", ".java", ".js", ".ts", ".py", ".rb", ".sh",
}
MAX_FILE_BYTES = 25 * 1024 * 1024


class FileValidationError(ValueError):
    """Raised for a file the API layer should reject with 400."""


def validate_upload(filename: str, size: int) -> None:
    suffix = filename[filename.rfind(".") :].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"Unsupported file type '{suffix or filename}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if size <= 0:
        raise FileValidationError("File is empty.")
    if size > MAX_FILE_BYTES:
        raise FileValidationError(
            f"File is {size / 1_048_576:.1f} MB; the limit is "
            f"{MAX_FILE_BYTES // 1_048_576} MB."
        )


async def list_files(client: AsyncOpenAI, vector_store_id: str) -> list[FileRecord]:
    """List everything currently attached to the knowledge base, with live index status."""
    records: list[FileRecord] = []
    async for entry in client.vector_stores.files.list(vector_store_id=vector_store_id):
        attributes = entry.attributes or {}
        filename = attributes.get("filename")
        records.append(
            FileRecord(
                id=entry.id,
                filename=str(filename) if filename is not None else None,
                status=entry.status,
                bytes=entry.usage_bytes,
                error=entry.last_error.message if entry.last_error else None,
            )
        )
    return records


async def upload_file(
    client: AsyncOpenAI, vector_store_id: str, filename: str, content: bytes
) -> FileRecord:
    """Upload one file and attach it to the existing store.

    Returns immediately with status `in_progress`; indexing continues on OpenAI's side.
    Poll `list_files` (or `get_file`) until the status is `completed` before treating the
    document as searchable.
    """
    validate_upload(filename, len(content))

    uploaded = await client.files.create(file=(filename, content), purpose="assistants")
    try:
        entry = await client.vector_stores.files.create(
            vector_store_id=vector_store_id,
            file_id=uploaded.id,
            # The vector-store entry carries no filename of its own; stash it here so
            # listing does not need an extra API call per file.
            attributes={"filename": filename},
        )
    except Exception:
        # Do not leave an orphaned file object behind if the attach fails.
        await client.files.delete(uploaded.id)
        raise

    return FileRecord(
        id=entry.id,
        filename=filename,
        status=entry.status,
        bytes=entry.usage_bytes,
        error=entry.last_error.message if entry.last_error else None,
    )


async def get_file(
    client: AsyncOpenAI, vector_store_id: str, file_id: str
) -> FileRecord | None:
    try:
        entry = await client.vector_stores.files.retrieve(
            file_id, vector_store_id=vector_store_id
        )
    except NotFoundError:
        return None
    attributes = entry.attributes or {}
    filename = attributes.get("filename")
    return FileRecord(
        id=entry.id,
        filename=str(filename) if filename is not None else None,
        status=entry.status,
        bytes=entry.usage_bytes,
        error=entry.last_error.message if entry.last_error else None,
    )


async def delete_file(client: AsyncOpenAI, vector_store_id: str, file_id: str) -> bool:
    """Detach from the store (stops it being searchable), then delete the file object.

    Both steps matter: detaching alone leaves the bytes and the storage bill behind,
    deleting alone can leave a broken entry in the store.
    """
    detached = False
    try:
        result = await client.vector_stores.files.delete(
            file_id, vector_store_id=vector_store_id
        )
        detached = result.deleted
    except NotFoundError:
        detached = False

    try:
        await client.files.delete(file_id)
    except NotFoundError:
        pass

    return detached
