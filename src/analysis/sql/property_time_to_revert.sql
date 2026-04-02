create table prop_reverts as
SELECT 
    v1.property_id,
    v1.property_label,
	COUNT(*) as reversion_count,
	AVG(EXTRACT(EPOCH FROM (v2.timestamp - v1.timestamp)) / 3600) as avg_hours_to_reversion
FROM value_change v1
JOIN value_change v2 ON 
	v1.value_id = v2.value_id and 
	v1.property_id = v2.property_id and
	v1.entity_id = v2.entity_id
WHERE 
v2.timestamp > v1.timestamp and
v1.is_reverted = 1 and 
v2.reversion = 1 and
(
	(v1.old_hash = v2.new_hash 
		AND v1.old_hash != '' 
		AND v2.new_hash != '')
	OR
	(v1.old_hash = '' 
		AND v2.new_hash = '' 
		AND v1.new_hash = v2.old_hash)
)
group by v1.property_id, v1.property_label