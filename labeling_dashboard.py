# streamlit_app_offline.py
import streamlit as st
import pandas as pd
import os

# --------------------
# FILE PATHS
# --------------------
DATA_FILE = "gold_standard.csv"

# --------------------
# FUNCTIONS
# --------------------
def load_changes():
    """Load the subset of changes to label from CSV."""
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        return df
    else:
        st.error(f"Data file {DATA_FILE} not found!")
        return pd.DataFrame()

def save_labels(change, selected_labels):
    """Update labels in the CSV file."""
    if not selected_labels:
        st.warning("No labels selected!")
        return  # nothing selected

    try:
        # Load current data
        df = pd.read_csv(DATA_FILE)
        
        # Debug: Show what we're looking for
        st.write("DEBUG - Looking for:")
        st.write(f"revision_id: {change['revision_id']} (type: {type(change['revision_id'])})")
        st.write(f"property_id: {change['property_id']} (type: {type(change['property_id'])})")
        st.write(f"value_id: {change['value_id']} (type: {type(change['value_id'])})")
        st.write(f"change_target: {change['change_target']} (type: {type(change['change_target'])})")
        
        # Find the row to update - be more careful with type conversions
        mask = (
            (df["revision_id"].astype(str) == str(change["revision_id"])) &
            (df["property_id"].astype(str) == str(change["property_id"])) &
            (df["value_id"].astype(str) == str(change["value_id"])) &
            (df["change_target"].astype(str) == str(change["change_target"]))
        )
        
        # Debug: Show how many rows match
        st.write(f"DEBUG - Rows matching: {mask.sum()}")
        
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
st.set_page_config(page_title="Change Labeling Dashboard", layout="wide")
st.title("Wikidata Change Labeling Dashboard (Offline Mode)")
st.write("Label a predefined subset of changes (you can select multiple labels).")

# Load changes once
if "changes_df" not in st.session_state:
    st.session_state.changes_df = load_changes()
    st.session_state.index = 0

df = st.session_state.changes_df

if df.empty:
    st.error("No data loaded. Make sure gold_standard_data.csv exists in the same directory.")
    st.stop()

index = st.session_state.index

# Navigation at the top
col1, col2, col3 = st.columns([2, 3, 2])
with col1:
    if st.button("⬅️ Previous", use_container_width=True) and st.session_state.index > 0:
        st.session_state.index -= 1
        st.rerun()
with col2:
    rev_choice = st.selectbox("Jump to revision ID:", df["revision_id"].tolist(), label_visibility="collapsed")
    if st.button("Go", use_container_width=True):
        st.session_state.index = df.index[df["revision_id"] == rev_choice].tolist()[0]
        st.rerun()
with col3:
    if st.button("➡️ Next", use_container_width=True) and st.session_state.index < len(df) - 1:
        st.session_state.index += 1
        st.rerun()

st.markdown("---")

if index < len(df):
    change = df.iloc[index]

    st.subheader(f"Change {index + 1} of {len(df)} — Revision {change['revision_id']} - Entity ID {change['entity_id']}")
    st.markdown(
        f"**Property ID:** {change['property_id']}  \n"
        f"**Property Label:** {change['property_label']}  \n"
        f"**Value ID:** {change['value_id']}  \n"
        f"**Target:** {change['change_target']}"
    )
    
    # Show current label if exists
    if pd.notna(change.get("label")) and change.get("label"):
        st.info(f"**Current label(s):** {change['label']}")

    st.markdown("### Old Value")
    st.code(change["old_value"] if pd.notna(change["old_value"]) else "", language="text")
    if pd.notna(change["old_value"]) and 'Q' in str(change["old_value"]):
        st.markdown("### Old Value Label")
        st.code(change["old_value_label"] if pd.notna(change["old_value_label"]) else "", language="text")
    
    st.markdown("### New Value")
    st.code(change["new_value"] if pd.notna(change["new_value"]) else "", language="text")
    if pd.notna(change["new_value"]) and 'Q' in str(change["new_value"]):
        st.markdown("### New Value Label")
        st.code(change["new_value_label"] if pd.notna(change["new_value_label"]) else "", language="text")

    st.markdown("### Choose labels (you can select multiple):")
    labels = [
        "typo", "formatting", "refinement", "value specification", "unrefinement", "value generalization",
        "reversion", "reverted edit", "property replacement", 
        "rewording", "link fix", "language standardization", "value correction", "type specialization",
        "type unrefinement", "none"
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
    if st.button("💾 Save labels", use_container_width=True, type="primary"):
        save_labels(change, selected_labels)
        st.success(f"Saved labels: {', '.join(selected_labels)}")
        # Automatically move to next
        if st.session_state.index < len(df) - 1:
            st.session_state.index += 1
        st.rerun()

else:
    st.success("🎉 You've labeled all available changes!")

st.markdown("---")
st.caption(f"Working with offline file: {DATA_FILE}")