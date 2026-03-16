import sys
import pandas as pd
import matplotlib.pyplot as plt
import json
import yaml
import os
import numpy as np
from matplotlib.patches import Patch
import matplotlib as mpl
import textwrap

from src.database.sql_runner import SQLRunner
from src.utils.const import RESULTS_DIR, YAML_SETUP_PATH, SQL_SCRIPT_DIR

RESULTS_DIR = f'{RESULTS_DIR}/classification_analysis'
os.makedirs(RESULTS_DIR, exist_ok=True)

RESULTS_DIR_FIGURES = f'{RESULTS_DIR}/figures'
os.makedirs(RESULTS_DIR_FIGURES, exist_ok=True)


def soft_deletion_vs_shard_deletion(db_config, reload_data):
    if reload_data:

        sql_runner = SQLRunner(db_config)

        sql_query = """
        with hard_deletions as (
            select entity_id, count(*) as hard_deletion_count
            from value_change
            where action = 'DELETE' and is_reverted = 0 and reversion = 0
            group by entity_id
        ),
        soft_deletions_qualifier as (
            select entity_id, count(*) as soft_deletion_count
            from qualifier_change
            where label = 'soft_deletion'
            group by entity_id
        ),
        soft_deletions_value_change as (
            select entity_id, count(*) as soft_deletion_count
            from value_change
            where label = 'soft_deletion' and is_reverted = 0 and reversion = 0
            group by entity_id
        )
        select hd.entity_id, COALESCE(sdq.soft_deletion_count, 0) + COALESCE(sdvc.soft_deletion_count, 0) as soft_deletions, hd.hard_deletion_count
        from hard_deletions hd
        left join 
        soft_deletions_qualifier sdq on hd.entity_id = sdq.entity_id
        left join
        soft_deletions_value_change sdvc on hd.entity_id = sdvc.entity_id;
        """

        df = sql_runner.query_to_df(sql_query)

        df.to_csv(f'{RESULTS_DIR}/soft_hard_deletion.csv', index=False)
    else:
        df = pd.read_csv(f'{RESULTS_DIR}/soft_hard_deletion.csv')

    df['soft_deletions'] = pd.to_numeric(df['soft_deletions'].fillna(0))
    df['hard_deletion_count'] = pd.to_numeric(df['hard_deletion_count'].fillna(0))
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 10))
    font_size = 5

    bars = axes[0].hist(df['soft_deletions'], bins=50, edgecolor='black', alpha=0.7)
    axes[0].set_xlabel('Number of Soft Deletions', fontsize=12)
    axes[0].set_ylabel('Number of Entities', fontsize=12)
    axes[0].set_title('Soft Deletions per Entity', fontsize=14, fontweight='bold')
    axes[0].bar_label(bars[2], fontsize=font_size, color='black', padding=3)
    axes[0].set_yscale('log') 

    bars = axes[1].hist(df['hard_deletion_count'], bins=50, edgecolor='black', alpha=0.7)
    axes[1].set_xlabel('Number of Hard Deletions', fontsize=12)
    axes[1].set_ylabel('Number of Entities', fontsize=12)
    axes[1].set_title('Hard Deletions per Entity', fontsize=14, fontweight='bold')
    axes[1].bar_label(bars[2], fontsize=font_size, color='black', padding=3)
    axes[1].set_yscale('log') 
    
    plt.savefig(f'{RESULTS_DIR}/figures/soft_vs_hard_deletions.png', dpi=300, bbox_inches='tight')
    plt.show()

