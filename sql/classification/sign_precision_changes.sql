CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS precision_change BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET precision_change = TRUE
WHERE 
NOT (
formatting OR typo OR value_refinement OR value_unrefinement OR
reverted_edit OR reversion) AND
action = 'UPDATE' AND 
target = 'PROPERTY_VALUE' AND
(
    (  
        -- precision changes, the last part has a levenshtein distance that is small (<= 3)
        datatype IN ('quantity') AND
        -- they both have precision
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND 
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' AND
        levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) <= 3
    )
    OR 
    (
        datatype IN ('globecoordinate') AND 
        (
            (
				new_value != '{}' AND old_value != '{}' AND
                REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND 
                REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND
                levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g'), '.', 2)) <= 3
            )
            OR
            (
				new_value != '{}' AND old_value != '{}' AND
                REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND 
                REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND
                levenshtein(SPLIT_PART(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g'), '.', 2), SPLIT_PART(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g'), '.', 2)) <= 3
            )
        )
    )
)
; 

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS sign_change BOOLEAN DEFAULT FALSE;


UPDATE :change 
SET sign_change = TRUE
WHERE
NOT (
formatting OR typo OR value_refinement OR value_unrefinement OR precision_change OR
reverted_edit OR reversion) AND
action = 'UPDATE' AND 
target = 'PROPERTY_VALUE' AND
(
    (  
        datatype IN ('quantity') AND
        REGEXP_REPLACE(new_value->>0, '^[+-]', '', 'g') = REGEXP_REPLACE(old_value->>0, '^[+-]', '', 'g')
    )
    OR 
    (
        datatype IN ('globecoordinate') AND 
        (
            (
				new_value != '{}' AND old_value != '{}' AND
                REGEXP_REPLACE(new_value->>'latitude', '^[+-]', '', 'g') = REGEXP_REPLACE(old_value->>'latitude', '^[+-]', '', 'g')
            )
            OR
            (
				new_value != '{}' AND old_value != '{}' AND
                REGEXP_REPLACE(new_value->>'longitude', '^[+-]', '', 'g') = REGEXP_REPLACE(old_value->>'longitude', '^[+-]', '', 'g')
            )
        )
    )
)
; 