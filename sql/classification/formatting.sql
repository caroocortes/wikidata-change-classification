CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS formatting BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET formatting = TRUE
WHERE 
	c.datatype NOT IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema', 'globecoordinate') AND
	reverted_edit = FALSE AND reversion = FALSE AND 
	c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
	c.old_value->>0 <> c.new_value->>0 AND 
	(

		(-- dates like 00002025-10-02T... to 2025-10-02
			datatype = 'time' AND (
				old_value->>0 = REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2') 
			   or 
			   new_value->>0 = REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2') -- \1 captures +/- and \2 captures leading zeros
			)
		) or
		( -- quantity
			datatype = 'quantity' AND (
				-- extra 0's at the beggining
				old_value->>0 = REGEXP_REPLACE(new_value->>0, '^([+-])0*(\d+)', '\1\2') 
				or 
				new_value->>0 = REGEXP_REPLACE(old_value->>0, '^([+-])0*(\d+)', '\1\2')
				or 
				-- extra 0's at the end
				old_value->>0 = REGEXP_REPLACE(new_value->>0, '(\d+)0*$', '\1') 
				or 
				new_value->>0 = REGEXP_REPLACE(old_value->>0, '(\d+)0*$', '\1')
			)
		) or
		-- string types
		(
			datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation') AND 
			(
				-- capitalization + trim + unaccent
				lower(unaccent(trim(c.old_value::text)))
				= 
				lower(unaccent(trim(c.new_value::text))) OR
				
				-- punctuation
				regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]', ' ', 'g') = 
				regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]', ' ', 'g') or 
				
				--  space normalization
				
				regexp_replace(lower(unaccent(c.old_value->>0)), '\s+', ' ', 'g') = 
				regexp_replace(lower(unaccent(c.new_value->>0)), '\s+', ' ', 'g') or
				
				-- trimming
				trim(c.old_value->>0) = 
				trim(c.new_value->>0) or
				
				-- quotes/brackets
				
				regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '["“”‘’\[\]\(\)\{\}]', ' ', 'g') =   
				regexp_replace(TRIM((LOWER(unaccent(c.new_value->>0)))), '["“”‘’\[\]\(\)\{\}]', ' ', 'g') or
				
				
				-- distance after removing hyphens/dashes
				
				regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '[-–—_]', ' ', 'g') = 
				regexp_replace(TRIM(LOWER(unaccent(c.new_value->>0))), '[-–—_]', ' ', 'g') or
				
				-- Article addition/removal at the start 
				
				regexp_replace(TRIM(LOWER(unaccent(old_value->>0))), '^(the |a |an )', '') = 
				regexp_replace(TRIM(LOWER(unaccent(new_value->>0))), '^(the |a |an )', '') or
				
				-- plural changes (s and es at the end) - because we focused on english labels... (what happens with multilingual text?)
				TRIM(LOWER(unaccent(old_value->>0))) = 
				regexp_replace(TRIM(LOWER(unaccent(new_value->>0))), 's$', '', 'g') or 
				TRIM(LOWER(unaccent(new_value->>0))) = 
				regexp_replace(TRIM(LOWER(unaccent(old_value->>0))), 's$', '', 'g')

				or (
					-- for "es" the one I don't remove "es" from has to not end with "e"
					(
						TRIM(LOWER(unaccent(old_value->>0))) = 
						regexp_replace(TRIM(LOWER(unaccent(new_value->>0))), 'es$', '', 'g') and RIGHT(TRIM(LOWER(unaccent(old_value->>0))), 1) <> 'e'
					) or 
					(
						TRIM(LOWER(unaccent(new_value->>0))) = 
						regexp_replace(TRIM(LOWER(unaccent(old_value->>0))), 'es$', '', 'g') and RIGHT(TRIM(LOWER(unaccent(old_value->>0))), 1) <> 'e'
					)
				)
			)
		)
	);