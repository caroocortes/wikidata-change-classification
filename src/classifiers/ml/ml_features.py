
import re
from sentence_transformers import SentenceTransformer, util
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import LabelEncoder
from decimal import Decimal

import requests
import pickle
from functools import lru_cache
from tqdm import tqdm
from Levenshtein import distance as levenshtein_distance
import torch
import time
import pandas as pd
import numpy as np
import json
import math
import os
import datetime
from datetime import datetime, timedelta

from ...utils.const import WD_ENTITY_TYPES, WD_STRING_TYPES

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

def has_adjacent_swap(old, new):
    """
        Check if two strings differ by an adjacent character swap
        e.g. "tent" vs "tetn" -> return 1
    """
    if len(old) != len(new):
        # different length -> there's a char addition or deletion
        return 0
    
    diffs = []
    for i in range(len(old)):
        # get charactes that differ in order
        if old[i] != new[i]:
            diffs.append(i)
        # old: caro old[2]=r old[3]=o
        # new: caor new[2]=o new[3]=r
        # diffs = [2,3]

    if len(diffs) == 2:
        i, j = diffs
        # check the difference is adjacent (j = i+1) and swapped
        if j == i + 1 and old[i] == new[j] and old[j] == new[i]:
            return 1
    return 0

def avg_word_levenshtein(old, new):
    """
        Calculate average Levenshtein distance between words in old and new strings
    """

    old_words = old.split()
    new_words = new.split()
    total_distance = 0
    count = 0
    for o_word in old_words:
        for n_word in new_words:
            dist = levenshtein_distance(o_word, n_word)
            total_distance += dist
            count += 1
    if count == 0:
        return 0
    return total_distance / count

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

    df_string['same_value_without_special_char'] = df_string.apply(lambda row: int(re.sub(r'[^a-zA-Z0-9]', '', row['old']) == re.sub(r'[^a-zA-Z0-9]', '', row['new'])), axis=1)
    
    # only for feature calculation - will be removed from result
    df_string['special_char_count_old'] = df_string['old'].str.count(r'[^a-zA-Z0-9]')
    df_string['special_char_count_new'] = df_string['new'].str.count(r'[^a-zA-Z0-9]')

    # actual features
    df_string['special_char_count_diff'] = df_string['special_char_count_new'] - df_string['special_char_count_old']
    df_string['special_chars_added'] = (df_string['special_char_count_diff'] > 0).astype(int)
    df_string['special_chars_removed'] = (df_string['special_char_count_diff'] < 0).astype(int)
    df_string['only_special_char_change'] = ((df_string['same_value_without_special_char'] == 1) & (df_string['special_char_count_diff'] != 0)).astype(int)

    df_string['levenshtein_distance'] = df_string.apply(
        lambda row: levenshtein_distance(row['old'].lower().strip(), row['new'].lower().strip()),
        axis=1
    )

    old_len = df_string['old'].str.len()
    new_len = df_string['new'].str.len()
    max_len = np.maximum(old_len, new_len).clip(lower=1) # replace 0's with 1 to avoid division by zero

    # percentage of how much changed
    df_string['edit_distance_ratio'] = df_string['levenshtein_distance'] / max_len

    df_string['complete_replacement'] = (
        (df_string['token_overlap'] == 0) & 
        (df_string['old_in_new'] == 0) & 
        (df_string['new_in_old'] == 0)
    ).astype(int)
    
    # for property_value_update or rewording (?), the structure similarity should be low.
    # for textual change the structure similarity should be high.
    df_string['structure_similarity'] = 1 - abs(df_string['token_count_old'] - df_string['token_count_new']) / \
                                     np.maximum(df_string['token_count_old'], df_string['token_count_new'])


    if 'label' not in old_col: # remove for entity
    
        def get_edit_operations(old_value, new_value):
            
            m, n = len(old_value), len(new_value)
            dp = [[0] * (n + 1) for _ in range(m + 1)]
            
            for i in range(m + 1):
                dp[i][0] = i
            for j in range(n + 1):
                dp[0][j] = j
            
            for i in range(1, m + 1):
                for j in range(1, n + 1):
                    if old_value[i-1] == new_value[j-1]:
                        dp[i][j] = dp[i-1][j-1]
                    else:
                        dp[i][j] = 1 + min(
                            dp[i-1][j],    # deletion
                            dp[i][j-1],    # insertion
                            dp[i-1][j-1]   # substitution
                        )

            i, j = m, n
            insertions = deletions = substitutions = 0
            
            while i > 0 or j > 0:
                if i > 0 and j > 0 and old_value[i-1] == new_value[j-1]:
                    i -= 1
                    j -= 1
                elif i > 0 and j > 0 and dp[i][j] == dp[i-1][j-1] + 1:
                    substitutions += 1
                    i -= 1
                    j -= 1
                elif j > 0 and dp[i][j] == dp[i][j-1] + 1:
                    insertions += 1
                    j -= 1
                else:
                    deletions += 1
                    i -= 1
            
            return insertions, deletions, substitutions

        results = df_string.apply(lambda row: get_edit_operations(row['old'], row['new']), axis=1)
        df_string[['char_insertions', 'char_deletions', 'char_substitutions']] = pd.DataFrame(results.tolist(), index=df_string.index)
        
        df_string['adjacent_char_swap'] = df_string.apply(
            lambda row: has_adjacent_swap(row['old'], row['new']), axis=1
        )

        df_string['avg_word_similarity'] = df_string.apply(
            lambda row: avg_word_levenshtein(row['old'], row['new']), axis=1
        )

        # what os.path.commonprefix returns: paths: ['/home/User/Photos', /home/User/Videos']    commonprefix: /home/User/
        # Added that length of suffix/prefix is at least 3 to avoid short suffix/prefix (e.g. just the first letter...)
        df_string['has_significant_prefix'] = df_string.apply(
            lambda row: int(len(os.path.commonprefix([row['old'], row['new']])) >= 3),
            axis=1
        )

        df_string['has_significant_suffix'] = df_string.apply(
            lambda row: int(len(os.path.commonprefix([row['old'][::-1], row['new'][::-1]])) >= 3),
            axis=1
        )

    feature_cols = [
        'token_overlap', 
        'old_in_new',
        'new_in_old', 
        'edit_distance_ratio',
        'complete_replacement'
    ]

    if 'label' not in old_col:
        feature_cols.extend([
            'length_diff_abs',  
            'token_count_old',
            'token_count_new',
            'levenshtein_distance',
            'structure_similarity',
            'same_value_without_special_char',
            'special_char_count_diff',
            'special_chars_added',
            'special_chars_removed',
            'only_special_char_change',
            'char_insertions',
            'char_deletions',
            'char_substitutions',
            'adjacent_char_swap',
            'avg_word_similarity',
            'has_significant_prefix',
            'has_significant_suffix'
        ])
    
    df_string.drop(columns=['old', 'new', 'special_char_count_old', 'special_char_count_new'], inplace=True)
    
    return df_string, feature_cols


