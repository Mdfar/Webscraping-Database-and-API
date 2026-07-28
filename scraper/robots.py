import logging
import urllib.robotparser
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Per-domain robots.txt cache. Fails open (allows) if robots.txt can't be fetched,
    since a missing/unreachable robots.txt does not itself forbid crawling.
    """

    def __init__(self, user_agent: str, enabled: bool = True):
        self.user_agent = user_agent
        self.enabled = enabled
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _get_parser(self, url: str):
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._parsers:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(origin + "/robots.txt")
            try:
                rp.read()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not read robots.txt for %s (%s); allowing by default", origin, exc)
                rp = None
            self._parsers[origin] = rp
        return self._parsers[origin]

    def is_allowed(self, url: str) -> bool:
        if not self.enabled:
            return True
        parser = self._get_parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:  # noqa: BLE001
            return True
