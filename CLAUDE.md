# EIA Curtailment Analysis - Operational Guide

## CRITICAL SETUP REQUIREMENTS

### 1. Virtual Environment (REQUIRED)
**MUST create and activate virtual environment before running any code:**

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment (do this EVERY time)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. API Key Setup (REQUIRED)
```bash
# Copy template and add your EIA API key
cp .env.template .env
# Edit .env and add: EIA_API_KEY=your_key_here
```

Get free API key at: https://www.eia.gov/opendata/register.php

## Key Project Files

- **README.md**: High-level project overview for human readers
- **rethinking-load-growth-paper.md**: Source research paper (Norris et al., 2025) that this project implements
- **config.py**: Configuration settings for the analysis
- **run_analysis.py**: Main analysis pipeline script
- **requirements.txt**: Python dependencies

## Refactored Project Structure

**CLEAN, FOCUSED STRUCTURE - PAPER IMPLEMENTATION ONLY**

```
eia-curtailment-analysis/
├── README.md              # Project overview and quick start guide
├── CLAUDE.md             # This file - operational guide for development
├── rethinking-load-growth-paper.md  # Research paper we're implementing
├── requirements.txt      # Python dependencies
├── .env                  # API key configuration (create from .env.template)
├── config.py             # Configuration settings
├── run_analysis.py       # Main analysis pipeline
├── venv/                 # Virtual environment (REQUIRED)
│
├── src/                  # 4 core modules only
│   ├── download.py       # EIA BA data download
│   ├── clean.py          # Data cleaning & validation
│   ├── analyze.py        # Curtailment analysis
│   └── visualize.py      # Plot generation
│
└── data/                 # Data storage
    ├── raw/              # Downloaded EIA data
    ├── cleaned/          # Processed data
    └── results/          # Analysis outputs & plots
```



## Common Commands

**ALWAYS activate virtual environment first:**
```bash
source venv/bin/activate
```

### Complete Analysis Pipeline
```bash
# Run complete analysis (download → clean → analyze → visualize)
python run_analysis.py --full

# Quick test with 3 months of PJM data
python run_analysis.py --bas PJM --start 2023-10-01 --end 2023-12-31

# Download and analyze specific BAs for specific years
python run_analysis.py --bas PJM MISO --years 2022 2023
```

### Individual Pipeline Phases
```bash
# Download only (all 22 BAs, 2016-2024)
python run_analysis.py --download-only --all

# Download specific BAs and years
python run_analysis.py --download-only --bas PJM MISO --years 2023 2024

# Clean existing downloaded data
python run_analysis.py --clean-only

# Analyze existing cleaned data
python run_analysis.py --analyze-only

# Generate visualizations only
python run_analysis.py --visualize-only
```

### Advanced Usage
```bash
# Custom date range
python run_analysis.py --start 2023-01-01 --end 2023-12-31

# Skip existing files during download
python run_analysis.py --skip-existing

# Process subset of BAs
python run_analysis.py --bas ERCO CISO SPP --years 2023
```

## Code Patterns and Conventions

### File Organization
- BA aggregate data: `ba_aggregate_data/raw/{BA}_{YEAR}.csv`
- Plant time-series: `plant_data/raw_plant_generation_data/{STATE}/{PLANT_ID}_{YEAR}_generation.csv`
- Plant metadata: `plant_data/plant_lookup.csv`
- Always use state-based organization for plant data

### Data Processing Patterns
```python
# When loading plant data, always merge with metadata
df = load_and_merge_plant_data(csv_file)  # Automatically joins with plant_lookup.csv

# For BA data, use the standardized label mapping
BA_LABEL_MAPPING = {
    'ERCO': 'ERCOT', 'SWPP': 'SPP', 'CISO': 'CAISO',
    'ISNE': 'ISO-NE', 'NYIS': 'NYISO', 'DUK': 'DEC',
    'CPLE': 'DEP', 'FPC': 'DEF', 'BPAT': 'BPA',
    'SCEG': 'DESC', 'SC': 'SCP'
}
```

### API Configuration
- API key must be in `.env` file (copy from `.env.template`)
- Rate limiting: Default 0.1s between requests
- Batch size for plant downloads: 200 (max 250)
- Always validate API key before starting downloads

## Implementation Details

### Balancing Authorities (22 total)
**RTOs/ISOs**: PJM, MISO, ERCOT (ERCO), SPP (SWPP), CAISO (CISO), ISO-NE (ISNE), NYISO (NYIS)
**Utilities**: SOCO, DEC/DUK, DEP/CPLE, DEF/FPC, TVA, BPA (BPAT), AZPS, FPL, PACE, PACW, PGE, PSCO, SRP, DESC (SCEG), SCP (SC)

Note: Codes in parentheses are EIA API codes that differ from paper notation.

### Data Enrichment Sources
1. **EIA-860**: Provides plant location (lat/long), ownership, county, zip
2. **Operating Generator Capacity API**: Provides BA assignments, entity info
3. **Facility-Fuel API**: Main source for generation data

### Cleaning Operations (BA data)
1. Date normalization to local time zones
2. Missing value linear interpolation
3. Outlier detection using IQR method
4. BA label standardization
5. Peak demand validation

### Performance Optimization
- Skip existing files by default (`--skip-existing`)
- Batch API requests (200 plants per request)
- Parallel processing where possible
- Cache EIA-860 zip files locally

## Known Issues and Workarounds

1. **API Response Format**: Plant IDs may be returned as strings or integers - always convert to string for comparison
2. **Missing EIA-860 Data**: If year not available, falls back gracefully without location/ownership
3. **Large Downloads**: Use `--batch-size` flag to optimize API performance, max appears to be 200-250 or so.

## Testing

Always test with small datasets first:

Easy to do this with smaller states with less power plants like AR, as well as with less years.

```bash
# Test BA download
python src/data_fetching/download_ba_aggregate_data.py --bas PJM --start 2023-10-01 --end 2023-12-31

# Test plant download  
python src/data_fetching/download_plant_data.py --states TX --limit 5 --start 2023 --end 2023
```

## Debugging Tips

- VSCode launch configuration available in `.vscode/launch.json`
- Use `--verbose` flag for detailed logging (when implemented)
- Check `plant_data/eia860_downloads/` for cached EIA-860 files
- API errors usually mean rate limiting - add delays if needed

## Current Development Status

See **ROADMAP.md** for detailed task breakdown and dependencies. Key priorities:

1. **Phase 1**: Plant data cleaning and curtailment analysis (immediate)
2. **Phase 2**: Key analysis questions - gas plants, storage, mapping
3. **Phase 3+**: Strategic insights and automation

For specific TODOs and implementation timeline, refer to ROADMAP.md.