def create_semantic_similarity_features(df, old_col, new_col, feature_cols):
    """
    Calculates cosine similarity between old and new value embeddings
    """
    
    old_texts = []
    new_texts = []

    old_description = []
    new_description = []

    old_label = []
    new_label = []

    for _, row in df.iterrows():

        old_val = str(row[old_col]).replace('"', '') # these are the entity labels
        new_val = str(row[new_col]).replace('"', '')
        if 'label' in old_col:
           
            old_value_description = str(row['old_value_description']) if not pd.isna(row['old_value_description']) else ''
            new_value_description = str(row['new_value_description']) if not pd.isna(row['new_value_description']) else ''
                
            # only calculate these features for entity changes
            old_label.append(old_val) # labels
            new_label.append(new_val)

            old_description.append(old_value_description) # descriptions
            new_description.append(new_value_description)

        else:
            # add the property label + entity label + latest description to provide context
            old_texts.append(old_val)
            new_texts.append(new_val)
    
    # load model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    device = "cuda" if torch.cuda.is_available() else "cpu"

    if 'label' not in old_col:
        old_text_embeddings = model.encode(
            old_texts,
            device=device,
            show_progress_bar=True
        )
        new_text_embeddings = model.encode(
            new_texts,
            device=device,
            show_progress_bar=True
        )
        # calculate cosine similarity
        similarities = np.array([
            cosine_similarity([old_emb], [new_emb])[0][0]
            for old_emb, new_emb in zip(old_text_embeddings, new_text_embeddings)
        ])
        df['value_cosine_similarity'] = similarities

        feature_cols.extend(['value_cosine_similarity'])

    if 'label' in old_col:
        old_label_embeddings = model.encode(
            old_label,
            device=device,
            show_progress_bar=True
        )
        new_label_embeddings = model.encode(
            new_label,
            device=device,
            show_progress_bar=True
        )
        # calculate cosine similarity
        similarities = np.array([
            cosine_similarity([old_emb], [new_emb])[0][0]
            for old_emb, new_emb in zip(old_label_embeddings, new_label_embeddings)
        ])
        df['label_cosine_similarity'] = similarities

        old_description_embeddings = model.encode(
            old_description,
            device=device,
            show_progress_bar=True
        )
        new_description_embeddings = model.encode(
            new_description,
            device=device,
            show_progress_bar=True
        )
        # calculate cosine similarity
        similarities = np.array([
            cosine_similarity([old_emb], [new_emb])[0][0]
            for old_emb, new_emb in zip(old_description_embeddings, new_description_embeddings)
        ])
        df['description_cosine_similarity'] = similarities 
        
        feature_cols.extend([
            'label_cosine_similarity', # cosine similarity between labels of old and new value (only for entity)
            'description_cosine_similarity']) # cosine similarity between description of old and new value (only for entity)

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
                time_str_cleaned = (re.sub(r'[^0-9TZ:\-]', '', str(datatime_str))).replace('Z', '')
                date_part = time_str_cleaned.split('T')[0]
                
                # Handle negative years (BC dates)
                is_negative = date_part.startswith('-')
                if is_negative:
                    date_part = date_part[1:]  # Remove leading '-'
                
                parts = date_part.split('-')
                
                if len(parts) < 3:
                    raise ValueError(f"Invalid date format: {datatime_str}")
                
                year = int(parts[0])
                if is_negative:
                    year = -year  # Make it negative again
                
                month = int(parts[1])
                day = int(parts[2])
                return year, month, day
            elif option == 'time':
                time_str_cleaned = (re.sub(r'[^0-9TZ:\-]', '', str(datatime_str))).replace('Z', '')
                parts = time_str_cleaned.split('T')[1].split(':')
                hour = int(parts[0])
                minute = int(parts[1])
                second = int(parts[2])
                return hour, minute, second
        except Exception as e:
            print(f"Error parsing datetime string: {datatime_str} with option {option}: {e}")
            raise e
    
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
    
    def calc_sign_change(row):
        dt1 = row['old_value'].replace('"', '')
        dt2 = row['new_value'].replace('"', '')

        if dt1[1:] == dt2[1:]:
            return 1
        else:
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
                
                if year1 != year2:
                    return 0

                if change_type == 'added':
                    if part == 'year' and year1 == 0 and year2 != 0:
                        return 1
                    # YYYY-01-01 -> YYYY-05-00:
                    # YYYY-01-01 -> YYYY-05-10:
                    if part == 'month' and ((month1 == 0 and month2 > 0 and day1 == 0) or (month1 == 1 and month2 > 1 and day1 == 1 and (day2 > 1 or day2 == 0))):
                        return 1
                    if part == 'day' and ((day1 == 0 and day2 > 0) or (day1 == 1 and day2 > 1 and month1 == 1 and month2 > 1)):
                        return 1
                    return 0
                elif change_type == 'removed':

                    if part == 'year' and year1 > 0 and year2 == 0:
                            return 1
                    if part == 'month' and month1 > 0 and month2 == 0:
                        if not (day1 == 1 and day2 == 0) and not (day1 == 0 and day2 == 0): # if it's not a reformatting change
                            return 1
                    if part == 'day' and day1 > 0 and day2 == 0:
                        if not (day1 == 1 and day2 == 0): # if it's not a reformatting change
                            return 1
                    return 0
           
        except:
            return 0

    def is_placeholder_to_zero(dt1, dt2):
        if 'somevalue' in dt1 or 'novalue' in dt1 or 'somevalue' in dt2 or 'novalue' in dt2:
            return 0
        year1, month1, day1 = get_date_parts(dt1, option='date')
        year2, month2, day2 = get_date_parts(dt2, option='date')
        
        if year1 != year2:
            return 0  # year changed, not a reformatting
        
        # YYYY-01-01 -> YYYY-00-00 
        if month1 == 1 and day1 == 1 and month2 == 0 and day2 == 0:
            return 1
        
        # YYYY-MM-01 -> YYYY-MM-00 
        if month1 == month2 and month1 > 1 and day1 == 1 and day2 == 0:
            return 1
        
        # YYYY-01-00 -> YYYY-00-00 
        if month1 == 1 and month2 == 0 and day1 == 0 and day2 == 0:
            return 1

        return 0
    
    def date_part_changed(dt1, dt2, option='year'):
        """
        Returns 1 if there was an actual change in the month/year/day
        Not re_formatting (e.g. 01-01 -> XX-XX, 01-01 -> 00-00, 01-00 -> XX-00) or unrefinement/refinement (e.g. from X to 0)
        """
        if 'somevalue' in dt1 or 'novalue' in dt1 or 'somevalue' in dt2 or 'novalue' in dt2:
            return 1

        year1, month1, day1 = get_date_parts(dt1, option='date')
        year2, month2, day2 = get_date_parts(dt2, option='date')
        if option == 'year':
            if year1 != year2:
                return 1
        elif option == 'month':
            # 1. goes from 01-01 to 00-00
            # 2. goes from XX-01 to XX-00 with XX that can be 01
            # 3. goes from 01-00 to 00-00
            is_reformatting = ((month1 == 1 and day1 == 1 and day2 == 0 and month2 == 0) or  \
                            (month1 > 0 and month2 > 0 and month1 == month2 and day1 == 1 and day2 == 0) or \
                            (month1 == 1 and month2 == 0 and day1 == 0 and day2 == 0)) and year1 == year2
            
            # 1. just month added
            # 2. goes from 01-01 to MM-00 or MM-DD
            # 3. goes from 00-00 to MM-DD
            is_refinement = ((month1 == 0 and month2 > 0 and day2 == 0) or \
                            (month1 == 1 and day1 == 1 and month2 > 1 and (day2 > 1 or day2 == 0)) or \
                            (month1 == 0 and month2 > 0 and day1 == 0 and day2 > 0)) and year1 == year2
            # goes from MM-00 (month1) to 00-00 (month2)
            is_unrefinement = (month2 == 0 and month1 > 0) and year1 == year2
            if month1 != month2 and not is_reformatting and not is_refinement and not is_unrefinement:
                return 1
        elif option == 'day':
            # 1. goes from 01-01 to 00-00
            # 2. goes from XX-01 to XX-00
            # 3. goes from 01-00 to 00-00
            is_reformatting = ((month1 == 1 and day1 == 1 and day2 == 0 and month2 == 0) or  \
                            (month1 > 0 and month2 > 0 and month1 == month2 and day1 == 1 and day2 == 0) or \
                            (month1 == 1 and month2 == 0 and day1 == 0 and day2 == 0)) and year1 == year2
            # 1. XX-00 to XX-DD with XX that can be 01/00
            # 2. goes from 01-01 to MM-DD
            is_refinement = ((day1 == 0 and day2 > 0) or \
                            (day1 == 1 and day2 > 1 and month1 == 1 and month2 > 1)) and year1 == year2
            # goes from XX-00 to XX-DD 
            is_unrefinement = (day2 == 0 and day1 > 0) and year1 == year2
            if day1 != day2 and not is_reformatting and not is_refinement and not is_unrefinement:
                return 1
        return 0

    # for prop value update
    subset['date_diff_days'] = subset.apply(calc_date_diff, axis=1)

    # for reformatting
    subset['sign_change'] = subset.apply(calc_sign_change, axis=1)
    subset['change_one_to_zero'] = subset.apply(lambda row: is_placeholder_to_zero(row['old_value'], row['new_value']), axis=1)

    # for ref/unref
    subset['day_added'] = subset.apply(lambda row: added_removed_part(row, part='day', option='date', change_type='added'), axis=1)
    subset['day_removed'] = subset.apply(lambda row: added_removed_part(row, part='day', option='date', change_type='removed'), axis=1)
    subset['month_added'] = subset.apply(lambda row: added_removed_part(row, part='month', option='date', change_type='added'), axis=1)
    subset['month_removed'] = subset.apply(lambda row: added_removed_part(row, part='month', option='date', change_type='removed'), axis=1)

    # for property value update
    subset['different_year'] = subset.apply(lambda row: date_part_changed(row['old_value'], row['new_value'], option='year'), axis=1)
    subset['different_day'] = subset.apply(lambda row: date_part_changed(row['old_value'], row['new_value'], option='day'), axis=1)
    subset['different_month'] = subset.apply(lambda row: date_part_changed(row['old_value'], row['new_value'], option='month'), axis=1)

    feature_cols.extend([
        'date_diff_days',
        'sign_change',
        'change_one_to_zero',
        'day_added',
        'day_removed',
        'month_added',
        'month_removed',
        'different_year',
        'different_day',
        'different_month'
    ])

    return subset, feature_cols

