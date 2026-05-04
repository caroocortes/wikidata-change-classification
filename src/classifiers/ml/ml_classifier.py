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

import io
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
from src.sql_runner.sql_runner import SQLRunner


class MLClassifier(BaseClassifier):
    def __init__(self, config_path: str):
        super().__init__(config_path=config_path)

        self.random_state = self.config.get('random_state', 42)
        self.fold_splits = self.config.get('fold_splits', 5)
        self.prob_threshold = self.config.get('prob_threshold', 0.5)

        self.runtimes = dict()

    # ------------------------------------------------------------------------
    # Methods to train models
    # ------------------------------------------------------------------------
    def get_features(self, dt_class, df):
        feature_cols = []
            
        if  dt_class == 'text':
            df, feature_cols = create_text_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_STRING_TYPES)]

        elif dt_class == 'entity':

            df, feature_cols = create_entity_features(df, feature_cols)
            df_type = df[df['datatype'].isin(WD_ENTITY_TYPES)]

        elif dt_class in WD_BASIC_TYPES:

            if dt_class == 'globecoordinate_latitude' or dt_class == 'globecoordinate_longitude':
                df, feature_cols = create_globe_coordinate_features(df, feature_cols)
            elif dt_class == 'quantity':
                df, feature_cols = create_quantity_features(df, feature_cols)
            elif dt_class == 'time':
                df, feature_cols = create_time_features(df, feature_cols)

            if dt_class == 'globecoordinate_latitude' or dt_class == 'globecoordinate_longitude':
                df_type = df[df['datatype'] == 'globecoordinate']
            else:
                df_type = df[df['datatype'] == dt_class]

        elif dt_class == REVERTED_EDIT_LABEL:
            df_type, feature_cols = create_reverted_edit_features(df, feature_cols)

        elif dt_class == PROPERTY_REPLACEMENT_LABEL:
            df_type, feature_cols = create_property_replacement_features(df, feature_cols)

        return df_type, feature_cols
    
    def perform_grid_search(self, classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config, cv):
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

        if model_config.get(classifier, {}).get(dt_class, {}) != {}: # best params already calcualted -> just return them
            print('Grid search already performed. Loading best params')
            best_params = model_config[classifier][dt_class]
            return best_params
        
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
            grid_search = GridSearchCV(RandomForestClassifier(self.random_state), param_grid=param_grid, cv=cv)

        elif classifier == 'KN':
            param_grid = {
                'n_neighbors': [3, 5, 7, 10, 15, 20, 25, 30]
            }
            grid_search = GridSearchCV(KNeighborsClassifier(), param_grid=param_grid, cv=cv)

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
                    cv=cv
                )
            else:
                grid_search = GridSearchCV(non_multilabel_model, param_grid=param_grid, cv=cv)

        elif classifier == 'XGBoost': # does not require meta model for multi-label
            param_grid = {
                'n_estimators': [50, 100, 150, 200],
                'max_depth': [3, 5, 7, 10]
            }

            grid_search = GridSearchCV(XGBClassifier(random_state=self.random_state), param_grid=param_grid, cv=cv)

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

    def get_model_instance(self, classifier, is_multilabel, best_params):
        """
            Returns model instance for the specified classifier.
            If the parameters for the model have already been optimized, they are loaded from model_config. If not, 
            grid search is performed to find the best parameters
        """
        
        if classifier == 'Random_Forest': # already supports multi-label
            
            model = RandomForestClassifier(
                n_estimators=best_params['n_estimators'], 
                max_depth=best_params['max_depth'],
                class_weight='balanced', # this handles unbalanced classes
                random_state=self.random_state
            )

        elif classifier == 'KN': # already supports multi-label

            model = KNeighborsClassifier(n_neighbors=best_params['n_neighbors'])
        
        elif classifier == 'Gradient_Boosting': # needs ensemble (MultiOutputClassifier) to support multi-label
                
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

        # do grid search to get best params (if grid search was performed before, just reads the stored best params)
        best_params = self.perform_grid_search(classifier, is_multilabel, dt_class, X_scaled, y_binary, model_config, cv)

        start_time = time.time()
        for fold, (train_index, test_index) in enumerate(split, 1):

            model, base_model = self.get_model_instance(classifier, is_multilabel, best_params)

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
                # 'train_index': train_index, 
                # 'test_index': actual_test_index,
                'multi_label_binarizer': label_binarizer,
                # 'label_distribution': Counter(all_labels),
                # 'X_test': X_test,
                # 'y_pred': y_pred,
                # 'y_test': y_test
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
    
    def train_classifier(self):
        os.makedirs(FEATURES_DIR, exist_ok=True)
        
        datatypes_classes = WD_BASIC_TYPES + ['text', 'entity'] 

        classifiers_rf = dict()
        classifiers_kn = dict()
        classifiers_gb = dict()
        classifiers_xgb = dict()
        
        scalers = dict()
        for dt_class in datatypes_classes:
            print(f"\n{'='*50}")
            print(f"Training classifier for: {dt_class}")
            print(f"{'='*50}")

            if dt_class == 'globecoordinate_latitude' or dt_class == 'globecoordinate_longitude':
                df_gs = pd.read_csv(f'{GOLD_STANDARD_DIR}/wikidata_edit_history_labeled_changes_globecoordinate.csv')
            else:
                df_gs = pd.read_csv(f'{GOLD_STANDARD_DIR}/wikidata_edit_history_labeled_changes.csv')

            #############################
            #   Load or create features
            #############################
            if os.path.isfile(f'{FEATURES_DIR}/gs_features_{dt_class}.csv'):
                df = pd.read_csv(f'{FEATURES_DIR}/gs_features_{dt_class}.csv', index_col=0)
                with open(f'{FEATURES_DIR}/feature_cols_{dt_class}.pkl', 'rb') as f:
                    feature_cols = pickle.load(f)

                print('Features already exist, loading.')
            else:
                print('Features dont exist, creating.')
                df = df_gs
                if dt_class in DATATYPE_INDEPENDENT_CLASSES: # reverted edit, property replacement have their own files
                    df = pd.read_csv(f'{GOLD_STANDARD_DIR}/{dt_class}.csv')

                # df is already filtered per datatype inside get_features
                df, feature_cols = self.get_features(dt_class, df)

                os.makedirs(FEATURES_DIR, exist_ok=True)
                df.to_csv(f'{FEATURES_DIR}/gs_features_{dt_class}.csv', index=True)

            if dt_class == 'globecoordinate_latitude':
                df = df[df['label_latitude'].notna()]  # only rows where latitude changed
                df['label'] = df['label_latitude']     # use latitude label
            elif dt_class == 'globecoordinate_longitude':
                df = df[df['label_longitude'].notna()] # only rows where longitude changed
                df['label'] = df['label_longitude']    # use longitude label
            
            if dt_class == PROPERTY_REPLACEMENT_LABEL:
                # de duplicate by pair_id because the features are the same for all the rows in the group, then I would have duplicated rows
                df = df.groupby('pair_id', as_index=False).first() # keep only one row per pair_id
            
            # Fill NAN/Inf with 0
            X = df[feature_cols].astype(float).fillna(0) # features
            print(X.shape)
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
        
    # ------------------------------------------------------------------------
    # Methods to classify changes with the trained models
    # ------------------------------------------------------------------------
    def classify_batch(self, df, X, X_index, dt_label):
        """
            We do ensemble voting with the models from all folds
            Make all models prdict, average the prob for the classes across all folds, pick the probs that are > 0.5
            If no prob is > 0.5, take the highest one (this inherently means that change will only have one label assigned, 
            for the other cases multiple labels may be assigned)
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
            # in my case it would be 1 array per label, so for refinement: [[prob_no_refinement_cahnge_1, prob_refinement_change_1], [prob_no_refinement_change_2, prob_refinement_change_2]]
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
        results_df = df.join(pred_df)

        # For globecoordinate changes, it can happen that only the lat/long changes
        # not necessarily both. Therefore, I apply the same logic as the other one and then just check, 
        # if they didn't change, I wipe the label
        if dt_label == 'globecoordinate_latitude':
            no_change_mask = results_df['latitude_old'].apply(lambda x: float(x) if x else None) == \
                             results_df['latitude_new'].apply(lambda x: float(x) if x else None)
            results_df.loc[no_change_mask, 'predicted_labels'] = ''

        elif dt_label == 'globecoordinate_longitude':
            no_change_mask = results_df['longitude_old'].apply(lambda x: float(x) if x else None) == \
                             results_df['longitude_new'].apply(lambda x: float(x) if x else None)
            results_df.loc[no_change_mask, 'predicted_labels'] = ''

        return results_df
    
    def classify_changes(self, dt_label, table_prefix, batch_size=1000000, max_batches=None, db_config_path=None):
        """
            Classify changes for a single datatye/label in smaller batches.
        """
        self.logger.info(f'Starting classification for {dt_label} with batch size {batch_size}')
        
        with open(f'{FEATURES_DIR}/feature_cols_{dt_label}.pkl', 'rb') as f:
            feature_cols = pickle.load(f)
        
        feature_cols_str = ', '.join(feature_cols)

        if dt_label in ('entity', 'text', 'time', 'quantity', 'globecoordinate_latitude', 'globecoordinate_longitude'):
            key_cols = BASE_KEY_TYPES.keys()
        else: # property_replacement
            key_cols = PROP_REP_KEY_TYPES.keys()

        key_cols_str = ', '.join(key_cols)

        table_name = dt_label
        label_column = 'label'
        add_old_new = False
        
        if dt_label == 'globecoordinate_latitude':
            label_column = 'label_latitude'
            table_name = 'globecoordinate'
            add_old_new = True
            old_new_cols = 'latitude_old, latitude_new'
        elif dt_label == 'globecoordinate_longitude':
            label_column = 'label_longitude'
            table_name = 'globecoordinate'
            add_old_new = True
            old_new_cols = 'longitude_old, longitude_new'
        
        if db_config_path:
            sql_runner = SQLRunner(db_config_path)
            conn = sql_runner.get_connection()
            cursor = conn.cursor()

            if dt_label in ('time', 'quantity', 'text', 'globecoordinate_latitude', 'globecoordinate_longitude', 'entity'):
                    key_cols_temp = ', '.join([f'{col} {col_type}' for col, col_type in BASE_KEY_TYPES.items()])
            else:
                key_cols_temp = ', '.join([f'{col} {col_type}' for col, col_type in PROP_REP_KEY_TYPES.items()])
            
            cursor.execute(f"CREATE TEMP TABLE temp_predictions_{dt_label} ({key_cols_temp}, predicted_labels TEXT)")

            num_batches = 0

            while True:

                if max_batches and num_batches >= max_batches:
                    print(f'Loaded {max_batches} batches from DB')
                    break

                time_0 = time.time()
                query = f"""
                    SELECT {key_cols_str}, {feature_cols_str}{', ' + old_new_cols if add_old_new else ''}
                    FROM features_{table_name}{table_prefix}
                    WHERE {label_column} = ''
                    LIMIT {batch_size}
                """
                df = sql_runner.query_to_df(query)
                conn.commit() # close read transaction to release locks

                time_1 = time.time()
                self.logger.info(f'Finished loading batch {num_batches+1} from DB, took {time_1 - time_0:.2f} seconds')
                
                if len(df) == 0:
                    break
                
                # Classify
                X = df.drop(columns=key_cols) # drop key columns, just keep features

                if add_old_new: # drop the old_new columns, just keep the features
                    old_new_cols_list = old_new_cols.split(', ')
                    X = X.drop(columns=old_new_cols_list)

                time_0  = time.time()
                results = self.classify_batch(df, X, df.index, dt_label)
                time_1 = time.time()
                self.logger.info(f'Finished classifying batch {num_batches+1}, took {time_1 - time_0:.2f} seconds')

                key_cols_list = list(key_cols)
                results_filtered = results[key_cols_list + ['predicted_labels']]

                buffer = io.StringIO()
                results_filtered.to_csv(buffer, index=False, header=False, sep=';', quoting=csv.QUOTE_NONE, escapechar='\\')
                buffer.seek(0)

                start_time = time.time()
                cursor.copy_expert(f"COPY temp_predictions_{dt_label} FROM STDIN (FORMAT CSV, DELIMITER ';' , QUOTE '\"', ESCAPE '\\')", buffer)
                elapsed_time = time.time() - start_time
                self.logger.info(f'Finished loading to temp table in {elapsed_time:.2f} seconds')

                start_time = time.time()
                # Update labels
                cursor.execute(f"""
                    UPDATE features_{table_name}{table_prefix} f
                    SET {label_column} = tp.predicted_labels
                    FROM temp_predictions_{dt_label} tp 
                    WHERE 
                        {' AND '.join([f'f.{key_col} = tp.{key_col}' if key_col != 'change_target' else f"COALESCE(f.{key_col}, '') = COALESCE(tp.{key_col}, '')" for key_col in key_cols])}
                """)
                elapsed_time = time.time() - start_time
                final_time, unit = get_time_unit(elapsed_time)
                self.logger.info(f'Finished updating table in {final_time} {unit}')

                cursor.execute(f"TRUNCATE TABLE temp_predictions_{dt_label}")

                conn.commit()

                num_batches += 1
            
            self.logger.info(f'Classified {num_batches} batches from DB for {dt_label}')

        else:
            print('No DB config provided, cannot classify in batches from DB')
            return
            

    # ------------------------------------------------------------------------------------------------
    # Methods to calculate evaluation metrics for the model + best model selection
    # ------------------------------------------------------------------------------------------------
    
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
        """
        Selects best classifier based on:
            - number of classification tasks they have highest F1
        if multiple models are best in the same number of classification tasks:
            - the best model is the one that has best F1 avg across all classification tasks
        """

        score_per_model = {}
        df_data = {
            'datatype': [],
            'label': [],
            'best_model': [],
            'best_f1': []
        }
        
        for datatype in results_dt_label_model:
            for label in results_dt_label_model[datatype]:
                best_f1 = -1
                best_models = []
                for model in results_dt_label_model[datatype][label]:
                    if model not in score_per_model:
                        score_per_model[model] = 0
                    
                    f1 = results_dt_label_model[datatype][label][model]['f1']
                    
                    print(f'Model: {model}', f'F1: {f1:.5f}', 'Datatype:', datatype, 'Label:', label)
                    
                    if f1 > best_f1:
                        best_f1 = f1
                        best_models = [model] # reset with a new best model
                    elif f1 == best_f1: # more than 1 model has best f1
                        best_models.append(model) 

                df_data['datatype'].append(datatype)
                df_data['label'].append(label)
                df_data['best_model'].append(', '.join(best_models))
                df_data['best_f1'].append(best_f1)
                
                for model in best_models:
                    score_per_model[model] += 1

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
                'Mean F1': np.mean(model_averages[model]['f1']),
                'Mean Precision': np.mean(model_averages[model]['precision']),
                'Mean Recall': np.mean(model_averages[model]['recall']),
                'Mean Accuracy': np.mean(model_averages[model]['accuracy'])
            })

        df_summary = pd.DataFrame(summary_stats)
        df_summary.to_csv(f'{TRAINING_RESULTS}/summary_all_models.csv')
        print("\nModel Performance Summary (across all classification tasks):")
        display(df_summary.to_string(index=False))

        best_model_f1 = None
        best_f1 = 0
        for i, stats in enumerate(summary_stats):
            if stats['Mean F1'] > best_f1:
                best_f1 = stats['Mean F1']
                best_model_f1 = stats['Model']
        
        print(f'Model with best F1 across all classification tasks is {best_model_f1} with an avg. F1 of {best_f1}')

        print(f'Saved summary stats to {TRAINING_RESULTS}/summary_all_models.csv')

        with open(f'{TRAINING_INFO_DIR}/training_info_{best_model_f1}.pkl', 'rb') as f:
            training_info_model = pickle.load(f)

        with open(f'{TRAINING_RESULTS}/best_model_training_info.pkl', 'wb') as f:
            pickle.dump(training_info_model, f)
        
    
    def evaluate(self):
        results_dt_label_model = MLClassifier.create_data_structure_for_visualization()

        MLClassifier.metric_visualization(results_dt_label_model)

        MLClassifier.select_best_classifier(results_dt_label_model)
    
        return results_dt_label_model
