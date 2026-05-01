-- TEXT REFINEMENTS 
select count(*)
from features_text f 
where label = 'refinement';

-- properties in refinements
SELECT property_id, property_label, count(*)
from features_text
where label = 'refinement'
group by  property_id, property_label
order by count(*) desc;

-- entities with changes to label and description
select property_id, property_label, count(distinct entity_id)
from value_change
where property_id = -1 or property_id = -2
group by property_id, property_label;
