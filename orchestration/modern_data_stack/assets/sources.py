from dagster import AssetKey, AssetSpec

from ingestion.config import TOOLS

# Define the tools and entities to map

ENTITIES = ["issues", "pulls", "releases"]

raw_github_sources = []

# Dynamically generate an AssetSpec for every combination
for tool in TOOLS:
    for entity in ENTITIES:
        table_name = f"{tool.table_prefix}_{entity}"
        raw_github_sources.append(
            AssetSpec(
                # This key must match the source name in dbt's sources.yml
                key=AssetKey(["raw_github", table_name]),
                # This tells Dagster that this source is produced by the ingestion asset
                deps=[AssetKey("raw_tools_data")],
                description=f"Raw GitHub {entity} for {tool.table_prefix.replace('_', ' ').title()}",
            )
        )
