from abc import ABC, abstractmethod


class Fetcher(ABC):
    """Common interface so the pipeline/parser don't care whether a page came
    from a plain HTTP request or a rendered browser session."""

    @abstractmethod
    def fetch(self, url: str, wait_for_selector: str | None = None) -> str:
        """Return the page's HTML."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any held resources (browser sessions, connection pools)."""
