import os
import logging
from dotenv import load_dotenv
from pathlib import Path

from ingestion.utils.api_client import GitHubAPIClient
from ingestion.extractors.dbt_core import DbtCoreExtractor
# Future: from ingestion.extractors.airflow import AirflowExtractor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    # 1. Load environment variables
    # 1. Explicitly point to the root .env file, regardless of where the script is run
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    
    if not env_path.exists():
        raise FileNotFoundError(f"Could not find .env file at {env_path}")
        
    load_dotenv(dotenv_path=env_path)
    
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN not found in .env file")

    landing_dir = os.getenv("LANDING_DIR", "data/landing")

    # 2. Initialize API Client
    client = GitHubAPIClient(token=github_token)

    # 3. Run Extractors
    extractors = [
        DbtCoreExtractor(client=client, landing_dir=landing_dir),
        # Add AirflowExtractor, DagsterExtractor, etc.,
    ]

    for extractor in extractors:
        try:
            extractor.extract()
        except Exception as e:
            logging.error(f"Failed to extract {extractor.repo_slug}: {e}")

if __name__ == "__main__":
    main()