import os
import time
import logging
import requests
from typing import Generator, Dict, Any

logger = logging.getLogger(__name__)

class GitHubAPIClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Modern-Data-Stack-Health-Tracker"
        }

    def _handle_rate_limit(self, response: requests.Response):
        """Pause execution if we are approaching GitHub's rate limit."""
        remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
        if remaining < 50:
            reset_time = int(response.headers.get("X-RateLimit-Reset", time.time()))
            sleep_time = max(reset_time - time.time(), 0) + 5
            logger.warning(f"Rate limit low ({remaining}). Sleeping for {sleep_time:.0f} seconds.")
            time.sleep(sleep_time)

    def paginate(self, endpoint: str, params: Dict[str, Any] = None) -> Generator[Dict[str, Any], None, None]:
        """
        Generator that yields items page by page, handling GitHub's Link header pagination.
        """
        params = params or {}
        params.setdefault("per_page", 100) # Max allowed by GitHub
        url = f"{self.base_url}{endpoint}"

        while url:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            self._handle_rate_limit(response)
            
            data = response.json()
            if not data:
                break
                
            yield from data
            
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