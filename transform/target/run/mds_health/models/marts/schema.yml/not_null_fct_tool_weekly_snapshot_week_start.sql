
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select week_start
from "ci_test"."main"."fct_tool_weekly_snapshot"
where week_start is null



  
  
      
    ) dbt_internal_test