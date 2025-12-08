from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List

WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']

###########################
#  PARAMS FOR DATA LOADER  #
###########################
SQL_UNTAGGED = True # doesn't consider changes tagged by SQL rules
ONLY_UPDATES = True
NO_RANK = True

###########################
#  PARAMS FOR CLUSTERING  #
###########################
CHANGE_TARGET = 'value'  # 'value' or 'datatype_metaddata'
ACTION = 'UPDATE'  # 'UPDATE' for now

# List of datatypes to cluster
DATATYPES_TO_CLUSTER = ['quantity', 'time', 'globecoordinate'] 
# DATATYPES_TO_CLUSTER = ['string','entity'] 
# DATATYPES_TO_CLUSTER = ['quantity', 'time', 'globecoordinate','string','entity'] 

@dataclass
class Config:
    """Configuration class"""
    root_dir = Path(__file__).resolve().parent.parent
    cluster_dir = Path(__file__).resolve().parent 
    data_dir: Path = Path('data')

    sql_untagged: bool = SQL_UNTAGGED
    only_updates: bool = ONLY_UPDATES
    no_rank: bool = NO_RANK

    # Change filtering
    change_target: str = CHANGE_TARGET
    action: str = ACTION

    # Clustering settings
    n_clusters: int = 0
    random_state: int = 42
    n_init: int = 3
    max_iter: int = 300
    
    # Dynamic properties set per datatype
    datatype: Optional[str] = None
    data_path: Optional[Path] = None
    features_path: Optional[Path] = None
    
    def set_datatype(self, datatype: str):
        """Configure paths for a specific datatype"""
        self.datatype = datatype
        self.data_path = self.data_dir / f'changes_for_clustering_{datatype}_{self.action.lower()}.parquet'
        self.features_path = None  # or set the specific path