import yaml
from src.pipeline import ClassificationPipeline


if __name__ == "__main__":

    with open('set_up.yml', 'r') as f:
        set_up = yaml.safe_load(f)

    classifier_type = set_up['classification']['classifier_type']
    
    pipeline = ClassificationPipeline()
    if classifier_type == 'ml':
        if set_up['classification_ml']['train']:
            pipeline.train()
        if set_up['classification_ml']['evaluate']:
            pipeline.evaluate()

    if classifier_type == 'llm' or (classifier_type == 'ml' and set_up['classification_ml']['classify']):
        datatypes = ['quantity', 'time', 'globecoordinate_latitude', 'globecoordinate_longitude', 'text', 'entity']
        for datatype in datatypes:
            if classifier_type == 'ml':
                table_prefix = set_up['classification_ml']['table_prefix']
                max_batches = set_up['classification_ml']['max_batches']
                pipeline.run_classification(datatype, table_prefix, max_batches=max_batches)
            else: # llm
                pipeline.run_classification(datatype)
                pipeline.evaluate()