
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder

from Levenshtein import distance as levenshtein_distance
import time
import pandas as pd
import numpy as np
import json
import math
import os

from src.const import WD_ENTITY_TYPES, WD_STRING_TYPES


os.environ["TOKENIZERS_PARALLELISM"] = "false"

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

def extract_text_features(df, old_col, new_col, mask=None):
    
    df_string = df[mask].copy() if mask is not None else df.copy()

    # NOTE: old_col / new_col can be old_value / new_Value or old_value_label / new_value_label
    df_string['old'] = df_string[old_col].astype(str).str.replace('"', '')
    df_string['new'] = df_string[new_col].astype(str).str.replace('"', '')
    
    valid = (df_string['old'] != '{}') & (df_string['new'] != '{}') & (df_string['old'] != 'nan') & (df_string['new'] != 'nan')
    df_string = df_string[valid]
    
    if len(df_string) == 0:
        return df_string
    
    df_string['length_diff_abs'] = (df_string['new'].str.len() - df_string['old'].str.len()).abs()
    
    # if 'label' not in old_col: # remove for entity
    #     df_string['case_differs'] = (
    #         (df_string['old'] != df_string['new']) & 
    #         (df_string['old'].str.lower() == df_string['new'].str.lower())
    #     ).astype(int)
    
    # if 'label' not in old_col: # remove for entity
    #     old_no_space = df_string['old'].str.replace(' ', '', regex=False)
    #     new_no_space = df_string['new'].str.replace(' ', '', regex=False)
    #     df_string['spaces_differs'] = (
    #         (df_string['old'] != df_string['new']) & 
    #         (old_no_space == new_no_space)
    #     ).astype(int)
    
    # old_no_punct = df_string['old'].str.replace(r'[^\w\s]', '', regex=True)
    # new_no_punct = df_string['new'].str.replace(r'[^\w\s]', '', regex=True)
    # df_string['punct_differs'] = (
    #     (df_string['old'] != df_string['new']) & 
    #     (old_no_punct == new_no_punct)
    # ).astype(int)
    
    # if 'label' not in old_col: # remove for entity
    #     old_no_dash = df_string['old'].str.replace(r'[-–—_]', '', regex=True)
    #     new_no_dash = df_string['new'].str.replace(r'[-–—_]', '', regex=True)
    #     df_string['hyph_dash_differs'] = (
    #         (df_string['old'] != df_string['new']) & 
    #         (old_no_dash == new_no_dash)
    #     ).astype(int)
    
    # if 'label' not in old_col: # remove for entity
    #     old_no_brackets = df_string['old'].str.replace(r'[\[\]\(\)\{\}"\']', '', regex=True)
    #     new_no_brackets = df_string['new'].str.replace(r'[\[\]\(\)\{\}"\']', '', regex=True)
    #     df_string['brackets_differs'] = (
    #         (df_string['old'] != df_string['new']) & 
    #         (old_no_brackets == new_no_brackets)
    #     ).astype(int)
    
    df_string['token_count_old'] = df_string['old'].str.split().str.len()
    df_string['token_count_new'] = df_string['new'].str.split().str.len()
    
    def calc_overlap(row):
        old_tokens = set(row['old'].split())
        new_tokens = set(row['new'].split())
        if len(old_tokens | new_tokens) == 0:
            return 0
        # | is union
        # & is intersection
        return len(old_tokens & new_tokens) / len(old_tokens | new_tokens)
    
    # percentage (ratio) of token overlap
    df_string['token_overlap'] = df_string.apply(calc_overlap, axis=1)
    
    df_string['old_in_new'] = df_string.apply(lambda row: int(row['old'] in row['new']), axis=1)
    df_string['new_in_old'] = df_string.apply(lambda row: int(row['new'] in row['old']), axis=1)
        
    df_string['levenshtein_distance'] = df_string.apply(
        lambda row: levenshtein_distance(row['old'].lower().strip(), row['new'].lower().strip()),
        axis=1
    )

    old_len = df_string['old'].str.len()
    new_len = df_string['new'].str.len()
    max_len = np.maximum(old_len, new_len).clip(lower=1) # replace 0's with 1 to avoid division by zero

    # percentage of how much changed
    df_string['edit_distance_ratio'] = df_string['levenshtein_distance'] / max_len
    

    feature_cols = [
        'levenshtein_distance', 
        'length_diff_abs', 
        # 'punct_differs', 
        'token_count_old', 
        'token_count_new',         
        'token_overlap', 
        'old_in_new',
        'new_in_old', 
        'edit_distance_ratio'
    ]

    # NOTE: removed because 95% of examples had 0 for this features
    # if 'label' not in old_col:
    #     feature_cols.extend([
    #         'case_differs',
    #         'spaces_differs', 
    #         'hyph_dash_differs', 
    #         'brackets_differs'
    #     ])
    
    df_string.drop(columns=['old', 'new'], inplace=True)
    
    return df_string, feature_cols


