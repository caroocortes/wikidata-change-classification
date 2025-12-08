-- sample 200 classified as "typo"
CREATE TABLE sample_typo AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	new_value
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE typo = TRUE
ORDER BY random()
LIMIT 200;

-- sample 200 classified as "formatting"
CREATE TABLE sample_formatting AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	new_value
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE formatting = TRUE
ORDER BY random()
LIMIT 200;

-- sample 200 classified as "value_refinement"
CREATE TABLE sample_value_refinement AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	new_value
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE value_refinement = TRUE
ORDER BY random()
LIMIT 200;

-- sample 200 classified as "value_unrefinement"
CREATE TABLE sample_value_unrefinement AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	new_value
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE value_unrefinement = TRUE
ORDER BY random()
LIMIT 200;

CREATE TABLE sample_random_entity_update AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	old_value_label
	new_value,
	new_value_label
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE 
	change_target = '' and
	datatype = 'wikibase-entityid' and 
	not (typo or formatting or value_refinement or value_unrefinement or reverted_edit or reversion or property_replacement)
	and action = 'UPDATE'
ORDER BY random()
LIMIT 200;


CREATE TABLE sample_random_non_entity_update AS
SELECT 
	r.revision_id, 
	entity_id,
	property_id,
	property_label,
	old_value,
	old_value_label
	new_value,
	new_value_label
FROM value_change_sample_30 vc join revision_sample_30 r on vc.revision_id = r.revision_id
WHERE 
	change_target = '' and
	datatype != 'wikibase-entityid' and 
	not (typo or formatting or value_refinement or value_unrefinement or reverted_edit or reversion or property_replacement)
	and action = 'UPDATE'
ORDER BY random()
LIMIT 200;


CREATE TABLE sample_property_replacement AS
select 
		cte1.entity_id as entity_id,
        cte1.revision_id as replaced_revision_id,
        cte1.property_id as replaced_property_id, 
        cte1.value_id as replaced_value_id,
		cte1.old_value as replaced_old_value,
        cte2.revision_id as replacement_revision_id, 
        cte2.property_id as replacement_property_id, 
        cte2.value_id as replacement_value_id,
		cte2.new_value as replacement_new_value
    from 
        change_timestamp_entity cte1 join change_timestamp_entity cte2 on 
        cte1.entity_id = cte2.entity_id and cte1.old_value = cte2.new_value
    where 
        cte1.change_target = '' and -- only check value changes
        cte2.change_target = '' and -- only check value changes
        cte1.timestamp <= cte2.timestamp and
        cte1.property_id != cte2.property_id and
        cte1.action = 'DELETE' and
        cte2.action = 'CREATE'
limit 200;

INSERT INTO sample_property_replacement
select 
		cte1.entity_id as entity_id,
        cte1.revision_id as replaced_revision_id,
        cte1.property_id as replaced_property_id, 
        cte1.value_id as replaced_value_id,
		cte1.old_value as replaced_old_value,
        cte2.revision_id as replacement_revision_id, 
        cte2.property_id as replacement_property_id, 
        cte2.value_id as replacement_value_id,
		cte2.new_value as replacement_new_value
    from 
        change_timestamp_entity cte1 join change_timestamp_entity cte2 on 
        cte1.entity_id = cte2.entity_id 
    where 
        cte1.change_target = '' and -- only check value changes
        cte2.change_target = '' and -- only check value changes
        cte1.timestamp <= cte2.timestamp and
        cte1.property_id != cte2.property_id and
        cte1.action = 'DELETE' and
        cte2.action = 'CREATE'
limit 200;


WITH random_sample AS (
    SELECT 
        r.revision_id, 
        r.entity_id,
        r.entity_label,
        vc.value_id,
        vc.property_id,
        vc.change_target,
        vc.property_label,
        vc.old_value,
        vc.old_value_label,
        vc.new_value,
        vc.new_value_label,
        vc.datatype,
        r.comment,
        r.timestamp
    FROM value_change vc 
    JOIN revision r ON r.revision_id = vc.revision_id 
    WHERE COALESCE(TRIM(r.comment), '') ILIKE ANY (ARRAY[
        '%rvv%', '%vandal%', '%rv v%', '%revert%', '%restore%', '%undo%'
    ]) 
	AND change_target = ''
    AND reversion = FALSE AND reverted_edit = FALSE
    AND file_path != 'wikidatawiki-20250601-pages-meta-history27.xml-p106201964p106272172.bz2'
    LIMIT 100
),
next_10_revisions AS (
    SELECT 
        rs.revision_id as anchor_revision_id,
        rs.entity_id,
        rs.property_id as anchor_property_id,
        rs.value_id as anchor_value_id,
        r.revision_id,
        r.timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY rs.revision_id, rs.property_id, rs.value_id, rs.change_target
            ORDER BY r.timestamp ASC
        ) as revision_rank
    FROM random_sample rs
    JOIN revision r ON r.entity_id = rs.entity_id
    JOIN value_change vc ON vc.revision_id = r.revision_id
        AND vc.property_id = rs.property_id      -- Same property
        AND vc.value_id = rs.value_id            -- Same value
    WHERE r.timestamp <= rs.timestamp AND vc.change_target = ''  -- Get revisions AFTER or at anchor time
)
SELECT 
    n10r.anchor_revision_id,
    r.revision_id, 
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
    n10r.revision_rank,
    r.timestamp,
    r.comment,
    vc.reverted_edit
FROM next_10_revisions n10r
JOIN revision r ON n10r.revision_id = r.revision_id
 JOIN value_change vc ON vc.revision_id = r.revision_id 
    AND vc.property_id = n10r.anchor_property_id 
    AND vc.value_id = n10r.anchor_value_id 
WHERE n10r.revision_rank <= 10 AND vc.change_target = ''
ORDER BY n10r.anchor_revision_id, r.timestamp ASC;