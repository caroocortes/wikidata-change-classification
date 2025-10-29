from classifier import Classifier

class MLClassifier(Classifier):
    def __init__(self, config):

        self.table_names = config['table_names']
    
    def run_classification(self):
        print('TODO')