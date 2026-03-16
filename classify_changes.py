import json
from src.core.pipeline import ClassificationPipeline


if __name__ == "__main__":

    pipeline = ClassificationPipeline(classifier_type='ml', db_config_path='src/config/db_config_cluster.json')
    
    with open('src/config/db_config_cluster.json', 'r') as f:
        db_config = json.load(f)
    
    table_prefix = ''
    max_batches = None

    datatypes = ['globecoordinate_latitude', 'globecoordinate_longitude', 'time', 'quantity', 'entity', 'text']
    for datatype in datatypes:
        pipeline.run_classification(datatype, table_prefix, max_batches=max_batches, db_config=db_config['db_params'])


