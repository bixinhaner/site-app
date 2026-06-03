import threading
import time
from collections import Counter, deque
from datetime import datetime
from typing import Any, Deque, Dict, Optional, Tuple


DEFAULT_OMC_RATE_LIMIT_PER_MINUTE = 120
DEFAULT_OMC_RATE_LIMIT_BURST = 10
DEFAULT_OMC_TOKEN_TTL_SECONDS = 600

MAX_OMC_RATE_LIMIT_PER_MINUTE = 3000
MAX_OMC_RATE_LIMIT_BURST = 500
MAX_OMC_TOKEN_TTL_SECONDS = 86400


def clamp_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def normalize_omc_runtime_config(data: Optional[Dict[str, Any]]) -> Dict[str, int]:
    data = data or {}
    rate_limit = clamp_int(
        data.get("rate_limit_per_minute"),
        DEFAULT_OMC_RATE_LIMIT_PER_MINUTE,
        1,
        MAX_OMC_RATE_LIMIT_PER_MINUTE,
    )
    burst = clamp_int(
        data.get("rate_limit_burst"),
        DEFAULT_OMC_RATE_LIMIT_BURST,
        1,
        MAX_OMC_RATE_LIMIT_BURST,
    )
    token_ttl = clamp_int(
        data.get("token_ttl_seconds"),
        DEFAULT_OMC_TOKEN_TTL_SECONDS,
        60,
        MAX_OMC_TOKEN_TTL_SECONDS,
    )
    return {
        "rate_limit_per_minute": rate_limit,
        "rate_limit_burst": min(burst, rate_limit),
        "token_ttl_seconds": token_ttl,
    }


