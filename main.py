from src.core.pipeline import ClassificationPipeline


if __name__ == "__main__":

    pipeline = ClassificationPipeline(classifier_type='ml', db_config_path='src/config/db_config.json')
    pipeline.train()

