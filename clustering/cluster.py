import os
import pandas as pd
import numpy as np
from Levenshtein import distance as levenshtein_distance
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
from collections import Counter
from sklearn.metrics import silhouette_score
from datetime import datetime
import json
import time

from experiment_tracker import ExperimentTracker

from pathlib import Path
from dotenv import load_dotenv
import psycopg2

WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']

DATA_FILE_PATH = 'changes_for_clustering.parquet'

# ==================== CLUSTERING ====================

def query_to_df(query, connection):
    try:
        with connection.cursor() as cur:
            cur.execute(query)
            
            if cur.description is not None:
                # Get column names
                colnames = [desc[0] for desc in cur.description]
                # Fetch all rows
                rows = cur.fetchall()
                # Return as Poras DataFrame
                return pd.DataFrame(rows, columns=colnames)
            else:
                print('Query did not return any rows')
                return pd.DataFrame()
    except Exception as e:
        raise e
    
def clean_for_parquet(df):
    """
    Clean DataFrame to be compatible with Parquet format
    Store complex objects as JSON strings
    """
    import json
    
    # Columns that might have dict/struct values
    json_cols = ['old_value', 'new_value']
    
    for col in json_cols:
        if col in df.columns:
            def to_json_string(x):
                if pd.isna(x) or x is None:
                    return None
                # If already a string, keep it
                if isinstance(x, str):
                    return x
                # If dict/list/complex object, convert to JSON
                try:
                    return json.dumps(x)
                except:
                    # Fallback to string conversion
                    return str(x)
            
            df[col] = df[col].apply(to_json_string)
    
    return df

    
def query_to_df_chunked(query, conn, chunksize=50000):
    """
    Execute query and return DataFrame using chunked reading
    to avoid memory issues
    """
    # First, disable parallel workers on the connection (before cursor)
    with conn.cursor() as temp_cur:
        temp_cur.execute("SET max_parallel_workers_per_gather = 0;")
    
    cur = conn.cursor(name='fetch_cursor')
    
    try:
        cur.itersize = chunksize
        
        print(f"Executing query...")
        cur.execute(query)
        
        # Fetch first batch to populate cur.description
        print(f"Fetching first batch...")
        rows = cur.fetchmany(chunksize)
        
        if not rows:
            print("Warning: No data returned from query")
            cur.close()
            return pd.DataFrame()
        
        
        # Get column names
        columns = [desc[0] for desc in cur.description]
        print(f"Query executed successfully. Columns: {len(columns)}")
        
        # Fetch in chunks
        chunks = []
        chunk_num = 0
        total_rows = 0
        
        while True:
            rows = cur.fetchmany(chunksize)
            if not rows:
                break
            
            chunk_df = pd.DataFrame(rows, columns=columns)
            chunk_df = clean_for_parquet(chunk_df)  # Clean before appending -> json valuies
            chunks.append(chunk_df)
            
            chunk_num += 1
            total_rows += len(rows)
            print(f"Fetched chunk {chunk_num}: {total_rows:,} rows total")
        
        print(f"Combining {len(chunks)} chunks...")
        df = pd.concat(chunks, ignore_index=True)
        
        print(f"Total rows fetched: {len(df):,}")
        return df
        
    except Exception as e:
        print(f"Error during query execution: {e}")
        raise
    finally:
        cur.close()


