import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from ingestion.utils.api_client import GitHubAPIClient
from ingestion.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class DbtCoreExtractor(BaseExtractor):
    def __init__(self, client: GitHubAPIClient, landing_dir: str):
        super().__init__("dbt-labs", "dbt-core", landing_dir)
        self.client = client
        # Look back 90 days for incremental-like extraction
        self.since_date = (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"

    def extract(self):
        logger.info(f"Starting extraction for {self.repo_slug}")
        
        # 1. Extract Repository Metadata
        repo_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}"))
        if repo_data:
            self._save_raw(repo_data, "repo_metadata.jsonl")

        # 2. Extract Issues (state=all includes closed issues, which we need for close-time metrics)
        # Note: GitHub's /issues endpoint includes PRs. We will filter them out or let dbt handle it.
        # Using 'since' makes this incremental and fast.
        issues_params = {"state": "all", "since": self.since_date}
        issues_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/issues", params=issues_params))
        self._save_raw(issues_data, "issues.jsonl")

        # 3. Extract Pull Requests (using the dedicated pulls endpoint for cleaner PR-specific data)
        pulls_params = {"state": "all", "sort": "updated", "direction": "desc"}
        pulls_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/pulls", params=pulls_params))
        self._save_raw(pulls_data, "pulls.jsonl")

        # 4. Extract Releases
        releases_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/releases"))
        self._save_raw(releases_data, "releases.jsonl")

        logger.info(f"Finished extraction for {self.repo_slug}")