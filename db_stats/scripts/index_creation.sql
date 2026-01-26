CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_property_id ON value_change_entity(property_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_entity_id ON value_change_entity(entity_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_property_label ON value_change_entity(property_label);
CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_timestamp ON value_change_entity(timestamp);
CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_action ON value_change_entity(action);
CREATE INDEX IF NOT EXISTS idx_(value_change_entity)_target ON value_change_entity(target);


CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_property_id ON value_change_quantity(property_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_entity_id ON value_change_quantity(entity_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_property_label ON value_change_quantity(property_label);
CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_timestamp ON value_change_quantity(timestamp);
CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_action ON value_change_quantity(action);
CREATE INDEX IF NOT EXISTS idx_(value_change_quantity)_target ON value_change_quantity(target);


CREATE INDEX IF NOT EXISTS idx_(value_change_text)_property_id ON value_change_text(property_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_text)_entity_id ON value_change_text(entity_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_text)_property_label ON value_change_text(property_label);
CREATE INDEX IF NOT EXISTS idx_(value_change_text)_timestamp ON value_change_text(timestamp);
CREATE INDEX IF NOT EXISTS idx_(value_change_text)_action ON value_change_text(action);
CREATE INDEX IF NOT EXISTS idx_(value_change_text)_target ON value_change_text(target);

CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_property_id ON value_change_globe(property_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_entity_id ON value_change_globe(entity_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_property_label ON value_change_globe(property_label);
CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_timestamp ON value_change_globe(timestamp);
CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_action ON value_change_globe(action);
CREATE INDEX IF NOT EXISTS idx_(value_change_globe)_target ON value_change_globe(target);

CREATE INDEX IF NOT EXISTS idx_(value_change_time)_property_id ON value_change_time(property_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_time)_entity_id ON value_change_time(entity_id);
CREATE INDEX IF NOT EXISTS idx_(value_change_time)_property_label ON value_change_time(property_label);
CREATE INDEX IF NOT EXISTS idx_(value_change_time)_timestamp ON value_change_time(timestamp);
CREATE INDEX IF NOT EXISTS idx_(value_change_time)_action ON value_change_time(action);
CREATE INDEX IF NOT EXISTS idx_(value_change_time)_target ON value_change_time(target);