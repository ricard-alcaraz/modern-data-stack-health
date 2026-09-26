

with source as (
    select * from read_json_auto('../data/landing/dbt-core/*/pulls.jsonl')
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
        'dbt-core' as tool_name
    from source
)

select * from renamed