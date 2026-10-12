import json
import os
from pathlib import Path

import pytest

from conversation_memory_loader import cli
from conversation_memory_loader.memory import SUPPORTING_CONTEXT

SAMPLE = str(Path(__file__).parent.parent / "sample_data" / "threads")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("NAMESPACE_SECRET", raising=False)
    monkeypatch.delenv("SUPERMEMORY_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no .env here


def test_dry_run_prints_payloads_and_needs_no_key(capsys, monkeypatch):
    def no_store(*args, **kwargs):
        raise AssertionError("dry run must not create a client")

    monkeypatch.setattr(cli, "MemoryStore", no_store)
    assert cli.main(["load", SAMPLE, "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "6 threads prepared, nothing sent" in output
    assert '"namespace": "conv_cust_001"' in output
    assert '"dreaming": "dynamic"' in output


def test_payload_shape():
    payload = cli.payloads(SAMPLE, instant=True)[0]
    assert set(payload) == {"namespace", "id", "content", "metadata", "date", "dreaming", "supporting_context"}
    assert payload["id"] == "thread_0001"
    assert payload["dreaming"] == "instant"
    assert payload["content"].startswith("[phone call]\nagent: ")
    assert payload["date"] == "2026-09-14T14:10:00+01:00"
    json.dumps(payload)  # everything is plain JSON


def test_supporting_context_fits_the_limit():
    assert len(SUPPORTING_CONTEXT) < 1500


def test_missing_api_key_is_a_clear_error(capsys):
    assert cli.main(["load", SAMPLE]) == 1
    assert "SUPERMEMORY_API_KEY is not set" in capsys.readouterr().err


def test_questions_come_from_the_flag_then_the_file_then_the_fallback(tmp_path):
    questions = tmp_path / "questions.json"
    questions.write_text(json.dumps({"cust_001": ["From the file?"]}))
    assert cli.questions_for("cust_001", ["Asked?"], str(questions)) == ["Asked?"]
    assert cli.questions_for("cust_001", None, str(questions)) == ["From the file?"]
    assert cli.questions_for("cust_404", None, str(questions)) == cli.FALLBACK_QUESTIONS


def test_dotenv_does_not_override_the_environment(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("# comment\nSUPERMEMORY_API_KEY='from-file'\nNAMESPACE_SECRET=abc\n")
    monkeypatch.setenv("NAMESPACE_SECRET", "already-set")
    cli.read_dotenv(str(tmp_path / ".env"))
    assert os.environ["SUPERMEMORY_API_KEY"] == "from-file"
    assert os.environ["NAMESPACE_SECRET"] == "already-set"


class FakeStore:
    def memory_counts(self, namespace, doc_ids):
        return {doc_id: 3 for doc_id in doc_ids}

    def document_statuses(self, namespace):
        return {"thread_0001": "done", "thread_0002": "done"}

    def profile(self, namespace):
        from conversation_memory_loader.memory import Profile

        return Profile(static=["Has a dog called Biscuit"], dynamic=[])

    def search(self, namespace, query, limit=5):
        from conversation_memory_loader.memory import Hit

        return [
            Hit("Car arrives in November", 0.81, [("extends", "Battery raised to 10 kWh")]),
            Hit("[call] customer: " + "x" * 300, 0.6, [], is_source=True),
        ]


def test_show_prints_documents_profile_and_search_results(capsys, monkeypatch):
    monkeypatch.setattr(cli, "MemoryStore", FakeStore)
    assert cli.main(["show", "cust_001", "-q", "When does the car arrive?"]) == 0
    output = capsys.readouterr().out
    assert "namespace conv_cust_001" in output
    assert "Documents: 2" in output
    assert "Memories: 6" in output
    assert "- Has a dog called Biscuit" in output
    assert "(nothing yet)" in output
    assert "Q: When does the car arrive?" in output
    assert "0.81  Car arrives in November" in output
    assert "extends: Battery raised to 10 kWh" in output
    assert "0.60  source: [call] customer: xxx" in output
    assert "x" * 200 not in output  # long source passages are shortened


def test_reset_needs_confirmation_and_deletes_each_namespace(capsys, monkeypatch):
    deleted = []

    class Store:
        def delete_namespace(self, namespace):
            deleted.append(namespace)
            return "deleted 4 documents and 32 memories"

    monkeypatch.setattr(cli, "MemoryStore", Store)
    assert cli.main(["reset", "cust_001"]) == 1
    assert "--yes" in capsys.readouterr().err
    assert deleted == []
    assert cli.main(["reset", "cust_001", "cust_002", "--yes"]) == 0
    assert deleted == ["conv_cust_001", "conv_cust_002"]
