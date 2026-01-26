from pathlib import Path
import logging
import time
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import pandas as pd
from sklearn.preprocessing import MultiLabelBinarizer
import json

from src.database.sql_runner import SQLRunner
from src.classifiers.base_classifier import BaseClassifier
from src.utils.const import BASIC_CHANGE_LABELS, REVERTED_EDIT_LABEL, PROPERTY_REPLACEMENT_LABEL, WD_BASIC_TYPES, WD_ENTITY_TYPES, WD_STRING_TYPES
from src.utils.utils import drop_predicted_columns

class BaselineClassifier(BaseClassifier):

    """
        Runs SQL classifier on the changes' table.
        Uses SQL queries defined in the `baseline/rules/` directory.
        For evaluation on gold standard, it uses the gold_standard, reverted_edit and property_replacement tables (see gold_standard/ directory).
        The parameter evaluation_gs is used to sepcify that the classification is done on the gold standard.
    """

    def __init__(self, config_path:str, classifier_type: str = "baseline", db_config_path: str = None):
        super().__init__(config_path=config_path, classifier_type=classifier_type)
        
        self.table_names = self.config['table_names']
        self.sql_dir = Path(self.config['sql_dir'])
        
        with open(db_config_path, "r") as f:
            self.db_config = json.load(f)

        self.sql_runner = SQLRunner(db_config=self.db_config['db_params'])

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
        self.logger.info(f'Finished re-formatting classification. Took {total_time} seconds.')

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

        self.logger.info(f'Finished textual change classification. Took {total_time} seconds.')

    def run_reverted_edit_classification(self, table_name=None, create_mat_view=True):
        
        sql_file = self.sql_dir / 'revert_edits.sql'

        mat_view_sql_file = self.sql_dir / 'materialized_view.sql'
        
        with open(mat_view_sql_file) as f:
            mat_view_query = f.read()

        if create_mat_view:
            mat_view_query = mat_view_query.replace("<change_timestamp_entity>", self.table_names['materialized_view']) \
                                            .replace("<change>", self.table_names['change_table']) 
                                    
            self.logger.info('Creating materialized view for reverted edit classification.')
            start_time = time.time()
            self.sql_runner.execute_query(mat_view_query)
            total_time = time.time() - start_time
            self.logger.info(f'Created materialized view for reverted edit classification. Took {total_time} seconds.')

            self.logger.info('Creating indexes')

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
            self.logger.info('Indexes created for reverted edit classification.')

        with open(sql_file) as f:
            revert_edit_query = f.read()

        revert_edit_query = revert_edit_query.replace("<change_timestamp_entity>", table_name if not create_mat_view else self.table_names['materialized_view']) \
                                            .replace("<change>", table_name if table_name else self.table_names['change_table'])     
        
        self.logger.info('Started reverted edit classification.')
        start_time = time.time()
        self.sql_runner.execute_query(revert_edit_query)
        total_time = time.time() - start_time

        self.logger.info(f'Finished reverted edit classification. Took {total_time} seconds.')

    def run_value_refinement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_refinement.sql'
        
        with open(sql_file) as f:
            value_refinement_query = f.read()
        self.logger.info('Started value refinement classification.')
        value_refinement_query = value_refinement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            value_refinement_query = value_refinement_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            value_refinement_query = value_refinement_query.replace("<additional_filters>", "")
        self.sql_runner.execute_query(value_refinement_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished value refinement classification. Took {total_time} seconds.')

    def run_value_unrefinement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'value_unrefinement.sql'
        
        with open(sql_file) as f:
            value_unrefinement_query = f.read()
        self.logger.info('Started value unrefinement classification.')
        value_unrefinement_query = value_unrefinement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            value_unrefinement_query = value_unrefinement_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            value_unrefinement_query = value_unrefinement_query.replace("<additional_filters>", "")
        
        self.sql_runner.execute_query(value_unrefinement_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished value unrefinement classification. Took {total_time} seconds.')

    def run_rank_deprecation_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'rank_deprecation.sql'
        
        with open(sql_file) as f:
            rank_deprecation_query = f.read()
        self.logger.info('Started rank deprecation classification.')
        rank_deprecation_query = rank_deprecation_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            rank_deprecation_query = rank_deprecation_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            rank_deprecation_query = rank_deprecation_query.replace("<additional_filters>", "")
        self.sql_runner.execute_query(rank_deprecation_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished rank deprecation classification. Took {total_time} seconds.')

    def run_link_change_classification(self, table_name=None, evaluation_gs=False):
        
        start_time = time.time()

        sql_file = self.sql_dir / 'link_change.sql'
        
        with open(sql_file) as f:
            link_change_query = f.read()
        self.logger.info('Started link change classification.')
        link_change_query = link_change_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            link_change_query = link_change_query.replace("<additional_filters>", "AND reverted_edit_predicted = FALSE AND reversion_predicted = FALSE")
        else:
            link_change_query = link_change_query.replace("<additional_filters>", "")

        self.sql_runner.execute_query(link_change_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished link change classification. Took {total_time} seconds.')

    def run_rewording_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'rewording.sql'
        
        with open(sql_file) as f:
            rewording_query = f.read()
        self.logger.info('Started rewording classification.')
        rewording_query = rewording_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            rewording_query = rewording_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted)")
        else:
            rewording_query = rewording_query.replace("<additional_filters>", "")
        
        self.sql_runner.execute_query(rewording_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished rewording classification. Took {total_time} seconds.')

    def run_property_replacement_classification(self, table_name=None, evaluation_gs=False):
        start_time = time.time()

        sql_file = self.sql_dir / 'property_replacement.sql'
        
        with open(sql_file) as f:
            property_replacement_query = f.read()
        self.logger.info('Started property replacement classification.')
    
        property_replacement_query = property_replacement_query.replace("<change>", table_name if table_name else self.table_names['change_table'])\
                                                                .replace("<change_timestamp_entity>", table_name if table_name else self.table_names['materialized_view'])
        
        if not evaluation_gs:
            property_replacement_query = property_replacement_query.replace("<additional_filters>", "AND reverted_edit_predicted = FALSE AND reversion_predicted = FALSE")
        else:
            property_replacement_query = property_replacement_query.replace("<additional_filters>", "")

        self.sql_runner.execute_query(property_replacement_query)

        total_time = time.time() - start_time
        self.logger.info(f'Finished property replacement classification. Took {total_time} seconds.')

    def run_property_value_update_classification(self, table_name=None, evaluation_gs=False):
        

        sql_file = self.sql_dir / 'property_value_update.sql'
        
        with open(sql_file) as f:
            property_value_update_query = f.read()

        property_value_update_query = property_value_update_query.replace("<change>", table_name if table_name else self.table_names['change_table'])
        
        if not evaluation_gs:
            property_value_update_query = property_value_update_query.replace("<additional_filters>", "AND NOT (reverted_edit_predicted OR reversion_predicted OR textual_change_predicted OR re_formatting_predicted OR link_change_predicted OR rank_deprecation_predicted OR value_refinement_predicted OR value_unrefinement_predicted OR property_replacement_predicted OR rewording_predicted)")
        else:
            property_value_update_query = property_value_update_query.replace("<additional_filters>", "")

        self.logger.info('Started property value update classification.')
        start_time = time.time()
        self.sql_runner.execute_query(property_value_update_query)
        total_time = time.time() - start_time
        self.logger.info(f'Finished property value update classification. Took {total_time} seconds.')

    def run_classification(self):
        """
            Runs classification on the DB.
        """
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

    def evaluate(self, gold_standard: bool = False):

        print("Evaluating baseline classifier. Parameter gold_standard =", gold_standard)

        if gold_standard:
            self.evaluate_on_gold_standard()
        else:
            self.run_classification()

        metric_results = self.calculate_evaluation_metrics()

        print("Evaluation results:")
        print(metric_results)

        return metric_results 

    def calculate_evaluation_metrics(self):
        """
            Calculates evaluation metrics based on the predictions made on the tables in the DB
            The predictions are stored in columns named <label>_predicted in the value_change table.
        """

        ## --------------------------------------------
        ## --------- BASIC CLASSES --------------------
        ## ---------------------------------------------

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
            datatype,
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

        metric_results = dict()
        datatypes = ['text', 'entity'] + WD_BASIC_TYPES
        for datatype in datatypes:
        
            metric_results[datatype] = dict()

            # for the changes with more than one tag, if the baseline is correct it will go to each class
            for label in BASIC_CHANGE_LABELS:
                if datatype in ('quantity', 'time', 'globecoordinate'):
                    filtered_df = result[(result['datatype'] == datatype) & (result['label'].str.contains(label))]
                elif datatype == 'entity':
                    filtered_df = result[result['datatype'].isin(WD_ENTITY_TYPES)& (result['label'].str.contains(label))]
                else:  # text
                    filtered_df = result[result['datatype'].isin(WD_STRING_TYPES) & (result['label'].str.contains(label))]
                
                if filtered_df.empty:
                    continue

                y_true = filtered_df[label]
                y_pred = filtered_df[f"{label}_predicted"].astype(int)

                accuracy = accuracy_score(y_true, y_pred)
                precision = precision_score(y_true, y_pred)
                recall = recall_score(y_true, y_pred)
                f1 = f1_score(y_true, y_pred)

                metric_results[datatype][label] = dict()

                metric_results[datatype][label]['accuracy'] = accuracy
                metric_results[datatype][label]['precision'] = precision
                metric_results[datatype][label]['recall'] = recall
                metric_results[datatype][label]['f1'] = f1

        ## --------------------------------------------
        ## --------- REVERTED EDIT --------------------
        ## ---------------------------------------------
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
        precision = precision_score(y_true, y_pred)
        recall = recall_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)

        metric_results['reverted_edit'] = dict()
        metric_results['reverted_edit']['accuracy'] = accuracy
        metric_results['reverted_edit']['precision'] = precision
        metric_results['reverted_edit']['recall'] = recall
        metric_results['reverted_edit']['f1'] = f1

        ## --------------------------------------------
        ## --------- PROPERTY REPLACEMENT --------------------
        ## ---------------------------------------------
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
        precision = precision_score(y_true, y_pred)
        recall = recall_score(y_true, y_pred)
        f1 = f1_score(y_true, y_pred)

        metric_results['property_replacement'] = dict()
        metric_results['property_replacement']['accuracy'] = accuracy
        metric_results['property_replacement']['precision'] = precision
        metric_results['property_replacement']['recall'] = recall
        metric_results['property_replacement']['f1'] = f1

        return metric_results

    def __del__(self):
        
        if self.sql_runner: # close db connection
            self.sql_runner.close()