import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv


def main():
    transform_dir = Path(__file__).parent
    root_dir = transform_dir.parent
    env_path = root_dir / ".env"

    # Load root .env
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)

    # Explicitly tell dbt where profiles.yml is.
    os.environ["DBT_PROFILES_DIR"] = str(transform_dir)

    # Run Elementary from transform/
    result = subprocess.run(
        ["edr", *sys.argv[1:]],
        cwd=transform_dir,
        env=os.environ.copy(),
    )

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
