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
from datetime import datetime, timedelta
import time
import logging
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# EIA API configuration
EIA_API_KEY = os.environ.get('EIA_API_KEY')
EIA_BASE_URL = "https://api.eia.gov/v2/"
BA_DATA_ENDPOINT = "electricity/rto/region-data/data/"

# The 22 balancing authorities from the research paper
BALANCING_AUTHORITIES = [
    # RTOs/ISOs
    'PJM',   # PJM Interconnection
    'MISO',  # Midcontinent ISO
    'ERCO',  # ERCOT (Texas)
    'SWPP',  # Southwest Power Pool
    'CISO',  # California ISO
    'ISNE',  # ISO New England
    'NYIS',  # New York ISO
    
    # Utilities
    'SOCO',  # Southern Company
    'DUK',   # Duke Energy Carolinas
    'CPLE',  # Duke Energy Progress
    'FPC',   # Duke Energy Florida
    'TVA',   # Tennessee Valley Authority
    'BPAT',  # Bonneville Power Administration
    'AZPS',  # Arizona Public Service
    'FPL',   # Florida Power & Light
    'PACE',  # PacifiCorp East
    'PACW',  # PacifiCorp West
    'PGE',   # Portland General Electric
    'PSCO',  # Public Service Company of Colorado
    'SRP',   # Salt River Project
    'SCEG',  # South Carolina Electric & Gas
    'SC',    # Santee Cooper
]

# Mapping of paper acronyms to official EIA respondent names
# This handles cases where the EIA API uses different codes
BA_MAPPING = {
    'CPLE': 'DEP',    # Duke Energy Progress East
    'DUK': 'DEC',     # Duke Energy Carolinas
    'SC': 'SCP',      # Santee Cooper
    'SWPP': 'SPP',    # Southwest Power Pool
    'SCEG': 'DESC',   # Dominion Energy South Carolina
    'FPC': 'DEF',     # Duke Energy Florida
    'CISO': 'CAISO',  # California ISO
    'BPAT': 'BPA',    # Bonneville Power Administration
    'NYIS': 'NYISO',  # New York ISO
    'ERCO': 'ERCOT',  # Texas
    'ISNE': 'ISO-NE'  # New England
}


