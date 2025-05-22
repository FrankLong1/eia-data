import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# EIA API configuration
EIA_API_URL = "https://api.eia.gov/v2/electricity/rto/region-data/data/"
EIA_API_KEY = os.environ.get('EIA_API_KEY')

# Test with just a few BAs first
TEST_BAS = ['PJM', 'MISO', 'ERCO']

def download_ba_data(ba, year):
    """Download one year of data for a BA"""
    
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    print(f"  Downloading {ba} for {year}...")
    
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
    total_records = 0
    
    while True:
        try:
            response = requests.get(EIA_API_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'response' in data and 'data' in data['response']:
                records = data['response']['data']
                if not records:
                    break
                
                all_data.extend(records)
                total_records += len(records)
                
                print(f"    Retrieved {len(records)} records (total: {total_records})")
                
                # Check if there are more pages
                if len(records) < 5000:
                    break
                
                params['offset'] += 5000
                
            else:
                print(f"    Unexpected response structure")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"    Error: {e}")
            break
        
        # Be nice to the API
        time.sleep(0.5)
    
    return all_data

def main():
    """Download test data"""
    
    os.makedirs('data/raw', exist_ok=True)
    
    # Test with 2023 data for 3 BAs
    year = 2023
    
    for ba in TEST_BAS:
        print(f"\nProcessing {ba}...")
        
        data = download_ba_data(ba, year)
        
        if data:
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Save to CSV
            output_file = f'data/raw/{ba}_{year}_hourly_demand.csv'
            df.to_csv(output_file, index=False)
            print(f"  Saved {len(df)} records to {output_file}")
            
            # Show sample data
            print(f"  Sample data:")
            print(df.head())
            
        time.sleep(1)
    
    print("\nTest download complete!")

if __name__ == "__main__":
    main()