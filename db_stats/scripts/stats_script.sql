DROP TABLE IF EXISTS stats;

CREATE TABLE IF NOT EXISTS stats (
    dataset TEXT NOT NULL,     -- 'rest' | 'scholarly_articles'
    metric  TEXT NOT NULL,
    count   BIGINT NOT NULL,
    computed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (dataset, metric)
);

WITH revision_stats AS (
    SELECT 
        COUNT(DISTINCT file_path) AS num_files,
        COUNT(*) AS num_revisions,
        COUNT(DISTINCT entity_id) AS num_entities
    FROM :revision_table
),
value_change_stats AS (
    SELECT 
    -- Basic change statistics
        COUNT(*) AS num_changes,
        COUNT(*) FILTER (WHERE action = 'CREATE') AS num_creates,
        COUNT(*) FILTER (WHERE action = 'DELETE') AS num_deletes,
		COUNT(*) FILTER (WHERE action = 'UPDATE') AS num_updates,
		COUNT(*) FILTER (WHERE change_target = '') AS num_only_value_changes,
		COUNT(*) FILTER (WHERE change_target = 'rank') AS num_rank_changes,
    -- Datatype-specific change statistics
		COUNT(*) FILTER (WHERE new_datatype = 'time' and old_datatype = 'time') AS num_time_changes,
		COUNT(*) FILTER (WHERE new_datatype = 'globecoordinate' and old_datatype = 'globecoordinate') AS num_globe_changes,
		COUNT(*) FILTER (WHERE new_datatype = 'quantity' and old_datatype = 'quantity') AS num_quantity_changes,
		COUNT(*) FILTER (WHERE new_datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values') and old_datatype IN ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values')) AS num_text_changes,
		COUNT(*) FILTER (WHERE new_datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema') and old_datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema')) AS num_entity_changes,
    	COUNT(*) FILTER (WHERE change_target != 'rank' and change_target != '') AS num_dt_metadata_changes

	FROM :value_change_table
),
entity_average_stats AS (
    SELECT 
        AVG(entity_change_count) AS avg_value_changes_per_entity,
        AVG(entity_value_updates) AS avg_value_updates_per_entity,
        AVG(entity_value_deletes) AS avg_value_deletes_per_entity,
        AVG(entity_value_creates) AS avg_value_creates_per_entity
    FROM (
        SELECT 
            entity_id, 
            COUNT(*) as entity_change_count,
            COUNT(*) FILTER (WHERE action = 'UPDATE') as entity_value_updates,
            COUNT(*) FILTER (WHERE action = 'DELETE') as entity_value_deletes,
            COUNT(*) FILTER (WHERE action = 'CREATE') as entity_value_creates
        FROM :value_change_table 
        WHERE change_target = ''
        GROUP BY entity_id
    ) per_entity
),
datatype_metadata_change_stats as
(
    SELECT 
        COUNT(*) AS num_dt_changes,
		COUNT(*) FILTER (WHERE action = 'CREATE') AS num_creates,
        COUNT(*) FILTER (WHERE action = 'DELETE') AS num_deletes,
		COUNT(*) FILTER (WHERE action = 'UPDATE') AS num_updates
	FROM :datatype_metadata_change_table
)

INSERT INTO stats (dataset, metric, count)
SELECT * FROM (
SELECT :'dataset_name' AS dataset, 'number of files' AS metric, num_files AS count FROM revision_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of revisions' AS metric, num_revisions AS count FROM revision_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of entities' AS metric, num_entities AS count FROM revision_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of changes' AS metric, num_changes AS count FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of creates' AS metric, num_creates FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of deletes' AS metric, num_deletes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of updates' AS metric, num_updates FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of value changes (ONLY)' AS metric, num_only_value_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'avg. number of value changes per entity' AS metric, avg_value_changes_per_entity FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'avg. number of value updates per entity' AS metric, avg_value_updates_per_entity FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'avg. number of value deletes per entity' AS metric, avg_value_deletes_per_entity FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'avg. number of value creates per entity' AS metric, avg_value_creates_per_entity FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of rank changes (ONLY)' AS metric, num_rank_changes FROM value_change_stats
-- UNION ALL -- union all doesn't remove duplicates (there won't be any anyway), it should be faster than just union
-- SELECT :'dataset_name' AS dataset, 'number of time changes' AS metric, num_time_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of globecoord. changes' AS metric, num_globe_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of quantity changes' AS metric, num_quantity_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of entity changes' AS metric, num_entity_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of text changes' AS metric, num_text_changes FROM value_change_stats
-- UNION ALL
-- SELECT :'dataset_name' AS dataset, 'number of datatype metadata changes' as metric, num_dt_changes FROM datatype_metadata_change_stats
-- UNION ALL 
-- SELECT :'dataset_name' AS dataset, 'number of datatype metadata creates' as metric, num_creates FROM datatype_metadata_change_stats
-- UNION ALL 
-- SELECT :'dataset_name' AS dataset, 'number of datatype metadata updates' as metric, num_updates FROM datatype_metadata_change_stats
-- UNION ALL 
-- SELECT :'dataset_name' AS dataset, 'number of datatype metadata deletes' as metric, num_deletes FROM datatype_metadata_change_stats
) s;