def distribution_change_types(db_config, reload_data):
    print('Calculating distribution of change types')

    query_name = 'dist_change_types'
    if reload_data:
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM change_type_distribution;')
        df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)

        df_ut = sql_runner.query_to_df('SELECT * FROM change_type_distribution_per_user_type;')
        df_ut.to_csv(f'{RESULTS_DIR}/{query_name}_per_user_type.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/{query_name}.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/{query_name}.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT * FROM change_type_distribution;')
            if len(df) == 0:
                print(f'No results found for {query_name}. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)
            del sql_runner

        if os.path.exists(f'{RESULTS_DIR}/{query_name}_per_user_type.csv'):
            df_ut = pd.read_csv(f'{RESULTS_DIR}/{query_name}_per_user_type.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df_ut = sql_runner.query_to_df('SELECT * FROM change_type_distribution_per_user_type;')
            if len(df_ut) == 0:
                print(f'No results found for {query_name}_per_user_type. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df_ut.to_csv(f'{RESULTS_DIR}/{query_name}_per_user_type.csv', index=False)
            del sql_runner
            
    df['total'] = pd.to_numeric(df['total'])
    df['count_reverted'] = pd.to_numeric(df['count_reverted'])
    df['count_non_reverted'] = pd.to_numeric(df['count_non_reverted'])

    df_grouped = df.groupby('label').agg({
        'count_reverted': 'sum',
        'count_non_reverted': 'sum',
        'total': 'sum'
    }).reset_index()

    df_grouped['reverted_percentage'] = (df_grouped['count_reverted'] / df_grouped['total']) * 100

    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(df_grouped['label']))
    width = 0.35
    bars1 = ax.bar([i - width/2 for i in x], df_grouped['count_reverted'], width, color='tomato', edgecolor='black', label='Reverted')
    bars2 = ax.bar([i + width/2 for i in x], df_grouped['count_non_reverted'], width, color='steelblue', edgecolor='black', label='Non-Reverted')
    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(df_grouped['label'], rotation=45, ha='right')
    ax.set_xlabel('Change Type', fontsize=12)
    ax.set_ylabel('Number of Changes (log scale)', fontsize=12)
    ax.set_title('Distribution of Reverted vs Non-Reverted Changes by Type (All Classes)', fontsize=14, fontweight='bold')
    ax.bar_label(bars1, labels=[f'{p:.1f}%' for p in df_grouped['reverted_percentage']], padding=3, fontsize=8)
    ax.legend()
    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_reverted.png', dpi=300, bbox_inches='tight')
    plt.show()

    datatypes = ['text', 'entity', 'quantity', 'time', 'globecoordinate']
    df_filt = df[df['source'].isin(datatypes)]

    df_filt_grouped = df_filt.groupby(['source', 'label']).agg({
        'count_reverted': 'sum',
        'count_non_reverted': 'sum'
    }).reset_index()

    labels_unique = df_filt_grouped['label'].unique()
    sources_unique = datatypes

    n_sources = len(sources_unique)
    n_labels = len(labels_unique)
    group_width = n_labels + 1

    fig, ax = plt.subplots(figsize=(18, 6))

    colors = plt.cm.tab10.colors 
    label_color = {label: colors[i] for i, label in enumerate(labels_unique)}

    for s_idx, source in enumerate(sources_unique):
        df_source = df_filt_grouped[df_filt_grouped['source'] == source]
        
        for l_idx, label in enumerate(labels_unique):
            row = df_source[df_source['label'] == label]
            if row.empty:
                continue
            
            x_pos = s_idx * group_width + l_idx
            color = label_color[label]
            
            non_rev = row['count_non_reverted'].values[0]
            rev = row['count_reverted'].values[0]
            
            bars_nrv = ax.bar(x_pos, non_rev, color=color, edgecolor='black', alpha=0.5, label=f'{label} (non-rev)' if s_idx == 0 else "")
            bars_rev = ax.bar(x_pos, rev, bottom=non_rev, color=color, edgecolor='black', alpha=1.0, label=f'{label}' if s_idx == 0 else "")
            
            # ax.bar_label(bars_nrv, labels=row['count_non_reverted'], label_type='edge', fontsize=7, color='black')
            # ax.bar_label(bars_rev, labels=row['count_reverted'], label_type='center', fontsize=7, color='black', fontweight='bold')

            total = rev + non_rev
            pct = (rev * 100 / total) if total > 0 else 0
            ax.text(x_pos, total * 1.05, f'{pct:.1f}%', ha='center', va='bottom', fontsize=7, color='black')

    group_centers = [s_idx * group_width + (n_labels - 1) / 2 for s_idx in range(n_sources)]
    ax.set_xticks(group_centers)
    ax.set_xticklabels(sources_unique, fontsize=12)

    # Vertical separators between datatype groups
    for s_idx in range(1, n_sources):
        ax.axvline(x=s_idx * group_width - 0.5, color='gray', linestyle='--', linewidth=1)

    ax.set_yscale('log')
    ax.set_xlabel('Datatype', fontsize=12)
    ax.set_ylabel('Number of Changes (log scale)', fontsize=12)
    ax.set_title('Reverted vs Non-Reverted Changes by Datatype and Label', fontsize=14, fontweight='bold')

    # Legend: one entry per label, dark=reverted, light=non-reverted
    
    legend_elements = [Patch(facecolor=label_color[l], edgecolor='black', label=l) for l in labels_unique]
    legend_elements += [
        Patch(facecolor='white', edgecolor='black', alpha=0.5, label='Light = Non-Reverted'),
        Patch(facecolor='gray', edgecolor='black', label='Dark = Reverted'),
    ]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1), loc='upper left')

    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_per_datatype.png', dpi=300, bbox_inches='tight')
    plt.show()

    # -----------------------------------------------------
    # change types per user (without the reverted edit)
    # -----------------------------------------------------

    df_ut_grouped = df_ut.groupby(['datatype', 'label', 'user_type']).agg({
        'total': 'sum'
    }).reset_index()

    df_ut_grouped['pct'] = df_ut_grouped.groupby(['datatype', 'label'])['total'].transform(lambda x: x / x.sum() * 100)

    user_types_unique = df_ut_grouped['user_type'].unique()
    labels_unique = df_ut_grouped['label'].unique()
    
    n_datatypes = len(datatypes)
    n_labels = len(labels_unique)
    group_width = n_labels + 1

    colors = plt.cm.tab10.colors
    label_color = {label: colors[i] for i, label in enumerate(labels_unique)}
    user_type_alpha = {ut: 0.3 + 0.7 * i / (len(user_types_unique) - 1) for i, ut in enumerate(user_types_unique)}

    fig, ax = plt.subplots(figsize=(18, 6))

    for d_idx, datatype in enumerate(datatypes): # datatype
        df_source = df_ut_grouped[df_ut_grouped['datatype'] == datatype]

        for l_idx, label in enumerate(labels_unique):
            df_label = df_source[df_source['label'] == label]
            if df_label.empty:
                continue

            x_pos = d_idx * group_width + l_idx
            color = label_color[label]
            bottom = 0

            for ut_idx, user_type in enumerate(user_types_unique):
                row = df_label[df_label['user_type'] == user_type]
                if row.empty:
                    continue

                pct = row['pct'].values[0]
                total = row['total'].values[0]

                ax.bar(x_pos, pct, bottom=bottom, color=color, edgecolor='black',
                    alpha=user_type_alpha[user_type],
                    label=f'{label} - {user_type}' if d_idx == 0 else "")

                def format_number(value):
                    return f'{int(value / 1000)}k'

                if pct > 5:
                    value = format_number(int(total)) if total >= 1000 else int(total)
                    ax.text(x_pos, bottom + pct / 2, f'{value}', 
                            ha='center', va='center', fontsize=6, color='black')
                
                bottom += pct

            # Total on top
            # ax.text(x_pos, bottom * 1.05, f'{int(bottom):,}', ha='center', va='bottom', fontsize=6, color='black')

    group_centers = [d_idx * group_width + (n_labels - 1) / 2 for d_idx in range(n_datatypes)]
    ax.set_xticks(group_centers)
    ax.set_xticklabels(datatypes, fontsize=12)

    for d_idx in range(1, n_datatypes):
        ax.axvline(x=d_idx * group_width - 0.5, color='gray', linestyle='--', linewidth=1)

    # ax.set_yscale('log')
    ax.set_xlabel('Datatype', fontsize=12)
    ax.set_ylabel('Percentage of Changes (%)', fontsize=12)
    ax.set_title('Total Changes by Datatype, Label and User', fontsize=14, fontweight='bold')

    # Legend: color = label, alpha = user type
    legend_elements = [Patch(facecolor=label_color[l], edgecolor='black', label=l) for l in labels_unique]
    legend_elements += [Patch(facecolor='gray', edgecolor='black', alpha=user_type_alpha[ut], label=ut) for ut in user_types_unique]
    ax.legend(handles=legend_elements, bbox_to_anchor=(1.01, 1), loc='upper left')

    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_per_usertype.png', dpi=300, bbox_inches='tight')
    plt.show()


