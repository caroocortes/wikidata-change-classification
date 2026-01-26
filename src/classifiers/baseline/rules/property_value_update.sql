ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS property_value_update_predicted BOOLEAN DEFAULT FALSE;

UPDATE <change> c
SET property_value_update_predicted = TRUE
WHERE 
c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND change_target = '' AND -- no rank
	c.old_value->>0 <> c.new_value->>0 AND 
    (
        (
        -- for text types just compare the values
            datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values') AND
            similarity(trim(lower(c.old_value->>0)), trim(lower(c.new_value->>0))) <= 0.1
        )
        OR 
        (
            -- for entities the Q-ids could be different but the label similar, so I also compare that the label is completely different
            datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema') AND
            similarity(trim(lower(c.old_value_label)), trim(lower(c.new_value_label))) <= 0.1
        )
        OR
        (
            ( (datatype IN ('quantity') AND change_target != 'unit') or (datatype IN ('globecoordinate') AND change_target = 'precision') ) AND
            (
                -- the non-fractional part is completely different
                FLOOR(CAST(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') AS numeric)) <> FLOOR(CAST(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') AS numeric)) OR
                -- fractional part differs for a lot
                abs(ROUND(CAST(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(old_value->>0, '[,]', '.', 'g') AS numeric)), 6) - ROUND(CAST(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(new_value->>0, '[,]', '.', 'g') AS numeric)), 6)) >= 0.5
            )
        )
        OR 
        (
            'globecoordinate' = datatype and (
                (
                    FLOOR(CAST(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') AS numeric)) <> FLOOR(CAST(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') AS numeric)) OR
                    -- fractional part differs for a lot
                    abs(ROUND(CAST(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(old_value->>'latitude', '[,]', '.', 'g') AS numeric)), 6) - ROUND(CAST(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(new_value->>'latitude', '[,]', '.', 'g') AS numeric)), 6)) >= 0.5
                )
                or
                (
                    FLOOR(CAST(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') AS numeric)) <> FLOOR(CAST(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') AS numeric)) OR
                    -- fractional part differs for a lot
                    abs(ROUND(CAST(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(old_value->>'longitude', '[,]', '.', 'g') AS numeric)), 6) - ROUND(CAST(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') AS numeric) - FLOOR(CAST(REGEXP_REPLACE(new_value->>'longitude', '[,]', '.', 'g') AS numeric)), 6)) >= 0.5
                )
            )
        )
        OR
        (
            datatype = 'time' AND (
                CAST(substring(c.old_value->>0 from '^([+-]?\d{1,6})-') AS integer) <> CAST(substring(c.new_value->>0 from '^([+-]?\d{1,6})-') AS integer)  OR
                CAST(substring(c.old_value->>0 from '^\+?\d{1,6}-(\d{2})-') AS integer) <> CAST(substring(c.new_value->>0 from '^\+?\d{1,6}-(\d{2})-') AS integer) OR
                CAST(substring(c.old_value->>0 from '^\+?\d{1,6}-\d{2}-(\d{2})') AS integer) <> CAST(substring(c.new_value->>0 from '^\+?\d{1,6}-\d{2}-(\d{2})') AS integer)  OR
                CAST(substring(c.old_value->>0 from 'T(\d{2}):') AS integer) <> CAST(substring(c.old_value->>0 from 'T(\d{2}):') AS integer) OR
                CAST(substring(c.old_value->>0 from 'T\d{2}:(\d{2}):') AS integer) <> CAST(substring(c.old_value->>0 from 'T\d{2}:(\d{2}):') AS integer) OR
                CAST(substring(c.old_value->>0 from ':(\d{2})Z$') AS integer) <> CAST(substring(c.old_value->>0 from ':(\d{2})Z$') AS integer)
            )
        )
    )
    <additional_filters>
    ; 