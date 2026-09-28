import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from ingestion.config import TOOLS
from ingestion.extractors.github_repo import GitHubRepoExtractor
from ingestion.utils.api_client import GitHubAPIClient
from ingestion.utils.db_writer import MotherDuckWriter

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / ".env"

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logging.info(f"Loaded environment variables from {env_path}")
    else:
        logging.info(
            "No .env file found. Relying on environment variables (CI/CD mode)."
        )

    github_token = os.getenv("TOKEN")
    if not github_token:
        raise ValueError("TOKEN not found in environment variables")

    landing_dir = os.getenv("LANDING_DIR", "data/landing")

    db_writer = None
    if os.getenv("MOTHERDUCK_TOKEN"):
        try:
            db_writer = MotherDuckWriter()
            logging.info("Initialized MotherDuck writer for durable storage")
        except Exception as e:
            logging.warning(
                f"Could not initialize MotherDuck writer: {e}. Continuing without durable storage."
            )

    client = GitHubAPIClient(token=github_token)

    # Instantiate the generic extractor for each tool
    extractors = [
        GitHubRepoExtractor(
            client=client,
            repo_owner=tool.owner,
            repo_name=tool.repo,
            landing_dir=landing_dir,
            db_writer=db_writer,
        )
        for tool in TOOLS
    ]

    for extractor in extractors:
        try:
            extractor.extract()
        except Exception as e:
            logging.error(f"Failed to extract {extractor.repo_slug}: {e}")
            raise

    if db_writer:
        db_writer.close()

    logging.info(f"✅ Successfully extracted data for {len(extractors)} tools")


if __name__ == "__main__":
    main()
