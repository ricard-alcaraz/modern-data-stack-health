
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select pr_id
from "mds_health_db"."main"."stg_github_pulls"
where pr_id is null



  
  
      
    ) dbt_internal_test