from src.classifier import ClassificationManager
import psycopg2
from dotenv import load_dotenv
import os


if __name__ == "__main__":

    manager = ClassificationManager('SQL')
    manager.run_classifier() 