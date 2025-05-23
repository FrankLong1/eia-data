# EIA Data Pipeline

This project implements the data pipeline described in the paper "Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems" by Norris et al. (2025).

## Overview

The pipeline downloads and processes hourly electricity demand data from the U.S. Energy Information Administration (EIA) API for 22 major balancing authorities from 2016-2024. This data is used to analyze the potential for integrating large flexible loads (like data centers) into the US power grid.

## Project Structure

```
eia-data/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env                         # API key configuration (not in git)
├── .env.template               # Template for API key setup
├── .gitignore                  # Git ignore rules
│
├── config/                     # Configuration module
│   ├── __init__.py
│   └── config.py              # Central configuration settings
│
├── src/                        # Source code modules
│   ├── __init__.py
│   ├── utils.py               # Common utility functions
│   ├── data_fetching/         # Data fetching modules
│   │   ├── __init__.py
│   │   ├── download_eia_data.py  # Command-line download script
│   │   └── test_eia_api.py       # API testing and debugging
│   ├── data_processing/       # Data cleaning and processing (to be implemented)
│   │   └── __init__.py
│   ├── data_analysis/         # Analysis modules (to be implemented)
│   │   └── __init__.py
│   └── data_viz/              # Visualization modules (to be implemented)
│       └── __init__.py
│
└── data/                       # Data directory
    ├── raw/                    # Raw downloaded data
    ├── processed/              # Cleaned data (to be created)
    └── output/                 # Analysis results (to be created)
```

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get EIA API Key**
   - Register for a free API key at: https://www.eia.gov/opendata/register.php
   - Copy `.env.template` to `.env` and add your API key

3. **Test the Setup**
   ```bash
   # Quick test - download 3 months of PJM data
   python src/data_fetching/download_eia_data.py --bas PJM --start 2023-10-01 --end 2023-12-31
   ```

## Data Download Options

The `download_eia_data.py` script provides flexible download options:

### Quick Test
```bash
# Download 3 months of PJM data to verify API connection
python src/data_fetching/download_eia_data.py --bas PJM --start 2023-10-01 --end 2023-12-31
```

### Download Specific BAs and Date Range
```bash
# Download specific BAs for a custom date range
python src/data_fetching/download_eia_data.py --bas PJM MISO ERCOT --start 2023-01-01 --end 2023-12-31
```

### Download All Data
```bash
# Download all BAs for full date range (2016-2024) - takes several hours
python src/data_fetching/download_eia_data.py --all
```

### Download Specific Years
```bash
# Download specific years for all BAs
python src/data_fetching/download_eia_data.py --years 2022 2023 2024

# Download specific years for specific BAs
python src/data_fetching/download_eia_data.py --bas PJM MISO --years 2023 2024
```

### Additional Options
- `--output DIR`: Specify output directory (default: data/raw)
- `--skip-existing`: Skip files that already exist

## Current Implementation Status

### ✅ Implemented

1. **Configuration (`config/config.py`)**
   - Central configuration for API settings, BA list, date ranges
   - Data paths and cleaning parameters

2. **Data Fetching**
   - **`download_eia_data.py`**: Flexible standalone script with multiple download options
   - Automatic pagination and rate limiting

3. **API Diagnostics (`src/data_fetching/test_eia_api.py`)**
   - Diagnostic tool for debugging API issues (NOT for downloading data)
   - Tests connectivity, explores endpoints, checks performance
   - Use when troubleshooting connection problems
   - Run with: `python src/data_fetching/test_eia_api.py`

4. **Utilities (`utils.py`)**
   - Helper functions for logging and validation

### 🚧 To Be Implemented

1. **Data Cleaning** - Following Appendix B specifications:
   - Date normalization
   - Missing value interpolation
   - Outlier detection and correction
   - BA label standardization
   - Peak validation

2. **Curtailment Analysis** - Following paper methodology:
   - Seasonal peak threshold determination
   - Curtailment goal-seek function
   - Load integration potential calculations

## Balancing Authorities

The pipeline processes data for 22 major balancing authorities:

**RTOs/ISOs:**
- PJM, MISO, ERCOT (ERCO), SPP (SWPP), CAISO (CISO), ISO-NE (ISNE), NYISO (NYIS)

**Utilities:**
- Southern Company (SOCO)
- Duke Energy (DEC/DUK, DEP/CPLE, DEF/FPC)
- TVA, BPA (BPAT)
- AZPS, FPL
- PacifiCorp (PACE, PACW)
- PGE, PSCO, SRP
- DESC (SCEG), SCP (SC)

*Note: Codes in parentheses are EIA API codes that differ from paper notation*

## Data Format

Raw data files are saved as CSV with columns:
- `period`: Timestamp (UTC)
- `respondent`: BA code
- `respondent-name`: Full BA name
- `type`: Data type (D=Demand)
- `type-name`: "Demand"
- `value`: Demand in megawatthours
- `value-units`: "megawatthours"

## Debugging

A VSCode launch configuration is provided in `.vscode/launch.json` for debugging the main control flow and data download scripts.

## References

- Paper: "Rethinking Load Growth" (Nicholas Institute, 2025)
- EIA API Documentation: https://www.eia.gov/opendata/documentation.php
- EIA Hourly Electric Grid Monitor: https://www.eia.gov/electricity/gridmonitor/