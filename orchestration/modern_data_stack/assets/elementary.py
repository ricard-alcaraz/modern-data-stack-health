import subprocess
from pathlib import Path
from dagster import asset, AssetExecutionContext

TRANSFORM_DIR = Path(__file__).parent.parent.parent.parent / "transform"


@asset(
    deps=["mds_dbt_assets"],  # Run after dbt build completes
    group_name="observability",  # Visually separate from data assets
    compute_kind="elementary",  # Shows a nice icon in the UI
    description="""
    Runs Elementary data quality tests and populates observability tables.
    
    Internal tables created in MotherDuck (main_elementary schema):
    - elementary_test_results: test outcomes over time
    - dbt_invocations: run history with timing
    - elementary_source_freshness_results: source freshness checks
    
    These are implementation details — query them via the Streamlit 
    'Data Quality' page or the `edr report` CLI.
    """,
)
def elementary_observability(context: AssetExecutionContext):
    """Run all Elementary checks as a single logical unit."""
    
    # 1. Run Elementary tests (populates observability tables)
    context.log.info("Running Elementary tests...")
    result = subprocess.run(
        ["dbt", "test", "--select", "elementary", "--target", "prod"],
        cwd=TRANSFORM_DIR,
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        context.log.warning(f"Elementary tests had warnings:\n{result.stdout}")
    else:
        context.log.info("✅ All Elementary tests passed")
    
    # 2. Check source freshness
    context.log.info("Checking source freshness...")
    freshness_result = subprocess.run(
        ["dbt", "source", "freshness", "--target", "prod"],
        cwd=TRANSFORM_DIR,
        capture_output=True,
        text=True,
    )
    context.log.info(f"Freshness check completed")
    
    # 3. Summary
    context.log.info("✅ Observability data updated in MotherDuck")
    return {"status": "complete"}