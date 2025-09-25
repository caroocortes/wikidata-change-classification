ALTER TABLE :change
ADD COLUMN IF NOT EXISTS value_refinement BOOLEAN DEFAULT FALSE;

WITH value_refinement_metrics_string AS (
    SELECT 
    revision_id, property_id, value_id, change_target,
    LENGTH(new_value->>0) - LENGTH(old_value->>0) as length_increase,
    
    -- Containment check
    CASE 
        WHEN (new_value->>0) LIKE '%' || (old_value->>0) || '%' THEN 1 
        ELSE 0 
    END as old_value_contained,
    
    -- Word count increase
    array_length(string_to_array(new_value->>0, ' '), 1) - 
    array_length(string_to_array(old_value->>0, ' '), 1) as word_increase
    
    FROM :change
    WHERE 
        action = 'UPDATE' AND 
        target = 'PROPERTY_VALUE' AND
        is_vandalism = FALSE
)
UPDATE :change c
SET value_refinement = TRUE
FROM value_refinement_metrics_string vrm
WHERE 
c.is_vandalism = FALSE AND
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
        old_value_contained > 0 AND 
        length_increase > 0 AND 
        word_increase > 0
    )
    OR
    ( -- time type
        datatype = 'time' AND
        ( 
            -- with the OR there can be both types of refinement
            --  NOTE: a case like 2025-00-01T00:00:00Z -> 2025-02-00T00:12:59Z is considered a refinement
            (
                -- date refinement
                (
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '[\+\-]|00', '', 'g')) > 
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '[\+\-]|00', '', 'g'))
                )
                AND 
                ( -- there was a time refinement, or the length stayed the same, but it didn't decrease (un-refinement)
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), '00|:|Z', '', 'g')) >=
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), '00|:|Z', '', 'g')) 
                )
            )
            OR 
            (   -- time refinement
                (
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), '00|:|Z', '', 'g')) >
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), '00|:|Z', '', 'g')) 
                )
                AND
                ( -- there was a date refinement, or the length stayed the same, but it didn't decrease (un-refinement)
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '[\+\-]|00', '', 'g')) >= 
                    LENGTH(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '[\+\-]|00', '', 'g'))
                )
            )
        )
    )
    OR 
    -- numeric & globe coordinate
    -- Precision was introduced: 9 -> 9.5
    (
        datatype IN ('quantity','globecoordinate') AND 
        old_value_contained > 0 AND
        length_increase > 0 AND
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') !~ '[.]' -- no decimal in old value -> decimal was introduced
    )
    OR
    -- Precision was enhanced: 9.5 -> 9.563
    (
        datatype IN ('quantity','globecoordinate') AND
        old_value_contained > 0 AND
        length_increase > 0 AND
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
        -- replace ',' for '.' to make it homogeneous
        -- SPLIT_PART(value, '.', 2) returns the value after the '.'
        LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2)) > LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) 
    )
)
