"""The Supermemory module against the real SDK, with HTTP replaced by a stub."""

import json

import httpx
import pytest
from supermemory import Supermemory

from conversation_memory_loader.memory import MemoryStore, StoreError, add_payload

SYSTEM = {"status": "done", "createdAt": "2026-10-01T10:00:00Z", "updatedAt": "2026-10-01T10:00:00Z"}
RESPONSES = {
    "/document": {"id": "thread_0001", "status": "queued"},
    "/list/documents": {
        "documents": [{"id": "thread_0001", "type": "text", "metadata": {}, "system": SYSTEM}],
        "chunks": [],
        "memories": [],
        "pagination": {"currentPage": 1, "totalItems": 1, "totalPages": 1},
    },
    "/document/thread_0001": {
        "id": "thread_0001",
        "type": "text",
        "metadata": {},
        "system": SYSTEM,
        "memories": [
            {
                "id": f"m{n}",
                "memory": "fact",
                "metadata": {},
                "isStatic": False,
                "isInference": False,
                "isLatest": True,
                "isForgotten": False,
                "version": 1,
                "system": {"createdAt": "2026-10-01T10:00:00Z", "updatedAt": "2026-10-01T10:00:00Z"},
            }
            for n in range(9)
        ],
    },
    "": {"status": "deleted", "namespace": "conv_cust_001", "deletedDocumentsCount": 4, "deletedMemoriesCount": 32},
    "/profile": {"profile": {"static": [{"id": "m1", "memory": "Has a dog"}], "dynamic": [], "buckets": {}}},
    "/search": {
        "searchTime": 12,
        "results": [
            {
                "id": "m2",
                "memory": "Car arrives in November",
                "metadata": {},
                "similarity": 0.81,
                "isLatest": True,
                "isInference": False,
                "system": {},
                "included": {
                    "related": {
                        "parents": [],
                        "children": [],
                        "siblings": [
                            {"id": "m3", "relation": "extends", "memory": "10 kWh", "metadata": {}, "system": {}}
                        ],
                    }
                },
            },
            {
                "id": "c1",
                "chunk": "[chat] customer: hello",
                "metadata": {},
                "similarity": 0.6,
                "isLatest": True,
                "isInference": False,
                "system": {"updatedAt": "2026-10-01T10:00:00Z"},
            },
        ],
    },
}


def store_with(handler, max_retries=0):
    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    return MemoryStore(client=Supermemory(api_key="test-key", max_retries=max_retries, http_client=http_client))


def test_calls_send_the_expected_requests():
    requests = []

    def handler(request):
        requests.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        suffix = request.url.path.removeprefix("/ns/conv_cust_001")
        return httpx.Response(200, json=RESPONSES[suffix])

    store = store_with(handler)
    payload = add_payload("conv_cust_001", "thread_0001", "[chat]\ncustomer: hi", {"turn_count": 1}, "2026-09-14", True)
    assert store.add(payload) == "queued"
    assert store.document_statuses("conv_cust_001") == {"thread_0001": "done"}
    assert store.profile("conv_cust_001").static == ["Has a dog"]
    assert store.delete_namespace("conv_cust_001") == "deleted 4 documents and 32 memories"
    assert store.memory_counts("conv_cust_001", ["thread_0001"]) == {"thread_0001": 9}
    hit, source = store.search("conv_cust_001", "When does the car arrive?")
    assert (hit.text, hit.related, hit.is_source) == ("Car arrives in November", [("extends", "10 kWh")], False)
    assert (source.text, source.is_source) == ("[chat] customer: hello", True)

    sent = {(method, path): body for method, path, body in requests}
    body = sent[("POST", "/ns/conv_cust_001/document")]
    assert ("DELETE", "/ns/conv_cust_001") in sent
    assert body["id"] == "thread_0001" and body["dreaming"] == "instant" and "supportingContext" in body
    assert sent[("POST", "/ns/conv_cust_001/search")] == {
        "query": "When does the car arrive?",
        "searchMode": "hybrid",
        "rerank": "aggregate",
        "include": {"related": True},
        "limit": 5,
    }


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "rejected the API key"), (402, "out of credits"), (429, "rate limiting"), (500, "HTTP 500")],
)
def test_http_errors_become_clear_messages(status, expected):
    store = store_with(lambda request: httpx.Response(status, json={"error": "no"}))
    with pytest.raises(StoreError, match=expected):
        store.profile("conv_cust_001")


def test_429_is_retried_before_giving_up(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda seconds: None)  # skip the SDK's backoff wait
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(429, json={"error": "slow down"}, headers={"retry-after-ms": "1"})
        return httpx.Response(200, json=RESPONSES["/profile"])

    assert store_with(handler, max_retries=4).profile("conv_cust_001").static == ["Has a dog"]
    assert len(attempts) == 3


def test_connection_failure_is_a_clear_message():
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(StoreError, match="Could not reach Supermemory"):
        store_with(handler).profile("conv_cust_001")
