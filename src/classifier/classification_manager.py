import time
import json

from .sql_classifier import SQLClassifier
from .ml_classifier import MLClassifier
from ..utils import copy_from_csv, update_column_types

class ClassificationManager:

    def __init__(self, classification_type, config_path='config/db_config.json'):
        with open(config_path, "r") as f:
            self.config = json.load(f)
        self.table_names = self.config['table_names']
        self.classification_type = classification_type
        if classification_type == 'SQL':
            self.classifier = SQLClassifier(self.config)
        else:
            self.classifier = MLClassifier(self.config)
            
        self.classifier.table_names = self.table_names

        self.load_gold_standard()

    def load_gold_standard(self):
        start_time = time.time()
        print(f'Start loading gold standard for classification.')
        
        exists_gs = copy_from_csv(self.classifier.sql_runner.conn, 'gold_standard/gold_standard.csv', 'gold_standard', ['revision_id','entity_id','entity_label','value_id','property_id','change_target','property_label','old_value','old_value_label','new_value','new_value_label','label','datatype', 'action', 'target'], ['revision_id', 'property_id', 'value_id', 'change_target'])
        exists_rve = copy_from_csv(self.classifier.sql_runner.conn, 'gold_standard/reverted_edit.csv', 'reverted_edit', ["anchor_revision_id","revision_id","entity_id","entity_label","value_id","property_id","change_target","property_label","old_value","old_value_label","new_value","new_value_label","datatype","new_hash","old_hash","revision_rank","timestamp","comment","label"], ['revision_id', 'property_id', 'value_id', 'change_target'])
        exists_pr = copy_from_csv(self.classifier.sql_runner.conn, 'gold_standard/property_replacement.csv', 'property_replacement', ["revision_id","entity_id","entity_label","value_id","property_id","change_target","property_label","old_value","old_value_label","new_value","new_value_label","datatype","action","target","comment","timestamp","label"], ['revision_id', 'property_id', 'value_id', 'change_target'])
        
        table_existence = {
            'gold_standard': exists_gs,
            'reverted_edit': exists_rve,
            'property_replacement': exists_pr
        }
        update_column_types(self.classifier.sql_runner.conn, table_existence=table_existence)
        print(f'Finished loading gold standard for classification. Took: {time.time() - start_time} seconds')

    def run_classifier(self):
        start_time = time.time()
        print(f'Start running {self.classification_type} classification.')
        self.classifier.run_classification()
        print(f'Finished running {self.classification_type} classification. Took: {time.time() - start_time} seconds')

    def evaluate_on_gold_standard(self):
        start_time = time.time()
        print(f'Start evaluating {self.classification_type} classifier on gold standard.')
        self.classifier.evaluate_on_gold_standard()
        print(f'Finished evaluating {self.classification_type} classifier on gold standard. Took: {time.time() - start_time} seconds')

    def calculate_evaluation_metrics(self):
        self.classifier.calculate_evaluation_metrics()

    def train_classifier(self):
        start_time = time.time()
        print(f'Start training {self.classification_type} classifier.')
        if self.classification_type == 'ML':
            self.classifier.train_classifier()
        else:
            print('SQL classifier does not require training.')
        print(f'Finished training {self.classification_type} classifier. Took: {time.time() - start_time} seconds')