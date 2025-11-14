ALTER TABLE :change
ADD COLUMN IF NOT EXISTS sign_change BOOLEAN DEFAULT FALSE;

UPDATE :change 
SET sign_change = TRUE
WHERE
action = 'UPDATE' AND 
target = 'PROPERTY_VALUE' AND
(
    (  
        datatype IN ('quantity') AND
        SUBSTRING(old_value->>0, 1, 1) IN ('+', '-') AND
        SUBSTRING(new_value->>0, 1, 1) IN ('+', '-') AND
        SUBSTRING(old_value->>0, 1, 1) != SUBSTRING(new_value->>0, 1, 1)
    )
    OR 
    (
        datatype IN ('globecoordinate') AND 
        (
            (
                new_value != '{}' AND old_value != '{}' AND
                SUBSTRING(old_value->>'latitude', 1, 1) IN ('+', '-') AND
                SUBSTRING(new_value->>'latitude', 1, 1) IN ('+', '-') AND
                SUBSTRING(old_value->>'latitude', 1, 1) != SUBSTRING(new_value->>'latitude', 1, 1)
            )
            OR
            (
                new_value != '{}' AND old_value != '{}' AND
                SUBSTRING(old_value->>'longitude', 1, 1) IN ('+', '-') AND
                SUBSTRING(new_value->>'longitude', 1, 1) IN ('+', '-') AND
                SUBSTRING(old_value->>'longitude', 1, 1) != SUBSTRING(new_value->>'longitude', 1, 1)
            )
        )
    )
)
;