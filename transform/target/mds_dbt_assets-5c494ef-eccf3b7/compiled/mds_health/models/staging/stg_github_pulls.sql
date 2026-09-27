

with combined as (
    
    
    select
        id, number, title, state, created_at, merged_at, closed_at, updated_at, user,
        'dbt-core' as tool_name
    from "mds_health_db"."raw"."dbt_core_pulls"
    
    union all
    
    
    select
        id, number, title, state, created_at, merged_at, closed_at, updated_at, user,
        'airflow' as tool_name
    from "mds_health_db"."raw"."airflow_pulls"
    
    union all
    
    
    select
        id, number, title, state, created_at, merged_at, closed_at, updated_at, user,
        'dagster' as tool_name
    from "mds_health_db"."raw"."dagster_pulls"
    
    

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