def reverted_edits(db_config, reload_data):
    sql_query = """
        create table reverted_edits_user_type_overtime as
        select c.year_month, user_type, count(*) as count_reverted_edit
        from revision r join value_change c on r.revision_id = c.revision_id
        where is_reverted = 1
        group by c.year_month, user_type;
    """

    query_name = 'reverted_edits_user_type_overtime'
    sql_runner = SQLRunner(db_config)
    if reload_data:
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM reverted_edits_user_type_overtime;')
        df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/{query_name}.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/{query_name}.csv')
        else:
            df = sql_runner.query_to_df('SELECT * FROM reverted_edits_user_type_overtime;')
            if len(df) == 0:
                print(f'No results found for {query_name}. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)

            del sql_runner

    fig, ax = plt.subplots(figsize=(12, 6))
    user_types = df['user_type'].unique()
    df['year_month'] = pd.to_datetime(df['year_month'])
    for user_type in user_types:
        filtered_df = df[df['user_type'] == user_type].copy()
        ax.plot(filtered_df['year_month'], filtered_df['count_reverted_edit'], label=user_type)
        
    ax.set_xlabel("Time")
    ax.set_ylabel("Number of Reverted Edits")
    ax.set_yscale('log')
    ax.legend()
    plt.title('Number of Reverted Edits per User Type Overtime')
    plt.show()

    plt.savefig(f'{RESULTS_DIR_FIGURES}/reverted_edits_user_type_overtime.png', dpi=300, bbox_inches='tight')

    
def redirects_analysis(db_config, reload_data):
    query = """
        CREATE TABLE redirects_analysis AS
        SELECT 
            es.entity_id,
            EXTRACT(EPOCH FROM (r2.first_redirect_timestamp - es.first_revision_timestamp)) / 86400 AS time_to_redirect_in_days,
            es.num_revisions
        FROM entity_stats es
        JOIN (
            SELECT entity_id, MIN(timestamp) AS first_redirect_timestamp
            FROM revision
            WHERE redirect = TRUE
            GROUP BY entity_id
        ) r2 ON r2.entity_id = es.entity_id;
    """
    if reload_data:
        sql_runner = SQLRunner(db_config)
        sql_runner.execute_query(query)
        df = sql_runner.query_to_df('SELECT * FROM redirects_analysis;')
        df.to_csv(f'{RESULTS_DIR}/redirects_analysis.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/redirects_analysis.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/redirects_analysis.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT * FROM redirects_analysis;')
            if len(df) == 0:
                print(f'No results found for redirects_analysis. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/redirects_analysis.csv', index=False)

            del sql_runner

    fig, ax = plt.subplots(figsize=(10, 6))

    df['time_to_redirect_in_days'] = np.floor(df['time_to_redirect_in_days'])

    def assign_bucket(days):
        if days <= 5:
            return '1-5 days'
        elif days <= 30:
            return '6-30 days'
        elif days <= 180:
            return '1-6 months'
        else:
            return '> 6 months'

    df['bucket'] = df['time_to_redirect_in_days'].apply(assign_bucket)

    bucket_order = ['1-5 days', '6-30 days', '1-6 months', '> 6 months']
    df_grouped = df.groupby('bucket')['entity_id'].count().reindex(bucket_order)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.bar(df_grouped.index, df_grouped.values, color='steelblue', edgecolor='black')

    for i, (label, val) in enumerate(zip(df_grouped.index, df_grouped.values)):
        ax.text(i, val * 1.01, f'{int(val):,}', ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Time to Redirect (days)', fontsize=12)
    ax.set_ylabel('Number of Entities', fontsize=12)
    ax.set_title('Time to Redirect', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/redirects_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()
    

def save_fig(fig, path):
    plt.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)

def format_number(n):
    n = float(n)
    if n >= 1_000_000_000:
        return f'{n/1_000_000_000:.1f}B'
    elif n >= 1_000_000:
        v = n / 1_000_000
        return f'{v:.0f}M' if v >= 100 else f'{v:.1f}M'
    elif n >= 1_000:
        v = n / 1_000
        return f'{v:.0f}K' if v >= 100 else f'{v:.1f}K'
    return str(int(n))

COLORS = ['#0072B2', '#E69F00', '#009E73']

# Descriptive analysis of dataset
def property_stats(db_config, reload_data):

    query_name = 'stats_properties'
    if reload_data:
        
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM stats_properties;')
        df.to_csv(f'{RESULTS_DIR}/stats_properties.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/stats_properties.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/stats_properties.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT * FROM stats_properties;')
            if len(df) == 0:
                print(f'No results found for stats_properties. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/stats_properties.csv', index=False)

            del sql_runner

    top_filter = 10

    df['property_label'] = df['property_label'].fillna('Label Unknown')
    df['display_label'] = df['property_label'].apply(
        lambda x: '\n'.join(textwrap.wrap(str(x), width=40))
    )
    df_filtered = df[df['count_entities'] >= 100].copy()

    df_filtered['pct_create'] = (df_filtered['count_create'] / df_filtered['count_changes']) * 100
    df_filtered['pct_delete'] = (df_filtered['count_delete'] / df_filtered['count_changes']) * 100
    df_filtered['pct_update'] = (df_filtered['count_update'] / df_filtered['count_changes']) * 100

    mpl.rcParams.update({
        'font.size': 4,
        'axes.titlesize': 4,
        'axes.labelsize': 4,
        'xtick.labelsize': 4,
        'ytick.labelsize': 4,
        'legend.fontsize': 4,
        'figure.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': False,
    })

    # --- Plot 1: Top properties most used ---
    df_filtered.sort_values('count_entities', ascending=True, inplace=True)  # ascending for barh so top is at top
    df_top = df_filtered.tail(top_filter) # get tail

    fig, ax = plt.subplots(figsize=(2.5, 2))
    bars = ax.barh(df_top['display_label'], df_top['count_entities'], color=COLORS[2], edgecolor='none')
    ax.bar_label(bars, labels=[format_number(c) for c in df_top['count_entities']], fontsize=4)
    ax.set_xlabel('Number of Entities')
    # ax.set_title(f'Top {top_filter} Entity Types by Number of Enities')
    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda x, _: format_number(x)))
    save_fig(fig, f'{RESULTS_DIR}/figures/property_count_{top_filter}.png')

    # --- Plot 2: Type of change stacked bar ---
    df_top = df_filtered.nlargest(top_filter, 'count_entities')
    x = np.arange(len(df_top))

    fig, ax = plt.subplots(figsize=(2.5, 2))
    ax.bar(x, df_top['pct_create'], label='Create', color=COLORS[0], edgecolor='none')
    ax.bar(x, df_top['pct_delete'], bottom=df_top['pct_create'], label='Delete', color=COLORS[1], edgecolor='none')
    ax.bar(x, df_top['pct_update'], bottom=df_top['pct_create'] + df_top['pct_delete'], label='Update', color=COLORS[2], edgecolor='none')
    ax.set_xticks(x)
    ax.set_xticklabels(df_top['display_label'], rotation=45, ha='right', fontsize=4)
    ax.set_ylabel('Percentage of changes')
    fig.legend(loc='outside lower right', markerscale=0.2, handlelength=1)
    save_fig(fig, f'{RESULTS_DIR}/figures/property_top_{top_filter}_change_type.png')


