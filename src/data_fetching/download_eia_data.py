#!/usr/bin/env python3
"""
Consolidated EIA data download script with flexible options.

Requires explicit parameters - no default download behavior.
Options available for bulk download and custom date ranges.
"""

# Standard library imports
import os  # For file and directory operations
import argparse  # For parsing command line arguments
import requests  # For making HTTP requests to the EIA API
import pandas as pd  # For data manipulation and CSV handling
from datetime import datetime, timedelta  # For date operations
import time  # For rate limiting and delays
from tqdm import tqdm  # For progress bars
import json  # For handling JSON responses
from dotenv import load_dotenv  # For loading environment variables
import logging  # For logging operations

# Configure logging with timestamp, level, and message format
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables from .env file
load_dotenv()

# EIA API configuration constants
EIA_API_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"  # Base URL for EIA API
EIA_API_KEY = os.environ.get('EIA_API_KEY')  # Get API key from environment variables

# List of all balancing authorities (BAs) from the research paper
BALANCING_AUTHORITIES = [
    'PJM', 'MISO', 'ERCO', 'SWPP', 'SOCO', 'CISO', 'ISNE', 'NYIS',
    'DUK', 'CPLE', 'FPC', 'TVA', 'BPAT', 'AZPS', 'FPL', 'PACE', 
    'PACW', 'PGE', 'PSCO', 'SRP', 'SCEG', 'SC'
]

# Mapping of paper acronyms to official EIA respondent names
# This mapping is based on Appendix B of the research paper
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


def get_eia_respondent_name(ba):
    """
    Convert balancing authority code to EIA respondent name
    Args:
        ba (str): Balancing authority code
    Returns:
        str: EIA respondent name
    """
    return BA_MAPPING.get(ba, ba)  # Return mapped name or original if not found


def check_api_key():
    """
    Validate the EIA API key by making a test request
    Returns:
        bool: True if API key is valid, False otherwise
    """
    # Test parameters for a minimal API request
    test_params = {
        'api_key': EIA_API_KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': 'PJM',
        'start': '2024-01-01T00',
        'end': '2024-01-01T00',
        'length': 1
    }
    
    try:
        # Make test request to API
        response = requests.get(EIA_API_URL, params=test_params, timeout=10)
        response.raise_for_status()  # Raise exception for bad status codes
        data = response.json()
        
        # Check if response contains expected structure
        if 'response' in data:
            logging.info("API key is valid!")
            return True
        else:
            logging.error("API key may be invalid or API structure has changed")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking API key: {e}")
        return False


def download_ba_data(ba, start_date, end_date, output_dir='data/raw', use_ba_folders=False, skip_existing=False):
    """
    Download hourly demand data for a specific balancing authority
    
    Args:
        ba (str): Balancing authority code
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        output_dir (str): Directory to save the data
        use_ba_folders (bool): Whether to create subfolders for each BA
        skip_existing (bool): Whether to skip downloading if file already exists
    
    Returns:
        pd.DataFrame or None: Downloaded data as DataFrame if successful, None if failed
    """
    
    # Determine output file path first to check if it exists
    if use_ba_folders:
        save_dir = os.path.join(output_dir, ba)
        filename = f"{ba}_{start_date}_{end_date}_hourly_demand.csv"
    else:
        save_dir = output_dir
        filename = f"{get_eia_respondent_name(ba)}_hourly_demand.csv"
    
    output_file = os.path.join(save_dir, filename)
    
    # Check if file already exists and skip if requested
    if skip_existing and os.path.exists(output_file):
        logging.info(f"File already exists, skipping: {output_file}")
        return pd.read_csv(output_file)  # Return existing data
    
    # API request parameters
    params = {
        'api_key': EIA_API_KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': ba,
        'facets[type][]': 'D',  # D = Demand
        'start': start_date + 'T00',
        'end': end_date + 'T23',
        'sort[0][column]': 'period',
        'sort[0][direction]': 'asc',
        'offset': 0,
        'length': 5000  # Maximum records per request
    }
    
    all_data = []  # List to store all downloaded records
    
    # Loop to handle pagination
    while True:
        # Make API request with timeout
        response = requests.get(EIA_API_URL, params=params, timeout=30)
        
        # Handle HTTP errors explicitly
        if response.status_code != 200:
            logging.error(f"HTTP {response.status_code} error for {ba}: {response.text}")
            return None
            
        try:
            data = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON response for {ba}: {e}")
            return None
            
        # ===== EXIT CONDITIONS =====
        # 1. Invalid response structure
        if 'response' not in data or 'data' not in data['response']:
            logging.warning(f"Unexpected response structure for {ba}")
            return None
            
        # 2. No data returned (empty result set)
        records = data['response']['data']
        if not records:
            logging.info(f"No more data available for {ba}")
            break
            
        # ===== PROCESS VALID DATA =====
        # Add all records from this page to our collection
        # Using extend() to flatten the list of records into individual items
        all_data.extend(records)
        
        # ===== CHECK PAGINATION =====
        # If we got fewer than max records, we've reached the last page, otherwise, move to the next page for the next API call
        if len(records) < 5000:
            logging.info(f"Reached last page for {ba} (received {len(records)} records)")
            break
        else:
            params['offset'] += 5000
        
        # Rate limiting to avoid API throttling
        time.sleep(0.1)
    
    if all_data: # if we got any data back, save it to a csv file
        # Create directory if it doesn't exist
        os.makedirs(save_dir, exist_ok=True)
        
        # Convert data to DataFrame and save as CSV
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False)
        
        logging.info(f"Saved {len(df)} records for {ba} to {output_file}")
        return df
    else:
        logging.warning(f"No data found for {ba}")
        return None


