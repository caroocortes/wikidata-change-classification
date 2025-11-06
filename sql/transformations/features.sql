ALTER TABLE  revision_sample_30
ADD COLUMN IF NOT EXISTS user_type VARCHAR DEFAULT NULL;

-- user type column: bot / anonymous / human
UPDATE revision_sample_30
SET user_type = 
    CASE
        WHEN username ILIKE '%bot%' THEN 'bot'
        WHEN user_id = '' and username = '' THEN 'anonymous'
        ELSE 'human'
    END;


-- Index on revision_id for faster joins
CREATE INDEX IF NOT EXISTS idx_value_change_sample_30_revision_id 
    ON value_change_sample_30(revision_id);

CREATE INDEX IF NOT EXISTS idx_value_change_metadata_sample_30_revision_id 
    ON value_change_metadata_sample_30(revision_id, property_id, value_id, change_target);


COPY (
    SELECT 
        c.revision_id,
        r.entity_id,
        r.entity_label,
        c.property_id,
        c.value_id,
        c.property_label,
        c.old_value,
        c.old_value_label,
        c.new_value,
        c.new_value_label,
        c.datatype,
        c.change_target,
        c.action,
        c.target,
        c.old_hash,
        c.new_hash,
        r.timestamp,
        r.user_type,
        r.user_id,
        r.comment,
        -- statistics from change
        CASE 
            WHEN property_label IS NULL THEN TRUE
            ELSE FALSE
        END AS deleted_property
    FROM 
    revision_sample_30 r JOIN value_change_sample_30 c ON c.revision_id = r.revision_id
    LEFT JOIN value_change_metadata_sample_30 cm ON  ON c.revision_id = cm.revision_id AND c.property_id = cm.property_id AND c.value_id = cm.value_id AND c.change_target = cm.change_target
) TO '/tmp/value_changes_for_clustering.csv' 
WITH (FORMAT CSV, HEADER true);


