"""TTL/LRU cache bounded, key hash và không persist plaintext."""
from __future__ import annotations

import copy
import hashlib
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

STAGE4_PIPELINE_VERSION = "stage4-v1-prompt4-otp-notice"


@dataclass
class _Entry:
    expires_at: float
    value: dict[str, Any]


class TTLHashCache:
    def __init__(
        self,
        *,
        capacity: int = 256,
        ttl_seconds: int = 3600,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.capacity = max(1, int(capacity))
        self.ttl_seconds = max(1, int(ttl_seconds))
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        now = self._clock()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return copy.deepcopy(entry.value)

    def put(self, key: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._entries[key] = _Entry(self._clock() + self.ttl_seconds, copy.deepcopy(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self.capacity:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


def build_cache_key(text: str, *, model: str, version: str = STAGE4_PIPELINE_VERSION) -> str:
    """Hash NFC text đã validate cùng model/pipeline version."""
    material = "\0".join((version, model, text)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()
