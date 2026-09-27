import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    # 1. Load .env file if it exists (for local development)
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded environment variables from {env_path}")
    else:
        logger.info("No .env file found. Relying on environment variables (CI/CD mode).")
    
    # 2. Get the dbt command from arguments (default to 'build')
    dbt_command = sys.argv[1:] if len(sys.argv) > 1 else ['build']
    
    # 3. Find the dbt executable in the current environment
    dbt_executable = shutil.which('dbt')
    if not dbt_executable:
        logger.error("ERROR: 'dbt' executable not found. Make sure dbt-core is installed.")
        sys.exit(1)
    
    # 4. Run dbt with the loaded environment variables
    cmd = [dbt_executable] + dbt_command
    
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()