def entity_type_stats(db_config, reload_data):

    query_name = 'stats_entity_type'
    if reload_data:
        
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM entity_type_stats;')
        df.to_csv(f'{RESULTS_DIR}/entity_type_stats.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/entity_type_stats.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/entity_type_stats.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT * FROM entity_type_stats;')
            if len(df) == 0:
                print(f'No results found for entity_type_stats. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/entity_type_stats.csv', index=False)

            del sql_runner

    top_filter = 10

    # sandbox entities
    entities_to_filter = ['Q16943273', 'Q17339402', 'Q4115189', 'Q13406268', 'Q15397819', 'Q112795079']
    df = df[~df['individual_type'].isin(entities_to_filter)].copy()

    # count is count of entities
    df.sort_values(by='count', ascending=False, inplace=True)
    df['entity_type_label'] = df['entity_type_label'].fillna('Label Unknown')

    label_counts = df['entity_type_label'].value_counts()
    df['display_label'] = df.apply(
        lambda row: f"{row['entity_type_label']} ({row['individual_type']})" 
        if label_counts[row['entity_type_label']] > 1 
        else row['entity_type_label'], 
        axis=1
    )

    df['display_label'] = df['display_label'].apply(
        lambda x: '\n'.join(textwrap.wrap(str(x), width=25))
    )

    df['total_edits_by_users'] = df['num_bot_edits'] + df['num_anonymous_edits'] + df['registered_user_edits']
    df['pct_bot'] = (df['num_bot_edits'] / df['total_edits_by_users']) * 100
    df['pct_anonymous'] = (df['num_anonymous_edits'] / df['total_edits_by_users']) * 100
    df['pct_registered'] = (df['registered_user_edits'] / df['total_edits_by_users']) * 100

    mpl.rcParams.update({
        'font.size': 4,
        'axes.titlesize': 4,
        'axes.labelsize': 4,
        'xtick.labelsize': 4,
        'ytick.labelsize': 4,
        'legend.fontsize': 4,
        'figure.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.grid': False,
    })

    # --- Plot 1: Top entity types by count ---
    df.sort_values('count', ascending=True, inplace=True)  # ascending for barh so top is at top
    df_top = df.tail(top_filter)

    fig, ax = plt.subplots(figsize=(2.5, 2))
    bars = ax.barh(df_top['display_label'], df_top['count'], color=COLORS[2], edgecolor='none')
    ax.bar_label(bars, labels=[format_number(c) for c in df_top['count']], fontsize=4)
    ax.set_xlabel('Number of Entities')
    # ax.set_title(f'Top {top_filter} Entity Types by Number of Enities')
    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda x, _: format_number(x)))
    save_fig(fig, f'{RESULTS_DIR}/figures/entity_type_count_{top_filter}.png')

    # --- Plot 2: Top by value changes ---
    
    df.sort_values('num_value_changes', ascending=True, inplace=True)
    df_top = df.tail(top_filter)

    fig, ax = plt.subplots(figsize=(2.5, 2))
    
    bars = ax.barh(df_top['display_label'], df_top['num_value_changes'], color=COLORS[0], edgecolor='none')
    ax.bar_label(bars, labels=[format_number(c) for c in df_top['num_value_changes']])
    ax.set_xlabel('Number of Value Changes')
    # ax.set_title(f'Top {top_filter} Entity Types by Value Changes')
    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda x, _: format_number(x)))

    save_fig(fig, f'{RESULTS_DIR}/figures/entity_type_top_{top_filter}_value_changes.png')

    fig, ax = plt.subplots(figsize=(2.5, 2))
    
    df['value_changes_per_entity'] = df['num_value_changes'] / df['count'] # normalize by count so I don't just get the
    df_filtered = df[df['count'] >= 100].copy() # filter out the ones with very low count, if not the ratio is skewed
    df_filtered.sort_values('value_changes_per_entity', ascending=True, inplace=True)
    df_top = df_filtered.tail(top_filter)

    bars = ax.barh(df_top['display_label'], df_top['value_changes_per_entity'], color=COLORS[1], edgecolor='none')
    ax.bar_label(bars, labels=[format_number(c) for c in df_top['value_changes_per_entity']])
    ax.set_xlabel('Number of Value Changes per Entity of the Type')
    # ax.set_title(f'Top {top_filter} Most Edited Entity Types')
    ax.xaxis.set_major_formatter(mpl.ticker.FuncFormatter(lambda x, _: format_number(x)))

    plt.subplots_adjust(wspace=0.5)

    save_fig(fig, f'{RESULTS_DIR}/figures/entity_type_top_{top_filter}_most_edited.png')

    # --- Plot 4: User type stacked bar ---
    df_top = df_filtered.nlargest(top_filter, 'value_changes_per_entity')
    x = np.arange(len(df_top))

    fig, ax = plt.subplots(figsize=(2.5, 2))
    ax.bar(x, df_top['pct_bot'], label='Bot', color=COLORS[0], edgecolor='none')
    ax.bar(x, df_top['pct_anonymous'], bottom=df_top['pct_bot'], label='Anonymous', color=COLORS[1], edgecolor='none')
    ax.bar(x, df_top['pct_registered'], bottom=df_top['pct_bot'] + df_top['pct_anonymous'], label='Registered', color=COLORS[2], edgecolor='none')
    ax.set_xticks(x)
    ax.set_xticklabels(df_top['display_label'], rotation=45, ha='right', fontsize=4)
    ax.set_ylabel('Percentage of Edits (%)')
    # ax.set_title(f'Edit Distribution by User Type (Top {top_filter} Most Edited Entity Types)')
    ax.legend(loc='outside lower center', markerscale=0.2, handlelength=1)
    save_fig(fig, f'{RESULTS_DIR}/figures/entity_type_top_{top_filter}_user_type.png')


