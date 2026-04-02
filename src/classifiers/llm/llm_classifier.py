from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from openai import OpenAI
import pandas as pd
import time
import json
import os

from src.classifiers.base_classifier import BaseClassifier
from src.utils.const import CLASSES_PER_DATATYPE, CLASSIFICATION_RESULTS, CLASS_DESCRIPTION, WD_ENTITY_TYPES, WD_STRING_TYPES

class LLMClassifier(BaseClassifier):
    def __init__(self, config_path: str):
        super().__init__(config_path=config_path)
        # from doc: https://huggingface.co/Qwen/Qwen3.5-35B-A3B-FP8
        self.base_url = self.config.get('base_url', '')
        self.api_key = self.config.get('api_key', 'EMPTY')

        self.llm_id = self.config.get('llm_id', '')
        
        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

        self.temperature = self.config.get('temperature', 0)
        self.max_tokens = self.config.get('max_tokens', 2048)

    @staticmethod
    def build_context(datatype):
        class_description = '\n'.join([f"- {CLASS_DESCRIPTION[datatype][label]}" for label in CLASSES_PER_DATATYPE[datatype]])
        context = f'''
        You are an experienced editor of Wikidata, the free and open knowledge base.
        You are given a change made to an entity on Wikidata, and your task is to classify the change into one of the following classes: {CLASSES_PER_DATATYPE[datatype]}.
        Classes description: \n 
        {class_description}
        The change is done between values of the datatype {datatype}.
        Note that a change can fall into more than one class.\n

        Return the classification of the change as one or more of the classes mentioned above, and only the classes, without any explanation.
        The result has to be in the format: class_1, class_2 if there are multiple classes, or class_1 if there is only one class.

        Next I will provide you with the details of each change, and I want you to classify it according to the instructions above.
        '''
        return context
    
    @staticmethod
    def build_content(data, datatype):
        content = f'''
        Change details: \n
        - Entity: {data['entity_label']} ({data['entity_id']}) \n
        - Property: {data['property_label']} ({data['property_id']}) \n
        - Old Value: {data['old_value']} {f"({data['old_value_label']})" if datatype == 'entity' else ''} \n
        - New Value: {data['new_value']} {f"({data['new_value_label']})" if datatype == 'entity' else ''} \n
        '''
        return content

    def classify(self, change, context, datatype):
        """ 
            Sends request to classify a single change to the LLM and returns the predicted class.
        """

        prompt = [
            {"role": "system", 
            "content": context}, 
            {'role': 'user',
            'content': LLMClassifier.build_content(change, datatype)}
        ]
        try:

            # Instruct (or non-thinking) mode for general tasks:
            # temperature=0.7, top_p=0.8, top_k=20, min_p=0.0, presence_penalty=1.5, repetition_penalty=1.0

            response = self.client.chat.completions.create(
                model=self.llm_id,
                messages=prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=0.8,
                extra_body={
                    "top_k": 20,
                    "chat_template_kwargs": {"enable_thinking": False}
                }
            )
            result = response.choices[0].message.content.strip()
            return result
        
        except Exception as e:
            print(f"Error making request: {e}")
            return ''

    def classify_changes(self, datatype):
        
        if datatype == 'globecoordinate_latitude' or datatype == 'globecoordinate_longitude':
            gs_path = 'gold_standard/gold_standard_globecoordinate.csv'
        else:             
            gs_path = 'gold_standard/gold_standard.csv'
        
        df = pd.read_csv(gs_path)

        if datatype == 'entity':
            df = df[df['datatype'].isin(WD_ENTITY_TYPES)]
        elif datatype == 'text':
            df = df[df['datatype'].isin(WD_STRING_TYPES)]
        elif datatype == 'globecoordinate_latitude' or datatype == 'globecoordinate_longitude':
            df = df[df['datatype'] == 'globecoordinate']
        else:
            df = df[df['datatype'] == datatype]

        t0 = time.time()

        context = LLMClassifier.build_context(datatype)

        if datatype == 'globecoordinate_latitude':
            df['predicted_class_latitude'] = df.apply(lambda row: self.classify(row, context, datatype), axis=1, result_type='reduce').astype(str)
        elif datatype == 'globecoordinate_longitude':
            df['predicted_class_longitude'] = df.apply(lambda row: self.classify(row, context, datatype), axis=1, result_type='reduce').astype(str)
        else:
            df['predicted_class'] = df.apply(lambda row: self.classify(row, context, datatype), axis=1, result_type='reduce').astype(str)
        t1 = time.time()
        print(f"Classification for datatype {datatype} completed in {t1-t0:.2f} seconds")

        os.makedirs(CLASSIFICATION_RESULTS, exist_ok=True)
        if len(df) > 0:
            df.to_csv(f'{CLASSIFICATION_RESULTS}/llm_classification_{datatype}.csv', index=False)

        runtime = t1 - t0
        self.logger.info(f"LLM classification for datatype {datatype} completed in {runtime:.2f} seconds, affected {len(df)} changes. Results saved to {CLASSIFICATION_RESULTS}/llm_classification_{datatype}.csv\n")

        with open(f'{CLASSIFICATION_RESULTS}/llm_classification_runtime.txt', 'a') as f:
            f.write(f"LLM classification for datatype {datatype} completed in {runtime:.2f} seconds, affected {len(df)} changes.\n")

    def evaluate(self):
        results = {'llm': {datatype: {} for datatype in CLASSES_PER_DATATYPE.keys()}}
        datatypes = CLASSES_PER_DATATYPE.keys()
        for datatype in datatypes:
            if os.path.exists(f'{CLASSIFICATION_RESULTS}/llm_classification_{datatype}.csv'):
                df = pd.read_csv(f'{CLASSIFICATION_RESULTS}/llm_classification_{datatype}.csv')

                def parse_labels(val):
                    if pd.isna(val) or str(val).strip() == '':
                        return []
                    return [l.strip() for l in str(val).split(',')]

                if datatype == 'globecoordinate_latitude':
                    df['labels_list'] = df['label_latitude'].apply(parse_labels)
                    df['predicted_class_list'] = df['predicted_class_latitude'].apply(parse_labels)
                elif datatype == 'globecoordinate_longitude':
                    df['labels_list'] = df['label_longitude'].apply(parse_labels)
                    df['predicted_class_list'] = df['predicted_class_longitude'].apply(parse_labels)
                else:
                    df['labels_list'] = df['label'].apply(parse_labels)
                    df['predicted_class_list'] = df['predicted_class'].apply(parse_labels)

                label_binarizer = MultiLabelBinarizer()
                y_true_binary = label_binarizer.fit_transform(df['labels_list'])
                y_pred_binary = label_binarizer.transform(df['predicted_class_list'])
                
                for i, label in enumerate(label_binarizer.classes_):
                    y_true = y_true_binary[:, i]
                    y_pred = y_pred_binary[:, i]

                    accuracy = accuracy_score(y_true, y_pred)
                    precision = precision_score(y_true, y_pred, zero_division=0)
                    recall = recall_score(y_true, y_pred, zero_division=0)
                    f1 = f1_score(y_true, y_pred, zero_division=0)

                    results['llm'][datatype][label] = {
                        'precision': precision,
                        'recall': recall,
                        'accuracy': accuracy,
                        'f1': f1
                    }

        with open(f'{CLASSIFICATION_RESULTS}/llm_classification.json', 'w') as f:
            json.dump(results, f, indent=4)
    
        return results
