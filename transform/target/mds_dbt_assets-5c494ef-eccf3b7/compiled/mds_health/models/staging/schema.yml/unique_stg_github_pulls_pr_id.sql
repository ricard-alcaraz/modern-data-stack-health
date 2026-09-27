
    
    

select
    pr_id as unique_field,
    count(*) as n_records

from "mds_health_db"."main"."stg_github_pulls"
where pr_id is not null
group by pr_id
having count(*) > 1


