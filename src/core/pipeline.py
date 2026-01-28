"""
Main pipeline for running classification and evaluation.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any

from src.classifiers.baseline.baseline_classifier import BaselineClassifier
from src.classifiers.ml.ml_classifier import MLClassifier
from src.data.loader import DataLoader
from src.utils.const import CONFIG_DIR


class ClassificationPipeline:
    """
    Main pipeline for orchestrating classification and evaluation tasks.
    
    This class provides a clean interface for:
    1. Initializing a classifier (SQL baseline or ML)
    2. Loading necessary data (full dataset or gold standard)
    3. Running classification
    4. Evaluating results

    """
    
    def __init__(
        self, 
        classifier_type: str,
        db_config_path=None
    ):
        """
        Initialize the classification pipeline.
        
        Args:
            classifier_type: Type of classifier to use ('sql', 'baseline', or 'ml')
            config_path: Path to database configuration file
            models_config_path: Path to ML models configuration (only needed for ML)
        """
        self.classifier_type = classifier_type.lower()

        self._setup_logging()

        self.data_loader = None
        if db_config_path:
            self.data_loader = DataLoader(db_config_path=db_config_path)
        
        # Initialize classifier
        self._initialize_classifier()
        
        self.logger.info(f"Pipeline initialized with {self.classifier_type} classifier")
    
    
    def _setup_logging(self):
        """Setup logging configuration."""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'pipeline.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _initialize_classifier(self):
        """Initialize the appropriate classifier based on type."""
        if self.classifier_type == 'ml':
            
            config_path = f'{CONFIG_DIR}/ml_classifier_config.json'
            conn = None
            if self.data_loader:
                conn = self.data_loader.sql_runner.get_connection()
            self.classifier = MLClassifier(config_path=config_path, classifier_type='ml',connection=conn)

        elif self.classifier_type == 'baseline':
            
            config_path = f'{CONFIG_DIR}/baseline_classifier_config.json'
            db_config_path = f'{CONFIG_DIR}/db_config.json'
            self.classifier = BaselineClassifier(db_config_path=db_config_path, config_path=config_path, classifier_type='baseline')
        
        else:
            raise ValueError(
                f"Unknown classifier type: {self.classifier_type}. "
                f"Must be 'sql', 'baseline', or 'ml'"
            )
    
    # ========== Data Loading ==========
    def load_gold_standard(self):
        """
        Load gold standard datasets to DB.
        
        This loads:
        - Main gold standard dataset
        - Reverted edits dataset
        - Property replacement dataset
        """
        start_time = time.time()
        self.logger.info("Loading gold standard datasets")
        
        self.data_loader.load_gold_standard()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Gold standard loaded successfully in {elapsed:.2f}s")

    
    # ========== Classification ==========
    def run_classification(self, datatype, table_prefix, max_batches=None):
        """
        Run classification on new changes with the trained ML model.
        """
        start_time = time.time()
        
        self.classifier.classify_in_batches(datatype, table_prefix, max_batches=max_batches)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Classification completed in {elapsed:.2f}s")
    
    
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
    
    
    
