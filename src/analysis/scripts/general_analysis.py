import pandas as pd
import matplotlib.pyplot as plt
import json
import yaml
import os

from src.database.sql_runner import SQLRunner
from src.utils.const import RESULTS_DIR, YAML_SETUP_PATH, SQL_SCRIPT_DIR

RESULTS_DIR = f'{RESULTS_DIR}/general_analysis'
os.makedirs(RESULTS_DIR, exist_ok=True)

os.makedirs(f'{RESULTS_DIR}/figures', exist_ok=True)

def stats_sa_ao(db_config, reload_data):

    query_name = 'stats_sa_ao'
    suffixes = ['_ao', '_sa']
    if reload_data:
        sql_runner = SQLRunner(db_config)
        for suffix in suffixes:
            
            with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
                sql_query = f.read()
                sql_query = sql_query.replace('<suffix>', suffix)
            
            df = sql_runner.query_to_df(sql_query)
            print(df.style.format({"count": "{:,.0f}"}).to_string())
            df.to_csv(f'{RESULTS_DIR}/stats{suffix}.csv', index=False)
    else:

        for suffix in suffixes:
            df = pd.read_csv(f'{RESULTS_DIR}/stats{suffix}.csv')
            print(df.style.format({"count": "{:,.0f}"}).to_string())

def stats_used_tables(db_config, reload_data):

    query_name = 'stats_sa_ao' # uses the same query
    suffix = ''
    if reload_data:
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
            sql_query = sql_query.replace('<suffix>', suffix)
        
        df = sql_runner.query_to_df(sql_query)
        print(df.style.format({"count": "{:,.0f}"}).to_string())
        df.to_csv(f'{RESULTS_DIR}/stats_used_tables.csv', index=False)
    else:
        df = pd.read_csv(f'{RESULTS_DIR}/stats_used_tables.csv')
        print(df.style.format({"count": "{:,.0f}"}).to_string())


def table_stats(db_config, reload_data):
    """
        Number of rows of the main tables in the database (value_change, qualifier, reference, revision).
    """

    sql_runner = SQLRunner(db_config)
    
    # suffixes = ['', '_less', '_sa', '_ao']
    suffixes = ['_sa', '_ao']
    tables = ['revision', 'value_change', 'reference_change', 'qualifier_change']
    query = """
        SELECT 'number of {table_name}' as metric, count(*)
        from {table_name}{suffix}
    """

    if reload_data:
        for suffix in suffixes:
            print(f'Table suffix: {suffix}')
            for table_name in tables:
                print(f'Processing table: {table_name}{suffix}')
                formatted_query = query.format(table_name=table_name, suffix=suffix)
                df_table = sql_runner.query_to_df(formatted_query)
                print(df_table.to_string(index=False))
                df_table.to_csv(f'{RESULTS_DIR}/general_stats{suffix}.csv', index=False, mode='a', header=not os.path.exists(f'{RESULTS_DIR}/general_stats{suffix}.csv'))
    else:
        for suffix in suffixes:
            print(f'Table suffix: {suffix}')
            df = pd.read_csv(f'{RESULTS_DIR}/general_stats{suffix}.csv')
            print(df.to_string(index=False))


def stats_feature_tables(db_config, reload_data):
    query_name = 'stats_feature_tables'
    if reload_data:
        sql_runner = SQLRunner(db_config)

        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
            
        df = sql_runner.query_to_df(sql_query)
        print(df.style.format({"count": "{:,.0f}"}).to_string())
        df.to_csv(f'{RESULTS_DIR}/stats_features_tables.csv', index=False)
    else:
        df = pd.read_csv(f'{RESULTS_DIR}/stats_features_tables.csv')
        print(df.style.format({"count": "{:,.0f}"}).to_string())