def create_semantic_similarity_features(df, old_col, new_col, feature_cols):
    """
    Calculates cosine similarity between old and new value embeddings
    """
    
    old_texts = []
    new_texts = []
    for _, row in df.iterrows():
        entity = str(row['entity_label'])
        prop = str(row['property_label'])
        # TODO: see how it perfoms, maybe I need to add this later
        # new_value_description = str(row['new_value_description'])
        # old_value_description = str(row['old_value_description'])

        new_value_type = str(row['new_value_entity_type'])
        old_value_type = str(row['old_value_entity_type'])
            
        latest_description = str(row['latest_description'])
        entity_type = str(row['main_entity_type'])

        old_val = str(row[old_col])
        new_val = str(row[new_col])
        if 'label' in old_col:
            # entity changes -> add the entity label as context
            old_texts.append(f"Entity: {entity}, Entity Type: {entity_type}, Entity Description: {latest_description}, Property: {prop}, Old Value Type: {old_value_type}, Old Value: {old_val}")
            new_texts.append(f"Entity: {entity}, Entity Type: {entity_type}, Entity Description: {latest_description}, Property: {prop}, New Value Type: {new_value_type}, New Value: {new_val}")
        else:
            # add the property label + entity label + latest description to provide context
            old_texts.append(f"Entity: {entity}, Entity Type: {entity_type}, Entity Description: {latest_description}, Property: {prop}, Old Value: {old_val}" )
            new_texts.append(f"Entity: {entity}, Entity Type: {entity_type}, Entity Description: {latest_description}, Property: {prop}, New Value: {new_val}")
    
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
    
    df['cosine_similarity'] = similarities
    
    feature_cols.append('cosine_similarity')
    
    return df, feature_cols

def create_text_features(df, feature_cols):
    """Extract text features for string datatypes"""
    string_mask = df['datatype'].isin(WD_STRING_TYPES)

    # df_sring is already filtered by the mask
    df_string, feature_cols = extract_text_features(df, 'old_value', 'new_value', mask=string_mask)

    df_string, feature_cols = create_semantic_similarity_features(df_string, 'old_value', 'new_value', feature_cols)

    return df_string, feature_cols

##############################
# Time feature extraction
##############################

