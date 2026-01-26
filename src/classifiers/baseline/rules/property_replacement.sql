ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS property_replacement_predicted BOOLEAN DEFAULT FALSE;

-- For cte1
CREATE INDEX IF NOT EXISTS idx_cte1_entity_oldvalue  ON <change_timestamp_entity>(entity_id, old_value);

-- For cte2
CREATE INDEX IF NOT EXISTS idx_cte2_entity_newvalue  ON <change_timestamp_entity>(entity_id, new_value);

CREATE TEMP TABLE
property_replacement_changes as (
    select 
        cte1.revision_id as replaced_revision_id, 
        cte1.property_id as replaced_property_id, 
        cte1.value_id as replaced_value_id,
        cte2.revision_id as replacement_revision_id, 
        cte2.property_id as replacement_property_id, 
        cte2.value_id as replacement_value_id
    from 
        <change_timestamp_entity> cte1 join <change_timestamp_entity> cte2 on 
        cte1.entity_id = cte2.entity_id
    where 
        cte1.change_target = '' and -- only check value changes
        cte2.change_target = '' and -- only check value changes
        (
            (
                cte1.old_value = cte2.new_value and 
                cte1.timestamp <= cte2.timestamp and
                cte1.property_id != cte2.property_id and
                cte1.action = 'DELETE' and
                cte2.action = 'CREATE'
            )
            or 
            (
                cte1.new_value = cte2.old_value and 
                cte1.timestamp <= cte2.timestamp and
                cte1.property_id != cte2.property_id and
                cte1.action = 'CREATE' and
                cte2.action = 'DELETE'
            )
        )
        <additional_filters>
        
);
UPDATE <change> AS vc
SET property_replacement_predicted = TRUE
FROM property_replacement_changes prc
WHERE 
    (
        vc.revision_id = prc.replaced_revision_id and 
        vc.property_id = prc.replaced_property_id and 
        vc.value_id = prc.replaced_value_id
    )
    or
    (
        vc.revision_id = prc.replacement_revision_id and 
        vc.property_id = prc.replacement_property_id and 
        vc.value_id = prc.replacement_value_id
    )
    ;