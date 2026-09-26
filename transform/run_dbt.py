import os
import sys
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv

def main():
    # 1. Find the root .env file (two levels up from transform/)
    root_dir = Path(__file__).parent.parent
    env_path = root_dir / '.env'
    
    if not env_path.exists():
        print(f"ERROR: Could not find .env file at {env_path}")
        sys.exit(1)
    
    # 2. Load the .env file into the current Python process environment
    load_dotenv(dotenv_path=env_path)
    print(f"Loaded environment variables from {env_path}")
    
    # 3. Get the dbt command from arguments (default to 'build')
    dbt_command = sys.argv[1:] if len(sys.argv) > 1 else ['build']
    
    # 4. Find the dbt executable in the current environment
    dbt_executable = shutil.which('dbt')
    if not dbt_executable:
        print("ERROR: 'dbt' executable not found. Make sure dbt-core is installed in your virtual environment.")
        sys.exit(1)
    
    # 5. Run dbt with the loaded environment variables
    cmd = [dbt_executable] + dbt_command
    
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent)
    
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()