def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="Download EIA hourly demand data with flexible options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test - 3 months of PJM data
  python download_eia_data.py --bas PJM --start 2023-10-01 --end 2023-12-31
  
  # Download specific date range for multiple BAs
  python download_eia_data.py --bas PJM MISO ERCOT --start 2023-01-01 --end 2023-12-31
  
  # Download all data for all BAs (2016-2024)
  python download_eia_data.py --all
  
  # Download specific years
  python download_eia_data.py --years 2022 2023 2024
  
  # Download specific years for specific BAs
  python download_eia_data.py --bas PJM MISO --years 2023 2024
        """
    )
    
    # Date range options
    parser.add_argument('--start', type=str, 
                       help='Start date (YYYY-MM-DD). Used with --end for custom range')
    parser.add_argument('--end', type=str, 
                       help='End date (YYYY-MM-DD). Used with --start for custom range')
    parser.add_argument('--years', type=int, nargs='+', 
                       help='Download complete years (e.g., --years 2022 2023 2024)')
    
    # Balancing authority selection options
    parser.add_argument('--bas', type=str, nargs='+', 
                       help='Specific BA codes to download (e.g., --bas PJM MISO ERCOT)')
    parser.add_argument('--all', action='store_true', 
                       help='Download ALL 22 BAs for full date range (2016-2024)')
    
    # Output options
    parser.add_argument('--output', type=str, default='data/raw', 
                       help='Output directory for CSV files (default: data/raw)')
    parser.add_argument('--skip-existing', action='store_true', 
                       help='Skip downloading files that already exist')
    
    return parser.parse_args()


def main():
    """
    Main function with control flow for different download scenarios
    """
    args = parse_arguments()
    
    # Validate API key
    if not EIA_API_KEY:
        print("Error: EIA_API_KEY not found in environment")
        print("Please set your API key in the .env file")
        return
    
    # Test API key
    if not check_api_key():
        print("Please check your API key")
        return
    
    # Handle different download scenarios based on command line arguments
    
    # Scenario 1: Download ALL data (--all flag)
    if args.all:
        bas = BALANCING_AUTHORITIES
        start_date = '2016-01-01'
        end_date = '2024-12-31'
        print(f"Downloading ALL data: {len(bas)} BAs from {start_date} to {end_date}")
        
        # Sequential download mode
        for ba in tqdm(bas, desc="Downloading BAs"):
            download_ba_data(ba, start_date, end_date, args.output, skip_existing=args.skip_existing)
            time.sleep(1)  # Rate limiting between BAs
                
    # Scenario 2: Download specific years (--years flag)
    elif args.years:
        bas = args.bas if args.bas else BALANCING_AUTHORITIES
        print(f"Downloading {len(bas)} BAs for years: {args.years}")
        
        # Sequential download year by year
        for year in args.years:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"
            for ba in tqdm(bas, desc=f"Downloading {year}"):
                download_ba_data(ba, start_date, end_date, args.output, skip_existing=args.skip_existing)
                time.sleep(1)  # Rate limiting
                    
    # Scenario 3: Custom date range (--start and --end flags)
    elif args.start and args.end:
        start_date = args.start
        end_date = args.end
        bas = args.bas if args.bas else BALANCING_AUTHORITIES
        
        print(f"Custom date range: Downloading {len(bas)} BAs from {start_date} to {end_date}")
        
        # Sequential download for custom date range
        for ba in tqdm(bas, desc="Downloading"):
            download_ba_data(ba, start_date, end_date, args.output, skip_existing=args.skip_existing)
            if len(bas) > 1:
                time.sleep(1)  # Rate limiting between BAs
                
    # No arguments provided - show help message
    else:
        print("Error: No download options specified!")
        print("\nPlease specify what to download using one of these options:")
        print("  --start and --end    : Custom date range")
        print("  --years              : Specific years")
        print("  --all                : All data (2016-2024)")
        print("\nFor a quick test, try:")
        print("  python download_eia_data.py --bas PJM --start 2023-10-01 --end 2023-12-31")
        print("\nUse --help for more examples and options.")
    
    print("\nDone!")


if __name__ == "__main__":
    main()