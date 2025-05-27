# EIA Data Project - Operational Guide

## Key Project Files

- **README.md**: High-level project overview for human readers
- **ROADMAP.md**: Detailed development roadmap with phases and dependencies
- **rethinking-load-growth-paper.md**: Source research paper (Norris et al., 2025) that this project implements and extends
- **.env.template**: Template for API key configuration
- **requirements.txt**: Python dependencies

## Project Structure & File Guide

NOTE: this may be out of date, but wanted to give you some sign posting so you don't have to look up every file every time.

NOTE: the data directories like plant_data and ba_aggregate_data are in gitignore but you can find them in here

```
eia-data/
├── README.md                    # Project overview and quick start guide
├── CLAUDE.md                   # This file - operational guide for development
├── ROADMAP.md                  # Development roadmap with sequential tasks
├── rethinking-load-growth-paper.md  # Research paper we're implementing
├── requirements.txt            # Python dependencies
├── .env                        # API key configuration (create from .env.template)
│
├── config/                     # Configuration module
│   ├── __init__.py
│   └── config.py              # Central settings: API keys, BA lists, date ranges
│
├── src/                        # Source code modules
│   ├── __init__.py
│   ├── utils/                 # Shared utilities
│   │   ├── api.py            # EIA API wrapper functions
│   │   ├── constants.py      # FUEL_TYPES, STATES, BA codes
│   │   └── formatting.py     # Data formatting helpers
│   │
│   ├── data_fetching/         # Download modules
│   │   ├── download_ba_aggregate_data.py  # Hourly BA demand data
│   │   └── download_plant_data.py         # Monthly plant generation data
│   │
│   ├── data_cleaning/         # Data validation and cleaning
│   │   ├── BAAggregateCleaner.py         # BA data cleaning class
│   │   ├── run_ba_aggregate_cleaning.py   # BA cleaning runner script
│   │   └── PlantDataCleaner.py          # Plant data cleaning (TODO)
│   │
│   └── data_analysis/         # Analysis modules
│       ├── BAAggregateCurtailmentAnalyzer.py      # BA curtailment analysis
│       ├── run_ba_aggregate_curtailment_analysis.py # BA analysis runner
│       ├── PlantCurtailmentAnalyzer.py            # Plant curtailment (TODO)
│       └── summarize_plant_data_by_state.py       # State summaries (TODO)
│
├── ba_aggregate_data/         # Balancing authority data directory
│   ├── raw/                   # Raw hourly demand CSVs: {BA}_{YEAR}.csv
│   ├── cleaned/              # Cleaned/interpolated data
│   └── visualizations/       # Plots and analysis outputs
│
├── plant_data/               # Individual plant data directory
│   ├── raw_plant_generation_data/  # Monthly generation data
│   │   └── {STATE}/              # State subdirectories
│   │       └── {PLANT_ID}_{YEAR}_generation.csv
│   ├── plant_lookup.csv          # Master metadata file (location, BA, ownership)
│   └── eia860_downloads/         # Cached EIA-860 zip files
│
└── tests/                     # Test modules
    ├── test_ba_aggregate_api.py
    ├── test_ba_aggregate_cleaner.py
    └── test_plant_location_endpoints.py
```



## Common Commands

### BA Aggregate Analysis Pipeline
```bash
# Download data
python src/data_fetching/download_ba_aggregate_data.py --bas PJM MISO --years 2023 2024
python src/data_fetching/download_ba_aggregate_data.py --all  # Download everything (takes hours)

# Clean data (processes all downloaded raw data)
python src/data_cleaning/run_ba_aggregate_cleaning.py

# Run curtailment analysis
python src/data_analysis/run_ba_aggregate_curtailment_analysis.py

# Quick test with 3 months of data
python src/data_fetching/download_ba_aggregate_data.py --bas PJM --start 2023-10-01 --end 2023-12-31
```

### Plant-Level Data Pipeline
```bash
# Download plant data by state
python src/data_fetching/download_plant_data.py --states TX CA --start 2020 --end 2023

# Download with specific fuel type
python src/data_fetching/download_plant_data.py --states CA --fuel SUN --start 2018 --end 2023

# Force re-download existing files
python src/data_fetching/download_plant_data.py --states TX --start 2020 --end 2023 --force-download

# Increase batch size for faster downloads
python src/data_fetching/download_plant_data.py --states TX CA --start 2020 --end 2023 --batch-size 250
```

### Common Analysis Tasks
```bash
# Summarize plant data by state (when implemented)
python src/data_analysis/summarize_plant_data_by_state.py

# Test API endpoints
python test_plant_location_endpoints.py
python test_utils.py
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