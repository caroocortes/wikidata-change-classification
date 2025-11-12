import json
from datetime import datetime
from pathlib import Path

class ExperimentTracker:
    def __init__(self, experiments_dir='experiments'):
        self.experiments_dir = Path(experiments_dir)
        self.experiments_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.experiment_dir = self.experiments_dir / self.timestamp
        self.experiment_dir.mkdir(exist_ok=True)
        
    def log_params(self, params):
        """Log experiment parameters"""
        with open(self.experiment_dir / 'params.json', 'w') as f:
            json.dump(params, f, indent=2, default=str)
    
    def log_metrics(self, metrics):
        """Log experiment metrics"""
        with open(self.experiment_dir / 'metrics.json', 'w') as f:
            json.dump(metrics, f, indent=2)
    
    def save_results(self, df, name='results'):
        """Save results DataFrame"""
        df.to_parquet(self.experiment_dir / f'{name}.parquet', compression='snappy')
    
    def save_model(self, model, scaler, label_encoders):
        """Save model artifacts"""
        import pickle
        with open(self.experiment_dir / 'model.pkl', 'wb') as f:
            pickle.dump({'model': model, 'scaler': scaler, 'encoders': label_encoders}, f)
    
    def save_figure(self, fig, name):
        """Save matplotlib figure"""
        fig.savefig(self.experiment_dir / f'{name}.png', dpi=300, bbox_inches='tight')
    
    def save_text(self, text, name):
        """Save text output"""
        with open(self.experiment_dir / name, 'w') as f:
            f.write(text)
    
    def get_summary(self):
        """Get path to this experiment"""
        return str(self.experiment_dir)