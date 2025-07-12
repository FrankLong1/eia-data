"""
Configuration settings for EIA curtailment analysis project.
Based on "Rethinking Demand-Side Load Growth" (Norris et al., 2025)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
EIA_API_KEY = os.getenv('EIA_API_KEY')
if not EIA_API_KEY or EIA_API_KEY == 'your_api_key_here':
    print("Warning: EIA_API_KEY not configured. Please set your API key in the .env file.")
    print("Get a free API key from: https://www.eia.gov/opendata/register.php")
    EIA_API_KEY = None

# Project directories
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
RESULTS_DIR = DATA_DIR / "results"

# Create directories if they don't exist
for directory in [RAW_DATA_DIR, CLEANED_DATA_DIR, RESULTS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Balancing Authorities (22 from the paper)
# RTOs/ISOs
BALANCING_AUTHORITIES = [
    'PJM',    # PJM Interconnection
    'MISO',   # Midcontinent ISO
    'ERCO',   # ERCOT (Texas)
    'SWPP',   # Southwest Power Pool
    'CISO',   # California ISO
    'ISNE',   # ISO New England
    'NYIS',   # New York ISO
    # Utilities
    'SOCO',   # Southern Company
    'DUK',    # Duke Energy Carolinas
    'CPLE',   # Duke Energy Progress
    'FPC',    # Duke Energy Florida
    'TVA',    # Tennessee Valley Authority
    'BPAT',   # Bonneville Power Administration
    'AZPS',   # Arizona Public Service
    'FPL',    # Florida Power & Light
    'PACE',   # PacifiCorp East
    'PACW',   # PacifiCorp West
    'PGE',    # Portland General Electric
    'PSCO',   # Public Service Company of Colorado
    'SRP',    # Salt River Project
    'SCEG',   # Dominion Energy South Carolina
    'SC',     # South Carolina Public Service Authority
]

# BA label mapping for consistency with paper
BA_LABEL_MAPPING = {
    'ERCO': 'ERCOT',
    'SWPP': 'SPP',
    'CISO': 'CAISO',
    'ISNE': 'ISO-NE',
    'NYIS': 'NYISO',
    'DUK': 'DEC',
    'CPLE': 'DEP',
    'FPC': 'DEF',
    'BPAT': 'BPA',
    'SCEG': 'DESC',
    'SC': 'SCP'
}

# Curtailment rates for analysis (from paper)
CURTAILMENT_RATES = [0.0025, 0.005, 0.01, 0.05]  # 0.25%, 0.5%, 1%, 5%

# Default date ranges
DEFAULT_START_DATE = "2019-01-01"
DEFAULT_END_DATE = "2023-12-31"

# API rate limiting
API_DELAY_SECONDS = 0.1  # Delay between API requests
EIA_MAX_RECORDS_PER_REQUEST = 5000  # EIA-imposed maximum records per API request

# Data quality thresholds
MAX_MISSING_HOURS = 24  # Maximum consecutive missing hours to interpolate
OUTLIER_THRESHOLD_IQR = 3  # IQR multiplier for outlier detection

# Visualization settings
FIGURE_DPI = 150
FIGURE_SIZE = (12, 8)
PLOT_STYLE = 'seaborn-v0_8-darkgrid'

# Analysis output formats
SAVE_FORMATS = ['png', 'pdf']  # Formats to save plots in
SAVE_CSV = True  # Whether to save analysis results as CSV

# Logging configuration
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'