LOG_DIR = 'logs'

WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']
WD_BASIC_TYPES = ['globecoordinate', 'quantity', 'time']

GS_COLUMNS = ['revision_id','entity_id','entity_label',',value_id','change_target','property_id','property_label','old_value','old_value_label','new_value','new_value_label','datatype','action','target','main_entity_type','latest_description','new_value_entity_type','old_value_entity_type','label']

BASIC_CHANGE_LABELS = ['textual_change', 're_formatting', 'refinement', 'unrefinement', 'property_value_update', 'link_change', 'rewording']

REVERTED_EDIT_LABEL = 'reverted_edit'

PROPERTY_REPLACEMENT_LABEL = 'property_replacement'

SOFT_INSERTIONS = 'soft_insertions' # normal/deprecated -> preferred 
SOFT_DELETIONS = 'soft_deletions' # rank deprecation (normal/prefered -> deprecated) + adding end time qualifier

CLASSES_PER_DATATYPE = {
    'string': ['textual_change', 're_formatting', 'refinement', 'unrefinement', 'property_value_update', 'rewording'],
    'quantity': ['refinement', 'unrefinement', 'property_value_update'],
    'time': ['re_formatting', 'refinement', 'unrefinement', 'property_value_update'],
    'globecoordinate': ['re_formatting', 'refinement', 'unrefinement', 'property_value_update'],
    'entity': ['refinement', 'unrefinement', 'property_value_update', 'link_change'] 
}

DATATYPE_INDEPENDENT_CLASSES = [REVERTED_EDIT_LABEL, PROPERTY_REPLACEMENT_LABEL, SOFT_INSERTIONS, SOFT_DELETIONS]

ML_MODELS = ['kn', 'random_forest', 'gradient_boosting']

ML_MODELS_LABELS = ['K-Neighbors', 'Random Forest', 'Gradient Boosting']

RANDOM_STATE = 42