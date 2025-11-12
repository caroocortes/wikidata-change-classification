
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from collections import Counter
from sklearn.cluster import KMeans, DBSCAN
from kneed import KneeLocator

def perform_clustering(X, method='kmeans', n_clusters=10, random_state=42, n_init=3, max_iter=300, **kwargs):
    """
    Perform clustering with different methods
    X is already scaled
    """
    
    if method == 'kmeans':
        # random state guarantees that the results are reproducible
        model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=n_init, max_iter=max_iter, verbose=0)
        labels = model.fit_predict(X)
        
    elif method == 'dbscan':
        eps = kwargs.get('eps', 0.5)
        min_samples = kwargs.get('min_samples', 5)
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(X)
    
    return labels, X

def find_optimal_k(X, random_state=42, n_init=3, max_iter=300, min_k=3, max_k=20, tracker=None):
    """
    Use elbow method to get best K
    """
    
    inertias = []
    K = range(min_k, max_k + 1)
    
    print(f"Testing k from {min_k} to {max_k}...")
    for k in K:
        # K-means is a centroid-based clustering algorithm, where we calculate the distance between each data point and a centroid to assign it to a cluster. 
        # The goal is to identify the K number of groups in the dataset.
        # It is iterative and minimizes distances between the data points and the cluster centroid.
        # After assigning points to clusters, the centroids are recalculated as the mean of the assigned points, and the process repeats until convergence.

        print(f"k={k}...", end=' ')
        kmeans = KMeans(
            n_clusters=k, 
            random_state=random_state,
            n_init=n_init, 
            max_iter=max_iter,  
            verbose=0
        )
        # n_init states how many different sets of randomly chosen centroids the algorithm should use
        # For each different set of points, a comparision is made about how much distance did the clusters move
        kmeans.fit(X)
        inertias.append(kmeans.inertia_)
        
    kl = KneeLocator(
        K, 
        inertias, 
        curve='convex', 
        direction='decreasing'
    )
    elbow_k = kl.elbow
    
    # Plot both metrics
    fig, ax1 = plt.subplots(1, 1, figsize=(8, 5))
    
    # Elbow curve
    ax1.plot(K, inertias, 'bx-', linewidth=2, markersize=8)
    ax1.set_xlabel('Number of clusters (k)', fontsize=12)
    ax1.set_ylabel('Inertia', fontsize=12)
    ax1.set_title('Elbow Method For Optimal k', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if  tracker is not None:
        plt.savefig(tracker.experiment_dir / 'elbow_analysis.png', dpi=300, bbox_inches='tight')
        print(f"\nSaved plot to {tracker.experiment_dir / 'elbow_analysis.png'}")
    
    plt.show()
    
    print("\n" + "="*50)
    print(f"BEST K (by kneed): {elbow_k}")
    print("="*50)
    
    # Save metrics
    metrics_df = pd.DataFrame({
        'k': list(K),
        'inertia': inertias
    })
    metrics_df.to_csv(tracker.experiment_dir / 'clustering_metrics.csv', index=False)
    print(f"Saved metrics to {tracker.experiment_dir / 'clustering_metrics.csv'}")
    
    return elbow_k


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


def analyze_clusters(df, labels, tracker=None, output_file_examples='cluster_examples.csv', output_file_analysis='cluster_analysis.csv', n_examples=20, datatype='string'):
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
    
    for cluster_id in sorted(set(labels)):
        if cluster_id == -1:
            continue
        
        cluster_data = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
        cluster_output = f"\n{'='*80}\n"
        cluster_output += f"CLUSTER {cluster_id} (n={len(cluster_data):,}, {len(cluster_data)/len(df)*100:.1f}%)\n"
        cluster_output += f"{'='*80}\n\n"
        
        # User type distribution
        cluster_output += "USER TYPE:\n"
        for user_type, count in cluster_data['user_type'].value_counts().items():
            cluster_output += f"  {user_type}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"

        # Top properties
        cluster_output += "\nTOP 10 PROPERTIES:\n"
        top_props = cluster_data['property_id'].value_counts().head(10)
        for prop, count in top_props.items():
            if 'property_label' in cluster_data.columns:
                label = cluster_data[cluster_data['property_id'] == prop]['property_label'].iloc[0]
                cluster_output += f"  {prop} ({label}): {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
            else:
                cluster_output += f"  {prop}: {count:,} ({count/len(cluster_data)*100:.1f}%)\n"
        
        # Change magnitude 
        if 'levenshtein_distance' in cluster_data.columns:
            actual_mag = cluster_data['levenshtein_distance']
            if len(actual_mag) > 0:
                cluster_output += f"\nLEVENSHTEIN DISTANCE:\n"
                cluster_output += f"  Mean: {actual_mag.mean():.2f}\n"
                cluster_output += f"  Range: [{actual_mag.min():.2f}-{actual_mag.max():.2f}]\n"
        
        # print(cluster_output)
        output.write(cluster_output + "\n")

    
    # Save to tracker if provided
    if tracker:
        tracker.save_text(output.getvalue(), output_file_analysis)

    # Get examples
    output_rows = []
    
    for cluster_id in sorted(set(labels)):
        cluster = df_with_clusters[df_with_clusters['cluster'] == cluster_id]
        
        if len(cluster) == 0:
            continue
        
        # Get examples
        example_cols = ['revision_id', 'entity_id', 'entity_label', 'property_id', 'property_label', 
                       'old_value', 'new_value', 'old_value_label', 'new_value_label', 
                       'user_type', 'datatype', 'change_target', 'value_id', 'action', 'target', 'timestamp']
        example_cols = [col for col in example_cols if col in cluster.columns]
        
        # Sample examples
        examples = cluster[example_cols].sample(min(n_examples, len(cluster)), random_state=42)
        
        for idx, row in examples.iterrows():
            output_row = {
                'cluster_id': cluster_id,
                'cluster_size': len(cluster)
            }
            
            # Add example data
            for col in example_cols:
                output_row[col] = row[col]
            
            output_rows.append(output_row)
    
    # Convert to DataFrame and save
    results_df = pd.DataFrame(output_rows)
    results_df.to_csv(tracker.experiment_dir / output_file_examples, index=False)
    print(f"\n Saved {len(results_df)} examples to {tracker.experiment_dir /output_file_examples}")

    return results_df

