CREATE TABLE IF NOT EXISTS change_type_distribution (
    datatype TEXT,        -- 'entity', 'text', 'time', 'quantity', 'globecoordinate', 'value_change', 'qualifier', 'reference'
    user_type TEXT,
    label TEXT,         -- change type label
    count_reverted BIGINT,
    count_non_reverted BIGINT,
    total BIGINT GENERATED ALWAYS AS (count_reverted + count_non_reverted) STORED,
    reversion_rate FLOAT GENERATED ALWAYS AS (count_reverted::float / NULLIF(count_reverted + count_non_reverted, 0)) STORED
);

----- QUANTITY ----
INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_quantity f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label IS NOT NULL AND label != ''
)
SELECT 
    'quantity' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;

----- TIME ----
INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_time f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label IS NOT NULL AND label != ''
)
SELECT 
    'time' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;

----- GLOBE ----
INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label_latitude, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_globecoordinate f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label_latitude IS NOT NULL AND label_latitude != ''
)
SELECT 
    'globecoordinate_latitude' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;


INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label_longitude, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_globecoordinate f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label_longitude IS NOT NULL AND label_longitude != ''
)
SELECT 
    'globecoordinate_longitude' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;

----- TEXT ----
INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_text f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label IS NOT NULL AND label != ''
)
SELECT 
    'text' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;

----- ENTITY ----
INSERT INTO change_type_distribution_per_user_type(datatype, user_type, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT 
        r.user_type,
        unnest(string_to_array(label, ', ')) AS individual_label,
        is_reverted, reversion
    FROM features_entity f 
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE label IS NOT NULL AND label != '' and old_value_label != '' AND new_value_label != ''
)
SELECT 
    'entity' as datatype,
    user_type,
    individual_label AS label,
    COUNT(*) FILTER (WHERE is_reverted = 1) AS count_reverted,
    COUNT(*) FILTER (WHERE is_reverted = 0 AND reversion = 0) AS count_non_reverted
FROM label_split
GROUP BY user_type, individual_label;