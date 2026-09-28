"""
Central tool registry for the Modern Data Stack Health project.

THIS IS THE SINGLE SOURCE OF TRUTH for which repositories the *Python* side tracks.
Every Python module (ingestion, orchestration, tests) imports from here.

To add a new tool:
  1. Add ONE `Tool(...)` entry to TOOLS below.
  2. Mirror the repo name in `transform/dbt_project.yml` under `vars.tools`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tool:
    owner: str  # GitHub org / user, e.g. "dbt-labs"
    repo: str  # GitHub repository name, e.g. "dbt-core"

    @property
    def slug(self) -> str:
        """`owner/repo` — used for GitHub API paths and logging."""
        return f"{self.owner}/{self.repo}"

    @property
    def tool_name(self) -> str:
        """Canonical warehouse tool name (equals the repo name)."""
        return self.repo

    @property
    def table_prefix(self) -> str:
        """Normalized prefix for raw warehouse tables (dashes -> underscores)."""
        return self.repo.replace("-", "_")


TOOLS: tuple[Tool, ...] = (
    Tool(owner="dbt-labs", repo="dbt-core"),
    Tool(owner="apache", repo="airflow"),
    Tool(owner="dagster-io", repo="dagster"),
)


def owner_repo_pairs() -> list[tuple[str, str]]:
    """Legacy `[(owner, repo), ...]` shape, for call sites not yet migrated."""
    return [(t.owner, t.repo) for t in TOOLS]


def table_prefixes() -> list[str]:
    """Normalized table prefixes, e.g. ['dbt_core', 'airflow', 'dagster']."""
    return [t.table_prefix for t in TOOLS]
