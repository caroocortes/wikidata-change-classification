ALTER TABLE :change
ADD COLUMN IF NOT EXISTS value_unrefinement BOOLEAN DEFAULT FALSE;

UPDATE :change
SET new_value = to_jsonb(REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

UPDATE :change
SET old_value = to_jsonb(REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2'))
WHERE datatype = 'time';

UPDATE :change c
SET value_unrefinement = TRUE
WHERE 
reverted_edit = FALSE AND reversion = FALSE AND
typo = FALSE AND formatting = FALSE AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE'
AND
(
    ( -- string types
        datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation') AND 
        regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') <@ regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') AND -- new value is contained because this is unrefinement
        (-- it's an or for cases when it's just a word that turns more specific (e.g. Hinduism -> Hindu)
            LENGTH(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) - LENGTH(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) > 0  
            or
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' ') , 1) - array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) > 0
        )
    )
    OR
    ( -- entity types
        datatype IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form') AND 
        (regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(new_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') <@ regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(old_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+')) AND -- new value is contained because this is unrefinement
        (-- it's an or for cases when it's just a word that turns more specific (e.g. Hinduism -> Hindu)
            LENGTH(old_value_label) - LENGTH(new_value_label) > 0 
            OR 
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(old_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) -
             array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(new_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) > 0 -- word decrease
        )
    )
    OR 
    -- numeric & globe coordinate
    -- Precision was removed: 9.5 -> 9
    (
        ( (datatype IN ('quantity') AND change_target != 'unit') or (datatype IN ('globecoordinate') AND change_target = 'precision') ) AND
        old_value->>0 LIKE new_value->>0 || '%' AND -- starts with the new_value
        LENGTH(old_value->>0) - LENGTH(new_value->>0) > 0 AND -- length decrease
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') !~ '[.]' AND -- no decimal in new value -> decimal was removed
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' 
    )
    OR
    -- Precision was cut: 9.563 -> 9.5
    (
        ( (datatype IN ('quantity') AND change_target != 'unit') or (datatype IN ('globecoordinate') AND change_target = 'precision') ) AND
        old_value->>0 LIKE new_value->>0 || '%' AND -- starts with the new_value
        LENGTH(old_value->>0) - LENGTH(new_value->>0) > 0 AND -- length decrease
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
        -- replace ',' for '.' to make it homogeneous
        -- SPLIT_PART(value, '.', 2) returns the value after the '.'
        LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2)) < LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) 
    )
    OR
    (
        datatype IN ('globecoordinate') AND change_target = ''  AND
        (
            (
                old_value->>'latitude' LIKE new_value->>'latitude' || '%' AND -- starts with the new_value
                LENGTH(old_value->>'latitude') - LENGTH(new_value->>'latitude') > 0 AND -- length decrease
                REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') !~ '[.]' AND -- no decimal in new value -> decimal was removed
                REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') ~ '[.]' 
            )
            OR
            (
                old_value->>'longitude' LIKE new_value->>'longitude' || '%' AND -- starts with the new_value
                LENGTH(old_value->>'longitude') - LENGTH(new_value->>'longitude') > 0 AND -- length decrease
                REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') !~ '[.]' AND -- no decimal in new value -> decimal was removed
                REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') ~ '[.]' 
            )
        )
    )
    OR
    -- Precision was rounded or cut: 9.563 -> 9.5
    (
        datatype IN ('globecoordinate') AND change_target = ''  AND
        (
            (
                old_value->>'latitude' LIKE new_value->>'latitude' || '%' AND -- starts with the new_value
                LENGTH(old_value->>'latitude') - LENGTH(new_value->>'latitude') > 0 AND -- length decrease
                REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
                REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
                -- replace ',' for '.' to make it homogeneous
                -- SPLIT_PART(value, '.', 2) returns the value after the '.'
                LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g'), '.', 2)) < LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g'), '.', 2)) 
            )
            OR
            (
                old_value->>'longitude' LIKE new_value->>'longitude' || '%' AND -- starts with the new_value
                LENGTH(old_value->>'longitude') - LENGTH(new_value->>'longitude') > 0 AND -- length decrease
                REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
                REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
                -- replace ',' for '.' to make it homogeneous
                -- SPLIT_PART(value, '.', 2) returns the value after the '.'
                LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g'), '.', 2)) < LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g'), '.', 2)) 
            )
        )
    )
);


--- time unrefinement
UPDATE :change c
SET value_unrefinement = TRUE
WHERE
typo = FALSE AND formatting = FALSE AND
datatype = 'time' AND
reverted_edit = FALSE AND reversion = FALSE AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND 
change_target = '' AND
(
    (
        -- DATE unrefinement: less specific date
        (
            -- the new date has more zero components
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g'))
            <
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g'))
        )
        AND -- and new value is contained in old value, so it's "smaller"
        REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g')::text ILIKE
    '%' || REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g')::text || '%'
    )
    OR
    (
        -- TIME unrefinement: less precise time
        (
            -- the new time has more zero components
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g'))
            <
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g'))
        )
        AND -- and new value is contained in old value, so it's "smaller"
        REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g')::text ILIKE
    '%' || REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g')::text || '%'
    )
);