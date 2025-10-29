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

CREATE TABLE sample_reverted_revision AS
SELECT
    cte1.revision_id AS revision_vandalized,
    cte2.revision_id AS revision_reverted,
    cte1.entity_id,
    cte1.property_id,
    cte1.value_id,
	cte1.old_value as reverted_old_value,
	cte1.new_value as reverted_new_value,
	cte2.old_value as reversion_old_value,
	cte2.new_value as reversion_new_value,
    cte2.comment AS comment_reverted,
    CASE 
        WHEN (cte2.comment ILIKE '%restore%' OR cte1.new_value != cte2.old_value) THEN 'restore'
        ELSE 'undo'
    END as type_revert
FROM change_timestamp_entity cte2
JOIN LATERAL (
    -- pick the most recent earlier cte1 that matches the revert condition
    SELECT cte1.*
    FROM change_timestamp_entity cte1
    WHERE
        cte1.entity_id   = cte2.entity_id
        AND cte1.property_id = cte2.property_id
        AND cte1.value_id    = cte2.value_id
        AND cte1.change_target = cte2.change_target
        AND cte1.timestamp < cte2.timestamp
        AND (
            -- hash is not NULL and cross value match
            (cte1.old_hash IS NOT NULL
             AND cte2.new_hash IS NOT NULL
             AND cte1.old_hash = cte2.new_hash
             AND cte1.old_value = cte2.new_value)
            OR
            -- addition/deletion changes (hashes null so compare hashes/values in the other direction)
            (cte1.old_hash IS NULL
             AND cte2.new_hash IS NULL
             AND cte1.new_hash = cte2.old_hash
             AND cte1.new_value = cte2.old_value)
        )
    ORDER BY cte1.timestamp DESC
    LIMIT 1
) cte1 ON TRUE
WHERE
    cte2.change_target = '' -- only check value changes, not datatype metadata
    -- either within a month or a revert-like comment
    AND (
        cte2.timestamp - cte1.timestamp <= INTERVAL '1 month'
        OR COALESCE(TRIM(cte2.comment), '') ILIKE ANY (ARRAY[
            '%rvv%', '%vandal%', '%rv v%', '%revert%', '%restore%', '%undo%'
        ])
    )
limit 200;

INSERT INTO sample_reverted_revision
SELECT
    c1.revision_id AS revision_vandalized,
    c2.revision_id AS revision_reverted,
    c1.entity_id,
    c1.property_id,
    c1.old_value AS reverted_old_value,
    c1.new_value AS reverted_new_value,
    c2.old_value AS reversion_old_value,
    c2.new_value AS reversion_new_value
FROM change_timestamp_entity c1
JOIN change_timestamp_entity c2
  ON c1.entity_id = c2.entity_id
 AND c1.property_id = c2.property_id
 AND c1.timestamp < c2.timestamp
WHERE c1.change_target = ''
  AND ((c1.old_value IS DISTINCT FROM c2.new_value) or (c1.new_value = c2.old_value and c1.old_value = c2.new_value))  -- ensure not obvious reversion
LIMIT 200;