def general_distribution_of_changes(db_config, reload_data):

    if reload_data:
        df = sql_runner.query_to_df('SELECT entity_id, num_revisions, num_value_changes FROM entity_stats;')
        df.to_csv(f'{RESULTS_DIR}/entity_stats.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/entity_stats.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/entity_stats.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT entity_id, num_revisions, num_value_changes FROM entity_stats;')
            if len(df) == 0:
                print(f'No results found for entity_stats. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/entity_stats.csv', index=False)
            del sql_runner

    mpl.rcParams.update({
        'font.size': 3,
        'axes.titlesize': 4,
        'axes.labelsize': 4,
        'xtick.labelsize': 4,
        'ytick.labelsize': 4,
        'legend.fontsize': 4,
        'figure.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False,
    })

    fig, axes = plt.subplots(1, 2, figsize=(2, 2))
    df = df[df['entity_id'] != '4115189']

    # 2. Distribution of revisions per entity (histogram)
    axes[0].hist(df['num_revisions'], bins=20, color=COLORS[0], edgecolor='none')
    axes[0].set_yscale('log')
    # axes[0].set_title('Distribution of Revisions per Entity')
    axes[0].set_xlabel('Number of Revisions')
    axes[0].set_ylabel('Number of Entities (log)')

    # 4. Distribution of value changes per entity
    axes[1].hist(df['num_value_changes'], bins=20, color=COLORS[1], edgecolor='none')
    axes[1].set_yscale('log')
    # axes[1].set_title('Distribution of Value Changes per Entity')
    axes[1].set_xlabel('Number of Value Changes')
    axes[1].set_ylabel('Number of Entities (log)')

    save_fig(fig, f'{RESULTS_DIR}/figures/descriptive_overview.png')
    
    max_revisions = df['num_revisions'].max()
    max_value_changes = df['num_value_changes'].max()
    min_revisions = df['num_revisions'].min()
    min_value_changes = df['num_value_changes'].min()
    avg_value_changes = df['num_value_changes'].mean()
    avg_num_revisions = df['num_revisions'].mean()

    entity_with_most_revisions = df.loc[df['num_revisions'].idxmax()]['entity_id']
    entity_with_most_value_changes = df.loc[df['num_value_changes'].idxmax()]['entity_id']

    print('================ STATISTICS ================')
    print(f'Max number of revisions for an entity: {max_revisions}, Min number of revisions for an entity: {min_revisions}')
    print(f'Max number of value changes for an entity: {max_value_changes}, Min number of value changes for an entity: {min_value_changes}')
    print(f'Entity with most revisions: {entity_with_most_revisions} ({max_revisions} revisions)')
    print(f'Entity with most value changes: {entity_with_most_value_changes} ({max_value_changes} value changes)')
    
    print(f'Average number of value changes per entity: {avg_value_changes:.2f}')
    print(f'Average number of revisions per entity: {avg_num_revisions}')


