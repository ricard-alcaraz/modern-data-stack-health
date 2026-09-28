import subprocess
from pathlib import Path
from dagster import asset, AssetExecutionContext

TRANSFORM_DIR = Path(__file__).parent.parent.parent.parent / "transform"


@asset(
    deps=["mds_dbt_assets"],  # Run after dbt build completes
    group_name="observability",
    description="Run Elementary data quality tests and populate observability tables",
)
def elementary_tests(context: AssetExecutionContext):
    """Run Elementary tests against production data after dbt build."""
    
    context.log.info("Running Elementary tests against production...")
    
    # Run Elementary tests (this populates the elementary schema in MotherDuck)
    result = subprocess.run(
        ["dbt", "test", "--select", "elementary", "--target", "prod"],
        cwd=TRANSFORM_DIR,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        context.log.warning(f"Some Elementary tests failed or warned:\n{result.stdout}")
        # Don't fail the asset - test failures are informational
    else:
        context.log.info("All Elementary tests passed")
    
    # Also check source freshness
    context.log.info("Checking source freshness...")
    freshness_result = subprocess.run(
        ["dbt", "source", "freshness"],
        cwd=TRANSFORM_DIR,
        capture_output=True,
        text=True,
    )
    context.log.info(f"Freshness check completed:\n{freshness_result.stdout}")
    
    return {"status": "complete", "tests_run": True}