# EIA Data Pipeline

This project implements the data pipeline described in the paper "Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems" by Norris et al. (2025).

## Overview

The pipeline downloads and processes hourly electricity demand data from the U.S. Energy Information Administration (EIA) API for 22 major balancing authorities from 2016-2024. This data is used to analyze the potential for integrating large flexible loads (like data centers) into the US power grid.

## Project Structure

```
eia-data/
├── README.md                     # This file
├── requirements.txt              # Python dependencies
├── .env                         # API key configuration (not in git)
├── .env.template                # Template for API key setup
├── .gitignore                   # Git ignore rules
├── rethinking-load-growth-paper.pdf  # Source paper
│
├── src/                         # Source code
│   ├── download_data.py         # Original download script
│   ├── download_all_data.py    # Optimized parallel download script
│   └── clean_data.py            # Data cleaning (to be implemented)
│
├── data/                        # Data directory
│   ├── raw/                     # Raw downloaded data
│   │   ├── PJM/                 # Data for each BA organized by folders
│   │   ├── MISO/
│   │   └── ...
│   └── processed/               # Cleaned data (to be created)
│
└── test_*.py                    # Various test scripts for API testing
```

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Get EIA API Key**
   - Register for a free API key at: https://www.eia.gov/opendata/register.php
   - Copy `.env.template` to `.env` and add your API key

3. **Download Data**
   ```bash
   python src/download_all_data.py
   ```

## Data Pipeline Components

### 1. Data Download (`src/download_all_data.py`)

Downloads hourly demand data from the EIA API v2 for 22 balancing authorities:
- **RTOs/ISOs**: PJM, MISO, ERCOT (ERCO), SPP (SWPP), CAISO (CISO), ISO-NE (ISNE), NYISO (NYIS)
- **Utilities**: Southern Company (SOCO), Duke Energy (DUK, CPLE, FPC), TVA, Bonneville (BPAT)
- **Others**: AZPS, FPL, PACE, PACW, PGE, PSCO, SRP, DESC (SCEG), SCP (SC)

The script:
- Uses the EIA API v2 endpoint: `/electricity/rto/region-data/data/`
- Downloads hourly demand data (type='D') for 2016-2024
- Implements parallel downloading with rate limiting
- Saves data as CSV files organized by BA and year

### 2. Data Cleaning (To Be Implemented)

Based on Appendix B of the paper, the cleaning process will:
- Normalize date-time formats
- Handle missing/zero values with linear interpolation
- Identify and correct outliers and spikes
- Map BA labels to standard acronyms
- Validate against FERC forecasted peaks

### 3. Analysis (To Be Implemented)

Calculate curtailment-enabled headroom following the paper's methodology:
- Determine seasonal peak thresholds
- Apply curtailment goal-seek function
- Generate results showing potential new load integration

## Balancing Authority Mappings

The EIA uses different codes than the paper. Key mappings:
- CPLE → DEP (Duke Energy Progress East)
- DUK → DEC (Duke Energy Carolinas)
- SC → SCP (Santee Cooper)
- SWPP → SPP (Southwest Power Pool)
- SCEG → DESC (Dominion Energy South Carolina)
- FPC → DEF (Duke Energy Florida)
- CISO → CAISO (California ISO)
- BPAT → BPA (Bonneville Power Administration)
- NYIS → NYISO (New York ISO)
- ERCO → ERCOT (Texas)
- ISNE → ISO-NE (New England)

## API Notes

- The EIA API v2 requires authentication via API key
- Rate limits: Be respectful with request frequency
- Data is returned in JSON format with pagination (5000 records max per request)
- Hourly data uses UTC timestamps

## Next Steps

1. Implement data cleaning pipeline following Appendix B specifications
2. Add analysis code to calculate curtailment-enabled headroom
3. Generate visualizations matching the paper's figures
4. Add validation against paper's results

## References

- Paper: "Rethinking Load Growth" (Nicholas Institute, 2025)
- EIA API Documentation: https://www.eia.gov/opendata/documentation.php
- EIA Hourly Electric Grid Monitor: https://www.eia.gov/electricity/gridmonitor/