"""
Main pipeline for running classification and evaluation.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any
import yaml

from src.classifiers.ml.ml_classifier import MLClassifier
from src.classifiers.llm.llm_classifier import LLMClassifier
from src.sql_runner.sql_runner import SQLRunner
from src.utils.const import YAML_SETUP_PATH


class ClassificationPipeline:
    """
    Main pipeline for orchestrating classification and evaluation tasks.
    
    This class provides a clean interface for:
    1. Initializing a classifier (ML or LLM)
    2. Running classification
    3. Evaluating results

    """
    
    def __init__(
        self, 
    ):
        """
        Initialize the classification pipeline.

        """

        with open(YAML_SETUP_PATH, 'r') as f:
            self.set_up = yaml.safe_load(f)

        self.classifier_type = self.set_up['classification']['classifier_type'].lower()

        self._setup_logging(f'pipeline_{self.classifier_type}.log')
        
        # Initialize classifier
        self._initialize_classifier()
        
        self.logger.info(f"Pipeline initialized with {self.classifier_type} classifier")
    
    
    def _setup_logging(self, log_file_name='pipeline.log'):
        """Setup logging configuration."""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_dir / log_file_name),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _initialize_classifier(self):
        """Initialize the appropriate classifier based on type."""
        if self.classifier_type == 'ml':
            
            config_path = self.set_up['config']['ml_config_path']
            self.classifier = MLClassifier(config_path=config_path)
            
        elif self.classifier_type == 'llm':
        
            config_path = self.set_up['config']['llm_config_path']
            self.classifier = LLMClassifier(config_path=config_path)
        
        else:
            raise ValueError(
                f"Unknown classifier type: {self.classifier_type}. "
                f"Must be 'llm', or 'ml'"
            )
    
    # ========== Classification ==========
    def run_classification(self, datatype, table_prefix=None, max_batches=None):
        """
        Run classification on new changes with the trained ML model.
        """
        if self.classifier_type == 'ml':
           
            start_time = time.time()

            db_config_path = self.set_up['config']['database_config_path']
            self.classifier.classify_changes(datatype, table_prefix, max_batches=max_batches, db_config_path=db_config_path)
            
            elapsed = time.time() - start_time
            self.logger.info(f"Classification completed in {elapsed:.2f}s")
        else: # llm 
            self.classifier.classify_changes(datatype)
    
    
    # ========== Training ==========
    def train(self):
        """
        Train ML classifier.
        Only applicable for ML classifiers.
        """
        if self.classifier_type != 'ml':
            self.logger.warning(
                f"Training not needed for {self.classifier_type} classifier"
            )
            return
        
        start_time = time.time()
        self.logger.info("Started training ML classifier")
        
        self.classifier.train_classifier()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Training completed in {elapsed:.2f}s")
    
    # ========== Evaluation ==========
    def evaluate(self) -> Dict[str, Any]:
        """
        Evaluate classifier performance.
            
        Returns:
            Dictionary containing evaluation metrics
        """
        start_time = time.time()
        self.logger.info("Evaluating classifier performance.")
        
        metrics = self.classifier.evaluate()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Evaluation completed in {elapsed:.2f}s")
        
        return metrics
    
    
    
