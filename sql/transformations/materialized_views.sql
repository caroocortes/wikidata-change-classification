CREATE MATERIALIZED VIEW :change_timestamp_entity AS
SELECT r.timestamp, r.entity_id, c.*
FROM :revision r JOIN :change c ON r.revision_id = c.revision_id