CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE INDEX IF NOT EXISTS idx_change_metadata_lookup 
  ON :change_metadata (revision_id, property_id, value_id, change_target, change_metadata); --  for WHERE filter

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS precision_change BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET precision_change = TRUE
WHERE 
NOT (
formatting OR typo OR value_refinement OR value_unrefinement OR
reverted_edit OR reversion) AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND
(
    (  
        -- precision changes, the last part has a levenshtein distance that is small (<= 3)
        c.datatype IN ('quantity') AND
        -- they both have precision
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]'
        levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) <= 3
    )
    OR 
    (
        c.datatype IN ('globecoordinate') AND 
        (
            (
                REGEXP_REPLACE(new_value::latitude, '[,]', '.', 'g') ~ '[.]' AND REGEXP_REPLACE(old_value::latitude, '[,]', '.', 'g') ~ '[.]'
                levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value::latitude, '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value::latitude, '[,]', '.', 'g'), '.', 2)) <= 3
            )
            OR
            (
                REGEXP_REPLACE(new_value::longitude, '[,]', '.', 'g') ~ '[.]' AND REGEXP_REPLACE(old_value::longitude, '[,]', '.', 'g') ~ '[.]'
                levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value::longitude, '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value::longitude, '[,]', '.', 'g'), '.', 2)) <= 3
            )
        )
    )
)
; 

UPDATE :change 
SET sign_change = TRUE
WHERE
NOT (
formatting OR typo OR value_refinement OR value_unrefinement OR
reverted_edit OR reversion) AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND
(
    (  
        c.datatype IN ('quantity') AND
        REGEXP_REPLACE(new_value->>0, '^[+-]', '', 'g') = REGEXP_REPLACE(old_value->>0, '^[+-]', '', 'g')
    )
    OR 
    (
        c.datatype IN ('globecoordinate') AND 
        (
            (
                REGEXP_REPLACE(new_value::latitude, '^[+-]', '', 'g') = REGEXP_REPLACE(old_value::latitude, '^[+-]', '', 'g')
            )
            OR
            (
                REGEXP_REPLACE(new_value::longitude, '^[+-]', '', 'g') = REGEXP_REPLACE(old_value::longitude, '^[+-]', '', 'g')
            )
        )
    )
)
; 