##############################
# Quantity feature extraction
##############################
def calc_precision_change(row, new_col, old_col, datatype='quantity', part=None):
    # returns 1 if only precision (decimal places) changed, 0 otherwise
    if datatype == 'globecoordinate':
        if '{' in row[old_col] and '{' in row[new_col]:
            old = json.loads(row[old_col]).get(part, None)
            new = json.loads(row[new_col]).get(part, None)
        
        elif type(row[old_col]) == dict and type(row[new_col]) == dict:

            old = row[old_col].get(part, None)
            new = row[new_col].get(part, None)
        
        else:
            return 0
        
        old_ndp = str(old).split('.')[0] if '.' in str(old) else str(old)
        try:
            old_dp = str(old).split('.')[1] if '.' in str(old) and int(str(old).split('.')[1]) > 0 else '0'
        except ValueError:
            old_dp = '0'

        new_ndp = str(new).split('.')[0] if '.' in str(new) else str(new)
        try:
            new_dp = str(new).split('.')[1] if '.' in str(new) and int(str(new).split('.')[1]) > 0 else '0'
        except ValueError:
            new_dp = '0'
    else:

        # quantity
        old_ndp = str(row[old_col]).split('.')[0] if '.' in str(row[old_col]) else str(row[old_col])
        try:
            old_dp = str(row[old_col]).split('.')[1] if '.' in str(row[old_col]) and int(str(row[old_col]).split('.')[1]) > 0 else '0'
        except ValueError:
            old_dp = '0'

        new_ndp = str(row[new_col]).split('.')[0] if '.' in str(row[new_col]) else str(row[new_col])
        try:
            new_dp = str(row[new_col]).split('.')[1] if '.' in str(row[new_col]) and int(str(row[new_col]).split('.')[1]) > 0 else '0'
        except ValueError:
            new_dp = '0'

    # if both decimal parts are 0 -> there's no precision change
    # e.g. 12 -> 12.0 is not a precision change, or 12.0 -> 12.00
    if old_ndp == new_ndp and old_dp != new_dp and (old_dp != '0' or new_dp != '0'):
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
        return 1 if ('.' not in new) and ('.' in old) else 0

