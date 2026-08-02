"""
Idempotency guard for webhook deliveries.

Prevents duplicate outbound replies when Meta retries a webhook POST.
Current implementation is in-memory; swap the concrete class for a
Redis-backed version in production without changing the interface.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from typing import Optional


class IdempotencyBackend(ABC):
    """Interface — implement for Redis, DynamoDB, etc."""

    @abstractmethod
    def is_seen(self, message_id: str) -> bool:
        """Return True if this message_id has already been processed."""

    @abstractmethod
    def mark_seen(self, message_id: str) -> None:
        """Record that this message_id has been processed."""


class InMemoryIdempotencyStore(IdempotencyBackend):
    """
    Bounded in-memory store.  Entries older than `ttl_seconds` are lazily
    evicted, and the store never holds more than `max_size` entries.
    """

    def __init__(self, max_size: int = 10_000, ttl_seconds: float = 600.0) -> None:
        self._store: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def is_seen(self, message_id: str) -> bool:
        ts = self._store.get(message_id)
        if ts is None:
            return False
        if time.monotonic() - ts > self._ttl:
            self._store.pop(message_id, None)
            return False
        return True

    def mark_seen(self, message_id: str) -> None:
        self._store[message_id] = time.monotonic()
        self._store.move_to_end(message_id)
        # Evict oldest if over capacity
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


# Singleton
idempotency_store: IdempotencyBackend = InMemoryIdempotencyStore()
