from src.classifier import ClassificationManager
import psycopg2
from dotenv import load_dotenv
import os
from old_scritps.aux import update_value_change_entity_labels


if __name__ == "__main__":

    dotenv_path = ".env"
    load_dotenv(dotenv_path)

    # credentials for DB connection
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

    update_value_change_entity_labels(conn, 'value_change_sample_30')

    conn.close()

    manager = ClassificationManager('SQL')
    manager.run_classifier() 