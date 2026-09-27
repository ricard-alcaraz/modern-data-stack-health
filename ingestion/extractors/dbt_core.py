import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from ingestion.utils.api_client import GitHubAPIClient
from ingestion.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class DbtCoreExtractor(BaseExtractor):
    def __init__(self, client: GitHubAPIClient, landing_dir: str, db_writer=None):
        super().__init__("dbt-labs", "dbt-core", landing_dir, db_writer)
        self.client = client

    def _get_latest_timestamp_from_warehouse(self, table_name: str) -> str:
        """Query MotherDuck to find the latest timestamp we have for this table."""
        if not self.db_writer:
            # If no warehouse, default to 90 days ago
            return (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
        
        try:
            query = f"""
                SELECT MAX(updated_at) as latest 
                FROM raw.{table_name}
            """
            result = self.db_writer.conn.execute(query).fetchone()
            
            if result and result[0]:
                # Return the timestamp in ISO format
                latest = result[0]
                if isinstance(latest, str):
                    return latest
                else:
                    return latest.isoformat() + "Z"
            else:
                # Table is empty or doesn't exist, default to 90 days ago
                return (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"
        except Exception as e:
            logger.warning(f"Could not query warehouse for latest timestamp: {e}. Defaulting to 90 days.")
            return (datetime.utcnow() - timedelta(days=90)).isoformat() + "Z"

    def extract(self):
        logger.info(f"Starting extraction for {self.repo_slug}")
        
        # 1. Extract Repository Metadata (always fetch, it's small)
        repo_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}"))
        if repo_data:
            self._save_raw(repo_data, "repo_metadata.jsonl")

        # 2. Extract Issues (incremental based on warehouse)
        issues_since = self._get_latest_timestamp_from_warehouse("dbt_core_issues")
        logger.info(f"Fetching issues updated since: {issues_since}")
        issues_params = {"state": "all", "since": issues_since}
        issues_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/issues", params=issues_params))
        self._save_raw(issues_data, "issues.jsonl")

        # 3. Extract Pull Requests (incremental based on warehouse)
        pulls_since = self._get_latest_timestamp_from_warehouse("dbt_core_pulls")
        logger.info(f"Fetching pull requests updated since: {pulls_since}")
        pulls_params = {"state": "all", "since": pulls_since, "sort": "updated", "direction": "desc"}
        pulls_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/pulls", params=pulls_params))
        self._save_raw(pulls_data, "pulls.jsonl")

        # 4. Extract Releases (always fetch, they're rare)
        releases_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}/releases"))
        self._save_raw(releases_data, "releases.jsonl")

        logger.info(f"Finished extraction for {self.repo_slug}")