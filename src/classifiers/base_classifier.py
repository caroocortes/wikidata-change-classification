"""
Base classifier interface.

All classifiers (SQL baseline, ML) inherit from this abstract base class
to ensure consistent interface across different classification approaches.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import json
import logging

class BaseClassifier(ABC):
    """
    Abstract base class for all classifiers.
    
    This defines the interface that all classifiers must implement
    
    Attributes:
        config: Configuration dictionary
        sql_runner: Database connection handler
        table_names: Dictionary of table names from config
        classifier_type: Type of classifier (sql, ml, baseline)
    """
    
    def __init__(self, config_path: str, classifier_type: str = "base"):
        """
        Initialize the base classifier.
        
        Args:
            config: Configuration dictionary containing database settings
            classifier_type: Type of classifier (e.g., 'sql', 'ml', 'baseline')
        """
   
        self.classifier_type = classifier_type.lower()
        self.logger = logging.getLogger(self.__class__.__name__)

        with open(config_path, "r") as f:
            self.config = json.load(f)
    
    
    @abstractmethod
    def run_classification(self, gold_standard: bool = False):
        """
        Run the classification process.
        
        This is the main method that performs classification on the dataset.
        
        Args:
            gold_standard: If True, run on gold standard for evaluation
                           If False, run on main dataset
        """
        pass
    
    @abstractmethod
    def evaluate(self) -> Dict[str, Any]:
        """
        Calculate evaluation metrics for the classifier.
        
        Returns:
            Dictionary containing evaluation metrics
        """
        pass
