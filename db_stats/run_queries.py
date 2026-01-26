import subprocess
from dotenv import load_dotenv
import json
import time

load_dotenv()

SCRIPT_DIR = 'scripts'

# Configurations for different queries
with open('scripts_config.json') as f:
    config = json.load(f)

queries = [
    config['stats_rest'],
    # config['stats_scholarly_articles'],
    # config['materialized_view_index_creation'],
]

with open("pipeline.log", "a") as log:
    
    for q in queries:
        try:
            start_time = time.time()
            cmd = [
                "psql",
                "-d", "wikidata_changes",
                "-e",
                "-a",
                *[x for kv in q["params"].items() for x in ("-v", f"{kv[0]}={kv[1]}")],
                "-f", SCRIPT_DIR + "/" + q['sql_file']
            ]

            subprocess.run(cmd, check=True)
            end_time = time.time()
            elapsed_time = end_time - start_time
            log.write(f"Successfully executed query from {q['sql_file']} with params {q['params']}. Took {elapsed_time} seconds\n")

        except subprocess.CalledProcessError as e:
            print(f"An error occurred while executing the query from {q['sql_file']}: {e}")