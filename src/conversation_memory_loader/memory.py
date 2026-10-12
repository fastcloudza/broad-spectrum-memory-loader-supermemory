"""Every Supermemory call lives here.

The rest of the package only uses MemoryStore's methods and the small result
types below, so another memory back end could be added by writing a second
class with the same methods.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

SUPPORTING_CONTEXT = (
    "These are conversations between a business's agents and one customer, across "
    "several channels: chats, phone calls, voice notes, meetings and documents. "
    "Lines starting with 'agent:' are the business speaking; lines starting with "
    "'customer:' are the customer."
)


MAX_RETRIES = 4


class StoreError(Exception):
    """A failure talking to the memory back end, with a message fit to show a user."""


@dataclass(frozen=True)
class Hit:
    text: str
    similarity: float
    related: list[tuple[str, str]] = field(default_factory=list)  # (relation, text)
    is_source: bool = False  # a passage from a document, not a learned memory


@dataclass(frozen=True)
class Profile:
    static: list[str]
    dynamic: list[str]


class MemoryStore:
    def __init__(self, api_key: str | None = None, client=None):
        """Pass `client` to use a ready-made Supermemory client (the tests do)."""
        if client is None:
            api_key = api_key or os.environ.get("SUPERMEMORY_API_KEY")
            if not api_key:
                raise StoreError(
                    "SUPERMEMORY_API_KEY is not set. Copy .env.example to .env and add your key, "
                    "or export it in your shell."
                )
            from supermemory import Supermemory

            # The SDK retries HTTP 429 itself, with backoff, and honours Retry-After.
            client = Supermemory(api_key=api_key, max_retries=MAX_RETRIES)
        self._client = client

    def _call(self, function, *args, **kwargs):
        import supermemory

        try:
            return function(*args, **kwargs)
        except supermemory.APIStatusError as error:
            if error.status_code == 401:
                message = "Supermemory rejected the API key (HTTP 401). Check SUPERMEMORY_API_KEY."
            elif error.status_code == 402:
                message = "Supermemory reports the account is out of credits or quota (HTTP 402)."
            elif error.status_code == 429:
                message = "Supermemory is rate limiting (HTTP 429) and the retries ran out. Try again shortly."
            else:
                message = f"Supermemory request failed (HTTP {error.status_code}): {error.body}"
            raise StoreError(message) from None
        except supermemory.APIConnectionError:
            raise StoreError("Could not reach Supermemory. Check your network connection.") from None

    def add(self, payload: dict) -> str:
        """Send one document (see add_payload) and return its processing status. Reusing an id appends."""
        return str(self._call(self._client.add, **payload).status)

    def document_statuses(self, namespace: str) -> dict[str, str]:
        statuses: dict[str, str] = {}
        page = 1
        while True:
            response = self._call(self._client.list, namespace, "documents", page=page, limit=100)
            for document in response.documents:
                statuses[document.id] = str(document.system.status)
            if not response.documents or page >= response.pagination.total_pages:
                return statuses
            page += 1

    def memory_counts(self, namespace: str, doc_ids: list[str]) -> dict[str, int]:
        """How many memories each document has produced so far."""
        counts = {}
        for doc_id in doc_ids:
            document = self._call(self._client.documents.get, namespace, doc_id, include="memories")
            counts[doc_id] = len(document.memories or [])
        return counts

    def delete_namespace(self, namespace: str) -> str:
        """Permanently delete a namespace with its documents and memories."""
        result = self._call(self._client.namespaces.delete, namespace)
        documents = getattr(result, "deleted_documents_count", "?")
        memories = getattr(result, "deleted_memories_count", "?")
        return f"deleted {documents} documents and {memories} memories"

    def profile(self, namespace: str) -> Profile:
        profile = self._call(self._client.profile, namespace).profile
        return Profile([f.memory for f in profile.static], [f.memory for f in profile.dynamic])

    def search(self, namespace: str, query: str, limit: int = 5) -> list[Hit]:
        """Hybrid search (memories plus source passages) with the "aggregate" rerank.

        Plain memory search returns the facts nearest the question one by one, so a
        question that needs a fact from a call and one from a chat gets only half.
        The aggregate rerank combines overlapping results into an answer.
        """
        response = self._call(
            self._client.search,
            namespace,
            query=query,
            search_mode="hybrid",
            rerank="aggregate",
            include={"related": True},
            limit=limit,
        )
        hits = []
        for result in response.results:
            related = []
            links = result.included.related if result.included else None
            if links:
                for memory in [*links.parents, *links.children, *links.siblings]:
                    related.append((str(memory.relation), memory.memory))
            is_source = not result.memory and bool(result.chunk)
            hits.append(Hit(result.memory or result.chunk or "", result.similarity, related, is_source))
        return hits


def add_payload(namespace: str, doc_id: str, content: str, metadata: dict, date: str, instant: bool) -> dict:
    """The exact keyword arguments sent to Supermemory for one thread. Also used by --dry-run."""
    return {
        "namespace": namespace,
        "id": doc_id,
        "content": content,
        "metadata": metadata,
        "date": date,
        "dreaming": "instant" if instant else "dynamic",
        "supporting_context": SUPPORTING_CONTEXT,
    }
