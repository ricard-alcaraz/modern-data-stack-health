import logging
import time
from collections.abc import Generator
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class GitHubAPIClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Modern-Data-Stack-Health-Tracker",
        }

        self.session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[403, 429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.headers.update(self.headers)

    def _handle_rate_limit(self, response: requests.Response):
        """Proactively pause execution if we are approaching GitHub's primary rate limit."""
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining < 50:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
            sleep_time = max(reset_time - time.time(), 0) + 5
            logger.warning(
                f"Rate limit low ({remaining}). Proactively sleeping for {sleep_time:.0f} seconds."
            )
            time.sleep(sleep_time)

    def paginate(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> Generator[dict[str, Any], None, None]:
        """
        Generator that yields items page by page, handling GitHub's Link header pagination.
        """
        params = params or {}
        params.setdefault("per_page", 100)  # Max allowed by GitHub
        url = f"{self.base_url}{endpoint}"

        while url:
            response = self.session.get(url, params=params, timeout=15)
            self._handle_rate_limit(response)

            response.raise_for_status()

            data = response.json()
            if not data:
                break

            if isinstance(data, list):
                yield from data
            else:
                yield data
                break  # Single object endpoints do not have pagination

            # Check for 'next' page in Link header
            link_header = response.headers.get("Link")
            url = None
            if link_header:
                links = link_header.split(",")
                for link in links:
                    if 'rel="next"' in link:
                        url = link.split(";")[0].strip().strip("<>")
                        break

            # Clear params for subsequent requests as the 'url' from Link header is absolute
            params = {}
