"""Read conversation thread files and turn them into speaker-attributed text."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHANNELS = ("chat", "phone_call", "voice_note", "meeting", "document")
SPEAKERS = ("customer", "agent")
SOURCE = "broad-spectrum-conversation-memory-loader"


class ThreadError(ValueError):
    """A thread file is missing something or holds a value we do not accept."""


@dataclass(frozen=True)
class Turn:
    speaker: str
    text: str
    channel: str


@dataclass(frozen=True)
class Thread:
    customer_id: str
    thread_id: str
    channel: str
    started_at: str
    turns: tuple[Turn, ...]

    @property
    def is_mixed(self) -> bool:
        return any(turn.channel != self.channel for turn in self.turns)


def _required_text(data: dict, key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ThreadError(f"{where}: '{key}' is missing or empty")
    return value.strip()


def _channel(value: object, where: str) -> str:
    if value not in CHANNELS:
        raise ThreadError(f"{where}: channel {value!r} is not one of {', '.join(CHANNELS)}")
    return str(value)


def parse_thread(data: object, where: str = "thread") -> Thread:
    """Validate one thread and return it. Turns with no text are dropped."""
    if not isinstance(data, dict):
        raise ThreadError(f"{where}: expected a JSON object")
    customer_id = _required_text(data, "customer_id", where)
    thread_id = _required_text(data, "thread_id", where)
    if len(thread_id) > 255:
        raise ThreadError(f"{where}: thread_id is longer than 255 characters")
    channel = _channel(data.get("channel"), where)
    started_at = _required_text(data, "started_at", where)
    try:
        datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    except ValueError:
        raise ThreadError(f"{where}: started_at {started_at!r} is not an ISO 8601 date") from None

    raw_turns = data.get("turns")
    if not isinstance(raw_turns, list):
        raise ThreadError(f"{where}: 'turns' must be a list")
    turns = []
    for number, raw in enumerate(raw_turns, start=1):
        turn_where = f"{where}, turn {number}"
        if not isinstance(raw, dict):
            raise ThreadError(f"{turn_where}: expected a JSON object")
        if raw.get("speaker") not in SPEAKERS:
            raise ThreadError(f"{turn_where}: speaker must be 'customer' or 'agent'")
        text = raw.get("text")
        if not isinstance(text, str):
            raise ThreadError(f"{turn_where}: 'text' must be a string")
        text = " ".join(text.split())  # one line per turn
        if not text:
            continue
        turn_channel = _channel(raw["channel"], turn_where) if "channel" in raw else channel
        turns.append(Turn(raw["speaker"], text, turn_channel))
    if not turns:
        raise ThreadError(f"{where}: no turns with text")
    return Thread(customer_id, thread_id, channel, started_at, tuple(turns))


def load_threads(folder: str | Path) -> list[Thread]:
    """Read every .json file under a folder, oldest thread first."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ThreadError(f"{folder} is not a folder")
    threads = []
    for path in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ThreadError(f"{path}: not valid JSON ({error})") from None
        threads.append(parse_thread(data, where=str(path)))
    if not threads:
        raise ThreadError(f"no .json files found under {folder}")
    seen: set[tuple[str, str]] = set()
    for thread in threads:
        key = (thread.customer_id, thread.thread_id)
        if key in seen:
            raise ThreadError(f"thread_id {thread.thread_id!r} appears twice for {thread.customer_id}")
        seen.add(key)
    return sorted(threads, key=lambda t: datetime.fromisoformat(t.started_at.replace("Z", "+00:00")).timestamp())


def channel_label(channel: str) -> str:
    return f"[{channel.replace('_', ' ')}]"


def format_transcript(thread: Thread) -> str:
    """One line per turn. The channel goes on the first line, or on every turn if they differ."""
    if thread.is_mixed:
        return "\n".join(f"{channel_label(t.channel)} {t.speaker}: {t.text}" for t in thread.turns)
    lines = [channel_label(thread.channel)]
    lines += [f"{t.speaker}: {t.text}" for t in thread.turns]
    return "\n".join(lines)


def thread_metadata(thread: Thread) -> dict[str, str | int]:
    """Flat values only: Supermemory metadata does not take nested objects."""
    return {"source": SOURCE, "channel": thread.channel, "turn_count": len(thread.turns)}
