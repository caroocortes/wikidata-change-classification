-- ENTITY UNREFINEMENTS
select r.user_type, COUNT(DISTINCT f.revision_id_reversion)
from features_entity f join revision r
on r.revision_id = f.revision_id_reversion -- with this join I get the users that mkae the reversion, not the reverted edit
where f.is_reverted = 1 and f.label = 'unrefinement' 
group by r.user_type


select count(*), user_type
from features_entity f join revision r
on r.revision_id = f.revision_id
where label = 'unrefinement' and is_reverted = 1
group by user_type

-- TEXT REFINEMENTS 
select count(*)
from features_text f 
where label = 'refinement'
-- properties in refinements
SELECT property_id, property_label, count(*)
from features_text
where label = 'refinement'
group by  property_id, property_label
order by count(*) desc
-- entities with changes to label and description
select property_id, property_label, count(distinct entity_id)
from value_change
where property_id = -1 or property_id = -2
group by property_id, property_label

-- TIME UNREFINEMENT ANALYSIS
-- what does the reversion comment say?
select count(*)
from features_time f join revision r on r.revision_id = f.revision_id_reversion
where 
f.label = 'unrefinement' and is_reverted = 1 and 
-- comment is on the reversion edit
((comment ilike '%undo%') or (comment ilike '%reverted%') or (comment ilike '%restore%'))

-- how many reverted unrefinemnt?
select count(*)
from features_time f 
where label = 'unrefinement' and is_reverted = 1

-- QUANTITY UNREFINEMENT ANALYSIS
SELECT 
    COUNT(*) AS total_unrefinements,
    -- floating point artifacts: old value has suspiciously long decimal
    SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) > 10 
        THEN 1 ELSE 0 END) AS long_precision_change,
	SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) <= 10 
		AND new_value->>0 ~ '\.' THEN 1 ELSE 0 END) as small_precision_change,
    -- genuine precision reduction: old value is short but loses decimals
    SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) <= 10
        AND new_value->>0 !~ '\.'
        THEN 1 ELSE 0 END) AS precision_removal
FROM features_quantity
WHERE label = 'unrefinement'


-- TIME REFINEMENT ANALYSIS
WITH time_refinements AS (
    -- Get all time refinements ordered by item + property + time
    SELECT 
		entity_id
        property_id,
		property_label,
        old_value,
        new_value,
        timestamp
    FROM features_time f join revision r on r.revision_id = f.revision_id
	WHERE
    label = 'refinement' and is_reverted = 0 and reversion = 0
	order by property_id, property_label, timestamp
),
incremental_pattern AS (
    -- Check if the pattern is 00 -> non-zero for month or day
    SELECT *,
        -- Month refinement: YYYY-00-00 -> YYYY-MM-00
        CASE WHEN (old_value->>0 ~ '\d+-00-00' or old_value->>0 ~ '\d+-01-01')
              AND new_value->>0 !~ '\d+-00-' and new_value->>0 ~ '-00T'
             THEN 1 ELSE 0 END AS is_month_refinement,
        -- Day refinement: YYYY-MM-00 -> YYYY-MM-DD
        CASE WHEN old_value->>0 ~ '\d+-\d{2}-00' 
              AND new_value->>0 !~ '-00T'
             THEN 1 ELSE 0 END AS is_day_refinement,
		-- Day & Month refinement at the same time
		CASE WHEN (old_value->>0 ~ '\d+-00-00' or old_value->>0 ~ '\d+-01-01')
			AND new_value->>0 !~ '\d+-00-' AND  -- month is not 00
			new_value->>0 !~ '-00T'
			THEN 1 ELSE 0 END AS is_month_day_refinement
    FROM time_refinements
)
SELECT 
    COUNT(*) AS total_time_refinements,
    SUM(is_month_refinement) AS only_month_refinements,
    SUM(is_day_refinement) AS only_day_refinements,
    SUM(is_month_day_refinement) AS day_month_refinements
FROM incremental_pattern;

SELECT 
    COUNT(*) AS total_time_values,
    SUM(CASE WHEN new_value->>0 ~ '^\+?\d+-00-00' or new_value->>0 ~ '^\+?\d+-01-01' THEN 1 ELSE 0 END) AS year_only
FROM value_change v
WHERE action = 'CREATE' and
new_datatype = 'time' and
change_target = ''


-- SOFT INSERTION ANALYSIS
-- how many statements that suffered a soft insertion 
-- have a reason for the preferred rank via the property 7452
select COUNT(*)
from value_change vc
where vc.label = 'soft_insertion'
and is_reverted = 0 and reversion = 0
and exists 
(select 1
from qualifier_change qc
where
qual_property_id = 7452 -- reason for preferred rank
and qc.property_id = vc.property_id and qc.value_id = vc.value_id and qc.entity_id = vc.entity_id
and qc.action = 'CREATE')

-- for statements that suffered a soft insertion
-- what is the reason for the preferred rank (via the property P7452)
WITH latest_reason AS (
    SELECT DISTINCT ON (entity_id, property_id, value_id)
        entity_id, property_id, value_id, new_value
    FROM qualifier_change
    WHERE qual_property_id = 7452
    AND action = 'CREATE'
    ORDER BY entity_id, property_id, value_id, timestamp DESC
)
SELECT lr.new_value, COUNT(*)
FROM value_change vc
JOIN latest_reason lr 
    ON lr.property_id = vc.property_id 
    AND lr.value_id = vc.value_id 
    AND lr.entity_id = vc.entity_id
WHERE vc.label = 'soft_insertion'
AND vc.is_reverted = 0 
AND vc.reversion = 0
GROUP BY lr.new_value
ORDER BY COUNT(*) DESC


-- Check for soft insertions which ones check that there's no other statement
-- with a start time (P580) greater than theirs
select count(*)
from value_change vc 
where label = 'soft_insertion'
and is_reverted = 0 and reversion = 0
and exists (
	select 1
	from qualifier_change qc
	-- the value has a qualifier start time
	where qc.property_id = vc.property_id and qc.value_id = vc.value_id and qc.entity_id = vc.entity_id
	and qc.qual_property_id = 580 and qc.action = 'CREATE'
	and not exists ( 
		-- there's not another value with a start time more recent
		select 1
		from qualifier_change qc2
		-- different value_id
		where qc2.property_id = qc.property_id and qc2.value_id != qc.value_id and qc.entity_id = qc2.entity_id
		and qc2.action = 'CREATE'
		and qc2.qual_property_id = 580 and qc2.new_value->>0 > qc.new_value->>0
		)
)

-- SOFT DELETION ANALYSIS
select COUNT(*)
from value_change vc
where vc.label = 'soft_deletion'
and is_reverted = 0 and reversion = 0
and exists 
(select 1
from qualifier_change qc
where
qual_property_id = 2241 -- reason for deprecated rank
and qc.property_id = vc.property_id and qc.value_id = vc.value_id and qc.entity_id = vc.entity_id
and qc.action = 'CREATE')

-- what are the reasons for sof deletion?
SELECT qc.new_value, COUNT(DISTINCT (vc.entity_id, vc.property_id, vc.value_id))
FROM qualifier_change qc
JOIN value_change vc 
    ON qc.property_id = vc.property_id 
    AND qc.value_id = vc.value_id 
    AND qc.entity_id = vc.entity_id
WHERE qc.qual_property_id = 2241
AND qc.action = 'CREATE'
AND vc.label = 'soft_deletion'
AND vc.is_reverted = 0 
AND vc.reversion = 0
GROUP BY qc.new_value
ORDER BY COUNT(*) DESC