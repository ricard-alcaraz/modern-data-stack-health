import os
import logging
import duckdb
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class MotherDuckWriter:
    def __init__(self, database: str = "mds_health_db"):
        self.token = os.getenv("MOTHERDUCK_TOKEN")
        if not self.token:
            raise ValueError("MOTHERDUCK_TOKEN not found in environment variables")
        
        self.conn = duckdb.connect(f"md:{database}?motherduck_token={self.token}")
        self.database = database
        self.conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        logger.info(f"Connected to MotherDuck database: {database}")
    
    def _table_has_column(self, table_name: str, column_name: str) -> bool:
        """Check if a table has a specific column."""
        result = self.conn.execute(f"""
            SELECT COUNT(*) > 0 FROM information_schema.columns 
            WHERE table_schema = 'raw' AND table_name = '{table_name}' 
            AND column_name = '{column_name}'
        """).fetchone()
        return result[0] if result else False
    
    def write_raw_table(self, table_name: str, jsonl_filepath: str):
        """Reads a JSONL file and writes it to a MotherDuck table."""
        full_table_name = f"raw.{table_name}"
        temp_table = f"temp_{table_name}"
        # Use date only, not full timestamp
        extracted_at = datetime.utcnow().date().isoformat()
        
        # 1. Read the new JSONL data into a temporary table
        self.conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
        self.conn.execute(f"""
            CREATE TEMP TABLE {temp_table} AS 
            SELECT 
                *,
                '{extracted_at}'::DATE as extracted_at
            FROM read_json_auto('{jsonl_filepath}')
        """)
        
        # 2. Check if the target table exists
        table_exists = self.conn.execute(f"""
            SELECT COUNT(*) > 0 FROM information_schema.tables 
            WHERE table_schema = 'raw' AND table_name = '{table_name}'
        """).fetchone()[0]
        
        if not table_exists:
            # First run: just create the table from the temp table
            self.conn.execute(f"CREATE TABLE {full_table_name} AS SELECT * FROM {temp_table}")
            row_count = self.conn.execute(f"SELECT COUNT(*) FROM {full_table_name}").fetchone()[0]
            logger.info(f"Created {full_table_name} with {row_count} rows")
        elif self._table_has_column(table_name, 'id'):
            # Table exists AND has an 'id' column (issues, pulls, releases)
            # -> UPSERT: delete old rows, insert new ones
            self.conn.execute(f"""
                DELETE FROM {full_table_name} 
                WHERE id IN (SELECT id FROM {temp_table})
            """)
            
            # Get common columns to avoid schema mismatch
            target_cols = [row[0] for row in self.conn.execute(f"DESCRIBE {full_table_name}").fetchall()]
            temp_cols = [row[0] for row in self.conn.execute(f"DESCRIBE {temp_table}").fetchall()]
            common_cols = [col for col in target_cols if col in temp_cols]
            cols_str = ", ".join(common_cols)
            
            self.conn.execute(f"""
                INSERT INTO {full_table_name} ({cols_str})
                SELECT {cols_str} FROM {temp_table}
            """)
            
            row_count = self.conn.execute(f"SELECT COUNT(*) FROM {full_table_name}").fetchone()[0]
            logger.info(f"Upserted data into {full_table_name}. Total rows: {row_count}")
        else:
            # Table exists but has NO 'id' column (e.g., repo_metadata)
            # -> FULL REPLACE: drop and recreate
            self.conn.execute(f"DROP TABLE {full_table_name}")
            self.conn.execute(f"CREATE TABLE {full_table_name} AS SELECT * FROM {temp_table}")
            row_count = self.conn.execute(f"SELECT COUNT(*) FROM {full_table_name}").fetchone()[0]
            logger.info(f"Replaced {full_table_name} with {row_count} rows")
        
        # Clean up
        self.conn.execute(f"DROP TABLE IF EXISTS {temp_table}")
    
    def close(self):
        self.conn.close()