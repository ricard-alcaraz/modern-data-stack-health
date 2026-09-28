{{ config(materialized='view') }}

with combined as (
    {{ union_tool_relations(
        suffix='_issues',
        columns='id, number, title, state, created_at, closed_at, updated_at, user, pull_request'
    ) }}
),

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
        user.type as author_type,
        coalesce(user.type = 'Bot', false) as is_bot,
        tool_name
    from deduplicated
    where rn = 1
)

select * from renamed