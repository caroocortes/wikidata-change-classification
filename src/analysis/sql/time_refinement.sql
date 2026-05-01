-- TIME REFINEMENT ANALYSIS
-- How many refinements add just the day, just the month, or both at the same time?
WITH time_refinements AS (
    -- Get all time refinements ordered by item + property + time
    SELECT 
		entity_id
        property_id,
		property_label,
        old_value,
        new_value,
        timestamp
    FROM features_time f join revision r on r.revision_id = f.revision_id
	WHERE
    label = 'refinement' and is_reverted = 0 and reversion = 0
	order by property_id, property_label, timestamp
),
incremental_pattern AS (
    -- Check if the pattern is 00 -> non-zero for month or day
    SELECT *,
        -- Month refinement: YYYY-00-00 -> YYYY-MM-00
        CASE WHEN (old_value->>0 ~ '\d+-00-00' or old_value->>0 ~ '\d+-01-01')
              AND new_value->>0 !~ '\d+-00-' and new_value->>0 ~ '-00T'
             THEN 1 ELSE 0 END AS is_month_refinement,
        -- Day refinement: YYYY-MM-00 -> YYYY-MM-DD
        CASE WHEN old_value->>0 ~ '\d+-\d{2}-00' 
              AND new_value->>0 !~ '-00T'
             THEN 1 ELSE 0 END AS is_day_refinement,
		-- Day & Month refinement at the same time
		CASE WHEN (old_value->>0 ~ '\d+-00-00' or old_value->>0 ~ '\d+-01-01')
			AND new_value->>0 !~ '\d+-00-' AND  -- month is not 00
			new_value->>0 !~ '-00T'
			THEN 1 ELSE 0 END AS is_month_day_refinement
    FROM time_refinements
)
SELECT 
    COUNT(*) AS total_time_refinements,
    SUM(is_month_refinement) AS only_month_refinements,
    SUM(is_day_refinement) AS only_day_refinements,
    SUM(is_month_day_refinement) AS day_month_refinements
FROM incremental_pattern;

-- Number of time creations where the value only contains a year
SELECT 
    COUNT(*) AS total_time_values,
    SUM(CASE WHEN new_value->>0 ~ '^\+?\d+-00-00' or new_value->>0 ~ '^\+?\d+-01-01' THEN 1 ELSE 0 END) AS year_only
FROM value_change v
WHERE action = 'CREATE' and
new_datatype = 'time' and
change_target = '';