-- Business rule: An issue cannot be closed before it is created.
-- If this returns any rows, the test fails.

select 
    issue_id,
    created_at,
    closed_at,
    datediff('day', created_at, closed_at) as close_time_days
from "ci_test"."main"."stg_github_issues"
where closed_at is not null 
  and datediff('day', created_at, closed_at) < 0