def calc_length_increase_decrease(row, new_col, old_col, datatype='quantity', option='increase', part=None):

    if datatype == 'quantity':
        new_length = len(str(row[new_col]).replace('-', '').replace('+', '').replace('.', ''))
        old_length = len(str(row[old_col]).replace('-', '').replace('+', '').replace('.', ''))
    else: # globecoordinate
        if '{' in row[old_col] and '{' in row[new_col]: # for somevalue or novalue
            old = str(json.loads(row[old_col]).get(part, '')) # part is longitude or latitude
            new = str(json.loads(row[new_col]).get(part, ''))
            new_length = len(new.replace('-', '').replace('+', '').replace('.', ''))
            old_length = len(old.replace('-', '').replace('+', '').replace('.', ''))
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
    return 1 if (old_float * new_float < 0) and (math.floor(abs(old_float)) == math.floor(abs(new_float))) else 0

def check_containment(row, old_col, new_col, datatype='quantity', part=None, option='old_in_new'):
    # dp here means decimal part
    old_value = row[old_col]
    new_value = row[new_col]
    if datatype == 'globecoordinate':
        if '{' in old_value and '{' in new_value:
            old_value = json.loads(old_value).get(part, None)
            new_value = json.loads(new_value).get(part, None)
        else:
            return 0

    if option == 'old_in_new':
        return 1 if str(new_value).startswith(str(old_value)) else 0
    elif option == 'new_in_old':
        return 1 if str(old_value).startswith(str(new_value)) else 0

def same_decimal_length(row, old_col, new_col, datatype='quantity', part=None):
    old_value = row[old_col]
    new_value = row[new_col]
    if datatype == 'globecoordinate':
        if '{' in old_value and '{' in new_value:
            old_value = json.loads(old_value).get(part, None)
            new_value = json.loads(new_value).get(part, None)
        else:
            return 0
        
    old_dec = str(old_value).split('.')[1] if '.' in str(old_value) else ''
    new_dec = str(new_value).split('.')[1] if '.' in str(new_value) else ''

    return 1 if len(old_dec) == len(new_dec) else 0

def same_float_value(row, old_col, new_col, datatype='quantity', part=None):
    old_value = row[old_col]
    new_value = row[new_col]
    if datatype == 'globecoordinate':
        if '{' in old_value and '{' in new_value:
            old_value = json.loads(old_value).get(part, None)
            new_value = json.loads(new_value).get(part, None)
        else:
            return 0
    try:
        return 1 if float(old_value) == float(new_value) else 0
    except:
        return 0

