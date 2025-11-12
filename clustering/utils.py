import matplotlib.pyplot as plt

def analyze_feature_distributions(X):

    for col in X.columns:
        print(f"\n{col} statistics:")
        print(X[col].describe())
        print(f"Min: {X[col].min()}, Max: {X[col].max()}")
        
        # Plot histogram
        plt.figure(figsize=(10, 4))
        plt.subplot(1, 2, 1)
        plt.hist(X[col].dropna(), bins=50)
        plt.title(f'{col} - Original')
        plt.xlabel('Value')
        
        # Plot boxplot to see outliers
        plt.subplot(1, 2, 2)
        plt.boxplot(X[col].dropna())
        plt.title(f'{col} - Boxplot')
        plt.tight_layout()
        plt.show()