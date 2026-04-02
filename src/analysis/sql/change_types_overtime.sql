-- QUANTITY
create table change_types_overtime as
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_quantity 
	WHERE label IS NOT NULL AND label != ''
)
select 
	'quantity' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year


-- TIME (1 hr 35 min)
INSERT INTO change_types_overtime (datatype, individual_label, count, year)
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_time
	WHERE label IS NOT NULL AND label != ''
)
select 
	'time' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year

-- GLOBE LATITUDE(1h 35min)
INSERT INTO change_types_overtime (datatype, individual_label, count, year)
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label_latitude, ', ')) AS individual_label
    FROM features_globecoordinate
	WHERE label_latitude IS NOT NULL AND label_latitude != ''
)
select 
	'globecoordinate_latitude' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year


-- GLOBE LONGITUDE (1h 35min)
INSERT INTO change_types_overtime (datatype, individual_label, count, year)
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label_longitude, ', ')) AS individual_label
    FROM features_globecoordinate
	WHERE label_longitude IS NOT NULL AND label_longitude != ''
)
select 
	'globecoordinate_longitude' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year


-- TEXT (1h 44min)
INSERT INTO change_types_overtime (datatype, individual_label, count, year)
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_text 
	WHERE label IS NOT NULL AND label != ''
)
select 
	'text' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year

-- ENTITY
INSERT INTO change_types_overtime (datatype, individual_label, count, year)
WITH label_split AS (
    SELECT 
		revision_id,
		property_id,
		value_id, 
		change_target,
		unnest(string_to_array(label, ', ')) AS individual_label
    FROM features_entity
	WHERE label IS NOT NULL AND label != ''
)
select 
	'entity' as datatype,
	individual_label,
	count(*),
	r.year
from label_split f join revision r on r.revision_id = f.revision_id
group by individual_label, r.year