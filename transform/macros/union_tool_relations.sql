{#
    Generates a UNION ALL across every tracked tool for a given raw table suffix.
    The tool registry lives in dbt_project.yml under `vars.tools`.

    Args:
        suffix:  table suffix, e.g. '_issues' or '_pulls'
        columns: comma-separated column list to select from each raw table
#}
{% macro union_tool_relations(suffix, columns) %}
    {% for tool in var('tools') %}
    select
        {{ columns }},
        '{{ tool.repo }}' as tool_name
    from {{ source('raw_github', tool.repo | replace('-', '_') ~ suffix) }}
    {% if not loop.last %}
    union all
    {% endif %}
    {% endfor %}
{% endmacro %}