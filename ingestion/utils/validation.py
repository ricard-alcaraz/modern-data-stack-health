"""
Pre-load data quality gate using Great Expectations.

This module validates the *raw* extracted data from GitHub API,,
so a schema change or bad payload from GitHub never reaches the warehouse.
"""

from __future__ import annotations

import logging
from typing import Any

import great_expectations as gx
import pandas as pd

logger = logging.getLogger(__name__)

_context = gx.get_context(mode="ephemeral")
_data_source = _context.data_sources.add_pandas(name="raw_github_payloads")

_EXPECTATIONS: dict[str, dict[str, list]] = {
    "issues": {
        "critical": [
            gx.expectations.ExpectColumnValuesToNotBeNull(column="id"),
            gx.expectations.ExpectColumnValuesToBeUnique(column="id"),
            gx.expectations.ExpectColumnValuesToNotBeNull(column="created_at"),
            gx.expectations.ExpectColumnDistinctValuesToBeInSet(
                column="state", value_set=["open", "closed"]
            ),
        ],
        "warning": [
            gx.expectations.ExpectTableRowCountToBeBetween(min_value=0, max_value=5000),
        ],
    },
    "pulls": {
        "critical": [
            gx.expectations.ExpectColumnValuesToNotBeNull(column="id"),
            gx.expectations.ExpectColumnValuesToBeUnique(column="id"),
            gx.expectations.ExpectColumnValuesToNotBeNull(column="created_at"),
            gx.expectations.ExpectColumnDistinctValuesToBeInSet(
                column="state", value_set=["open", "closed"]
            ),
        ],
        "warning": [
            gx.expectations.ExpectTableRowCountToBeBetween(min_value=0, max_value=5000),
        ],
    },
    "releases": {
        "critical": [
            gx.expectations.ExpectColumnValuesToNotBeNull(column="id"),
            gx.expectations.ExpectColumnValuesToBeUnique(column="id"),
        ],
        "warning": [],
    },
    "repo_metadata": {
        "critical": [
            gx.expectations.ExpectColumnValuesToNotBeNull(column="id"),
        ],
        "warning": [],
    },
}

# Build every suite + batch definition once at import time, keyed by (entity, severity)
_BATCH_DEFS: dict[tuple[str, str], Any] = {}

for _entity, _spec in _EXPECTATIONS.items():
    for _severity, _expectations in _spec.items():
        if not _expectations:
            continue

        _suite = gx.ExpectationSuite(name=f"{_entity}_{_severity}")
        for _exp in _expectations:
            _suite.add_expectation(_exp)
        _context.suites.add(_suite)

        _asset = _data_source.add_dataframe_asset(name=f"{_entity}_{_severity}_asset")
        _batch_def = _asset.add_batch_definition_whole_dataframe(
            f"{_entity}_{_severity}_batch"
        )
        _BATCH_DEFS[(_entity, _severity)] = (_batch_def, _suite)


def _run_suite(df: pd.DataFrame, entity: str, severity: str) -> list[str]:
    """Runs the pre-built suite for (entity, severity) against a fresh df."""
    entry = _BATCH_DEFS.get((entity, severity))
    if entry is None:
        return []

    batch_def, suite = entry
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})
    result = batch.validate(suite)

    return [
        r["expectation_config"]["type"] for r in result["results"] if not r["success"]
    ]


def validate_raw_batch(data: list[dict[str, Any]], entity: str) -> None:
    """
    Validates a raw GitHub payload before it's persisted.

    Raises ValueError on a critical failure. Logs and continues on a
    warning-only failure.
    """
    if entity not in _EXPECTATIONS or not data:
        return

    df = pd.DataFrame(data)

    critical_failures = _run_suite(df, entity, "critical")
    warning_failures = _run_suite(df, entity, "warning")

    if warning_failures:
        logger.warning(
            f"[GX] {entity}: {len(warning_failures)} warning-level check(s) failed: "
            f"{warning_failures}"
        )

    if critical_failures:
        raise ValueError(
            f"[GX] {entity}: critical data quality check(s) failed: {critical_failures}. "
            "Refusing to load this batch."
        )
