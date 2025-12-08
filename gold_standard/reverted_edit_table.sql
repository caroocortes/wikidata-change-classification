WITH reverted_edits AS (
    SELECT 
        revision_id,
        entity_id,
        property_id,
        value_id,
        change_target,
        timestamp,
		label
    FROM reverted_edit_gs r
),
-- get previous 10 changes
previous_10_changes AS (
    SELECT 
        re.revision_id as anchor_revision_id,
        re.entity_id,
        re.property_id as anchor_property_id,
        re.value_id as anchor_value_id,
        re.change_target as anchor_change_target,
        r.revision_id,
        r.timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY re.revision_id, re.property_id, re.value_id, re.change_target
            ORDER BY r.timestamp DESC
        ) as revision_rank_before
    FROM reverted_edits re
    JOIN revision r ON r.entity_id = re.entity_id
    JOIN value_change vc ON vc.revision_id = r.revision_id
        AND vc.property_id = re.property_id
        AND vc.value_id = re.value_id
        AND vc.change_target = re.change_target
    WHERE r.timestamp < re.timestamp  -- Changes BEFORE the reverted edit
),
-- Get ALL changes within 1 month after (not limited to 10)
next_changes_1month AS (
    SELECT 
        re.revision_id as anchor_revision_id,
        re.entity_id,
        re.property_id as anchor_property_id,
        re.value_id as anchor_value_id,
        re.change_target as anchor_change_target,
        r.revision_id,
        r.timestamp
    FROM reverted_edits re
    JOIN revision r ON r.entity_id = re.entity_id
    JOIN value_change vc ON vc.revision_id = r.revision_id
        AND vc.property_id = re.property_id
        AND vc.value_id = re.value_id
        AND vc.change_target = re.change_target
    WHERE r.timestamp > re.timestamp  -- Changes AFTER the reverted edit
        AND r.timestamp <= re.timestamp + INTERVAL '1 month'  -- Within 1 month
)
-- Put everything in 1 table
SELECT 
    p10.anchor_revision_id,
    r.revision_id,
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
    vc.new_hash,
    vc.old_hash,
    -1 as revision_rank,
    r.timestamp,
    r.comment,
    '' as label
FROM previous_10_changes p10
JOIN revision r ON p10.revision_id = r.revision_id
JOIN value_change vc ON vc.revision_id = r.revision_id
    AND vc.property_id = p10.anchor_property_id
    AND vc.value_id = p10.anchor_value_id
    AND vc.change_target = p10.anchor_change_target
WHERE p10.revision_rank_before <= 10

UNION ALL

SELECT 
    re.revision_id as anchor_revision_id,
    r.revision_id,
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
    vc.new_hash,
    vc.old_hash,
    0 as revision_rank,
    r.timestamp,
    r.comment,
    re.label
FROM reverted_edits re
JOIN revision r ON re.revision_id = r.revision_id
JOIN value_change vc ON vc.revision_id = r.revision_id
    AND vc.property_id = re.property_id
    AND vc.value_id = re.value_id
    AND vc.change_target = re.change_target

UNION ALL

-- All changes within 1 month after
SELECT 
    n1m.anchor_revision_id,
    r.revision_id,
    r.entity_id,
    r.entity_label,
    vc.value_id,
    vc.property_id,
    vc.change_target,
    vc.property_label,
    vc.old_value,
    vc.old_value_label,
    vc.new_value,
    vc.new_value_label,
    vc.datatype,
    vc.new_hash,
    vc.old_hash,
    1 as revision_rank,
    r.timestamp,
    r.comment,
    '' as label
FROM next_changes_1month n1m
JOIN revision r ON n1m.revision_id = r.revision_id
JOIN value_change vc ON vc.revision_id = r.revision_id
    AND vc.property_id = n1m.anchor_property_id
    AND vc.value_id = n1m.anchor_value_id
    AND vc.change_target = n1m.anchor_change_target

ORDER BY anchor_revision_id, revision_rank, timestamp;


