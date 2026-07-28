import random
import time
from urllib.parse import urlparse


class RateLimiter:
    """Enforces a politeness delay (+ jitter) between requests to the same domain."""

    def __init__(self, delay_seconds: float = 2.0, jitter_seconds: float = 1.0):
        self.delay_seconds = delay_seconds
        self.jitter_seconds = jitter_seconds
        self._last_request_at: dict[str, float] = {}

    def wait(self, url: str) -> None:
        domain = urlparse(url).netloc
        last = self._last_request_at.get(domain)
        if last is not None:
            elapsed = time.monotonic() - last
            required = self.delay_seconds + random.uniform(0, self.jitter_seconds)
            remaining = required - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at[domain] = time.monotonic()
