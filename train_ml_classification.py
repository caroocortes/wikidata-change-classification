from src.core.pipeline import ClassificationPipeline


if __name__ == "__main__":

    pipeline = ClassificationPipeline(classifier_type='ml')
    pipeline.train()
    pipeline.evaluate()


