-- Sets the column "change_classification" to "likely_typo" for changes
-- in strings with a change_magnitude between 1 and 2 that remained stable for more than 30 days, for strings with length > 2

CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE INDEX IF NOT EXISTS idx_change_metadata_lookup 
  ON :change_metadata (revision_id, property_id, value_id, change_target, change_metadata); --  for WHERE filter

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS typo BOOLEAN DEFAULT FALSE;

WITH change_with_stability AS (
    SELECT
        c.revision_id, -- for join to update
        c.property_id, -- for join to update
        c.value_id, -- for join to update
        c.change_target, -- for join to update
        cm.value AS change_magnitude,

        -- stability after: time until next change
        EXTRACT(EPOCH FROM (LEAD(r.timestamp) OVER (
            PARTITION BY r.entity_id, c.property_id
            ORDER BY r.timestamp
        ) - r.timestamp)) / 86400.0 AS days_stable_after
    FROM 
        (:revision r -- for the timestamp
        JOIN 
        :change c 
        ON r.revision_id = c.revision_id) -- uses FK of revision_id
        LEFT JOIN -- uses FK of revision_id, property_id, value_id, change_target
        :change_metadata cm ON c.revision_id = cm.revision_id AND c.property_id = cm.property_id AND c.value_id = cm.value_id AND c.change_target = cm.change_target
	WHERE 
		c.is_vandalism = FALSE AND
        c.action = 'UPDATE' AND 
		c.target = 'PROPERTY_VALUE' AND
        cm.value > 0 AND
         -- if it's only numbers, don't consider it as a typo (e.g. the vesion of something 3.2.1 changes to 3.2.5)
        NOT (old_value->>0 ~ '[0-9[:punct:]]' AND new_value->>0 ~ '[0-9[:punct:]]') AND
        cm.change_metadata = 'CHANGE_MAGNITUDE' AND
        c.datatype IN ('monolingualtext', 'string', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation')
)
UPDATE :change c
SET typo = TRUE
FROM change_with_stability cws
WHERE 
c.is_vandalism = FALSE AND
c.action = 'UPDATE' AND 
c.target = 'PROPERTY_VALUE' AND
c.revision_id = cws.revision_id AND
c.property_id = cws.property_id AND
c.value_id = cws.value_id AND
c.change_target = cws.change_target AND
change_magnitude BETWEEN 1 AND 2 AND 
days_stable_after > 30 AND 
LENGTH(old_value->>0) > 2 AND-- if the length is 2 and the change magnitude is also 2, then it means that the whole value changed
formatting = FALSE; -- so it doesn't overlap with formatting changes

-- Handles typos that are due to accents introduced/removed
-- mark typo correction if the accent was introduced
ALTER TABLE :change
ADD COLUMN IF NOT EXISTS typo_correction BOOLEAN DEFAULT FALSE;
UPDATE :change
SET typo_correction = TRUE
WHERE
typo = TRUE AND
new_value->>0 != old_value->>0 AND 
unaccent(old_value->>0) = unaccent(new_value->>0) AND
levenshtein(unaccent(old_value->>0), old_value->>0) <= levenshtein(unaccent(new_value->>0), new_value->>0);

-- mark typo introduction if the accent was removed
ALTER TABLE :change
ADD COLUMN IF NOT EXISTS typo_introduction BOOLEAN DEFAULT FALSE;
UPDATE :change
SET typo_introduction = TRUE
WHERE
typo = TRUE AND
new_value->>0 != old_value->>0 AND 
unaccent(old_value->>0) = unaccent(new_value->>0) AND
-- there are more accents in the old_value
-- levenshtein(unaccent(old_value), old_value) -> returns the number of accents in old_value
levenshtein(unaccent(old_value->>0), old_value->>0) >= levenshtein(unaccent(new_value->>0), new_value->>0);