def create_quantity_features(df, feature_cols):
    quant_mask = df['datatype'] == 'quantity'
    
    if quant_mask.sum() == 0:
        return df, feature_cols

    subset = df[quant_mask].copy()
    
    # remove + sign
    subset['old_str'] = subset['old_value'].astype(str).str.replace('"', '').str.replace('+', '', regex=False)
    subset['new_str'] = subset['new_value'].astype(str).str.replace('"', '').str.replace('+', '', regex=False)
    
    # for ref/unref and prop value update
    subset['precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_str', 'old_str', datatype='quantity'), axis=1)

    # sign change 
    subset['sign_change'] = subset.apply(lambda row: calc_sign_change(row, 'new_str', 'old_str', datatype='quantity'), axis=1)
    
    # for refinement, unrefinement when there's 
    subset['length_increase'] = subset.apply(lambda row: 
                                                calc_length_increase_decrease(row, 'new_str', 'old_str', datatype='quantity', option='increase')
                                                and 
                                                check_containment(row, 'old_str', 'new_str', datatype='quantity', option='old_in_new')
                                                # and 
                                                # not (np.floor(abs(float(row['old_str']))) != np.floor(abs(float(row['new_str'])))) # whole number change
                                                , axis=1).astype(int)
    subset['length_decrease'] = subset.apply(lambda row: 
                                                calc_length_increase_decrease(row, 'new_str', 'old_str', datatype='quantity', option='decrease')
                                                and
                                                check_containment(row, 'new_str', 'old_str', datatype='quantity', option='new_in_old')
                                                # and 
                                                # not (np.floor(abs(float(row['old_str']))) != np.floor(abs(float(row['new_str'])))) # whole number change
                                                , axis=1).astype(int)

    # for prop value update
    subset['whole_number_change'] = subset.apply(lambda row: int(np.floor(abs(float(row['old_str']))) != np.floor(abs(float(row['new_str'])))), axis=1)

    # for ref & unref & also if it's 0 helps with prop value update, since there's no containment
    subset['old_is_prefix_of_new'] = subset.apply(lambda row: check_containment(row, 'old_str', 'new_str', datatype='quantity', option='old_in_new'), axis=1)
    subset['new_is_prefix_of_old'] = subset.apply(lambda row: check_containment(row, 'old_str', 'new_str', datatype='quantity', option='new_in_old'), axis=1)

    # for re_formatting (e.g. 1.50 -> 1.5 or 9.0 -> 9)
    subset['same_float_value'] = subset.apply(lambda row: same_float_value(row, 'old_str', 'new_str', datatype='quantity'), axis=1)

    feature_cols.extend([
        'sign_change', # format
        'precision_change', # ref/unref/prop val update
        'length_increase', # ref
        'length_decrease', # unref
        'whole_number_change', # prop val update
        'old_is_prefix_of_new', # refinement
        'new_is_prefix_of_old',  # unrefinement
        'same_float_value', # for ref/unref/reformat
    ])

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

            # the sign changes but at least the whole number remains the same
            subset.loc[idx, 'latitude_sign_change'] = int((float(new_val['latitude']) * float(old_val['latitude']) < 0) and (math.floor(abs(new_val['latitude'])) == math.floor(abs(old_val['latitude']))))
            subset.loc[idx, 'longitude_sign_change'] = int((float(new_val['longitude']) * float(old_val['longitude']) < 0) and (math.floor(abs(new_val['longitude'])) == math.floor(abs(old_val['longitude']))))

            # add abs because if there's a negative value then they will be different even though the whole number is the same
            subset.loc[idx, 'latitude_whole_number_change'] = int(math.floor(abs(new_val['latitude'])) != math.floor(abs(old_val['latitude'])))
            subset.loc[idx, 'longitude_whole_number_change'] = int(math.floor(abs(new_val['longitude'])) != math.floor(abs(old_val['longitude'])))
            
        except:
            pass
    
    subset['latitude_precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_value', 'old_value', datatype='globecoordinate', part='latitude'), axis=1)
    subset['longitude_precision_change'] = subset.apply(lambda row: calc_precision_change(row, 'new_value', 'old_value', datatype='globecoordinate', part='longitude'), axis=1)
    
    subset['latitude_length_increase'] = subset.apply(lambda row: 
                                                        calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='increase', part='latitude')
                                                        and
                                                        check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='latitude', option='old_in_new')
                                                        , axis=1).astype(int)
    subset['latitude_length_decrease'] = subset.apply(lambda row: 
                                                        calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='decrease', part='latitude')
                                                        and
                                                        check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='latitude', option='new_in_old'), axis=1).astype(int)
    
    subset['longitude_length_increase'] = subset.apply(lambda row: 
                                                       calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='increase', part='longitude')
                                                       and 
                                                       check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='longitude', option='old_in_new')
                                                       , axis=1).astype(int)
    subset['longitude_length_decrease'] = subset.apply(lambda row: 
                                                        calc_length_increase_decrease(row, 'new_value', 'old_value', 'globecoordinate', option='decrease', part='longitude')
                                                        and
                                                        check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='longitude', option='new_in_old')
                                                        , axis=1).astype(int)

    subset['longitude_old_is_prefix_of_new'] = subset.apply(lambda row: check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='longitude', option='old_in_new'), axis=1)
    subset['longitude_new_is_prefix_of_old'] = subset.apply(lambda row: check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='longitude', option='new_in_old'), axis=1)
    subset['longitude_same_float_value'] = subset.apply(lambda row: same_float_value(row, 'old_value', 'new_value', datatype='globecoordinate', part='longitude'), axis=1)

    subset['latitude_old_is_prefix_of_new'] = subset.apply(lambda row: check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='latitude', option='old_in_new'), axis=1)
    subset['latitude_new_is_prefix_of_old'] = subset.apply(lambda row: check_containment(row, 'old_value', 'new_value', datatype='globecoordinate', part='latitude', option='new_in_old'), axis=1)
    subset['latitude_same_float_value'] = subset.apply(lambda row: same_float_value(row, 'old_value', 'new_value', datatype='globecoordinate', part='latitude'), axis=1)
    
    feature_cols.extend([

        'latitude_sign_change',
        'longitude_sign_change',
        
        'latitude_whole_number_change',
        'longitude_whole_number_change',
        
        'latitude_precision_change',
        'longitude_precision_change',
        
        'latitude_length_increase',
        'latitude_length_decrease',
        
        'longitude_length_increase',
        'longitude_length_decrease',

        'latitude_old_is_prefix_of_new',
        'latitude_new_is_prefix_of_old',
        'latitude_same_float_value',
        
        'longitude_old_is_prefix_of_new',
        'longitude_new_is_prefix_of_old',
        'longitude_same_float_value',

    ])

    return subset, feature_cols

##############################
# Entity feature extraction
##############################

