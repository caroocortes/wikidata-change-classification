CREATE TABLE IF NOT EXISTS change_stas_per_entity_time (
    entity_id INTEGER NOT NULL,
    property_id  INTEGER NOT NULL,
    time_period INTERVAL NOT NULL, -- chequear esto
    
    -- From value change table
    num_property_value_additions BIGINT DEFAULT 0, 
    num_property_value_deletions BIGINT DEFAULT 0,

    num_value_updates BIGINT DEFAULT 0,
    num_rank_changes BIGINT DEFAULT 0,

    -- From ref/qual tables
    num_reference_additions BIGINT DEFAULT 0,
    num_reference_deletions BIGINT DEFAULT 0,
    num_qualifier_additions BIGINT DEFAULT 0,
    num_qualifier_deletions BIGINT DEFAULT 0,

    -- num_soft_insertions BIGINT DEFAULT 0,
    -- num_soft_deletions BIGINT DEFAULT 0,

    -- From revision table
    total_num_revisions BIGINT DEFAULT 0,
    num_revisions_bot BIGINT DEFAULT 0,
    num_revisions_human BIGINT DEFAULT 0,
    num_revisions_anonymous BIGINT DEFAULT 0,
    num_unique_editors BIGINT DEFAULT 0,
    
    first_change_timestamp TIMESTAMP,
    last_change_timestamp TIMESTAMP,
    -- time_between_revisions INTERVAL,
    
    computed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (entity_id, property_id, time_period)
);

-- num entities per type -> can help me find popular types to showcase

INSERT INTO change_statistics (
    entity_id, property_id, time_period, 
    total_num_revisions,
    num_value_updates,
    num_rank_changes,
    num_property_value_additions,
    num_property_value_deletions,
    first_change_timestamp,
    last_change_timestamp)
SELECT 
    
    entity_id, 
    property_id, 
    to_char(timestamp, 'YYYY-MM') as time_period, 
    
    COUNT(distinct revision_id) as total_num_revisions,
    
    COUNT(*) FILTER (WHERE change_target = '' and action = 'UPDATE') as num_value_updates,
    COUNT(*) FILTER (WHERE change_target = 'rank' and action = 'UPDATE') as num_rank_changes,
    
    COUNT(value_id) FILTER (WHERE change_target = '' AND action = 'CREATE') as num_property_value_additions, -- if the same value is added multiple times, it counts multiple times
    COUNT(value_id) FILTER (WHERE change_target = '' AND action = 'DELETE') as num_property_value_deletions,

    MIN(timestamp) as first_change_timestamp,
    MAX(timestamp) as last_change_timestamp

FROM value_change
GROUP BY entity_id, property_id, time_period
ON CONFLICT (entity_id, property_id, time_period) DO NOTHING;