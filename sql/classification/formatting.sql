CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER TABLE :change
ADD COLUMN IF NOT EXISTS formatting BOOLEAN DEFAULT FALSE;

UPDATE :change c
SET formatting = TRUE
WHERE 
   c.datatype NOT IN ('wikibase-item', 'wikibase-entityid','wikibase-property','wikibase-lexeme','wikibase-sense','wikibase-form','entity-schema', 'globecoordinate') AND
   reverted_edit = FALSE AND reversion = FALSE AND -- considers (rever)ted edit + (rever)sion
   c.action = 'UPDATE' AND target = 'PROPERTY_VALUE' AND
   c.old_value->>0 <> c.new_value->>0 AND 
   (
   LOWER(TRIM(unaccent(c.old_value->>0)))
   = 
   LOWER(TRIM(unaccent(c.new_value->>0))) OR

   -- punctuation
   regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]', '', 'g') = 
   regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]', '', 'g') or 

   --  space normalization

   regexp_replace(lower(unaccent(c.old_value->>0)), '\s+', ' ', 'g') = 
   regexp_replace(lower(unaccent(c.new_value->>0)), '\s+', ' ', 'g') or

   -- trimming
   trim(c.old_value->>0) = 
   trim(c.new_value->>0) or

    -- quotes/brackets

   regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '["“”‘’\[\]\(\)\{\}]', '', 'g') =   
   regexp_replace(TRIM((LOWER(unaccent(c.new_value->>0)))), '["“”‘’\[\]\(\)\{\}]', '', 'g') or


    -- distance after removing hyphens/dashes

   regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '[-–—_]', '', 'g') = 
   regexp_replace(TRIM(LOWER(unaccent(c.new_value->>0))), '[-–—_]', '', 'g') or


    -- Article addition/removal at the start 

   regexp_replace(TRIM(LOWER(unaccent(old_value->>0))), '^(the |a |an )', '') = 
   regexp_replace(TRIM(LOWER(unaccent(new_value->>0))), '^(the |a |an )', '')
   )
   -- not an accent change (typo)
   AND NOT
      TRIM(LOWER(unaccent(c.old_value->>0))) = TRIM(LOWER(unaccent(c.new_value->>0))
) ;

----------------------------------------------------------------------------------
----------------------------------------------------------------------------------
-- Formatting changes and other things
----------------------------------------------------------------------------------
----------------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

ALTER TABLE change_sample
ADD COLUMN IF NOT EXISTS formatting BOOLEAN DEFAULT FALSE;

-- CTEs to compute distances and token stats
WITH candidates AS (
  SELECT
   c.revision_id,
   c.property_id,
   c.value_id,
   c.change_target,
   c.old_value->>0 AS old_val,
   c.new_value->>0 AS new_val,
   levenshtein(c.old_value->>0, c.new_value->>0) AS dist_raw,

   regexp_replace(
      regexp_replace(
         regexp_replace(
            regexp_replace(
               regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]+', ' ', 'g'), '\s+', ' ', 'g'
            ),
            '["“”‘’\[\]\(\)\{\}]', '', 'g'
         ), '[-–—_]', '', 'g'
      ), '^(the |a |an )', ''
   ) AS old_norm,

   regexp_replace(
      regexp_replace(
         regexp_replace(
            regexp_replace(
               regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]+', ' ', 'g'), '\s+', ' ', 'g'
            ),
            '["“”‘’\[\]\(\)\{\}]', '', 'g'
         ), '[-–—_]', '', 'g'
      ), '^(the |a |an )', ''
   ) AS new_norm,
    
    -- distance after punctuation+space normalization
   levenshtein(
      regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]', '', 'g'),
      regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]', '', 'g')
   ) AS dist_nopunct, 

   -- distance after space normalization
   levenshtein(
      regexp_replace(lower(unaccent(c.old_value->>0)), '\s+', ' ', 'g'), 
      regexp_replace(lower(unaccent(c.new_value->>0)), '\s+', ' ', 'g') 
   ) AS dist_spaces,

   -- distance after trimming
   levenshtein(
      trim(c.old_value->>0),
      trim(c.new_value->>0)
    ) AS dist_trim,

    -- distance after removing quotes/brackets
   levenshtein(
      regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '["“”‘’\[\]\(\)\{\}]', '', 'g'), 
      regexp_replace(TRIM((LOWER(unaccent(c.new_value->>0)))), '["“”‘’\[\]\(\)\{\}]', '', 'g')
    ) AS dist_quotes_brackets,

    -- distance after removing hyphens/dashes
   levenshtein(
      regexp_replace(TRIM(LOWER(unaccent(c.old_value->>0))), '[-–—_]', '', 'g'),
      regexp_replace(TRIM(LOWER(unaccent(c.new_value->>0))), '[-–—_]', '', 'g')
   ) AS dist_hyphens_dashes,

    -- Article addition/removal at the start 
   levenshtein(
      regexp_replace(TRIM(LOWER(unaccent(old_value->>0))), '^(the |a |an )', ''),
      regexp_replace(TRIM(LOWER(unaccent(new_value->>0))), '^(the |a |an )', '')
   ) AS dist_articles,

   array_length(regexp_split_to_array(
   regexp_replace(
      regexp_replace(
         regexp_replace(
            regexp_replace(
               regexp_replace(lower(unaccent(trim(c.old_value->>0))), '[[:punct:]\s]+', ' ', 'g'), '\s+', ' ', 'g'
            ),
            '["“”‘’\[\]\(\)\{\}]', '', 'g'
         ), '[-–—_]', '', 'g'
      ), '^(the |a |an )', ''
   ), '\s+'), 1) AS old_norm_toks,

   array_length(regexp_split_to_array(
   regexp_replace(
      regexp_replace(
         regexp_replace(
            regexp_replace(
               regexp_replace(lower(unaccent(trim(c.new_value->>0))), '[[:punct:]\s]+', ' ', 'g'), '\s+', ' ', 'g'
            ),
            '["“”‘’\[\]\(\)\{\}]', '', 'g'
         ), '[-–—_]', '', 'g'
      ), '^(the |a |an )', ''
   ), '\s+'), 1) AS new_norm_toks,

  FROM change_sample c
  WHERE
    c.datatype NOT IN (
      'wikibase-item','wikibase-entityid','wikibase-property','wikibase-lexeme',
      'wikibase-sense','wikibase-form','entity-schema','globecoordinate'
    )
    AND c.action = 'UPDATE'
    AND c.target = 'PROPERTY_VALUE'
    AND c.old_value IS NOT NULL
    AND c.new_value IS NOT NULL
    AND c.old_value->>0 IS DISTINCT FROM c.new_value->>0
),