def create_time_features(df, feature_cols):
    """
    Extract time change features
    """
    time_mask = (df['datatype'] == 'time')
    subset = df[time_mask].copy()
    
    if time_mask.sum() == 0:
        return df, feature_cols

    def get_date_parts(datatime_str, option='date'):

        try:
            if option == 'date':
                time_str_cleaned = str(datatime_str).replace('Z', '').replace('+', '').lstrip('−')
                parts = time_str_cleaned.split('T')[0].split('-')
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                return year, month, day
            elif option == 'time':
                time_str_cleaned = str(datatime_str).replace('Z', '').replace('+', '').lstrip('−')
                parts = time_str_cleaned.split('T')[1].split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2])
                return hour, minute, second
        except:
            return None
    
    def calc_date_diff(row):
        """Calculate date difference in days"""
        try:
            dt1 = row['old_value'].replace('"', '')
            dt2 = row['new_value'].replace('"', '')
            if dt1 is None or dt2 is None:
                return 1000
            
            if 'T' not in dt1 or 'T' not in dt2:
                # if there's somevalue or novalue
                return 1000
            
            dt1_year, dt1_month, dt1_day = get_date_parts(dt1, option='date')
            dt2_year, dt2_month, dt2_day = get_date_parts(dt2, option='date')

            if None in (dt1_year, dt1_month, dt1_day, dt2_year, dt2_month, dt2_day):
                return 1000
            # do it manually since WD allows 00 for month and day and Pyhton libraries don't
            diff_year = int(abs(dt2_year - dt1_year) * 365.25) # use .25 for leap years
            diff_month = int(abs(dt2_month - dt1_month) * 30.44) # average days in month
            diff_day = int(abs(dt2_day - dt1_day))

            return diff_year + diff_month + diff_day
        
        except:
            return 1000
    
    def calc_time_diff(row):
        """Calculate time difference in minutes"""
        try:
            dt1 = row['old_value'].replace('"', '')
            dt2 = row['new_value'].replace('"', '')
            if dt1 is None or dt2 is None:
                return 1000
            
            if 'T' not in dt1 or 'T' not in dt2:
                # if there's somevalue or novalue
                return 1000
            
            hour1, minute1, second1 = get_date_parts(dt1, option='time')
            hour2, minute2, second2 = get_date_parts(dt2, option='time')

            if None in (hour1, minute1, second1, hour2, minute2, second2):
                return 1000

            minute_diff = int(abs(minute2 - minute1))
            hour_diff = int(abs(hour2 - hour1) * 60) # convert to minutes
            second_diff = int(abs(second2 - second1) / 60)  # convert to minutes
            
            return hour_diff + minute_diff + second_diff
        
        except:
            return 1000

    def calc_sign_change(row):
        dt1 = row['old_value'].replace('"', '')
        dt2 = row['new_value'].replace('"', '')

        if dt1[1:] == dt2[1:]:
            return 1
        else:
            return 0
    
    def change_one_to_value(row):
        dt1 = row['old_value'].replace('"', '')
        dt2 = row['new_value'].replace('"', '')
        try:
            if dt1 is None or dt2 is None:
                return 0
            if 'T' not in dt1 or 'T' not in dt2:
                # for somevalue or novalue
                return 0

            year1, month1, day1 = get_date_parts(dt1, option='date')
            year2, month2, day2 = get_date_parts(dt2, option='date')

            if ((month1 == 1 and month2 > 0) or (day1 == 1 and day2 > 0)) and year1 == year2:
                return 1
            else:
                return 0
        except:
            return 0

    def calc_change_zero_one(row, option='zero_to_one'):
        dt1 = row['old_value'].replace('"', '')
        dt2 = row['new_value'].replace('"', '')
        try:
            
            if dt1 is None or dt2 is None:
                return 0
            if 'T' not in dt1 or 'T' not in dt2:
                # for somevalue or novalue
                return 0

            year1, month1, day1 = get_date_parts(dt1, option='date')
            year2, month2, day2 = get_date_parts(dt2, option='date')

            if option == 'zero_to_one':
                # YYYY-00-00 -> YYYY-01-01
                # YYYY-00-00 -> YYYY-01-00
                # YYYY-00-00 -> YYYY-00-01
                if ((month1 == 0 and month2 == 1) or (day1 == 0 and day2 == 1)) and year1 == year2:
                    return 1
                else:
                    return 0
                
            elif option == 'one_to_zero':
                # YYYY-01-01 -> YYYY-00-00
                # YYYY-01-00 -> YYYY-00-00
                # YYYY-00-01 -> YYYY-00-00
                if ((month1 == 1 and month2 == 0) or (day1 == 1 and day2 == 0)) and year1 == year2:
                    return 1
                else:
                    return 0
        except:
            return 0

    def added_removed_part(row, part='year', option='date', change_type='added'):
        dt1 = row['old_value'].replace('"', '')
        dt2 = row['new_value'].replace('"', '')

        try:
            if dt1 is None or dt2 is None:
                return 0
            if 'T' not in dt1 or 'T' not in dt2:
                # for somevalue or novalue
                return 0

            if option == 'date':
                year1, month1, day1 = get_date_parts(dt1, option='date')
                year2, month2, day2 = get_date_parts(dt2, option='date')
                if change_type == 'added':
                    if part == 'year' and year1 == 0 and year2 != 0:
                        return 1
                    if part == 'month' and ((month1 == 0 and month2 > 0) or (month1 == 1 and month2 > 1)):
                        return 1
                    if part == 'day' and ((day1 == 0 and day2 > 0) or (day1 == 1 and day2 > 1)):
                        return 1
                    return 0
                elif change_type == 'removed':
                    if part == 'year' and year1 > 0 and year2 == 0:
                        return 1
                    if part == 'month' and month1 > 0 and month2 == 0:
                        return 1
                    if part == 'day' and day1 > 0 and day2 == 0:
                        return 1
                    return 0
           
            elif option == 'time':
                hour1, minute1, second1 = get_date_parts(dt1, option='time')
                hour2, minute2, second2 = get_date_parts(dt2, option='time')
                if change_type == 'added':
                    if part == 'hour' and hour1 == 0 and hour2 != 0:
                        return 1
                    if part == 'minute' and minute1 == 0 and minute2 != 0:
                        return 1
                    if part == 'second' and second1 == 0 and second2 != 0:
                        return 1
                    return 0
                elif change_type == 'removed':
                    if part == 'hour' and hour1 != 0 and hour2 == 0:
                        return 1
                    if part == 'minute' and minute1 != 0 and minute2 == 0:
                        return 1
                    if part == 'second' and second1 != 0 and second2 == 0:
                        return 1
                    return 0
        except:
            return 0

    subset['date_diff_days'] = subset.apply(calc_date_diff, axis=1)
    subset['time_diff_minutes'] = subset.apply(calc_time_diff, axis=1)
    subset['sign_change'] = subset.apply(calc_sign_change, axis=1)
    subset['change_one_to_zero'] = subset.apply(lambda row: calc_change_zero_one(row, option='one_to_zero'), axis=1)
    subset['change_zero_to_one'] = subset.apply(lambda row: calc_change_zero_one(row, option='zero_to_one'), axis=1)
    subset['year_added'] = subset.apply(lambda row: added_removed_part(row, part='year', option='date', change_type='added'), axis=1)
    subset['year_removed'] = subset.apply(lambda row: added_removed_part(row, part='year', option='date', change_type='removed'), axis=1)
    subset['month_added'] = subset.apply(lambda row: added_removed_part(row, part='month', option='date', change_type='added'), axis=1)
    subset['month_removed'] = subset.apply(lambda row: added_removed_part(row, part='month', option='date', change_type='removed'), axis=1)
    subset['day_added'] = subset.apply(lambda row: added_removed_part(row, part='day', option='date', change_type='added'), axis=1)
    subset['day_removed'] = subset.apply(lambda row: added_removed_part(row, part='day', option='date', change_type='removed'), axis=1)
    subset['hour_added'] = subset.apply(lambda row: added_removed_part(row, part='hour', option='time', change_type='added'), axis=1)
    subset['hour_removed'] = subset.apply(lambda row: added_removed_part(row, part='hour', option='time', change_type='removed'), axis=1)
    subset['minute_added'] = subset.apply(lambda row: added_removed_part(row, part='minute', option='time', change_type='added'), axis=1)
    subset['minute_removed'] = subset.apply(lambda row: added_removed_part(row, part='minute', option='time', change_type='removed'), axis=1)
    subset['second_added'] = subset.apply(lambda row: added_removed_part(row, part='second', option='time', change_type='added'), axis=1)
    subset['second_removed'] = subset.apply(lambda row: added_removed_part(row, part='second', option='time', change_type='removed'), axis=1)
    subset['change_one_to_value'] = subset.apply(change_one_to_value, axis=1)
    
    feature_cols.extend([
        'date_diff_days',
        'time_diff_minutes',
        'sign_change',
        'change_one_to_zero', # YYYY-01-01 -> YYYY-00-00 -> I treated this as formatting
        'change_zero_to_one', # YYYY-00-00 -> YYYY-01-01 -> I treated this as refinement? # TODO: check this
        'year_added',
        'year_removed',
        'month_added',
        'month_removed',
        'day_added',
        'day_removed',
        'hour_added',
        'hour_removed',
        'minute_added',
        'minute_removed',
        'second_added',
        'second_removed'
    ])

    return subset, feature_cols

