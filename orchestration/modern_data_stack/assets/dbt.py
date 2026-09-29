from pathlib import Path

from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# 1. Resolve the absolute path to the dbt project directory
DBT_PROJECT_DIR = Path(__file__).parent.parent.parent.parent / "transform"

# 2. Initialize the DbtProject object
dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
)

# 3. Prepare the project
dbt_project.prepare_if_dev()


# 4. Define the assets
@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
    select="staging intermediate marts",
)
def mds_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Runs dbt source freshness, then dbt build.
    If freshness fails (stale data), the asset fails and dbt build is skipped.
    """

    # --- STEP 1: Freshness Gate (dbt-native) ---
    context.log.info("🔍 Running dbt source freshness...")
    # dbt.cli raises an exception if the command returns a non-zero exit code.
    # dbt source freshness returns exit code 1 for warnings, 2 for errors.
    yield from dbt.cli(
        ["source", "freshness", "--target", "prod"], context=context
    ).stream()

    # --- STEP 2: Build (Only runs if Step 1 succeeds) ---
    context.log.info("✅ Freshness check passed. Running dbt build...")
    yield from dbt.cli(["build", "--target", "prod"], context=context).stream()
