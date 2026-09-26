import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from dagster import asset, AssetExecutionContext

# Import your existing extractor
from ingestion.utils.api_client import GitHubAPIClient
from ingestion.extractors.dbt_core import DbtCoreExtractor

@asset(
    group_name="ingestion",
    description="Extracts raw GitHub data (issues, PRs, releases) for dbt-core and lands it as JSONL."
)
def raw_dbt_core_data(context: AssetExecutionContext):
    """Dagster asset wrapping the custom Python GitHub extractor."""
    
    # 1. Load environment variables
    root_dir = Path(__file__).parent.parent.parent.parent
    env_path = root_dir / '.env'
    load_dotenv(dotenv_path=env_path)
    
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN not found in .env")

    landing_dir = os.getenv("LANDING_DIR", "data/landing")

    # 2. Initialize and run the extractor
    context.log.info("Initializing GitHub API Client...")
    client = GitHubAPIClient(token=github_token)
    
    extractor = DbtCoreExtractor(client=client, landing_dir=landing_dir)
    
    context.log.info(f"Starting extraction for {extractor.repo_slug}...")
    extractor.extract()
    
    context.log.info("Ingestion complete. Raw data landed in data/landing/dbt-core/")
    
    # Returning the path tells Dagster where the physical data lives
    return f"{landing_dir}/dbt-core"