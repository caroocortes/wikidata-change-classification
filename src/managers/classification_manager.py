from pathlib import Path
import logging
import pandas as pd
from unidecode import unidecode
from nltk.corpus import wordnet
import time

from .sql_runner import SQLRunner
from const import LOG_DIR

log_dir = Path(LOG_DIR)
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "runtime.log"

logging.basicConfig(
    level=logging.INFO,  # change to DEBUG if you want more detail
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="a"),  # append logs
        logging.StreamHandler()                   # also print to console
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

class ClassificationManager:
    def __init__(self, config):
        self.sql_runner = SQLRunner(db_config=config['db_params'])
        self.sql_dir = Path(config['sql_dir'])
        self.table_names = config['table_names']

    def run_formatting_classification(self):
        start_time = time.time()
        sql_file = self.sql_dir / 'formatting.sql'
        logging.info('Started formatting classification')

        with open(sql_file) as f:
            formatting_query = f.read()
        
        formatting_query = formatting_query.replace(":change", self.table_names['change_table'])
        self.sql_runner.execute_query(formatting_query)
        
        total_time = time.time() - start_time
        logging.info(f'Finished formatting classification. Took {total_time} seconds')

    def classify_typo_intent(self, row):

        old_norm = unidecode(row['old_value']).lower()
        new_norm = unidecode(row['new_value']).lower()

        typo_intro = False
        typo_corr = False

        # Typo introduction -> old is valid, new is not
        if wordnet.synsets(old_norm) and not wordnet.synsets(new_norm):
            typo_intro = True

        # Typo correction -> old is not valid, new is
        if not wordnet.synsets(old_norm) and wordnet.synsets(new_norm):
            typo_corr = True

        # Both in dictionary -> Assume correction
        if (wordnet.synsets(old_norm) and wordnet.synsets(new_norm)) or (not wordnet.synsets(old_norm) and not wordnet.synsets(new_norm)):
            typo_corr = True

        return pd.Series({'typo_introduction': typo_intro, 'typo_correction': typo_corr})

    def run_typo_classification(self):
        start_time = time.time()
        logging.info('Started typo classification')
        
        sql_file = self.sql_dir / 'typo_detection.sql'
        
        with open(sql_file) as f:
            typo_query = f.read()

        typo_query = typo_query.replace(":change_metadata", self.table_names["change_metadata_table"]) \
                                .replace(":change", self.table_names['change_table']) \
                                .replace(":revision", self.table_names["revision_table"])
        
        start_time_sql = time.time()
        self.sql_runner.execute_query(typo_query)
        total_time_sql = time.time() - start_time_sql
        logging.info(f'SQL-based typo classification took: {total_time_sql} seconds')

        start_time_wordnet = time.time()
        query_typo_errors = """
            SELECT revision_id, property_id, value_id, change_target, old_value, new_value, typo, typo_correction, typo_introduction
            FROM {change_table}
            WHERE typo = TRUE AND typo_correction = FALSE AND typo_introduction = FALSE
        """.format(change_table=self.table_names['change_table'])
        df = self.sql_runner.query_to_df(query_typo_errors)

        print('Number of changes to check for typo intent:', len(df.index))

        # Do introduction/correction of typo
        df[['typo_correction', 'typo_introduction']] = df.apply(self.classify_typo_intent, axis=1)

        # Update DB
        typo_correction_values = list(df[["typo_correction", "revision_id", "property_id", "value_id", "change_target"]].itertuples(index=False, name=None))
        query = """
            UPDATE {change_table}
            SET typo_correction = %s
            WHERE revision_id = %s AND property_id = %s AND value_id = %s AND change_target = %s
        """.format(change_table=self.table_names['change_table'])
        self.sql_runner.execute_many(query, typo_correction_values)

        # Update DB
        typo_introduction_values = list(df[["typo_introduction", "revision_id", "property_id", "value_id", "change_target"]].itertuples(index=False, name=None))
        query = """
            UPDATE {change_table}
            SET typo_introduction = %s
            WHERE revision_id = %s AND property_id = %s AND value_id = %s AND change_target = %s
        """.format(change_table=self.table_names['change_table'])
        self.sql_runner.execute_many(query, typo_introduction_values)

        total_time_wordnet = time.time() - start_time_wordnet
        logging.info(f'Wordnet-based typo classification took: {total_time_wordnet} seconds')

        total_time = time.time() - start_time
        logging.info(f'Finished typo classification. Took {total_time} seconds')
        

    def run_value_refinement_classification(self):
        start_time = time.time()
        logging.info('Started value refinement classification')

        sql_file = self.sql_dir / 'value_refinement.sql'
        
        with open(sql_file) as f:
            value_refinement_query = f.read()
        
        value_refinement_query = value_refinement_query.replace(":change", self.table_names['change_table'])
        self.sql_runner.execute_query(value_refinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished value refinement classification. Took {total_time} seconds')

    def run_classification(self):
        # self.run_formatting_classification()
        self.run_typo_classification()
        self.run_value_refinement_classification()
