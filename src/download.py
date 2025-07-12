#!/usr/bin/env python3
"""
Simplified EIA BA aggregate data download module for curtailment analysis.

This module provides a clean, self-contained interface for downloading hourly 
demand data from the EIA-930 API for the 22 balancing authorities analyzed 
in the curtailment research paper.

Key features:
- Downloads hourly demand data from EIA-930 API
- Handles all 22 BAs from the research paper
- Built-in rate limiting and error handling
- Self-contained with no external dependencies on utils modules
- Focused specifically on BA aggregate data (no plant-level data)
"""

import os
import requests
import pandas as pd
import time
import logging
from typing import Optional
from pathlib import Path
from . import config


def _make_request(endpoint: str, params: dict) -> Optional[dict]:
    """Make a request to the EIA API."""
    if not config.EIA_API_KEY:
        raise ValueError("EIA_API_KEY not found. Set it in your .env file.")
    
    url = f"https://api.eia.gov/v2/{endpoint}"
    params['api_key'] = config.EIA_API_KEY
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def download_ba_data(ba: str, start_date: str, end_date: str, 
                    output_dir: str, skip_existing: bool = False) -> Optional[pd.DataFrame]:
    """Download hourly demand data for a specific balancing authority."""
    # Set up file paths
    save_dir = Path(output_dir) / ba
    save_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{ba}_{start_date}_{end_date}_hourly_demand.csv"
    output_file = save_dir / filename
    
    # Check if file already exists and skip if requested
    if skip_existing and output_file.exists():
        logging.info(f"File already exists, skipping: {output_file}")
        return pd.read_csv(output_file)
    
    # API request parameters
    params = {
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': ba,  # Use BA code directly
        'facets[type][]': 'D',  # D = Demand
        'start': start_date + 'T00',
        'end': end_date + 'T23',
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc',
        'offset': 0,
        'length': config.EIA_MAX_RECORDS_PER_REQUEST
    }
    
    all_data = []
    
    # Handle pagination
    while True:
        data = _make_request("electricity/rto/region-data/data/", params)
        
        if not data or 'response' not in data or 'data' not in data['response']:
            break
            
        records = data['response']['data']
        if not records:
            break
            
        all_data.extend(records)
        
        if len(records) < config.EIA_MAX_RECORDS_PER_REQUEST:
            break
        else:
            params['offset'] += config.EIA_MAX_RECORDS_PER_REQUEST
        
        time.sleep(config.API_DELAY_SECONDS)
    
    # Save data if we got any
    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False)
        logging.info(f"Saved {len(df)} records for {ba}")
        return df
    else:
        logging.warning(f"No data found for {ba}")
        return None


def download_all_ba_data(bas_list: list, start_date: str, end_date: str,
                        output_dir: str, skip_existing: bool = False):
    """Download data for all requested balancing authorities."""
    for ba in bas_list:
        logging.info(f"Downloading data for {ba}")
        download_ba_data(ba, start_date, end_date, output_dir, skip_existing)
        time.sleep(config.API_DELAY_SECONDS)


if __name__ == "__main__":
    # Simple test
    download_ba_data('PJM', '2023-10-01', '2023-12-31', 'test_data')