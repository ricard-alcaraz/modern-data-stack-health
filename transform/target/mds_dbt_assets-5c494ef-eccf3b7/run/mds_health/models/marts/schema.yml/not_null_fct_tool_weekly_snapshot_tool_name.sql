
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select tool_name
from "mds_health_db"."main"."fct_tool_weekly_snapshot"
where tool_name is null



  
  
      
    ) dbt_internal_test