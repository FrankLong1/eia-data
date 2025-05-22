"""Module for fetching EIA hourly load data."""

import os
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import pandas as pd
import requests
from tqdm import tqdm

from config import (
    EIA_API_BASE_URL, EIA_API_KEY, BALANCING_AUTHORITIES,
    START_DATE, END_DATE, RAW_DATA_DIR
)

logger = logging.getLogger(__name__)


class EIADataFetcher:
    """Fetches hourly load data from EIA API."""
    
    def __init__(self, api_key: str = EIA_API_KEY):
        """Initialize the data fetcher with API key."""
        if not api_key:
            raise ValueError("EIA API key is required. Set EIA_API_KEY environment variable.")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": api_key})
    
    def fetch_ba_data(self, ba_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch hourly load data for a specific balancing authority.
        
        Args:
            ba_code: Balancing authority code
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            DataFrame with hourly load data
        """
        logger.info(f"Fetching data for {ba_code} from {start_date} to {end_date}")
        
        # EIA API endpoint for electricity grid operations
        endpoint = f"{EIA_API_BASE_URL}electricity/rto/region-data/data/"
        
        params = {
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": ba_code,
            "facets[type][]": "D",  # Demand/Load
            "start": f"{start_date}T00",
            "end": f"{end_date}T23",
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
            "offset": 0,
            "length": 5000
        }
        
        all_data = []
        
        while True:
            try:
                response = self.session.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                
                if "response" in data and "data" in data["response"]:
                    records = data["response"]["data"]
                    if not records:
                        break
                    
                    all_data.extend(records)
                    
                    # Check if there are more pages
                    if len(records) < params["length"]:
                        break
                    
                    params["offset"] += params["length"]
                else:
                    logger.warning(f"Unexpected response structure for {ba_code}")
                    break
                    
                # Rate limiting
                time.sleep(0.1)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching data for {ba_code}: {e}")
                break
        
        if all_data:
            df = pd.DataFrame(all_data)
            df["timestamp"] = pd.to_datetime(df["period"])
            df["ba_code"] = ba_code
            df = df.rename(columns={"value": "load_mw"})
            df = df[["timestamp", "ba_code", "load_mw"]]
            df = df.sort_values("timestamp")
            return df
        else:
            return pd.DataFrame()
    
    def fetch_all_ba_data(self, 
                          ba_codes: List[str] = BALANCING_AUTHORITIES,
                          start_date: str = START_DATE,
                          end_date: str = END_DATE,
                          save_individual: bool = True) -> pd.DataFrame:
        """
        Fetch data for all balancing authorities.
        
        Args:
            ba_codes: List of BA codes to fetch
            start_date: Start date
            end_date: End date
            save_individual: Whether to save individual BA files
            
        Returns:
            Combined DataFrame with all BA data
        """
        all_ba_data = []
        
        for ba_code in tqdm(ba_codes, desc="Fetching BA data"):
            try:
                ba_data = self.fetch_ba_data(ba_code, start_date, end_date)
                
                if not ba_data.empty:
                    all_ba_data.append(ba_data)
                    
                    if save_individual:
                        # Save individual BA data
                        filename = f"{ba_code}_hourly_load_{start_date}_{end_date}.csv"
                        filepath = os.path.join(RAW_DATA_DIR, filename)
                        ba_data.to_csv(filepath, index=False)
                        logger.info(f"Saved {ba_code} data to {filepath}")
                else:
                    logger.warning(f"No data retrieved for {ba_code}")
                    
            except Exception as e:
                logger.error(f"Failed to fetch data for {ba_code}: {e}")
                continue
        
        # Combine all BA data
        if all_ba_data:
            combined_df = pd.concat(all_ba_data, ignore_index=True)
            
            # Save combined data
            combined_filename = f"all_ba_hourly_load_{start_date}_{end_date}.csv"
            combined_filepath = os.path.join(RAW_DATA_DIR, combined_filename)
            combined_df.to_csv(combined_filepath, index=False)
            logger.info(f"Saved combined data to {combined_filepath}")
            
            return combined_df
        else:
            logger.error("No data retrieved for any balancing authority")
            return pd.DataFrame()
    
    def update_data(self, ba_codes: List[str] = BALANCING_AUTHORITIES) -> pd.DataFrame:
        """
        Update data with the latest available information.
        
        Args:
            ba_codes: List of BA codes to update
            
        Returns:
            Updated DataFrame
        """
        # Check existing data to determine last update
        existing_files = [f for f in os.listdir(RAW_DATA_DIR) if f.endswith(".csv")]
        
        if existing_files:
            # Find the most recent date in existing data
            combined_file = [f for f in existing_files if f.startswith("all_ba_hourly_load")]
            if combined_file:
                df = pd.read_csv(os.path.join(RAW_DATA_DIR, combined_file[0]))
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                last_date = df["timestamp"].max()
                start_date = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                start_date = START_DATE
        else:
            start_date = START_DATE
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        
        logger.info(f"Updating data from {start_date} to {end_date}")
        return self.fetch_all_ba_data(ba_codes, start_date, end_date)


def main():
    """Main function for testing the data fetcher."""
    logging.basicConfig(level=logging.INFO)
    
    fetcher = EIADataFetcher()
    
    # Test fetching data for a single BA
    test_ba = "PJM"
    test_start = "2024-01-01"
    test_end = "2024-01-31"
    
    df = fetcher.fetch_ba_data(test_ba, test_start, test_end)
    print(f"Fetched {len(df)} records for {test_ba}")
    print(df.head())


if __name__ == "__main__":
    main()