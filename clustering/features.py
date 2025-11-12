
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from sklearn.preprocessing import LabelEncoder
from Levenshtein import distance as levenshtein_distance
import time
import pandas as pd
import json

from const import WD_ENTITY_TYPES, WD_STRING_TYPES

##############################
# Text feature extraction
##############################

"""
Useful to use ratios for levenshtein distance because they give you a percentage of what changed.

Example 1:
- Old: "cat"
- New: "dog"
- Levenshtein distance: 3

Without ratio: distance = 3 

With ratio: 3 / 3 = 1 (100% changed)

Example 2:
- Old: "The quick brown fox jumps over the lazy dog"
- New: "The quick brown fox jumps over the lazy cat"
- Levenshtein distance: 3 (dog -> cat)

Without ratio: distance = 3 (same as before)

With ratio: 3 / 44 = 0.068 (only 6.8% changed)

"""

def extract_text_features(df, old_col, new_col, mask):

    if mask.sum() == 0:
        return df
    
    subset = df.loc[mask].copy()
    
    subset['old'] = subset[old_col].astype(str)
    subset['new'] = subset[new_col].astype(str)
    
    valid = (subset['old'] != '{}') & (subset['new'] != '{}') & (subset['old'] != 'nan') & (subset['new'] != 'nan')
    subset = subset[valid]
    
    if len(subset) == 0:
        return df
    
    subset['length_diff_abs'] = (subset['new'].str.len() - subset['old'].str.len()).abs()
    
    subset['case_differs'] = (
        (subset['old'] != subset['new']) & 
        (subset['old'].str.lower() == subset['new'].str.lower())
    ).astype(int)
    
    old_no_space = subset['old'].str.replace(' ', '', regex=False)
    new_no_space = subset['new'].str.replace(' ', '', regex=False)
    subset['spaces_differs'] = (
        (subset['old'] != subset['new']) & 
        (old_no_space == new_no_space)
    ).astype(int)
    
    old_no_punct = subset['old'].str.replace(r'[^\w\s]', '', regex=True).str.replace(' ', '', regex=False)
    new_no_punct = subset['new'].str.replace(r'[^\w\s]', '', regex=True).str.replace(' ', '', regex=False)
    subset['punct_differs'] = (
        (subset['old'] != subset['new']) & 
        (old_no_punct == new_no_punct)
    ).astype(int)
    
    old_no_dash = subset['old'].str.replace(r'[-–—_]', '', regex=True).str.replace(' ', '', regex=False)
    new_no_dash = subset['new'].str.replace(r'[-–—_]', '', regex=True).str.replace(' ', '', regex=False)
    subset['hyph_dash_differs'] = (
        (subset['old'] != subset['new']) & 
        (old_no_dash == new_no_dash)
    ).astype(int)
    
    old_no_brackets = subset['old'].str.replace(r'[\[\]\(\)\{\}"\']', '', regex=True).str.replace(' ', '', regex=False)
    new_no_brackets = subset['new'].str.replace(r'[\[\]\(\)\{\}"\']', '', regex=True).str.replace(' ', '', regex=False)
    subset['brackets_differs'] = (
        (subset['old'] != subset['new']) & 
        (old_no_brackets == new_no_brackets)
    ).astype(int)
    
    subset['token_count_old'] = subset['old'].str.split().str.len()
    subset['token_count_new'] = subset['new'].str.split().str.len()
    
    def calc_overlap(row):
        old_tokens = set(row['old'].split())
        new_tokens = set(row['new'].split())
        if len(old_tokens | new_tokens) == 0:
            return 0
        return len(old_tokens & new_tokens) / len(old_tokens | new_tokens)
    
    # percentage (ratio) of token overlap
    subset['token_overlap'] = subset.apply(calc_overlap, axis=1)
    
    subset['old_in_new'] = subset.apply(lambda row: int(row['old'] in row['new']), axis=1)
    subset['new_in_old'] = subset.apply(lambda row: int(row['new'] in row['old']), axis=1)
        
    subset['levenshtein_distance'] = subset.apply(
        lambda row: levenshtein_distance(row['old'].lower().strip(), row['new'].lower().strip()),
        axis=1
    )

    old_len = subset['old'].str.len()
    new_len = subset['new'].str.len()
    max_len = np.maximum(old_len, new_len).clip(lower=1) # replace 0's with 1 to avoid division by zero

    # percentage of how much changed
    subset['edit_distance_ratio'] = subset['levenshtein_distance'] / max_len
    
    feature_cols = ['levenshtein_distance', 'length_diff_abs', 'case_differs', 
                'spaces_differs', 'punct_differs', 'hyph_dash_differs', 
                'brackets_differs', 'token_count_old', 'token_count_new', 
                'token_overlap', 'old_in_new', 'new_in_old', 'edit_distance_ratio']

    for col in feature_cols:
        df.loc[subset.index, col] = subset[col]
    
    return df, feature_cols

