{#
    Force tout modèle dans le schéma bi_ (défini dans le profil dbt), sans suffixe
    <target_schema>_<custom_schema> par défaut de dbt. Choix : un seul schéma bi_
    pour staging ET marts, conforme à ADR-005 (schéma isolé unique côté BI).
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema }}
{%- endmacro %}
