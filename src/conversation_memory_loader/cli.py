"""Command-line interface: load conversations, then show what was learned."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .memory import MemoryStore, StoreError, add_payload
from .namespace import NamespaceError, namespace_for
from .threads import ThreadError, format_transcript, load_threads, thread_metadata

DEFAULT_THREADS = "sample_data/threads"
DEFAULT_QUESTIONS = "sample_data/questions.json"
FALLBACK_QUESTIONS = [
    "What does this customer want from the business?",
    "What has been agreed with this customer so far?",
]
FINISHED = ("done", "failed")


def read_dotenv(path: str = ".env") -> None:
    """Load KEY=value lines from .env without overriding what is already set."""
    if not os.path.isfile(path):
        return
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def payloads(folder: str, instant: bool) -> list[dict]:
    return [
        add_payload(
            namespace_for(thread.customer_id),
            thread.thread_id,
            format_transcript(thread),
            thread_metadata(thread),
            thread.started_at,
            instant,
        )
        for thread in load_threads(folder)
    ]


def load(args: argparse.Namespace) -> None:
    items = payloads(args.folder, args.instant)
    if args.dry_run:
        for item in items:
            print(json.dumps(item, indent=2, ensure_ascii=False))
        print(f"\nDry run: {len(items)} threads prepared, nothing sent.")
        return
    store = MemoryStore()
    for item in items:
        status = store.add(item)
        print(f"{item['namespace']}  {item['id']}  {status}")
    print(f"\nSent {len(items)} threads. Run 'conversation-memory-loader show <customer_id>' to see the result.")


def wait_for_documents(store: MemoryStore, namespace: str, timeout: float) -> dict[str, str]:
    deadline = time.monotonic() + timeout
    while True:
        statuses = store.document_statuses(namespace)
        pending = [doc_id for doc_id, status in statuses.items() if status not in FINISHED]
        if not pending or time.monotonic() >= deadline:
            return statuses
        print(f"Waiting for {len(pending)} of {len(statuses)} documents...", file=sys.stderr)
        time.sleep(5)


def wait_for_memories(store: MemoryStore, namespace: str, doc_ids: list[str], timeout: float) -> dict[str, int]:
    """Memories form after the documents finish, so wait until every document has some."""
    deadline = time.monotonic() + timeout
    while True:
        counts = store.memory_counts(namespace, doc_ids)
        waiting = [doc_id for doc_id, count in counts.items() if count == 0]
        if not waiting or time.monotonic() >= deadline:
            return counts
        print(f"Waiting for memories from {len(waiting)} of {len(counts)} documents...", file=sys.stderr)
        time.sleep(10)


def questions_for(customer_id: str, asked: list[str] | None, questions_file: str) -> list[str]:
    if asked:
        return asked
    if os.path.isfile(questions_file):
        by_customer = json.loads(Path(questions_file).read_text(encoding="utf-8"))
        if by_customer.get(customer_id):
            return list(by_customer[customer_id])
    return FALLBACK_QUESTIONS


def show(args: argparse.Namespace) -> None:
    namespace = namespace_for(args.customer_id)
    store = MemoryStore()
    statuses = wait_for_documents(store, namespace, args.timeout)
    if not statuses:
        raise StoreError(f"No documents in namespace {namespace}. Run 'conversation-memory-loader load' first.")

    print(f"Customer {args.customer_id}  (namespace {namespace})")
    print(f"Documents: {len(statuses)}")
    for doc_id, status in sorted(statuses.items()):
        print(f"  {doc_id}  {status}")
    unfinished = [doc_id for doc_id, status in statuses.items() if status not in FINISHED]
    if unfinished:
        print(f"\nStill processing after {args.timeout:.0f}s: {', '.join(sorted(unfinished))}.")
        print("Results below may be incomplete. Run show again later, or load with --instant.")

    counts = wait_for_memories(store, namespace, sorted(statuses), args.timeout)
    print(f"\nMemories: {sum(counts.values())}")
    for doc_id, count in sorted(counts.items()):
        print(f"  {doc_id}  {count}")
    if not all(counts.values()):
        print(f"Some documents had no memories after {args.timeout:.0f}s. Run show again in a few minutes.")

    profile = store.profile(namespace)
    print("\nProfile")
    for title, facts in (("Static", profile.static), ("Dynamic", profile.dynamic)):
        print(f"  {title}")
        for fact in facts or ["(nothing yet)"]:
            print(f"    - {fact}")

    for question in questions_for(args.customer_id, args.question, args.questions):
        print(f"\nQ: {question}")
        hits = store.search(namespace, question, limit=args.limit)
        if not hits:
            print("    (no memories found)")
        for hit in hits:
            text = hit.text
            if hit.is_source:
                text = "source: " + (text if len(text) <= 160 else text[:157] + "...")
            print(f"    {hit.similarity:.2f}  {text}")
            for relation, text in hit.related:
                print(f"            {relation}: {text}")


def reset(args: argparse.Namespace) -> None:
    if not args.yes:
        raise StoreError("reset permanently deletes everything stored for these customers. Add --yes to confirm.")
    store = MemoryStore()
    for customer_id in args.customer_ids:
        namespace = namespace_for(customer_id)
        try:
            print(f"{namespace}  {store.delete_namespace(namespace)}")
        except StoreError as error:
            if "HTTP 404" not in str(error):
                raise
            print(f"{namespace}  not found, nothing to delete")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="conversation-memory-loader",
        description="Load multi-channel customer conversations into Supermemory.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    load_parser = commands.add_parser("load", help="send conversation files to Supermemory")
    load_parser.add_argument("folder", nargs="?", default=DEFAULT_THREADS, help=f"default: {DEFAULT_THREADS}")
    load_parser.add_argument("--dry-run", action="store_true", help="print the payloads and send nothing")
    load_parser.add_argument("--instant", action="store_true", help="process each document right away (for demos)")
    load_parser.set_defaults(run=load)

    show_parser = commands.add_parser("show", help="print a customer's profile and run searches")
    show_parser.add_argument("customer_id")
    show_parser.add_argument("-q", "--question", action="append", help="ask this instead; repeat for more")
    show_parser.add_argument("--questions", default=DEFAULT_QUESTIONS, help=f"default: {DEFAULT_QUESTIONS}")
    show_parser.add_argument("--limit", type=int, default=5, help="results per question (default 5)")
    show_parser.add_argument("--timeout", type=float, default=300, help="seconds to wait for processing")
    show_parser.set_defaults(run=show)

    reset_parser = commands.add_parser("reset", help="permanently delete what is stored for customers")
    reset_parser.add_argument("customer_ids", nargs="+", metavar="customer_id")
    reset_parser.add_argument("--yes", action="store_true", help="confirm the deletion")
    reset_parser.set_defaults(run=reset)
    return parser


def main(argv: list[str] | None = None) -> int:
    read_dotenv()
    args = build_parser().parse_args(argv)
    try:
        args.run(args)
    except (ThreadError, NamespaceError, StoreError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
