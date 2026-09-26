

with issues as (
    select
        tool_name,
        date_trunc('week', created_at) as week_start,
        count_if(state = 'open') as issues_opened,
        count_if(state = 'closed') as issues_closed,
        avg(datediff('day', created_at, closed_at)) as avg_issue_close_time_days
    from "mds_health_db"."main"."stg_github_issues"
    group by 1, 2
),

pulls as (
    select
        tool_name,
        date_trunc('week', created_at) as week_start,
        count_if(state = 'open') as prs_opened,
        count_if(merged_at is not null) as prs_merged
    from "mds_health_db"."main"."stg_github_pulls"
    group by 1, 2
)

select
    coalesce(i.tool_name, p.tool_name) as tool_name,
    coalesce(i.week_start, p.week_start) as week_start,
    coalesce(i.issues_opened, 0) as issues_opened,
    coalesce(i.issues_closed, 0) as issues_closed,
    round(coalesce(i.avg_issue_close_time_days, 0), 2) as avg_issue_close_time_days,
    coalesce(p.prs_opened, 0) as prs_opened,
    coalesce(p.prs_merged, 0) as prs_merged
from issues i
full outer join pulls p 
    on i.tool_name = p.tool_name 
    and i.week_start = p.week_start