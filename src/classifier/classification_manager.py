import time
import json

from src.classifier.sql_classifier import SQLClassifier
from src.classifier.ml_classifier import MLClassifier

class ClassificationManager:

    def __init__(self, classification_type, config_path='config/db_config.json'):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.classification_type = classification_type
        if classification_type == 'SQL':
            self.classifier = SQLClassifier(self.config)
        else:
            self.classifier = MLClassifier(self.config)

    def run_classifier(self):
        start_time = time.time()
        print(f'Start running {self.classification_type} classification.')
        self.classifier.run_classification()
        print(f'Finished running {self.classification_type} classification. Took: {time.time() - start_time} seconds')