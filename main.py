from src.pipeline import ClassificationPipeline


if __name__ == "__main__":

    pipeline = ClassificationPipeline()
    # if pipeline.classifier_type == 'ml':
    #     pipeline.train()
    #     pipeline.evaluate()

    datatypes = ['quantity', 'time', 'globecoordinate_latitude', 'globecoordinate_longitude', 'text', 'entity']
    for datatype in datatypes:
        if pipeline.classifier_type == 'ml':
            table_prefix = ''
            max_batches = None
            pipeline.run_classification(datatype, table_prefix, max_batches=max_batches)
        else: # llm
            pipeline.run_classification(datatype)
            pipeline.evaluate()