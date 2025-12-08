ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS rewording_predicted BOOLEAN DEFAULT FALSE;

UPDATE <change>
SET rewording_predicted = TRUE
WHERE
	datatype IN ('monolingualtext', 'string', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation') AND
	change_target = '' AND
	similarity(new_value->>0, old_value->>0) > 0.7
	and NOT (textual_change_predicted or re_formatting_predicted)
	<additional_filters>;