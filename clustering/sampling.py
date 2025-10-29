import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
import os
import psycopg2

def stratified_sample(df, n_samples=50000):
    """
    Sample in a way that preserves diversity
    """
    # Stratify by important categorical variables
    strata_cols = ['user_type', 'datatype', 'action']
    
    # Calculate samples per stratum proportionally
    samples = []
    for name, group in df.groupby(strata_cols):
        # Sample proportionally, but ensure at least some from each stratum
        n_stratum = max(10, int(n_samples * len(group) / len(df)))
        if len(group) <= n_stratum:
            samples.append(group)
        else:
            samples.append(group.sample(n=n_stratum, random_state=42))
    
    return pd.concat(samples).sample(n=min(n_samples, len(pd.concat(samples))), random_state=42)

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
    
if "__main__":

    dotenv_path = Path().resolve().parent.parent / ".env"
    load_dotenv(dotenv_path, override=True)

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


    query = """
        SELECT 
    """

    df = query_to_df(query, conn)

    df_small = stratified_sample(df, n_samples=20000)

    df_small.to_csv('value_change_sample_20k.csv', index=False)