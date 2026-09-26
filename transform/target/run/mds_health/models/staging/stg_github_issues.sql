
  
  create view "mds_health_db"."main"."stg_github_issues__dbt_tmp" as (
    -- Reads all JSONL files for dbt-core issues across all dates


with source as (
    select * from '../data/landing/dbt-core/*/issues.jsonl'
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
        pull_request is not null as is_pull_request,
        'dbt-core' as tool_name
    from source
    where pull_request is null
)

select * from renamed
  );
