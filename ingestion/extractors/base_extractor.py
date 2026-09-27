import os
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BaseExtractor(ABC):
    def __init__(self, repo_owner: str, repo_name: str, landing_dir: str, db_writer=None):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.repo_slug = f"{repo_owner}/{repo_name}"
        self.landing_dir = Path(landing_dir) / self.repo_name
        self.today_str = datetime.utcnow().strftime("%Y-%m-%d")
        self.db_writer = db_writer

    def _save_raw(self, data: List[Dict[str, Any]], filename: str):
        """Saves data as newline-delimited JSON (JSONL) to the landing zone AND to MotherDuck."""
        # 1. Save to local landing zone
        output_dir = self.landing_dir / self.today_str
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")
        
        logger.info(f"Saved {len(data)} records to {filepath}")
        
        # 2. Save to MotherDuck (for production durability)
        if self.db_writer:
            # Convert repo name to valid table name (replace hyphens with underscores)
            table_name = f"{self.repo_name.replace('-', '_')}_{filename.replace('.jsonl', '')}"
            
            # Convert path to absolute path for DuckDB
            abs_filepath = str(filepath.absolute())
            
            # Write to MotherDuck
            self.db_writer.write_raw_table(table_name, abs_filepath)

    @abstractmethod
    def extract(self):
        """To be implemented by specific tool extractors."""
        pass