CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS formatting BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET formatting = TRUE
WHERE 
   c.datatype NOT IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema', 'globecoordinate') AND
   is_vandalism = FALSE AND
   c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
   c.old_value->>0 <> c.new_value->>0 AND 
   (
       -- Capitalization 
      LOWER(c.old_value->>0) = LOWER(c.new_value->>0) OR
       -- Punctuation or whitespace
      REGEXP_REPLACE(c.old_value->>0, '[[:punct:]\s]', '', 'g') = 
         REGEXP_REPLACE(c.new_value->>0, '[[:punct:]\s]', '', 'g') OR
         -- Leading/trailing spaces
      TRIM(c.old_value->>0) = TRIM(c.new_value->>0) OR
         -- Quotes/brackets normalization
      REGEXP_REPLACE(c.old_value->>0, '["“”‘’\[\]\(\)\{\}]', '', 'g') = 
         REGEXP_REPLACE(c.new_value->>0, '["“”‘’\[\]\(\)\{\}]', '', 'g') OR
         -- Hyphens/dashes normalization
      REGEXP_REPLACE(c.old_value->>0, '[-–—_]', '', 'g') = 
         REGEXP_REPLACE(c.new_value->>0, '[-–—_]', '', 'g') OR
         -- Fuzzy changes
      SIMILARITY(c.old_value->>0, c.new_value->>0) > 0.9
   ) ;
