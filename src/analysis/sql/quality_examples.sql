-- DEAD LINK CHANGES
select 
	f.revision_id, f.property_id, f.property_label, f.old_value, f.new_value, 
	f.old_value_label, f.new_value_label, f.label, r.entity_id, r.q_id_redirect
from features_entity f, revision r, revision rt
where 
f.label = 'link_change' and 
f.is_reverted = 0 and 
f.new_value_label != '' and 
f.old_value_label != '' and 
-- new value is an entity that got redirected to the old value
f.new_value->>0 = 'Q' || r.entity_id and 
r.redirect and not exists (select 1 from revision r2 where r.entity_id = r2.entity_id and r2.timestamp > r.timestamp) -- and the redirect was not undone
and 'Q' || r.q_id_redirect = f.old_value->>0 and 
-- join with revision to get timestamp
rt.revision_id = f.revision_id and
-- keep the ones when the change in link happened after the entities were redirected
rt.timestamp > r.timestamp;


-- DATE REFINEMENTS REVERTED BECAUSE OF LACK OF SOURCE
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


--- DIFFERENT FORMATS FOR THE SAME PROPERTY
-- get the most recent value for property 2035 per entity
WITH latest_values AS (
    SELECT DISTINCT ON (r.entity_id)
        r.entity_id,
        f.new_value->>0,
		CASE WHEN f.new_value->>0 LIKE '%/' 
	        THEN 'with slash' 
	        ELSE 'without slash' 
	    END as format,
		user_type,
		username
    FROM features_text f
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE f.property_id = 2035
    AND f.is_reverted = 0
    ORDER BY r.entity_id, r.timestamp DESC
)
SELECT 
    format,
	user_type,
	username,
    COUNT(*) as total,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) as pct
FROM latest_values
GROUP BY format, user_type, username;


-- OSCILLATIONS FOR REFINEMENTS/UNREFINEMENTS IN ENTITY CHANGES
WITH entity_changes AS (
    SELECT 
        r.entity_id,
        f.property_id,
		f.value_id,
        f.property_label,
        f.old_value_label,
        f.new_value_label,
        f.label,
        r.timestamp,
        -- check if next change on same entity+property+value is the opposite
        LEAD(f.label) OVER (
            PARTITION BY r.entity_id, f.property_id, f.value_id
            ORDER BY r.timestamp asc
        ) AS next_label
    FROM features_entity f
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE f.label IN ('refinement', 'unrefinement')
    AND f.is_reverted = 0
),
oscillations AS (
    SELECT *
    FROM entity_changes
    WHERE (label = 'refinement' AND next_label = 'unrefinement')
    OR (label = 'unrefinement' AND next_label = 'refinement')
)
SELECT 
    entity_id,
    property_id,
	value_id,
    property_label,
    COUNT(*) as oscillation_count,
    -- show the sequence of values
    array_agg(old_value_label || ' → ' || new_value_label 
        ORDER BY timestamp) as change_sequence
FROM oscillations
GROUP BY entity_id, property_id, property_label, value_id
HAVING COUNT(*) >= 2  -- at least 2 oscillations
ORDER BY oscillation_count DESC;