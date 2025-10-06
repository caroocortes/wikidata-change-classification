
-- For equality comparisons (NULL == NULL returns NULL, not TRUE)
-- UPDATE :change
-- SET new_value = '{}'::jsonb
-- WHERE new_value IS NULL;

-- UPDATE :change
-- SET old_value = '{}'::jsonb
-- WHERE old_value IS NULL;

-- Normalize time dates that have leading zeros in the year part
-- this is a formatting change in WD:
UPDATE change_sample
SET new_value = to_jsonb(REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

UPDATE change_sample
SET old_value = to_jsonb(REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

-- Materialized view for queries that need to compare changes with timestamp

CREATE MATERIALIZED VIEW :change_timestamp_entity AS
SELECT r.timestamp, r.entity_id, c.*
FROM :revision r JOIN :change c ON r.revision_id = c.revision_id;

CREATE INDEX idx_cte_entity_property_value_target_ts
ON change_timestamp_entity (entity_id, property_id, value_id, change_target, timestamp); -- for join + timestamp comparison

-- old_value and new_value labels for entity values

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS old_value_label VARCHAR DEFAULT NULL;
ALTER TABLE :change
ADD COLUMN IF NOT EXISTS new_value_label VARCHAR DEFAULT NULL;

CREATE INDEX idx_change_old_value ON :change (old_value);
CREATE INDEX idx_change_new_value ON :change (new_value);

WITH entity_labels AS (
    SELECT DISTINCT entity_id, entity_label
    FROM revision
)
UPDATE :change c
SET old_value_label = ev.entity_label
FROM entity_labels ev
WHERE old_value->>0 = ev.entity_id;

UPDATE :change c
SET new_value_label = ev.entity_label
FROM entity_labels ev
WHERE new_value->>0 = ev.entity_id;
