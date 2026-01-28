import glob
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from xgboost import XGBClassifier
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler, LabelBinarizer
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import KFold, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
from IPython.display import display
import csv

import matplotlib.pyplot as plt
import pickle
import time
import os
from collections import Counter
import numpy as np
import pickle
import json

from src.utils.utils import get_time_unit
from src.classifiers.base_classifier import BaseClassifier
from .ml_features import create_text_features, create_entity_features, create_globe_coordinate_features, create_quantity_features, create_time_features, create_reverted_edit_features, create_property_replacement_features
from src.utils.const import BASE_KEY_TYPES, PROP_REP_KEY_TYPES, CHANGES_TO_CLASSIFY, CLASSIFICATION_RESULTS, TRAINING_RESULTS, MODELS_CONFIG_PATH, WD_ENTITY_TYPES, WD_STRING_TYPES, WD_BASIC_TYPES, ML_MODELS, ML_MODELS_LABELS, DATATYPE_INDEPENDENT_CLASSES, REVERTED_EDIT_LABEL, TRAINING_INFO_DIR, PROPERTY_REPLACEMENT_LABEL, FEATURES_DIR, GOLD_STANDARD_DIR

class MLClassifier(BaseClassifier):
    def __init__(self, config_path: str, classifier_type: str = "ml", connection=None):
        super().__init__(config_path=config_path, classifier_type=classifier_type)

        self.random_state = self.config.get('random_state', 42)
        self.fold_splits = self.config.get('fold_splits', 5)
        self.prob_threshold = self.config.get('prob_threshold', 0.5)

        self.runtimes = dict()

        self.conn = connection


    def get_features(self, dt_class, df):
        feature_cols = []
            
        if  dt_class == 'text':
            df, feature_cols = create_text_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_STRING_TYPES)]

        elif dt_class == 'entity':

            df, feature_cols = create_entity_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_ENTITY_TYPES)]

        elif dt_class in WD_BASIC_TYPES:

            if dt_class == 'globecoordinate':
                df, feature_cols = create_globe_coordinate_features(df, feature_cols)
            elif dt_class == 'quantity':
                df, feature_cols = create_quantity_features(df, feature_cols)
            elif dt_class == 'time':
                df, feature_cols = create_time_features(df, feature_cols)

            df_type = df[df['datatype'] == dt_class]

        elif dt_class == REVERTED_EDIT_LABEL:
            df_type, feature_cols = create_reverted_edit_features(df, feature_cols)

        elif dt_class == PROPERTY_REPLACEMENT_LABEL:
            df_type, feature_cols = create_property_replacement_features(df, feature_cols)

        return df_type, feature_cols
    
    def perform_grid_search(self, classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config):
        print(f'Performing grid search for {classifier} on datatype {dt_class}...')
        """
            Model Config structure:
            {
                "Random_Forest": {
                    "string": {
                        "n_estimators": int,
                        "max_depth": int,
                        ...
                    },
                    "entity": {...},
                    ...
                },
                "KN": {...} // the same structure as RF
                "Gradient_Boosting": {...} // the same structure as RF
            }
        """
        
        if classifier == 'Random_Forest':
            param_grid = {
                'n_estimators': [50, 100, 150, 200],
                'max_depth': [None, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                # NOTE: I remove these 2 since they are not that important in RF
                # because RF already diminishes the chance of overfitting by averaging multiple trees
                # 'min_samples_split': [2, 5, 8, 10],
                # 'min_samples_leaf': [1, 2, 3, 4, 5],
                'bootstrap': [True, False]
            }
            
            # This already does cross-validation internally (fold=5)
            grid_search = GridSearchCV(RandomForestClassifier(self.random_state), param_grid=param_grid, cv=5)

        elif classifier == 'KN':
            param_grid = {
                'n_neighbors': [3, 5, 7, 10, 15, 20, 25, 30]
            }
            grid_search = GridSearchCV(KNeighborsClassifier(), param_grid=param_grid, cv=5)

        elif classifier == 'Gradient_Boosting':
            param_grid = {
                'n_estimators': [50, 100, 150, 200],
                'max_depth': [3, 5, 7, 10]
            }
            non_multilabel_model = GradientBoostingClassifier(random_state=self.random_state)

            if is_multilabel: 
                # NOTE: when using MultiOutputClassifier the internal estimator's 
                # parameters need to be accessed with the prefix estimator__, if not, it just considers the params for the MultiOutput
                param_grid = {
                    f'estimator__{key}': value 
                    for key, value in param_grid.items()
                }
                
                grid_search = GridSearchCV(
                    MultiOutputClassifier(non_multilabel_model), 
                    param_grid=param_grid, 
                    cv=5
                )
            else:
                grid_search = GridSearchCV(non_multilabel_model, param_grid=param_grid, cv=5)

        elif classifier == 'XGBoost': # does not require meta model for multi-label
            param_grid = {
                'n_estimators': [50, 100, 150, 200],
                'max_depth': [3, 5, 7, 10]
            }

            grid_search = GridSearchCV(XGBClassifier(random_state=self.random_state), param_grid=param_grid, cv=5)

        grid_search.fit(X_scaled, y_binary)
        best_params = grid_search.best_params_
        if is_multilabel:
            # remove the prefix estimator__ from the result
            best_params = {
                key.replace('estimator__', ''): value 
                for key, value in best_params.items()
            }
        model_config[classifier][dt_class] = best_params

        with open(MODELS_CONFIG_PATH, 'w') as config_file:
            json.dump(model_config, config_file, indent=4)

        return best_params

    def get_model_instance(self, classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config):
        """
            Returns model instance for the specified classifier.
            If the parameters for the model have already been optimized, they are loaded from model_config. If not, 
            grid search is performed to find the best parameters
        """
        
        if classifier == 'Random_Forest': # already supports multi-label
            
            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = self.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]
            
            model = RandomForestClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                class_weight='balanced', # this handles unbalanced classes
                random_state=self.random_state
            )

        elif classifier == 'KN': # already supports multi-label

            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = self.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]

            model = KNeighborsClassifier(n_neighbors=model_config[classifier][dt_class]['n_neighbors'])
        
        elif classifier == 'Gradient_Boosting': # needs ensemble (MultiOutputClassifier) to support multi-label

            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = self.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]
                
            # Base classifier
            base_model = GradientBoostingClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                random_state=self.random_state 
            )

            model = base_model
            if is_multilabel:
                model = MultiOutputClassifier(base_model)

        elif classifier == 'XGBoost': 
            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = self.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]
            
            # Base classifier
            model = XGBClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                random_state=self.random_state 
            )
        
        return model, base_model if classifier == 'Gradient_Boosting' and is_multilabel else None

    def perform_kfold_training(self, X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, df_index, classifier='Random_Forest'):
        print(f'Performing k-fold training for {dt_class}, {classifier}')
        
        is_multilabel = y_binary.shape[1] > 1 # shape[1] is number of columns (labels)

        model_config = {}

        if not is_multilabel:
            y_binary = y_binary.ravel() # for binary classification needs to be 1D

        if os.path.isfile(MODELS_CONFIG_PATH):
            with open(MODELS_CONFIG_PATH, 'r') as config_file:
                model_config = json.load(config_file)
        
        if classifier not in model_config:
            model_config[classifier] = {}

        if dt_class not in model_config[classifier]:
            model_config[classifier][dt_class] = {}
            
        if is_multilabel:
            cv = MultilabelStratifiedKFold(n_splits=self.fold_splits, shuffle=True, random_state=self.random_state)
            split = cv.split(X_scaled, y_binary)
        else:
            cv = KFold(n_splits=self.fold_splits, shuffle=True, random_state=self.random_state)
            split = cv.split(X_scaled)

        results_folds = []
        # aggregate all test and predictions across all folds, given that each instance appears only once in the test set
        # across all folds. Then, I have a prediction for each instance and then I calculate precision, recall, accuracy, f1
        all_y_test = []
        all_y_pred = []

        start_time = time.time()
        for fold, (train_index, test_index) in enumerate(split, 1):

            model, base_model = self.get_model_instance(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            X_train, X_test = X_scaled[train_index], X_scaled[test_index]
            y_train, y_test = y_binary[train_index], y_binary[test_index]

            metrics_results = {}

            actual_test_index = df_index[test_index]

            if is_multilabel:
                clf = model.fit(X_train, y_train) # fit model on trainting data

                # bEFORE:
                # y_pred = clf.predict(X_test) # predict on test data

                y_pred = np.zeros((len(X_test), len(label_binarizer.classes_)))
                y_pred_proba = model.predict_proba(X_test)
                # predict_proba from docs: ndarray of shape (n_samples, n_classes), or a list of such arrays
                # The class probabilities of the input samples. The order of the classes corresponds to that in the attribute classes_.
                
                if isinstance(y_pred_proba, list):
                    # the sklearn classifiers return a list of arrays, one per label
                    # each array has shape (n_samples, 2), where the second column is the positive class probability
                    for label_idx in range(len(label_binarizer.classes_)):
                        probs = y_pred_proba[label_idx][:, 1] # positive class prob for label
                        y_pred[:, label_idx] = (probs >= self.prob_threshold).astype(int)

                    # cases where none of the probs reaches 0.5
                    no_prediction_mask = y_pred.sum(axis=1) == 0
                    if no_prediction_mask.any():
                        # get all probabilities as array (n_samples, n_classes)
                        all_probs = np.column_stack([y_pred_proba[j][:, 1] for j in range(len(label_binarizer.classes_))]) # get positive class porb
                        # for samples with no prediction, set highest prob class to 1
                        max_indices = np.argmax(all_probs[no_prediction_mask], axis=1)
                        y_pred[no_prediction_mask, max_indices] = 1
                else:
                    # XGboost returns an ndarray with shape (n_samples, n_classes)
                    # so it gives you for every sample the probabilities for each class
                    y_pred = (y_pred_proba >= self.prob_threshold).astype(int)    

                    no_prediction_mask = y_pred.sum(axis=1) == 0
                    if no_prediction_mask.any():
                        max_indices = np.argmax(y_pred_proba[no_prediction_mask], axis=1)
                        y_pred[no_prediction_mask, max_indices] = 1
      
                for i, class_label in enumerate(label_binarizer.classes_):
                    #NOTE: this selects all rows for label i
                    if not class_label in metrics_results:
                        metrics_results[class_label] = {}

                    label_accuracy = accuracy_score(y_test[:, i], y_pred[:, i])
                    label_precision = precision_score(y_test[:, i], y_pred[:, i], zero_division=0)
                    label_recall = recall_score(y_test[:, i], y_pred[:, i], zero_division=0)
                    label_f1 = f1_score(y_test[:, i], y_pred[:, i], zero_division=0)
                    
                    metrics_results[class_label]['accuracy'] = label_accuracy
                    metrics_results[class_label]['precision'] = label_precision
                    metrics_results[class_label]['recall'] = label_recall
                    metrics_results[class_label]['f1'] = label_f1

            else:
                # if it's not multi-label it's binary -> calculate metrics overall, don't filter per label
                clf = model.fit(X_train, y_train.ravel())
                y_pred = clf.predict(X_test)
                
                metrics_results[dt_class] = {} # dt_class here is property_replacement or reverted_edit
                
                metrics_results[dt_class]['accuracy'] = accuracy_score(y_test.ravel(), y_pred.ravel())
                metrics_results[dt_class]['precision'] = precision_score(y_test.ravel(), y_pred.ravel(), zero_division=0)
                metrics_results[dt_class]['recall'] = recall_score(y_test.ravel(), y_pred.ravel(), zero_division=0)
                metrics_results[dt_class]['f1'] = f1_score(y_test.ravel(), y_pred.ravel(), zero_division=0)

            all_y_test.append(y_test)
            all_y_pred.append(y_pred)

            results_folds.append({
                'classifier': classifier.lower(),
                'fold': fold,
                'metrics_results': metrics_results,
                'model': clf,
                'base_model': base_model if classifier == 'Gradient_Boosting' and is_multilabel else None,
                'features': feature_cols,
                'train_index': train_index, 
                'test_index': actual_test_index,
                'multi_label_binarizer': label_binarizer,
                'label_distribution': Counter(all_labels),
                'X_test': X_test,
                'y_pred': y_pred,
                'y_test': y_test
            })

        training_time = time.time() - start_time
        if dt_class not in self.runtimes:
            self.runtimes[dt_class] = dict()
        
        self.runtimes[dt_class][classifier] = training_time
        
        if is_multilabel:
            labels = label_binarizer.classes_
        else:
            labels = [dt_class] 

        micro_averages = dict()
        if is_multilabel:
            all_y_test = np.vstack(all_y_test) # concatenate all folds
            all_y_pred = np.vstack(all_y_pred)
            
            for i, class_label in enumerate(labels):
                micro_averages[class_label] = {
                    'precision': precision_score(all_y_test[:, i], all_y_pred[:, i], zero_division=0),
                    'recall': recall_score(all_y_test[:, i], all_y_pred[:, i], zero_division=0),
                    'accuracy': accuracy_score(all_y_test[:, i], all_y_pred[:, i]),
                    'f1': f1_score(all_y_test[:, i], all_y_pred[:, i], zero_division=0)
                }
        else:
            all_y_test = np.concatenate(all_y_test)
            all_y_pred = np.concatenate(all_y_pred)
            micro_averages[dt_class] = {
                'precision': precision_score(all_y_test, all_y_pred, zero_division=0),
                'recall': recall_score(all_y_test, all_y_pred, zero_division=0),
                'accuracy': accuracy_score(all_y_test, all_y_pred),
                'f1': f1_score(all_y_test, all_y_pred, zero_division=0)
            }

        return results_folds, micro_averages
    
    def calculate_evaluation_metrics(self, model='Random_Forest'):

        with open(f'datatype_classifiers_multilabel_{model.lower()}.pkl', 'rb') as f:
            classifiers = pickle.load(f)

        for datatype, folds_info in classifiers.items(): # info is a list of dicts, one per fold
            print(f"\n{'='*80}")
            print(f"DATATYPE: {datatype.upper()}")
            
            num_folds = len(folds_info)

            overall_accuracy_all_folds = {}
            overall_precision_all_folds = {}
            overall_recall_all_folds = {}
            overall_f1_all_folds = {}
            label_distribution = folds_info[0].get('label_distribution', {}) # it's the same for all folds
            features = folds_info[0].get('features', [])

            for fold in folds_info:
                for label, metric_values in fold['metrics_results'].items(): # metric values for this fold
                    
                    if label not in overall_accuracy_all_folds:
                        overall_accuracy_all_folds[label] = 0
                    overall_accuracy_all_folds[label] += metric_values['accuracy']
                    
                    if label not in overall_precision_all_folds:
                        overall_precision_all_folds[label] = 0
                    overall_precision_all_folds[label] += metric_values['precision']
                    
                    if label not in overall_recall_all_folds:
                        overall_recall_all_folds[label] = 0
                    overall_recall_all_folds[label] += metric_values['recall']

                    if label not in overall_f1_all_folds:
                        overall_f1_all_folds[label] = 0
                    overall_f1_all_folds[label] += metric_values['f1']

            print('Metric values averaged across all folds:')
            for label in overall_accuracy_all_folds.keys():
                overall_accuracy_all_folds[label] = overall_accuracy_all_folds[label] / num_folds
                overall_precision_all_folds[label] = overall_precision_all_folds[label] / num_folds
                overall_recall_all_folds[label] = overall_recall_all_folds[label] / num_folds
                overall_f1_all_folds[label] = overall_f1_all_folds[label] / num_folds
                print(f"LABEL: {label.upper()}")

                print(f"Accuracy': {overall_accuracy_all_folds[label]:.3f}")
                print(f"Precision': {overall_precision_all_folds[label]:.3f}")
                print(f"Recall': {overall_recall_all_folds[label]:.3f}")
                print(f"F1 Score': {overall_f1_all_folds[label]:.3f}")

                print(f"{'-'*80}")

            print(f"\nLabel Distribution:")
            for label, distribution in label_distribution.items():
                print(f"'{label}': {distribution}")
            
            print(f"\nFeatures: {features}")
            print(f"{'='*80}")

    @staticmethod
    def create_data_structure_for_visualization():

        """
        training_info_{model}.pkl structure:
        {
            "datatype": { # for reverted_edit & property_replacement, datatype is the name of the label
                'results_folds': [results per fold],
                'micro_averages': {}
            ...
        }

        results per fold:
        {
            'classifier': string, # kn, xgboost, random_forest, gradient_boosting
            'fold': int,
            'metrics_results': {
                'label': { 
                    'precision': float,
                    'recall': float,
                    'accuracy': float,
                    'f1': float
                },
                ....
            },
            'model': clf,
            'base_model': model,
            'features': feature_cols,
            ....
        }

        Final structure to save:
        "model": {
            "datatype":{
                "label": {
                    "precision": float,
                    "recall": float,
                    "accuracy": float,
                    "f1": float
                }
            }
        }
        """

        # Create data structure
        results = {}
        for model in ['kn', 'random_forest', 'gradient_boosting', 'xgboost']:
            print(f'Processing model: {model}')
            with open(f'{TRAINING_INFO_DIR}/training_info_{model}.pkl', 'rb') as f:
                training_info_model = pickle.load(f)
            
            results[model] = {}
            
            # go over each fold's results for a single datatype
            for datatype, training_info in training_info_model.items():
                
                micro_averages = training_info['micro_averages']

                results[model][datatype] = {}

                for label, metric_values in micro_averages.items(): # metric values across all folds

                    results[model][datatype][label] = {
                        'precision': metric_values['precision'],
                        'recall': metric_values['recall'],
                        'accuracy': metric_values['accuracy'],
                        'f1': metric_values['f1']
                    }

        # re-order data structure for visualization

        """
        Structure for visualization:
        "datatype": {
            "label": {
                "model": {
                    "precision": float,
                    "recall": float,
                    "accuracy": float,
                    "f1": float
                }
            }
        }
        """

        results_dt_label_model_micro = {}
        for model in results:
            for datatype in results[model]:
                if datatype not in results_dt_label_model_micro:
                    results_dt_label_model_micro[datatype] = {}
                
                for label in results[model][datatype]:
                    if label not in results_dt_label_model_micro[datatype]:
                        results_dt_label_model_micro[datatype][label] = {}
                    
                    results_dt_label_model_micro[datatype][label][model] = results[model][datatype][label]
                
        return results_dt_label_model_micro
    
    @staticmethod
    def metric_visualization(results_dt_label_model):

        metrics = ['precision', 'recall', 'accuracy', 'f1']

        # Count subplots
        total_plots = sum(len(results_dt_label_model[dt]) for dt in results_dt_label_model)
        ncols = 3
        nrows = (total_plots + ncols - 1) // ncols

        fig, axes = plt.subplots(nrows, ncols, figsize=(18, 5*nrows))
        if isinstance(axes, np.ndarray):
            axes = axes.flatten()
        else:
            axes = [axes]

        plot_idx = 0
        for datatype in sorted(results_dt_label_model.keys()):
            for label in sorted(results_dt_label_model[datatype].keys()):
                ax = axes[plot_idx]
                
                x = np.arange(len(ML_MODELS))
                width = 0.2
                
                for i, metric in enumerate(metrics):
                    values = [results_dt_label_model[datatype][label][model][metric] for model in ML_MODELS] # metric (accuracy/precision/recall/f1) values for this label and datatype
                    
                    offset = (i - 1) * width
                    bars = ax.bar(x + offset, values, width, label=metric.capitalize(), alpha=0.8)
                    
                    for bar in bars:
                        height = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2., height,
                            f'{height:.2f}',
                            ha='center', va='bottom', fontsize=8)
                
                ax.set_ylabel('Score')
                ax.set_title(f'{datatype.upper()}\n{label}', fontweight='bold', fontsize=12)
                ax.set_xticks(x)
                ax.set_xticklabels(ML_MODELS_LABELS, rotation=45, ha='right', fontsize=9)
                ax.legend(loc='upper left', fontsize=9)
                ax.grid(axis='y', alpha=0.3)
                ax.set_ylim([0, 1.05])
                
                plot_idx += 1

        for idx in range(plot_idx, len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        os.makedirs(TRAINING_RESULTS, exist_ok=True)
        plt.savefig(f'{TRAINING_RESULTS}/classifier_metrics_all.png', dpi=300, bbox_inches='tight')
        plt.show()

        print(f'Saved evaluation metric plots to {TRAINING_RESULTS}/classifier_metrics_all.png')

    @staticmethod
    def select_best_classifier(results_dt_label_model):

        score_per_model = {}
        df_data = {
            'datatype': [],
            'label': [],
            'best_model': [],
            'best_f1': [],
            'best_recall': [],
            'best_precision': []
        }
        for datatype in results_dt_label_model:
            for label in results_dt_label_model[datatype]:
                best_model = None
                best_f1 = 0
                best_recall = 0
                best_precision = 0
                for model in results_dt_label_model[datatype][label]:
                    if model not in score_per_model:
                        score_per_model[model] = 0
                    f1 = results_dt_label_model[datatype][label][model]['f1']
                    recall = results_dt_label_model[datatype][label][model]['recall']
                    precision = results_dt_label_model[datatype][label][model]['precision']
                    if f1 > best_f1:
                        best_f1 = f1
                        best_model = model

                    if recall > best_recall:
                        best_recall = recall
                    
                    if precision > best_precision:
                        best_precision = precision

                df_data['datatype'].append(datatype)
                df_data['label'].append(label)
                df_data['best_model'].append(best_model)
                df_data['best_f1'].append(best_f1)
                df_data['best_recall'].append(best_recall)
                df_data['best_precision'].append(best_precision)
                score_per_model[best_model] += 1

        df = pd.DataFrame(df_data)

        df.to_csv(f'{TRAINING_RESULTS}/best_model_per_f1_all_tasks.csv', header=0)
        print(f'Saved best model per classification task (according to F1 score) to {TRAINING_RESULTS}/best_model_per_f1_all_tasks.csv')

        print('Overall best model (considering only F1 score):')

        best_score = 0
        best_model = None
        for model, score in score_per_model.items():
            if score > best_score:
                best_score = score
                best_model = model
            print(f'Model: {model}, Score: {score}')

        print(f'Overall best model is {best_model} with score {best_score}/ {sum(score_per_model.values())}')

        model_averages = {model: {'f1': [], 'precision': [], 'recall': [], 'accuracy': []} 
                        for model in ML_MODELS}

        for datatype in results_dt_label_model:
            for label in results_dt_label_model[datatype]:
                for model in ML_MODELS:
                    model_averages[model]['f1'].append(results_dt_label_model[datatype][label][model]['f1'])
                    model_averages[model]['precision'].append(results_dt_label_model[datatype][label][model]['precision'])
                    model_averages[model]['recall'].append(results_dt_label_model[datatype][label][model]['recall'])
                    model_averages[model]['accuracy'].append(results_dt_label_model[datatype][label][model]['accuracy'])


        summary_stats = []
        for model in ML_MODELS:
            summary_stats.append({
                'Model': model,
                'Mean F1': np.mean(model_averages[model]['f1']).round(2),
                'Mean Precision': np.mean(model_averages[model]['precision']).round(2),
                'Mean Recall': np.mean(model_averages[model]['recall']).round(2),
                'Mean Accuracy': np.mean(model_averages[model]['accuracy']).round(2)
            })

        df_summary = pd.DataFrame(summary_stats)
        df_summary.to_csv(f'{TRAINING_RESULTS}/summary_all_models.csv')
        print("\nModel Performance Summary (across all classification tasks):")
        display(df_summary.to_string(index=False))

        best_model = None
        best_f1 = 0
        for i, stats in enumerate(summary_stats):
            if stats['Mean F1'] > best_f1:
                best_f1 = stats['Mean F1']
                best_model = stats['Model']
        
        print(f'Model with best F1 across all classification tasks is {best_model} with an avg. F1 of {best_f1}')

        print(f'Saved summary stats to {TRAINING_RESULTS}/summary_all_models.csv')

        with open(f'{TRAINING_INFO_DIR}/training_info_{best_model}.pkl', 'rb') as f:
            training_info_model = pickle.load(f)

        with open(f'{TRAINING_RESULTS}/best_model_training_info.pkl', 'wb') as f:
            pickle.dump(training_info_model, f)


    def train_classifier(self):
        os.makedirs(FEATURES_DIR, exist_ok=True)
        
        df_gs = pd.read_csv(f'{GOLD_STANDARD_DIR}/gold_standard.csv')

        datatypes_classes = WD_BASIC_TYPES + ['text', 'entity', PROPERTY_REPLACEMENT_LABEL] 
        classifiers_rf = dict()
        classifiers_kn = dict()
        classifiers_gb = dict()
        classifiers_xgb = dict()

        
        scalers = dict()
        for dt_class in datatypes_classes:
            print(f"\n{'='*50}")
            print(f"Training classifier for: {dt_class}")
            print(f"{'='*50}")

            #############################
            #   Load or create features
            #############################
            if os.path.isfile(f'{FEATURES_DIR}/gs_features_{dt_class}.csv'):
                df = pd.read_csv(f'{FEATURES_DIR}/gs_features_{dt_class}.csv', index_col=0)
                with open(f'{FEATURES_DIR}/feature_cols_{dt_class}.pkl', 'rb') as f:
                    feature_cols = pickle.load(f)

                print('Features already exist, loading from disk.')
            else:
                print('Features dont exist, creating.')
                df = df_gs
                if dt_class in DATATYPE_INDEPENDENT_CLASSES: # reverted edit, property replacement have their own files
                    df = pd.read_csv(f'{GOLD_STANDARD_DIR}/{dt_class}.csv')

                # df is already filtered per datatype inside get_features
                df, feature_cols = self.get_features(dt_class, df)
                os.makedirs(FEATURES_DIR, exist_ok=True)
                df.to_csv(f'{FEATURES_DIR}/gs_features_{dt_class}.csv', index=True)
            
            if dt_class == PROPERTY_REPLACEMENT_LABEL:
                # de duplicate by pair_id because the features are the same for all the rows in the group, then I would have duplicated rows
                df = df.groupby('pair_id', as_index=False).first() # keep only one row per pair_id
            
            # Fill NAN/Inf with 0
            X = df[feature_cols].astype(float).fillna(0) # features
            X.replace([np.inf, -np.inf], np.nan).fillna(0, inplace=True)
            
            # Remove zero-variance features
            zero_std_cols = X.columns[X.std() == 0]

            if len(zero_std_cols) > 0:
                X = X.drop(columns=zero_std_cols)
                print('Removed zero-variance features: ', zero_std_cols.tolist())

            with open(f'{FEATURES_DIR}/feature_cols_{dt_class}.pkl', 'wb') as f:
                pickle.dump([f for f in feature_cols if f not in zero_std_cols], f) # remove zero-variance features
            
            # Scale
            path_to_scalers = f'{FEATURES_DIR}/scalers.pkl'
            if os.path.exists(path_to_scalers):
                with open(path_to_scalers, 'rb') as f:
                    scalers = pickle.load(f)
                scaler = scalers[dt_class]
                X_scaled = scaler.transform(X)
            else:# else: uses the scaler created in the beggining and it gets saved at the end
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                scalers[dt_class] = scaler

            # Split label into binary columns
            label_binarizer = None
            if dt_class not in DATATYPE_INDEPENDENT_CLASSES:
                df['labels_list'] = df['label'].fillna('').str.split(',').apply(lambda x: [l.strip() for l in x])
        
                all_labels = [label for labels in df['labels_list'] for label in labels]

                # To do multi-label classification we need 1 column per label
                label_binarizer = MultiLabelBinarizer()
                y_binary = label_binarizer.fit_transform(df['labels_list'])
                
            else: # for reverted edit, property replacement I only have single labels
                label_binarizer = LabelBinarizer()
                df['label'] = df['label'].fillna(f'non_{dt_class}')# fills nan with non_reverted_edit, non_property_replacement, etc.
                all_labels = df['label'].tolist() 
                y_binary = label_binarizer.fit_transform(df['label'])

            results_folds_rf, micro_averages_rf = self.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, df.index.values, classifier='Random_Forest')
            results_folds_kn, micro_averages_kn = self.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, df.index.values, classifier='KN')
            results_folds_gb, micro_averages_gb = self.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, df.index.values, classifier='Gradient_Boosting')
            results_folds_xg, micro_averages_xg = self.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, df.index.values, classifier='XGBoost')

            classifiers_rf[dt_class] = {
                'results_folds': results_folds_rf,
                'micro_averages': micro_averages_rf
            }

            classifiers_kn[dt_class] = {
                'results_folds': results_folds_kn,
                'micro_averages': micro_averages_kn
            }

            classifiers_gb[dt_class] = {
                'results_folds': results_folds_gb,
                'micro_averages': micro_averages_gb
            }

            classifiers_xgb[dt_class] = {
                'results_folds': results_folds_xg,
                'micro_averages': micro_averages_xg
            }

        models_to_save = {
            'random_forest': classifiers_rf,
            'kn': classifiers_kn,
            'gradient_boosting': classifiers_gb,
            'xgboost': classifiers_xgb
        }

        os.makedirs(TRAINING_INFO_DIR, exist_ok=True)

        for model, dict_ in models_to_save.items():
            if not os.path.isfile(f'{TRAINING_INFO_DIR}/training_info_{model}.pkl'):
                with open(f'{TRAINING_INFO_DIR}/training_info_{model}.pkl', 'wb') as f:
                    pickle.dump(dict_, f)
            else:
                try:
                    with open(f'{TRAINING_INFO_DIR}/training_info_{model}.pkl', 'rb') as f:
                        info = pickle.load(f)
                except Exception as e:
                    print(f"Error loading existing training info for {model}: {e}")
                    raise e
                
                for dt_class in dict_.keys():
                    info[dt_class] = dict_[dt_class]
                
                with open(f'{TRAINING_INFO_DIR}/training_info_{model}.pkl', 'wb') as f:
                    pickle.dump(info, f)

        path_to_scaler = f'{FEATURES_DIR}/scalers.pkl'
        if not os.path.exists(path_to_scaler):
            with open(path_to_scaler, 'wb') as f:
                pickle.dump(scalers, f)

        with open(f'{TRAINING_INFO_DIR}/training_runtimes.pkl', 'wb') as f:
            pickle.dump(self.runtimes, f)

        for dt_class, runtime_models in self.runtimes.items():

            print(f'# ------ {dt_class.upper()} ------ #')
            for model, runtime in runtime_models.items():
                print(f'{model}: {runtime} seconds')
            print('# ------------------------------ #')
        
    
    def evaluate(self):
        results_dt_label_model = MLClassifier.create_data_structure_for_visualization()

        MLClassifier.metric_visualization(results_dt_label_model)

        MLClassifier.select_best_classifier(results_dt_label_model)
    
        return results_dt_label_model

    def run_classification(self, X, X_index, dt_label):
        """
            We do ensemble voting with the models from all folds
            Make all models prdict, average the prob for the classes across all folds, pick the probs that are > 0.5
            If no prob is > 0.5, take the highest one
        """
        with open(f'{FEATURES_DIR}/scalers.pkl', 'rb') as f:
            scalers = pickle.load(f)

        # scale features with same scalers used during training
        scaler = scalers[dt_label]
        X_scaled = scaler.transform(X)

        # load best model
        with open(f'{TRAINING_RESULTS}/best_model_training_info.pkl', 'rb') as f:
            training_info_model = pickle.load(f)

        # load results_folds, has the trained model
        results_folds = training_info_model[dt_label]['results_folds']

        all_predictions = []

        for i, fold_result in enumerate(results_folds):
            model = fold_result['model']
            
            # Get probability predictions for each class
            # For multi-label, this returns shape (n_samples, n_classes)
            pred_proba = model.predict_proba(X_scaled)
            
            # predict_proba for multi-label returns list of arrays (one per class)
            # Each element is (n_samples, 2) for [prob_class_0, prob_class_1]
            # want (n_samples, n_classes) with prob of class being 1
            
            if isinstance(pred_proba, list):  # Multi-label case
                # positive class (index 1) for each label
                # each p is an array of lists, corresponding to a specific label
                # when we do p[:, 1] we are getting the prob of class 1 for all examples, for that label
                # with np.column_stack, we stack them on a column, so we get:
                # e.g. pred_proba = array([[0.99799539, 0.00200461], [0.99799539, 0.00200461],[0.00441102, 0.99558898]]), array([[0.99322399, 0.00677601],[0.99606133, 0.00393867],[0.01199732, 0.98800268]])
                # p = array([[0.99799539, 0.00200461], [0.99799539, 0.00200461],[0.00441102, 0.99558898]])
                # p[:, 1] = [ 0.00200461
                #             0.00200461
                #             0.99558898 ]
                # for the next label, it will be another column
                pred_proba_positive = np.column_stack([p[:, 1] for p in pred_proba]) 
            else:  # Single-label case
                pred_proba_positive = pred_proba
            
            # has one array for each fold
            all_predictions.append(pred_proba_positive)

        # Stack all predictions: shape (n_folds, n_samples, n_classes)
        all_predictions = np.array(all_predictions)

        # Average across folds: shape (n_samples, n_classes)
        avg_prediction = np.mean(all_predictions, axis=0)

        # Apply 0.5 threshold for each instance
        final_labels = (avg_prediction >= 0.5).astype(int)

        # Apply fallback for instances with no labels
        for i in range(len(final_labels)):
            if not final_labels[i].any():  # No label assigned
                highest_idx = np.argmax(avg_prediction[i])
                final_labels[i, highest_idx] = 1

        # get label binarizer to create column of labels
        multi_label_binarizer = results_folds[0]['multi_label_binarizer'] # it's the same for all folds

        # get actual label names
        final_labels_transformed = multi_label_binarizer.inverse_transform(final_labels)

        # create list of labels
        pred_df = pd.DataFrame({
            'predicted_labels': [', '.join(labels) if labels else '(none)' for labels in final_labels_transformed]
        }, index=X_index)

        # join labels list to original data
        results_df = X.join(pred_df)

        return results_df
    
    def classify_in_batches(self, dt_label, table_prefix, batch_size=100000, max_batches=None):
        """
            Classify changes for a single datatye/label in smaller batches.
        """
        
        predictions_files = []
        offset = 0

        with open(f'{FEATURES_DIR}/features_cols_{dt_label}.pkl') as f:
            feature_cols = pickle.load(f)
        
        feature_cols_str = ', '.join(feature_cols)

        if dt_label in ('entity', 'text', 'time', 'quantity', 'globecoordinate'):
            key_cols = BASE_KEY_TYPES.keys()
        else: # property_replacement
            key_cols = PROP_REP_KEY_TYPES.keys()

        key_cols_str = ', '.join(key_cols)

        if self.conn:
            print('Getting changes to classify from DB')
            num_batches = 0
            while True:

                if max_batches and num_batches >= max_batches:
                    print(f'Loaded {max_batches} batches from DB')
                    break

                # get data
                query = f"""
                    SELECT {key_cols_str}, {feature_cols_str}
                    FROM sample_features_{dt_label}{table_prefix}
                    WHERE
                        (label IS NULL or label = '') 
                    LIMIT {batch_size} OFFSET {offset}
                """
                df = pd.read_sql(query, self.conn)
                
                if len(df) == 0:
                    break
                
                # Classify
                results = self.run_classification(df, df.index, dt_label)
                
                # Save to csv for loading with copy
                os.makedirs(f'{CLASSIFICATION_RESULTS}/{dt_label}{table_prefix}', exist_ok=True)
                batch_file = f'{CLASSIFICATION_RESULTS}/{dt_label}{table_prefix}/predictions_chunk_{offset//batch_size}.csv'
                results.to_csv(batch_file, index=False, header=False, sep=';', quoting=csv.QUOTE_NONE, escapechar='\\')
                predictions_files.append(batch_file)
                
                offset += batch_size
                num_batches += 1
            
            print(f'Classified {num_batches} batches from DB for {dt_label}')

        else:
            print(f'No connection to DB. Checking if there are batches of changes stored in {CHANGES_TO_CLASSIFY}')
            # get full path
            os.chdir(CHANGES_TO_CLASSIFY)
            num_files = 0
            for file_name in list(glob.glob('*.csv')):
                df = pd.read_csv(file_name)
                results = self.run_classification(df, df.index, dt_label)
                
                # Save to csv for loading with copy
                os.makedirs(f'{CLASSIFICATION_RESULTS}/{dt_label}{table_prefix}', exist_ok=True)
                batch_file = f'{CLASSIFICATION_RESULTS}/{dt_label}{table_prefix}/{file_name}'
                results.to_csv(batch_file, index=False, header=False, sep=';', quoting=csv.QUOTE_NONE, escapechar='\\')
                predictions_files.append(batch_file)

                num_files += 1

            print(f'Classified {num_files} files for {dt_label}')

        if len(predictions_files) > 0 and self.conn:
            # Load all batches into temp table
            print('Updating DB with predictions')

            print('Creating temp table')
            cursor = self.conn.cursor()

            if dt_label in ('time', 'quantity', 'text', 'globecoordinate'):
                key_cols_temp = ', '.join([f'{col} {col_type}' for col, col_type in BASE_KEY_TYPES.items()])
            else:
                key_cols_temp = ', '.join([f'{col} {col_type}' for col, col_type in PROP_REP_KEY_TYPES.items()])
            
            cursor.execute(f"CREATE TEMP TABLE temp_predictions ({key_cols_temp}, label TEXT)")
            
            print('Loading data into temp table')
            start_time = time.time()
            for batch_file in predictions_files:
                with open(batch_file, 'r') as f:
                    cursor.copy_expert("COPY temp_predictions FROM STDIN (FORMAT CSV, DELIMITER ';')", f)
                
                os.remove(batch_file) # remove batch file after it was loaded to temp

            elapsed_time = time.time() - start_time
            final_time, unit = get_time_unit(elapsed_time)
            print(f'Finished loading data into temp table, took {final_time} {unit}')
            
            print('Updating change table')
            start_time = time.time()
            # Update labels
            cursor.execute(f"""
                UPDATE sample_features_{dt_label}{table_prefix} f
                SET label = tp.label
                FROM temp_predictions tp 
                WHERE 
                    {' AND'.join([f'f.{key_col} = tp.{key_col}' if key_col != 'change_target' else f"COALESCE(f.{key_col}, '') = COALESCE(tp.{key_col}, '')" for key_col in key_cols])}
            """)
            elapsed_time = time.time() - start_time
            final_time, unit = get_time_unit(elapsed_time)
            print(f'Finished updating table in {final_time} {unit}')

            cursor.execute("DROP TABLE temp_predictions")

            self.conn.commit()

    def __del__(self):
        if self.conn:
            self.conn.close()