def get_data_from_db(conn, sql_untagged=True):

    print('Updating revision table with user_type column...')

    update_user_type = """

        CREATE INDEX IF NOT EXISTS idx_revision_user ON revision(username, user_id);

        CREATE INDEX IF NOT EXISTS idx_revision_username_lower ON revision(LOWER(username));
        
        ALTER TABLE  revision
        ADD COLUMN IF NOT EXISTS user_type VARCHAR DEFAULT NULL;

        UPDATE revision SET user_type = 'anonymous' WHERE user_id = '' AND username = '';

		UPDATE revision SET user_type = 'bot' WHERE user_type IS NULL AND LOWER(username) LIKE '%bot%';

        UPDATE revision SET user_type = 'human' WHERE user_type IS NULL;
    """

    with conn.cursor() as cur:
        cur.execute(update_user_type)
        conn.commit()

    print('Updated user_type column in revision table', flush=True)

    print('Creating indexes to speed up data extraction...', flush=True)

    index_vc = """ 
        CREATE INDEX IF NOT EXISTS idx_value_change_revision_id 
        ON value_change(revision_id);
    """

    index_vcm = """
        CREATE INDEX IF NOT EXISTS idx_value_change_metadata_revision_id 
        ON value_change_metadata(revision_id, property_id, value_id, change_target);
    """

    with conn.cursor() as cur:
        cur.execute(index_vc)
        cur.execute(index_vcm)
        conn.commit()

    print('Created indexes', flush=True)

    print('\nGoing to extract data from db', flush=True)
    query = """
        SELECT 
            c.revision_id,
            r.entity_id,
            r.entity_label,
            c.property_id,
            c.value_id,
            c.property_label,
            c.old_value,
            c.old_value_label,
            c.new_value,
            c.new_value_label,
            c.datatype,
            c.change_target,
            c.action,
            c.target,
            c.old_hash,
            c.new_hash,
            r.timestamp,
            r.user_type,
            r.user_id,
            r.comment,
            COUNT(*) OVER (PARTITION BY c.revision_id) as num_changes_in_revision,
            EXTRACT(EPOCH FROM (
                r.timestamp - MIN(r.timestamp) OVER (PARTITION BY r.entity_id)
            )) / 86400.0 as entity_age_days,
            CASE 
                WHEN c.property_label IS NULL THEN TRUE
                ELSE FALSE
            END AS deleted_property,
            CASE 
                WHEN cm.value IS NULL THEN 10000.0
                ELSE cm.value
            END AS change_magnitude
        FROM 
            revision r 
            JOIN value_change c ON c.revision_id = r.revision_id
            LEFT JOIN value_change_metadata cm 
                ON c.revision_id = cm.revision_id 
                AND c.property_id = cm.property_id 
                AND c.value_id = cm.value_id 
                AND c.change_target = cm.change_target
    """

    if sql_untagged:
        query += """
        WHERE NOT 
            (typo OR value_refinement OR formatting OR reverted_edit OR reversion OR value_unrefinement OR link_fix OR property_replacement)
        """

    print('\nExecuting query...', flush=True)
    df = query_to_df_chunked(query, conn, chunksize=50000)

    if len(df) > 0:
        df.to_parquet(DATA_FILE_PATH, compression='snappy')
        print(f'Saved {len(df):,} rows to parquet', flush=True)
    else:
        print('No data to save!', flush=True)

    import sys

    sys.stdout.flush()
    
    return df

def perform_clustering(X, method='kmeans', n_clusters=10, **kwargs):
    """
    Perform clustering with different methods
    X is already scaled
    """
    
    if method == 'kmeans':
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(X)
        
    elif method == 'dbscan':
        eps = kwargs.get('eps', 0.5)
        min_samples = kwargs.get('min_samples', 5)
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(X)
    
    return labels, X