##############################
# Quantity feature extraction
##############################
def calc_precision_change(row, new_col, old_col, datatype='quantity', part=None):
    # returns 1 if only precision (decimal places) changed, 0 otherwise
    if datatype == 'latitude' or datatype == 'longitude':
        if '{' in row[old_col] and '{' in row[new_col]:
            old = json.loads(row[old_col]).get(part, None)
            new = json.loads(row[new_col]).get(part, None)
            
            old_ndp = str(old).split('.')[0] if '.' in str(old) else str(old)
            old_dp = str(old).split('.')[1] if '.' in str(old) else 0

            new_ndp = str(new).split('.')[0] if '.' in str(new) else str(new)
            new_dp = str(new).split('.')[1] if '.' in str(new) else 0
        else:
            return 0
    else:

        # quantity
        old_ndp = str(row[old_col]).split('.')[0] if '.' in str(row[old_col]) else str(row[old_col])
        old_dp = str(row[old_col]).split('.')[1] if '.' in str(row[old_col]) else 0

        new_ndp = str(row[new_col]).split('.')[0] if '.' in str(row[new_col]) else str(row[new_col])
        new_dp = str(row[new_col]).split('.')[1] if '.' in str(row[new_col]) else 0

    if old_ndp == new_ndp and old_dp != new_dp:
        return 1
    else:
        return 0

