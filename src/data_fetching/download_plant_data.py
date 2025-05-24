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
import pandas as pd
from datetime import datetime, timedelta
import time
from tqdm import tqdm
import logging

# Import shared utilities
from ..utils import (
    FUEL_TYPES, STATES, 
    validate_api_key, make_eia_request
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# EIA API endpoint for plant data
PLANT_DATA_ENDPOINT = "electricity/facility-fuel/data/"


def get_plant_list_with_metadata(state=None, fuel_type=None):
    """
    Get list of available plants with metadata filtered by state and/or fuel type
    
    Args:
        state (str): State abbreviation to filter by
        fuel_type (str): Fuel type code to filter by
    
    Returns:
        dict: Dictionary mapping plant IDs to their metadata (state, name)
    """
    logging.info(f"Fetching plant list with metadata (state={state}, fuel_type={fuel_type})")
    
    # Use facility-fuel endpoint to get plant data
    params = {
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
    
    plant_metadata = {}
    
    while True:
        data = make_eia_request(PLANT_DATA_ENDPOINT, params)
        
        if not data or 'response' not in data or 'data' not in data['response']:
            break
            
        records = data['response']['data']
        if not records:
            break
            
        # Extract plant metadata
        for record in records:
            if 'plantCode' in record:
                plant_id = str(record['plantCode'])
                if plant_id not in plant_metadata:
                    plant_metadata[plant_id] = {
                        'state': record.get('state', 'Unknown'),
                        'name': record.get('plantName', 'Unknown'),
                        'state_desc': record.get('stateDescription', 'Unknown')
                    }
        
        if len(records) < 5000:
            break
            
        params['offset'] += 5000
        time.sleep(0.1)
    
    logging.info(f"Found {len(plant_metadata)} unique plants")
    return plant_metadata


def download_plant_data(plant_id, start_date, end_date, data_type='generation', 
                       output_dir='plant_data/raw', skip_existing=False, state=None):
    """
    Download data for a specific plant
    
    Args:
        plant_id (str): Plant ID to download
        start_date (str): Start date in YYYY-MM format
        end_date (str): End date in YYYY-MM format  
        data_type (str): Type of data to download ('generation', 'consumption', 'receipts')
        output_dir (str): Directory to save the data
        skip_existing (bool): Whether to skip if file exists
        state (str): State code for organizing output directory
    
    Returns:
        pd.DataFrame or None: Downloaded data if successful
    """
    # Create state directory structure (no plant subdirectory)
    if state:
        save_dir = os.path.join(output_dir, state)
    else:
        save_dir = output_dir
    
    # Include plant ID in filename
    filename = f"{plant_id}_{data_type}_{start_date}_{end_date}.csv"
    output_file = os.path.join(save_dir, filename)
    
    # Check if file exists
    if skip_existing and os.path.exists(output_file):
        logging.info(f"File already exists, skipping: {output_file}")
        return pd.read_csv(output_file)
    
    # API parameters
    params = {
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
        data = make_eia_request(PLANT_DATA_ENDPOINT, params)
        
        if not data or 'response' not in data or 'data' not in data['response']:
            if not all_data:  # Only warn if we got no data at all
                logging.warning(f"No data found for plant {plant_id}")
            break
            
        records = data['response']['data']
        if not records:
            break
            
        all_data.extend(records)
        
        if len(records) < 5000:
            break
        else:
            params['offset'] += 5000
            
        time.sleep(0.1)
    
    if all_data:
        os.makedirs(save_dir, exist_ok=True)
        
        df = pd.DataFrame(all_data)
        
        # Convert period to datetime for sorting
        df['period'] = pd.to_datetime(df['period'], format='%Y-%m')
        
        # Sort by period (chronological order) and then by other columns for consistency
        df = df.sort_values(['period', 'fuel2002', 'primeMover'], na_position='last')
        
        # Convert period back to string format
        df['period'] = df['period'].dt.strftime('%Y-%m')
        
        # Save to CSV
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
  
  # Download plants in multiple states (organized by state folders)
  python download_plant_data.py --states TX CA --years 2023
  
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
    parser.add_argument('--states', type=str, nargs='+', choices=STATES,
                       help='Download all plants in multiple states (2-letter codes)')
    parser.add_argument('--fuel', type=str, choices=list(FUEL_TYPES.keys()),
                       help='Download all plants with specific fuel type')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of plants per state (for testing)')
    
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
    if not validate_api_key():
        return
    
    # Determine plant list and metadata
    plant_metadata = {}
    
    if args.plants:
        # Specific plants requested - we'll get their state info later
        for plant_id in args.plants:
            plant_metadata[plant_id] = {'state': None, 'name': 'Unknown'}
        print(f"Downloading data for {len(args.plants)} specific plants")
        
    elif args.states:
        # Multiple states requested
        print(f"Fetching plants for states: {', '.join(args.states)}")
        for state in args.states:
            state_plants = get_plant_list_with_metadata(state=state, fuel_type=args.fuel)
            plant_metadata.update(state_plants)
            print(f"  {state}: {len([p for p in state_plants.values() if p['state'] == state])} plants")
        
    elif args.state:
        # Single state requested
        plant_metadata = get_plant_list_with_metadata(state=args.state, fuel_type=args.fuel)
        print(f"Found {len(plant_metadata)} plants in {args.state}")
        
    elif args.fuel:
        # Fuel type only
        plant_metadata = get_plant_list_with_metadata(fuel_type=args.fuel)
        print(f"Found {len(plant_metadata)} {args.fuel} plants")
        
    else:
        print("Error: Must specify either --plants, --state, --states, or --fuel")
        print("Use --help for examples")
        return
    
    if not plant_metadata:
        print("No plants found matching criteria")
        return
    
    # If we have specific plants without state info, try to get their metadata
    if args.plants and any(p['state'] is None for p in plant_metadata.values()):
        print("Fetching metadata for specified plants...")
        all_metadata = get_plant_list_with_metadata()
        for plant_id in args.plants:
            if plant_id in all_metadata:
                plant_metadata[plant_id] = all_metadata[plant_id]
    
    # Apply limit if specified
    if args.limit and args.states:
        print(f"\nLimiting to {args.limit} plants per state...")
        limited_metadata = {}
        for state in args.states:
            state_plants = {pid: meta for pid, meta in plant_metadata.items() 
                          if meta.get('state') == state}
            # Take first N plants from each state
            for i, (pid, meta) in enumerate(state_plants.items()):
                if i < args.limit:
                    limited_metadata[pid] = meta
        plant_metadata = limited_metadata
    
    # Show summary by state
    state_counts = {}
    for plant_id, metadata in plant_metadata.items():
        state = metadata.get('state', 'Unknown')
        state_counts[state] = state_counts.get(state, 0) + 1
    
    print("\nPlants by state:")
    for state, count in sorted(state_counts.items()):
        print(f"  {state}: {count} plants")
    
    # Determine date range
    if args.years:
        # Download by years
        for year in args.years:
            start_date = f"{year}-01"
            end_date = f"{year}-12"
            
            print(f"\nDownloading {args.data_type} data for {year}")
            for plant_id, metadata in tqdm(plant_metadata.items(), 
                                          desc=f"Plants ({year})"):
                download_plant_data(
                    plant_id, start_date, end_date,
                    data_type=args.data_type,
                    output_dir=args.output,
                    skip_existing=args.skip_existing,
                    state=metadata.get('state')
                )
                time.sleep(0.5)  # Rate limiting
                
    elif args.start and args.end:
        # Custom date range
        print(f"\nDownloading {args.data_type} data from {args.start} to {args.end}")
        
        for plant_id, metadata in tqdm(plant_metadata.items(), desc="Plants"):
            download_plant_data(
                plant_id, args.start, args.end,
                data_type=args.data_type,
                output_dir=args.output,
                skip_existing=args.skip_existing,
                state=metadata.get('state')
            )
            time.sleep(0.5)  # Rate limiting
            
    else:
        print("Error: Must specify either --start/--end or --years")
        print("Use --help for examples")
        return
    
    print("\nDownload complete!")
    print(f"Data saved to: {args.output}/[STATE]/[PLANT_ID]_generation_[dates].csv")


if __name__ == "__main__":
    main()