@lru_cache(maxsize=5000)
def add_entity_types(entity_id):
    """
    Add column with entity types (QIDs) for a given entity.
    """

    if pd.isna(entity_id) or not entity_id:
        return '[]'
    
    entity_id = str(entity_id).strip().replace('"', '')
    
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>

    SELECT ?o {{
        wd:{entity_id} wdt:P31 ?o .
    }}
    """

    try:
        response = requests.get(
            "https://qlever.cs.uni-freiburg.de/api/wikidata",
            params={'query': query},
            headers={'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            if not results:
                return False
            types = [binding['o']['value'].split('/')[-1] for binding in results.get('results', {}).get('bindings', [])]
            return str(types)
    except Exception as e:
        print(f"Error getting types for {entity_id}: {e}")
        return '[]'

@lru_cache(maxsize=5000)
def check_relationship(entity1, entity2, prop_id):

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    """
    Check if entity1 is part of entity2 (using P361).
    Returns True if there's a path: entity1 -P361+-> entity2
    """
    if pd.isna(entity1) or pd.isna(entity2) or not entity1 or not entity2:
        return False
    
    entity1 = str(entity1).strip().replace('"', '')
    entity2 = str(entity2).strip().replace('"', '')
    
    if entity1 == entity2:
        return False

    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>

    ASK {{
        wd:{entity1} wdt:{prop_id}+ wd:{entity2} .
    }}
    """

    try:
        response = requests.get(
            "https://qlever.cs.uni-freiburg.de/api/wikidata",
            params={'query': query},
            headers={'User-Agent': 'ExtractTypePaths/1.0','Accept': 'application/sparql-results+json'},
            timeout=30,
            verify=False
        )
        
        if response.status_code == 200:
            results = response.json()
            if not results:
                return False
            return results.get('boolean', False)
    except Exception as e:
        print(f"Error checking part-of {entity1} -> {entity2}: {e}")
    
        return False
    
@lru_cache(maxsize=5000)
def calculate_subclass_partof_features(entity1, entity2):
    """ 
        Check if there's a path p279 / p361 between  entity1 and entity2
    """

    if pd.isna(entity1) or pd.isna(entity2) or not entity1 or not entity2:
        return False
    
    entity1 = str(entity1).strip().replace('"', '')
    entity2 = str(entity2).strip().replace('"', '')
    
    if entity1 == entity2:
        return False
    
    query = f"""
    PREFIX wd: <http://www.wikidata.org/entity/>
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>

    ASK {{
        wd:{entity1} wdt:P279+ / wdt:P361+ wd:{entity2} .
    }}
    """

    try:
        response = requests.get(
            "https://qlever.cs.uni-freiburg.de/api/wikidata",
            params={'query': query},
            headers={'User-Agent': 'ExtractTypePaths/1.0', 'Accept': 'application/sparql-results+json'},
            timeout=30
        )
        
        if response.status_code == 200:
            results = response.json()
            return results.get('boolean', False)
    except Exception as e:
        print(f"Error checking part-of {entity1} -> {entity2}: {e}")
    
        return False

def calculate_relationship_features(row):

    # Feature 1 & 2: new_value is part of old_value or vice versa
    new_value_part_of_old_value = check_relationship(row['new_value'], row['old_value'], 'P361')
    old_value_part_of_new_value = check_relationship(row['old_value'], row['new_value'], 'P361')

    # Feature 3 & 4: new_value is subclass of old_value or vice versa
    new_value_subclass_old_value = check_relationship(row['new_value'], row['old_value'], 'P279')
    old_value_subclass_new_value = check_relationship(row['old_value'], row['new_value'], 'P279')

    # Feature 5 & 6: new_value has parts() old_value or vice versa
    new_value_has_parts_old_value = check_relationship(row['new_value'], row['old_value'], 'P527')
    old_value_has_parts_new_value = check_relationship(row['old_value'], row['new_value'], 'P527')

    # located in the administrative territorial entity # P131
    new_value_located_in_old_value = check_relationship(row['new_value'], row['old_value'], 'P131')
    old_value_located_in_new_value = check_relationship(row['old_value'], row['new_value'], 'P131')

    # is metaclass for P8225
    new_value_is_metaclass_for_old_value = check_relationship(row['old_value'], row['new_value'], 'P8225')
    old_value_is_metaclass_for_new_value = check_relationship(row['new_value'], row['old_value'], 'P8225')

    time.sleep(1)

    return pd.Series({
        'new_value_part_of_old_value': int(new_value_part_of_old_value),
        'old_value_part_of_new_value': int(old_value_part_of_new_value),
        'new_value_subclass_old_value': int(new_value_subclass_old_value),
        'old_value_subclass_new_value': int(old_value_subclass_new_value),
        'new_value_has_parts_old_value': int(new_value_has_parts_old_value),
        'old_value_has_parts_new_value': int(old_value_has_parts_new_value),
        'new_value_located_in_old_value': int(new_value_located_in_old_value),
        'old_value_located_in_new_value': int(old_value_located_in_new_value),
        'new_value_is_metaclass_for_old_value': int(new_value_is_metaclass_for_old_value),
        'old_value_is_metaclass_for_new_value': int(old_value_is_metaclass_for_new_value)
    })


def check(value1, value2, table_name, transitive_cache):
    """Check if value2 is in transitive closure of value1
    
        Example: to check if value1 is a subclass of value2, use table_name='subclass_transitive'
    """
    value1 = str(value1).replace('"', '').strip()
    value2 = str(value2).replace('"', '').strip()
    if table_name not in transitive_cache:
        return 0
    
    if value1 not in transitive_cache[table_name]:
        # print(f'the value {value1} is not in the cache for {table_name}', flush=True)
        return 0
    
    cleaned_trans = [val.strip() for val in transitive_cache[table_name][value1]]
    result = 1 if value2 in cleaned_trans else 0

    return result

