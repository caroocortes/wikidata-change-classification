import psycopg2
import pandas as pd

class SQLRunner:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)

    def execute_query(self, query, params=None):
        try:
            with self.conn.cursor() as cur:
                cur.execute(query, params)
                affected_rows = cur.rowcount 

                if cur.description: 
                    result = cur.fetchall()
                    return result
                else:
                    self.conn.commit()
                    return affected_rows  
        except Exception as e:
            print('There was an error when trying to execute the query.')
            raise e
    
    def query_to_df(self, query):
        try:
            with self.conn.cursor() as cur:
                cur.execute(query)
                
                if cur.description is not None:
                    # Get column names
                    colnames = [desc[0] for desc in cur.description]
                    # Fetch all rows
                    rows = cur.fetchall()
                    # Return as Pandas DataFrame
                    return pd.DataFrame(rows, columns=colnames)
                else:
                    print('Query did not return any rows')
                    return pd.DataFrame()
        except Exception as e:
            raise e
        
    def execute_many(self, query, values):
        try:
            with self.conn.cursor() as cur:
                cur.executemany(query, values)
            self.conn.commit()
        except Exception as e:
            print('There was an error when trying to execute the query.')
            raise e

    def __del__(self):
        self.conn.close()