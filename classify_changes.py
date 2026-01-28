from src.core.pipeline import ClassificationPipeline


if __name__ == "__main__":

    pipeline = ClassificationPipeline(classifier_type='ml', db_config_path='src/config/db_config_cluster.json')
    
    datatype = 'text'
    table_prefix = ''
    max_batches = 2

    pipeline.run_classification(datatype, table_prefix, max_batches=max_batches)


