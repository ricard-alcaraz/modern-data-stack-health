-- Reads all JSONL files for dbt-core issues across all dates
{{ config(materialized='view') }}

with source as (
    select * from {{ source('raw_github', 'dbt_core_issues') }}
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