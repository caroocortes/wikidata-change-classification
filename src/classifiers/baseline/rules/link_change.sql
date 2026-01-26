ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS link_change_predicted BOOLEAN DEFAULT FALSE;

UPDATE <change> c
SET link_change_predicted = TRUE
WHERE 
	link_change_predicted = FALSE AND
	c.datatype IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema') AND
	c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
    -- Q-id is differnt but the labels are the same (can differ on capitalization)
	c.old_value->>0 <> c.new_value->>0 AND trim(lower(c.old_value_label)) = trim(lower(c.new_value_label))
	<additional_filters>
	;