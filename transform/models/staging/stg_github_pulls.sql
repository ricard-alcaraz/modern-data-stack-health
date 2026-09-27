{{ config(materialized='view') }}

with dbt_core as (
    select 
        id, number, title, state, created_at, merged_at, closed_at, updated_at, 
        user, 'dbt-core' as tool_name 
    from {{ source('raw_github', 'dbt_core_pulls') }}
),

airflow as (
    select 
        id, number, title, state, created_at, merged_at, closed_at, updated_at, 
        user, 'airflow' as tool_name 
    from {{ source('raw_github', 'airflow_pulls') }}
),

dagster as (
    select 
        id, number, title, state, created_at, merged_at, closed_at, updated_at, 
        user, 'dagster' as tool_name 
    from {{ source('raw_github', 'dagster_pulls') }}
),

combined as (
    select * from dbt_core
    union all
    select * from airflow
    union all
    select * from dagster
),

deduplicated as (
    select 
        *,
        row_number() over (partition by id order by updated_at desc) as rn
    from combined
),

renamed as (
    select
        id as pr_id,
        number as pr_number,
        title,
        state,
        created_at::timestamp as created_at,
        merged_at::timestamp as merged_at,
        closed_at::timestamp as closed_at,
        user.login as author_login,
        tool_name
    from deduplicated
    where rn = 1
)

select * from renamed