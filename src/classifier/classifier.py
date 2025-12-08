from abc import ABC, abstractmethod
from ..sql.sql_runner import SQLRunner

class Classifier(ABC):
    def __init__(self, config):
        self.sql_runner = SQLRunner(db_config=config['db_params'])
        self.table_names = config['table_names']
    
    @abstractmethod
    def run_classification(self):
        pass