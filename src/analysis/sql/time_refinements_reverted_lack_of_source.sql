-- DATE REFINEMENTS REVERTED BECAUSE OF LACK OF SOURCE (PROPERTY DATE OF BIRTH - P569)
-- total number of refinements reverted
select
	count(*) as total_refs_569
from features_time  f
where f.property_id = 569 and is_reverted = 1 and label = 'refinement';

-- date reifnements that have been reveted and their reversion comment contains "non-WP source(s)"
select
	count(*) as reverted_with_comment 
from features_time f join revision r on r.revision_id = f.revision_id
where f.property_id = 569 and f.label = 'refinement' and revision_id_reversion in (
select revision_id
from revision 
where comment ilike '%non-WP source(s)%'
);