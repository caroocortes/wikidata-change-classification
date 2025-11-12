import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from const import Config
import os

from cluster import perform_clustering, find_optimal_k, analyze_clusters
from features import create_text_features
from experiment_tracker import ExperimentTracker
from data_loader import get_data_to_cluster

if "__main__":
    config = Config()

    tracker = ExperimentTracker()

    if config.data_path == '':

        params = {
            'sql_untagged': config.sql_untagged,
            'only_updates': config.only_updates,
            'no_rank': config.no_rank,
            'datatype': config.datatype
        }
        df = get_data_to_cluster(params)
    else:   
        df = pd.read_parquet(config.data_path)

    if config.action != '':
        df_filtered = df[df['action'] == config.action].copy()

    if config.change_target == 'value':
        df_filtered= df_filtered[(df_filtered['change_target'] == '')].copy()
    elif config.change_target == 'datatype_metaddata':
        df_filtered = df_filtered[(df_filtered['change_target'] != '') & (df_filtered['change_target'] != 'rank')].copy()

    if config.change_target == 'value':
        df_filtered = df_filtered[df_filtered['datatype'] == config.datatype].copy()

    if config.features_path is None:
        if config.datatype == 'string':
            df_filtered, feature_cols = create_text_features(df_filtered, [], semantic_similarity=True)
            features_cols_change_id = feature_cols + ['revision_id', 'property_id', 'value_id', 'change_target']
            features_df = df_filtered[features_cols_change_id].copy()
            os.makedirs(f'{config.cluster_dir}/features', exist_ok=True)
            features_df.to_parquet(f'{config.cluster_dir}/features/{config.datatype}_features.parquet', compression='snappy')
    else:
        features_df = pd.read_parquet(config.features_path)
    
    # only use the features for clustering, but saved with change id
    features_df = features_df.drop(columns=['revision_id', 'property_id', 'value_id', 'change_target'], errors='ignore')
    features_df = features_df.astype(float)
    features_df = features_df.fillna(0)

    zero_std_cols = features_df.columns[features_df.std() == 0]
    print(f"Features with zero variance: {zero_std_cols.tolist()}")

    # Remove them
    if len(zero_std_cols) > 0:
        print(f"Removing {len(zero_std_cols)} zero-variance features")
        features_df = features_df.drop(columns=zero_std_cols)

    X = features_df.astype(float).values  # df to numpy array

    # scale so std is ~1 and mean ~0
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print('Mean after scaling: ', X_scaled.mean(axis=0))
    print('Std after scaling: ', X_scaled.std(axis=0))

    pca = PCA(n_components=0.95) 
    X_reduced = pca.fit_transform(X_scaled)
    print('Mean after PCA: ', X_reduced.mean(axis=0))
    print(f"\nReduced from {X_scaled.shape[1]} to {X_reduced.shape[1]} features")

    # Add these debug prints
    print(f"\nData shape before PCA: {X_scaled.shape}")
    print(f"Data shape after PCA: {X_reduced.shape}")
    print(f"Total data points: {X_reduced.shape[0]:,}")
    print(f"Number of features: {X_reduced.shape[1]}")

    if config.n_clusters == 0:
        # Find optimal k
        print('\n' + "="*50)
        print("FINDING OPTIMAL K")
        print("="*50)
        best_k = find_optimal_k(
            X_reduced, 
            random_state=config.random_state, 
            n_init=config.n_init, 
            max_iter=config.max_iter, 
            max_k=15, 
            min_k=3, 
            tracker=tracker
        )
        print(f"Best k determined: {best_k}")
    else:
        best_k = config.n_clusters
    
    k = best_k  
    print(f"\nUsing k={k} for clustering...")

    # Cluster
    print('Clustering...')
    labels, _ = perform_clustering(X_reduced, n_clusters=k, random_state=config.random_state, n_init=config.n_init, max_iter=config.max_iter)

    # Analyze and save examples to CSV
    results_df = analyze_clusters(
        df_filtered, 
        labels, 
        tracker,
        output_file_examples=f'cluster_examples_{config.datatype}.csv',
        output_file_analysis=f'cluster_analysis_{config.datatype}.csv',
        n_examples=15
    )

    print(f"Saved examples to cluster_examples_{config.datatype}.csv")