class OmcRateLimiter:
    """Process-wide token bucket for all outbound OMC HTTP requests."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rate_limit_per_minute = DEFAULT_OMC_RATE_LIMIT_PER_MINUTE
        self._burst = DEFAULT_OMC_RATE_LIMIT_BURST
        self._tokens = float(DEFAULT_OMC_RATE_LIMIT_BURST)
        self._updated_at = time.monotonic()
        self._waiters = 0
        self._last_wait_seconds = 0.0
        self._total_wait_seconds = 0.0

    def configure(self, rate_limit_per_minute: int, burst: int) -> None:
        with self._lock:
            rate_limit_per_minute = clamp_int(
                rate_limit_per_minute,
                DEFAULT_OMC_RATE_LIMIT_PER_MINUTE,
                1,
                MAX_OMC_RATE_LIMIT_PER_MINUTE,
            )
            burst = clamp_int(
                burst,
                DEFAULT_OMC_RATE_LIMIT_BURST,
                1,
                MAX_OMC_RATE_LIMIT_BURST,
            )
            self._refill_locked()
            self._rate_limit_per_minute = rate_limit_per_minute
            self._burst = min(burst, rate_limit_per_minute)
            self._tokens = min(self._tokens, float(self._burst))

    def acquire(self) -> float:
        total_wait = 0.0
        counted_waiter = False
        while True:
            wait_seconds = 0.0
            with self._lock:
                self._refill_locked()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    if counted_waiter:
                        self._waiters = max(0, self._waiters - 1)
                    self._last_wait_seconds = total_wait
                    self._total_wait_seconds += total_wait
                    return total_wait

                if not counted_waiter:
                    self._waiters += 1
                    counted_waiter = True

                refill_per_second = self._rate_limit_per_minute / 60.0
                wait_seconds = (1.0 - self._tokens) / refill_per_second
                wait_seconds = max(0.05, min(wait_seconds, 5.0))

            time.sleep(wait_seconds)
            total_wait += wait_seconds

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._refill_locked()
            return {
                "rate_limit_per_minute": self._rate_limit_per_minute,
                "rate_limit_burst": self._burst,
                "available_tokens": round(self._tokens, 2),
                "waiting_requests": self._waiters,
                "last_wait_seconds": round(self._last_wait_seconds, 3),
                "total_wait_seconds": round(self._total_wait_seconds, 3),
            }

    def _refill_locked(self) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self._updated_at)
        refill_per_second = self._rate_limit_per_minute / 60.0
        if elapsed > 0:
            self._tokens = min(float(self._burst), self._tokens + elapsed * refill_per_second)
            self._updated_at = now


class OmcTokenCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: Dict[str, Tuple[str, float]] = {}
        self._hits = 0
        self._misses = 0
        self._writes = 0

    def get(self, key: str) -> Optional[str]:
        now = time.monotonic()
        with self._lock:
            item = self._items.get(key)
            if not item:
                self._misses += 1
                return None
            token, expires_at = item
            if expires_at <= now:
                self._items.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return token

    def set(self, key: str, token: str, ttl_seconds: int) -> None:
        ttl = clamp_int(
            ttl_seconds,
            DEFAULT_OMC_TOKEN_TTL_SECONDS,
            60,
            MAX_OMC_TOKEN_TTL_SECONDS,
        )
        with self._lock:
            self._items[key] = (token, time.monotonic() + ttl)
            self._writes += 1

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._items.pop(key, None)

    def snapshot(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            expired = [key for key, (_, expires_at) in self._items.items() if expires_at <= now]
            for key in expired:
                self._items.pop(key, None)
            return {
                "entries": len(self._items),
                "hits": self._hits,
                "misses": self._misses,
                "writes": self._writes,
            }


class OmcRuntimeStats:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._started_at = datetime.utcnow()
        self._events: Deque[Dict[str, Any]] = deque(maxlen=10000)
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=200)
        self._total = 0
        self._success = 0
        self._failed = 0
        self._by_source: Counter[str] = Counter()
        self._by_endpoint: Counter[str] = Counter()
        self._by_status_code: Counter[str] = Counter()
        self._monitor_queue_depth = 0
        self._monitor_cycle_started_at: Optional[str] = None
        self._monitor_cycle_finished_at: Optional[str] = None
        self._monitor_cycle_work_orders = 0

    def record_request(
        self,
        *,
        source: str,
        method: str,
        endpoint: str,
        status_code: Optional[int],
        success: bool,
        duration_seconds: float,
        wait_seconds: float,
        error: Optional[str] = None,
    ) -> None:
        now = time.time()
        status_key = str(status_code) if status_code is not None else "unknown"
        event = {
            "timestamp": now,
            "time": datetime.utcnow().isoformat() + "Z",
            "source": source or "unknown",
            "method": method.upper(),
            "endpoint": endpoint,
            "status_code": status_code,
            "success": bool(success),
            "duration_seconds": round(duration_seconds, 3),
            "wait_seconds": round(wait_seconds, 3),
            "error": (error or "")[:200] or None,
        }
        with self._lock:
            self._events.append(event)
            self._recent.appendleft(event)
            self._total += 1
            if success:
                self._success += 1
            else:
                self._failed += 1
            self._by_source[event["source"]] += 1
            self._by_endpoint[endpoint] += 1
            self._by_status_code[status_key] += 1

    def set_monitor_queue(self, depth: int, total_work_orders: Optional[int] = None) -> None:
        with self._lock:
            self._monitor_queue_depth = max(0, int(depth or 0))
            if total_work_orders is not None:
                self._monitor_cycle_work_orders = max(0, int(total_work_orders or 0))
                self._monitor_cycle_started_at = datetime.utcnow().isoformat() + "Z"

    def finish_monitor_cycle(self) -> None:
        with self._lock:
            self._monitor_queue_depth = 0
            self._monitor_cycle_finished_at = datetime.utcnow().isoformat() + "Z"

    def snapshot(self) -> Dict[str, Any]:
        now = time.time()
        with self._lock:
            events = list(self._events)
            recent = list(self._recent)[:50]
            return {
                "started_at": self._started_at.isoformat() + "Z",
                "total_requests": self._total,
                "success_requests": self._success,
                "failed_requests": self._failed,
                "requests_last_1m": self._count_since(events, now, 60),
                "requests_last_5m": self._count_since(events, now, 300),
                "requests_last_15m": self._count_since(events, now, 900),
                "failed_last_15m": self._count_since(events, now, 900, success=False),
                "by_source": dict(self._by_source),
                "by_endpoint": dict(self._by_endpoint),
                "by_status_code": dict(self._by_status_code),
                "monitor_queue_depth": self._monitor_queue_depth,
                "monitor_cycle_work_orders": self._monitor_cycle_work_orders,
                "monitor_cycle_started_at": self._monitor_cycle_started_at,
                "monitor_cycle_finished_at": self._monitor_cycle_finished_at,
                "recent_requests": [
                    {key: value for key, value in event.items() if key != "timestamp"}
                    for event in recent
                ],
            }

    @staticmethod
    def _count_since(
        events: list[Dict[str, Any]],
        now: float,
        seconds: int,
        success: Optional[bool] = None,
    ) -> int:
        cutoff = now - seconds
        count = 0
        for event in events:
            if event.get("timestamp", 0) < cutoff:
                continue
            if success is not None and bool(event.get("success")) != success:
                continue
            count += 1
        return count


rate_limiter = OmcRateLimiter()
token_cache = OmcTokenCache()
runtime_stats = OmcRuntimeStats()


def configure_omc_runtime(config: Optional[Dict[str, Any]]) -> Dict[str, int]:
    normalized = normalize_omc_runtime_config(config)
    rate_limiter.configure(
        normalized["rate_limit_per_minute"],
        normalized["rate_limit_burst"],
    )
    return normalized


def acquire_omc_request_slot() -> float:
    return rate_limiter.acquire()


def get_omc_runtime_stats(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized = configure_omc_runtime(config)
    return {
        "config": normalized,
        "limiter": rate_limiter.snapshot(),
        "token_cache": token_cache.snapshot(),
        "stats": runtime_stats.snapshot(),
    }
