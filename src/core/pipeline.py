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
    5. Generating reports
    
    Example usage:
        # For training ML classifier
        pipeline = ClassificationPipeline(classifier_type='ml', config_path='config/db_config.json')
        pipeline.load_training_data()
        pipeline.train()
        
        # For running SQL baseline classification
        pipeline = ClassificationPipeline(classifier_type='sql', config_path='config/db_config.json')
        pipeline.run_classification()
        pipeline.evaluate()

    """
    
    def __init__(
        self, 
        classifier_type: str,
        db_config_path: str
    ):
        """
        Initialize the classification pipeline.
        
        Args:
            classifier_type: Type of classifier to use ('sql', 'baseline', or 'ml')
            config_path: Path to database configuration file
            models_config_path: Path to ML models configuration (only needed for ML)
        """
        self.classifier_type = classifier_type.lower()

        # Setup logging
        self._setup_logging()
        
        # Initialize classifier
        self._initialize_classifier()
        
        # TODO: uncomment
        # # Initialize data loader
        # self.data_loader = DataLoader(db_config_path=db_config_path)
        
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
            self.classifier = MLClassifier(config_path=config_path, classifier_type='ml')
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
        Load gold standard datasets for evaluation.
        
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
    def run_classification(self, gold_standard: bool = False):
        """
        Run classification on the main dataset.
        
        Args:
            gold_standard: If True, runs on gold standard
        """
        start_time = time.time()
        
        if gold_standard:
            self.logger.info(f"Running {self.classifier_type} classification on gold standard")
        else:
            self.logger.info(f"Running {self.classifier_type} classification on main dataset")
        
        self.classifier.run_classification(gold_standard=gold_standard)
        
        elapsed = time.time() - start_time
        self.logger.info(f"Classification completed in {elapsed:.2f}s")
    
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
        self.logger.info("Training ML classifier...")
        
        self.classifier.train_classifier()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Training completed in {elapsed:.2f}s")
    
    # ========== Evaluation ==========
    
    def evaluate(self, gold_standard: bool = False) -> Dict[str, Any]:
        """
        Evaluate classifier performance.
            
        Returns:
            Dictionary containing evaluation metrics
        """
        start_time = time.time()
        self.logger.info("Evaluating classifier performance.")
        
        if gold_standard:
            metrics = self.evaluate_on_gold_standard()
        else:
            metrics = self.evaluate_on_main_dataset()
        
        elapsed = time.time() - start_time
        self.logger.info(f"Evaluation completed in {elapsed:.2f}s")
        
        return metrics
    
    
    def run_full_pipeline(
        self,
        train_ml: bool = False,
        classify: bool = True,
        evaluate: bool = True
    ):
        """
        Run the complete pipeline from start to finish.
        
        Args:
            train_ml: Whether to train ML classifier (only for ML type)
            classify: Whether to run classification
            evaluate: Whether to evaluate results
        """
        self.logger.info("=" * 60)
        self.logger.info("STARTING PIPELINE")
        self.logger.info("=" * 60)
        
        pipeline_start = time.time()
        
        try:
            # Step 1: Train if needed
            if train_ml and self.classifier_type == 'ml':
                self.train()
            
            # Step 2: Classify
            if classify:
                self.run_classification()
            
            # Step 3: Evaluate
            if evaluate:
                self.evaluate(gold_standard=True)
            
            total_elapsed = time.time() - pipeline_start
            self.logger.info("=" * 60)
            self.logger.info(f"PIPELINE COMPLETED SUCCESSFULLY in {total_elapsed:.2f}s")
            self.logger.info("=" * 60)
            
        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            raise
    