def find_optimal_k(X_scaled, max_k=20, save_plot=True):
    """
    Use elbow method to find optimal number of clusters
    """
    inertias = []
    silhouette_scores = []
    K = range(2, max_k + 1)
    
    print(f"Testing k from 2 to {max_k}...")
    for k in K:
        print(f"k={k}...", end=' ')
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
        
        # Calculate silhouette score
        labels = kmeans.labels_
        sil_score = silhouette_score(X_scaled, labels, sample_size=min(10000, len(X_scaled)))
        silhouette_scores.append(sil_score)
        print(f"Silhouette: {sil_score:.3f}")
    
    # Plot both metrics
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 5))
    
    # Elbow curve
    ax1.plot(K, inertias, 'bx-', linewidth=2, markersize=8)
    ax1.set_xlabel('Number of clusters (k)', fontsize=12)
    ax1.set_ylabel('Inertia', fontsize=12)
    ax1.set_title('Elbow Method For Optimal k', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    # Silhouette scores
    ax2.plot(K, silhouette_scores, 'go-', linewidth=2, markersize=8)
    ax2.set_xlabel('Number of clusters (k)', fontsize=12)
    ax2.set_ylabel('Silhouette Score', fontsize=12)
    ax2.set_title('Silhouette Score (Higher = Better)', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    
    # Mark best silhouette
    best_k = K[silhouette_scores.index(max(silhouette_scores))]
    ax2.axvline(best_k, color='red', linestyle='--', label=f'Best k={best_k}')
    ax2.legend()
    
    plt.tight_layout()
    
    if save_plot:
        plt.savefig('elbow_analysis.png', dpi=300, bbox_inches='tight')
        print(f"\nSaved plot to elbow_analysis.png")
    
    plt.show()
    
    # Print recommendation
    print("\n" + "="*50)
    print(f"BEST K (by Silhouette Score): {best_k}")
    print("="*50)
    
    # Save metrics
    metrics_df = pd.DataFrame({
        'k': list(K),
        'inertia': inertias,
        'silhouette_score': silhouette_scores
    })
    metrics_df.to_csv('clustering_metrics.csv', index=False)
    print("Saved metrics to clustering_metrics.csv")
    
    return K, inertias, silhouette_scores, best_k

# ==================== VISUALIZATION ====================

def visualize_clusters(X_scaled, labels, method='pca'):
    """
    Visualize clusters in 2D
    """
    if method == 'pca':
        reducer = PCA(n_components=2, random_state=42)
        X_2d = reducer.fit_transform(X_scaled)
        title = f'PCA Visualization (explained var: {reducer.explained_variance_ratio_.sum():.2%})'
        
    elif method == 'tsne':
        reducer = TSNE(n_components=2, random_state=42, perplexity=30)
        X_2d = reducer.fit_transform(X_scaled)
        title = 't-SNE Visualization'
    
    plt.figure(figsize=(12, 8))
    scatter = plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels, cmap='tab20', alpha=0.6)
    plt.colorbar(scatter)
    plt.title(title)
    plt.xlabel('Component 1')
    plt.ylabel('Component 2')
    plt.show()


def analyze_clusters(df, labels, tracker=None, output_file_examples='cluster_examples.csv', output_file_analysis='cluster_analysis.csv', n_examples=20):
    """
    Enhanced cluster analysis with detailed statistics
    """
    df_with_clusters = df.copy()
    df_with_clusters['cluster'] = labels
    
    from io import StringIO
    output = StringIO()
     
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    
    # Overall statistics
    header = f"CLUSTERING ANALYSIS - {n_clusters} clusters\n"
    header += "=" * 80 + "\n\n"
    header += f"Total samples: {len(df):,}\n"
    header += f"Cluster sizes:\n"
    
    cluster_sizes = Counter(labels)
    for cluster_id in sorted(cluster_sizes.keys()):
        size = cluster_sizes[cluster_id]
        pct = size / len(df) * 100
        header += f"  Cluster {cluster_id}: {size:,} ({pct:.1f}%)\n"
    
    print(header)
    output.write(header + "\n")
    
    # For each cluster
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:
            continue
        
        cluster_data = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
        cluster_output = f"\n{'='*80}\n"
        cluster_output += f"CLUSTER {cluster_id} (n={len(cluster_data):,}, {len(cluster_data)/len(df)*100:.1f}%)\n"
        cluster_output += f"{'='*80}\n\n"
        
        # User type distribution
        cluster_output += "USER TYPE:\n"
        for user_type, count in cluster_data['user_type'].value_counts().head(3).items():
            cluster_output += f"  {user_type}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"

        # Datatype distribution
        cluster_output += "\nDATATYPE:\n"
        for dtype, count in cluster_data['datatype'].value_counts().head(20).items():
            cluster_output += f"  {dtype}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
        
        # Action distribution
        cluster_output += "\nACTION:\n"
        for action, count in cluster_data['action'].value_counts().items():
            cluster_output += f"  {action}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"

        # Target distribution
        cluster_output += "\nTARGET:\n"
        for target, count in cluster_data['target'].value_counts().items():
            cluster_output += f"  {target}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
        
        # Top properties
        cluster_output += "\nTOP 10 PROPERTIES:\n"
        top_props = cluster_data['property_id'].value_counts().head(10)
        for prop, count in top_props.items():
            if 'property_label' in cluster_data.columns:
                label = cluster_data[cluster_data['property_id'] == prop]['property_label'].iloc[0]
                cluster_output += f"  {prop} ({label}): {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
            else:
                cluster_output += f"  {prop}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
        
        # Change magnitude (excluding placeholder)
        if 'change_magnitude' in cluster_data.columns:
            actual_mag = cluster_data[cluster_data['change_magnitude'] != 10000]['change_magnitude']
            if len(actual_mag) > 0:
                cluster_output += f"\nCHANGE MAGNITUDE (excluding placeholder):\n"
                cluster_output += f"  Count with metadata: {len(actual_mag):,} ({len(actual_mag)/len(cluster_data)*100:.1f}%)\n"
                cluster_output += f"  Median: {actual_mag.median():.2f}\n"
                cluster_output += f"  Mean: {actual_mag.mean():.2f}\n"
                cluster_output += f"  Range: [{actual_mag.min():.2f}-{actual_mag.max():.2f}]\n"
        
        print(cluster_output)
        output.write(cluster_output + "\n")
    
    # Save to tracker if provided
    if tracker:
        tracker.save_text(output.getvalue(), tracker.experiments_dir + '/' + output_file_analysis)

    # Get examples
    output_rows = []
    
    for cluster_id in sorted(set(labels)):
        cluster = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
        
        if len(cluster) == 0:
            continue
        
        # Get examples
        example_cols = ['revision_id', 'entity_id', 'entity_label', 'property_id', 'property_label', 
                       'old_value', 'new_value', 'old_value_label', 'new_value_label', 
                       'user_type', 'datatype', 'change_target', 'value_id', 'action', 'timestamp']
        example_cols = [col for col in example_cols if col in cluster.columns]
        
        # Sample examples
        examples = cluster[example_cols].sample(min(n_examples, len(cluster)), random_state=42)
        
        for idx, row in examples.iterrows():
            output_row = {
                'cluster_id': cluster_id,
                'cluster_size': len(cluster),
                'cluster_pct': len(cluster) / len(df_with_clusters) * 100,
            }
            
            # Add example data
            for col in example_cols:
                output_row[col] = row[col]
            
            output_rows.append(output_row)
    
    # Convert to DataFrame and save
    results_df = pd.DataFrame(output_rows)
    results_df.to_csv(tracker.experiments_dir + '/' + output_file_examples, index=False)
    print(f"\n Saved {len(results_df)} examples to {output_file_examples}")

    return results_df


def calculate_cluster_metrics(df_with_clusters, X_scaled, labels):
    """
    Calculate clustering quality metrics
    """
    from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score

    
    # Sample for silhouette (expensive on large datasets)
    sample_size = min(10000, len(X_scaled))
    sample_indices = np.random.choice(len(X_scaled), sample_size, replace=False)
    
    metrics = {
        'n_clusters': len(set(labels)) - (1 if -1 in labels else 0),
        'n_samples': len(df_with_clusters),
        'silhouette_score': silhouette_score(X_scaled[sample_indices], labels[sample_indices]),
        'calinski_harabasz_score': calinski_harabasz_score(X_scaled, labels),
        'davies_bouldin_score': davies_bouldin_score(X_scaled, labels),
    }
    
    # Cluster size statistics
    cluster_sizes = df_with_clusters['cluster'].value_counts()
    metrics['largest_cluster_size'] = int(cluster_sizes.max())
    metrics['smallest_cluster_size'] = int(cluster_sizes.min())
    metrics['largest_cluster_pct'] = float(cluster_sizes.max() / len(df_with_clusters) * 100)
    
    return metrics


#################### NEW

def extract_time_features(df, feature_cols):
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
        # This handles extreme dates better
        old_timestamps = df.loc[valid_mask, 'old_time_parsed'].astype('int64') / 10**9  # Convert to seconds
        new_timestamps = df.loc[valid_mask, 'new_time_parsed'].astype('int64') / 10**9
        df.loc[valid_mask, 'time_diff_days'] = ((new_timestamps - old_timestamps) / 86400).abs()
    
    df.loc[valid_mask, 'time_diff_years'] = df.loc[valid_mask, 'time_diff_days'] / 365.25

    df.loc[valid_mask, 'levenshtein_distance'] = df.loc[valid_mask].apply(
        lambda row: levenshtein_distance(row['old_value'], row['new_value']), 
        axis=1
    )

    feature_cols.extend([
        'time_diff_days',
        'time_diff_years',
        'levenshtein_distance'
    ])

    return df, feature_cols

def extract_text_features(new, old, idx, df):
    new_norm = new.lower().strip().replace(' ', '').replace(r'[^\w\s]', '').replace(r'-–—_', '').replace(r'["“”‘’\[\]\(\)\{\}]', '')
    old_norm = old.lower().strip().replace(' ', '').replace(r'[^\w\s]', '').replace(r'-–—_', '').replace(r'["“”‘’\[\]\(\)\{\}]', '')
    df.loc[idx, 'levenshtein_distance'] = levenshtein_distance(old_norm, new_norm)
    
    # Length changes
    df.loc[idx, 'length_diff_abs'] = abs(len(new) - len(old))
    
    # Formatting changes
    df.loc[idx, 'case_differs'] = (old != new) and (old.lower() == new.lower())
    df.loc[idx, 'spaces_differs'] = (old != new) and (old.replace(' ', '') == new.replace(' ', ''))
    df.loc[idx, 'punct_differs'] = (old != new) and (old.replace(r'[^\w\s]', '') == new.replace(r'[^\w\s]', ''))
    df.loc[idx, 'hyph_dash_differs'] = (old != new) and (old.replace(r'-–—_', '') == new.replace(r'-–—_', ''))
    df.loc[idx, 'brackets_differs'] = (old != new) and (old.replace(r'["“”‘’\[\]\(\)\{\}]', '') == new.replace(r'["“”‘’\[\]\(\)\{\}]', ''))

    # Token-level
    old_tokens = old.split()
    new_tokens = new.split()
    df.loc[idx, 'token_count_old'] = len(old_tokens)
    df.loc[idx, 'token_count_new'] = len(new_tokens)
    df.loc[idx, 'token_overlap'] = len(set(old_tokens) & set(new_tokens)) / max(len(set(old_tokens) | set(new_tokens)), 1)
    
    # Containment
    df.loc[idx, 'old_in_new'] = int(old in new)
    df.loc[idx, 'new_in_old'] = int(new in old)
    
    return df

def create_text_features(df, feature_cols):

    string_mask = df['datatype'].isin(WD_STRING_TYPES)
    
    for idx in df[string_mask].index:
        old = str(df.loc[idx, 'old_value'])
        new = str(df.loc[idx, 'new_value'])
        
        if old == '{}' or new == '{}':
            continue
        
        df = extract_text_features(new, old, idx, df)

    feature_cols.extend([
        'levenshtein_distance',
        'length_diff_abs',
        'case_differs',
        'spaces_differs',
        'punct_differs',
        'hyph_dash_differs',
        'brackets_differs',
        'token_count_old',
        'token_count_new',
        'token_overlap',
        'old_in_new',
        'new_in_old'
    ])
    
    return df, feature_cols

def create_entity_features(df, feature_cols):
    entity_mask = df['datatype'].isin(WD_ENTITY_TYPES)
    
    for idx in df[entity_mask].index:
        old_id = str(df.loc[idx, 'old_value'])
        new_id = str(df.loc[idx, 'new_value'])
        old_label = str(df.loc[idx, 'old_value_label'])
        new_label = str(df.loc[idx, 'new_value_label'])
        
        if old_id == '{}' or new_id == '{}':
            continue
        
        # Label similarity
        if old_label and new_label and old_label != 'nan' and new_label != 'nan':
            df = extract_text_features(new_label, old_label, idx, df)

    feature_cols.extend([
        'levenshtein_distance',
        'length_diff_abs',
        'case_differs',
        'spaces_differs',
        'punct_differs',
        'hyph_dash_differs',
        'brackets_differs',
        'token_count_old',
        'token_count_new',
        'token_overlap',
        'old_in_new',
        'new_in_old'
    ])

    return df, feature_cols

def create_quantity_features(df, feature_cols):
    quant_mask = df['datatype'] == 'quantity'
    
    for idx in df[quant_mask].index:
        try:
            old_val = float(str(df.loc[idx, 'old_value'])).replace('+', '') # because I convert to float the '-' remains
            new_val = float(str(df.loc[idx, 'new_value'])).replace('+', '')
            
            df.loc[idx, 'value_diff_abs'] = abs(old_val - new_val)
            df.loc[idx, 'sign_change'] = (old_val * new_val < 0) # sign change

            df.loc[idx, 'levenshtein_distance'] = levenshtein_distance(str(old_val), str(new_val))
             
        except:
            pass
    
    feature_cols.extend([
        'value_diff_abs',
        'sign_change',
        'levenshtein_distance'
    ])

    return df, feature_cols

def create_globe_coordinate_features(df, feature_cols):
    coordinate_mask = df['datatype'] == 'globecoordinate'
    
    for idx in df[coordinate_mask].index:
        try:
            old_val = json.loads(df.loc[idx, 'old_value'])
            new_val = json.loads(df.loc[idx, 'new_value'])
            
            df.loc[idx, 'latitude_diff_abs'] = abs(new_val['latitude'] - old_val['latitude'])
            df.loc[idx, 'longitude_diff_abs'] = abs(new_val['longitude'] - old_val['longitude'])

            df.loc[idx, 'longitude_lev_dist'] = levenshtein_distance(new_val['longitude'], old_val['longitude'])
            df.loc[idx, 'latitude_lev_dist'] = levenshtein_distance(new_val['latitude'], old_val['latitude'])
            
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
        'longitude_lev_dist',
        'latitude_lev_dist',
        'coordinate_distance_km'
    ])

    return df, feature_cols

