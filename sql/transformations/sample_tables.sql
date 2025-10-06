CREATE TABLE revision_sample_30 AS
WITH ordered_files AS (
    SELECT DISTINCT file_path, entity_id
    FROM revision_sample
    ORDER BY entity_id ASC
),
limit_files AS (
    SELECT file_path
    FROM ordered_files
    LIMIT 30
)
SELECT * FROM revision_sample
WHERE file_path IN (SELECT file_path FROM limit_files);

ALTER TABLE revision_sample_30
ADD PRIMARY KEY (revision_id);

CREATE TABLE change_sample_30 AS
SELECT * FROM change_sample
WHERE revision_id IN (SELECT revision_id FROM revision_sample_30);

ALTER TABLE change_sample_30
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target),
ADD FOREIGN KEY (revision_id) REFERENCES revision_sample_30(revision_id);

CREATE TABLE change_metadata_sample_30 AS
SELECT cm.*
FROM change_metadata_sample cm
JOIN change_sample_30 c
  ON cm.revision_id = c.revision_id
 AND cm.property_id = c.property_id
 AND cm.value_id = c.value_id
 AND cm.change_target = c.change_target;

ALTER TABLE change_metadata_sample_30
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target, change_metadata),
ADD FOREIGN KEY (revision_id, property_id, value_id, change_target)
    REFERENCES change_sample_30(revision_id, property_id, value_id, change_target);