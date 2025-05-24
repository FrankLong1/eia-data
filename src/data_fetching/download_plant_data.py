#!/usr/bin/env python3
"""
EIA Plant-Level Data Download Script

Downloads monthly generation data for individual power plants from the EIA API.
Supports flexible download options including by plant ID, state, fuel type, and date ranges.

Note: EIA provides plant-level data at monthly granularity through the facility-fuel endpoint.
This data includes generation, consumption, and fuel receipts for each plant.
"""

# Standard library imports
import os
import argparse
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import json
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# EIA API configuration
EIA_API_URL = "https://api.eia.gov/v2/electricity/facility-fuel/data/"
EIA_API_KEY = os.environ.get('EIA_API_KEY')

# Common fuel types for filtering
FUEL_TYPES = {
    'NG': 'Natural Gas',
    'COL': 'Coal', 
    'NUC': 'Nuclear',
    'SUN': 'Solar',
    'WND': 'Wind',
    'WAT': 'Hydro',
    'OIL': 'Oil',
    'GEO': 'Geothermal',
    'BIO': 'Biomass',
    'OTH': 'Other'
}

# State abbreviations for filtering
STATES = [
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
]


def check_api_key():
    """
    Validate the EIA API key
    Returns:
        bool: True if API key is valid, False otherwise
    """
    test_params = {
        'api_key': EIA_API_KEY,
        'frequency': 'monthly',
        'data[0]': 'generation',
        'start': '2024-01',
        'end': '2024-01',
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


def get_plant_list(state=None, fuel_type=None):
    """
    Get list of available plants filtered by state and/or fuel type
    
    Args:
        state (str): State abbreviation to filter by
        fuel_type (str): Fuel type code to filter by
    
    Returns:
        list: List of plant IDs matching criteria
    """
    logging.info(f"Fetching plant list (state={state}, fuel_type={fuel_type})")
    
    # Use facility-fuel endpoint to get plant data
    # First do a test query to get plants
    params = {
        'api_key': EIA_API_KEY,
        'frequency': 'monthly',
        'data[0]': 'generation',
        'start': '2023-01',
        'end': '2023-01',
        'sort[0][column]': 'generation',
        'sort[0][direction]': 'desc',
        'offset': 0,
        'length': 5000
    }
    
    # Add filters if specified
    if state:
        params['facets[state][]'] = state
    if fuel_type:
        params['facets[fuel2002][]'] = fuel_type
    
    all_plants = set()
    
    while True:
        try:
            response = requests.get(EIA_API_URL, params=params, timeout=30)
            
            if response.status_code != 200:
                logging.error(f"HTTP {response.status_code}: {response.text[:200]}")
                break
                
            data = response.json()
            
            if 'response' not in data or 'data' not in data['response']:
                break
                
            records = data['response']['data']
            if not records:
                break
                
            # Extract unique plant IDs
            for record in records:
                if 'plantCode' in record:
                    all_plants.add(str(record['plantCode']))
            
            if len(records) < 5000:
                break
                
            params['offset'] += 5000
            time.sleep(0.1)
            
        except Exception as e:
            logging.error(f"Error fetching plant list: {e}")
            break
    
    plant_list = sorted(list(all_plants))
    logging.info(f"Found {len(plant_list)} unique plants")
    return plant_list


def download_plant_data(plant_id, start_date, end_date, data_type='generation', 
                       output_dir='plant_data/raw', skip_existing=False):
    """
    Download data for a specific plant
    
    Args:
        plant_id (str): Plant ID to download
        start_date (str): Start date in YYYY-MM format
        end_date (str): End date in YYYY-MM format  
        data_type (str): Type of data to download ('generation', 'consumption', 'receipts')
        output_dir (str): Directory to save the data
        skip_existing (bool): Whether to skip if file exists
    
    Returns:
        pd.DataFrame or None: Downloaded data if successful
    """
    # Create plant-specific directory
    save_dir = os.path.join(output_dir, str(plant_id))
    filename = f"{plant_id}_{data_type}_{start_date}_{end_date}.csv"
    output_file = os.path.join(save_dir, filename)
    
    # Check if file exists
    if skip_existing and os.path.exists(output_file):
        logging.info(f"File already exists, skipping: {output_file}")
        return pd.read_csv(output_file)
    
    # API parameters
    params = {
        'api_key': EIA_API_KEY,
        'frequency': 'monthly',
        'data[0]': data_type,
        'facets[plantCode][]': plant_id,
        'start': start_date,
        'end': end_date,
        'sort[0][column]': data_type,
        'sort[0][direction]': 'desc',
        'offset': 0,
        'length': 5000
    }
    
    all_data = []
    
    while True:
        try:
            response = requests.get(EIA_API_URL, params=params, timeout=30)
            
            if response.status_code != 200:
                logging.error(f"HTTP {response.status_code} for plant {plant_id}: {response.text}")
                return None
                
            data = response.json()
            
            if 'response' not in data or 'data' not in data['response']:
                logging.warning(f"Unexpected response structure for plant {plant_id}")
                return None
                
            records = data['response']['data']
            if not records:
                break
                
            all_data.extend(records)
            
            if len(records) < 5000:
                break
            else:
                params['offset'] += 5000
                
            time.sleep(0.1)
            
        except Exception as e:
            logging.error(f"Error downloading data for plant {plant_id}: {e}")
            return None
    
    if all_data:
        os.makedirs(save_dir, exist_ok=True)
        
        df = pd.DataFrame(all_data)
        df.to_csv(output_file, index=False)
        
        logging.info(f"Saved {len(df)} records for plant {plant_id} to {output_file}")
        return df
    else:
        logging.warning(f"No data found for plant {plant_id}")
        return None




def parse_arguments():
    """
    Parse command line arguments
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Download EIA plant-level data with flexible options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download data for specific plants
  python download_plant_data.py --plants 3 10 55876 --start 2023-01 --end 2023-12
  
  # Download all plants in a state
  python download_plant_data.py --state TX --start 2023-01 --end 2023-12
  
  # Download all plants with specific fuel type
  python download_plant_data.py --fuel NG --start 2023-01 --end 2023-12
  
  # Download plants in state with specific fuel type
  python download_plant_data.py --state CA --fuel SUN --start 2023-01 --end 2023-12
  
  # Download specific years
  python download_plant_data.py --plants 3 10 --years 2022 2023 2024
  
  # Download different data types (generation, consumption, receipts)
  python download_plant_data.py --plants 3 --start 2023-01 --end 2023-12 --data-type consumption
  
  # Skip existing files
  python download_plant_data.py --state TX --years 2023 --skip-existing
        """
    )
    
    # Date options
    parser.add_argument('--start', type=str,
                       help='Start date (YYYY-MM format for monthly data)')
    parser.add_argument('--end', type=str,
                       help='End date (YYYY-MM format for monthly data)')
    parser.add_argument('--years', type=int, nargs='+',
                       help='Download complete years (e.g., --years 2022 2023)')
    
    # Plant selection options
    parser.add_argument('--plants', type=str, nargs='+',
                       help='Specific plant IDs to download')
    parser.add_argument('--state', type=str, choices=STATES,
                       help='Download all plants in a state (2-letter code)')
    parser.add_argument('--fuel', type=str, choices=list(FUEL_TYPES.keys()),
                       help='Download all plants with specific fuel type')
    
    # Data options
    parser.add_argument('--data-type', type=str, default='generation',
                       choices=['generation', 'consumption', 'receipts'],
                       help='Type of data to download (default: generation)')
    
    # Output options
    parser.add_argument('--output', type=str, default='plant_data/raw',
                       help='Output directory (default: plant_data/raw)')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip downloading files that already exist')
    
    return parser.parse_args()