def calc_precision_added_removed(row, new_col, old_col, option='added', datatype='quantity', part=None):
    """
        Returns 1 if precision was added or removed, 0 otherwise
        NOTE: we only check that the precision was added/removed, not that it increased/decreased
    """
    if datatype == 'quantity':
        
        new = str(row[new_col])
        old = str(row[old_col])

    else: # globecoordinate
        if '{' in row[old_col] and '{' in row[new_col]:
            old = str(json.loads(row[old_col]).get(part, '')) # part is longitude or latitude
            new = str(json.loads(row[new_col]).get(part, ''))
        else:
            return 0
        
    new_first_part = new.split('.')[0]
    old_first_part = old.split('.')[0]
    if new_first_part != old_first_part:
        return 0  # different values, not just precision change

    if option == 'added':
        return 1 if ('.' in new) and ('.' not in old) else 0
    else: # removed
        if old == '27834.0':
            print(old, new)
        return 1 if ('.' not in new) and ('.' in old) else 0

def calc_length_increase_decrease(row, new_col, old_col, datatype='quantity', option='increase', part=None):

    if datatype == 'quantity':
        new_length = len(str(row[new_col]).replace('-', '').replace('+', ''))
        old_length = len(str(row[old_col]).replace('-', '').replace('+', ''))
    else: # globecoordinate
        if '{' in row[old_col] and '{' in row[new_col]: # for somevalue or novalue
            old = str(json.loads(row[old_col]).get(part, '')) # part is longitude or latitude
            new = str(json.loads(row[new_col]).get(part, ''))
            new_length = len(new.replace('-', '').replace('+', ''))
            old_length = len(old.replace('-', '').replace('+', ''))
        else:
            return 0
    
    if option == 'increase':
        return 1 if new_length > old_length else 0
    else: # decrease
        return 1 if new_length < old_length else 0
    
def calc_sign_change(row, new_col, old_col, datatype='quantity', part=None):

    if datatype == 'quantity':
        new_float = float(row[new_col])
        old_float = float(row[old_col])
    else: # globecoordinate
        if '{' in row[old_col] and '{' in row[new_col]: # for somevalue or novalue
            old = str(json.loads(row[old_col]).get(part, '')) # part is longitude or latitude
            new = str(json.loads(row[new_col]).get(part, ''))
            new_float = float(new)
            old_float = float(old)
        else:
            return 0
    return 1 if (old_float * new_float < 0) else 0

def calc_relative_value_diff_abs(row, new_col, old_col, datatype='quantity', part=None):

    if datatype == 'quantity':
        new_float = float(row[new_col])
        old_float = float(row[old_col])
    else: # globecoordinate
        if '{' in row[old_col] and '{' in row[new_col]: # for somevalue or novalue
            old = str(json.loads(row[old_col]).get(part, '')) # part is longitude or latitude
            new = str(json.loads(row[new_col]).get(part, ''))
            new_float = float(new)
            old_float = float(old)
        else:
            return 0
    return abs((new_float - old_float) / (old_float if old_float != 0 else 1))

