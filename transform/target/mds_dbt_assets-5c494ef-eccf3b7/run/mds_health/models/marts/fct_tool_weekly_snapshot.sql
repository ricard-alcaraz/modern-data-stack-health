
    

    create  table
      "mds_health_db"."main"."fct_tool_weekly_snapshot__dbt_tmp"
  
    
    as (
      

with issue_opened_events as (
    select
        tool_name,
        date_trunc('week', created_at) as week_start,
        count(*) as issues_opened
    from "mds_health_db"."main"."stg_github_issues"
    where created_at is not null
    group by 1, 2
),

issue_closed_events as (
    select
        tool_name,
        date_trunc('week', closed_at) as week_start,
        count(*) as issues_closed,
        avg(datediff('day', created_at, closed_at)) as avg_issue_close_time_days
    from "mds_health_db"."main"."stg_github_issues"
    where closed_at is not null
    group by 1, 2
),

issue_metrics as (
    select
        coalesce(o.tool_name, c.tool_name) as tool_name,
        coalesce(o.week_start, c.week_start) as week_start,
        coalesce(o.issues_opened, 0) as issues_opened,
        coalesce(c.issues_closed, 0) as issues_closed,
        round(coalesce(c.avg_issue_close_time_days, 0), 2) as avg_issue_close_time_days
    from issue_opened_events o
    full outer join issue_closed_events c 
        on o.tool_name = c.tool_name 
        and o.week_start = c.week_start
),

pr_opened_events as (
    select
        tool_name,
        date_trunc('week', created_at) as week_start,
        count(*) as prs_opened
    from "mds_health_db"."main"."stg_github_pulls"
    where created_at is not null
    group by 1, 2
),

pr_merged_events as (
    select
        tool_name,
        date_trunc('week', merged_at) as week_start,
        count(*) as prs_merged
    from "mds_health_db"."main"."stg_github_pulls"
    where merged_at is not null
    group by 1, 2
),

pr_metrics as (
    select
        coalesce(o.tool_name, m.tool_name) as tool_name,
        coalesce(o.week_start, m.week_start) as week_start,
        coalesce(o.prs_opened, 0) as prs_opened,
        coalesce(m.prs_merged, 0) as prs_merged
    from pr_opened_events o
    full outer join pr_merged_events m 
        on o.tool_name = m.tool_name 
        and o.week_start = m.week_start
)

select
    coalesce(i.tool_name, p.tool_name) as tool_name,
    coalesce(i.week_start, p.week_start) as week_start,
    coalesce(i.issues_opened, 0) as issues_opened,
    coalesce(i.issues_closed, 0) as issues_closed,
    coalesce(i.avg_issue_close_time_days, 0) as avg_issue_close_time_days,
    coalesce(p.prs_opened, 0) as prs_opened,
    coalesce(p.prs_merged, 0) as prs_merged
from issue_metrics i
full outer join pr_metrics p 
    on i.tool_name = p.tool_name 
    and i.week_start = p.week_start
    );
    
  