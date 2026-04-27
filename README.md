# Change Classification in Wikidata

This repository contains code and artifacts for classifying Wikidata value changes across multiple datatypes (e.g., `quantity`, `time`, `text`, `entity`, and `globecoordinate`).  
It includes LLM baseline classification, ML-based classification, and analysis scripts.

Change Type classification is a 3-step process, where the first 2 steps are performed during change extraction (performed using [WiDiff](https://anonymous.4open.science/r/WiDiff-DC11/README.md)).

![classification framework architecture](change_classification_framework.svg)

This tool assumes a database populated by [WiDiff](https://anonymous.4open.science/r/WiDiff-DC11/README.md) exists, and that change extraction was performed with *feature_extraction: true* and *re_interpretation: true* (see `set_up.yml` of **WiDiff**).

---

## Repository Structure
```text
wikidata-change-analysis/
├── main.py                         # Main entrypoint for train/evaluate/classify
├── set_up.yml                      # Configuration
├── requirements.txt                # Python dependencies
├── notebook.ipynb                  # Ad-hoc analysis notebook
│
├── src/
│   ├── pipeline.py                 # Orchestrates classifier init, train, eval, run
│   │
│   ├── classifiers/
│   │   ├── base_classifier.py      # Shared classifier interface
│   │   ├── ml/
│   │   │   ├── ml_classifier.py    # Train & Evaluate ML classifier
│   │   │   ├── ml_features.py      # Feature extraction
│   │   │   ├── features/           # Feature columns, scalers, training dataset features
│   │   │   └── training_info/      # Saved model training artifacts
│   │   └── llm/
│   │       └── llm_classifier.py   # implements calls for LLM classification
│   │
│   ├── config/
│   │   ├── db_config.json              # DB params for connection
│   │   ├── ml_classifier_config.json   # Configuration params for ML classification
│   │   ├── llm_classifier_config.json  # Configuration params for LLM classification
│   │   └── models_config.json
│   │
│   ├── sql_runner/
│   │   └── sql_runner.py           # SQL execution layer
│   │
│   ├── utils/
│   │   ├── const.py
│   │   └── utils.py
│   │
│   ├── analysis/
│   │   ├── scripts/
│   │   │   └── classification_analysis.py # analysis scripts
│   │   ├── sql/                    # Analysis SQL queries
│   │   └── results/                # Generated analysis outputs (CSV)
│   │
│   └── results/
│       ├── classification/         # Classification outputs of LLM
│       └── training/               # Model selection/training summaries
│
├── transitive_closures/            # Cached transitive closure data (for feature extraction)
├── gold_standard/                  # Gold-standard dataset + Labeling rules
└── logs/                           # Runtime logs
```

--- 

## Reproduce results

We provide the trained models and features in [Wikidata Change Classification Trained Models and Features](https://doi.org/10.5281/zenodo.19788996).

To re-use this resources, unzip files and put in the following folders:
- features.zip -> src/classifiers/ml/features/
- training_info_all_classifiers.zip -> src/classifiers/ml/training_info/
- trained_model.zip -> src/results/training/

Follow the steps below for classification or traininig.

---

## Classification

**Note:** The classification uses the training_info.pkl stored in *src/results/training/*. By default, this folder stores the best model (the one with highest F1 across all tasks). To use another model, copy its *training_info.pkl* from *src/classifiers/ml/training_info/* to *src/results/training/* and rename with *best_model_training_info.pkl*.

Example: If you want to use random forest, then *src/classifiers/ml/training_info/training_info_random_forest.pkl* needs to be moved to *src/results/training/* and renamed accordingly.

### ML classification
1. Set database parameters in a .json file and set the path to this config file in `set_up.yml` under *config* - *database_config_path*

````bash
{
    "user": "username",
    "password": "password",
    "dbname": "database_name",
    "port": 5432,
    "host": "localhost"
}
````

2. Set *classifier_type* to *ml* in `set_up.yml` and the respective step (train, evaluate, classify) to be ran in *classification_ml*. For the classify step, set `table_prefix` (can be one of: '_less', '_sa', '_ao', '' - See entity filters in change extraction tool) and `max_batches` (maximum number of batches of changes to classify) accordingly.
3. Run `python3 main.py`.

*Note:* For classification of all changes in the DB (step *classification_ml - classify: true* in `set_up.yml`), change extraction should have been performed with *feature_extraction: true*, and the script `compute_remaining_features.py` should have been ran. Refer to [WiDiff](https://anonymous.4open.science/r/WiDiff-DC11/README.md) for this last step (Section *Compute remaining features* in README).

#### Training

For training, the transitive closure cache must be created beforehand. Refer to [WiDiff](https://anonymous.4open.science/r/WiDiff-DC11/README.md) for transitive closure extraction and cache creation (Section *Transitive closure cachce creation* in README). The `transitive_closure_cache.pkl` file should be inside the directory `/transitive_closures`. *Note:* The .csv files for the cache creation are provided in [WiDiff: Wikidata Entity Labels, Descriptions and Alias, Types (P31 and P279), and Transitive Closures (October 2025)](https://doi.org/10.5281/zenodo.19771721).

**Configuration**

Training is performed doing 5-fold cross validation. The number of folds can be changed in *config/ml_classifier_config.json*

Additionally, since we want to guarantee that every change has a label assigned and multi-label classifiers return probabilities for each class, we assign all labels to a change where prob >= 0.5, If no probability reaches this threshold, we take the one with the maximum probability. This threshold can be modified in *config/ml_classifier_config.json*.

Finally, we use *random_state = 42* so results are reproducible (also set in *config/ml_classifier_config.json*).

**Output**

Training outputs *training_info_<model_name>.pkl* files with the following structure:

`````bash
    {
        "datatype": {
            'results_folds': [], # results per fold
            'micro_averages': {
                'datatype': {
                    'precision': float,
                    'recall': float,
                    'accuracy': float,
                    'f1': float
                }
            } 
    }

    # results per fold:
    {
        'classifier': string, # kn, xgboost, random_forest, gradient_boosting
        'fold': int, # 0-4
        'metrics_results': { # macro average
            'label': { 
                'precision': float,
                'recall': float,
                'accuracy': float,
                'f1': float
            }
        },
        'model': clf, # if the base_model doesn't support MultiOutput classification, we send it through MultiOutputClassifier. If not base_model == model
        'base_model': model, # base model (GradientBoosting, RandomForest, XGBoost, KNN)
        'features': feature_cols, 
        'multi_label_binarizer': label_binarizer,
    }
`````

**Note:** The `notebook.ipynb` provides code for plotting comparison between different classifiers (Traditional and LLM) from their *training_info.pkl* 

---

### LLM baseline
1. Configure LLM in `config/llm_classifier_config.json`. To use Qwen 3.5 (FP8 quantized), run the following command in the background:
```bash
vllm serve Qwen/Qwen3.5-35B-A3B-FP8 \
    --port 8001 \
    --tensor-parallel-size 2 \
    --max-model-len 4096 \
    --reasoning-parser qwen3 \
    --language-model-only
```
and set the corresponding `base_url` in the configuration file (`src/config/llm_classifier.json`). 
2. Set *classifier_type* to *llm* in `set_up.yml`. 
3. Run `python3 main.py`. This classifies changes on the labeled dataset (`gold_standard/gold_standard.csv`)

---

## Analysis
The script `src/analysis/classification_analisys.py` generates plots for the classified changes. 
Each function corresponds to a specific analysis and can be run independently by toggling the corresponding `execute` flag in `setup.yml`. When `reload_data=True`, the function executes the underlying SQL query and caches the results as a CSV; subsequent runs load from the cache instead of re-querying the database.

Available analysis:

| Function | Description |
|---|---|
| `distribution_change_types` | Distribution of change types overall, per datatype, and per user type |
| `change_types_overtime` | Evolution of change types over time, overall and per datatype |
| `soft_deletion_vs_hard_deletion` | Comparison of soft and hard deletion counts per entity |
| `reverted_edits` | Reverted edits over time broken down by user type |
| `prop_reverts_overtime` | Average time until reversion per property |

Output figures are saved to `results/classification_analysis/figures/`.

To run the analysis, execute from root:
````bash
python3 -m src.analysis.scripts.classification_analysis
````