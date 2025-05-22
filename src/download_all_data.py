import os
import requests
import pandas as pd
from datetime import datetime
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

# Years to download (2016-2024)
YEARS = list(range(2016, 2025))

def download_ba_year_data(ba, year):
    """Download one year of data for a specific BA"""
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
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
                logging.warning(f"Unexpected response for {ba} {year}")
                break
            
            # Rate limiting
            time.sleep(0.2)
            
    except Exception as e:
        logging.error(f"Error downloading {ba} {year}: {e}")
        return None
    
    return all_data

def save_data(ba, year, data):
    """Save data to CSV file"""
    if not data:
        return False
    
    df = pd.DataFrame(data)
    
    # Create output directory if needed
    output_dir = f'data/raw/{ba}'
    os.makedirs(output_dir, exist_ok=True)
    
    # Save to CSV
    output_file = f'{output_dir}/{ba}_{year}_hourly_demand.csv'
    df.to_csv(output_file, index=False)
    
    logging.info(f"Saved {len(df)} records for {ba} {year}")
    return True

def download_all_data():
    """Download all data using parallel processing"""
    
    # Create list of all BA-year combinations
    tasks = [(ba, year) for ba in BALANCING_AUTHORITIES for year in YEARS]
    
    completed = 0
    failed = []
    
    # Use ThreadPoolExecutor for parallel downloads
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(download_ba_year_data, ba, year): (ba, year) 
            for ba, year in tasks
        }
        
        # Process completed tasks
        with tqdm(total=len(tasks), desc="Downloading data") as pbar:
            for future in as_completed(future_to_task):
                ba, year = future_to_task[future]
                
                try:
                    data = future.result()
                    if data:
                        save_data(ba, year, data)
                        completed += 1
                    else:
                        failed.append((ba, year))
                        logging.warning(f"No data for {ba} {year}")
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

def check_existing_data():
    """Check what data has already been downloaded"""
    existing = []
    
    for ba in BALANCING_AUTHORITIES:
        ba_dir = f'data/raw/{ba}'
        if os.path.exists(ba_dir):
            for year in YEARS:
                file_path = f'{ba_dir}/{ba}_{year}_hourly_demand.csv'
                if os.path.exists(file_path):
                    existing.append((ba, year))
    
    return existing

def main():
    """Main function"""
    
    # Check API key
    if not EIA_API_KEY:
        print("Error: EIA_API_KEY not found in environment")
        return
    
    # Check existing data
    existing = check_existing_data()
    if existing:
        print(f"Found {len(existing)} existing files")
        response = input("Skip existing files? (y/n): ")
        if response.lower() == 'y':
            # Filter out existing tasks
            global BALANCING_AUTHORITIES, YEARS
            existing_set = set(existing)
            tasks = [(ba, year) for ba in BALANCING_AUTHORITIES for year in YEARS 
                     if (ba, year) not in existing_set]
            
            if not tasks:
                print("All data already downloaded!")
                return
            
            # Update globals for download
            BALANCING_AUTHORITIES = list(set(ba for ba, _ in tasks))
            YEARS = list(set(year for _, year in tasks))
    
    # Start download
    print(f"\nDownloading data for {len(BALANCING_AUTHORITIES)} BAs and {len(YEARS)} years")
    download_all_data()

if __name__ == "__main__":
    main()