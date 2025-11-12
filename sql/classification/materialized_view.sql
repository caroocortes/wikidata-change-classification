CREATE MATERIALIZED VIEW IF NOT EXISTS change_timestamp_entity AS
SELECT r.timestamp, r.entity_id, c.*, r.comment
FROM :revision r JOIN :change c ON r.revision_id = c.revision_id
WITH DATA;

CREATE INDEX IF NOT EXISTS idx_cte_join_conditions 
ON change_timestamp_entity (entity_id, property_id, value_id, change_target, timestamp);
