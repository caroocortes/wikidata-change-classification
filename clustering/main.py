import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from const import Config, DATATYPES_TO_CLUSTER
import os
from pathlib import Path
import logging

from const import Config, WD_ENTITY_TYPES, WD_STRING_TYPES
from cluster import perform_clustering, find_optimal_k, analyze_clusters
from features import create_text_features, create_quantity_features, create_globe_coordinate_features, create_time_features, create_entity_features
from experiment_tracker import ExperimentTracker
from data_loader import get_data_to_cluster


log_dir = Path('logs/')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "clustering.log"

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, mode="a"), 
        logging.StreamHandler()                 
    ]
)

logger = logging.getLogger(__name__)

def run_clustering_for_datatype(config: Config, tracker: ExperimentTracker, datatype: str):
    """Run clustering pipeline for a specific datatype"""
    
    logger.info(f"STARTING CLUSTERING FOR DATATYPE: {datatype.upper()}")
    
    # Configure for this datatype
    config.set_datatype(datatype)
    # Load data
    if config.data_path == '' or not config.data_path.exists():
        params = {
            'sql_untagged': config.sql_untagged,
            'only_updates': config.only_updates,
            'no_rank': config.no_rank,
            'datatype': config.datatype
        }
        df = get_data_to_cluster(params, logging=logger)
    else:   
        df = pd.read_parquet(config.data_path)
    
    # Filter data
    if config.action != '':
        df_filtered = df[df['action'] == config.action].copy()
    
    # In the DB it's NULL
    df_filtered['change_target'] = df_filtered['change_target'].fillna('')   

    if config.change_target == 'value':
        df_filtered = df_filtered[(df_filtered['change_target'] == '')].copy()
    elif config.change_target == 'datatype_metadata':
        df_filtered = df_filtered[(df_filtered['change_target'] != '') & (df_filtered['change_target'] != 'rank')].copy()
    
    if config.change_target == 'value':

        if config.datatype == 'entity':
            df_filtered = df_filtered[df_filtered['datatype'].isin(WD_ENTITY_TYPES)].copy()
        elif config.datatype == 'string':
            df_filtered = df_filtered[df_filtered['datatype'].isin(WD_STRING_TYPES)].copy()
        else:
            df_filtered = df_filtered[df_filtered['datatype'] == config.datatype].copy()
    
    logger.info(f"Filtered data shape: {df_filtered.shape}")
    
    if len(df_filtered) == 0:
        logger.info(f"No data found for {datatype}, skipping...")
        return
    
    # Extract or load features
    if config.features_path is None:
        logger.info(f"Extracting features for {datatype}...")
        
        if config.datatype == 'quantity':
            df_filtered, feature_cols = create_quantity_features(df_filtered, [])
        elif config.datatype == 'globecoordinate':
            df_filtered, feature_cols = create_globe_coordinate_features(df_filtered, [])
        elif config.datatype == 'time':
            df_filtered, feature_cols = create_time_features(df_filtered, [])
        else:
            return
        # elif config.datatype == 'entity':
        #     df_filtered, feature_cols = create_entity_features(df_filtered, [], semantic_similarity=True)
        # elif config.datatype == 'string':
        #     df_filtered, feature_cols = create_text_features(df_filtered, [], semantic_similarity=True)
        
        features_cols_change_id = feature_cols + ['revision_id', 'property_id', 'value_id', 'change_target']
        features_df = df_filtered[features_cols_change_id].copy()
        features_df[feature_cols] = features_df[feature_cols].astype(float).fillna(0)

        # Save features
        os.makedirs(f'{tracker.experiment_dir}/{config.datatype}', exist_ok=True)
        features_df.to_parquet(f'{tracker.experiment_dir}/{config.datatype}/features.parquet', compression='snappy')
    else:
        features_df = pd.read_parquet(config.features_path)
    
    # Prepare features for clustering
    features_df = features_df.drop(columns=['revision_id', 'property_id', 'value_id', 'change_target'], errors='ignore')
    features_df = features_df.astype(float)
    features_df = features_df.fillna(0)
    
    # Remove zero-variance features
    zero_std_cols = features_df.columns[features_df.std() == 0]
    logger.info(f"Features with zero variance: {zero_std_cols.tolist()}")
    
    if len(zero_std_cols) > 0:
        logger.info(f"Removing {len(zero_std_cols)} zero-variance features")
        features_df = features_df.drop(columns=zero_std_cols)
    
    X = features_df.astype(float).values
    
    # Scale and reduce dimensions
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print('Mean after scaling: ', X_scaled.mean(axis=0))
    print('Std after scaling: ', X_scaled.std(axis=0))
    
    pca = PCA(n_components=0.95) 
    X_reduced = pca.fit_transform(X_scaled)
    print('Mean after PCA: ', X_reduced.mean(axis=0))
    print(f"\nReduced from {X_scaled.shape[1]} to {X_reduced.shape[1]} features")
    
    logger.info(f"\nData shape before PCA: {X_scaled.shape}")
    logger.info(f"Data shape after PCA: {X_reduced.shape}")
    logger.info(f"Total data points: {X_reduced.shape[0]:,}")
    logger.info(f"Number of features: {X_reduced.shape[1]}")
    
    # Find optimal k or use configured k
    if config.n_clusters == 0:
        logger.info("FINDING OPTIMAL K")
        best_k = find_optimal_k(
            X_reduced, 
            random_state=config.random_state, 
            n_init=config.n_init, 
            max_iter=config.max_iter, 
            max_k=15, 
            min_k=3, 
            tracker=tracker
        )
        logger.info(f"Best k determined: {best_k}")
    else:
        best_k = config.n_clusters
    
    k = best_k  
    logger.info(f"\nUsing k={k} for clustering...")
    
    # Perform clustering
    logger.info('Clustering...')
    labels, _ = perform_clustering(X_reduced, n_clusters=k, random_state=config.random_state, n_init=config.n_init, max_iter=config.max_iter)
    
    # Save cluster assignments
    df_filtered['cluster_id'] = labels
    cluster_assignments = df_filtered[['revision_id', 'property_id', 'value_id', 'change_target', 'cluster_id']].copy()
    cluster_assignments.to_csv(f'{tracker.experiment_dir}/{config.datatype}/cluster_assignments.csv', index=False)
    
    # Analyze and save examples
    results_df = analyze_clusters(
        df_filtered, 
        labels, 
        tracker,
        output_file_examples=f'{config.datatype}/cluster_examples.csv',
        output_file_analysis=f'{config.datatype}/cluster_analysis.csv',
        n_examples=15
    )
    
    logger.info(f"Completed clustering for {datatype}")
    logger.info(f"Saved to: {tracker.experiment_dir}")


if __name__ == "__main__":
    config = Config()
    tracker = ExperimentTracker()
    
    logger.info(f"STARTING MULTI-DATATYPE CLUSTERING")
    logger.info(f"Datatypes to process: {DATATYPES_TO_CLUSTER}")
    
    # Run clustering for each datatype
    for datatype in DATATYPES_TO_CLUSTER:
        try:
            run_clustering_for_datatype(config, tracker, datatype)
        except Exception as e:
            logger.info(f"Error processing {datatype}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    logger.info("ALL CLUSTERING COMPLETED")