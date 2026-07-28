import logging

import requests
from retrying import Retrying

from .base import Fetcher

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    def __init__(self, status_code: int, url: str):
        self.status_code = status_code
        super().__init__(f"Retryable HTTP {status_code} for {url}")


class StaticFetcher(Fetcher):
    """Fetches static HTML via requests, with retry/backoff for transient failures."""

    def __init__(
        self,
        headers: dict | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 3,
        retry_wait_fixed_ms: int = 2000,
    ):
        self.session = requests.Session()
        self.session.headers.update(headers or {})
        self.timeout_seconds = timeout_seconds
        self._retryer = Retrying(
            stop_max_attempt_number=max_retries,
            wait_fixed=retry_wait_fixed_ms,
            retry_on_exception=self._is_retryable,
        )

    @staticmethod
    def _is_retryable(exc: BaseException) -> bool:
        return isinstance(exc, (requests.exceptions.ConnectionError,
                                 requests.exceptions.Timeout,
                                 RetryableHTTPError))

    def _do_fetch(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout_seconds)
        if response.status_code in _RETRYABLE_STATUS:
            raise RetryableHTTPError(response.status_code, url)
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text

    def fetch(self, url: str, wait_for_selector: str | None = None) -> str:
        logger.info("GET %s", url)
        try:
            return self._retryer.call(self._do_fetch, url)
        except Exception:
            logger.exception("Failed to fetch %s after retries", url)
            raise

    def close(self) -> None:
        self.session.close()
