from src.classifier.classification_manager import ClassificationManager
from dotenv import load_dotenv


if __name__ == "__main__":

    manager = ClassificationManager('SQL')
    manager.run_classifier() 