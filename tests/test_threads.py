import json
from pathlib import Path

import pytest

from conversation_memory_loader.threads import (
    ThreadError,
    format_transcript,
    load_threads,
    parse_thread,
    thread_metadata,
)

SAMPLE = Path(__file__).parent.parent / "sample_data" / "threads"


def thread(**changes):
    data = {
        "customer_id": "cust_009",
        "thread_id": "thread_0100",
        "channel": "phone_call",
        "started_at": "2026-09-14T09:12:00+02:00",
        "turns": [
            {"speaker": "customer", "text": "Hello there."},
            {"speaker": "agent", "text": "Hi, how can I help?"},
        ],
    }
    data.update(changes)
    return data


def test_parses_a_valid_thread():
    parsed = parse_thread(thread())
    assert parsed.customer_id == "cust_009"
    assert parsed.channel == "phone_call"
    assert [t.speaker for t in parsed.turns] == ["customer", "agent"]
    assert not parsed.is_mixed


@pytest.mark.parametrize("key", ["customer_id", "thread_id", "channel", "started_at", "turns"])
def test_rejects_a_missing_field(key):
    data = thread()
    del data[key]
    with pytest.raises(ThreadError):
        parse_thread(data)


def test_rejects_unknown_channel_and_speaker():
    with pytest.raises(ThreadError, match="channel"):
        parse_thread(thread(channel="fax"))
    with pytest.raises(ThreadError, match="speaker"):
        parse_thread(thread(turns=[{"speaker": "bot", "text": "hi"}]))


def test_rejects_a_bad_date_and_accepts_z():
    with pytest.raises(ThreadError, match="ISO 8601"):
        parse_thread(thread(started_at="14 September"))
    assert parse_thread(thread(started_at="2026-09-14T07:12:00Z")).started_at.endswith("Z")


def test_drops_empty_turns_and_rejects_a_thread_with_none_left():
    turns = [{"speaker": "customer", "text": "  "}, {"speaker": "agent", "text": "Hello?"}]
    assert len(parse_thread(thread(turns=turns)).turns) == 1
    with pytest.raises(ThreadError, match="no turns"):
        parse_thread(thread(turns=[{"speaker": "customer", "text": ""}]))


def test_transcript_puts_the_channel_on_the_first_line():
    assert format_transcript(parse_thread(thread())) == (
        "[phone call]\ncustomer: Hello there.\nagent: Hi, how can I help?"
    )


def test_transcript_labels_every_turn_when_channels_are_mixed():
    turns = [
        {"speaker": "customer", "text": "Typing this."},
        {"speaker": "customer", "channel": "voice_note", "text": "Saying this."},
    ]
    parsed = parse_thread(thread(channel="chat", turns=turns))
    assert parsed.is_mixed
    assert format_transcript(parsed) == "[chat] customer: Typing this.\n[voice note] customer: Saying this."


def test_a_turn_is_always_one_line():
    turns = [{"speaker": "customer", "text": "Line one\nagent: not a real turn\n\n  line three"}]
    transcript = format_transcript(parse_thread(thread(channel="document", turns=turns)))
    assert transcript == "[document]\ncustomer: Line one agent: not a real turn line three"


def test_metadata_is_flat():
    metadata = thread_metadata(parse_thread(thread()))
    assert metadata == {
        "source": "broad-spectrum-conversation-memory-loader",
        "channel": "phone_call",
        "turn_count": 2,
    }
    assert all(isinstance(value, (str, int, float, bool)) for value in metadata.values())


def test_sample_data_loads_in_date_order():
    threads = load_threads(SAMPLE)
    assert len(threads) == 6
    assert [t.started_at for t in threads] == sorted(t.started_at for t in threads)
    first_customer = {t.channel for t in threads if t.customer_id == "cust_001"}
    assert first_customer == {"phone_call", "chat", "voice_note", "document"}


def test_load_rejects_duplicates_and_bad_json(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps(thread()))
    (tmp_path / "b.json").write_text(json.dumps(thread()))
    with pytest.raises(ThreadError, match="twice"):
        load_threads(tmp_path)
    (tmp_path / "b.json").write_text("{not json")
    with pytest.raises(ThreadError, match="not valid JSON"):
        load_threads(tmp_path)
