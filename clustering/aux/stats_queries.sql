-- Number of change: 59.284.666
select count(*)
from value_change

-- Number of updates: 3.916.893
select count(*)
from value_change
where action = 'UPDATE'

-- Number of value updates: 2.747.935
select count(*)
from value_change
where action = 'UPDATE' AND change_target = ''

-- Number of quantity updates: 119.950
select count(*)
from value_change
where action = 'UPDATE' AND change_target = '' AND datatype = 'quantity'

-- Number of time updates: 104.913
select count(*)
from value_change
where action = 'UPDATE' AND change_target = '' AND datatype = 'time'

-- Number of globecoordinate updates: 26.913
select count(*)
from value_change
where action = 'UPDATE' AND change_target = '' AND datatype = 'globecoordinate'

-- Number of deletes: 7.859.208
select count(*)
from value_change
where action = 'DELETE'

-- Number of creates: 47.508.565
select count(*)
from value_change
where action = 'CREATE'

-- Number of string updates: 1.543.790
select count(*)
from value_change
where action = 'UPDATE' AND change_target = '' AND datatype in ('monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values')


-- Number of entity updates: 952.040
select count(*)
from value_change
where action = 'UPDATE' AND change_target = '' AND datatype in
('wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema')
