
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- Asserts that (tool_name, week_start) is a unique combination in the mart.
-- If this query returns rows, the test will fail, indicating a fan-out in the full outer join.
select 
    tool_name, 
    week_start, 
    count(*) as n
from "mds_health_db"."main"."fct_tool_weekly_snapshot"
group by 1, 2
having count(*) > 1
  
  
      
    ) dbt_internal_test