import logging
from ingestion.utils.api_client import GitHubAPIClient
from ingestion.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)

class GitHubRepoExtractor(BaseExtractor):
    """Generic extractor for any GitHub repository."""
    
    def __init__(self, client: GitHubAPIClient, repo_owner: str, repo_name: str, 
                 landing_dir: str, db_writer=None):
        super().__init__(repo_owner, repo_name, landing_dir, db_writer)
        self.client = client

    def extract(self):
        logger.info(f"Starting extraction for {self.repo_slug}")
        
        # 1. Repository Metadata
        repo_data = list(self.client.paginate(f"/repos/{self.repo_owner}/{self.repo_name}"))
        if repo_data:
            self._save_raw(repo_data, "repo_metadata.jsonl")

        # 2. Issues (incremental)
        table_name = f"{self.repo_name.replace('-', '_')}_issues"
        issues_since_dt = self._get_latest_timestamp_from_warehouse(table_name)
        # GitHub API accepts ISO 8601 format
        issues_since = issues_since_dt.isoformat() if issues_since_dt else None
        
        logger.info(f"Fetching issues updated since: {issues_since}")
        issues_params = {"state": "all", "since": issues_since}
        issues_data = list(self.client.paginate(
            f"/repos/{self.repo_owner}/{self.repo_name}/issues", 
            params=issues_params
        ))
        self._save_raw(issues_data, "issues.jsonl")

        # 3. Pull Requests (incremental)
        table_name_pr = f"{self.repo_name.replace('-', '_')}_pulls"
        pulls_since_dt = self._get_latest_timestamp_from_warehouse(table_name_pr)
        
        logger.info(f"Fetching pull requests updated since: {pulls_since_dt.isoformat() if pulls_since_dt else 'N/A'}")
        
        pulls_params = {"state": "all", "sort": "updated", "direction": "desc"}
        
        pulls_data = []
        for pr in self.client.paginate(
            f"/repos/{self.repo_owner}/{self.repo_name}/pulls", 
            params=pulls_params
        ):
            pr_updated_str = pr.get("updated_at")
            
            if pulls_since_dt and pr_updated_str:
                try:
                    from datetime import datetime
                    # Handle 'Z' suffix safely
                    pr_updated_dt = datetime.fromisoformat(pr_updated_str.replace("Z", "+00:00"))
                    if pr_updated_dt < pulls_since_dt:
                        logger.info("Reached PRs older than the incremental threshold, stopping pagination early.")
                        break
                except ValueError:
                    logger.warning(f"Could not parse PR updated_at: {pr_updated_str}")
                    
            pulls_data.append(pr)
            
        self._save_raw(pulls_data, "pulls.jsonl")

        # 4. Releases
        releases_data = list(self.client.paginate(
            f"/repos/{self.repo_owner}/{self.repo_name}/releases"
        ))
        self._save_raw(releases_data, "releases.jsonl")

        logger.info(f"Finished extraction for {self.repo_slug}")