from pathlib import Path
import logging
import time
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, classification_report, confusion_matrix
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer

from .classifier import Classifier
from ..const import LOG_DIR, BASIC_CHANGE_LABELS, REVERTED_EDIT_LABEL, PROPERTY_REPLACEMENT_LABEL
from ..utils import drop_predicted_columns

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

    """
        Runs SQL classifier on the changes' table.
        Uses SQL queries defined in the `sql/baseline_classification/` directory.
        For evaluation on gold standard, it uses the gold_standard, reverted_edit and property_replacement tables (see gold_standard/ directory).
        The parameter evaluation_gs is used to sepcify that the classification is done on the gold standard. If not, some filters apply (e.g. not reverted_edit) 
    """

    def __init__(self, config):
        super().__init__(config)
        self.sql_dir = Path(config['sql_dir'])


    def run_re_formatting_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()
        sql_file = self.sql_dir / 're_formatting.sql'

        with open(sql_file) as f:
            formatting_query = f.read()
        print('Started re-formatting classification.')
        formatting_query = formatting_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            formatting_query = formatting_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            formatting_query = formatting_query.replace("<additional_filters>", "")
        
        self.sql_runner.execute_query(formatting_query)
        
        total_time = time.time() - start_time
        logging.info(f'Finished re-formatting classification. Took {total_time} seconds.')

    def run_textual_change_classification(self, table_name=None, evaluation_gs=False):
        
        sql_file = self.sql_dir / 'textual_change.sql'
        
        with open(sql_file) as f:
            textual_change_query = f.read()
        print('Started textual change classification.')
        textual_change_query = textual_change_query.replace("<change_metadata>", self.table_names["change_metadata_table"]) \
                                .replace("<change>", table_name if table_name else self.table_names['change_table']) \
                                .replace("<revision>", self.table_names["revision_table"])
        
        if not evaluation_gs:
            textual_change_query = textual_change_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            textual_change_query = textual_change_query.replace("<additional_filters>", "")

        start_time = time.time()
        self.sql_runner.execute_query(textual_change_query)
        total_time = time.time() - start_time

        logging.info(f'Finished textual change classification. Took {total_time} seconds.')

    def run_reverted_edit_classification(self, table_name=None, create_mat_view=True):
        
        sql_file = self.sql_dir / 'revert_edits.sql'

        mat_view_sql_file = self.sql_dir / 'materialized_view.sql'
        
        with open(mat_view_sql_file) as f:
            mat_view_query = f.read()

        if create_mat_view:
            mat_view_query = mat_view_query.replace("<change_timestamp_entity>", self.table_names['materialized_view']) \
                                            .replace("<change>", self.table_names['change_table']) 
                                    
            logging.info('Creating materialized view for reverted edit classification.')
            start_time = time.time()
            self.sql_runner.execute_query(mat_view_query)
            total_time = time.time() - start_time
            logging.info(f'Created materialized view for reverted edit classification. Took {total_time} seconds.')

            logging.info('Creating indexes')

            indexes_query ="""
                -- Index for hash lookups
                CREATE INDEX IF NOT EXISTS idx_cte_hashes_old_not_null
                ON change_timestamp_entity (old_hash, new_hash) 
                WHERE old_hash IS NOT NULL;

                CREATE INDEX IF NOT EXISTS idx_cte_hashes_old_null
                ON change_timestamp_entity (old_hash, new_hash) 
                WHERE old_hash IS NULL;

                -- Index for comment searches
                CREATE INDEX IF NOT EXISTS idx_cte_comment 
                ON change_timestamp_entity (comment) 
                WHERE comment ILIKE ANY(ARRAY['%rvv%', 'rv v', '%vandal%', '%revert%', '%restore%']);

            """
            self.sql_runner.execute_query(indexes_query)
            logging.info('Indexes created for reverted edit classification.')

        with open(sql_file) as f:
            revert_edit_query = f.read()

        revert_edit_query = revert_edit_query.replace("<change_timestamp_entity>", table_name if not create_mat_view else self.table_names['materialized_view']) \
                                            .replace("<change>", table_name if table_name else self.table_names['change_table'])     
        
        logging.info('Started reverted edit classification.')
        start_time = time.time()
        self.sql_runner.execute_query(revert_edit_query)
        total_time = time.time() - start_time

        logging.info(f'Finished reverted edit classification. Took {total_time} seconds.')

    def run_value_refinement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_refinement.sql'
        
        with open(sql_file) as f:
            value_refinement_query = f.read()
        logging.info('Started value refinement classification.')
        value_refinement_query = value_refinement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            value_refinement_query = value_refinement_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            value_refinement_query = value_refinement_query.replace("<additional_filters>", "")
        self.sql_runner.execute_query(value_refinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished value refinement classification. Took {total_time} seconds.')

    def run_value_unrefinement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_unrefinement.sql'
        
        with open(sql_file) as f:
            value_unrefinement_query = f.read()
        logging.info('Started value unrefinement classification.')
        value_unrefinement_query = value_unrefinement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            value_unrefinement_query = value_unrefinement_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            value_unrefinement_query = value_unrefinement_query.replace("<additional_filters>", "")
        
        self.sql_runner.execute_query(value_unrefinement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished value unrefinement classification. Took {total_time} seconds.')

    def run_rank_deprecation_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'rank_deprecation.sql'
        
        with open(sql_file) as f:
            rank_deprecation_query = f.read()
        logging.info('Started rank deprecation classification.')
        rank_deprecation_query = rank_deprecation_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            rank_deprecation_query = rank_deprecation_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            rank_deprecation_query = rank_deprecation_query.replace("<additional_filters>", "")
        self.sql_runner.execute_query(rank_deprecation_query)

        total_time = time.time() - start_time
        logging.info(f'Finished rank deprecation classification. Took {total_time} seconds.')

    def run_link_change_classification(self, table_name=None, evaluation_gs=False):
        
        start_time = time.time()

        sql_file = self.sql_dir / 'link_change.sql'
        
        with open(sql_file) as f:
            link_change_query = f.read()
        logging.info('Started link change classification.')
        link_change_query = link_change_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            link_change_query = link_change_query.replace("<additional_filters>", "AND reverted_edit_predicted = FALSE AND reversion_predicted = FALSE")
        else:
            link_change_query = link_change_query.replace("<additional_filters>", "")

        self.sql_runner.execute_query(link_change_query)

        total_time = time.time() - start_time
        logging.info(f'Finished link change classification. Took {total_time} seconds.')

    def run_rewording_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'rewording.sql'
        
        with open(sql_file) as f:
            rewording_query = f.read()
        logging.info('Started rewording classification.')
        rewording_query = rewording_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            rewording_query = rewording_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            rewording_query = rewording_query.replace("<additional_filters>", "")
        
        self.sql_runner.execute_query(rewording_query)

        total_time = time.time() - start_time
        logging.info(f'Finished rewording classification. Took {total_time} seconds.')

    def run_property_replacement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'property_replacement.sql'
        
        with open(sql_file) as f:
            property_replacement_query = f.read()
        logging.info('Started property replacement classification.')
    
        property_replacement_query = property_replacement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])\
                                                                .replace("<change_timestamp_entity>", table_name if table_name else self.table_names['materialized_view'])
        
        if not evaluation_gs:
            property_replacement_query = property_replacement_query.replace("<additional_filters>", "AND reverted_edit_predicted = FALSE AND reversion_predicted = FALSE")
        else:
            property_replacement_query = property_replacement_query.replace("<additional_filters>", "")

        self.sql_runner.execute_query(property_replacement_query)

        total_time = time.time() - start_time
        logging.info(f'Finished property replacement classification. Took {total_time} seconds.')

    def run_property_value_update_classification(self, table_name=None, evaluation_gs=False):
        

        sql_file = self.sql_dir / 'property_value_update.sql'
        
        with open(sql_file) as f:
            property_value_update_query = f.read()

        property_value_update_query = property_value_update_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            property_value_update_query = property_value_update_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted OR textual_change_predicted OR re_formatting_predicted OR link_change_predicted OR rank_deprecation_predicted OR value_refinement_predicted OR value_unrefinement_predicted OR property_replacement_predicted OR rewording_predicted)")
        else:
            property_value_update_query = property_value_update_query.replace("<additional_filters>", "")

        logging.info('Started property value update classification.')
        start_time = time.time()
        self.sql_runner.execute_query(property_value_update_query)
        total_time = time.time() - start_time
        logging.info(f'Finished property value update classification. Took {total_time} seconds.')

    def run_classification(self):
        """
            Runs classification on the DB.
        """

        # query = f"""
        #     DROP MATERIALIZED VIEW IF EXISTS change_timestamp_entity;
        # """
        # res = self.sql_runner.execute_query(query)

        # num_changes_query = f"""
        #     SELECT count(*)
        #     from {self.table_names['change_table']}
        # """
        # num_changes = self.sql_runner.execute_query(num_changes_query)
        # num_changes = num_changes[0][0] if num_changes else 0

        # num_revisions_query = f"""
        #     SELECT count(*)
        #     from {self.table_names['revision_table']}
        # """
        # num_revisions = self.sql_runner.execute_query(num_revisions_query)
        # num_revisions = num_revisions[0][0] if num_revisions else 0

        # num_files_query = f"""
        #     SELECT count(DISTINCT file_path)
        #     from {self.table_names['revision_table']}
        # """
        # num_files = self.sql_runner.execute_query(num_files_query)
        # num_files = num_files[0][0] if num_files else 0

        # num_entities_query = f"""
        #     SELECT count(DISTINCT entity_id)
        #     from {self.table_names['revision_table']}
        # """
        # num_entities = self.sql_runner.execute_query(num_entities_query)
        # num_entities = num_entities[0][0] if num_entities else 0

        # logging.info(f'Running change classification: {num_changes:,} changes, {num_revisions:,} revisions, {num_files:,} files, {num_entities:,} entities.')

        self.run_reverted_edit_classification()
        self.run_re_formatting_classification()
        self.run_textual_change_classification()
        self.run_value_refinement_classification()
        self.run_value_unrefinement_classification()
        self.run_sign_classification()
        self.run_rank_deprecation_classification()
        self.run_link_change_classification()
        self.run_property_replacement_classification()
        self.run_property_value_update_classification()

    def evaluate_on_gold_standard(self):
        """ 
            Evaluates SQL baseline on gold standard tables
        """

        drop_predicted_columns(self.sql_runner.conn)

        # Reverted edit
        self.run_reverted_edit_classification(table_name='reverted_edit', create_mat_view=False)

        # Formatting
        self.run_re_formatting_classification(table_name='gold_standard', evaluation_gs=True)

        # Typo 
        self.run_textual_change_classification(table_name='gold_standard', evaluation_gs=True)

        # Value refinement
        self.run_value_refinement_classification(table_name='gold_standard', evaluation_gs=True)

        # Value unrefinement
        self.run_value_unrefinement_classification(table_name='gold_standard', evaluation_gs=True)

        # Rank deprecation
        self.run_rank_deprecation_classification(table_name='gold_standard', evaluation_gs=True)

        # Link change
        self.run_link_change_classification(table_name='gold_standard', evaluation_gs=True)
        
        # Rewording
        self.run_rewording_classification(table_name='gold_standard', evaluation_gs=True)

        # Property replacement
        self.run_property_replacement_classification(table_name='property_replacement', evaluation_gs=True)

        self.run_property_value_update_classification(table_name='gold_standard', evaluation_gs=True)

    def calculate_evaluation_metrics(self):
        """
            Calculates evaluation metrics based on the predictions made on the gold standard tables.
        """

        ## BASIC CLASSIFICATION

        predicted_label_cols = []

        for label in BASIC_CHANGE_LABELS:
            predicted_label_cols.append(f"{label}_predicted")

        predicted_label_cols = ','.join(predicted_label_cols)

        query = f"""
        SELECT 
            revision_id, 
            property_id, 
            value_id,
            change_target,
            property_label,
            new_value,
            new_value_label,
            old_value,
            old_value_label,
            label,
            {predicted_label_cols}
        FROM gold_standard
        """

        df = self.sql_runner.query_to_df(query)
        
        # split label column + generate binary columns per label
        df['labels_list'] = df['label'].str.split(',')
        
        # set index for combine later
        id_cols = ['revision_id', 'property_id', 'value_id', 'change_target']
        df = df.set_index(id_cols)
        
        # binary columns per label
        mlb = MultiLabelBinarizer()
        binary_labels = mlb.fit_transform(df['labels_list'])

        binary_df = pd.DataFrame(binary_labels, columns=mlb.classes_, index=df.index)

        # combine binary columns with original df, they match on the index (key of the changes)
        result = pd.concat([df, binary_df], axis=1)

        result.to_csv('experiments/gs_predicted_true.csv')

        for label in BASIC_CHANGE_LABELS:
            # for the changes with more than one tag, if the baseline is correct it will go to each class
            y_true = result[label]
            y_pred = result[f"{label}_predicted"].astype(int)

            accuracy = accuracy_score(y_true, y_pred)
            precision = precision_score(y_true, y_pred, average='macro', zero_division=0)
            recall = recall_score(y_true, y_pred, average='macro', zero_division=0)
            f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)

            print(f'Metrics for label: {label}')
            print(f'  Accuracy: {accuracy:.4f}')
            print(f'  Precision: {precision:.4f}')
            print(f'  Recall: {recall:.4f}')
            print(f'  F1-Score: {f1:.4f}')
            print()
    
        ## REVERTED EDIT

        predicted_label_col = f"{REVERTED_EDIT_LABEL}_predicted"
        
        query = f"""
        SELECT 
            revision_id, 
            property_id, 
            value_id,
            change_target,
            property_label,
            new_value,
            new_value_label,
            old_value,
            old_value_label,
            label,
            {predicted_label_col}
        FROM reverted_edit
        """

        df = self.sql_runner.query_to_df(query)

        df['new_label'] = (df['label'] == REVERTED_EDIT_LABEL).astype(int)
        y_true = df['new_label']
        y_pred = df[f"{predicted_label_col}"].astype(int)

        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average='macro', zero_division=0)
        recall = recall_score(y_true, y_pred, average='macro', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)

        print(f'Metrics for label: {predicted_label_col}')
        print(f'  Accuracy: {accuracy:.4f}')
        print(f'  Precision: {precision:.4f}')
        print(f'  Recall: {recall:.4f}')
        print(f'  F1-Score: {f1:.4f}')

        ## PROPERTY REPLACEMENT

        predicted_label_col = f"{PROPERTY_REPLACEMENT_LABEL}_predicted"
        
        query = f"""
        SELECT 
            revision_id, 
            property_id, 
            value_id,
            change_target,
            property_label,
            new_value,
            new_value_label,
            old_value,
            old_value_label,
            label,
            {predicted_label_col}
        FROM property_replacement
        """

        df = self.sql_runner.query_to_df(query)

        df['new_label'] = (df['label'] == PROPERTY_REPLACEMENT_LABEL).astype(int)
        y_true = df['new_label']
        y_pred = df[f"{predicted_label_col}"].astype(int)

        accuracy = accuracy_score(y_true, y_pred)
        precision = precision_score(y_true, y_pred, average='macro', zero_division=0)
        recall = recall_score(y_true, y_pred, average='macro', zero_division=0)
        f1 = f1_score(y_true, y_pred, average='macro', zero_division=0)

        print(f'Metrics for label: {predicted_label_col}')
        print(f'  Accuracy: {accuracy:.4f}')
        print(f'  Precision: {precision:.4f}')
        print(f'  Recall: {recall:.4f}')
        print(f'  F1-Score: {f1:.4f}')