def extract_general_change_features(df, feature_cols):
    """
    General features
    """
    df = df.copy()

    label_encoders = {}
    categorical_cols = [
        'user_type',  # bot/human/anonymous
        'datatype',
        'action'
    ]
    
    for col in categorical_cols:
        if col in df.columns:
            le = LabelEncoder()
            df[f'{col}_encoded'] = le.fit_transform(df[col].astype(str))
            label_encoders[col] = le

    feature_cols.extend([
        'datatype_encoded',
        'user_type_encoded',
        'action_encoded'
    ])

    return df, feature_cols

def create_property_features(df):
    """
    Represent properties by how they're typically edited
    """

    # Group by property and calculate min/max timestamp, count of changes
    change_rate = df.groupby('property_id').agg({
        'timestamp': ['min', 'max', 'count']
    }).reset_index()

    change_rate.columns = ['property_id', 'first_change', 'last_change', 'total_changes']

    # Calculate time between first and last change in days
    change_rate['days_active'] = (
        pd.to_datetime(change_rate['last_change']) - 
        pd.to_datetime(change_rate['first_change'])
    ).dt.days

    # Avg changes per day
    change_rate['changes_per_day'] = (
        change_rate['total_changes'] / change_rate['days_active'].replace(0, 1)
    )

    df['is_bot'] = (df['user_type_encoded'] == 'bot').astype(int)
    df['is_human'] = (df['user_type_encoded'] == 'human').astype(int)
    df['is_anon'] = (df['user_type_encoded'] == 'anonymous').astype(int)
    df['is_update'] = (df['action_encoded'] == 'UPDATE').astype(int)

    property_stats = df.groupby('property_id').agg({
        'is_update': 'mean',  # update rate
        'is_bot': 'mean',     # bot rate
        'is_human': 'mean',   # human rate
        'is_anon': 'mean',    # anonymous rate
        'change_magnitude': ['mean', 'std'],
    }).fillna(0)

    # Rename for clarity
    property_stats.columns = ['_'.join(col).strip('_') if isinstance(col, tuple) else col 
                            for col in property_stats.columns]

    property_stats = property_stats.rename(columns={
        'is_update': 'update_rate',
        'is_bot': 'bot_rate',
        'is_human': 'human_rate',
        'is_anon': 'anon_rate'
    })

    # Add the changes_per_day to stats
    property_stats = property_stats.merge(
        change_rate[['property_id', 'changes_per_day']], 
        on='property_id', 
        how='left'
    )

    property_stats.columns = ['property_id'] + [f'prop_{c}' for c in property_stats.columns[1:]]

    df = df.merge(property_stats, on='property_id', how='left')
    
    return df