def create_quantity_features(df, feature_cols):
    quant_mask = df['datatype'] == 'quantity'
    
    if quant_mask.sum() == 0:
        return df, feature_cols

    subset = df[quant_mask].copy()
    
    # remove + sign
    subset['old_str'] = subset['old_value'].astype(str).str.replace('"', '').str.replace('+', '', regex=False)
    subset['new_str'] = subset['new_value'].astype(str).str.replace('"', '').str.replace('+', '', regex=False)
    
    # relative value diff
    # relative value difernece -> proportional change relative to the old_value
    subset['relative_value_diff_abs'] = subset.apply(lambda row: calc_relative_value_diff_abs(row, 'new_str', 'old_str', datatype='quantity'), axis=1)
    
    # sign change 
    subset['sign_change'] = subset.apply(lambda row: calc_sign_change(row, 'new_str', 'old_str', datatype='quantity'), axis=1)
    
    # only precision change 
    subset['precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_str', 'old_str', datatype='quantity'), axis=1)
    
    # precision added/removed
    subset['precision_added'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_str', 'old_str', 'added', 'quantity'),axis=1)
    subset['precision_removed'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_str', 'old_str', 'removed', 'quantity'),axis=1)

    subset['length_increase'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_str', 'old_str', datatype='quantity', option='increase'), axis=1)
    subset['length_decrease'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_str', 'old_str', datatype='quantity', option='decrease'), axis=1)

    subset['whole_number_change'] = subset.apply(lambda row: int(np.floor(abs(float(row['old_str']))) != np.floor(abs(float(row['new_str'])))), axis=1)

    feature_cols.extend([
        'sign_change',
        'precision_change',
        'precision_added',
        'precision_removed',
        'length_increase',
        'length_decrease',
        'relative_value_diff_abs',
        'whole_number_change'
    ])

    subset, feature_cols = create_semantic_similarity_features(subset, 'old_str', 'new_str', feature_cols)

    subset.drop(columns=['old_str', 'new_str'], inplace=True)
    
    return subset, feature_cols

##############################
# Globe coordinate feature extraction
##############################
def create_globe_coordinate_features(df, feature_cols):
    coordinate_mask = df['datatype'] == 'globecoordinate'

    subset = df[coordinate_mask].copy()
    
    for idx in subset.index:
        try:
            old_val = json.loads(subset.loc[idx, 'old_value'])
            new_val = json.loads(subset.loc[idx, 'new_value'])

            subset.loc[idx, 'relative_value_diff_latitude'] = abs(
                (new_val['latitude'] - old_val['latitude']) / (old_val['latitude'] if old_val['latitude'] != 0 else 1)
            )

            subset.loc[idx, 'relative_value_diff_longitude'] = abs(
                (new_val['longitude'] - old_val['longitude']) / (old_val['longitude'] if old_val['longitude'] != 0 else 1)
            )
            
            # subset.loc[idx, 'latitude_diff_abs'] = abs(new_val['latitude'] - old_val['latitude'])
            # subset.loc[idx, 'longitude_diff_abs'] = abs(new_val['longitude'] - old_val['longitude'])
            
            subset.loc[idx, 'latitude_sign_change'] = int((float(new_val['latitude']) * float(old_val['latitude']) < 0))
            subset.loc[idx, 'longitude_sign_change'] = int((float(new_val['longitude']) * float(old_val['longitude']) < 0))

            # add abs because if there's a negative value then they will be different even though the whole number is the same
            subset.loc[idx, 'latitude_whole_number_change'] = (math.floor(abs(new_val['latitude'])) != math.floor(abs(old_val['latitude'])))
            subset.loc[idx, 'longitude_whole_number_change'] = (math.floor(abs(new_val['longitude'])) != math.floor(abs(old_val['longitude'])))

            # distance with haversine formula
            from math import radians, sin, cos, sqrt, atan2
            
            lat1, lon1 = radians(old_val['latitude']), radians(old_val['longitude'])
            lat2, lon2 = radians(new_val['latitude']), radians(new_val['longitude'])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * atan2(sqrt(a), sqrt(1-a))
            distance_km = 6371 * c  # Earth radius in km
            
            subset.loc[idx, 'coordinate_distance_km'] = distance_km

        except:
            pass
    
    subset['latitude_precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_value', 'old_value', datatype='globecoordinate', part='latitude'), axis=1)
    subset['longitude_precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_value', 'old_value', datatype='globecoordinate', part='longitude'), axis=1)
    
    subset['latitude_precision_added'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_value', 'old_value', 'added', 'globecoordinate', 'latitude'),axis=1)
    subset['latitude_precision_removed'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_value', 'old_value', 'removed', 'globecoordinate', 'latitude'),axis=1)
    
    subset['longitude_precision_added'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_value', 'old_value', 'added', 'globecoordinate', 'longitude'),axis=1)
    subset['longitude_precision_removed'] = subset.apply(lambda row: calc_precision_added_removed(row, 'new_value', 'old_value', 'removed', 'globecoordinate', 'longitude'),axis=1)

    subset['latitude_length_increase'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='increase', part='latitude'), axis=1).astype(int)
    subset['latitude_length_decrease'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='decrease', part='latitude'), axis=1).astype(int)
    
    subset['longitude_length_increase'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='increase', part='longitude'), axis=1).astype(int)
    subset['longitude_length_decrease'] = subset.apply(lambda row: calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='decrease', part='longitude'), axis=1).astype(int)

    feature_cols.extend([
        # 'latitude_diff_abs',
        # 'longitude_diff_abs',
        'coordinate_distance_km',
        'latitude_precision_change',
        'longitude_precision_change',
        'latitude_sign_change',
        'longitude_sign_change',
        'latitude_precision_added',
        'latitude_precision_removed',
        'longitude_precision_added',
        'longitude_precision_removed',
        'relative_value_diff_latitude',
        'relative_value_diff_longitude',
        'latitude_length_increase',
        'latitude_length_decrease',
        'longitude_length_increase',
        'longitude_length_decrease',
        'latitude_whole_number_change',
        'longitude_whole_number_change',
    ])

    subset, feature_cols = create_semantic_similarity_features(subset, 'old_value', 'new_value', feature_cols)

    return subset, feature_cols

##############################
# Entity feature extraction
##############################
def create_entity_features(df, feature_cols):
    """Extract features for entity datatypes using labels"""

    entity_mask = df['datatype'].isin(WD_ENTITY_TYPES)

    df_entity, feature_cols = extract_text_features(df, 'old_value_label', 'new_value_label', entity_mask)
    df_entity, feature_cols = create_semantic_similarity_features(df_entity, 'old_value_label', 'new_value_label', feature_cols)
    
    return df_entity, feature_cols

#####################################
# Reverted edit feature extraction
#####################################

def get_next_10_changes(row, df):
    # filter by same entity-property-value & higher timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors ='coerce')
    df = df.sort_values(by='timestamp') # by default it`s ascending=True

    next_10_changes = df[(df['entity_id'] == row['entity_id']) &
                         (df['property_id'] == row['property_id']) &
                         (df['value_id'] == row['value_id']) & 
                         (df['timestamp'] > row['timestamp'])].copy()
    
    num_changes = len(next_10_changes.index)
    if num_changes < 10:
        # if not enough changes, get more changes fro the same entity-property
        extra_changes = df[(df['entity_id'] == row['entity_id']) &
                         (df['property_id'] == row['property_id']) &
                         (df['timestamp'] > row['timestamp'])].copy().iloc[:(10 - num_changes)]
        
        next_10_changes = pd.concat([next_10_changes, extra_changes], ignore_index=True)
    return next_10_changes

def calc_keywords_in_comment_next_changes(row, df, keywords):
    
    next_10_changes = get_next_10_changes(row, df)
    for _, row in next_10_changes.iterrows():
        if any(keyword in str(row['comment']).lower() for keyword in keywords):
            return 1
    return 0

def calc_new_hash_in_future_old_hash_next_10_changes(row, df):
    next_10_changes = get_next_10_changes(row, df)
    for _, next_row in next_10_changes.iterrows():
        # Case 1: value updates
                        # (old_value, new_value, old_hash, new_hash)
        # row:           (Y, X, old_hash_row, new_hash_row)  cte1.old_hash IS NOT NULL
        # next change : (X, Y, new_hash_row, old_hash_row) cte2.new_hash IS NOT NULL
        # hashes are inverted

        # Case 2: addition/deletion changes
        # Deletion:        (old_value, new_value, old_hash, new_hash)
        # row;           (Y, NULL, old_hash_row, NULL) cte1.old_hash != null
        # next change : (NULL, Y, NULL, old_hash_row)  cte2.new_hash != null

        # Creation:       (old_value, new_value, old_hash, new_hash)
        # row;           (NULL, Y, NULL, new_hash_row) cte1.old_hash = NULL and cte1.new_hash != null
        # next change : (Y, NULL, new_hash_row, NULL) cte2.new_hash = NULL and cte2.old_hash != null

        # creation
        if (row['old_hash'] is None or row['old_hash'] == '') and (next_row['new_hash'] is None or next_row['new_hash'] == '') and str(row['new_hash']) == str(next_row['old_hash']) and (str(row['new_value']) == str(next_row['old_value'])):
            return 1
        
        # deletion & updates
        if (row['old_hash'] is not None and row['old_hash'] != '') and (next_row['new_hash'] is not None and next_row['new_hash'] != '') and str(row['old_hash']) == str(next_row['new_hash']) and (str(row['old_value']) == str(next_row['new_value'])):
            return 1

    return 0

def calc_time_to_change(row, df, option='next'):
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors ='coerce')
    df = df.sort_values(by='timestamp') # by default it`s ascending=True

    if option == 'next':
        future_changes = df[(df['entity_id'] == row['entity_id']) &
                             (df['property_id'] == row['property_id']) &
                             (df['value_id'] == row['value_id']) & 
                             (df['timestamp'] > row['timestamp'])].copy()
        if future_changes.empty:
            future_changes = df[(df['entity_id'] == row['entity_id']) &
                             (df['property_id'] == row['property_id']) &
                             (df['timestamp'] > row['timestamp'])].copy()
            
        if future_changes.empty:
            return -1  # no future change found
        else:
            next_change_time = future_changes.iloc[0]['timestamp'] # first row -> it was sorted ascending, so it will be the inmediate next change
            time_diff = (next_change_time - row['timestamp']).total_seconds()
            return time_diff

    else:  # previous
        past_changes = df[(df['entity_id'] == row['entity_id']) &
                           (df['property_id'] == row['property_id']) &
                           (df['value_id'] == row['value_id']) & 
                           (df['timestamp'] < row['timestamp'])].copy()
        if past_changes.empty:
            past_changes = df[(df['entity_id'] == row['entity_id']) &
                           (df['property_id'] == row['property_id']) &
                           (df['timestamp'] < row['timestamp'])].copy()
        if not past_changes.empty:
            prev_change_time = past_changes.iloc[-1]['timestamp'] # last row -> it was sorted ascending, so it will be the inmediate previous change
            time_diff = (row['timestamp'] - prev_change_time).total_seconds()
            return time_diff
        else:
            return -1  # no past change found

