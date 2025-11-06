from pathlib import Path
import logging
import time

from ..sql.sql_runner import SQLRunner
from .classifier import Classifier
from const import LOG_DIR

log_dir = Path(LOG_DIR)
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "runtime.log"

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="a"), 
        logging.StreamHandler()                 
    ]
)

def log_runtime(func):
    """Decorator to log runtime of functions."""
    def wrapper(*args, **kwargs):
        start = time.time()
        logging.info(f"Started {func.__name__}")
        result = func(*args, **kwargs)
        end = time.time()
        logging.info(f"Finished {func.__name__} in {end - start:.2f} seconds")
        return result
    return wrapper

class SQLClassifier(Classifier):
    def __init__(self, config):
        self.sql_runner = SQLRunner(db_config=config['db_params'])
        self.sql_dir = Path(config['sql_dir'])

    def run_formatting_classification(self):
        start_time = time.time()
        sql_file = self.sql_dir / 'formatting.sql'

        with open(sql_file) as f:
            formatting_query = f.read()
        
        formatting_query = formatting_query.replace(":change", self.table_names['change_table'])
        affected_rows = self.sql_runner.execute_query(formatting_query)
        
        total_time = time.time() - start_time
        logging.info(f'Finished formatting classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def run_typo_classification(self):
        
        
        sql_file = self.sql_dir / 'typo_detection.sql'
        
        with open(sql_file) as f:
            typo_query = f.read()

        typo_query = typo_query.replace(":change_metadata", self.table_names["change_metadata_table"]) \
                                .replace(":change", self.table_names['change_table']) \
                                .replace(":revision", self.table_names["revision_table"])
        
        start_time = time.time()
        affected_rows = self.sql_runner.execute_query(typo_query)
        total_time = time.time() - start_time

        logging.info(f'Finished typo classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def run_reverted_edit_classification(self):
        
        
        sql_file = self.sql_dir / 'revert_edits.sql'
        
        with open(sql_file) as f:
            revert_edit_query = f.read()

        revert_edit_query = revert_edit_query.replace(":change", self.table_names['change_table']) \
                                .replace(":revision", self.table_names["revision_table"])
        
        start_time = time.time()
        affected_rows = self.sql_runner.execute_query(revert_edit_query)
        total_time = time.time() - start_time

        logging.info(f'Finished reverted edit classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def run_value_refinement_classification(self):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_refinement.sql'
        
        with open(sql_file) as f:
            value_refinement_query = f.read()
        
        value_refinement_query = value_refinement_query.replace(":change", self.table_names['change_table'])
        affected_rows = self.sql_runner.execute_query(value_refinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished value refinement classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def run_value_unrefinement_classification(self):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_unrefinement.sql'
        
        with open(sql_file) as f:
            value_unrefinement_query = f.read()
        
        value_unrefinement_query = value_unrefinement_query.replace(":change", self.table_names['change_table'])
        affected_rows = self.sql_runner.execute_query(value_unrefinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished value unrefinement classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def run_sign_precision_classification(self):
        start_time = time.time()

        sql_file = self.sql_dir / 'sign_precision_changes.sql'
        
        with open(sql_file) as f:
            sign_precision_query = f.read()
        
        sign_precision_query = sign_precision_query.replace(":change", self.table_names['change_table'])
        affected_rows = self.sql_runner.execute_query(sign_precision_query)

        total_time = time.time() - start_time
        logging.info(f'Finished sign precision classification. Took {total_time} seconds. Affected {affected_rows:,} rows')

    def link_fix_classification(self):
        start_time = time.time()

        sql_file = self.sql_dir / 'link_fix.sql'
        
        with open(sql_file) as f:
            value_unrefinement_query = f.read()
        
        value_unrefinement_query = value_unrefinement_query.replace(":change", self.table_names['change_table'])
        self.sql_runner.execute_query(value_unrefinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished link fix classification. Took {total_time} seconds.')


    def run_property_replacement_classification(self):
        start_time = time.time()

        sql_file = self.sql_dir / 'property_replacement.sql'
        
        with open(sql_file) as f:
            property_replacement_query = f.read()
        
        property_replacement_query = property_replacement_query.replace(":change", self.table_names['change_table'])
        affected_rows = self.sql_runner.execute_query(property_replacement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished property replacement classification. Took {total_time} seconds. Affected {affected_rows:,} rows')


    def run_classification(self):

        query = f"""
            DROP MATERIALIZED VIEW IF EXISTS change_timestamp_entity;

            ALTER TABLE {self.table_names['change_table']}
            DROP COLUMN IF EXISTS typo, DROP COLUMN IF EXISTS formatting, DROP COLUMN IF EXISTS value_refinement, DROP COLUMN IF EXISTS value_unrefinement, DROP COLUMN IF EXISTS reverted_edit, DROP COLUMN IF EXISTS reversion;
        """
        res = self.sql_runner.execute_query(query)

        num_changes_query = f"""
            SELECT count(*)
            from {self.table_names['change_table']}
        """
        num_changes = self.sql_runner.execute_query(num_changes_query)
        num_changes = num_changes[0][0] if num_changes else 0

        num_revisions_query = f"""
            SELECT count(*)
            from {self.table_names['revision_table']}
        """
        num_revisions = self.sql_runner.execute_query(num_revisions_query)
        num_revisions = num_revisions[0][0] if num_revisions else 0

        num_files_query = f"""
            SELECT count(DISTINCT file_path)
            from {self.table_names['revision_table']}
        """
        num_files = self.sql_runner.execute_query(num_files_query)
        num_files = num_files[0][0] if num_files else 0

        num_entities_query = f"""
            SELECT count(DISTINCT entity_id)
            from {self.table_names['revision_table']}
        """
        num_entities = self.sql_runner.execute_query(num_entities_query)
        num_entities = num_entities[0][0] if num_entities else 0

        logging.info(f'Running change classification: {num_changes:,} changes, {num_revisions:,} revisions, {num_files:,} files, {num_entities:,} entities.')

        self.run_reverted_edit_classification()
        self.run_formatting_classification()
        self.run_typo_classification()
        self.run_value_refinement_classification()
        self.run_value_unrefinement_classification()
        self.run_sign_precision_classification()
        self.link_fix_classification()
        self.run_property_replacement_classification()
