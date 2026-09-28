import logging
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from ingestion.utils.sql_utils import safe_identifier

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    def __init__(self, repo_owner: str, repo_name: str, landing_dir: str, db_writer=None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_slug = f"{repo_owner}/{repo_name}"
        self.landing_dir = Path(landing_dir) / self.repo_name
        self.today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.db_writer = db_writer

    def _get_latest_timestamp_from_warehouse(self, table_name: str) -> Optional[datetime]:
        """Query MotherDuck to find the latest timestamp we have for this table."""
        default_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        
        if not self.db_writer:
            return default_cutoff
        
        safe_table_name = safe_identifier(table_name)
        
        try:
            query = f"SELECT MAX(updated_at) as latest FROM raw.{safe_table_name}"
            result = self.db_writer.conn.execute(query).fetchone()
            
            if result and result[0]:
                latest = result[0]
                if isinstance(latest, datetime):
                    if latest.tzinfo is None:
                        return latest.replace(tzinfo=timezone.utc)
                    return latest
                elif isinstance(latest, str):
                    return datetime.fromisoformat(latest.replace("Z", "+00:00"))
            return default_cutoff
        
        except Exception as e:
            logger.warning(f"Could not query warehouse for latest timestamp: {e}. Defaulting to 90 days.")
            return default_cutoff
    def _save_raw(self, data: List[Dict[str, Any]], filename: str):
        """Saves data as JSONL locally AND upserts to MotherDuck."""
        if not data:
            logger.info(f"No data to save for {filename}")
            return

        # 1. Save to local landing zone
        output_dir = self.landing_dir / self.today_str
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        
        logger.info(f"Saved {len(data)} records to {filepath}")
        
        # 2. Save to MotherDuck
        if self.db_writer:
            table_name = f"{self.repo_name.replace('-', '_')}_{filename.replace('.jsonl', '')}"
            abs_filepath = str(filepath.absolute())
            self.db_writer.write_raw_table(table_name, abs_filepath)

    @abstractmethod
    def extract(self):
        """To be implemented by specific tool extractors."""
        pass