"""
Data loading and management module.

This module handles:
- Loading gold standard datasets
- Database table management
"""

import logging
from pathlib import Path
import json

from src.database.sql_runner import SQLRunner
from src.utils.utils import copy_from_csv, update_column_types

class DataLoader:
    """
    Handles loading and preprocessing of datasets.
    
    This class manages:
    - Gold standard datasets (for evaluation)
    - Training datasets (for ML)
    - Database table creation and population
    """
    
    def __init__(self, db_config_path: str):
        """
        Initialize the data loader.
        
        Args:
            db_config_path: Path to database configuration file
        """
        with open(db_config_path, 'r') as f:
            db_config = json.load(f)

        self.sql_runner = SQLRunner(db_config=db_config['db_params'])
        self.logger = logging.getLogger(__name__)
        
        self.gold_standard_dir = Path('gold_standard')
    
    def load_gold_standard(self):
        """
        Load gold standard datasets into the database.
        
        This loads three main datasets:
        1. gold_standard.csv - Basic labels dataset
        2. reverted_edit.csv - Reverted edits dataset
        3. property_replacement.csv - Property replacement dataset
        """

        datasets = [
            {
                'name': 'gold_standard',
                'file': self.gold_standard_dir / 'gold_standard.csv',
                'columns': [
                    "revision_id","entity_id","entity_label","value_id","change_target","property_id",
                    "property_label","old_value","old_value_label","new_value","new_value_label","datatype",
                    "action","target","instance_of_main_entity",
                    "latest_description","new_value_description","old_value_description","label","subclass_of_main_entity"
                ],
                'primary_keys': ['revision_id', 'property_id', 'value_id', 'change_target']
            },
            {
                'name': 'reverted_edit',
                'file': self.gold_standard_dir / 'reverted_edit.csv',
                'columns': [
                    "anchor_revision_id","revision_id","entity_id","entity_label","value_id","property_id",
                    "change_target","property_label","old_value","old_value_label","new_value","new_value_label",
                    "datatype","new_hash","old_hash","revision_rank","timestamp","comment","label","username","user_id","action"
                ],
                'primary_keys': ['revision_id', 'property_id', 'value_id', 'change_target']
            },
            {
                'name': 'property_replacement',
                'file': self.gold_standard_dir / 'property_replacement.csv',
                'columns': [
                    "pair_id","revision_id","entity_id","entity_label",
                    "value_id","property_id","change_target","property_label",
                    "old_value","old_value_label","new_value","new_value_label","datatype",
                    "action","target","comment","timestamp","label","username"
                ],
                'primary_keys': ['revision_id', 'property_id', 'value_id', 'change_target']
            }
        ]
        
        # Load each dataset
        table_existence = {}
        for dataset in datasets:
            self.logger.info(f"Loading {dataset['name']}")
            
            exists = copy_from_csv(
                conn=self.sql_runner.conn,
                csv_path=str(dataset['file']),
                table_name=dataset['name'],
                columns=dataset['columns'],
                primary_keys=dataset['primary_keys']
            )
            
            table_existence[dataset['name']] = exists
            
            if exists:
                self.logger.info(f"{dataset['name']} loaded successfully")
            else:
                self.logger.warning(f"{dataset['name']} already exists, skipped")
        
        # update column types
        update_column_types(self.classifier.sql_runner.conn, table_existence=table_existence)
    
    
    def drop_predicted_columns(self, table_name: str):
        """
        Drop all predicted columns from a table.
        
        This is useful for re-running classification from scratch.
        
        Args:
            table_name: Name of the table to clean
        """
        self.logger.info(f"Dropping predicted columns from {table_name}...")
        
        # Get all columns ending with '_predicted'
        query = f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}' 
            AND column_name LIKE '%_predicted'
        """
        
        results = self.sql_runner.execute_query(query, fetch=True)
        
        if not results:
            self.logger.info("No predicted columns found")
            return
        
        # Drop each predicted column
        for row in results:
            col_name = row[0]
            drop_query = f"ALTER TABLE {table_name} DROP COLUMN IF EXISTS {col_name}"
            self.sql_runner.execute_query(drop_query)
            self.logger.debug(f"Dropped column: {col_name}")
        
        self.logger.info(f"Dropped {len(results)} predicted columns")
    
    def __del__(self):
        self.sql_runner.close()
