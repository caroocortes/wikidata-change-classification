#!/usr/bin/env python3
"""
Crawler for Wikidata Deleted Properties page
Extracts property ID (first column) and label (second column) to CSV
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import psycopg2
from dotenv import load_dotenv
import os
import csv

def crawl_deleted_properties(url, output_file="deleted_properties.csv"):
    """
    Crawl the Wikidata deleted properties page and extract property IDs and labels.
    
    Args:
        url: URL of the Wikidata deleted properties page
        output_file: Output CSV filename
        
    Returns:
        DataFrame with columns: id, label
        
    """
    
    # Fetch the page
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return pd.DataFrame()
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    tables = soup.find_all('table', class_='wikitable')
    
    if not tables:
        tables = soup.find_all('table')
    
    
    properties = []
    seen_ids = set()
    
    for table_idx, table in enumerate(tables):
        rows = table.find_all('tr')
        
        for row in rows[1:]:
            cells = row.find_all('td')
            
            if len(cells) < 2:
                continue
            
            id_cell = cells[0]
            id_text = id_cell.get_text(strip=True)
            
            id_match = re.search(r'P?(\d+)', id_text)
            if not id_match:
                continue
            
            property_id = id_match.group(1)
            
            if property_id in seen_ids:
                continue
            
            label_cell = cells[1]
            property_label = label_cell.get_text(strip=True)
            
            properties.append({
                'id': property_id,
                'label': property_label
            })
            seen_ids.add(property_id)
            
            print(f"  Found: P{property_id} - {property_label}")
    
    print(f"\n Total unique properties found: {len(properties)}")
    
    df = pd.DataFrame(properties)
    
    if not df.empty:
        df['id'] = df['id'].astype(int)
        df = df.sort_values('id').reset_index(drop=True)
        df['id'] = df['id'].astype(str)
    
    return df


def execute_crawl():
    """
        At the moment of creating the crawler the table had ID as first column and label as second for every deleted property
    """
    url = "https://www.wikidata.org/wiki/Wikidata:Database_reports/Deleted_properties"
    output_file = "deleted_properties.csv"
    
    try:
        # Crawl the page
        df = crawl_deleted_properties(url, output_file)
        
        if df.empty:
            print("\n No properties found. The page format may have changed.")
            return
        
        # Save to CSV
        df.to_csv(output_file, index=False)
        print(f"\n✓ Saved {len(df)} properties to {output_file}")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

def preprocess_csv(input_file, output_file, delimiter=';'):
    """
    Read CSV with mixed quotes and write with standardized double quotes
    """
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        # Read with Python's csv module (handles mixed quotes)
        reader = csv.reader(infile, delimiter=delimiter)
        
        # Write with standard double quotes
        writer = csv.writer(outfile, delimiter=delimiter, quotechar='"', 
                          quoting=csv.QUOTE_MINIMAL)
        
        for row in reader:
            writer.writerow(row)
    
    print(f"Preprocessed CSV saved to {output_file}")


def copy_from_csv(conn, csv_file_path, table_name, columns, primary_keys, delimiter=';'):
    temp_table = f"{table_name}_temp"


    with conn.cursor() as cur:
        cols_definition = ', '.join([f"{col} VARCHAR" for col in columns])
        cur.execute(f"CREATE TEMP TABLE {temp_table} ({cols_definition});")
        
        cols = ','.join(columns)
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            # next(f)  # skip header
            cur.copy_expert(f"""
                COPY {temp_table} ({cols})
                FROM STDIN
                WITH (FORMAT csv, HEADER FALSE, DELIMITER '{delimiter}', QUOTE '"');
            """, f)
        
        print(f"Loaded data into temp table. Removing duplicates...")
        
        cur.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT DISTINCT * FROM {temp_table};")

        # add PK
        if primary_keys:
            
            pk_cols_str = ', '.join(primary_keys)
            # remove duplicates based on primary key columns
            print("Removing duplicates...")
            cur.execute(f"""
                DELETE FROM {table_name} a
                USING {table_name} b
                WHERE a.ctid < b.ctid
                AND {' AND '.join([f'a.{col} = b.{col}' for col in primary_keys])};
            """)

            print("Adding PK")
            cur.execute(f"ALTER TABLE {table_name} ADD PRIMARY KEY ({pk_cols_str});")
    
    conn.commit()

def save_to_db():
    copy_from_csv(conn, 'deleted_properties.csv', 'property_labels', ['id', 'label'], ['id'])

def update_property_label(conn, table_name, property_id_column, property_label_column, deleted_properties_path='deleted_properties.csv'):
    """
        Updates the column "property_label_column" in the "table_name", where the column for property_id is "property_id" 
        Creates a table property_labels from a csv file (csv_file_path) which contains a list of P-ids, Labels for all properties in WD.
        Example: 
            For value_change
                - table_name = 'value_change'
                - property_id_column = 'property_id'
                - property_label_column = 'property_label'
    """

    with conn.cursor() as cur:
        
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'property_labels'
            );
        """)
        exists = cur.fetchone()[0]
        
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {property_label_column} VARCHAR DEFAULT NULL;")
    conn.commit()
    
    if not exists:
        copy_from_csv(conn, deleted_properties_path, 'property_labels', ['id', 'label'], ['id'], ';')

    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_value_change_property_id
                ON {table_name}({property_id_column});

            CREATE INDEX IF NOT EXISTS idx_property_labels_id
                ON property_labels(id);

            CREATE INDEX IF NOT EXISTS idx_value_change_property_label_null
                ON {table_name}({property_id_column})
                WHERE {property_label_column} IS NULL;

            UPDATE {table_name} vc
            SET property_label = pl.label
            FROM property_labels pl
            WHERE (vc.{property_label_column} IS NULL or vc.{property_label_column} = '') AND 'P' || vc.{property_id_column}::VARCHAR = pl.id;

            UPDATE {table_name} vc
            SET property_label = 'label'
            WHERE vc.{property_id_column} = -1 AND vc.{property_label_column} IS NULL;

            UPDATE {table_name} vc
            SET property_label = 'description'
            WHERE vc.{property_id_column} = -2 AND vc.{property_label_column} IS NULL;

        """)
    conn.commit()


if __name__ == "__main__":
    # crawl deleted properties
    # execute_crawl()

    dotenv_path = ".env"
    load_dotenv(dotenv_path)

    DB_USER = os.environ.get("DB_USER")
    DB_PASS = os.environ.get("DB_PASS")
    DB_NAME = os.environ.get("DB_NAME")
    DB_HOST = os.environ.get("DB_HOST")
    DB_PORT = os.environ.get("DB_PORT")
    
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS, 
        host=DB_HOST,
        port=DB_PORT
    )

    # save_to_db()

    update_property_label(conn, 'gold_standard', 'property_id', 'property_label', 'deleted_properties.csv') 
    update_property_label(conn, 'reverted_edit', 'property_id', 'property_label', 'deleted_properties.csv') 
    update_property_label(conn, 'property_replacement', 'property_id', 'property_label', 'deleted_properties.csv') 

    # update_property_label(conn, 'reference_change', 'ref_property_id', 'ref_property_label', 'deleted_properties.csv') 
    # update_property_label(conn, 'qualifier_change', 'qual_property_id', 'qual_property_label', 'deleted_properties.csv') 

    # copy_from_csv(conn, 'gold_standard/reverted_edit_gold_standard.csv', 'reverted_edit_gs', ["revision_id","entity_id","entity_label","value_id","property_id","change_target","property_label","old_value","old_value_label","new_value","new_value_label","label","datatype"], ['revision_id', 'property_id', 'value_id', 'change_target'], ',')