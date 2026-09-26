from dagster import AssetSpec, AssetKey

# Define specs for each raw source table
# These tell Dagster that these "assets" are produced by the ingestion asset
raw_github_sources = [
    AssetSpec(
        key=AssetKey(["raw_github", "dbt_core_issues"]),
        deps=[AssetKey("raw_dbt_core_data")],
        description="Raw GitHub issues for dbt-core",
    ),
    AssetSpec(
        key=AssetKey(["raw_github", "dbt_core_pulls"]),
        deps=[AssetKey("raw_dbt_core_data")],
        description="Raw GitHub pull requests for dbt-core",
    ),
    AssetSpec(
        key=AssetKey(["raw_github", "dbt_core_releases"]),
        deps=[AssetKey("raw_dbt_core_data")],
        description="Raw GitHub releases for dbt-core",
    ),
]