def create_reverted_edit_features(df, feature_cols):

    df['user_type'] = [
        'BOT' if 'bot' in str(username).lower() 
        else 'USER' if ('bot' not in str(username).lower() and str(username) != '')
        else 'ANONYMOUS' 
        for username in df['username']
    ]

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors ='coerce')

    df['is_weekend'] = df['timestamp'].dt.weekday > 4 # 0:  Monday, 6: Sunday
    df['day_of_week'] = df['timestamp'].dt.day_name()
    df['hour_of_day'] = df['timestamp'].dt.hour
    
    # encode categorical features: user_type, day_of_week, hour_of_day, is_weekend
    le = LabelEncoder()

    categorical_cols = [
        'user_type',
        'day_of_week',
        'hour_of_day',
        'is_weekend',
        'action'
    ]

    for col in categorical_cols:
        df[f'{col}_encoded'] = le.fit_transform(df[col].astype(str))
    
    rv_keywords = ['revert', 'rv', 'undid', 'restore', 'rvv', 'vandal', 'undo']

    df['rv_keyword_in_comment_next_10_changes'] = df.apply(lambda row: calc_keywords_in_comment_next_changes(row, df, rv_keywords),axis=1)

    df['new_hash_in_future_old_hash_next_10_changes'] = df.apply(lambda row: calc_new_hash_in_future_old_hash_next_10_changes(row, df),axis=1)

    df['time_to_next_change_seconds'] = df.apply(lambda row: calc_time_to_change(row, df, option='next'),axis=1)

    df['time_to_prev_change_seconds'] = df.apply(lambda row: calc_time_to_change(row, df, option='prev'),axis=1)

    feature_cols = [
        'user_type_encoded',
        'is_weekend_encoded',
        'day_of_week_encoded',
        'hour_of_day_encoded',
        'rv_keyword_in_comment_next_10_changes', # maybe i need to encode this somehow, instead of binary (e.g. return the keyword and then encode)
        'new_hash_in_future_old_hash_next_10_changes',
        'time_to_next_change_seconds', 
        'time_to_prev_change_seconds',
        'action_encoded', # UPDATE/DELETE/CREATE
        # 'entity_age_years' # thought here: old entities are "important" so maybe they get more vandalism?
    ]

    # TODO: agregar latest_description, entity_type, etc para reverted edit
    # df, feature_cols = create_semantic_similarity_features(df, 'old_value', 'new_value', feature_cols)

    return df, feature_cols, le

