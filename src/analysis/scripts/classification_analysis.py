import sys
from turtle import width
import pandas as pd
import matplotlib.pyplot as plt
import json
import yaml
import os
import numpy as np
from matplotlib.patches import Patch
import matplotlib as mpl
import textwrap

from src.sql_runner.sql_runner import SQLRunner
from src.utils.const import RESULTS_DIR, YAML_SETUP_PATH, SQL_SCRIPT_DIR

RESULTS_DIR = f'{RESULTS_DIR}/classification_analysis'
os.makedirs(RESULTS_DIR, exist_ok=True)

RESULTS_DIR_FIGURES = f'{RESULTS_DIR}/figures'
os.makedirs(RESULTS_DIR_FIGURES, exist_ok=True)

# https://jrnold.github.io/ggthemes/reference/ptol_pal.html
color_palette = [
    '#4477AA', '#88CCEE', '#117733', '#DDCC77', '#CC6677', 
    '#AA4499', '#332288', '#6699CC', '#44AA99', 
    '#117733', '#999933', '#661100', '#882255' 
]

clear_color_palette = ['#88CCEE', '#DDCC77', '#CC6677', '#44AA99', '#999933', '#6699CC']

def format_number(n):
    n = float(n)
    if n >= 1_000_000_000:
        return f'{n/1_000_000_000:.1f}B'
    elif n >= 1_000_000:
        v = n / 1_000_000
        return f'{v:.1f}M'
    elif n >= 1_000:
        v = n / 1_000
        return f'{v:.1f}K'
    return str(int(n))

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


def save_fig(fig, path):
    plt.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches='tight', pad_inches=0)
    plt.close(fig)


