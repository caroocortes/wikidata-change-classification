

def text_features():
    """
    length_diff_abs
    case_differs
    space_differs
    punct_differs
    hyph_dash_differs
    brackets_differs
    token_overlap
    old_in_new (containment)
    new_in_old (containment)
    levenshtein_distance (maybe needs to be a ratio to compensate when strings are long)
    edit_distance_ratio
    "semantic_similarity (cosine similarity between embeddings)
    string embedding: property_label - old_value - new_value
    entity embedding: entity_label - property_label - old_value - new_value"

    embedding of the latest description of the entity 
    embedding of entity typeS (all of them)

    for changes between entities, need the description of the entities that are changing
    """

    pass
