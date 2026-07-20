with source as (
    select * from {{ source('dams_prod', 'auth_user') }}
)

select
    id as user_id,
    username,
    first_name,
    last_name
from source
