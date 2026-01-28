# =====================================
#  LABELS, etc 
# =====================================
WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']
WD_BASIC_TYPES = ['globecoordinate', 'quantity', 'time']

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

# ===============================
#  ML Models 
# ===============================
ML_MODELS = ['kn', 'random_forest', 'gradient_boosting', 'xgboost']
ML_MODELS_LABELS = ['K-Neighbors', 'Random Forest', 'Gradient Boosting', 'XGBoost']

# ===============================
#  Paths 
# ===============================
TRAINING_INFO_DIR = 'src/classifiers/ml/training_info' # stores trained models
FEATURES_DIR = 'src/classifiers/ml/features'
GOLD_STANDARD_DIR = 'gold_standard'
CONFIG_DIR = 'src/config'
LOG_DIR = 'logs'
MODELS_CONFIG_PATH = 'src/config/models_config.json'
TRAINING_RESULTS = 'src/results/training'
BASELINE_RESULTS = 'src/results/baseline'
CLASSIFICATION_RESULTS = 'src/results/classification'
CHANGES_TO_CLASSIFY = 'src/changes_to_classify'



BASE_KEY_TYPES = {
    'revision_id': 'BIGINT',
    'property_id': 'INT',
    'value_id': 'TEXT',
    'change_target': 'TEXT'
}

PROP_REP_KEY_TYPES = {
    'pair_id': 'BIGINT'
}