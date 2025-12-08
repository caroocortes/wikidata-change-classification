from src.classifier.classification_manager import ClassificationManager
from dotenv import load_dotenv


if __name__ == "__main__":

    manager = ClassificationManager('SQL')
    # manager.evaluate_on_gold_standard()
    manager.calculate_evaluation_metrics()