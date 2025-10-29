ALTER TABLE :change
ADD COLUMN IF NOT EXISTS link_fix BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET link_fix = TRUE
WHERE 
	c.datatype IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema', 'globecoordinate') AND
	reverted_edit = FALSE AND reversion = FALSE AND
	c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
    -- Q-id is differnt but the labels are the same (can differ on capitalization)
	c.old_value->>0 <> c.new_value->>0 AND trim(lower(c.old_value_label)) = trim(lower(c.new_value_label))
	;