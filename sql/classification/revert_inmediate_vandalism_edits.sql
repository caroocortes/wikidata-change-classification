-- Get vandalism + reverted edit:
-- Changes that were reverted (the hash of the newest revision is an old hash) in less than 2 hours

-- This scripts creates a new column "is_vandalism" in the change table set to TRUE if the change was 
-- reverted due to vandalism

-- This version only works for inmediate reverts
ALTER TABLE change
ADD COLUMN IF NOT EXISTS is_vandalism BOOLEAN DEFAULT FALSE;

WITH revision_changes AS (
    SELECT
        c.*,
        r.entity_id,
        r.timestamp,
        r.comment,
        r.username,
        LEAD(c.new_hash) OVER (
            PARTITION BY r.entity_id, c.property_id, c.value_id, c.change_target
            ORDER BY r.timestamp
        ) AS next_new_hash,
        LEAD(r.comment) OVER (
            PARTITION BY r.entity_id, c.property_id, c.value_id, c.change_target
            ORDER BY r.timestamp
        ) AS next_comment,
        LEAD(r.revision_id) OVER (
            PARTITION BY r.entity_id, c.property_id, c.value_id, c.change_target
            ORDER BY r.timestamp
        ) AS next_revision_id,
        LEAD(r.timestamp) OVER (
            PARTITION BY r.entity_id, c.property_id, c.value_id, c.change_target
            ORDER BY r.timestamp
        ) AS next_timestamp
    FROM revision r
    JOIN change c ON r.revision_id = c.revision_id
)
UPDATE change c
SET is_vandalism = TRUE
FROM revision_changes rc
WHERE c.revision_id IN (
        rc.revision_id,        -- the original revision (vandalism)
        rc.next_revision_id    -- the reverting revision
    )
  AND rc.next_new_hash = rc.old_hash
  AND rc.next_timestamp - rc.timestamp <= INTERVAL '2 hours';