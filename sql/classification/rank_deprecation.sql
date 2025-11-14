ALTER TABLE :change
ADD COLUMN IF NOT EXISTS rank_deprecation BOOLEAN DEFAULT FALSE;

UPDATE :change 
SET rank_deprecation = TRUE
WHERE
NOT (
formatting OR typo OR value_refinement OR value_unrefinement OR precision_change OR
reverted_edit OR reversion) AND
action = 'UPDATE' AND 
target = 'PROPERTY_VALUE' AND
old_value->>0 != 'deprecated' AND
new_value->>0 = 'deprecated';
