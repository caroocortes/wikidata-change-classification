CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS re_formatting_predicted BOOLEAN DEFAULT FALSE;

UPDATE <change> c
SET re_formatting_predicted = TRUE
WHERE 
	re_formatting_predicted = FALSE AND
	c.datatype NOT IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema') AND
	c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
	c.old_value->>0 NOT IN ('somevalue', 'novalue') AND
	c.old_value->>0 <> c.new_value->>0 AND 
	(

		(-- dates like 00002025-10-02T... to 2025-10-02
			datatype = 'time' AND (
			(
				old_value->>0 = REGEXP_REPLACE(new_value->>0, '([+-])0*(\d+)', '\1\2') 
			   or 
			   new_value->>0 = REGEXP_REPLACE(old_value->>0, '([+-])0*(\d+)', '\1\2') -- \1 captures +/- and \2 captures leading zeros
			) 
			or 
			(
				old_value->>0 LIKE '%-01-01T%'
				AND new_value->>0 LIKE '%-00-00T%'
				AND substring(old_value->>0, 1, 5) = substring(new_value->>0, 1, 5)	-- same year
			)
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
				regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]+', '', 'g') = 
				regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]+', '', 'g') or 
				
				--  space normalization
				
				regexp_replace(lower(unaccent(c.old_value->>0)), '\s+', '', 'g') = 
				regexp_replace(lower(unaccent(c.new_value->>0)), '\s+', '', 'g') or
				
				-- trimming
				trim(c.old_value->>0) = 
				trim(c.new_value->>0) or
				
				-- quotes/brackets
				
				regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '["“”‘’\[\]\(\)\{\}\s]+', '', 'g') =   
				regexp_replace(TRIM((LOWER(unaccent(c.new_value->>0)))), '["“”‘’\[\]\(\)\{\}\s]+', '', 'g') or
				
				
				-- distance after removing hyphens/dashes
				
				regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '[-–—_\s]+', '', 'g') = 
				regexp_replace(TRIM(LOWER(unaccent(c.new_value->>0))), '[-–—_\s]+', '', 'g') or
				
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
		-- sign change conditions
		OR
		(
		
			datatype = 'quantity' AND
			(
				(
					SUBSTRING(old_value->>0, 1, 1) IN ('+', '-') AND
					SUBSTRING(new_value->>0, 1, 1) IN ('+', '-') AND
					SUBSTRING(old_value->>0, 1, 1) != SUBSTRING(new_value->>0, 1, 1) AND -- sign differs
					SUBSTRING(old_value->>0, 2) = SUBSTRING(new_value->>0, 2) -- rest remains the same
				)
				OR
				(
					SUBSTRING(new_value->>0, 1, 1) != '+' AND
					(old_value->>0)::decimal < 0 AND 
					(new_value->>0)::decimal > 0 AND
					ABS((old_value->>0)::decimal) = (new_value->>0)::decimal
				)
				OR 
				(
					SUBSTRING(old_value->>0, 1, 1) != '+' AND
					(old_value->>0)::decimal > 0 AND 
					(new_value->>0)::decimal < 0 AND
					(old_value->>0)::decimal = ABS((new_value->>0)::decimal)
				)
				OR
				( -- changes from 31.0 to 31, removing .0 at the end
					REPLACE(old_value, '+', '') LIKE '%.0'
  					AND REPLACE(new_value, '+', '') = REPLACE(REPLACE(old_value, '+', ''), '.0', '')
				)
			)
		)
		OR
		(  
			datatype = 'time' AND
			SUBSTRING(old_value->>0, 1, 1) IN ('+', '-') AND
			SUBSTRING(new_value->>0, 1, 1) IN ('+', '-') AND
			SUBSTRING(old_value->>0, 1, 1) != SUBSTRING(new_value->>0, 1, 1) AND -- sign differs
			SUBSTRING(old_value->>0, 2) = SUBSTRING(new_value->>0, 2) -- rest reamins the same
		)
		OR 
		(
			datatype = 'globecoordinate' AND 
			(
				(
					new_value->>'latitude' != '{}' AND old_value->>'latitude' != '{}' AND
					SUBSTRING(old_value->>'latitude', 1, 1) IN ('+', '-') AND
					SUBSTRING(new_value->>'latitude', 1, 1) IN ('+', '-') AND
					SUBSTRING(old_value->>'latitude', 1, 1) != SUBSTRING(new_value->>'latitude', 1, 1) AND
					SUBSTRING(old_value->>'latitude', 2) = SUBSTRING(new_value->>'latitude', 2)
				)
				OR
				(
					new_value->>'longitude' != '{}' AND old_value->>'longitude' != '{}' AND
					SUBSTRING(old_value->>'longitude', 1, 1) IN ('+', '-') AND
					SUBSTRING(new_value->>'longitude', 1, 1) IN ('+', '-') AND
					SUBSTRING(old_value->>'longitude', 1, 1) != SUBSTRING(new_value->>'longitude', 1, 1) AND
					SUBSTRING(old_value->>'longitude', 2) = SUBSTRING(new_value->>'longitude', 2)
				)
				-- not stored without the + for >0
				OR
				(
					SUBSTRING(new_value->>'latitude', 1, 1) != '+' AND
					(old_value->>'latitude')::decimal < 0 AND 
					(new_value->>'latitude')::decimal > 0 AND
					ABS((old_value->>'latitude')::decimal) = (new_value->>'latitude')::decimal
				)
				OR
				(
					SUBSTRING(old_value->>'latitude', 1, 1) != '+' AND
					(old_value->>'latitude')::decimal > 0 AND 
					(new_value->>'latitude')::decimal < 0 AND
					(old_value->>'latitude')::decimal = ABS((new_value->>'latitude')::decimal)
				)
				OR
				(
					SUBSTRING(new_value->>'longitude', 1, 1) != '+' AND
					(old_value->>'longitude')::decimal < 0 AND 
					(new_value->>'longitude')::decimal > 0 AND
					ABS((old_value->>'longitude')::decimal) = (new_value->>'longitude')::decimal
				)
				OR
				(
					SUBSTRING(old_value->>'longitude', 1, 1) != '+' AND
					(old_value->>'longitude')::decimal > 0 AND 
					(new_value->>'longitude')::decimal < 0 AND
					(old_value->>'longitude')::decimal = ABS((new_value->>'longitude')::decimal)
				)
			)
		)
	)
	<additional_filters>
	;