def create_entity_features(df):
    """
    Represent entities by their edit history
    """

    # For each (entity, property) pair, get change statistics
    entity_change_rate = df.groupby(['entity_id', 'property_id']).agg({
        'timestamp': ['min', 'max', 'count']
    }).reset_index()

    entity_change_rate.columns = ['entity_id', 'property_id', 'first_change', 'last_change', 'changes']

    # Calculate time span for each entity-property pair
    entity_change_rate['days_active'] = (
        pd.to_datetime(entity_change_rate['last_change']) - 
        pd.to_datetime(entity_change_rate['first_change'])
    ).dt.days

    entity_change_rate = entity_change_rate.rename(columns={
        'changes': 'ent_prop_total_changes',
        'days_active': 'ent_prop_days_active'
    })

    # Calculate avg changes per day for entity-property pair
    entity_change_rate['ent_prop_changes_per_day'] = (
        entity_change_rate['ent_prop_total_changes'] / 
        entity_change_rate['ent_prop_days_active'].replace(0, 1)
    )

    # Select features to merge
    entity_prop_features = entity_change_rate[[
        'entity_id', 
        'property_id', 
        'ent_prop_total_changes',
        'ent_prop_days_active',
        'ent_prop_changes_per_day'
    ]]

    # Merge back to original dataframe on entity_id and property_id
    df = df.merge(entity_prop_features, on=['entity_id', 'property_id'], how='left')

    return df

