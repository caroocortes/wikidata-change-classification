import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import matplotlib.pyplot as plt
import seaborn as sns
from collections import Counter

# Load your data
# Assuming you have a DataFrame with your changes
df = pd.read_csv('your_changes.csv')  # or load from your database

# ==================== FEATURE ENGINEERING ====================

# Create datatype-specific features
def extract_datatype_features(df):
    """Extract features specific to each datatype"""
    
    # For quantities
    df['is_quantity'] = (df['datatype'] == 'quantity').astype(int)
    df.loc[df['is_quantity'] == 1, 'quantity_has_unit'] = df['new_value'].str.contains('unit', na=False).astype(int)
    
    # For time values
    df['is_time'] = (df['datatype'] == 'time').astype(int)
    df.loc[df['is_time'] == 1, 'time_precision'] = df['new_value'].str.extract(r'precision:(\d+)').astype(float)
    
    # For entities
    df['is_entity'] = (df['datatype'] == 'wikibase-item').astype(int)
    
    # For strings
    df['is_string'] = (df['datatype'] == 'string').astype(int)
    df.loc[df['is_string'] == 1, 'string_length_category'] = pd.cut(
        df['new_value'].str.len(), 
        bins=[0, 10, 50, 200, float('inf')],
        labels=['very_short', 'short', 'medium', 'long']
    )
    
    # For coordinates
    df['is_coordinate'] = (df['datatype'] == 'globe-coordinate').astype(int)
    
    return df

def prepare_features(df):
    """
    Prepare features for clustering
    """
    features_df = df.copy()
    
    # Categorical encoding
    label_encoders = {}
    categorical_cols = [
        'user_type',  # bot/human/anonymous
        'entity_label',
        'property_label',
        'datatype',
        'change_table',  # value_changes/reference_changes/qualifier_changes
        'action'  # create/delete/update
    ]
    
    for col in categorical_cols:
        if col in features_df.columns:
            le = LabelEncoder()
            features_df[f'{col}_encoded'] = le.fit_transform(features_df[col].astype(str))
            label_encoders[col] = le
    
    # Temporal features
    if 'timestamp' in features_df.columns:
        features_df['timestamp'] = pd.to_datetime(features_df['timestamp'])
        features_df['day_of_week'] = features_df['timestamp'].dt.dayofweek
        features_df['hour_of_day'] = features_df['timestamp'].dt.hour
        features_df['is_weekend'] = features_df['day_of_week'].isin([5, 6]).astype(int)
    
    # Boolean features
    boolean_cols = ['was_redirected']
    for col in boolean_cols:
        if col in features_df.columns:
            features_df[col] = features_df[col].astype(int)
    
    # Handle value changes (simplified representation)
    # For initial clustering, we'll use indicators rather than actual values
    features_df['has_old_value'] = (~features_df['old_value'].isna()).astype(int)
    features_df['has_new_value'] = (~features_df['new_value'].isna()).astype(int)
    
    # Value length features (if text-based)
    if 'old_value' in features_df.columns:
        features_df['old_value_length'] = features_df['old_value'].astype(str).str.len()
        features_df['new_value_length'] = features_df['new_value'].astype(str).str.len()
    
    return features_df, label_encoders


def select_clustering_features(features_df, feature_set='basic'):
    """
    Select which features to use for clustering
    """
    if feature_set == 'basic':
        # Simple structural features
        feature_cols = [
            'user_type_encoded',
            'property_label_encoded',
            'datatype_encoded',
            'change_table_encoded',
            'action_encoded',
            'was_redirected',
            'has_old_value',
            'has_new_value',
            'day_of_week',
            'hour_of_day'
        ]
    
    elif feature_set == 'with_statistics':
        # Add your statistical features
        feature_cols = [
            'user_type_encoded',
            'property_label_encoded',
            'datatype_encoded',
            'change_table_encoded',
            'action_encoded',
            'was_redirected',
            'num_changes_in_revision',
            'time_since_entity_creation',
            'user_edit_count',
            'user_revert_rate',
            'num_references_before',
            'num_references_after',
            'day_of_week',
            'hour_of_day'
        ]
    
    elif feature_set == 'all':
        # Use all available numeric features
        feature_cols = features_df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Filter to only existing columns
    feature_cols = [col for col in feature_cols if col in features_df.columns]
    
    return features_df[feature_cols]


# ==================== CLUSTERING ====================

def perform_clustering(X, method='kmeans', n_clusters=10, **kwargs):
    """
    Perform clustering with different methods
    """
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    if method == 'kmeans':
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(X_scaled)
        
    elif method == 'dbscan':
        eps = kwargs.get('eps', 0.5)
        min_samples = kwargs.get('min_samples', 5)
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(X_scaled)
    
    return labels, X_scaled, scaler


