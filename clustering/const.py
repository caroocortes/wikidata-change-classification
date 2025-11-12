
from pathlib import Path
from dataclasses import dataclass

WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']

###########################
#  PARAMS FOR DATA LOADER  #
###########################
SQL_UNTAGGED = True
ONLY_UPDATES = True
NO_RANK = True
DATATYPE = 'string' # 'string', 'quantity', 'time', 'entity', 'globecoordinate'.
DATA_FILE_PATH = f'changes_for_clustering_{DATATYPE}_updates.parquet'

###########################
#  PARAMS FOR CLUSTERING  #
###########################
# FEATURES_FILE_PATH = 'string_change_features.parquet'
FEATURES_FILE_PATH = 'string_features.parquet'  # Precomputed features file path. If None, features will be computed from raw data.
CHANGE_TARGET = 'value'  # 'value' or 'datatype_metaddata'
ACTION = 'UPDATE'  # 'UPDATE' for now

@dataclass
class Config:
    """Configuration class"""
    root_dir = Path(__file__).resolve().parent.parent
    cluster_dir = Path(__file__).resolve().parent 
    data_dir: Path = root_dir / 'data'

    sql_untagged: bool = SQL_UNTAGGED
    only_updates: bool = ONLY_UPDATES
    no_rank: bool = NO_RANK

    # Data paths
    data_path: Path = data_dir / DATA_FILE_PATH
    if FEATURES_FILE_PATH:
        features_path: Path = cluster_dir / 'data' / FEATURES_FILE_PATH
    else:
        features_path: Path = None

    # Change filtering
    change_target: str = CHANGE_TARGET
    datatype: str = DATATYPE
    action: str = ACTION

    # Clustering settings
    n_clusters: int = 8
    random_state: int = 42
    n_init : int = 3
    max_iter : int = 300
    
