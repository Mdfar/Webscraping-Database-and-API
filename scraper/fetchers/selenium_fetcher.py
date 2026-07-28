import logging

from retrying import Retrying
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import Fetcher

logger = logging.getLogger(__name__)


class SeleniumFetcher(Fetcher):
    """Fetches JS-rendered HTML via a headless Chrome session."""

    def __init__(
        self,
        user_agent: str | None = None,
        timeout_seconds: int = 15,
        max_retries: int = 3,
        retry_wait_fixed_ms: int = 2000,
        headless: bool = True,
    ):
        options = Options()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        if user_agent:
            options.add_argument(f"--user-agent={user_agent}")

        self.driver = webdriver.Chrome(options=options)
        self.timeout_seconds = timeout_seconds
        self._retryer = Retrying(
            stop_max_attempt_number=max_retries,
            wait_fixed=retry_wait_fixed_ms,
            retry_on_exception=lambda exc: isinstance(exc, (TimeoutException, WebDriverException)),
        )

    def _do_fetch(self, url: str, wait_for_selector: str | None) -> str:
        self.driver.get(url)
        if wait_for_selector:
            WebDriverWait(self.driver, self.timeout_seconds).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, wait_for_selector))
            )
        return self.driver.page_source

    def fetch(self, url: str, wait_for_selector: str | None = None) -> str:
        logger.info("GET (selenium) %s", url)
        try:
            return self._retryer.call(self._do_fetch, url, wait_for_selector)
        except Exception:
            logger.exception("Failed to fetch %s after retries", url)
            raise

    def close(self) -> None:
        try:
            self.driver.quit()
        except Exception:  # noqa: BLE001
            pass