def distribution_change_types(db_config, reload_data):

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

    # create_order = ['reference_insertion', 'qualifier_insertion', 'statement_insertion', 'soft_insertion']
    # update_order = ['link_change', 're_formatting', 'refinement', 'unrefinement', 'property_value_update', 'textual_change']
    # delete_order = ['reference_deletion', 'qualifier_deletion', 'statement_deletion', 'soft_deletion']
    # all_order = create_order + update_order + delete_order

    df_grouped = df_grouped.set_index('label').sort_values('total').reset_index()

    fig, ax = plt.subplots(figsize=(4.5,6))
    width = 0.4
    y = range(len(df_grouped['label']))
    labels = []
    for label in df_grouped['label']:
        if label == 'property_value_update':
            labels.append('value update')
        else:
            labels.append(label.replace('_', '\n'))
        
    # x_pos_rev = [i + width if 'qualifier' not in label and 'reference' not in label else i for i, label in enumerate(labels)]
    x_pos_non_rev = [i/2 +0.1 for i in y]
    
    bars2 = ax.barh(x_pos_non_rev, df_grouped['total'], height=width, color=clear_color_palette[1])
    for bar, p, r in zip(bars2, df_grouped['total'], df_grouped['reverted_percentage']):
        # label = f'{format_number(p)} ({r:.1f}%)' if r > 0 else f'{format_number(p)}'
        label = f'{format_number(p)} ({r:.1f}%)'
        bar_width = bar.get_width()
        bar_y = bar.get_y() + bar.get_height() / 2
        threshold = 10000000
        if bar_width > threshold:
            ax.text(bar_width*0.3, bar_y, label,
                    ha='center', va='center', fontsize=9, color='black')
        else:
            ax.text(bar_width * 1.05, bar_y, label,
                    ha='left', va='center', fontsize=9, color='black')

    ax.set_xscale('log')
    ax.set_yticks(x_pos_non_rev)
    ax.set_ylim(-0.2, x_pos_non_rev[-1] +0.3)
    ax.set_yticklabels(labels, fontsize=9)
    ax.tick_params(axis='x', labelsize=9) # font size of x-axis labels
    ax.set_xlabel('Number of Changes (log scale)', fontsize=9)
    # fig.legend(loc='outside lower left', markerscale=0.1, handlelength=1, fontsize=6)
    
    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_reverted.png', dpi=500, pad_inches=0)
    plt.show()

    # -----------------------------------------------------
    # change types per datatypes with reverted edit percentage
    # -----------------------------------------------------

    df['source'] = df['source'].replace({
        'globecoordinate_latitude': 'globecoordinate',
        'globecoordinate_longitude': 'globecoordinate'
    })
    
    datatypes = ['globecoordinate', 'quantity', 'time', 'text', 'entity']
    df_filt = df[df['source'].isin(datatypes)]

    df_filt_grouped = df_filt.groupby(['source', 'label']).agg({
        'count_reverted': 'sum',
        'count_non_reverted': 'sum',
        'total': 'sum'
    }).reset_index()

    df_filt_grouped['reverted_percentage'] = (df_filt_grouped['count_reverted'] / df_filt_grouped['total']) * 100
    
    df_filt_grouped['label'] = df_filt_grouped['label'].str.replace('property_value_update', 'value_update')
    labels_unique = df_filt_grouped['label'].unique()
    label_color = {label.replace('_', ' '): clear_color_palette[i] for i, label in enumerate(labels_unique)}

    datatype_n_labels = {}
    for datatype in datatypes:
        df_source = df_filt_grouped[df_filt_grouped['source'] == datatype]
        datatype_n_labels[datatype] = df_source['label'].nunique()
    
    # start of bars
    width_bars = 0.14

    datatype_x_start = {}
    x_cursor = 0
    for datatype in datatypes:
        datatype_x_start[datatype] = x_cursor/5
        x_cursor += datatype_n_labels[datatype]

    fig, ax = plt.subplots(figsize=(5, 5)) # width, height
    group_centers = []
    x_positions = []
    all_bars = []
    for s_idx, source in enumerate(datatypes):
        df_source = df_filt_grouped[df_filt_grouped['source'] == source]
        x_start = datatype_x_start[source]
        labels_dt = df_source['label'].unique()

        for l_idx, label in enumerate(labels_dt):
            row = df_source[df_source['label'] == label]
            if row.empty:
                continue
            
            x_pos = x_start + l_idx/6
            x_positions.append(x_pos)
            color = label_color[label.replace('_', ' ')]
            
            total = row['total'].values[0]
            
            bars_total = ax.barh(x_pos, total, color=color, edgecolor='black', alpha=0.5, label=f'{label}' if s_idx == 0 else "", height=width_bars)
            all_bars.append((bars_total[0], total, row['reverted_percentage'].values[0]))

    for bar, p, r in all_bars:
        label = f'{format_number(p)} ({r:.1f}%)' if r > 0 else f'{format_number(p)}'
        bar_width = bar.get_width()
        bar_y = bar.get_y() + bar.get_height() / 2
        threshold = 1000000
        if bar_width > threshold:
            ax.text(bar_width*0.3, bar_y, label,
                    ha='center', va='center', fontsize=10, color='black')
        else:
            ax.text(bar_width * 1.05, bar_y, label,
                    ha='left', va='center', fontsize=10, color='black')

    ax.set_xscale('log')
    ax.set_yticks(x_positions)
    
    # center of each group to put the datatype label
    group_centers = []
    for dt in datatypes:
        if datatype_n_labels[dt] % 2 == 0:
            group_centers.append(datatype_x_start[dt] + datatype_n_labels[dt]/14)
        else:
            group_centers.append(datatype_x_start[dt] + (datatype_n_labels[dt]+1)/14)

    ax.set_yticks(group_centers)
    ax.set_yticklabels([d.replace('_', ' ') if d != 'globecoordinate' else 'globe\ncoordinate' for d in datatypes], fontsize=9, multialignment='center')

    # Vertical separators between datatype groups
    for i, datatype in enumerate(datatypes[1:], 1):
        prev_datatype = datatypes[i - 1]
        
        # last bar of previous group
        last_bar_prev = datatype_x_start[prev_datatype] + (datatype_n_labels[prev_datatype] - 1) / 6
        # first bar of current group
        first_bar_curr = datatype_x_start[datatype]
        
        midpoint = (last_bar_prev + first_bar_curr) / 2
        ax.axhline(y=midpoint, color='black', linestyle='--', linewidth=1)

    ax.set_xscale('log')
    ax.set_ylim(-0.2, x_cursor/5-0.1)
    ax.set_xlabel('Number of Changes (log scale)', fontsize=9)

    # Legend: one entry per label, dark=reverted, light=non-reverted
    legend_elements = [Patch(facecolor=label_color[l.replace('_', ' ')], edgecolor='black', label=l.replace('_', ' ')) for l in labels_unique]
    # legend_elements += [
    #     Patch(facecolor='white', edgecolor='black', alpha=0.5, label='light (non-reverted)'),
    #     Patch(facecolor='gray', edgecolor='black', label='dark (reverted)'),
    # ]
    fig.legend(handles=legend_elements, ncol=3, loc='outside lower center', fontsize=9, markerscale=0.08, handlelength=1, bbox_to_anchor=(0.53, -0.06))

    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_per_datatype.png', dpi=200, bbox_inches='tight', pad_inches=0)
    plt.show()

    # -----------------------------------------------------
    # change types per user (without the reverted edit)
    # -----------------------------------------------------

    df_ut['datatype'] = df_ut['datatype'].replace({
        'globecoordinate_latitude': 'globecoordinate',
        'globecoordinate_longitude': 'globecoordinate'
    })

    df_ut_grouped = df_ut.groupby(['datatype', 'label', 'user_type']).agg({
        'total': 'sum'
    }).reset_index()

    df_ut_grouped['label'] = df_ut_grouped['label'].str.replace('property_value_update', 'value_update')
    labels_unique = df_ut_grouped['label'].unique()

    df_ut_grouped['pct'] = df_ut_grouped.groupby(['datatype', 'label'])['total'].transform(lambda x: x / x.sum() * 100)
    
    df_ut_grouped['user_type'] = df_ut_grouped['user_type'].str.replace('human', 'registered')
    user_types_unique = df_ut_grouped['user_type'].unique()
    user_type_alpha = {ut: 0.3 + 0.7 * i / (len(user_types_unique) - 1) for i, ut in enumerate(user_types_unique)}
    
    datatype_n_labels = {}
    for datatype in datatypes:
        df_source = df_ut_grouped[df_ut_grouped['datatype'] == datatype]
        datatype_n_labels[datatype] = df_source['label'].nunique()

    datatype_x_start = {}
    x_cursor = 0
    for datatype in datatypes:
        datatype_x_start[datatype] = x_cursor/5
        x_cursor += datatype_n_labels[datatype]

    fig, ax = plt.subplots(figsize=(7, 7))
    width_bars = 0.12

    for d_idx, datatype in enumerate(datatypes): # datatype
        df_source = df_ut_grouped[df_ut_grouped['datatype'] == datatype]
        x_start = datatype_x_start[datatype]
        labels_dt = df_source['label'].unique()
        
        for l_idx, label in enumerate(labels_dt):
            df_label = df_source[df_source['label'] == label]
            if df_label.empty:
                continue
            
            x_pos = x_start + l_idx/6
            color = label_color[label.replace('_', ' ')]
            bottom = 0

            for ut_idx, user_type in enumerate(user_types_unique):
                row = df_label[df_label['user_type'] == user_type]
                if row.empty:
                    continue

                pct = row['pct'].values[0]
                total = row['total'].values[0]

                ax.barh(x_pos, pct, left=bottom, color=color, edgecolor='black',
                    alpha=user_type_alpha[user_type],
                    label=f'{label} - {user_type}' if d_idx == 0 else "", height=width_bars)

                # if pct > 5:
                #     value = format_number(int(total)) if total >= 1000 else int(total)
                #     ax.text(bottom + pct / 2, x_pos, f'{value}', 
                #             ha='center', va='center', fontsize=8, color='black')
                
                bottom += pct

            # Total on top
            # ax.text(x_pos, bottom * 1.05, f'{int(bottom):,}', ha='center', va='bottom', fontsize=6, color='black')
     
    # group_centers = [datatype_x_start[dt] + (datatype_n_labels[dt]-1) / 2 for dt in datatypes]
    group_centers = []
    for dt in datatypes:
        if datatype_n_labels[dt] % 2 == 0:
            group_centers.append(datatype_x_start[dt] + datatype_n_labels[dt]/14)
        else:
            group_centers.append(datatype_x_start[dt] + (datatype_n_labels[dt]+1)/14)
    ax.set_yticks(group_centers)
    ax.set_yticklabels([d.replace('_', ' ') if d != 'globecoordinate' else f'globe\ncoordinate' for d in datatypes], fontsize=13, multialignment='center')
    
    # dash lines to separate the datatypes
    for i, datatype in enumerate(datatypes[1:], 1):
        prev_datatype = datatypes[i - 1]
        
        # last bar of previous group
        last_bar_prev = datatype_x_start[prev_datatype] + (datatype_n_labels[prev_datatype] - 1) / 6
        # first bar of current group
        first_bar_curr = datatype_x_start[datatype]
        
        midpoint = (last_bar_prev + first_bar_curr) / 2
        ax.axhline(y=midpoint, color='black', linestyle='--', linewidth=1)

    # ax.set_xlabel('Datatype', fontsize=12)
    ax.set_ylim(-0.2, x_cursor/5-0.1)
    ax.set_xlabel('Percentage of Changes', fontsize=13)
    # ax.set_title('Total Changes by Datatype, Label and User', fontsize=14, fontweight='bold')

    # Legend: color = label, alpha = user type
    legend_elements = [Patch(facecolor=label_color[l.replace('_', ' ')], edgecolor='black', label=l.replace('_', ' ')) for l in labels_unique]
    legend_elements += [Patch(facecolor='gray', edgecolor='black', alpha=user_type_alpha[ut], label=ut) for ut in user_types_unique]
    # ax.legend()
    fig.legend(handles=legend_elements,  ncol=len(legend_elements)//2 -1, loc='outside lower center',  bbox_to_anchor=(0.55, -0.12), fontsize=13, markerscale=0.08, handlelength=1)

    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/distribution_change_types_per_usertype.png', dpi=600, bbox_inches='tight', pad_inches=0)
    plt.show()

def change_types_overtime(db_config, reload_data):
    query_name = 'change_types_overtime'
    if reload_data:
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM change_types_overtime;')
        df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/{query_name}.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/{query_name}.csv')
        else:
            sql_runner = SQLRunner(db_config)
            df = sql_runner.query_to_df('SELECT * FROM change_types_overtime;')
            if len(df) == 0:
                print(f'No results found for {query_name}. Please run with reload_data=True (see setup.yml) to execute the query and save results.')
                return
            df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)
            del sql_runner
    df['individual_label'] = df['individual_label'].str.replace('property_value_update', 'value_update')

    # fill all year, datatype, label combination with 0 if they don0t have a value 
    all_years = list(range(2012, 2026))
    all_labels = df['individual_label'].unique()
    all_datatypes = df['datatype'].unique()

    full_index = pd.MultiIndex.from_product(
        [all_years, all_labels, all_datatypes],
        names=['year', 'individual_label', 'datatype']
    )
    df_full = pd.DataFrame(index=full_index).reset_index()

    df = df_full.merge(df, on=['year', 'individual_label', 'datatype'], how='left')
    df['count'] = df['count'].fillna(0)

    #  Change types overtime across all datatypes
    fig, ax = plt.subplots(figsize=(12, 6))
    change_types = df['individual_label'].unique()
    df.sort_values('year', inplace=True)

    df_grouped = df.groupby(['year', 'individual_label'])['count'].sum().reset_index()
    df_grouped.sort_values('year', inplace=True)

    for i, change_type in enumerate(change_types):
        filtered_df = df_grouped[df_grouped['individual_label'] == change_type].copy()
        ax.plot(filtered_df['year'], filtered_df['count'], label=change_type.replace('_', ' '), color=clear_color_palette[i])
    
    plt.setp(ax.get_xticklabels(), visible=True, rotation=45, fontsize=7)

    ax.set_xlabel("Year")
    ax.set_ylabel("Number of Changes")
    ax.set_yscale('log')
    ax.legend()
    plt.title('Change Types Overtime')
    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/change_types_overtime_all.png', dpi=300, bbox_inches='tight')
    plt.show()

    #  Change types overtime per datatype (separate plots)
    datatypes = ['text', 'entity', 'quantity', 'time', 'globecoordinate_latitude', 'globecoordinate_longitude']
    fig, axes = plt.subplots(3, 2, sharex=True, figsize=(10, 10))
    axes = axes.flatten()
    for i, datatype in enumerate(datatypes):
        ax = axes[i]
        filtered_df = df[df['datatype'] == datatype].copy()
        labels = filtered_df['individual_label'].unique()
        for label in labels:
            label_df = filtered_df[filtered_df['individual_label'] == label]
            ax.plot(label_df['year'], label_df['count'], label=label)

        ax.set_title(datatype, fontsize=9)
        ax.set_ylabel("Number of Changes", fontsize=7)
        ax.set_yscale('log')
        ax.legend(fontsize=6, loc='upper left')
        ax.tick_params(axis='both', labelsize=7)
    for ax in axes:
        plt.setp(ax.get_xticklabels(), visible=True, rotation=45, fontsize=7)

    fig.supxlabel("Year", fontsize=9)
    plt.savefig(f'{RESULTS_DIR}/figures/change_types_overtime_datatype.png', dpi=300, bbox_inches='tight')
    plt.show()

