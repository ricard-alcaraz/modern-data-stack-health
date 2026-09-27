"""
Load test fixtures into a local DuckDB database for CI testing.
This script creates a deterministic test environment that doesn't require
external API calls or MotherDuck access.
"""

import duckdb
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ingestion.config import TOOLS

def load_fixtures(db_path: str = "ci_test.duckdb"):
    """Load all test fixtures into a local DuckDB database."""
    
    fixtures_dir = Path(__file__).parent / "fixtures"
    
    if not fixtures_dir.exists():
        print(f"Error: Fixtures directory not found at {fixtures_dir}")
        sys.exit(1)
    
    # Connect to local DuckDB
    conn = duckdb.connect(db_path)
    
    # Create raw schema
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    
    # Load each fixture

    data_types = ["issues", "pulls", "releases"]
    
    for tool in TOOLS:
        for data_type in data_types:
            table_name = f"{tool.repo}_{data_type}"
            fixture_path = fixtures_dir / f"{table_name}.jsonl"
            
            if not fixture_path.exists():
                print(f"Warning: Fixture not found: {fixture_path}")
                continue
            
            # Drop table if exists, then create from JSONL
            conn.execute(f"DROP TABLE IF EXISTS raw.{table_name}")
            conn.execute(f"""
                CREATE TABLE raw.{table_name} AS 
                SELECT * FROM read_json_auto('{fixture_path}')
            """)
            
            row_count = conn.execute(f"SELECT COUNT(*) FROM raw.{table_name}").fetchone()[0]
            print(f"✓ Loaded {row_count} rows into raw.{table_name}")
    
    conn.close()
    print(f"\n✅ All fixtures loaded into {db_path}")

if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "ci_test.duckdb"
    load_fixtures(db_path)