def entity_stats(db_config, reload_data, filter_big_entities):
    """
        Entity stats analysis: distributions of number of revisions, creates, deletes, updates per entity.
    """

    if not db_config:
        print("No DB config provided.")
        return 

    if reload_data:
        sql_runner = SQLRunner(db_config=db_config)
        
        df_final = pd.DataFrame()
        batch_size = 100000
        offset = 0
        while True:
            query = """
                SELECT * 
                FROM entity_stats
                OFFSET {offset} LIMIT {limit}
            """.format(offset=offset, limit=batch_size)

            offset += batch_size
            df = sql_runner.query_to_df(query)
            print(f'Fetched {len(df)} records from offset {offset - batch_size}')
            if len(df) == 0:
                break
                
            df_final = pd.concat([df_final, df], ignore_index=True)

        df_final.to_csv(f'{RESULTS_DIR}/entity_stats.csv', index=False)
    else:
        df_final = pd.read_csv(f'{RESULTS_DIR}/entity_stats.csv')

    if filter_big_entities:
        # -- earth > 20.000
        # -- sandbox > 60.000
        df_filtered = df_final[df_final['num_revisions'] < 60000]
        print(f'Filtered out big entities: {len(df_final) - len(df_filtered)}')
    else:
        df_filtered = df_final

    fig, axes = plt.subplots(4, 2, figsize=(14, 10))
    font_size = 3

    # histogram of revisions per entity
    bars = axes[0, 0].hist(df_filtered['num_revisions'], bins=50, edgecolor='black', alpha=0.7) # returns values, bins, bars
    axes[0, 0].set_xlabel('Number of Revisions')
    axes[0, 0].set_ylabel('Number of Entities')
    axes[0, 0].set_title('Distribution of Revisions per Entity')
    axes[0, 0].bar_label(bars[2], fontsize=5, color='black', padding=3)
    axes[0, 0].set_yscale('log') 

    # histogram of creates
    bars = axes[0, 1].hist(df_filtered['num_value_change_creates'], bins=50, edgecolor='black', alpha=0.7, color='green')
    axes[0, 1].set_xlabel('Number of Creates')
    axes[0, 1].set_ylabel('Number of Entities')
    axes[0, 1].set_title('Distribution of Creates per Entity')
    axes[0, 1].bar_label(bars[2], fontsize=font_size, color='black', padding=3)
    axes[0, 1].set_yscale('log') 

    # histogram of deletes
    bars = axes[1, 0].hist(df_filtered['num_value_change_deletes'], bins=50, edgecolor='black', alpha=0.7, color='red')
    axes[1, 0].set_xlabel('Number of Deletes')
    axes[1, 0].set_ylabel('Number of Entities')
    axes[1, 0].set_title('Distribution of Deletes per Entity')
    axes[1, 0].bar_label(bars[2], fontsize=font_size, color='black', padding=3)
    axes[1, 0].set_yscale('log') 

    # histogram of updates
    bars = axes[1, 1].hist(df_filtered['num_value_change_updates'], bins=50, edgecolor='black', alpha=0.7, color='orange')
    axes[1, 1].set_xlabel('Number of Updates')
    axes[1, 1].set_ylabel('Number of Entities')
    axes[1, 1].set_title('Distribution of Updates per Entity')
    axes[1, 1].bar_label(bars[2], fontsize=font_size, color='black', padding=3)
    axes[1, 1].set_yscale('log') 

    plt.tight_layout()
    if filter_big_entities:
        img_file_name = f'{RESULTS_DIR}/figures/entity_stats_distributions.png'
    else:
        img_file_name = f'{RESULTS_DIR}/figures/entity_stats_distributions_no_filter.png'
    plt.savefig(img_file_name, dpi=300)
    plt.show()


if __name__ == "__main__":

    with open(YAML_SETUP_PATH, 'r') as f:
        set_up = yaml.safe_load(f)

    with open(set_up['database_config_path'], 'r') as f:
        db_config = json.load(f)

    # reload_data = set_up['analysis']['general']['db_tables']['reload_data']
    # table_stats(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['general']['stats_sa_ao']['reload_data']
    # stats_sa_ao(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['general']['stats_used_tables']['reload_data']
    # stats_used_tables(db_config['db_params'], reload_data)




    # reload_data = set_up['analysis']['general']['entity_stats']['reload_data']
    # filter_big_entities = set_up['analysis']['general']['entity_stats']['filter_big_entities']
    # entity_stats(db_config['db_params'], reload_data, filter_big_entities)

    # reload_data = set_up['analysis']['general']['stats_feature_tables']['reload_data']
    # stats_feature_tables(db_config['db_params'], reload_data)

    created_entities_over_time(db_config['db_params'], set_up['analysis']['general']['created_entities_overtime']['reload_data'])