def create_semantic_similarity_features(df, old_col, new_col, feature_cols, string_mask):
    """
    Calculates cosine similarity between old and new value embeddings
    """
    
    if string_mask.sum() == 0:
        return df, feature_cols
    
    subset = df[string_mask].copy()
    
    if 'label' in old_col:
        # entity changes -> add the entity label as context
        for _, row in subset.iterrows():
            entity = str(row['entity_label'])
            prop = str(row['property_label'])
            old_val = str(row[old_col])
            new_val = str(row[new_col])
            
            old_texts.append(f"Entity: {entity}, {prop}: {old_val}")
            new_texts.append(f"Entity: {entity}, {prop}: {new_val}")
    else:
        # add the property label to provide context
        old_texts = [
            f"{prop}: {old}" 
            for prop, old in zip(subset['property_label'].astype(str), subset[old_col].astype(str))
        ]
        new_texts = [
            f"{prop}: {new}" 
            for prop, new in zip(subset['property_label'].astype(str), subset[new_col].astype(str))
        ]
    
    # load model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    old_embeddings = model.encode(
        old_texts,
        device="mps",
        show_progress_bar=True
    )
    
    new_embeddings = model.encode(
        new_texts,
        device="mps",
        show_progress_bar=True
    )
    
    # calculate cosine similarity
    similarities = np.array([
        cosine_similarity([old_emb], [new_emb])[0][0]
        for old_emb, new_emb in zip(old_embeddings, new_embeddings)
    ])
    
    subset['semantic_similarity'] = similarities
    
    # update original df
    df.loc[string_mask, 'semantic_similarity'] = subset['semantic_similarity']
    
    feature_cols.append('semantic_similarity')
    
    return df, feature_cols

def create_text_features(df, feature_cols, semantic_similarity=True):
    """Extract text features for string datatypes"""
    string_mask = df['datatype'].isin(WD_STRING_TYPES)
    
    print(f"Creating basic features.")
    start_time = time.time()
    df, feature_cols = extract_text_features(df, 'old_value', 'new_value', string_mask)
    end_time = time.time()
    print(f"Basic features created in {end_time - start_time:.2f} seconds.")
    
    if semantic_similarity:
        print('Creating semantic similarity from embeddings.')
        start_time = time.time()
        df, feature_cols = create_semantic_similarity_features(df, 'old_value', 'new_value', feature_cols, string_mask)
        end_time = time.time()
        print(f"Semantic similarity features created in {end_time - start_time:.2f} seconds.")

    df, feature_cols = extract_general_change_features(df, feature_cols)

    return df, feature_cols

##############################
# Time feature extraction
##############################
def create_time_features(df, feature_cols):
    """
    Extract time change features
    """
    time_mask = (df['datatype'] == 'time')
    
    if time_mask.sum() == 0:
        return df
    
    def parse_wikidata_time(time_str):
        try:
            time_str = str(time_str).lstrip('+')
            return pd.to_datetime(time_str, format='%Y-%m-%dT%H:%M:%SZ')
        except:
            return pd.NaT
    
    df.loc[time_mask, 'old_time_parsed'] = df.loc[time_mask, 'old_value'].apply(parse_wikidata_time)
    df.loc[time_mask, 'new_time_parsed'] = df.loc[time_mask, 'new_value'].apply(parse_wikidata_time)
    
    valid_mask = time_mask & df['old_time_parsed'].notna() & df['new_time_parsed'].notna()
    
    if valid_mask.sum() == 0:
        return df
    
    try:
        df.loc[valid_mask, 'time_diff_days'] = (
            df.loc[valid_mask, 'new_time_parsed'] - df.loc[valid_mask, 'old_time_parsed']
        ).dt.days.abs()
    except (OverflowError, ValueError):
        # Fallback: calculate manually using timestamps (seconds since epoch)
        old_timestamps = df.loc[valid_mask, 'old_time_parsed'].astype('int64') / 10**9  # Convert to seconds
        new_timestamps = df.loc[valid_mask, 'new_time_parsed'].astype('int64') / 10**9
        df.loc[valid_mask, 'time_diff_days'] = ((new_timestamps - old_timestamps) / 86400).abs()
    
    df.loc[valid_mask, 'time_diff_years'] = df.loc[valid_mask, 'time_diff_days'] / 365.25

    feature_cols.extend([
        'time_diff_days',
        'time_diff_years',
    ])

    return df, feature_cols

