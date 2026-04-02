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
    
    Attributes:
        config: Configuration dictionary
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the base classifier.
        
        Args:
            config: Configuration dictionary containing database settings
        """
   
        self.logger = logging.getLogger(self.__class__.__name__)

        with open(config_path, "r") as f:
            self.config = json.load(f)
    
    
    @abstractmethod
    def classify_changes(self):
        """
        Run the classification process.
        
        This is the main method that performs classification on the dataset.
        
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
