-- GLOBECOORDINATE REFINEMENT ANALYSIS
-- Latitude (DMS to decimal conversion + comment check)
SELECT 
	count(*) AS total_refinements,
    sum(
	CASE WHEN abs(
        (regexp_match(comment, '(\d+)°(\d+)''(\d+\.?\d*)"'))[1]::float +
        (regexp_match(comment, '(\d+)°(\d+)''(\d+\.?\d*)"'))[2]::float / 60 +
        (regexp_match(comment, '(\d+)°(\d+)''(\d+\.?\d*)"'))[3]::float / 3600
        - abs(latitude_new::float)
    ) < 0.0001 and comment ~ '\d+°\d+' then 1 else 0 end) as dms_coversion
FROM features_globecoordinate f join revision r on r.revision_id = f.revision_id
WHERE label_latitude = 'refinement';


-- Longitude (DMS to decimal conversion + comment check)
WITH matches AS (
    SELECT 
		new_value,
        longitude_new,
        comment,
        array_agg(m) AS all_matches
    FROM features_globecoordinate f
    JOIN revision r ON r.revision_id = f.revision_id,
    regexp_matches(comment, '(\d+)°(\d+)''(\d+\.?\d*)"', 'g') AS m
    WHERE label_longitude = 'refinement'
    GROUP BY new_value, longitude_new, comment
)
SELECT
	COUNT(*) as all_refinements,
    sum(case when abs(
        all_matches[2][1]::float + 
        all_matches[2][2]::float / 60 + 
        all_matches[2][3]::float / 3600
        - abs(longitude_new::float)
    ) < 0.0001 then 1 else 0 end) AS num_dms_matches
FROM matches
WHERE array_length(all_matches, 1) >= 2
