#!/usr/bin/env python
"""
Consolidated EIA data download script with flexible options.

Default behavior: Downloads 3 months of data for testing
Options available for bulk download, parallel processing, and custom date ranges.
"""

import os
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import json
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# EIA API configuration
EIA_API_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
EIA_API_KEY = os.environ.get('EIA_API_KEY')

# Balancing authorities from the paper
BALANCING_AUTHORITIES = [
    'PJM', 'MISO', 'ERCO', 'SWPP', 'SOCO', 'CISO', 'ISNE', 'NYIS',
    'DUK', 'CPLE', 'FPC', 'TVA', 'BPAT', 'AZPS', 'FPL', 'PACE', 
    'PACW', 'PGE', 'PSCO', 'SRP', 'SCEG', 'SC'
]

# Map paper acronyms to EIA respondent names (based on Appendix B)
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
    """Convert balancing authority to EIA respondent name"""
    return BA_MAPPING.get(ba, ba)


def check_api_key():
    """Check if API key is valid by making a test request"""
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
        response = requests.get(EIA_API_URL, params=test_params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'response' in data:
            logging.info("API key is valid!")
            return True
        else:
            logging.error("API key may be invalid or API structure has changed")
            return False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Error checking API key: {e}")
        return False


def download_ba_data(ba, start_date, end_date, output_dir='data/raw', use_ba_folders=False):
    """
    Download hourly demand data for a specific balancing authority
    
    Parameters:
    - ba: Balancing authority code
    - start_date: Start date (YYYY-MM-DD format)
    - end_date: End date (YYYY-MM-DD format)
    - output_dir: Directory to save the data
    - use_ba_folders: Whether to create subfolders for each BA
    """
    
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
        'length': 5000
    }
    
    all_data = []
    
    try:
        while True:
            response = requests.get(EIA_API_URL, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if 'response' in data and 'data' in data['response']:
                records = data['response']['data']
                if not records:
                    break
                
                all_data.extend(records)
                
                # Check if there are more pages
                if len(records) < 5000:
                    break
                
                params['offset'] += 5000
            else:
                logging.warning(f"Unexpected response for {ba}")
                break
            
            # Rate limiting
            time.sleep(0.2)
            
    except Exception as e:
        logging.error(f"Error downloading {ba} from {start_date} to {end_date}: {e}")
        return None
    
    if all_data:
        # Create output path
        if use_ba_folders:
            save_dir = os.path.join(output_dir, ba)
            os.makedirs(save_dir, exist_ok=True)
            filename = f"{ba}_{start_date}_{end_date}_hourly_demand.csv"
        else:
            save_dir = output_dir
            os.makedirs(save_dir, exist_ok=True)
            filename = f"{get_eia_respondent_name(ba)}_hourly_demand.csv"
        
        output_file = os.path.join(save_dir, filename)
        
        # Convert to DataFrame and save
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False)
        
        logging.info(f"Saved {len(df)} records for {ba} to {output_file}")
        return df
    else:
        logging.warning(f"No data found for {ba}")
        return None


def download_ba_year_data(ba, year, output_dir='data/raw'):
    """Download one year of data for a specific BA (for parallel processing)"""
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    return download_ba_data(ba, start_date, end_date, output_dir, use_ba_folders=True)


