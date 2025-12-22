from src.classifier.classification_manager import ClassificationManager


if __name__ == "__main__":

    # manager = ClassificationManager('SQL')
    # manager.evaluate_on_gold_standard()
    # manager.calculate_evaluation_metrics()

    manager = ClassificationManager('ML')
    manager.train_classifier()
    # manager.calculate_evaluation_metrics()
