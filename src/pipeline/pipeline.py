import time
import json

from src.managers.classification_manager import ClassificationManager

class Pipeline:
    def __init__(self, config_path='config/db_config.json'):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.manager = ClassificationManager(self.config)

    def run_classification(self):
        start_time = time.time()
        print('Start running classification.')
        self.manager.run_classification()
        print(f'Finished running classification. Took: {time.time() - start_time} seconds')

    
