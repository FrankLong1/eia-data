"""Configuration settings for EIA data pipeline."""

import os
from datetime import datetime
from pathlib import Path

# Project directories
PROJECT_ROOT = Path(__file__).parent.parent

# API Settings
EIA_API_BASE_URL = "https://api.eia.gov/v2/"
EIA_API_KEY = os.getenv("EIA_API_KEY", "")  # Set your EIA API key as environment variable

# Balancing Authorities
BALANCING_AUTHORITIES = [
    "PJM", "MISO", "ERCOT", "SPP", "SOCO", "CAISO", "ISO-NE", "NYISO",
    "DEC", "DEP", "DEF", "TVA", "BPA", "AZPS", "FPL", "PACE",
    "PACW", "PGE", "PSCO", "SRP", "DESC", "SCP"
]

# Date Range
START_DATE = "2016-01-01"
END_DATE = "2024-12-31"
DEFAULT_START_DATE = "2019-01-01"
DEFAULT_END_DATE = "2023-12-31"

# Data Paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
RESULTS_DIR = DATA_DIR / "results"
OUTPUT_DIR = DATA_DIR / "output"

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

# Curtailment rates for analysis (from paper)
CURTAILMENT_RATES = [0.0025, 0.005, 0.01, 0.05]  # 0.25%, 0.5%, 1%, 5%

# API rate limiting
API_DELAY_SECONDS = 0.1  # Delay between API requests

# Data quality thresholds
MAX_MISSING_HOURS = 24  # Maximum consecutive missing hours to interpolate
OUTLIER_THRESHOLD_IQR = 3  # IQR multiplier for outlier detection

# Logging
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Output Formats
OUTPUT_FORMATS = ["csv", "parquet"]  # Supported output formats
SAVE_FORMATS = ['png', 'pdf']  # Formats to save plots in
SAVE_CSV = True  # Whether to save analysis results as CSV

# Visualization settings
FIGURE_DPI = 150
FIGURE_SIZE = (12, 8)
PLOT_STYLE = 'seaborn-v0_8-darkgrid'

# Create directories if they don't exist
for directory in [RAW_DATA_DIR, CLEANED_DATA_DIR, PROCESSED_DATA_DIR, RESULTS_DIR, OUTPUT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)