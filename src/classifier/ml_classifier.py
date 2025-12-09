import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score
import pickle

from .classifier import Classifier
from ml_features import create_text_features, create_entity_features, create_globe_coordinate_features, create_quantity_features, create_time_features, extract_general_change_features
from ..const import WD_ENTITY_TYPES, WD_STRING_TYPES, WD_BASIC_TYPES

class MLClassifier(Classifier):
    def __init__(self, config):
        super().__init__(config)
    
    def train_text_classifier(self, datatype):

        df = pd.read_csv('gold_standard/gold_standard_latest.csv')

        datatypes = WD_BASIC_TYPES + ['text', 'entity']
        classifiers = {}

        for datatype in datatypes:
            print(f"\n{'='*50}")
            print(f"Training classifier for: {datatype}")
            print(f"{'='*50}")
            
            if  datatype == 'text':

                df_type = df[df['datatype'].isin(WD_STRING_TYPES)]
                print(df_type[(df_type['datatype'].isin(WD_STRING_TYPES))].groupby('label').size())
                df_type, feature_cols = create_text_features(df_type)

            elif datatype == 'entity':

                df_type = df[df['datatype'].isin(WD_ENTITY_TYPES)]
                print(df_type[(df_type['datatype'].isin(WD_ENTITY_TYPES))].groupby('label').size())
                df_type, feature_cols = create_entity_features(df_type)

            elif datatype in WD_BASIC_TYPES:

                df_type = df[df['datatype'].isin(WD_BASIC_TYPES)]
                print(df_type[(df_type['datatype'].isin(WD_BASIC_TYPES))].groupby('label').size())

                if datatype == 'globecoordinate':
                    df_type, feature_cols = create_globe_coordinate_features(df_type)
                elif datatype == 'quantity':
                    df_type, feature_cols = create_quantity_features(df_type)
                elif datatype == 'time':
                    df_type, feature_cols = create_time_features(df_type)
                
            
            X = df_type[feature_cols].fillna(0) # features
            y = df_type['label']
            
            rf = RandomForestClassifier(
                n_estimators=50,
                max_depth=5,
                min_samples_leaf=3,
                class_weight='balanced',
                random_state=42
            )
            
            # Cross-validation
            cv = StratifiedKFold(n_splits=min(5, len(df_type)//20), shuffle=True, random_state=42)
            
            cv_scores = cross_val_score(rf, X, y, cv=cv, scoring='f1_weighted', n_jobs=-1)
            
            print(f"CV F1-Score: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})")
            
            # Train final model
            rf.fit(X, y)
            classifiers[datatype] = {
                'model': rf,
                'features': feature_cols,
                'cv_score': cv_scores.mean()
            }
        
        with open('datatype_classifiers.pkl', 'wb') as f:
            pickle.dump(classifiers, f)