def main():
    """
    Main function to orchestrate plant data downloads
    """
    args = parse_arguments()
    
    # Validate API key
    if not EIA_API_KEY:
        print("Error: EIA_API_KEY not found in environment")
        print("Please set your API key in the .env file")
        return
    
    if not check_api_key():
        print("Please check your API key")
        return
    
    # Determine plant list
    plants = []
    
    if args.plants:
        # Specific plants requested
        plants = args.plants
        print(f"Downloading data for {len(plants)} specific plants")
        
    elif args.state or args.fuel:
        # Get plants by state and/or fuel type
        plants = get_plant_list(state=args.state, fuel_type=args.fuel)
        if not plants:
            print("No plants found matching criteria")
            return
        print(f"Found {len(plants)} plants matching criteria")
        
    else:
        print("Error: Must specify either --plants, --state, or --fuel")
        print("Use --help for examples")
        return
    
    # Determine date range
    if args.years:
        # Download by years
        for year in args.years:
            start_date = f"{year}-01"
            end_date = f"{year}-12"
            
            print(f"\nDownloading {args.data_type} data for {year}")
            for plant_id in tqdm(plants, desc=f"Plants ({year})"):
                download_plant_data(
                    plant_id, start_date, end_date,
                    data_type=args.data_type,
                    output_dir=args.output,
                    skip_existing=args.skip_existing
                )
                time.sleep(0.5)  # Rate limiting
                
    elif args.start and args.end:
        # Custom date range
        print(f"\nDownloading {args.data_type} data from {args.start} to {args.end}")
        
        for plant_id in tqdm(plants, desc="Plants"):
            download_plant_data(
                plant_id, args.start, args.end,
                data_type=args.data_type,
                output_dir=args.output,
                skip_existing=args.skip_existing
            )
            time.sleep(0.5)  # Rate limiting
            
    else:
        print("Error: Must specify either --start/--end or --years")
        print("Use --help for examples")
        return
    
    print("\nDownload complete!")


if __name__ == "__main__":
    main()