import hashlib
import hmac

import pytest

from conversation_memory_loader.namespace import ALLOWED, NamespaceError, namespace_for


@pytest.fixture(autouse=True)
def no_secret_in_environment(monkeypatch):
    monkeypatch.delenv("NAMESPACE_SECRET", raising=False)


def test_default_is_prefix_plus_customer_id():
    assert namespace_for("cust_001") == "conv_cust_001"


def test_secret_gives_an_hmac_of_the_customer_id():
    expected = hmac.new(b"s3cret", b"cust_001", hashlib.sha256).hexdigest()
    assert namespace_for("cust_001", secret="s3cret") == "conv_" + expected


def test_hmac_is_stable_and_depends_on_the_secret():
    assert namespace_for("cust_001", secret="a") == namespace_for("cust_001", secret="a")
    assert namespace_for("cust_001", secret="a") != namespace_for("cust_001", secret="b")
    assert namespace_for("cust_001", secret="a") != namespace_for("cust_002", secret="a")


def test_secret_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("NAMESPACE_SECRET", "from-env")
    assert namespace_for("cust_001") == namespace_for("cust_001", secret="from-env")


def test_ids_with_other_characters_need_a_secret():
    with pytest.raises(NamespaceError, match="NAMESPACE_SECRET"):
        namespace_for("marisol@example.invalid")
    assert ALLOWED.match(namespace_for("marisol@example.invalid", secret="s3cret"))


@pytest.mark.parametrize("customer_id", ["cust_001", "a:b-c_D9"])
def test_namespaces_match_the_allowed_pattern(customer_id):
    assert ALLOWED.match(namespace_for(customer_id))
    assert ALLOWED.match(namespace_for(customer_id, secret="s3cret"))


def test_long_ids_need_a_secret():
    with pytest.raises(NamespaceError, match="too long"):
        namespace_for("c" * 96)
    assert len(namespace_for("c" * 96, secret="s3cret")) == 69
