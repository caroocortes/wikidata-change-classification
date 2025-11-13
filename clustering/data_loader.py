import os
import psycopg2
import pandas as pd
import time
from pathlib import Path
import json

WD_STRING_TYPES = ['monolingualtext', 'string', 'external-id', 'url', 'commonsMedia', 'geo-shape', 'tabular-data', 'math', 'musical-notation', 'unknown-values']
WD_ENTITY_TYPES = ['wikibase-item', 'wikibase-entityid', 'wikibase-property', 'wikibase-lexeme', 'wikibase-sense', 'wikibase-form', 'entity-schema']

def query_to_df(query, connection):
    try:
        with connection.cursor() as cur:
            cur.execute(query)
            
            if cur.description is not None:
                # Get column names
                colnames = [desc[0] for desc in cur.description]
                # Fetch all rows
                rows = cur.fetchall()
                # Return as Poras DataFrame
                return pd.DataFrame(rows, columns=colnames)
            else:
                print('Query did not return any rows')
                return pd.DataFrame()
    except Exception as e:
        raise e
    
def clean_for_parquet(df):
    """
    Clean DataFrame to be compatible with Parquet format
    Store complex objects as JSON strings
    """
    import json
    
    # Columns that might have dict/struct values
    json_cols = ['old_value', 'new_value']
    
    for col in json_cols:
        if col in df.columns:
            def to_json_string(x):
                if pd.isna(x) or x is None:
                    return None
                # If already a string, keep it
                if isinstance(x, str):
                    return x
                # If dict/list/complex object, convert to JSON
                try:
                    return json.dumps(x)
                except:
                    # Fallback to string conversion
                    return str(x)
            
            df[col] = df[col].apply(to_json_string)
    
    return df

    
def query_to_df_chunked(query, conn, chunksize=50000, logging=None):
    """
    Execute query and return DataFrame using chunked reading
    to avoid memory issues
    """
    with conn.cursor() as temp_cur:
        temp_cur.execute("SET max_parallel_workers_per_gather = 0;")
        conn.commit() 
    
    import uuid
    cursor_name = f'fetch_cursor_{uuid.uuid4().hex[:8]}'
    cur = conn.cursor(name=cursor_name)
    
    try:
        cur.itersize = chunksize
        
        logging.info(f"Executing query...")
        cur.execute(query)
        
        # Fetch first batch to populate cur.description
        logging.info(f"Fetching first batch...")
        first_rows = cur.fetchmany(chunksize)
        
        if not first_rows:
            logging.info("Warning: No data returned from query")
            cur.close()
            return pd.DataFrame()
        
        
        # Get column names
        columns = [desc[0] for desc in cur.description]
        logging.info(f"Query executed successfully. Columns: {len(columns)}")
        
        # Fetch in chunks
        first_chunk = pd.DataFrame(first_rows, columns=columns)
        first_chunk = clean_for_parquet(first_chunk)
        chunks = [first_chunk]
        total_rows = len(first_rows)
        chunk_num = 1
        
        while True:
            rows = cur.fetchmany(chunksize)
            if not rows:
                break

            chunk_df = pd.DataFrame(rows, columns=columns)
            chunk_df = clean_for_parquet(chunk_df)  # Clean before appending -> json valuies
            chunks.append(chunk_df)
            
            chunk_num += 1
            total_rows += len(rows)
            logging.info(f"Fetched chunk {chunk_num}: {total_rows:,} rows total")
        
        logging.info(f"Combining {len(chunks)} chunks...")
        df = pd.concat(chunks, ignore_index=True)
        
        logging.info(f"Total rows fetched: {len(df):,}")
        return df
        
    except Exception as e:
        logging.error(f"Error during query execution: {e}")
        raise
    finally:
        cur.close()



