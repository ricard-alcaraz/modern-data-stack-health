from dagster import AssetSpec, AssetKey

# Define the tools and entities to map
TOOLS = ["dbt_core", "airflow", "dagster"]
ENTITIES = ["issues", "pulls", "releases"]

raw_github_sources = []

# Dynamically generate an AssetSpec for every combination
for tool in TOOLS:
    for entity in ENTITIES:
        table_name = f"{tool}_{entity}"
        raw_github_sources.append(
            AssetSpec(
                # This key must match the source name in dbt's sources.yml
                key=AssetKey(["raw_github", table_name]),
                # This tells Dagster that this source is produced by the ingestion asset
                deps=[AssetKey("raw_tools_data")], 
                description=f"Raw GitHub {entity} for {tool.replace('_', ' ').title()}",
            )
        )