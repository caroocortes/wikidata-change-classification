CREATE TABLE property_time_until_reversion AS
select 
	property_id,
	property_label,
	AVG(AGE(reversion_timestamp, timestamp)) as avg_age_until_reversion,
	AVG(EXTRACT(YEAR FROM AGE(reversion_timestamp, timestamp))) as avg_year_until_reversion,
	AVG(EXTRACT(MONTH FROM AGE(reversion_timestamp, timestamp))) as avg_month_until_reversion,
	AVG(EXTRACT(DAY FROM AGE(reversion_timestamp, timestamp))) as avg_day_until_reversion,
	count(*) as num_reverted_edits
from value_change
where is_reverted = 1
group by property_id, property_label;