CREATE MATERIALIZED VIEW IF NOT EXISTS change_timestamp_entity AS
SELECT r.timestamp, r.entity_id, c.*, r.comment
FROM :revision r JOIN :change c ON r.revision_id = c.revision_id
WITH DATA;

CREATE INDEX idx_cte_entity_property_value_target_ts
ON change_timestamp_entity (entity_id, property_id, value_id, change_target, timestamp); -- for join + timestamp comparison

CREATE INDEX idx_temp_cte_old_hash
ON change_timestamp_entity (old_hash); -- for hash comparison

REFRESH MATERIALIZED VIEW change_timestamp_entity;

-- Add the column if not exists
ALTER TABLE :change
ADD COLUMN IF NOT EXISTS vandalism BOOLEAN DEFAULT FALSE;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS reverted_vandalism BOOLEAN DEFAULT FALSE;

-- Reverted revisions within 2 hours
DROP TABLE IF EXISTS reverted;
CREATE TEMP TABLE reverted AS (
    SELECT
        cte1.revision_id AS revision_vandalized,
        cte2.revision_id AS revision_reverted,
        cte1.entity_id,
        cte1.property_id,
        cte1.value_id,
        cte1.change_target,
        cte1.timestamp AS time_vandalized,
        cte2.timestamp AS time_reverted,
        cte2.comment AS comment_reverted
    FROM change_timestamp_entity cte1
    JOIN change_timestamp_entity cte2
      ON cte1.entity_id = cte2.entity_id
     AND cte1.property_id = cte2.property_id
     AND cte1.value_id = cte2.value_id
     AND cte1.change_target = cte2.change_target
     AND cte1.old_hash = cte2.new_hash  -- reverted to previous state
	 AND cte1.old_value = cte2.new_value -- the values match
	 AND cte1.new_value = cte2.old_value
     AND cte2.timestamp > cte1.timestamp -- cte2 is a revision in the future
     AND cte2.timestamp - cte1.timestamp <= INTERVAL '2 hours' -- that happened in less than 2 hours
);
-- Mark revision that has the vandalism
UPDATE :change c
SET vandalism = TRUE
FROM reverted rev
WHERE c.revision_id = rev.revision_vandalized;

-- Mark revision that reverts the vandalism
UPDATE :change c
SET reverted_vandalism = TRUE
FROM reverted rev
WHERE c.revision_id = rev.revision_reverted;