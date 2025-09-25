-- Get vandalism + reverted edit:
-- Changes that were reverted (the hash of the newest revision is an old hash) in less than a day

-- This scripts creates a new column "is_reverted" in the change table set to TRUE if the change was 
-- reverted due to vandalism

-- NOTE: the script uses a "change_sample" table for testing
-- It should be with the table "change"

ALTER TABLE change_sample
ADD COLUMN IF NOT EXISTS change_classification VARCHAR DEFAULT '';

WITH revision_changes AS (
    SELECT
        c.*,
        r.entity_id,
        r.timestamp,
        r.comment
    FROM revision r
    JOIN change c ON r.revision_id = c.revision_id
),
reverted AS (
    SELECT
        rc1.entity_id,
        rc1.property_id,
        rc1.value_id,
        rc1.revision_id AS revision_vandalized,
        rc2.revision_id AS revision_reverted,
        rc1.timestamp AS time_vandalized,
        rc2.timestamp AS time_reverted,
        rc1.comment AS comment_vandalized,
        rc2.comment AS comment_reverted
    FROM revision_changes rc1 JOIN revision_changes rc2 
	ON rc1.entity_id = rc2.entity_id
     AND rc1.property_id = rc2.property_id
     AND rc1.value_id = rc2.value_id
	 AND rc1.change_target = rc2.change_target
     AND rc2.timestamp - rc1.timestamp > INTERVAL '1 day'
     AND rc1.old_hash = rc2.new_hash -- the change goes to a previous state (reverted edit)
     AND rc2.timestamp > rc1.timestamp 
)
-- Then handle 'undo' separately
UPDATE change_sample  
SET change_classification = 'revert_non_vandalism_undo'
FROM reverted rev
WHERE change_sample.revision_id IN (rev.revision_vandalized, rev.revision_reverted)
  AND rev.comment_reverted ILIKE '%undo%' or rev.comment_reverted = '';
  
UPDATE change_sample
SET change_classification = 'revert_non_vandalism_restore'
FROM reverted rev
JOIN revision r ON r.entity_id = rev.entity_id
WHERE change_sample.revision_id = r.revision_id
  AND rev.comment_reverted ILIKE '%restore%'
  AND r.timestamp BETWEEN rev.time_vandalized AND rev.time_reverted;

