{{ config(materialized='view') }}

with combined as (
    {{ union_tool_relations(
        suffix='_pulls',
        columns='id, number, title, state, created_at, merged_at, closed_at, updated_at, user'
    ) }}
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