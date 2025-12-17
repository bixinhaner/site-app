from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock
from typing import Generic, Optional, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class CacheValue(Generic[T]):
    value: T
    expires_at: float


class TtlLruCache(Generic[T]):
    def __init__(self, max_size: int, default_ttl_seconds: int):
        self._max_size = max(1, int(max_size))
        self._default_ttl_seconds = max(1, int(default_ttl_seconds))
        self._data: "OrderedDict[str, CacheValue[T]]" = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[T]:
        now = time.time()
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            if item.expires_at <= now:
                self._data.pop(key, None)
                return None
            # LRU 续命（移动到末尾）
            self._data.move_to_end(key)
            return item.value

    def set(self, key: str, value: T, ttl_seconds: Optional[int] = None) -> None:
        ttl = self._default_ttl_seconds if ttl_seconds is None else max(1, int(ttl_seconds))
        expires_at = time.time() + ttl
        with self._lock:
            self._data[key] = CacheValue(value=value, expires_at=expires_at)
            self._data.move_to_end(key)
            while len(self._data) > self._max_size:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