def download_all_parallel(bas=None, start_year=2016, end_year=2024, output_dir='data/raw', max_workers=3):
    """Download data using parallel processing by BA-year combinations"""
    
    if bas is None:
        bas = BALANCING_AUTHORITIES
    
    years = list(range(start_year, end_year + 1))
    tasks = [(ba, year) for ba in bas for year in years]
    
    completed = 0
    failed = []
    
    # Use ThreadPoolExecutor for parallel downloads
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(download_ba_year_data, ba, year, output_dir): (ba, year) 
            for ba, year in tasks
        }
        
        # Process completed tasks
        with tqdm(total=len(tasks), desc="Downloading data") as pbar:
            for future in as_completed(future_to_task):
                ba, year = future_to_task[future]
                
                try:
                    result = future.result()
                    if result is not None:
                        completed += 1
                    else:
                        failed.append((ba, year))
                except Exception as e:
                    failed.append((ba, year))
                    logging.error(f"Failed to process {ba} {year}: {e}")
                
                pbar.update(1)
    
    # Summary
    print(f"\nDownload complete!")
    print(f"Successfully downloaded: {completed}/{len(tasks)}")
    
    if failed:
        print(f"\nFailed downloads ({len(failed)}):")
        for ba, year in failed[:10]:  # Show first 10
            print(f"  - {ba} {year}")
        if len(failed) > 10:
            print(f"  ... and {len(failed) - 10} more")


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Download EIA hourly demand data with flexible options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test download (default: 3 months of PJM data)
  python download_eia_data.py
  
  # Download specific date range for specific BAs
  python download_eia_data.py --bas PJM MISO --start 2023-01-01 --end 2023-12-31
  
  # Download all data for all BAs (2016-2024)
  python download_eia_data.py --all
  
  # Download all data using parallel processing
  python download_eia_data.py --all --parallel --workers 5
  
  # Download specific years
  python download_eia_data.py --years 2022 2023 2024
        """
    )
    
    # Date range options
    parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--years', type=int, nargs='+', help='Specific years to download')
    
    # BA selection
    parser.add_argument('--bas', type=str, nargs='+', help='Specific BAs to download')
    parser.add_argument('--all', action='store_true', help='Download all BAs for full date range (2016-2024)')
    
    # Processing options
    parser.add_argument('--parallel', action='store_true', help='Use parallel downloading')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    
    # Output options
    parser.add_argument('--output', type=str, default='data/raw', help='Output directory')
    parser.add_argument('--skip-existing', action='store_true', help='Skip existing files')
    
    return parser.parse_args()


def main():
    """Main function"""
    args = parse_arguments()
    
    # Check API key
    if not EIA_API_KEY:
        print("Error: EIA_API_KEY not found in environment")
        print("Please set your API key in the .env file")
        return
    
    # Test API key
    if not check_api_key():
        print("Please check your API key")
        return
    
    # Determine what to download
    if args.all:
        # Download everything
        bas = BALANCING_AUTHORITIES
        start_date = '2016-01-01'
        end_date = '2024-12-31'
        print(f"Downloading ALL data: {len(bas)} BAs from {start_date} to {end_date}")
        
        if args.parallel:
            download_all_parallel(bas, 2016, 2024, args.output, args.workers)
        else:
            # Sequential download
            for ba in tqdm(bas, desc="Downloading BAs"):
                download_ba_data(ba, start_date, end_date, args.output)
                time.sleep(1)  # Be nice to the API
                
    elif args.years:
        # Download specific years
        bas = args.bas if args.bas else BALANCING_AUTHORITIES
        print(f"Downloading {len(bas)} BAs for years: {args.years}")
        
        if args.parallel:
            for year in args.years:
                download_all_parallel(bas, year, year, args.output, args.workers)
        else:
            for year in args.years:
                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31"
                for ba in tqdm(bas, desc=f"Downloading {year}"):
                    download_ba_data(ba, start_date, end_date, args.output)
                    time.sleep(1)
                    
    else:
        # Default or custom date range
        if args.start and args.end:
            start_date = args.start
            end_date = args.end
            bas = args.bas if args.bas else BALANCING_AUTHORITIES
        else:
            # Default: 3 months of PJM data for testing
            start_date = '2023-10-01'
            end_date = '2023-12-31'
            bas = ['PJM'] if not args.bas else args.bas
            
        print(f"Downloading {len(bas)} BAs from {start_date} to {end_date}")
        
        for ba in tqdm(bas, desc="Downloading"):
            download_ba_data(ba, start_date, end_date, args.output)
            if len(bas) > 1:
                time.sleep(1)  # Be nice to the API
    
    print("\nDone!")


if __name__ == "__main__":
    main()