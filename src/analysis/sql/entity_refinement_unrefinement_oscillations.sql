WITH entity_changes AS (
    SELECT 
        r.entity_id,
        f.property_id,
		f.value_id,
        f.property_label,
        f.old_value_label,
        f.new_value_label,
        f.label,
        r.timestamp,
        -- get the next change for the same entity+property+value
        LEAD(f.label) OVER (
            PARTITION BY r.entity_id, f.property_id, f.value_id
            ORDER BY r.timestamp asc
        ) AS next_label
    FROM features_entity f
    JOIN revision r ON r.revision_id = f.revision_id
    WHERE f.label IN ('refinement', 'unrefinement')
    AND f.is_reverted = 0
),
-- get oscillations where a refinement is followed by an unrefinement or vice versa
oscillations AS (
    SELECT *
    FROM entity_changes
    WHERE (label = 'refinement' AND next_label = 'unrefinement')
    OR (label = 'unrefinement' AND next_label = 'refinement')
)
-- count oscillations per entity+property+value and show the sequence of changes
SELECT 
    entity_id,
    property_id,
	value_id,
    property_label,
    COUNT(*) as oscillation_count,
    -- show the sequence of values
    array_agg(old_value_label || ' -> ' || new_value_label 
        ORDER BY timestamp) as change_sequence
FROM oscillations
GROUP BY entity_id, property_id, property_label, value_id
HAVING COUNT(*) >= 2  -- at least 2 oscillations
ORDER BY oscillation_count DESC;