def get_data_from_db(conn, params, logging=None):
    """
        params = {
            'sql_untagged': True/False,
            'only_updates': True/False,
            'no_rank': True/False,
            'datatype': 'string/entity/quantity/time/globecoordinate'
        }
    """
    start_time = time.time()
    logging.info('Creating indexes to speed up queries')
    index_vc = """ 
        CREATE INDEX IF NOT EXISTS idx_value_change_revision_id 
        ON value_change(revision_id);
    """

    index_vcm = """
        CREATE INDEX IF NOT EXISTS idx_value_change_metadata_revision_id 
        ON value_change_metadata(revision_id, property_id, value_id, change_target);
    """

    with conn.cursor() as cur:
        cur.execute(index_vc)
        cur.execute(index_vcm)
        conn.commit()

    logging.info(f'Created indexes in {time.time() - start_time} seconds')

    logging.info('\nGoing to extract data from db')
    start_time = time.time()
    query = """
        SELECT 
            c.revision_id,
            r.entity_id,
            r.entity_label,
            c.property_id,
            c.value_id,
            c.property_label,
            c.old_value,
            c.old_value_label,
            c.new_value,
            c.new_value_label,
            c.datatype,
            c.change_target,
            c.action,
            c.target,
            c.old_hash,
            c.new_hash,
            r.timestamp,
            CASE
                WHEN username ILIKE '%bot%' THEN 'bot'
                WHEN user_id = '' and username = '' THEN 'anonymous'
                ELSE 'human'
            END AS user_type,
            r.username,
            r.user_id,
            r.comment,
            COUNT(*) OVER (PARTITION BY c.revision_id) as num_changes_in_revision,
            EXTRACT(EPOCH FROM (
                r.timestamp - MIN(r.timestamp) OVER (PARTITION BY r.entity_id)
            )) / 86400.0 as entity_age_days,
            CASE 
                WHEN cm.value IS NULL THEN 10000.0
                ELSE cm.value
            END AS change_magnitude
        FROM 
            revision r 
            JOIN value_change c ON c.revision_id = r.revision_id
            LEFT JOIN value_change_metadata cm 
                ON c.revision_id = cm.revision_id 
                AND c.property_id = cm.property_id 
                AND c.value_id = cm.value_id 
                AND c.change_target = cm.change_target
    """

    if 'sql_untagged' in params and params['sql_untagged']:
        query += """
        WHERE NOT 
            (typo OR value_refinement OR formatting OR reverted_edit OR reversion OR value_unrefinement OR link_fix OR property_replacement)
        """

    if 'only_updates' in params and params['only_updates']:
        query += """
        AND c.action = 'UPDATE'
        """

    if 'no_rank' in params and params['no_rank']:
        query += """
        AND c.change_target != 'rank'
        """
    
    if 'datatype' in params:
        if params['datatype'] == 'string':
            query += f"""
            AND c.datatype IN ({', '.join(["'%s'" % dt for dt in WD_STRING_TYPES])})
            """
        elif params['datatype'] == 'entity':
            query += f"""
            AND c.datatype IN ({', '.join(["'%s'" % dt for dt in WD_ENTITY_TYPES])})
            """
        else:
            query += f"""
            AND c.datatype = '{params['datatype']}'
            """
    
    if params['datatype'] == 'globecoordinate':
        logging.info(f"FULL QUERY:\n{query}")

    df = query_to_df_chunked(query, conn, chunksize=50000, logging=logging)

    os.mkdir('data') if not os.path.exists('data') else None

    if len(df) > 0:
        # TODO: use the config class
        base_file_path = "data/changes_for_clustering"
        if 'datatype' in params:
            base_file_path += f"_{params['datatype']}"
        if 'only_updates' in params and params['only_updates']:
            base_file_path += "_update"

        df.to_parquet(base_file_path + ".parquet", compression='snappy')
        logging.info(f'Saved {len(df):,} rows to {base_file_path}.parquet')
    else:
        logging.info('No data to save!')
    logging.info(f'Extracted data from db in {time.time() - start_time} seconds')
    return df


def get_data_to_cluster(params, logging=None):
    """
    Get data from DB and save to parquet for clustering
    """
    root_dir = Path(__file__).parent.parent

    config_path = root_dir / "config" / "db_config.json"

    with open(config_path, "r") as f:
        config = json.load(f)

    logging.info('Connecting to database...')

    conn = psycopg2.connect(
        dbname=config['db_params']['dbname'],
        user=config['db_params']['user'],
        password=config['db_params']['password'],
        host=config['db_params']['host'],
        port=config['db_params']['port']
    )

    logging.info('Connected to database.')
    df = get_data_from_db(conn, params, logging=logging)

    conn.close()
    return df



    