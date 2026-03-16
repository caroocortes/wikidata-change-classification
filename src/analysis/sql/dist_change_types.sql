CREATE INDEX IF NOT EXISTS action_idx_qualifier_change ON qualifier_change (action);
CREATE INDEX IF NOT EXISTS action_idx_reference_change ON reference_change (action);
CREATE INDEX IF NOT EXISTS label_idx_qualifier_change ON qualifier_change (label);

create index IF NOT EXISTS label_idx_value_change on value_change (label);
create index IF NOT EXISTS label_idx_features_text on features_text (label);
create index IF NOT EXISTS label_idx_features_quantity on features_quantity (label);
create index IF NOT EXISTS label_idx_features_time on features_time (label);
create index IF NOT EXISTS label_idx_features_globecoordinate on features_globecoordinate (label);


CREATE TABLE IF NOT EXISTS change_type_distribution (
    source TEXT,        -- 'entity', 'text', 'time', 'quantity', 'globecoordinate', 'value_change', 'qualifier', 'reference'
    label TEXT,         -- change type label
    count_reverted BIGINT,
    count_non_reverted BIGINT,
    total BIGINT GENERATED ALWAYS AS (count_reverted + count_non_reverted) STORED,
    reversion_rate FLOAT GENERATED ALWAYS AS (count_reverted::float / NULLIF(count_reverted + count_non_reverted, 0)) STORED
);

-- entity
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_entity WHERE label IS NOT NULL AND label != '' AND old_value_label != '' AND new_value_label != ''
)
SELECT 'entity', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;

--- text
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_text WHERE label IS NOT NULL AND label != ''
)
SELECT 'text', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;

--- quantity
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_quantity WHERE label IS NOT NULL AND label != ''
)
SELECT 'quantity', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;

--- globe latitude
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label_latitude, ', ')) AS individual_label
    FROM features_globecoordinate WHERE label_latitude IS NOT NULL AND label_latitude != ''
)
SELECT 'globecoordinate_latitude', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;

-- globe longitude
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label_longitude, ', ')) AS individual_label
    FROM features_globecoordinate WHERE label_longitude IS NOT NULL AND label_longitude != ''
)
SELECT 'globecoordinate_longitude', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;


--- time
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
WITH label_split AS (
    SELECT is_reverted, unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_time WHERE label IS NOT NULL AND label != ''
)
SELECT 'time', individual_label,
    COUNT(*) FILTER (WHERE is_reverted = 1),
    COUNT(*) FILTER (WHERE is_reverted = 0)
FROM label_split GROUP BY individual_label;

-- Insert value_change derived labels
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'value_change', 'statement_insertion', COUNT(*) FILTER(WHERE is_reverted = 1), COUNT(*) FILTER(WHERE is_reverted = 0)
FROM value_change
WHERE (label='statement_insertion' or label='value_insertion') AND change_target='';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'value_change', 'statement_deletion', COUNT(*) FILTER(WHERE is_reverted = 1), COUNT(*) FILTER(WHERE is_reverted = 0)
FROM value_change
WHERE (label='statement_deletion' or label='value_deletion') AND change_target='';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'value_change', 'property_value_update', COUNT(*) FILTER(WHERE is_reverted = 1), COUNT(*) FILTER(WHERE is_reverted = 0)
FROM value_change
WHERE (label='value_update') AND change_target='';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'value_change', 'soft_insertion', COUNT(*) FILTER(WHERE is_reverted = 1), COUNT(*) FILTER(WHERE is_reverted = 0)
FROM value_change
WHERE (label='soft_insertion') AND change_target='rank';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'value_change', 'soft_deletion', COUNT(*) FILTER(WHERE is_reverted = 1), COUNT(*) FILTER(WHERE is_reverted = 0)
FROM value_change
WHERE (label='soft_deletion') AND change_target='rank';

-- Insert qualifier changes
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'qualifier', 'qualifier_insertion', 0, COUNT(*) 
FROM qualifier_change
WHERE action='CREATE';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'qualifier', 'qualifier_deletion', 0, COUNT(*) 
FROM qualifier_change
WHERE action='DELETE';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'qualifier', 'soft_deletion', 0, COUNT(*) 
FROM qualifier_change
WHERE label='soft_deletion';

-- Insert reference changes (no is_reverted on reference_change)
INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'reference', 'reference_insertion', 0, COUNT(*) 
FROM reference_change WHERE action='CREATE';

INSERT INTO change_type_distribution (source, label, count_reverted, count_non_reverted)
SELECT 'reference', 'reference_deletion', 0, COUNT(*) 
FROM reference_change WHERE action='DELETE';
