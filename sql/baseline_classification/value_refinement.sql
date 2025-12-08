ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS refinement_predicted BOOLEAN DEFAULT FALSE;

-- UPDATE <change>
-- SET new_value = to_jsonb(REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2'))
-- WHERE datatype = 'time';

-- UPDATE <change>
-- SET old_value = to_jsonb(REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2'))
-- WHERE datatype = 'time';

UPDATE <change> c
SET refinement_predicted = TRUE
WHERE 
refinement_predicted = FALSE AND
textual_change_predicted = FALSE AND re_formatting_predicted = FALSE AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE'
AND
(

    ( -- string types
        datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation') AND 
        -- old value contained
        regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') <@ regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') AND 
        -- word increase or length increase
        (
            -- it's an or for cases when it's just a word that turns more specific (e.g. Hindu -> Hinduism)
            LENGTH(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) - LENGTH(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) > 0
            or 
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(new_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) - 
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(old_value->>0)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) > 0
        )
    )
    OR (-- for entity values I consider the label of the entity 
        datatype IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form')
        AND 
        (regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(old_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+') <@ regexp_split_to_array(regexp_replace(regexp_replace(lower(trim(new_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), '\s+')) AND  -- old value is contained
        ( -- it's an or for cases when it's just a word that turns more specific (e.g. Hindu -> Hinduism)
            LENGTH(regexp_replace(regexp_replace(lower(trim(new_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) - LENGTH(regexp_replace(regexp_replace(lower(trim(old_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g')) > 0 -- length increase
            OR
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(new_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) - 
            array_length(string_to_array(regexp_replace(regexp_replace(lower(trim(old_value_label)), '[[:punct:]]', ' ', 'g'), '[-–—_]', ' ', 'g'), ' '), 1) > 0 -- word increase
        )  
    )
    OR 
    -- numeric
    -- Precision was introduced: 9 -> 9.5
    (
        ( (datatype IN ('quantity') AND change_target != 'unit') or (datatype IN ('globecoordinate') AND change_target = 'precision') ) AND
        new_value->>0 ILIKE old_value->>0 || '%' AND -- old_value is at the beginning
        LENGTH(new_value->>0) - LENGTH(old_value->>0) > 0 AND -- length increase
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND -- decimal in new value
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') !~ '[.]' -- no decimal in old value -> decimal was introduced
    )
    OR
    -- Precision was enhanced: 9.5 -> 9.563
    (
        ( (datatype IN ('quantity') AND change_target != 'unit') or (datatype IN ('globecoordinate') AND change_target = 'precision') ) AND
        new_value->>0  ILIKE old_value->>0 || '%' AND
        LENGTH(new_value->>0) - LENGTH(old_value->>0) > 0 AND
        REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') ~ '[.]' AND -- still has decimla
        REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') ~ '[.]' AND   -- already had decimal
        -- replace ',' for '.' to make it homogeneous
        -- SPLIT_PART(value, '.', 2) returns the value after the '.'
        (
            (
                LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2)) = LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)) 
                -- I remove this part because I already check that new_value starts with old_value
                -- AND
                -- SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 1) = SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 1)
                AND
                SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2) != SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)
            )
            OR
            (LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g'), '.', 2)) > LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g'), '.', 2)))
        )
    )
    OR 
    ( -- globe coordinate
        datatype IN ('globecoordinate') AND change_target = ''  AND(
            -- latitude change
            (
                new_value->>'latitude' ILIKE old_value->>'latitude' || '%' AND -- starts with the old_value
                LENGTH(new_value->>'latitude') - LENGTH(old_value->>'latitude') > 0 AND
                REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND
                REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') !~ '[.]' -- no decimal in old value -> decimal was introduced
            )
            OR
            -- longitude change
            (
                new_value->>'longitude' ILIKE old_value->>'longitude' || '%' AND -- starts with the old_value
                LENGTH(new_value->>'longitude') - LENGTH(old_value->>'longitude') > 0 AND
                REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND
                REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') !~ '[.]' -- no decimal in old value -> decimal was introduced
            )
        )
    )
    OR
    -- Precision was enhanced: 9.5 -> 9.563
    ( -- globe coordinate
        datatype IN ('globecoordinate') AND change_target = ''  AND (
            -- latitude change
            (
                new_value->>'latitude' ILIKE old_value->>'latitude' || '%' AND -- starts with the old_value
                REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND 
                REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') ~ '[.]' AND 
                -- replace ',' for '.' to make it homogeneous
                -- SPLIT_PART(value, '.', 2) returns the value after the '.'
                LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g'), '.', 2)) > LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g'), '.', 2)) 
            )
            OR
            -- longitude change
            (
                new_value->>'longitude' ILIKE old_value->>'longitude' || '%' AND -- starts with the old_value
                REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND
                REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') ~ '[.]' AND-- no decimal in old value -> decimal was introduced
                LENGTH(SPLIT_PART(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g'), '.', 2)) > LENGTH(SPLIT_PART(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g'), '.', 2)) 
            )
        )
    )
)
<additional_filters>
;

--- time refinement
UPDATE <change> c
SET refinement_predicted = TRUE
WHERE
textual_change_predicted = FALSE AND re_formatting_predicted = FALSE AND
datatype = 'time' AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND
change_target = '' AND
(
    (
        -- DATE refinement: more specific date
        (
            -- the new date has more non-zero components
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g'))
            >
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g'))
        )
        AND -- and some part is still contained
        REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g')::text ILIKE
    '%' || REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 1), '^[-+]', ''), '-00', '', 'g')::text || '%'
    )
    OR
    (
        -- TIME refinement: more precise time
        (
            -- the new time has more non-zero components
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g'))
            >
            LENGTH(REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g'))
        )
        AND -- and some part is still contained
        REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(new_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g')::text ILIKE
    '%' || REGEXP_REPLACE(REGEXP_REPLACE(SPLIT_PART(old_value->>0, 'T', 2), 'Z', ''), '(:|00)', '', 'g')::text || '%'
    )
)
<additional_filters>;
