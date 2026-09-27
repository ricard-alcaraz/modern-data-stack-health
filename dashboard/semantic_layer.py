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
    "weekly_pr_merge_rate": {
        "description": "Percentage of opened PRs that were merged in a given week. Higher is better — indicates a healthy, responsive review process.",
        "sql": """
            SELECT 
                tool_name,
                week_start,
                SUM(prs_opened) as prs_opened,
                SUM(prs_merged) as prs_merged,
                ROUND(SUM(prs_merged) * 100.0 / NULLIF(SUM(prs_opened), 0), 2) as merge_rate_pct
            FROM fct_tool_weekly_snapshot
            GROUP BY tool_name, week_start
            ORDER BY tool_name, week_start
        """
    },
    "issue_resolution_velocity": {
        "description": "Average number of days to close an issue per week. Lower is better — indicates faster bug resolution.",
        "sql": """
            SELECT 
                tool_name,
                week_start,
                issues_opened,
                issues_closed,
                ROUND(avg_issue_close_time_days, 2) as avg_close_time_days
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """
    },
    "issue_backlog_trend": {
        "description": "Net change in open issues per week (opened minus closed). Negative values mean the backlog is shrinking, which is healthy.",
        "sql": """
            SELECT 
                tool_name,
                week_start,
                issues_opened,
                issues_closed,
                (issues_opened - issues_closed) as net_issue_change
            FROM fct_tool_weekly_snapshot
            ORDER BY tool_name, week_start
        """
    },
    "contributor_concentration": {
        "description": "Number of unique contributors and total contributions per tool. A high ratio of contributions-per-person suggests reliance on a small core team.",
        "sql": """
            WITH all_contributions AS (
                SELECT tool_name, author_login FROM stg_github_issues
                WHERE author_login IS NOT NULL
                UNION ALL
                SELECT tool_name, author_login FROM stg_github_pulls
                WHERE author_login IS NOT NULL
            )
            SELECT 
                tool_name,
                COUNT(DISTINCT author_login) as unique_contributors,
                COUNT(*) as total_contributions,
                ROUND(COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT author_login), 0), 2) as avg_contributions_per_person
            FROM all_contributions
            GROUP BY tool_name
            ORDER BY unique_contributors DESC
        """
    },
    "top_contributors": {
        "description": "Top 10 most active contributors per tool by total issues opened and PRs submitted.",
        "sql": """
            WITH all_contributions AS (
                SELECT tool_name, author_login, 'issue' as type FROM stg_github_issues
                WHERE author_login IS NOT NULL
                UNION ALL
                SELECT tool_name, author_login, 'pr' as type FROM stg_github_pulls
                WHERE author_login IS NOT NULL
            )
            SELECT 
                tool_name,
                author_login,
                COUNT(*) as total_contributions,
                COUNT(CASE WHEN type = 'issue' THEN 1 END) as issues,
                COUNT(CASE WHEN type = 'pr' THEN 1 END) as pull_requests
            FROM all_contributions
            GROUP BY tool_name, author_login
            ORDER BY total_contributions DESC
            LIMIT 10
        """
    },
    "tool_health_score": {
        "description": "A composite health score per tool based on PR merge rate, issue close time, and contributor count. Higher is better.",
        "sql": """
            WITH metrics AS (
                SELECT 
                    tool_name,
                    AVG(avg_issue_close_time_days) as avg_close_time,
                    SUM(prs_merged) * 100.0 / NULLIF(SUM(prs_opened), 0) as merge_rate,
                    SUM(issues_closed) * 100.0 / NULLIF(SUM(issues_opened), 0) as close_rate
                FROM fct_tool_weekly_snapshot
                GROUP BY tool_name
            )
            SELECT 
                tool_name,
                ROUND(merge_rate, 2) as pr_merge_rate_pct,
                ROUND(close_rate, 2) as issue_close_rate_pct,
                ROUND(avg_close_time, 2) as avg_close_time_days,
                ROUND(
                    (COALESCE(merge_rate, 0) * 0.4) + 
                    (COALESCE(close_rate, 0) * 0.3) + 
                    (GREATEST(0, 30 - COALESCE(avg_close_time, 30)) * 100.0 / 30 * 0.3)
                , 2) as health_score
            FROM metrics
            ORDER BY health_score DESC
        """
    }
}


def get_semantic_layer_prompt() -> str:
    """Generate a formatted string of all available metrics for the LLM prompt."""
    lines = ["AVAILABLE BUSINESS METRICS (use these when the user asks about these concepts):"]
    
    for name, meta in METRICS.items():
        lines.append(f"\n- `{name}`: {meta['description']}")
    
    lines.append("\nWhen the user asks about one of these metrics, use the pre-defined SQL.")
    lines.append("You can add WHERE clauses to filter by tool_name or date range.")
    lines.append("For any other question, write custom SQL using the table schema.")
    
    return "\n".join(lines)


def get_metric_sql(metric_name: str) -> str | None:
    """Get the SQL for a specific metric by name."""
    metric = METRICS.get(metric_name)
    return metric["sql"] if metric else None


def list_metric_names() -> list[str]:
    """Return a list of all available metric names."""
    return list(METRICS.keys())