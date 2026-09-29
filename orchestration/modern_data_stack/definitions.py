from dagster import AssetSelection, Definitions, ScheduleDefinition
from dagster_dbt import DbtCliResource

from .assets.dbt import dbt_project, mds_dbt_assets
from .assets.elementary import elementary_observability

# Note: raw_dbt_core_data is now raw_tools_data
from .assets.ingestion import raw_tools_data
from .assets.sources import raw_github_sources

# Define a schedule to run the whole pipeline every day at 6:00 AM
daily_schedule = ScheduleDefinition(
    name="daily_mds_refresh",
    cron_schedule="0 6 * * *",
    target=AssetSelection.all(),
)

# The master Definitions object
defs = Definitions(
    # Note: we unpack raw_github_sources using *
    assets=[
        raw_tools_data,
        mds_dbt_assets,
        *raw_github_sources,
        elementary_observability,
    ],
    schedules=[daily_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project),
    },
)