class EIADownloader:
    """
    Simple, self-contained downloader for EIA BA aggregate data.
    
    This class handles API authentication, rate limiting, and error handling
    for downloading hourly demand data from the EIA-930 API.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the EIA downloader.
        
        Args:
            api_key: Optional API key. If not provided, will look for EIA_API_KEY env var
        """
        self.api_key = api_key or EIA_API_KEY
        if not self.api_key:
            raise ValueError("EIA_API_KEY not found. Please set the environment variable or pass api_key parameter.")
        
        # Validate API key on initialization
        if not self._validate_api_key():
            raise ValueError("Invalid API key. Please check your EIA API key.")
    
    def _validate_api_key(self) -> bool:
        """
        Validate the EIA API key by making a test request.
        
        Returns:
            bool: True if API key is valid, False otherwise
        """
        test_url = f"{EIA_BASE_URL}electricity/retail-sales/data/"
        test_params = {
            'api_key': self.api_key,
            'frequency': 'annual',
            'data[0]': 'sales',
            'start': '2023',
            'end': '2023',
            'length': 1
        }
        
        try:
            response = requests.get(test_url, params=test_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'response' in data:
                logging.info("API key validation successful")
                return True
            else:
                logging.error("API key validation failed - unexpected response format")
                return False
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Error validating API key: {e}")
            return False
    
    def _make_request(self, endpoint: str, params: Dict, timeout: int = 30) -> Optional[Dict]:
        """
        Make a request to the EIA API with error handling.
        
        Args:
            endpoint: API endpoint (relative to base URL)
            params: Query parameters for the request
            timeout: Request timeout in seconds
            
        Returns:
            Response data as dictionary, or None if request failed
        """
        url = f"{EIA_BASE_URL}{endpoint}"
        
        # Always add API key
        params['api_key'] = self.api_key
        
        try:
            response = requests.get(url, params=params, timeout=timeout)
            
            if response.status_code != 200:
                logging.error(f"HTTP {response.status_code}: {response.text[:200]}")
                return None
                
            return response.json()
            
        except requests.exceptions.Timeout:
            logging.error(f"Request timeout after {timeout} seconds")
            return None
            
        except requests.exceptions.ConnectionError:
            logging.error("Connection error - check your internet connection")
            return None
            
        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            return None
            
        except ValueError as e:
            logging.error(f"Invalid JSON response: {e}")
            return None
    
    def _get_eia_respondent_name(self, ba: str) -> str:
        """
        Convert balancing authority code to EIA respondent name.
        
        Args:
            ba: Balancing authority code
            
        Returns:
            EIA respondent name
        """
        return BA_MAPPING.get(ba, ba)
    
    def download_ba_data(self, ba: str, start_date: str, end_date: str, 
                        output_dir: str = 'ba_aggregate_data/raw', 
                        skip_existing: bool = False) -> Optional[pd.DataFrame]:
        """
        Download hourly demand data for a specific balancing authority.
        
        Args:
            ba: Balancing authority code
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_dir: Directory to save the data
            skip_existing: Whether to skip downloading if file already exists
        
        Returns:
            Downloaded data as DataFrame if successful, None if failed
        """
        # Validate BA code
        if ba not in BALANCING_AUTHORITIES:
            logging.error(f"Unknown balancing authority: {ba}")
            logging.info(f"Valid BAs: {', '.join(BALANCING_AUTHORITIES)}")
            return None
        
        # Set up file paths
        save_dir = os.path.join(output_dir, ba)
        filename = f"{ba}_{start_date}_{end_date}_hourly_demand.csv"
        output_file = os.path.join(save_dir, filename)
        
        # Check if file already exists and skip if requested
        if skip_existing and os.path.exists(output_file):
            logging.info(f"File already exists, skipping: {output_file}")
            return pd.read_csv(output_file)
        
        # Get EIA respondent name for API request
        eia_respondent = self._get_eia_respondent_name(ba)
        
        # API request parameters
        params = {
            'frequency': 'hourly',
            'data[0]': 'value',
            'facets[respondent][]': eia_respondent,
            'facets[type][]': 'D',  # D = Demand
            'start': start_date + 'T00',
            'end': end_date + 'T23',
            'sort[0][column]': 'period',
            'sort[0][direction]': 'asc',
            'offset': 0,
            'length': 5000  # Maximum records per request
        }
        
        all_data = []
        
        # Handle pagination
        while True:
            # Make API request
            data = self._make_request(BA_DATA_ENDPOINT, params)
            
            # Check for valid response
            if not data or 'response' not in data or 'data' not in data['response']:
                if not all_data:
                    logging.warning(f"No data found for {ba}")
                break
                
            # Extract records
            records = data['response']['data']
            if not records:
                logging.info(f"No more data available for {ba}")
                break
                
            # Add records to collection
            all_data.extend(records)
            
            # Check if we've reached the last page
            if len(records) < 5000:
                logging.info(f"Reached last page for {ba} (received {len(records)} records)")
                break
            else:
                params['offset'] += 5000
            
            # Rate limiting
            time.sleep(0.1)
        
        # Save data if we got any
        if all_data:
            # Create directory if it doesn't exist
            os.makedirs(save_dir, exist_ok=True)
            
            # Convert to DataFrame and save
            df = pd.DataFrame(all_data)
            df.to_csv(output_file, index=False)
            
            logging.info(f"Saved {len(df)} records for {ba} to {output_file}")
            return df
        else:
            logging.warning(f"No data found for {ba}")
            return None
    
    def download_multiple_bas(self, bas: List[str], start_date: str, end_date: str,
                             output_dir: str = 'ba_aggregate_data/raw',
                             skip_existing: bool = False) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Download data for multiple balancing authorities.
        
        Args:
            bas: List of balancing authority codes
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_dir: Directory to save the data
            skip_existing: Whether to skip downloading if files already exist
            
        Returns:
            Dictionary mapping BA codes to their downloaded DataFrames
        """
        results = {}
        
        for ba in bas:
            logging.info(f"Downloading data for {ba}")
            results[ba] = self.download_ba_data(ba, start_date, end_date, output_dir, skip_existing)
            
            # Rate limiting between BAs
            if len(bas) > 1:
                time.sleep(1)
        
        return results
    
    def download_all_bas(self, start_date: str, end_date: str,
                        output_dir: str = 'ba_aggregate_data/raw',
                        skip_existing: bool = False) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Download data for all 22 balancing authorities.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            output_dir: Directory to save the data
            skip_existing: Whether to skip downloading if files already exist
            
        Returns:
            Dictionary mapping BA codes to their downloaded DataFrames
        """
        logging.info(f"Downloading data for all {len(BALANCING_AUTHORITIES)} BAs from {start_date} to {end_date}")
        return self.download_multiple_bas(BALANCING_AUTHORITIES, start_date, end_date, output_dir, skip_existing)
    
    def download_year(self, year: int, bas: Optional[List[str]] = None,
                     output_dir: str = 'ba_aggregate_data/raw',
                     skip_existing: bool = False) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Download data for a complete year.
        
        Args:
            year: Year to download
            bas: List of BA codes (if None, downloads all BAs)
            output_dir: Directory to save the data
            skip_existing: Whether to skip downloading if files already exist
            
        Returns:
            Dictionary mapping BA codes to their downloaded DataFrames
        """
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        if bas is None:
            bas = BALANCING_AUTHORITIES
        
        logging.info(f"Downloading {len(bas)} BAs for year {year}")
        return self.download_multiple_bas(bas, start_date, end_date, output_dir, skip_existing)


def main():
    """
    Example usage of the EIA downloader.
    """
    # Initialize downloader
    try:
        downloader = EIADownloader()
    except ValueError as e:
        print(f"Error: {e}")
        print("\nTo get an API key:")
        print("1. Visit https://www.eia.gov/opendata/register.php")
        print("2. Register for a free API key")
        print("3. Create a .env file in the project root")
        print("4. Add: EIA_API_KEY=your_key_here")
        return
    
    # Example 1: Download a single BA for a date range
    print("Example 1: Downloading PJM data for Q4 2023")
    result = downloader.download_ba_data('PJM', '2023-10-01', '2023-12-31')
    if result is not None:
        print(f"Downloaded {len(result)} records for PJM")
    
    # Example 2: Download multiple BAs
    print("\nExample 2: Downloading multiple BAs")
    results = downloader.download_multiple_bas(['PJM', 'MISO'], '2023-01-01', '2023-01-31')
    for ba, df in results.items():
        if df is not None:
            print(f"Downloaded {len(df)} records for {ba}")
    
    # Example 3: Download all BAs for a year
    print("\nExample 3: Download all BAs for 2023 (this would take a while)")
    # results = downloader.download_year(2023)
    print("(Commented out to avoid long download)")
    
    print("\nDone!")


if __name__ == "__main__":
    main()