# EIA Power Grid Analysis

This project analyzes U.S. electricity generation patterns to assess opportunities for integrating large flexible loads (like data centers) into the power grid. Based on the research paper "Rethinking Load Growth" by Norris et al. (2025), it reproduces the data pipeline described in the paper, as well as extending the analysis from balancing authority aggregates to individual power plant data.

## What This Project Does

1. **Downloads comprehensive electricity data** from the EIA API
   - Hourly demand data for 22 major balancing authorities (2016-2024)
   - Monthly generation data for individual power plants across all U.S. states
   
2. **Analyzes curtailment potential** to identify opportunities for flexible load integration
   - Calculates "curtailment-enabled headroom" where new loads can operate without grid upgrades
   - Maps generation patterns to find optimal locations for data centers

3. **Provides actionable insights** for grid operators and large electricity consumers
   - Identifies when and where excess generation capacity exists
   - Quantifies the potential for load flexibility to improve grid utilization

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your EIA API key (get one free at https://www.eia.gov/opendata/register.php)
cp .env.template .env
# Edit .env and add your API key

# 3. Download some sample data
python src/data_fetching/download_ba_aggregate_data.py --bas PJM --years 2023

# 4. Run the analysis pipeline
python src/data_cleaning/run_ba_aggregate_cleaning.py
python src/data_analysis/run_ba_aggregate_curtailment_analysis.py
```

## Project Structure

```
eia-data/
├── src/                        # Source code
│   ├── data_fetching/         # Download data from EIA API
│   ├── data_cleaning/         # Clean and validate data
│   └── data_analysis/         # Analyze curtailment potential
│
├── ba_aggregate_data/         # Balancing authority data
│   ├── raw/                   # Raw downloaded data
│   ├── cleaned/              # Processed data
│   └── visualizations/       # Analysis results
│
└── plant_data/               # Individual plant data
    ├── raw_plant_generation_data/  # Monthly generation by plant
    └── plant_lookup.csv           # Plant metadata (location, ownership)
```

## Two Analysis Modes

### 1. Balancing Authority Analysis
Analyzes hourly demand data for 22 major balancing authorities (RTOs/ISOs and major utilities):
```bash
# Download BA data (e.g., PJM for 2023)
python src/data_fetching/download_ba_aggregate_data.py --bas PJM --years 2023

# Run analysis pipeline
python src/data_cleaning/run_ba_aggregate_cleaning.py
python src/data_analysis/run_ba_aggregate_curtailment_analysis.py
```

### 2. Plant-Level Analysis
Analyzes monthly generation data for individual power plants:
```bash
# Download plant data (e.g., all Texas plants for 2020-2023)
python src/data_fetching/download_plant_data.py --states TX --start 2020 --end 2023

# Analysis tools coming soon
```

## Data Sources

- **Balancing Authority Data**: Hourly electricity demand from EIA's Electric Grid Monitor
- **Plant Data**: Monthly generation data and plant characteristics from EIA's facility-level APIs
- **Coverage**: 22 major balancing authorities covering ~80% of U.S. electricity demand

## References

- [Research Paper: "Rethinking Load Growth"](https://nicholasinstitute.duke.edu/publications/rethinking-load-growth) (Nicholas Institute, 2025)
- [EIA API Documentation](https://www.eia.gov/opendata/documentation.php)
- [EIA Electric Grid Monitor](https://www.eia.gov/electricity/gridmonitor/)