def prop_reverts_overtime(db_config, reload_data):
    query_name = 'prop_reverts_overtime'
    if reload_data:
        sql_runner = SQLRunner(db_config)
        with open(f'{SQL_SCRIPT_DIR}/{query_name}.sql', 'r') as f:
            sql_query = f.read()
        sql_runner.execute_query(sql_query)
        df = sql_runner.query_to_df('SELECT * FROM property_time_until_reversion;')
        df.to_csv(f'{RESULTS_DIR}/{query_name}.csv', index=False)
        del sql_runner
    else:
        if os.path.exists(f'{RESULTS_DIR}/{query_name}.csv'):
            df = pd.read_csv(f'{RESULTS_DIR}/{query_name}.csv')
        else: 
            print('Re-run the analysis with reload_data=True to execute the query and save results.')

    
    # remove properties with < 10 reverts
    df = df[df['num_reverted_edits'] >= 10].copy()

    print('Removed properties with less than 10 reverts, remaining properties:', len(df))

    df['avg_day_until_reversion'] = df['avg_day_until_reversion'].astype(int).fillna(0)

    df_grouped = df.groupby('avg_day_until_reversion').size().reset_index(name='num_properties')

    fig, ax = plt.subplots(figsize=(4, 3))
    bars = ax.bar(df_grouped['avg_day_until_reversion'], df_grouped['num_properties'], color=clear_color_palette[0], edgecolor='none')
    # ax.bar_label(bars, labels=[str(c) for c in df_grouped['num_properties']], fontsize=5)
    ax.set_xlabel('Average days until reversion')
    ax.set_ylabel('Number of properties')
    plt.tight_layout()
    plt.savefig(f'{RESULTS_DIR}/figures/prop_reverts_overtime.png', dpi=450, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    with open(YAML_SETUP_PATH, 'r') as f:
        set_up = yaml.safe_load(f)

    with open(set_up['config']['database_config_path'], 'r') as f:
        db_config = json.load(f)
    
    distribution_change_types_setup = set_up['analysis']['distribution_change_types']
    if distribution_change_types_setup['execute']:
        distribution_change_types(db_config, distribution_change_types_setup['reload_data'])

    change_types_overtime_setup = set_up['analysis']['change_types_overtime']
    if change_types_overtime_setup['execute']:
        change_types_overtime(db_config, change_types_overtime_setup['reload_data'])

    prop_reverts_overtime_setup = set_up['analysis']['prop_reverts_overtime']
    if prop_reverts_overtime_setup['execute']:
        prop_reverts_overtime(db_config, prop_reverts_overtime_setup['reload_data'])

    reverted_edits_setup = set_up['analysis']['reverted_edits_user_type_overtime']
    if reverted_edits_setup['execute']:
        reverted_edits(db_config, reverted_edits_setup['reload_data'])
    
    soft_deletion_vs_shard_deletion_setup = set_up['analysis']['soft_deletion_vs_shard_deletion']
    if soft_deletion_vs_shard_deletion_setup['execute']:
        soft_deletion_vs_shard_deletion(db_config, soft_deletion_vs_shard_deletion_setup['reload_data'])