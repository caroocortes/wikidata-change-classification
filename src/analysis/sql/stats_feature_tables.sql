select 'number of entity changes' as metric, count(*) as count
from features_entity
union all
select 'number of text changes' as metric ,count(*) as count
from features_text
union all
select 'number of quantity changes' as metric,count(*) as count
from features_quantity
union all
select 'number of globe changes' as metric,count(*) as count
from features_globecoordinate
union all
select 'number of time changes' as metric,count(*) as count
from features_time