def find_optimal_k(X_scaled, max_k=20):
    """
    Use elbow method to find optimal number of clusters
    """
    inertias = []
    silhouette_scores = []
    K = range(2, max_k + 1)
    
    for k in K:
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(X_scaled)
        inertias.append(kmeans.inertia_)
        
    # Plot elbow curve
    plt.figure(figsize=(10, 5))
    plt.plot(K, inertias, 'bx-')
    plt.xlabel('Number of clusters (k)')
    plt.ylabel('Inertia')
    plt.title('Elbow Method For Optimal k')
    plt.show()
    
    return K, inertias


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


def analyze_clusters(df, labels, original_features):
    """
    Analyze what characterizes each cluster
    """
    df_with_clusters = df.copy()
    df_with_clusters['cluster'] = labels
    
    print(f"Number of clusters found: {len(set(labels))}")
    print(f"Cluster sizes: {Counter(labels)}")
    print("\n" + "="*50 + "\n")
    
    # For each cluster, show most common values for key features
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:  # DBSCAN noise
            continue
            
        cluster_data = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
        print(f"CLUSTER {cluster_id} (n={len(cluster_data)})")
        print("-" * 50)
        
        # Show most common values for important categorical features
        important_cols = ['user_type', 'property_label', 'datatype', 'action', 'change_table']
        for col in important_cols:
            if col in cluster_data.columns:
                top_values = cluster_data[col].value_counts().head(3)
                print(f"\n{col}:")
                for val, count in top_values.items():
                    print(f"  {val}: {count} ({count/len(cluster_data)*100:.1f}%)")
        
        # Show statistics for numeric features
        numeric_cols = ['num_changes_in_revision', 'user_edit_count', 'time_since_entity_creation']
        numeric_cols = [col for col in numeric_cols if col in cluster_data.columns]
        if numeric_cols:
            print(f"\nNumeric features:")
            print(cluster_data[numeric_cols].describe().loc[['mean', '50%']])
        
        print("\n" + "="*50 + "\n")
    
    return df_with_clusters


# ==================== MAIN WORKFLOW ====================

def main():
    # 1. Load and prepare data
    print("Loading data...")
    df = pd.read_csv('your_changes.csv')  # Load your data
    
    # Sample if dataset is very large
    if len(df) > 50000:
        df_sample = df.sample(n=50000, random_state=42)
        print(f"Sampled {len(df_sample)} records for initial clustering")
    else:
        df_sample = df
    
    # 2. Feature engineering
    print("\nPreparing features...")
    features_df, label_encoders = prepare_features(df_sample)
    
    # 3. Select features for clustering
    print("\nSelecting features...")
    X = select_clustering_features(features_df, feature_set='basic')
    print(f"Using {X.shape[1]} features: {list(X.columns)}")
    
    # Handle missing values
    X = X.fillna(-1)  # or use median/mode depending on your data
    
    # 4. Find optimal number of clusters (optional)
    print("\nFinding optimal k...")
    labels_scaled, X_scaled, scaler = perform_clustering(X, method='kmeans', n_clusters=5)
    K, inertias = find_optimal_k(X_scaled, max_k=15)
    
    # 5. Perform clustering with chosen k
    optimal_k = 8  # Choose based on elbow plot
    print(f"\nClustering with k={optimal_k}...")
    labels, X_scaled, scaler = perform_clustering(X, method='kmeans', n_clusters=optimal_k)
    
    # 6. Visualize
    print("\nVisualizing clusters...")
    visualize_clusters(X_scaled, labels, method='pca')
    visualize_clusters(X_scaled, labels, method='tsne')
    
    # 7. Analyze clusters
    print("\nAnalyzing clusters...")
    df_with_clusters = analyze_clusters(features_df, labels, X.columns)
    
    # 8. Save results
    df_with_clusters.to_csv('changes_with_clusters.csv', index=False)
    print("\nResults saved to 'changes_with_clusters.csv'")
    
    # 9. Sample from each cluster for manual labeling
    print("\nSampling from each cluster for manual review...")
    samples_per_cluster = 10
    sample_rows = []
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:
            continue
        cluster_samples = df_with_clusters[df_with_clusters['cluster'] == cluster_id].sample(
            n=min(samples_per_cluster, len(df_with_clusters[df_with_clusters['cluster'] == cluster_id])),
            random_state=42
        )
        sample_rows.append(cluster_samples)
    
    manual_review_df = pd.concat(sample_rows)
    manual_review_df.to_csv('manual_review_samples.csv', index=False)
    print(f"Saved {len(manual_review_df)} samples for manual review")


if __name__ == "__main__":
    main()