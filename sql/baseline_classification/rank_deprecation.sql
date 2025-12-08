ALTER TABLE <change>
ADD COLUMN IF NOT EXISTS rank_deprecation_predicted BOOLEAN DEFAULT FALSE;

UPDATE <change> 
SET rank_deprecation_predicted = TRUE
WHERE
change_target = 'rank' and 
old_value->>0 IN ('normal', 'preferred') and 
new_value->>0 = 'deprecated'
<additional_filters>
;
