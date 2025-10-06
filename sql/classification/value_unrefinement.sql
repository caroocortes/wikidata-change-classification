ALTER TABLE :change
ADD COLUMN IF NOT EXISTS value_unrefinement BOOLEAN DEFAULT FALSE;

UPDATE :change
SET new_value = to_jsonb(REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

UPDATE :change
SET old_value = to_jsonb(REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

WITH value_unrefinement_metrics_string AS (
    SELECT 
    revision_id, property_id, value_id, change_target,
    LENGTH(old_value->>0) - LENGTH(new_value->>0) as length_decrease,
    
    -- Containment check
    CASE 
        WHEN (new_value->>0) LIKE '%' || (old_value->>0) || '%' THEN 1 
        ELSE 0 
    END as new_value_contained,
    
    -- Word count decrease
    array_length(string_to_array(old_value->>0, ' '), 1) - array_length(string_to_array(new_value->>0, ' '), 1) as word_decrease
    
    FROM :change
    WHERE 
        action = 'UPDATE' AND 
        target = 'PROPERTY_VALUE' AND
        vandalism = FALSE
)
UPDATE :change c
SET unvalue_refinement = TRUE
FROM value_unrefinement_metrics_string vrm
WHERE 
reverted_edit = FALSE AND reversion = FALSE AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND
c.revision_id = vrm.revision_id AND 
c.property_id = vrm.property_id AND
c.value_id = vrm.value_id AND
c.change_target = vrm.change_target
AND
(
    ( -- string types
        datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation') AND 
        new_value_contained > 0 AND -- new value is contained because this is unrefinement
        length_decrease > 0 AND 
        word_decrease > 0
    )
    OR
    ( -- time type
        datatype = 'time' AND
        ( 
            -- with the OR there can be both types of refinement
            --  NOTE: a case like 2025-00-01T00:00:00Z -> 2025-02-00T00:12:59Z is considered a refinement
            (
                -- date unrefinement
                (
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '[\+\-]|00', '', 'g')) < 
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '[\+\-]|00', '', 'g'))
                )
                AND 
                ( -- there was a time unrefinement, or the length stayed the same, but it didn't increase (refinement)
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), '00|:|Z', '', 'g')) <=
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), '00|:|Z', '', 'g')) 
                )
                AND 
                ( -- something stayed the same
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 1), '-', 1) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 1), '-', 1) OR -- year
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 1), '-', 2) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 1), '-', 2) OR -- month
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 1), '-', 3) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 1), '-', 3 ) -- day
                )
                
            )
            OR 
            (   -- time unrefinement
                (
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), '00|:|Z', '', 'g')) <
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), '00|:|Z', '', 'g')) 
                )
                AND
                ( -- there was a date unrefinement, or the length stayed the same, but it didn't increase (un-refinement)
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '[\+\-]|00', '', 'g')) <= 
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '[\+\-]|00', '', 'g'))
                )
                AND 
                ( -- something stayed the same
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 2), ':', 1) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 2), ':', 1) OR -- year
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 2), ':', 2) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 2), ':', 2) OR -- month
                    SPLIT_PART(SPLIT_PART(new_value->>0, 'T', 2), ':', 3) = SPLIT_PART(SPLIT_PART(old_value->>0, 'T', 2), ':', 3 ) -- day
                )
            )
        )
    )
    OR 
    -- numeric & globe coordinate
    -- Precision was removed: 9.5 -> 9
    (
        datatype IN ('quantity','globecoordinate') AND 
        new_value_contained > 0 AND
        length_decrease > 0 AND
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') !~ '[.]' AND -- no decimal in new value -> decimal was removed
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' 
    )
    OR
    -- Precision was rounded or cut: 9.563 -> 9.5
    (
        datatype IN ('quantity','globecoordinate') AND
        new_value_contained > 0 AND
        length_decrease > 0 AND
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
        -- replace ',' for '.' to make it homogeneous
        -- SPLIT_PART(value, '.', 2) returns the value after the '.'
        LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2)) < LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) 
    )
)