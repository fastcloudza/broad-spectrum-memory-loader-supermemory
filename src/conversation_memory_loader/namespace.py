"""Derive the Supermemory namespace for a customer."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

PREFIX = "conv_"
ALLOWED = re.compile(r"^[a-zA-Z0-9_:-]+$")
MAX_LENGTH = 100  # Supermemory's limit


class NamespaceError(ValueError):
    pass


def namespace_for(customer_id: str, secret: str | None = None) -> str:
    """Return conv_<customer_id>, or conv_<HMAC-SHA256> when a secret is given.

    With no secret argument, NAMESPACE_SECRET is read from the environment.
    """
    if secret is None:
        secret = os.environ.get("NAMESPACE_SECRET")
    if secret:
        digest = hmac.new(secret.encode(), customer_id.encode(), hashlib.sha256).hexdigest()
        return PREFIX + digest
    namespace = PREFIX + customer_id
    if len(namespace) > MAX_LENGTH:
        raise NamespaceError(
            f"customer_id {customer_id!r} is too long for a namespace ({MAX_LENGTH} characters at most). "
            "Set NAMESPACE_SECRET to use a hash of the id instead."
        )
    if not ALLOWED.match(namespace):
        raise NamespaceError(
            f"customer_id {customer_id!r} has characters a namespace cannot hold "
            "(allowed: letters, digits, '_', ':' and '-'). "
            "Set NAMESPACE_SECRET to use a hash of the id instead."
        )
    return namespace