def add_temporal_patterns(df, feature_cols):
    """
    When edits happen might reveal patterns
    """
    df = df.copy()
    
    # Time since entity creation when edit happens
    df['edit_timing_ratio'] = df['entity_age_days'] / (df['entity_age_days'] + 1)
    
    # Burst editing (multiple changes in short time)
    df = df.sort_values('timestamp')
    df['time_since_last_edit'] = df.groupby('entity_id')['timestamp'].diff().dt.total_seconds() / 3600
    df['is_burst_edit'] = (df['time_since_last_edit'] < 1).astype(int)  # within 1 hour
    
    feature_cols.extend([
        'edit_timing_ratio',
        'day_of_week',
        'hour_of_day',
    ])

    return df, feature_cols


def prepare_features(df, datatype):
    
    feature_cols = []

    # Extract change descriptors
    df, feature_cols = extract_general_change_features(df, feature_cols)

    if datatype == 'quantity':
        df, feature_cols = create_quantity_features(df, feature_cols)
    elif datatype == 'time':
        df, feature_cols = extract_time_features(df, feature_cols)
    elif datatype == 'globecoordinate':
        df, feature_cols = create_globe_coordinate_features(df, feature_cols)
    elif datatype == 'string':
        df, feature_cols = create_text_features(df, feature_cols)
    elif datatype in 'entity':
        df, feature_cols = create_entity_features(df, feature_cols)
    
    # Property characteristics 
    # df = create_property_features(df)

    # Entityt characteristics 
    # df = create_entity_features(df)
    
    # Temporal patterns of changes
    # df, feature_cols = add_temporal_patterns(df, feature_cols)
    
    feature_cols = [col for col in feature_cols if col in df.columns]
    X = df[feature_cols].fillna(0)
    
    return X, df


