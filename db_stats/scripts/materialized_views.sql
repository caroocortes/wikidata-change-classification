CREATE MATERIALIZED VIEW IF NOT EXISTS value_change_time
AS
 SELECT *
 FROM value_change
 WHERE new_datatype = 'time' OR old_datatype = 'time'
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS value_change_quantity
AS
 SELECT *
 FROM value_change
 WHERE new_datatype = 'quantity' OR old_datatype = 'quantity'
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS value_change_globe
AS
 SELECT *
 FROM value_change
 WHERE new_datatype = 'globecoordinate' OR old_datatype = 'globecoordinate'
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS value_change_text
AS
 SELECT *
 FROM value_change
 WHERE new_datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values') OR old_datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values')
WITH DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS value_change_entity
AS
 SELECT *
 FROM value_change
 WHERE new_datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema') OR old_datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema')
WITH DATA;