import logging
import os
from datetime import datetime, timezone

import duckdb

from ingestion.utils.sql_utils import quote_literal, safe_identifier

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
            WHERE table_schema = 'raw' AND table_name = '{safe_identifier(table_name)}' 
            AND column_name = '{safe_identifier(column_name)}'
        """).fetchone()
        return result[0] if result else False

    def write_raw_table(self, table_name: str, jsonl_filepath: str):
        """Reads a JSONL file and writes it to a MotherDuck table."""
        full_table_name = f"raw.{table_name}"
        temp_table = f"temp_{table_name}"
        extracted_at = datetime.now(timezone.utc).date().isoformat()
        # 1. Read the new JSONL data into a temporary table
        # IMPORTANT: Deduplicate by id within the source data itself
        # (GitHub API can return the same item twice if it was updated during pagination)
        # Also explicitly cast id to BIGINT to avoid type mismatches
        self.conn.execute(f"DROP TABLE IF EXISTS {safe_identifier(temp_table)}")

        if self._jsonl_has_id_field(jsonl_filepath):
            # For tables with 'id', deduplicate at the source
            self.conn.execute(f"""
                CREATE TEMP TABLE {safe_identifier(temp_table)} AS 
                SELECT DISTINCT ON (id)
                    *,
                    '{extracted_at}'::DATE as extracted_at
                FROM read_json_auto({quote_literal(jsonl_filepath)})
                ORDER BY id, updated_at DESC NULLS LAST
            """)
        else:
            # For tables without 'id' (like repo_metadata), just read as-is
            self.conn.execute(f"""
                CREATE TEMP TABLE {safe_identifier(temp_table)} AS 
                SELECT 
                    *,
                    '{extracted_at}'::DATE as extracted_at
                FROM read_json_auto({quote_literal(jsonl_filepath)})
            """)

        temp_row_count = self.conn.execute(
            f"SELECT COUNT(*) FROM {safe_identifier(temp_table)}"
        ).fetchone()[0]
        logger.info(
            f"Loaded {temp_row_count} rows from {jsonl_filepath} into temp table"
        )

        # 2. Check if the target table exists
        table_exists = self.conn.execute(f"""
            SELECT COUNT(*) > 0 FROM information_schema.tables 
            WHERE table_schema = 'raw' AND table_name = '{safe_identifier(table_name)}'
        """).fetchone()[0]

        if not table_exists:
            # First run: just create the table from the temp table
            self.conn.execute(
                f"CREATE TABLE {safe_identifier(full_table_name)} AS SELECT * FROM {safe_identifier(temp_table)}"
            )
            row_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {safe_identifier(full_table_name)}"
            ).fetchone()[0]
            logger.info(f"Created {full_table_name} with {row_count} rows")
        elif self._table_has_column(table_name, "id"):
            # Table exists AND has an 'id' column -> UPSERT

            # First, check how many rows we're about to delete (for debugging)
            dup_count = self.conn.execute(f"""
                SELECT COUNT(*) FROM {safe_identifier(full_table_name)} 
                WHERE id IN (SELECT id FROM {safe_identifier(temp_table)})
            """).fetchone()[0]
            logger.info(
                f"Found {dup_count} existing rows to replace in {full_table_name}"
            )

            # Delete existing rows that are being updated
            # Explicitly cast both sides to BIGINT to avoid type mismatches
            self.conn.execute(f"""
                DELETE FROM {safe_identifier(full_table_name)} 
                WHERE CAST(id AS BIGINT) IN (SELECT CAST(id AS BIGINT) FROM {safe_identifier(temp_table)})
            """)

            # Get common columns to avoid schema mismatch
            target_cols = [row[0] for row in self.conn.execute(f"DESCRIBE {safe_identifier(full_table_name)}").fetchall()]
            temp_cols = [row[0] for row in self.conn.execute(f"DESCRIBE {safe_identifier(temp_table)}").fetchall()]
            common_cols = [col for col in target_cols if col in temp_cols]
            
            select_cols = []
            for col in common_cols:
                # Get the target column type
                target_type = self.conn.execute(f"""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'raw' 
                    AND table_name = '{safe_identifier(table_name)}'
                    AND column_name = '{safe_identifier(col)}'
                """).fetchone()[0]
                
                # Cast the temp column to match target type
                select_cols.append(f"TRY_CAST({safe_identifier(col)} AS {target_type}) AS {safe_identifier(col)}")
            
            cols_str = ", ".join([safe_identifier(col) for col in common_cols])
            select_str = ", ".join(select_cols)
            
            self.conn.execute(f"""
                INSERT INTO {safe_identifier(full_table_name)} ({cols_str})
                SELECT {select_str} FROM {safe_identifier(temp_table)}
            """)

            row_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {safe_identifier(full_table_name)}"
            ).fetchone()[0]
            logger.info(
                f"Upserted data into {safe_identifier(full_table_name)}. Total rows: {row_count}"
            )
        else:
            # Table exists but has NO 'id' column (e.g., repo_metadata) -> FULL REPLACE
            self.conn.execute(f"DROP TABLE {safe_identifier(full_table_name)}")
            self.conn.execute(
                f"CREATE TABLE {safe_identifier(full_table_name)} AS SELECT * FROM {safe_identifier(temp_table)}"
            )
            row_count = self.conn.execute(
                f"SELECT COUNT(*) FROM {safe_identifier(full_table_name)}"
            ).fetchone()[0]
            logger.info(
                f"Replaced {safe_identifier(full_table_name)} with {row_count} rows"
            )

        # Clean up
        self.conn.execute(f"DROP TABLE IF EXISTS {safe_identifier(temp_table)}")

    def _jsonl_has_id_field(self, jsonl_filepath: str) -> bool:
        """Check if the JSONL file contains an 'id' field by sampling the first row."""
        try:
            result = self.conn.execute(f"""
                SELECT COUNT(*) > 0 FROM read_json_auto({quote_literal(jsonl_filepath)})
                LIMIT 1
            """).fetchone()

            if not result or not result[0]:
                return False

            # Check if 'id' is in the columns
            cols = [
                row[0]
                for row in self.conn.execute(f"""
                DESCRIBE SELECT * FROM read_json_auto({quote_literal(jsonl_filepath)}) LIMIT 1
            """).fetchall()
            ]
            return "id" in cols
        except Exception as e:
            logger.warning(f"Could not inspect JSONL file: {e}")
            return False

    def close(self):
        self.conn.close()
