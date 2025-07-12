# EIA Curtailment Analysis

A clean, focused implementation of the curtailment analysis methodology from "Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems" (Norris et al., 2025).

## Overview

This project analyzes curtailment-enabled headroom across 22 US balancing authorities to determine how much additional flexible load can be integrated at different curtailment rates. The analysis uses hourly demand data from EIA-930 to calculate the potential for large flexible loads like data centers to utilize excess grid capacity.

## Key Findings

The analysis shows that US power systems have significant headroom for flexible loads:
- **98 GW** of additional load at 0.5% annual curtailment
- **126 GW** at 1.0% curtailment  
- **215 GW** at 5.0% curtailment

Top 5 balancing authorities by headroom potential (0.5% curtailment):
1. PJM: 18 GW
2. MISO: 15 GW  
3. ERCOT: 10 GW
4. SPP: 10 GW
5. SOCO: 8 GW

## Quick Start

1. **Setup Environment**:
   ```bash
   pip install -r requirements.txt
   cp .env.template .env
   # Add your EIA API key to .env # Get your free API key from: https://www.eia.gov/opendata/register.php
   ```

2. **Run Complete Analysis**:
   ```bash
   python run_analysis.py --full
   ```

3. **Test with Sample Data**:
   ```bash
   python run_analysis.py --bas PJM --start 2023-10-01 --end 2023-12-31
   ```

## Project Structure

```
eia-curtailment-analysis/
├── README.md              # This file
├── requirements.txt       # Python dependencies
├── config.py             # Configuration settings
├── run_analysis.py       # Main analysis pipeline
│
├── src/                  # Core modules
│   ├── download.py       # EIA data download
│   ├── clean.py          # Data cleaning & validation
│   ├── analyze.py        # Curtailment analysis
│   └── visualize.py      # Plot generation
│
└── data/                 # Data storage
    ├── raw/              # Downloaded EIA data
    ├── cleaned/          # Processed data
    └── results/          # Analysis outputs & plots
```

## Usage

### Basic Commands

```bash
# Download and analyze specific BAs
python run_analysis.py --bas PJM MISO --years 2022 2023

# Run analysis on existing data
python run_analysis.py --analyze-only

# Generate only visualizations
python run_analysis.py --visualize-only
```

### Advanced Usage

```bash
# Custom date range
python run_analysis.py --start 2023-01-01 --end 2023-12-31

# Download only (no analysis)
python run_analysis.py --download-only --all

# Force re-download of existing files
python run_analysis.py --force-redownload
```

## Methodology

The analysis follows the research paper's methodology:

1. **Data Collection**: Download hourly demand data from EIA-930 for 22 balancing authorities
2. **Data Cleaning**: Remove outliers using IQR method, interpolate missing values
3. **Curtailment Analysis**: Calculate headroom at standard rates (0.25%, 0.5%, 1.0%, 5.0%)
4. **Visualization**: Generate publication-ready plots and summary statistics

### Balancing Authorities (22 total)

**RTOs/ISOs**: PJM, MISO, ERCOT, SPP, CAISO, ISO-NE, NYISO  
**Utilities**: SOCO, DEC, DEP, DEF, TVA, BPA, AZPS, FPL, PACE, PACW, PGE, PSCO, SRP, DESC, SCP

## API Setup

1. Get a free API key from https://www.eia.gov/opendata/register.php
2. Copy `.env.template` to `.env`
3. Add your key: `EIA_API_KEY=your_key_here`

## Output

The analysis generates:
- **CSV files**: Curtailment headroom results by BA and curtailment rate
- **Visualizations**: Load duration curves, headroom comparisons, seasonal patterns
- **Summary statistics**: System-wide metrics and BA-specific details

## Dependencies

Core requirements:
- pandas, numpy: Data manipulation
- matplotlib, seaborn: Visualization
- requests: API calls
- python-dotenv: Environment variables

See `requirements.txt` for complete list.

## Citation

If you use this analysis, please cite the original research:

Norris, T. H., T. Profeta, D. Patino-Echeverri, and A. Cowie-Haskell. 2025. Rethinking Load Growth: Assessing the Potential for Integration of Large Flexible Loads in US Power Systems. NI R 25-01. Durham, NC: Nicholas Institute for Energy, Environment & Sustainability, Duke University.