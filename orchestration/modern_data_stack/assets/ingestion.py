import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from dagster import asset, AssetExecutionContext

from ingestion.config import TOOLS
from ingestion.utils.api_client import GitHubAPIClient
from ingestion.utils.db_writer import MotherDuckWriter
from ingestion.extractors.github_repo import GitHubRepoExtractor

@asset(
    group_name="ingestion",
    description="Extracts raw GitHub data for all tracked tools and upserts into MotherDuck."
)
def raw_tools_data(context: AssetExecutionContext):
    """Dagster asset wrapping the multi-tool Python extraction."""
    
    root_dir = Path(__file__).parent.parent.parent.parent
    env_path = root_dir / '.env'
    
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        context.log.info(f"Loaded environment variables from {env_path}")

    github_token = os.getenv("TOKEN")
    if not github_token:
        raise ValueError("TOKEN not found in environment variables")

    landing_dir = os.getenv("LANDING_DIR", "data/landing")
    
    db_writer = None
    if os.getenv("MOTHERDUCK_TOKEN"):
        try:
            db_writer = MotherDuckWriter()
            context.log.info("Initialized MotherDuck writer for durable storage")
        except Exception as e:
            context.log.warning(f"Could not initialize MotherDuck writer: {e}")

    client = GitHubAPIClient(token=github_token)

    extractors = [
        GitHubRepoExtractor(
            client=client,
            repo_owner=tool.owner,
            repo_name=tool.repo,
            landing_dir=landing_dir,
            db_writer=db_writer
        )
        for tool in TOOLS
    ]

    for extractor in extractors:
        context.log.info(f"Starting extraction for {extractor.repo_slug}...")
        extractor.extract()
    
    if db_writer:
        db_writer.close()

    context.log.info("Ingestion complete for all tracked tools.")
    return f"Extracted data for {len(extractors)} tools"