if __name__ == "__main__":
    with open(YAML_SETUP_PATH, 'r') as f:
        set_up = yaml.safe_load(f)

    with open(set_up['database_config_path'], 'r') as f:
        db_config = json.load(f)

    # reload_data = set_up['analysis']['classification_analysis']['dist_change_types_per_datatype']['reload_data']
    # distribution_change_types_per_datatype(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['classification_analysis']['dist_change_types_per_user']['reload_data']
    # distribution_change_types_per_user(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['classification_analysis']['soft_vs_hard_deletions']['reload_data']
    # soft_deletion_vs_shard_deletion(db_config['db_params'], reload_data)
    
    # reload_data = set_up['analysis']['classification_analysis']['redirects_analysis']['reload_data']
    # redirects_analysis(db_config['db_params'], reload_data)
    
    # reload_data = set_up['analysis']['classification_analysis']['distribution_change_types']['reload_data']
    # distribution_change_types(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['classification_analysis']['reverted_edit_analysis']['reload_data']
    # reverted_edits(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['classification_analysis']['entity_types_analysis']['reload_data']
    # entity_type_stats(db_config['db_params'], reload_data)

    # reload_data = set_up['analysis']['classification_analysis']['general_distribution_of_changes']['reload_data']
    # general_distribution_of_changes(db_config['db_params'], reload_data)

    reload_data = set_up['analysis']['classification_analysis']['property_analysis']['reload_data']
    property_stats(db_config['db_params'], reload_data=reload_data)