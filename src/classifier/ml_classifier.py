import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.neighbors import KNeighborsClassifier
from xgboost import XGBClassifier
from sklearn.preprocessing import MultiLabelBinarizer, StandardScaler, LabelBinarizer
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import KFold, GridSearchCV
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

import matplotlib.pyplot as plt
import pickle
import os
from collections import Counter
import numpy as np
import pickle
import json

from .classifier import Classifier
from .ml_features import create_text_features, create_entity_features, create_globe_coordinate_features, create_quantity_features, create_time_features, create_reverted_edit_features, create_property_replacement_features
from ..const import WD_ENTITY_TYPES, WD_STRING_TYPES, WD_BASIC_TYPES, ML_MODELS, ML_MODELS_LABELS, DATATYPE_INDEPENDENT_CLASSES, REVERTED_EDIT_LABEL, SOFT_DELETIONS, SOFT_INSERTIONS, PROPERTY_REPLACEMENT_LABEL, RANDOM_STATE

class MLClassifier(Classifier):
    def __init__(self, config):
        super().__init__(config)

    def run_classification(self):
        pass

    def get_features(self, dt_class, df):
        feature_cols = []
        label_encoder = None
            
        if  dt_class == 'text':
            df, feature_cols = create_text_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_STRING_TYPES)].reset_index(drop=True)

        elif dt_class == 'entity':

            df, feature_cols = create_entity_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_ENTITY_TYPES)].reset_index(drop=True)

        elif dt_class in WD_BASIC_TYPES:

            if dt_class == 'globecoordinate':
                df, feature_cols = create_globe_coordinate_features(df, feature_cols)
            elif dt_class == 'quantity':
                df, feature_cols = create_quantity_features(df, feature_cols)
            elif dt_class == 'time':
                df, feature_cols = create_time_features(df, feature_cols)

            df_type = df[df['datatype'] == dt_class].reset_index(drop=True)

        elif dt_class == REVERTED_EDIT_LABEL:
            df_type, feature_cols, label_encoder = create_reverted_edit_features(df, feature_cols)

        elif dt_class == PROPERTY_REPLACEMENT_LABEL:
            df_type, feature_cols, label_encoder = create_property_replacement_features(df, feature_cols)

        return df_type, feature_cols, label_encoder
    
    @staticmethod
    def perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config, all_labels=None):

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
            grid_search = GridSearchCV(RandomForestClassifier(RANDOM_STATE), param_grid=param_grid, cv=5)

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
            non_multilabel_model = GradientBoostingClassifier(random_state=RANDOM_STATE)

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

        elif classifier == 'XGBoost':
            param_grid = {
                'n_estimators': [50, 100, 150, 200],
                'max_depth': [3, 5, 7, 10],
                'objective': ['multi:softmax']
            }
            unique_classes = set(all_labels)
            num_classes = len(unique_classes)
            non_multilabel_model = XGBClassifier(objective='multi:softmax', num_class=num_classes, random_state=RANDOM_STATE)

            if is_multilabel: 

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

        grid_search.fit(X_scaled, y_binary)
        best_params = grid_search.best_params_
        if is_multilabel:
            # remove the prefix estimator__ from the result
            best_params = {
                key.replace('estimator__', ''): value 
                for key, value in best_params.items()
            }
        model_config[classifier][dt_class] = best_params

        with open('config/models_config.json', 'w') as config_file:
            json.dump(model_config, config_file, indent=4)

        return best_params

    @staticmethod
    def perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, classifier='Random_Forest'):
        is_multilabel = y_binary.shape[1] > 1 # shape[1] is number of columns (labels)

        model_config = {}

        if not is_multilabel:
            y_binary = y_binary.ravel() # for binary classification needs to be 1D

        if os.path.isfile('config/models_config.json'):
            with open('config/models_config.json', 'r') as config_file:
                model_config = json.load(config_file)
        
        if classifier not in model_config:
            model_config[classifier] = {}

        if dt_class not in model_config[classifier]:
            model_config[classifier][dt_class] = {}

        if classifier == 'Random_Forest': # already supports multi-label
            
            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = MLClassifier.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]
            
            model = RandomForestClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                class_weight='balanced', # this handles unbalanced classes
                random_state=RANDOM_STATE
            )

        if classifier == 'KN': # already supports multi-label

            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = MLClassifier.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]

            model = KNeighborsClassifier(n_neighbors=model_config[classifier][dt_class]['n_neighbors'])
        
        if classifier == 'Gradient_Boosting': # needs ensemble (MultiOutputClassifier) to support multi-label

            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = MLClassifier.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config)
            else:
                best_params = model_config[classifier][dt_class]
                
            # Base classifier
            base_model = GradientBoostingClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                random_state=RANDOM_STATE 
            )

            model = base_model
            if is_multilabel:
                model = MultiOutputClassifier(base_model)

        if classifier == 'XGBoost': # needs ensemble (MultiOutputClassifier) to support multi-label
            if not model_config.get(classifier, {}).get(dt_class, {}):
                best_params = MLClassifier.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config, all_labels)
            else:
                best_params = model_config[classifier][dt_class]
            
            unique_classes = set(all_labels)
            num_classes = len(unique_classes)

            # Base classifier
            base_model = XGBClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                num_classes=num_classes,
                random_state=RANDOM_STATE 
            )

            model = base_model
            if is_multilabel:
                model = MultiOutputClassifier(base_model)

        cv = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
        results_folds = []
        for fold, (train_index, test_index) in enumerate(cv.split(X_scaled), 1):
            X_train, X_test = X_scaled[train_index], X_scaled[test_index]
            y_train, y_test = y_binary[train_index], y_binary[test_index]

            metrics_results = {}

            if is_multilabel:
                # calculate accuracy per label 
                clf = model.fit(X_train, y_train)
                
                y_pred = clf.predict(X_test)
            
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
                
                metrics_results[dt_class] = {}
                
                metrics_results[dt_class]['accuracy'] = accuracy_score(y_test.ravel(), y_pred.ravel())
                metrics_results[dt_class]['precision'] = precision_score(y_test.ravel(), y_pred.ravel(), zero_division=0)
                metrics_results[dt_class]['recall'] = recall_score(y_test.ravel(), y_pred.ravel(), zero_division=0)
                metrics_results[dt_class]['f1'] = f1_score(y_test.ravel(), y_pred.ravel(), zero_division=0)

            results_folds.append({
                'classifier': classifier.lower(),
                'fold': fold,
                'metrics_results': metrics_results,
                'model': clf,
                'features': feature_cols,
                'train_index': train_index, 
                'test_index': test_index,
                'multi_label_binarizer': label_binarizer,
                'label_distribution': Counter(all_labels),
                'y_pred': y_pred,
                'y_test': y_test
            })

        return results_folds
    
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
        Create the following data structure:
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
        for model in ML_MODELS:
            print(f'Processing model: {model}')
            with open(f'datatype_classifiers_multilabel_{model}.pkl', 'rb') as f:
                classifiers = pickle.load(f)
            
            results[model] = {}
            
            # go over each fold's results for a single datatype
            for datatype, folds_info in classifiers.items():
                
                results[model][datatype] = {}
            
                overall_accuracy_all_folds = {}
                overall_precision_all_folds = {}
                overall_recall_all_folds = {}
                overall_f1_all_folds = {}

                num_folds = len(folds_info)

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

                # Calculate average metrics across all folds
                for label in overall_accuracy_all_folds.keys():

                    results[model][datatype][label] = {
                        'precision': overall_precision_all_folds[label] / num_folds,
                        'recall': overall_recall_all_folds[label] / num_folds,
                        'accuracy': overall_accuracy_all_folds[label] / num_folds,
                        'f1': overall_f1_all_folds[label] / num_folds
                    }

        """
            Re-order the data structure for visualization (barchart split into model -> metrics per datatype and label):

            "datatype": {
                "label":{
                    "model": {
                        "precision": float,
                        "recall": float,
                        "accuracy": float,
                        "f1": float
                    }
                }
            }
        """
        # re-order data structure for visualization
        results_dt_label_model = {}
        for model in results:
            for datatype in results[model]:
                if datatype not in results_dt_label_model:
                    results_dt_label_model[datatype] = {}
                
                for label in results[model][datatype]:
                    if label not in results_dt_label_model[datatype]:
                        results_dt_label_model[datatype][label] = {}
                    
                    results_dt_label_model[datatype][label][model] = results[model][datatype][label]

        return results_dt_label_model
    
    def metric_visualization(self):

        results_dt_label_model = MLClassifier.create_data_structure_for_visualization()

        models = ML_MODELS
        model_labels = ML_MODELS_LABELS
        metrics = ['precision', 'recall', 'accuracy', 'f1']

        # Count subplots
        total_plots = sum(len(results_dt_label_model[dt]) for dt in results_dt_label_model)
        ncols = 3
        nrows = (total_plots + ncols - 1) // ncols

        fig, axes = plt.subplots(nrows, ncols, figsize=(18, 5*nrows))
        axes = axes.flatten() if total_plots > 1 else [axes]

        plot_idx = 0
        for datatype in sorted(results_dt_label_model.keys()):
            for label in sorted(results_dt_label_model[datatype].keys()):
                ax = axes[plot_idx]
                
                x = np.arange(len(models))
                width = 0.25
                
                for i, metric in enumerate(metrics):
                    values = [results_dt_label_model[datatype][label][model][metric] for model in models] # metric (accuracy/precision/recall/f1) values for this label and datatype
                    
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
                ax.set_xticklabels(model_labels, rotation=45, ha='right', fontsize=9)
                ax.legend(loc='upper left', fontsize=9)
                ax.grid(axis='y', alpha=0.3)
                ax.set_ylim([0, 1.05])
                
                plot_idx += 1

        for idx in range(plot_idx, len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        plt.savefig('classifier_metrics_all.png', dpi=300, bbox_inches='tight')
        plt.show()

        # OVERALL: the best one seems to be gradient boosting, in some cases (not many) random forest does better

    def select_better_classifier():
        
        results_dt_label_model = MLClassifier.create_data_structure_for_visualization()
        score_per_model = {}
        for datatype in results_dt_label_model:
            for label in results_dt_label_model[datatype]:
                best_model = None
                best_f1 = 0
                for model in results_dt_label_model[datatype][label]:
                    if model not in score_per_model:
                        score_per_model[model] = 0

                    f1 = results_dt_label_model[datatype][label][model]['f1']
                    if f1 > best_f1:
                        best_f1 = f1
                        best_model = model
                print(f'Best model for datatype {datatype} and label {label}: {best_model} with F1: {best_f1:.3f}')
                
                score_per_model[best_model] += 1

        print('Overall best model:')
        best_score = 0
        best_model = None
        for model, score in score_per_model.items():
            if score > best_score:
                best_score = score
                best_model = model
            print(f'Model: {model}, Score: {score}')

        print(f'Overall best model is {best_model} with score {best_score}/ {sum(score_per_model.values())}')

    def train_classifier(self):
        
        df_gs = pd.read_csv('gold_standard/gold_standard.csv')

        datatypes_classes = WD_BASIC_TYPES + ['text', 'entity', REVERTED_EDIT_LABEL, PROPERTY_REPLACEMENT_LABEL] 
        # datatypes_classes = ['globecoordinate']
        classifiers_rf = {}
        classifiers_kn = {}
        classifiers_gb = {}
        classifiers_xgb = {}
        for dt_class in datatypes_classes:
            print(f"\n{'='*50}")
            print(f"Training classifier for: {dt_class}")
            print(f"{'='*50}")

            # Get + save the features
            if os.path.isfile(f'features/gs_features_{dt_class}.csv'):
                df = pd.read_csv(f'features/gs_features_{dt_class}.csv')
                with open(f'features/feature_cols_{dt_class}.pkl', 'rb') as f:
                    feature_cols = pickle.load(f)
            else:
                df = df_gs
                if dt_class in DATATYPE_INDEPENDENT_CLASSES: # reverted edit, property replacement have their own files
                    df = pd.read_csv(f'gold_standard/{dt_class}.csv')

                # df is already filtered per datatype inside get_features
                df, feature_cols, label_encoder = self.get_features(dt_class, df)
                os.makedirs('features', exist_ok=True)
                df.to_csv(f'features/gs_features_{dt_class}.csv', index=False)
                with open(f'features/feature_cols_{dt_class}.pkl', 'wb') as f:
                    pickle.dump(feature_cols, f)
                
                if label_encoder:
                    with open(f'features/label_encoder_{dt_class}.pkl', 'wb') as f:
                        pickle.dump(label_encoder, f)
            
            if dt_class == PROPERTY_REPLACEMENT_LABEL:
                # de duplicate by pair_id because the features are the same for all the rows in the group
                df = df.groupby('pair_id').first().reset_index() # keep only one row per pair_id
            
            # Fill NAN/Inf with 0
            X = df[feature_cols].astype(float).fillna(0) # features
            X.replace([np.inf, -np.inf], np.nan).fillna(0, inplace=True)
            
            # Remove zero-variance features
            zero_std_cols = X.columns[X.std() == 0]

            if len(zero_std_cols) > 0:
                X = X.drop(columns=zero_std_cols)
                print('Removed zero-variance features: ', zero_std_cols.tolist())
            
            # Scale
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            print('Mean after scaling: ', X_scaled.mean(axis=0))
            print('Std after scaling: ', X_scaled.std(axis=0))

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
                df['label'] = df['label'].fillna(f'non_{dt_class}')
                all_labels = df['label'].tolist() # fills nan with non_reverted_edit, non_property_replacement, etc.
                y_binary = label_binarizer.fit_transform(df['label'].fillna(''))

            classifiers_rf[dt_class] = MLClassifier.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, classifier='Random_Forest')
            classifiers_kn[dt_class] = MLClassifier.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, classifier='KN')
            classifiers_gb[dt_class] = MLClassifier.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, classifier='Gradient_Boosting')
            classifiers_xgb[dt_class] = MLClassifier.perform_kfold_training(X_scaled, y_binary, dt_class, label_binarizer, all_labels, feature_cols, classifier='XGBoost')

        if classifiers_rf:
            model = 'Random_Forest'.lower()
            print(model)
            with open(f'classifiers_multilabel_{model}.pkl', 'wb') as f:
                pickle.dump(classifiers_rf, f)

        if classifiers_kn:
            model = 'KN'.lower()
            with open(f'classifiers_multilabel_{model}.pkl', 'wb') as f:
                pickle.dump(classifiers_kn, f)

        if classifiers_gb:
            model = 'Gradient_Boosting'.lower()
            with open(f'classifiers_multilabel_{model}.pkl', 'wb') as f:
                pickle.dump(classifiers_gb, f) 

        if classifiers_xgb:
            model = 'XGBoost'.lower()
            with open(f'classifiers_multilabel_{model}.pkl', 'wb') as f:
                pickle.dump(classifiers_xgb, f)