#####################################
# Property replacement feature extraction
#####################################
def calculate_pair_features(group, model):
    """
    group has 2 rows: one create, one delete
    Calculate features comparing them
    """

    create_row = group[group['action'] == 'CREATE'].iloc[0]
    delete_row = group[group['action'] == 'DELETE'].iloc[0]

    delete_row['timestamp'] = pd.to_datetime(delete_row['timestamp'], errors='coerce')
    create_row['timestamp'] = pd.to_datetime(create_row['timestamp'], errors='coerce')
    if delete_row['timestamp'] < create_row['timestamp']:
        time_diff = (create_row['timestamp'] - delete_row['timestamp']).total_seconds()
    else:
        time_diff = (delete_row['timestamp'] - create_row['timestamp']).total_seconds()

    embeddings = model.encode(
        [create_row['property_label'], delete_row['property_label']],
        device="mps",
        show_progress_bar=False
    )

    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()

    features = {
        'time_diff': time_diff,
        'property_label_similarity': similarity,
        'same_user': create_row['username'] == delete_row['username']
    }
    
    return pd.Series(features)

def create_property_replacement_features(df, feature_cols):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    pair_features = df.groupby('pair_id').apply(lambda group: calculate_pair_features(group, model)).reset_index()

    df = df.merge(pair_features, on='pair_id', how='left')

    le = LabelEncoder()

    categorical_cols = [
        'action'
    ]

    for col in categorical_cols:
        df[f'{col}_encoded'] = le.fit_transform(df[col].astype(str))

    feature_cols = [
        'same_user',
        'property_label_similarity',
        'time_diff',
        'action_encoded'
        # For this feature I need to get the changes to other entities with the same property
        #'' # check if entities of the same type get the same property deleted and added at similar times (e.g. within the same week) (?) how do i calculate this
    ]

    return df, feature_cols, le

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
        # 'user_type',  # bot/human/anonymous
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
        # 'user_type_encoded',
        'day_of_week_encoded',
        'hour_of_day_encoded',
        'is_weekend_encoded',
        'num_changes_in_revision',
        # 'entity_age_days'
    ])

    return df, feature_cols