token_pairs AS (
  SELECT
    cand.revision_id,
    gs.i,
    otoks[gs.i] AS old_tok,
    ntoks[gs.i] AS new_tok
  FROM (
    SELECT
      revision_id,
      regexp_split_to_array(old_norm, '\s+') AS otoks, -- split into words
      regexp_split_to_array(new_norm, '\s+') AS ntoks -- split into words
    FROM candidates
  ) cand
  CROSS JOIN LATERAL generate_series(
    1,
    greatest(array_length(otoks,1), array_length(ntoks,1))
  ) AS gs(i)
),

token_agg AS (
  SELECT
    revision_id,
    COUNT(*) FILTER (WHERE COALESCE(old_tok,'') = COALESCE(new_tok,''))             AS same_tokens,
    COUNT(*) FILTER (WHERE COALESCE(old_tok,'') <> COALESCE(new_tok,''))             AS diff_tokens,
    MAX(levenshtein(COALESCE(old_tok,''), COALESCE(new_tok,''))) 
        FILTER (WHERE old_tok IS DISTINCT FROM new_tok)                              AS max_token_dist
  FROM token_pairs
  GROUP BY revision_id
),

metrics AS (
  SELECT
    c.*,
    COALESCE(t.same_tokens, 0) AS same_tokens,
    COALESCE(t.diff_tokens, 0) AS diff_tokens,
    COALESCE(t.max_token_dist, 0) AS max_token_dist
  FROM candidates c
  LEFT JOIN token_agg t USING (revision_id)
)

UPDATE change_sample cs
SET formatting_only = TRUE
FROM metrics m
WHERE cs.revision_id = m.revision_id
  AND (
   -- pure formatting: normalization makes them identical
   m.dist_spaces = 0
   OR m.dist_nopunct = 0
   OR m.dist_trim = 0
   OR m.dist_quotes_brackets = 0
   OR m.dist_hyphens_dashes = 0
   OR m.dist_articles = 0
  );

UPDATE change_sample cs
SET formatting_component = TRUE
FROM metrics m
WHERE cs.revision_id = m.revision_id
  AND (
       -- normalization reduces edit distance -> formatting change exists
       m.dist_spaces < m.dist_raw
    OR m.dist_nopunct < m.dist_raw 
    OR m.dist_trim < m.dist_raw
    OR m.dist_quotes_brackets < m.dist_raw
    OR m.dist_hyphens_dashes < m.dist_raw
    OR m.dist_articles < m.dist_raw
    -- OR: most tokens equal (only one token differs)
    OR (
         m.same_tokens >= GREATEST(COALESCE(m.old_norm_toks,0), COALESCE(m.new_norm_toks,0)) - 1
       )
  );