"""
Constants for data cleaning operations.

This module contains all configuration values and thresholds used in the data cleaning pipeline.
"""

from dataclasses import dataclass
from typing import Dict, List


# Data validation limits
MAX_REASONABLE_DEMAND_GW = 200  # Maximum reasonable demand for any single BA (GW)
MIN_REASONABLE_DEMAND_MW = 0    # Minimum reasonable demand (MW)

# Outlier detection thresholds
LOW_OUTLIER_THRESHOLD_FACTOR = 0.1      # Values below 10% of BA mean considered low outliers
SPIKE_THRESHOLD_FACTOR = 3.0            # Values beyond 3 std devs considered spikes
PEAK_THRESHOLD_FACTOR = 2.0             # Values above 2x BA max considered erroneous peaks

# Rolling window parameters
DEFAULT_SPIKE_WINDOW_SIZE = 3           # Window size for spike detection
DEFAULT_INTERPOLATION_LIMIT = None      # No limit on interpolation distance

# API and processing limits
DEFAULT_TIME_BETWEEN_REQUESTS = 0.0     # Seconds between API requests
DEFAULT_API_BATCH_SIZE = 5000           # Records per API request
MAX_API_RETRIES = 3                     # Maximum API retry attempts

# Statistical method options
OUTLIER_DETECTION_METHODS = {
    'iqr_extreme': 'Interquartile Range with extreme bounds',
    'mad': 'Median Absolute Deviation',  
    'zscore': 'Standard Z-score'
}

# Balancing Authority label mappings (moved from BAAggregateCleaner.py)
BA_LABEL_MAPPING = {
    "CPLE": "DEP", 
    "DUK": "DEC", 
    "SC": "SCP", 
    "SWPP": "SPP",
    "SCEG": "DESC", 
    "FPC": "DEF", 
    "CISO": "CAISO", 
    "BPAT": "BPA",
    "NYIS": "NYISO", 
    "ERCO": "ERCOT", 
    "ISNE": "ISO-NE"
}


@dataclass
class CleaningConfig:
    """Configuration for data cleaning operations."""
    
    # Outlier detection parameters
    low_outlier_threshold: float = LOW_OUTLIER_THRESHOLD_FACTOR
    spike_threshold: float = SPIKE_THRESHOLD_FACTOR
    peak_threshold: float = PEAK_THRESHOLD_FACTOR
    
    # Window and processing parameters  
    spike_window_size: int = DEFAULT_SPIKE_WINDOW_SIZE
    outlier_method: str = 'iqr_extreme'
    
    # Column names (configurable for different datasets)
    datetime_col: str = 'Timestamp'
    demand_col_primary: str = 'Demand'
    adj_demand_col: str = 'Adjusted demand'
    ba_col: str = 'Balancing Authority'
    
    # Processing options
    interpolate_zeros: bool = True
    remove_low_outliers: bool = True
    correct_spikes: bool = True
    handle_peaks: bool = True
    
    def __post_init__(self):
        """Validate configuration parameters."""
        if self.outlier_method not in OUTLIER_DETECTION_METHODS:
            raise ValueError(f"Invalid outlier method: {self.outlier_method}")
        
        if self.low_outlier_threshold <= 0 or self.low_outlier_threshold >= 1:
            raise ValueError("Low outlier threshold must be between 0 and 1")
            
        if self.spike_threshold <= 0:
            raise ValueError("Spike threshold must be positive")


# Error messages
ERROR_MESSAGES = {
    'missing_demand_col': "Demand column '{col}' not found for {operation}. Skipping.",
    'missing_ba_col': "BA column '{col}' not found for {operation}. Applying global correction.",
    'missing_datetime_col': "Datetime column '{col}' not found for {operation}. Skipping.",
    'insufficient_data': "Insufficient data points ({count}) for {operation} in BA {ba}",
    'interpolation_failed': "Failed to interpolate missing values in column '{col}'",
    'outlier_detection_failed': "Outlier detection failed for BA {ba}: {error}"
}

# Logging messages
LOG_MESSAGES = {
    'normalized_datetime': "Normalized datetime column: {col}",
    'created_unified_demand': "Created Unified Demand column",
    'mapped_ba_labels': "Mapped BA labels in column: {col}",
    'filled_missing_values': "Filled {count} missing/zero values via interpolation",
    'imputed_outliers': "Imputed {count} low outliers",
    'smoothed_spikes': "Smoothed {count} demand spikes", 
    'removed_peaks': "Removed {count} extreme peaks",
    'processing_complete': "Data cleaning complete for {ba_count} BAs, {record_count} records"
}