
select 'number of entities' as metric, count(*)
from entity_stats<suffix>
union all
select  'number value changes' as metric, SUM(num_value_changes)
from entity_stats<suffix>
union all 
select  'number of revisions' as metric, SUM(num_revisions)
from entity_stats<suffix>
union all
select  'number value change creates' as metric, SUM(num_value_change_creates)
from entity_stats<suffix>
union all
select  'number value change deletes' as metric, SUM(num_value_change_deletes)
from entity_stats<suffix>
union all
select  'number value change updates' as metric, SUM(num_value_change_updates)
from entity_stats<suffix>
union all
select  'number rank changes' as metric, SUM(num_rank_changes)
from entity_stats<suffix>
union all
select  'number qualifier changes' as metric, SUM(num_qualifier_changes)
from entity_stats<suffix>
union all
select  'number reference changes' as metric, SUM(num_reference_changes)
from entity_stats<suffix>
union all
select  'number bot changes' as metric, SUM(num_bot_edits)
from entity_stats<suffix>
union all 
select  'number bot changes' as metric, SUM(num_anonymous_edits)
from entity_stats<suffix>
union all
select  'number human changes' as metric, SUM(num_human_edits)
from entity_stats<suffix>
union all
select  'number reverted edits' as metric, SUM(num_reverted_edits)
from entity_stats<suffix>
union all
select  'number of reversions' as metric, SUM(num_reversions)
from entity_stats<suffix>
union all
select  'number of reverted creates' as metric, SUM(num_reverted_edits_create)
from entity_stats<suffix>
union all
select  'number of reverted deletes' as metric, SUM(num_reverted_edits_delete)
from entity_stats<suffix>
union all
select  'number of reverted updates' as metric, SUM(num_reverted_edits_update)
from entity_stats<suffix>
union all
select 'number of features for datatype text' as metric, count(*)
from features_text<suffix>
union all
select 'number of features for datatype quantity' as metric, count(*)
from features_quantity<suffix>
union all
select 'number of features for datatype time' as metric, count(*)
from features_time<suffix>
union all
select 'number of features for datatype globe-coordinate' as metric, count(*)
from features_globecoordinate<suffix>
union all
select 'number of features for datatype entity' as metric, count(*)
from features_entity<suffix>
;