# streamlit_app_clustering.py
import streamlit as st
import pandas as pd
import os

# --------------------
# FILE PATHS
# --------------------
DATA_FILE = "cluster_examples_string.csv"  # or whatever your clustering output file is

# --------------------
# FUNCTIONS
# --------------------
def load_changes():
    """Load the clustering examples to label from CSV."""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # Add label column if it doesn't exist
        if 'label' not in df.columns:
            df['label'] = ""
        return df
    else:
        st.error(f"Data file {DATA_FILE} not found!")
        return pd.DataFrame()

def save_labels(change, selected_labels):
    """Update labels in the CSV file."""
    if not selected_labels:
        st.warning("No labels selected!")
        return

    try:
        # Load current data
        df = pd.read_csv(DATA_FILE)
        
        # Find the row to update using index or unique identifiers
        # Adjust these fields based on what's in your clustering output
        mask = (
            (df["revision_id"].astype(str) == str(change["revision_id"])) &
            (df["property_id"].astype(str) == str(change["property_id"])) &
            (df["entity_id"].astype(str) == str(change["entity_id"]))
        )
        
        if mask.sum() == 0:
            st.error("No matching row found in CSV!")
            return
        
        # Update label (join multiple labels with comma)
        df.loc[mask, "label"] = ", ".join(selected_labels)
        
        # Save back to CSV
        df.to_csv(DATA_FILE, index=False)
        
        # Update session state
        st.session_state.changes_df = df
        
        st.success(f"Successfully saved: {', '.join(selected_labels)}")
        
    except Exception as e:
        st.error(f"Error saving labels: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

# --------------------
# STREAMLIT UI
# --------------------
st.set_page_config(page_title="Clustering Examples Labeling", layout="wide")
st.title("Clustering Examples Labeling Dashboard")
st.write("Label changes from clustering results to validate cluster quality.")

# Load changes once
if "changes_df" not in st.session_state:
    st.session_state.changes_df = load_changes()
    st.session_state.index = 0
    st.session_state.filter_cluster = None

df = st.session_state.changes_df

if df.empty:
    st.error(f"No data loaded. Make sure {DATA_FILE} exists in the same directory.")
    st.stop()

# Sidebar for filtering by cluster
st.sidebar.header("Filters")
if 'cluster' in df.columns:
    all_clusters = ['All'] + sorted(df['cluster'].unique().tolist())
    selected_cluster = st.sidebar.selectbox("Filter by Cluster:", all_clusters)
    
    if selected_cluster != 'All':
        df = df[df['cluster'] == selected_cluster].reset_index(drop=True)
        st.sidebar.info(f"Showing {len(df)} changes from cluster {selected_cluster}")
    else:
        st.sidebar.info(f"Showing all {len(df)} changes")

# Show cluster statistics if available
if 'cluster' in df.columns:
    st.sidebar.markdown("---")
    st.sidebar.subheader("Cluster Statistics")
    cluster_counts = st.session_state.changes_df['cluster'].value_counts().sort_index()
    st.sidebar.dataframe(cluster_counts, use_container_width=True)

index = st.session_state.index

# Navigation at the top
col1, col2, col3 = st.columns([2, 3, 2])
with col1:
    if st.button("⬅️ Previous", use_container_width=True) and st.session_state.index > 0:
        st.session_state.index -= 1
        st.rerun()
with col2:
    st.write(f"Change {index + 1} of {len(df)}")
with col3:
    if st.button("➡️ Next", use_container_width=True) and st.session_state.index < len(df) - 1:
        st.session_state.index += 1
        st.rerun()

st.markdown("---")

if index < len(df):
    change = df.iloc[index]

    # Display cluster information if available
    if 'cluster' in change:
        st.subheader(f"Cluster {change['cluster_id']} — Revision {change['revision_id']} - Entity {change['entity_id']}")
    else:
        st.subheader(f"Revision {change['revision_id']} - Entity {change['entity_id']}")
    
    # Show metadata
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            f"**Cluster:** {change['cluster_id']}  \n"
            f"**Property Label:** {change['property_label']}  \n"
            f"**Entity Label:** {change['entity_label']}  \n"
            f"**Datatype:** {change.get('datatype', 'N/A')}  \n"
            f"**Change target:** {change.get('change_target', 'N/A')}  \n"
        )
    with col2:
        st.markdown(
            f"**User Type:** {change.get('user_type', 'N/A')}  \n"
            f"**Action:** {change.get('action', 'N/A')}  \n"
            f"**Timestamp:** {change.get('timestamp', 'N/A')}  \n"
        )
    with col3:
        st.markdown(
            f"**Num changes per revision:** {change.get('num_changes_in_revision', 'N/A')}  \n"
            f"**Entity age in days:** {change.get('entity_age_days', 'N/A')}  \n"
        )
    
    # Show current label if exists
    if pd.notna(change.get("label")) and change.get("label"):
        st.info(f"**Current label(s):** {change['label']}")

    # Display values
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Old Value")
        st.code(change["old_value"] if pd.notna(change["old_value"]) else "", language="text")
        if pd.notna(change.get("old_value_label")):
            st.caption(f"Label: {change['old_value_label']}")
    
    with col2:
        st.markdown("### New Value")
        st.code(change["new_value"] if pd.notna(change["new_value"]) else "", language="text")
        if pd.notna(change.get("new_value_label")):
            st.caption(f"Label: {change['new_value_label']}")

    # Show additional features if available
    if 'levenshtein_distance' in change:
        st.markdown("### Edit Metrics")
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
        with metrics_col1:
            st.metric("Levenshtein Distance", f"{change.get('levenshtein_distance', 'N/A')}")
        with metrics_col2:
            st.metric("Levenshtein Ratio", f"{change.get('levenshtein_ratio', 'N/A'):.2f}" if pd.notna(change.get('levenshtein_ratio')) else "N/A")
        with metrics_col3:
            st.metric("Length Ratio", f"{change.get('length_ratio', 'N/A'):.2f}" if pd.notna(change.get('length_ratio')) else "N/A")

    st.markdown("### Choose labels (you can select multiple):")
    labels = [
        "typo", "formatting", "refinement", "value specification", "unrefinement", "value generalization",
        "reversion", "reverted edit", "property replacement", 
        "rewording", "link fix", "language standardization", "value correction", "type specialization",
        "type unrefinement", "none", "unclear", "sign change", "precision change"
    ]

    # Pre-select existing labels
    existing_labels = []
    if pd.notna(change.get("label")) and change.get("label"):
        existing_labels = [l.strip() for l in str(change["label"]).split(",")]

    # Create checkboxes in 3 columns
    selected_labels = []
    num_cols = 3
    cols = st.columns(num_cols)
    
    for i, label in enumerate(labels):
        col_idx = i % num_cols
        with cols[col_idx]:
            is_checked = label in existing_labels
            if st.checkbox(label.capitalize(), key=f"checkbox_{label}", value=is_checked):
                selected_labels.append(label)

    # Save button
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 Save labels", use_container_width=True, type="primary"):
            save_labels(change, selected_labels)
            # Automatically move to next
            if st.session_state.index < len(df) - 1:
                st.session_state.index += 1
            st.rerun()
    
    with col2:
        if st.button("⏭️ Skip (no label)", use_container_width=True):
            if st.session_state.index < len(df) - 1:
                st.session_state.index += 1
            st.rerun()

else:
    st.success("🎉 You've labeled all available changes in this view!")
    if st.button("🔄 Reset to beginning"):
        st.session_state.index = 0
        st.rerun()

st.markdown("---")
st.caption(f"Working with file: {DATA_FILE}")

# Show progress
labeled_count = df['label'].notna().sum() if 'label' in df.columns else 0
st.sidebar.markdown("---")
st.sidebar.metric("Labeled Changes", f"{labeled_count} / {len(df)}")
progress = labeled_count / len(df) if len(df) > 0 else 0
st.sidebar.progress(progress)