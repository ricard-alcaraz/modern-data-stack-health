import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from ingestion.utils.api_client import GitHubAPIClient
from ingestion.utils.db_writer import MotherDuckWriter
from ingestion.extractors.dbt_core import DbtCoreExtractor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

def main():
    # 1. Load .env file if it exists
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logging.info(f"Loaded environment variables from {env_path}")
    else:
        logging.info("No .env file found. Relying on environment variables (CI/CD mode).")
    
    # 2. Validate required environment variables
    github_token = os.getenv("TOKEN")
    if not github_token:
        raise ValueError("TOKEN not found in environment variables")

    landing_dir = os.getenv("LANDING_DIR", "data/landing")
    
    # 3. Initialize MotherDuck writer (optional - only if MOTHERDUCK_TOKEN is available)
    db_writer = None
    if os.getenv("MOTHERDUCK_TOKEN"):
        try:
            db_writer = MotherDuckWriter()
            logging.info("Initialized MotherDuck writer for durable storage")
        except Exception as e:
            logging.warning(f"Could not initialize MotherDuck writer: {e}. Continuing without durable storage.")

    # 4. Initialize API Client
    client = GitHubAPIClient(token=github_token)

    # 5. Run Extractors
    extractors = [
        DbtCoreExtractor(client=client, landing_dir=landing_dir, db_writer=db_writer),
    ]

    for extractor in extractors:
        try:
            extractor.extract()
        except Exception as e:
            logging.error(f"Failed to extract {extractor.repo_slug}: {e}")
            raise
    
    # 6. Close database connection
    if db_writer:
        db_writer.close()

if __name__ == "__main__":
    main()