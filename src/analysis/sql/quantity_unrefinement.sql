SELECT 
    COUNT(*) AS total_unrefinements,
    -- floating point artifacts: old value has suspiciously long decimal
    SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) > 10 
        THEN 1 ELSE 0 END) AS long_precision_change,
	SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) <= 10 
		AND new_value->>0 ~ '\.' THEN 1 ELSE 0 END) as small_precision_change,
    -- genuine precision reduction: old value is short but loses decimals
    SUM(CASE WHEN length(old_value->>0) - position('.' IN old_value->>0) <= 10
        AND new_value->>0 !~ '\.'
        THEN 1 ELSE 0 END) AS precision_removal
FROM features_quantity
WHERE label = 'unrefinement'