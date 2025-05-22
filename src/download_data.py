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
EIA_API_KEY = os.environ.get('EIA_API_KEY', 'YOUR_API_KEY_HERE')

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

def download_hourly_data(ba, start_date, end_date, output_dir):
    """
    Download hourly demand data for a specific balancing authority
    
    Parameters:
    - ba: Balancing authority code
    - start_date: Start date (YYYY-MM-DD format)
    - end_date: End date (YYYY-MM-DD format)
    - output_dir: Directory to save the data
    """
    
    # EIA API parameters
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
                
                # Check if there are more pages
                if len(records) < 5000:
                    break
                
                params['offset'] += 5000
                
            else:
                print(f"Unexpected response structure for {ba}: {data}")
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error downloading data for {ba}: {e}")
            break
        
        # Be nice to the API
        time.sleep(0.5)
    
    if all_data:
        # Convert to DataFrame
        df = pd.DataFrame(all_data)
        
        # Save to CSV
        output_file = os.path.join(output_dir, f'{get_eia_respondent_name(ba)}_hourly_demand.csv')
        df.to_csv(output_file, index=False)
        print(f"Saved {len(df)} records for {ba} to {output_file}")
        
        return df
    else:
        print(f"No data found for {ba}")
        return None

def check_api_key():
    """Check if API key is valid by making a test request"""
    test_params = {
        'api_key': EIA_API_KEY,
        'frequency': 'hourly',
        'data[0]': 'value',
        'facets[respondent][]': 'PJM',
        'start': '2024-01-01',
        'end': '2024-01-01',
        'length': 1
    }
    
    try:
        response = requests.get(EIA_API_URL, params=test_params)
        response.raise_for_status()
        data = response.json()
        
        if 'response' in data:
            print("API key is valid!")
            return True
        else:
            print("API key may be invalid or API structure has changed")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Error checking API key: {e}")
        return False

def main():
    """Main function to download all data"""
    
    # Check for API key
    if EIA_API_KEY == 'YOUR_API_KEY_HERE':
        print("Please set your EIA API key in the environment variable EIA_API_KEY")
        print("You can get a free API key from: https://www.eia.gov/opendata/register.php")
        return
    
    # Test API key
    if not check_api_key():
        print("Please check your API key")
        return
    
    # Create output directory
    output_dir = 'data/raw'
    os.makedirs(output_dir, exist_ok=True)
    
    # Date range from the paper
    start_date = '2016-01-01'
    end_date = '2024-12-31'
    
    print(f"Downloading hourly demand data from {start_date} to {end_date}")
    
    # Download data for each balancing authority
    for ba in tqdm(BALANCING_AUTHORITIES, desc="Downloading BA data"):
        print(f"\nDownloading data for {ba}...")
        download_hourly_data(ba, start_date, end_date, output_dir)
        
        # Be nice to the API - wait between BAs
        time.sleep(1)
    
    print("\nDownload complete!")

if __name__ == "__main__":
    main()