def main_discovery_cluster(change_target='value', datatype='string'):
    df = pd.read_parquet('changes_for_clustering.parquet')

    if change_target == 'value':
        df_updates = df[(df['action'] == 'UPDATE') & (df['change_target'] == '')].copy()
    elif change_target == 'datatype_metaddata':
        df_updates = df[(df['action'] == 'UPDATE') & (df['change_target'] != '') & (df['change_target'] != 'rank')].copy()
    else: # rank updates don't make much sense to analyze
        return
    
    if change_target == 'value':
        df_updates = df_updates[df_updates['datatype'] == datatype].copy()
    
    print(f"Total {change_target} updates: {len(df_updates):,}")
     
    # Sample if needed
    # if len(df_updates) > 400000:
    #     print("Sampling data...")
    #     df_updates = stratified_sample_with_validation(file_path='changes_for_clustering.parquet', n_samples=400000, df=df_updates)
    
    # Prepare features
    print('Prepare features')
    X, df_updates = prepare_features(df_updates, datatype=datatype)

    X = X.astype(float).values  # Convert DataFrame to numpy array

    X_clipped = np.clip(X, -10000, 10000)  # Reasonable range for your features

    num_clipped = (X != X_clipped).sum()
    print(f"Clipped {num_clipped:,} extreme values")

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # After scaling, std should be ~1 and mean ~0
    std_values_scaled = X_scaled.std(axis=0)
    print("\nStatistics after scaling:")
    print(f"Mean: {std_values_scaled.mean():.3f}")
    print(f"Std: {std_values_scaled}")

    # Then do PCA
    pca = PCA(n_components=0.95)  # Keep 95% variance
    X_reduced = pca.fit_transform(X_scaled)
    print(f"\nReduced from {X_scaled.shape[1]} to {X_reduced.shape[1]} features")

    # Find optimal k
    print('\n' + "="*50)
    print("FINDING OPTIMAL K")
    print("="*50)
    K, inertias, silhouette_scores, best_k = find_optimal_k(X_reduced, max_k=20)
    
    print(f"Best k determined: {best_k}")
    k = best_k  
    print(f"\nUsing k={k} for clustering...")
    
    # Cluster
    print('Clustering...')
    
    # Try with a different 
    labels, _ = perform_clustering(X_reduced, n_clusters=k)
    
    tracker = ExperimentTracker()
    # Analyze and save to CSV
    results_df = analyze_clusters(
        df_updates, 
        labels, 
        tracker,
        output_file_examples=f'cluster_examples_{datatype}.csv',
        output_file_analysis=f'cluster_analysis_{datatype}',
        n_examples=20
    )
    
    print("Saved examples to cluster_examples_summary.csv")

    # # ========================================
    # # HIERARCHICAL CLUSTERING
    # # ========================================
    # print('\n' + "="*50)
    # print("HIERARCHICAL CLUSTERING")
    # print("="*50)
    
    # from sklearn.cluster import AgglomerativeClustering
    # from sklearn.metrics import silhouette_score
    
    # # Try hierarchical with same k
    # print(f"Running Agglomerative Clustering with k={k}...")
    # agg = AgglomerativeClustering(n_clusters=k, linkage='ward')
    # labels_hier = agg.fit_predict(X_reduced)
    
    # # Calculate silhouette score
    # sil_hier = silhouette_score(X_reduced, labels_hier, sample_size=min(10000, len(X_reduced)))
    # sil_kmeans = silhouette_score(X_reduced, labels, sample_size=min(10000, len(X_reduced)))
    
    # print(f"\nSilhouette Scores:")
    # print(f"  K-Means:      {sil_kmeans:.3f}")
    # print(f"  Hierarchical: {sil_hier:.3f}")
    
    # # Analyze and save hierarchical results
    # results_df_hier = analyze_clusters(
    #     df_updates, 
    #     labels_hier, 
    #     tracker,
    #     output_file='cluster_examples_hierarchical.csv',
    #     n_examples=100
    # )
    
    # print("Saved Hierarchical examples to cluster_examples_hierarchical.csv")
    
    # # Compare cluster distributions
    # print("\n" + "="*50)
    # print("CLUSTER SIZE COMPARISON")
    # print("="*50)
    
    # kmeans_sizes = pd.Series(labels).value_counts().sort_index()
    # hier_sizes = pd.Series(labels_hier).value_counts().sort_index()
    
    # comparison = pd.DataFrame({
    #     'K-Means': kmeans_sizes,
    #     'Hierarchical': hier_sizes,
    #     'Difference': hier_sizes - kmeans_sizes
    # })
    # print(comparison)

def get_data_to_cluster(sql_untagged=True):
    """
    Get data from DB and save to parquet for clustering
    """
    script_dir = Path(__file__).parent

    root_dir = script_dir.parent

    dotenv_path = root_dir / ".env"
    load_dotenv(dotenv_path)

    DB_USER = os.environ.get("DB_USER")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME")
    DB_HOST = os.environ.get("DB_HOST")
    DB_PORT = os.environ.get("DB_PORT")

    print('Connecting to database...', flush=True)
    print(DB_HOST, DB_PORT, DB_NAME, DB_USER)

    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT
    )

    print('Connected to database.', flush=True)
    df = get_data_from_db(conn, sql_untagged=sql_untagged)

    conn.close()
    return df

if __name__ == "__main__":

    get_data_to_cluster(sql_untagged=True)

    # start_time = time.time()
    # main_discovery_cluster()
    # print('Total time: %.2f seconds' % (time.time() - start_time))


    