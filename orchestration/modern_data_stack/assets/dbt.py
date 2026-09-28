from pathlib import Path
from dagster import AssetExecutionContext
from dagster_dbt import DbtCliResource, DbtProject, dbt_assets

# 1. Resolve the absolute path to the dbt project directory
DBT_PROJECT_DIR = Path(__file__).parent.parent.parent.parent / "transform"

# 2. Initialize the DbtProject object
dbt_project = DbtProject(
    project_dir=DBT_PROJECT_DIR,
)

# 3. Prepare the project (this runs `dbt parse` to generate the manifest.json)
dbt_project.prepare_if_dev()

# 4. Define the assets - Dagster will auto-infer dependencies from the dbt manifest
@dbt_assets(
    manifest=dbt_project.manifest_path,
    project=dbt_project,
)
def mds_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    """Runs dbt build and streams results to Dagster."""
    yield from dbt.cli(["build", "--target", "prod"], context=context).stream()