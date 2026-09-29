"""
Lightweight Semantic Layer for the Modern Data Stack Health project.

This module defines business metrics as named, pre-validated SQL queries.
The AI Analyst can reference these by name, ensuring consistent definitions
across all queries and preventing metric drift.

To add a new metric:
1. Add an entry to METRICS below
2. The AI Analyst will automatically know about it
"""

METRICS = {
    "weekly_pr_merge_ratio": {
        "description": (
            "Ratio of PRs merged to PRs opened in a given week (flow-based throughput). "
            "Can exceed 100% when a backlog of older PRs is merged; it is NOT a cohort merge rate."
        ),
        "sql": """
            SELECT 
                tool_name,
                week_start,
                prs_opened,
                prs_merged,
                ROUND(prs_merged * 100.0 / NULLIF(prs_opened, 0), 2) AS merge_ratio_pct
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """,
    },
    "weekly_issue_close_ratio": {
        "description": (
            "Ratio of issues closed to issues opened in a given week (flow-based throughput). "
            "Over 100% means the backlog is shrinking."
        ),
        "sql": """
            SELECT 
                tool_name,
                week_start,
                issues_opened,
                issues_closed,
                ROUND(issues_closed * 100.0 / NULLIF(issues_opened, 0), 2) AS close_ratio_pct
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """,
    },
    "issue_resolution_velocity": {
        "description": (
            "Average days to close issues, per week. NULL (shown as a gap) when no issues "
            "were closed that week. Lower is better."
        ),
        "sql": """
            SELECT 
                tool_name,
                week_start,
                issues_opened,
                issues_closed,
                ROUND(avg_issue_close_time_days, 2) AS avg_close_time_days
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """,
    },
    "issue_backlog_trend": {
        "description": "Net change in open issues per week (opened minus closed). Negative values mean the backlog is shrinking, which is healthy.",
        "sql": """
            SELECT 
                tool_name,
                week_start,
                issues_opened,
                issues_closed,
                (issues_opened - issues_closed) AS net_issue_change
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """,
    },
    "contributor_concentration": {
        "description": (
            "How concentrated contributions are among human authors (bots excluded). "
            "concentration_hhi is the Herfindahl index: 1.0 = one person does everything, near 0 = flat. "
            "top_contributor_share / top5_share are the fraction of all contributions from the top 1 / top 5 authors. "
            "High concentration = bus-factor risk."
        ),
        "sql": """
            WITH all_contributions AS (
                SELECT tool_name, author_login
                FROM stg_github_issues
                WHERE author_login IS NOT NULL AND NOT is_bot
                UNION ALL
                SELECT tool_name, author_login
                FROM stg_github_pulls
                WHERE author_login IS NOT NULL AND NOT is_bot
            ),
            per_author AS (
                SELECT tool_name, author_login, COUNT(*) AS contributions
                FROM all_contributions
                GROUP BY tool_name, author_login
            ),
            with_share AS (
                SELECT
                    tool_name,
                    author_login,
                    contributions,
                    contributions * 1.0 / SUM(contributions) OVER (PARTITION BY tool_name) AS share,
                    ROW_NUMBER() OVER (PARTITION BY tool_name ORDER BY contributions DESC) AS author_rank
                FROM per_author
            )
            SELECT
                tool_name,
                COUNT(DISTINCT author_login) AS unique_contributors,
                SUM(contributions) AS total_contributions,
                ROUND(SUM(share * share), 4) AS concentration_hhi,
                ROUND(MAX(CASE WHEN author_rank = 1 THEN share END), 4) AS top_contributor_share,
                ROUND(SUM(CASE WHEN author_rank <= 5 THEN share ELSE 0 END), 4) AS top5_share
            FROM with_share
            GROUP BY tool_name
            ORDER BY concentration_hhi DESC
        """,
    },
    "top_contributors": {
        "description": "Top 10 most active contributors PER TOOL (bots excluded), ranked by total issues opened + PRs submitted.",
        "sql": """
            WITH all_contributions AS (
                SELECT tool_name, author_login, 'issue' AS type
                FROM stg_github_issues
                WHERE author_login IS NOT NULL AND NOT is_bot
                UNION ALL
                SELECT tool_name, author_login, 'pr' AS type
                FROM stg_github_pulls
                WHERE author_login IS NOT NULL AND NOT is_bot
            ),
            per_author AS (
                SELECT
                    tool_name,
                    author_login,
                    COUNT(*) AS total_contributions,
                    COUNT(CASE WHEN type = 'issue' THEN 1 END) AS issues,
                    COUNT(CASE WHEN type = 'pr' THEN 1 END) AS pull_requests
                FROM all_contributions
                GROUP BY tool_name, author_login
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY tool_name ORDER BY total_contributions DESC) AS tool_rank
                FROM per_author
            )
            SELECT
                tool_name,
                author_login,
                total_contributions,
                issues,
                pull_requests,
                tool_rank
            FROM ranked
            WHERE tool_rank <= 10
            ORDER BY tool_name, tool_rank
        """,
    },
    "contributor_churn": {
        "description": (
            "Contributor churn (bots excluded): of the people active in the prior 90-day window, "
            "the share who made NO contribution in the most recent 90-day window. Lower is healthier. "
            "Requires at least ~180 days of ingested history to be meaningful."
        ),
        "sql": """
            WITH contributions AS (
                SELECT tool_name, author_login, created_at AS contributed_at
                FROM stg_github_issues
                WHERE author_login IS NOT NULL AND NOT is_bot
                UNION ALL
                SELECT tool_name, author_login, created_at AS contributed_at
                FROM stg_github_pulls
                WHERE author_login IS NOT NULL AND NOT is_bot
            ),
            bounds AS (
                SELECT MAX(contributed_at) AS latest FROM contributions
            ),
            windowed AS (
                SELECT
                    c.tool_name,
                    c.author_login,
                    CASE
                        WHEN c.contributed_at >= b.latest - INTERVAL '90 days' THEN 'current'
                        ELSE 'prior'
                    END AS period
                FROM contributions c
                CROSS JOIN bounds b
                WHERE c.contributed_at >= b.latest - INTERVAL '180 days'
            ),
            prior_authors AS (
                SELECT DISTINCT tool_name, author_login FROM windowed WHERE period = 'prior'
            ),
            current_authors AS (
                SELECT DISTINCT tool_name, author_login FROM windowed WHERE period = 'current'
            )
            SELECT
                p.tool_name,
                COUNT(DISTINCT p.author_login) AS prior_contributors,
                COUNT(DISTINCT CASE WHEN c.author_login IS NULL THEN p.author_login END) AS churned_contributors,
                ROUND(
                    COUNT(DISTINCT CASE WHEN c.author_login IS NULL THEN p.author_login END) * 100.0
                    / NULLIF(COUNT(DISTINCT p.author_login), 0), 2
                ) AS churn_rate_pct
            FROM prior_authors p
            LEFT JOIN current_authors c
                ON p.tool_name = c.tool_name AND p.author_login = c.author_login
            GROUP BY p.tool_name
            ORDER BY churn_rate_pct DESC
        """,
    },
    "tool_health_score": {
        "description": (
            "Composite health score per tool. Uses a WEIGHTED average issue-close time "
            "(sum of close-days / issues closed) and caps merge/close ratios at 100% so backlog "
            "burn-down can't inflate the score. Higher is better."
        ),
        "sql": """
            WITH metrics AS (
                SELECT 
                    tool_name,
                    SUM(issue_close_time_days_total) * 1.0 / NULLIF(SUM(issues_closed), 0) AS avg_close_time,
                    LEAST(SUM(prs_merged) * 100.0 / NULLIF(SUM(prs_opened), 0), 100) AS merge_ratio,
                    LEAST(SUM(issues_closed) * 100.0 / NULLIF(SUM(issues_opened), 0), 100) AS close_ratio
                FROM fct_tool_weekly_snapshot
                GROUP BY tool_name
            )
            SELECT 
                tool_name,
                ROUND(merge_ratio, 2) AS pr_merge_ratio_pct,
                ROUND(close_ratio, 2) AS issue_close_ratio_pct,
                ROUND(avg_close_time, 2) AS avg_close_time_days,
                ROUND(
                    (COALESCE(merge_ratio, 0) * 0.4) + 
                    (COALESCE(close_ratio, 0) * 0.3) + 
                    (GREATEST(0, 30 - COALESCE(avg_close_time, 30)) * 100.0 / 30 * 0.3)
                , 2) AS health_score
            FROM metrics
            ORDER BY health_score DESC
        """,
    },
}


def get_semantic_layer_prompt() -> str:
    """Generate a formatted string of all available metrics for the LLM prompt."""
    lines = [
        "AVAILABLE BUSINESS METRICS (use these exact definitions when the user asks about these concepts):"
    ]

    for name, meta in METRICS.items():
        lines.append(f"\n- `{name}`: {meta['description']}")
        lines.append(f"  Pre-defined SQL:\n  ```sql\n  {meta['sql'].strip()}\n  ```")

    lines.append(
        "\nWhen the user asks about one of these metrics, YOU MUST USE the pre-defined SQL. You can wrap it in a CTE or add WHERE clauses to filter by tool_name or date range."
    )
    lines.append("For any other question, write custom SQL using the table schema.")

    return "\n".join(lines)


def get_metric_sql(metric_name: str) -> str | None:
    """Get the SQL for a specific metric by name."""
    metric = METRICS.get(metric_name)
    return metric["sql"] if metric else None


def list_metric_names() -> list[str]:
    """Return a list of all available metric names."""
    return list(METRICS.keys())
