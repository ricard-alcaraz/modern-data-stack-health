
    
    

select
    issue_id as unique_field,
    count(*) as n_records

from "mds_health_db"."main"."stg_github_issues"
where issue_id is not null
group by issue_id
having count(*) > 1


