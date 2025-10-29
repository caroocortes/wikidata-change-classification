from abc import ABC, abstractmethod

class Classifier(ABC):
    def __init__(self, config):

        self.table_names = config['table_names']
    
    @abstractmethod
    def run_classification(self):
        pass