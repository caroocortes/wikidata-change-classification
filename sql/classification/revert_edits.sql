ALTER TABLE :change
ADD COLUMN IF NOT EXISTS reverted_edit BOOLEAN DEFAULT FALSE;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS reversion BOOLEAN DEFAULT FALSE;

CREATE MATERIALIZED VIEW IF NOT EXISTS change_timestamp_entity AS
SELECT r.timestamp, r.entity_id, c.*, r.comment
FROM :revision r JOIN :change c ON r.revision_id = c.revision_id
WHERE reverted_edit = FALSE AND reversion = FALSE
WITH DATA;

CREATE INDEX idx_cte_join_conditions 
ON change_timestamp_entity (entity_id, property_id, value_id, change_target, timestamp);

-- Index for hash lookups
CREATE INDEX idx_cte_hashes_old_not_null
ON change_timestamp_entity (old_hash, new_hash) 
WHERE old_hash IS NOT NULL;

CREATE INDEX idx_cte_hashes_old_null
ON change_timestamp_entity (old_hash, new_hash) 
WHERE old_hash IS NULL;

-- Index for comment searches
CREATE INDEX idx_cte_comment 
ON change_timestamp_entity (comment) 
WHERE comment ILIKE ANY(ARRAY['%rvv%', 'rv v', '%vandal%', '%revert%', '%restore%']);

-- =================================================================
-- 		REVERTED REVISIONS
-- =================================================================
DROP TABLE IF EXISTS reverted;

CREATE TEMP TABLE reverted AS
SELECT
    cte1.revision_id        AS revision_vandalized,
    cte2.revision_id        AS revision_reverted,
    cte1.entity_id,
    cte1.property_id,
    cte1.value_id,
    cte1.timestamp          AS time_vandalized,
    cte2.timestamp          AS time_reverted,
    cte2.comment            AS comment_reverted,
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
    );

-- =================================================================
-- 		TAG CHANGES
-- =================================================================
CREATE INDEX idx_reverted_lookup_vand ON reverted (revision_vandalized, property_id, value_id);
CREATE INDEX idx_reverted_lookup_rev ON reverted (revision_reverted, property_id, value_id);
CREATE INDEX idx_reverted_restore ON reverted (entity_id, property_id, value_id, time_vandalized, time_reverted) 
WHERE type_revert = 'restore';

-- Update reverted edits 
EXPLAIN ANALYZE
UPDATE :change c
SET reverted_edit = TRUE
WHERE EXISTS (
    SELECT 1
    FROM reverted rev
    WHERE rev.revision_vandalized = c.revision_id
      AND rev.property_id = c.property_id
      AND rev.value_id = c.value_id
);

-- Update reverting revisions 
UPDATE :change c
SET reversion = TRUE
WHERE EXISTS (
    SELECT 1
    FROM reverted rev
    WHERE c.revision_id = rev.revision_reverted
	  AND c.property_id = rev.property_id
	  AND c.value_id = rev.value_id
);

-- Update intermediate revisions for 'restore' type 
UPDATE :change c
SET 
    reverted_edit = TRUE
FROM change_timestamp_entity cte JOIN reverted rev
  ON rev.entity_id = cte.entity_id 
 AND rev.property_id = cte.property_id
 AND rev.value_id = cte.value_id
WHERE 
	type_revert = 'restore' AND
	c.revision_id = cte.revision_id
  AND c.property_id = cte.property_id
  AND c.value_id = cte.value_id
  AND cte.timestamp > rev.time_vandalized 
  AND cte.timestamp < rev.time_reverted
  AND cte.revision_id NOT IN (rev.revision_vandalized, rev.revision_reverted);
