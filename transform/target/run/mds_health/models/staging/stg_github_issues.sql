
  
  create view "ci_test"."main"."stg_github_issues__dbt_tmp" as (
    

with dbt_core as (
    select 
        id, number, title, state, created_at, closed_at, updated_at, 
        user, pull_request, 'dbt-core' as tool_name 
    from "ci_test"."raw"."dbt_core_issues"
),

airflow as (
    select 
        id, number, title, state, created_at, closed_at, updated_at, 
        user, pull_request, 'airflow' as tool_name 
    from "ci_test"."raw"."airflow_issues"
),

dagster as (
    select 
        id, number, title, state, created_at, closed_at, updated_at, 
        user, pull_request, 'dagster' as tool_name 
    from "ci_test"."raw"."dagster_issues"
),

combined as (
    select * from dbt_core
    union all
    select * from airflow
    union all
    select * from dagster
),

-- Filter out PRs (GitHub's /issues endpoint includes both) and deduplicate
deduplicated as (
    select 
        *,
        row_number() over (partition by id order by updated_at desc) as rn
    from combined
    where pull_request is null
),

renamed as (
    select
        id as issue_id,
        number as issue_number,
        title,
        state,
        created_at::timestamp as created_at,
        closed_at::timestamp as closed_at,
        user.login as author_login,
        tool_name
    from deduplicated
    where rn = 1
)

select * from renamed
  );
