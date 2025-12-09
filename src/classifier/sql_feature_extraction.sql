-- Get latest description of all the entities
alter table gold_standard
add column latest_description VARCHAR(255) DEFAULT '';

WITH ranked_descriptions AS (
    SELECT r.entity_id, r.revision_id, vc.new_value,
           ROW_NUMBER() OVER (PARTITION BY r.entity_id ORDER BY r.timestamp DESC) as rn
    FROM revision r
    JOIN value_change vc ON r.revision_id = vc.revision_id
	JOIN gold_standard gs on gs.entity_id = r.entity_id
    WHERE vc.property_id = -2
)
UPDATE gold_standard gs
SET latest_description = rd.new_value
FROM ranked_descriptions rd
WHERE gs.entity_id = rd.entity_id AND rd.rn = 1;

-- Get main entity type + old_value/new_value entity type if they are entity's ids
alter table gold_standard
ADD PRIMARY KEY (revision_id, property_id, value_id, change_target),
ADD FOREIGN KEY (revision_id) REFERENCES revision(revision_id);

CREATE INDEX gs_entity_id
ON gold_standard (entity_id);

CREATE INDEX rev_entity_id
ON revision (entity_id);

ALTER TABLE gold_standard
ADD COLUMN main_entity_type VARCHAR(1000),
ADD COLUMN new_value_entity_type VARCHAR(1000),
ADD COLUMN old_value_entity_type VARCHAR(1000);

WITH entity_types AS (
SELECT 
    gs.entity_id,
    STRING_AGG(DISTINCT class_label, ', ') as entity_types
FROM gold_standard gs 
JOIN revision r ON gs.revision_id = r.revision_id
LEFT JOIN (
    SELECT entity_id_numeric, class_label FROM entity_type_p31
    UNION ALL
    SELECT entity_id_numeric, class_label FROM entity_type_p279
) all_types ON all_types.entity_id_numeric = r.entity_id
GROUP BY gs.entity_id
)
UPDATE gold_standard gs
SET main_entity_type = et.entity_types
FROM entity_types et
WHERE gs.entity_id = et.entity_id;

-- TYPE OF NEW VALUE
WITH entity_types_new_value AS (
    SELECT 
        gs.new_value->>0 AS entity_id,
        STRING_AGG(DISTINCT class_label, ', ') as entity_types
    FROM gold_standard gs
    JOIN revision r ON gs.revision_id = r.revision_id
    LEFT JOIN (
        SELECT entity_id, class_label FROM entity_type_p31
        UNION ALL
        SELECT entity_id, class_label FROM entity_type_p279
    ) all_types ON all_types.entity_id = gs.new_value->>0
    WHERE 
    gs.datatype IN ('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema') 
    GROUP BY gs.new_value
)
UPDATE gold_standard gs
SET new_value_entity_type = etnv.entity_types
FROM entity_types_new_value etnv
WHERE gs.new_value->>0 = etnv.entity_id;

-- TYPE OF OLD VALUE
WITH entity_types_old_value AS (
    SELECT 
        gs.old_value->>0 AS entity_id,
        STRING_AGG(DISTINCT class_label, ', ') as entity_types
    FROM gold_standard gs
    JOIN revision r ON gs.revision_id = r.revision_id
    LEFT JOIN (
        SELECT entity_id, class_label FROM entity_type_p31
        UNION ALL
        SELECT entity_id, class_label FROM entity_type_p279
    ) all_types ON all_types.entity_id = gs.old_value->>0
    WHERE 
    gs.old_value->>0 ILIKE 'Q%'
    GROUP BY gs.old_value
)
UPDATE gold_standard gs
SET old_value_entity_type = etov.entity_types
FROM entity_types_old_value etov
WHERE gs.old_value->>0 = etov.entity_id;