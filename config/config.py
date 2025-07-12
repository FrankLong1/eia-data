"""Configuration settings for EIA data pipeline."""

import os
from datetime import datetime

# API Settings
EIA_API_BASE_URL = "https://api.eia.gov/v2/"
EIA_API_KEY = os.getenv("EIA_API_KEY", "")  # Set your EIA API key as environment variable

# Balancing Authorities
BALANCING_AUTHORITIES = [
    "PJM", "MISO", "ERCO", "SWPP", "SOCO", "CISO", "ISNE", "NYIS",
    "DUK", "CPLE", "FPC", "TVA", "BPAT", "AZPS", "FPL", "PACE",
    "PACW", "PGE", "PSCO", "SRP", "SCEG", "SC"
]

# Date Range
START_DATE = "2016-01-01"
END_DATE = "2024-12-31"

# Data Paths
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
RAW_DATA_DIR = os.path.join(DATA_DIR, "raw")
CLEANED_DATA_DIR = os.path.join(DATA_DIR, "cleaned")
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, "processed")
RESULTS_DIR = os.path.join(DATA_DIR, "results")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

# Data Cleaning Parameters (from Appendix B)
CLEANING_PARAMS = {
    "remove_duplicates": True,
    "handle_missing": "interpolate",  # Options: 'interpolate', 'forward_fill', 'drop'
    "outlier_method": "iqr",  # Options: 'iqr', 'zscore'
    "outlier_threshold": 3,  # For zscore method
    "iqr_multiplier": 1.5,  # For IQR method
    "min_data_completeness": 0.95,  # Minimum required data completeness
}

# Curtailment Analysis Parameters
CURTAILMENT_PARAMS = {
    "percentile_threshold": 95,  # 95th percentile for peak load
    "rolling_window_hours": 24,  # Rolling window for smoothing
    "min_headroom_mw": 0,  # Minimum headroom to consider
}

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Output Formats
OUTPUT_FORMATS = ["csv", "parquet"]  # Supported output formats

# Create directories if they don't exist
for directory in [RAW_DATA_DIR, CLEANED_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, OUTPUT_DIR]:
    os.makedirs(directory, exist_ok=True)