# =====================================
#  LABELS, etc 
# =====================================
WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']
WD_BASIC_TYPES = ['globecoordinate_latitude', 'globecoordinate_longitude', 'quantity', 'time']

BASIC_CHANGE_LABELS = ['textual_change', 're_formatting', 'refinement', 'unrefinement', 'property_value_update', 'link_change', 'rewording']

REVERTED_EDIT_LABEL = 'reverted_edit'
PROPERTY_REPLACEMENT_LABEL = 'property_replacement'

SOFT_INSERTIONS = 'soft_insertions' # normal/deprecated -> preferred 
SOFT_DELETIONS = 'soft_deletions' # rank deprecation (normal/prefered -> deprecated) + adding end time qualifier

CLASSES_PER_DATATYPE = {
    'text': ['textual_change', 're_formatting', 'refinement', 'unrefinement', 'property_value_update'],
    'quantity': ['refinement', 'unrefinement', 'property_value_update', 're_formatting'],
    'time': ['refinement', 'unrefinement', 'property_value_update'],
    'globecoordinate_latitude': ['refinement', 'unrefinement', 'property_value_update'],
    'globecoordinate_longitude': ['refinement', 'unrefinement', 'property_value_update'],
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
SCRIPT_DIR = 'src/analysis/scripts'
SQL_SCRIPT_DIR = 'src/analysis/sql'
RESULTS_DIR = 'src/analysis/results'
LOGS_DIR = 'src/analysis/logs'

YAML_SETUP_PATH = 'set_up.yml'


BASE_KEY_TYPES = {
    'revision_id': 'BIGINT',
    'property_id': 'INT',
    'value_id': 'TEXT',
    'change_target': 'TEXT'
}

PROP_REP_KEY_TYPES = {
    'pair_id': 'BIGINT'
}

CLASS_DESCRIPTION = {
    'quantity': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes. It also includes sign changes. Examples: +1684527 -> +1719070, -1 -> +1",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement increases numerical precision while remaining semantically compatible with the original value. Examples: +222 -> +222.4",
        're_formatting': "a property value's representation is modified on a surface-level, without altering its underlying meaning. For quantity values, re-formatting covers changes in numerical precision that do not alter the value (e.g., adding trailing zeros). Examples: +4.0 -> +4, +98 -> +98.0",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement decreases numerical precision while remaining semantically compatible with the original value. Examples: +222.4 -> +222"
    },
    'time': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes, It also includes sign changes. Examples: -5-00-00T00:00:00Z -> +1951-09-25T00:00:00Z, +100-00-00 -> -100-00-00",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement may add more contextual information, while remaining semantically compatible with the original value. Examples: +1976-01-01T00:00:00Z -> +1976-11-22T00:00:00Z",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement may remove contextual information, while remaining semantically compatible with the original value. Examples: +839-02-04T00:00:00Z -> +839-00-00T00:00:00Z"
    },
    'entity': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes. Examples: Agnosticism (Q288928) -> Islam (Q432)",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement provides a more specific classification while remaining semantically compatible with the original value. Examples: business (Q4830453) -> automobile manufacturer (Q786820)",
        'link_change': "an entity reference is replaced by another one with a similar or identical label but representing a different concept. Examples: Queen Victoria (Q235199) -> Victoria (Q9439), historical Jesus (Q51666) -> Jesus (Q225149)",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement generalizes to a broader classification while remaining semantically compatible with the original value. Examples:  electrical engineer (Q1326886) -> engineer (Q81096)"
    },
    'text': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes. Examples: a country in North America -> a country in Central America",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement may add more contextual information or rephrase a text to convey the same meaning more clearly, while remaining semantically compatible with the original value. Examples: city -> city in South Korea",
        'textual_change': "a property value of type text is modified to correct or introduce language errors, such as spelling, typos, or grammar, without altering sentence structure or the statement's meaning.",
        're_formatting': "a property value's representation is modified on a surface-level, without altering its underlying meaning. For text values, re-formatting covers changes to visual presentation, such as spacing, capitalization, hyphenation, and other typographical elements.",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement removes contextual information, while remaining semantically compatible with the original value. Examples: 2007 thriller movie on the war in Afghanistan directed by Robert Redford -> 2007 film directed by Robert Redford"
    },
    'globecoordinate_longitude': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes. It also includes sign changes. Examples: {\"latitude\": -3.09771, \"longitude\": -226.98051} -> {\"latitude\": -2.8114, \"longitude\": 118.169}, {\"latitude\": 33.7413, \"longitude\": 151.1391} -> {\"latitude\": -33.7413,\"longitude\": 151.1391}",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement increases numerical precision, while remaining semantically compatible with the original value. Examples: {\"latitude\": 14, \"longitude\": 121.917} -> {\"latitude\":14, \"longitude\": 121.91666666667}",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement decreases numerical precision, while remaining semantically compatible with the original value. Examples: {\"latitude\": 32, \"longitude\": 35.383333333333} -> {\"latitude\": 32, \"longitude\": 35.4}"
    },
    'globecoordinate_latitude': {
        'property_value_update': "a property value is replaced with a semantically different value, altering the statement's meaning. This includes corrections of incorrect values and updates reflecting real-world changes. It also includes sign changes. Examples: {\"latitude\": -3.09771, \"longitude\": -226.98051} -> {\"latitude\": -2.8114, \"longitude\": 118.169}, {\"latitude\": 33.7413, \"longitude\": 151.1391} -> {\"latitude\": -33.7413,\"longitude\": 151.1391}",
        'refinement': "a property value is replaced by a more specific or precise value, without changing the statement's meaning. The refinement increases numerical precision, while remaining semantically compatible with the original value. Examples: {\"latitude\": 14, \"longitude\": 121.917} -> {\"latitude\":14, \"longitude\": 121.91666666667}",
        'unrefinement': "a property value is replaced by a less specific or precise value, without changing the statement's meaning. The unrefinement decreases numerical precision, while remaining semantically compatible with the original value. Examples: {\"latitude\": 32, \"longitude\": 35.383333333333} -> {\"latitude\": 32, \"longitude\": 35.4}"
    }
}