def calculate_relationship_features_from_cache(row, transitive_cache):
    """Calculate relationship features using transitive cache"""

    new_value = str(row['new_value']).strip()
    old_value = str(row['old_value']).strip()

    return pd.Series({
        'new_value_subclass_old_value': check(new_value, old_value, 'subclass_transitive', transitive_cache),
        'old_value_subclass_new_value': check(old_value, new_value, 'subclass_transitive', transitive_cache),
        'new_value_located_in_old_value': check(new_value, old_value, 'located_in_transitive', transitive_cache),
        'old_value_located_in_new_value': check(old_value, new_value, 'located_in_transitive', transitive_cache),
        'new_value_has_parts_old_value': check(new_value, old_value, 'has_part_transitive', transitive_cache),
        'old_value_has_parts_new_value': check(old_value, new_value, 'has_part_transitive', transitive_cache),
        'new_value_part_of_old_value': check(new_value, old_value, 'part_of_transitive', transitive_cache),
        'old_value_part_of_new_value': check(old_value, new_value, 'part_of_transitive', transitive_cache),
    })

def create_entity_features(df, feature_cols):
    """Extract features for entity datatypes using labels"""

    entity_mask = df['datatype'].isin(WD_ENTITY_TYPES)

    df_entity, feature_cols = extract_text_features(df, 'old_value_label', 'new_value_label', entity_mask)
    df_entity, feature_cols = create_semantic_similarity_features(df_entity, 'old_value_label', 'new_value_label', feature_cols)

    # same label, != Q-id
    df_entity['is_link_change'] = ((df['old_value_label'] == df['new_value_label']) & (df['old_value'] != df['new_value'])).astype(int)

    feature_cols.append('is_link_change')

    df_mask = df_entity[entity_mask].copy()

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    FEATURES_PATH = os.path.join(BASE_DIR, 'features', 'gs_features_entity.csv')

    tqdm.pandas()
    try:
        print('Loading cache', flush=True)
        start_time = time.time()
        TRANSITIVE_CACHE_PATH = os.path.join('transitive_closures', 'transitive_closure_cache.pkl')
        with open(TRANSITIVE_CACHE_PATH, 'rb') as f:
            transitive_cache = pickle.load(f)

        end_time = time.time()
        print(f'Cache loaded in {end_time - start_time:.2f} seconds', flush=True)

        chunk_size = 100
        all_relationship_features = []
        
        for i in tqdm(range(0, len(df_mask), chunk_size), desc="Processing chunks"):
            chunk = df_mask.iloc[i:i+chunk_size]
            chunk_features = chunk.progress_apply(
                lambda row: calculate_relationship_features_from_cache(row, transitive_cache), 
                axis=1
            )
            all_relationship_features.append(chunk_features)
            
            checkpoint = pd.concat(all_relationship_features)
            column_list = ['revision_id', 'property_id', 'value_id', 'change_target'] + list(checkpoint.columns)
            df_mask.loc[checkpoint.index, checkpoint.columns] = checkpoint.values
            print(f'saving checkpoint of entity features to {FEATURES_PATH}', flush=True)
            df_mask.loc[checkpoint.index, column_list].to_csv(FEATURES_PATH, index=False)

        relationship_features = pd.concat(all_relationship_features)

        # add to df_entity
        for col in relationship_features.columns:
            df_mask[col] = 0  # Initialize with 0 for all rows
            df_mask.loc[relationship_features.index, col] = relationship_features[col]

        # use index of the mask df to update original df
        df_entity.loc[df_mask.index, relationship_features.columns] = df_mask[relationship_features.columns].values

        column_list = ['revision_id', 'property_id', 'value_id', 'change_target'] + list(relationship_features.columns)
        df_entity[column_list].to_csv(FEATURES_PATH, index=False)

    except Exception as e:
        print(f"Error calculating relationship features: {e}")
        raise e
        
    feature_cols.extend([
        'old_value_subclass_new_value',
        'new_value_subclass_old_value',
        'old_value_located_in_new_value',
        'new_value_located_in_old_value',
        'old_value_has_parts_new_value',
        'new_value_has_parts_old_value',
        'old_value_part_of_new_value',
        'new_value_part_of_old_value',
    ])

    return df_entity, feature_cols

#####################################
# Reverted edit feature extraction
#####################################

def get_next_changes(row, df, limit=None):
    # filter by same entity-property-value & higher timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors ='coerce')
    df = df.sort_values(by='timestamp') # by default it`s ascending=True

    next_changes = df[(df['entity_id'] == row['entity_id']) &
                         (df['property_id'] == row['property_id']) &
                         (df['value_id'] == row['value_id']) & 
                         (df['timestamp'] > row['timestamp'])].copy()
    
    if limit is not None:
        next_changes = next_changes.iloc[:limit].copy()

    return next_changes

def calc_keywords_in_comment_next_changes(row, df, keywords):
    
    next_changes = get_next_changes(row, df, limit=10)
    for _, row in next_changes.iterrows():
        if any(keyword in str(row['comment']).lower() for keyword in keywords):
            return 1
    return 0


def check_hash_revert(current_change, next_changes):
    """Check for hash reversion in next 10 changes"""
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

    curr_old_hash = current_change['old_hash']
    curr_new_hash = current_change['new_hash']
    
    for next_change in next_changes:
        next_old_hash = next_change['old_hash']
        next_new_hash = next_change['new_hash']
        # delete + update
        if (curr_old_hash == next_new_hash and curr_old_hash != '' and next_new_hash != '') or (curr_old_hash == '' and next_new_hash == '' and curr_new_hash == next_old_hash): # create
            return 1
    
    return 0

def calc_hash_reverted_next_10_changes(row, df):
    next_10_changes = get_next_changes(row, df)
    return check_hash_revert(row, [next_10_changes.iloc[i] for i in range(len(next_10_changes))])
        

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