##############################
# Quantity feature extraction
##############################
def create_quantity_features(df, feature_cols):
    quant_mask = df['datatype'] == 'quantity'
    
    if quant_mask.sum() == 0:
        return df, feature_cols

    subset = df[quant_mask].copy()
    
    # remove + sign
    subset['old_str'] = subset['old_value'].astype(str).str.replace('+', '', regex=False)
    subset['new_str'] = subset['new_value'].astype(str).str.replace('+', '', regex=False)
    
    subset['old_float'] = pd.to_numeric(subset['old_str'], errors='coerce')
    subset['new_float'] = pd.to_numeric(subset['new_str'], errors='coerce')
    
    valid_mask = subset['old_float'].notna() & subset['new_float'].notna()
    
    # value diff absolute
    subset.loc[valid_mask, 'value_diff_abs'] = (
        subset.loc[valid_mask, 'new_float'] - subset.loc[valid_mask, 'old_float']
    ).abs()
    
    # sign change 
    subset.loc[valid_mask, 'sign_change'] = (
        subset.loc[valid_mask, 'old_float'] * subset.loc[valid_mask, 'new_float'] < 0
    ).astype(int)
    
    # precision difference 
    def get_decimal_places(val_str):
        val_str = str(val_str)
        if '.' in val_str:
            decimal_part = val_str.split('.')[1] if len(val_str.split('.')) > 1 else ''
            return len(decimal_part)
        elif ',' in val_str:
            decimal_part = val_str.split(',')[1] if len(val_str.split(',')) > 1 else ''
            return len(decimal_part)
        else:
            return 0
    
    subset.loc[valid_mask, 'old_decimal_places'] = subset.loc[valid_mask, 'old_str'].apply(get_decimal_places)
    subset.loc[valid_mask, 'new_decimal_places'] = subset.loc[valid_mask, 'new_str'].apply(get_decimal_places)
    
    subset.loc[valid_mask, 'precision_diff_abs'] = (
        subset.loc[valid_mask, 'new_decimal_places'] - subset.loc[valid_mask, 'old_decimal_places']
    ).abs()
    
    # add changes to original df
    df.loc[quant_mask, 'value_diff_abs'] = subset['value_diff_abs']
    df.loc[quant_mask, 'sign_change'] = subset['sign_change']
    df.loc[quant_mask, 'precision_diff_abs'] = subset['precision_diff_abs']
    
    feature_cols.extend([
        'value_diff_abs',
        'sign_change',
        'precision_diff_abs'
    ])
    
    return df, feature_cols

##############################
# Globe coordinate feature extraction
##############################
def create_globe_coordinate_features(df, feature_cols):
    coordinate_mask = df['datatype'] == 'globecoordinate'
    
    for idx in df[coordinate_mask].index:
        try:
            old_val = json.loads(df.loc[idx, 'old_value'])
            new_val = json.loads(df.loc[idx, 'new_value'])
            
            df.loc[idx, 'latitude_diff_abs'] = abs(new_val['latitude'] - old_val['latitude'])
            df.loc[idx, 'longitude_diff_abs'] = abs(new_val['longitude'] - old_val['longitude'])
            
            # distance with haversine formula
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(old_val['latitude']), radians(old_val['longitude'])
            lat2, lon2 = radians(new_val['latitude']), radians(new_val['longitude'])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance_km = 6371 * c  # Earth radius in km
            
            df.loc[idx, 'coordinate_distance_km'] = distance_km

        except:
            pass

    feature_cols.extend([
        'latitude_diff_abs',
        'longitude_diff_abs',
        'coordinate_distance_km'
    ])

    return df, feature_cols

##############################
# Genearl feature extraction
##############################
def create_entity_features(df, feature_cols):
    """Extract features for entity datatypes using labels"""
    entity_mask = df['datatype'].isin(WD_ENTITY_TYPES)
    
    print(f"Processing {entity_mask.sum()} entity changes.")
    df, feature_cols = extract_text_features(df, 'old_value_label', 'new_value_label', entity_mask)

    print('Creating semantic similarity from embeddings.')
    start_time = time.time()
    df, feature_cols = create_semantic_similarity_features(df, 'old_value_label', 'new_value_label', feature_cols, entity_mask)
    end_time = time.time()
    print(f"Semantic similarity features created in {end_time - start_time:.2f} seconds.")
    
    return df, feature_cols

##############################
# Genearl feature extraction
##############################
def extract_general_change_features(df, feature_cols):
    """
    General features
    """
    df = df.copy()

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['is_weekend'] = df['day_of_week'].isin(['Saturday', 'Sunday']).astype(int)

    label_encoders = {}
    categorical_cols = [
        'user_type',  # bot/human/anonymous
        'day_of_week',
        'hour_of_day',
        'is_weekend'
    ]
    
    for col in categorical_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f'{col}_encoded'] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le

    feature_cols.extend([
        'user_type_encoded',
        'day_of_week_encoded',
        'hour_of_day_encoded',
        'is_weekend_encoded',
        'num_changes_in_revision',
        'entity_age_days'
    ])

    return df, feature_cols