def calc_is_reverted_within_day(current_change, df):
    is_reverted_within_day = 0
    current_ts = datetime.strptime(str(current_change['timestamp']).replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S%z")
    next_changes = get_next_changes(current_change, df)
    for _, row in next_changes.iterrows():
    
        future_timestamp = datetime.strptime(str(row['timestamp']).replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S%z")
        if (future_timestamp - current_ts).total_seconds() > 86400: # more than a day
            break

        if (
            check_hash_revert(current_change, [row])
        ):
            is_reverted_within_day = 1
            break
    
    return is_reverted_within_day

def num_changes_same_user_last_24h(current_change, df):
    current_ts = datetime.strptime(str(current_change['timestamp']).replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S%z")
    current_user = current_change['username']
    
    # Get all previous changes (changes before current_ts)
    previous_changes = df[(df['entity_id'] == current_change['entity_id']) &
                         (df['property_id'] == current_change['property_id']) &
                         (df['value_id'] == current_change['value_id']) & 
                         (df['timestamp'] < current_change['timestamp'])].copy()

    same_user_changes = previous_changes[previous_changes['username'] == current_user]
    
    window_start = current_ts - timedelta(hours=24)
    
    # changes by same user in last 24 hours
    num_changes_same_user_last_24h = 0
    for _, row in same_user_changes.iterrows():
        row_ts = datetime.strptime(str(row['timestamp']).replace("T", " ").replace("Z", ""), "%Y-%m-%d %H:%M:%S%z")
        if row_ts >= window_start:
            num_changes_same_user_last_24h += 1
    
    return num_changes_same_user_last_24h

def create_reverted_edit_features(df, feature_cols):

    df['user_type'] = [
        'BOT' if 'bot' in str(username).lower() 
        else 'USER' if ('bot' not in str(username).lower() and str(username) != '' and pd.notna(username))
        else 'ANONYMOUS' 
        for username in df['username']
    ]

    # Initialize columns first
    df['user_type_encoded'] = -1
    df['action_encoded'] = -1

    USER_TYPE_MAP = {'HUMAN': 0, 'BOT': 1, 'ANONYMOUS': 2}
    df['user_type_encoded'] = df['user_type'].map(USER_TYPE_MAP)

    df['timestamp'] = pd.to_datetime(df['timestamp'], errors ='coerce')

    df['day_of_week'] = df['timestamp'].dt.day_name()
    DAY_OF_WEEK_MAP = {'Friday': 0, 'Monday': 1, 'Saturday': 2, 'Sunday': 3, 'Thursday': 4, 'Tuesday': 5, 'Wednesday': 6}
    df[f'day_of_week_encoded'] = df['day_of_week'].map(DAY_OF_WEEK_MAP)

    df['hour_of_day'] = df['timestamp'].dt.hour
    df['is_weekend'] = (df['timestamp'].dt.weekday >= 5).astype(int)
    
    ACTION_MAP = {'CREATE': 0, 'DELETE': 1, 'UPDATE': 2}
    df['action_encoded'] = df['action'].map(ACTION_MAP)
    
    rv_keywords = ['revert', 'rv', 'undid', 'restore', 'rvv', 'vandal', 'undo']

    df['is_reverted_within_day'] = df.apply(lambda row: calc_is_reverted_within_day(row, df), axis=1).astype(int)

    df['num_changes_same_user_last_24h'] = df.apply(lambda row: num_changes_same_user_last_24h(row, df), axis=1)

    df['rv_keyword_in_comment_next_10'] = df.apply(lambda row: calc_keywords_in_comment_next_changes(row, df, rv_keywords),axis=1)

    df['hash_reversion_next_10'] = df.apply(lambda row: calc_hash_reverted_next_10_changes(row, df),axis=1)

    df['time_to_next_change_seconds'] = df.apply(lambda row: calc_time_to_change(row, df, option='next'),axis=1)

    df['time_to_prev_change_seconds'] = df.apply(lambda row: calc_time_to_change(row, df, option='prev'),axis=1)

    feature_cols = [
        'user_type_encoded',
        'day_of_week_encoded',
        'hour_of_day',
        'is_weekend',
        'action_encoded', # UPDATE/DELETE/CREATE
        'is_reverted_within_day', 
        'num_changes_same_user_last_24h',
        'rv_keyword_in_comment_next_10', 
        'hash_reversion_next_10', 
        'time_to_prev_change_seconds', 
        'time_to_next_change_seconds'
        # 'entity_age_years' # thought here: old entities are "important" so maybe they get more vandalism?
    ]

    # TODO: agregar latest_description, entity_type, etc para reverted edit
    # df, feature_cols = create_semantic_similarity_features(df, 'old_value', 'new_value', feature_cols)

    reverted_edits = df[df['label'] == 'reverted_edit'].copy()
    non_reverted_edits = df[df['label'] != 'reverted_edit'].copy()

    sampled_non_reverted = non_reverted_edits.groupby('anchor_revision_id').sample(n=1, random_state=42)

    df = pd.concat([reverted_edits, sampled_non_reverted], ignore_index=True)

    return df, feature_cols

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

    same_hour = 1 if delete_row['timestamp'] == create_row['timestamp'] else 0

    same_revision = 1 if delete_row['revision_id'] == create_row['revision_id'] else 0
    delete_before_create = 1 if delete_row['timestamp'] < create_row['timestamp'] else 0
    same_user = 1 if create_row['username'] == delete_row['username'] else 0

    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    embeddings = model.encode(
        [create_row['property_label'], delete_row['property_label']],
        device=device,
        show_progress_bar=False
    )

    similarity = util.cos_sim(embeddings[0], embeddings[1]).item()

    features = {
        'time_diff': time_diff,
        'same_hour': same_hour,
        'property_label_similarity': similarity,
        'same_revision': same_revision,
        'same_user': same_user,
        'delete_before_create': delete_before_create
    }
    
    return pd.Series(features)

def create_property_replacement_features(df, feature_cols):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    pair_features = df.groupby('pair_id').apply(lambda group: calculate_pair_features(group, model)).reset_index()

    df = df.merge(pair_features, on='pair_id', how='left')

    feature_cols = [
        'time_diff',
        'same_hour',
        'property_label_similarity',
        'same_revision',
        'same_user',
        'delete_before_create'
        # For this feature I need to get the changes to other entities with the same property
        #'' # check if entities of the same type get the same property deleted and added at similar times (e.g. within the same week) (?) how do i calculate this
    ]

    return df, feature_cols

