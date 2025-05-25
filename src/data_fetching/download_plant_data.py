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
import requests
import zipfile
import io

TIME_BETWEEN_REQUESTS = 0.1

# Import shared utilities
from ..utils import (
    FUEL_TYPES, STATES, 
    validate_api_key, make_eia_request
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# EIA API endpoint for plant data
PLANT_DATA_ENDPOINT = "electricity/facility-fuel/data/"

# EIA API endpoint for plant location data (operating generator capacity includes lat/long)
PLANT_LOCATION_ENDPOINT = "electricity/operating-generator-capacity/data/"


def download_eia860_plant_data(year=2023, cache_dir='plant_data/eia860_cache'):
    """
    Download and parse EIA-860 plant data including lat/long and ownership info.
    
    Args:
        year (int): Year of data to download
        cache_dir (str): Directory to cache the downloaded data
    
    Returns:
        dict: Dictionary with plant data including coordinates and ownership
    """
    import json
    
    # Check cache first
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f'eia860_{year}_plant_data.json')
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                logging.info(f"Loading EIA-860 data from cache: {cache_file}")
                return json.load(f)
        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
    
    logging.info(f"Downloading EIA-860 data for year {year}")
    
    # EIA-860 download URL pattern
    url = f"https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"
    
    try:
        # Download the zip file
        response = requests.get(url)
        response.raise_for_status()
        
        # Extract and read the Plant file
        with zipfile.ZipFile(io.BytesIO(response.content)) as z:
            plant_data = {}
            
            # Look for the Plant file (usually named 2___Plant_Y[Year].xlsx)
            plant_file = None
            for filename in z.namelist():
                if '2___Plant' in filename and filename.endswith('.xlsx'):
                    plant_file = filename
                    break
                    
            # Debug: show all files in the zip
            logging.info(f"Files in EIA-860 zip: {z.namelist()}")
            
            if plant_file:
                logging.info(f"Reading plant data from {plant_file}")
                with z.open(plant_file) as f:
                    # Read the Excel file, skipping the first row which is a header
                    df = pd.read_excel(f, engine='openpyxl', skiprows=1)
                    
                    # Log available columns for debugging
                    logging.info(f"First few columns in Plant file: {list(df.columns)[:10]}")
                    
                    # Try different possible column names for plant ID
                    plant_id_col = None
                    for col in ['Plant Code', 'Plant ID', 'PlantCode', 'PlantID', 'plant_id']:
                        if col in df.columns:
                            plant_id_col = col
                            break
                    
                    if not plant_id_col:
                        logging.warning(f"Could not find plant ID column. Available columns: {list(df.columns)}")
                        return plant_data
                    
                    # Extract relevant columns (with flexible column name matching)
                    for _, row in df.iterrows():
                        plant_id = str(row.get(plant_id_col, ''))
                        if plant_id and plant_id != 'nan':
                            plant_data[plant_id] = {
                                'latitude': row.get('Latitude') or row.get('latitude') or row.get('LAT'),
                                'longitude': row.get('Longitude') or row.get('longitude') or row.get('LON'),
                                'county': row.get('County') or row.get('county'),
                                'zip_code': row.get('Zip') or row.get('Zip Code') or row.get('ZIP'),
                                'street_address': row.get('Street Address') or row.get('Street_Address'),
                                'city': row.get('City') or row.get('city'),
                                'balancing_authority_code_eia': row.get('Balancing Authority Code') or row.get('BA Code'),
                                'balancing_authority_name_eia': row.get('Balancing Authority Name') or row.get('BA Name'),
                                'nerc_region': row.get('NERC Region') or row.get('NERC_Region'),
                                'primary_purpose': row.get('Primary Purpose NAICS Code') or row.get('Primary_Purpose')
                            }
            
            # Look for the Owner file (usually named 4___Owner_Y[Year].xlsx)
            owner_file = None
            for filename in z.namelist():
                if '4___Owner' in filename and filename.endswith('.xlsx'):
                    owner_file = filename
                    break
            
            if owner_file:
                logging.info(f"Reading ownership data from {owner_file}")
                with z.open(owner_file) as f:
                    # Read the Excel file, skipping the first row which is a header
                    df_owner = pd.read_excel(f, engine='openpyxl', skiprows=1)
                    
                    # Log available columns for debugging
                    logging.info(f"First few columns in Owner file: {list(df_owner.columns)[:10]}")
                    
                    # Find plant ID column
                    plant_id_col = None
                    for col in ['Plant Code', 'Plant ID', 'PlantCode', 'PlantID', 'plant_id']:
                        if col in df_owner.columns:
                            plant_id_col = col
                            break
                    
                    if plant_id_col:
                        # Aggregate ownership data by plant
                        for _, row in df_owner.iterrows():
                            plant_id = str(row.get(plant_id_col, ''))
                            if plant_id and plant_id != 'nan' and plant_id in plant_data:
                                if 'owners' not in plant_data[plant_id]:
                                    plant_data[plant_id]['owners'] = []
                                
                                owner_name = row.get('Owner Name') or row.get('Owner_Name') or row.get('owner_name')
                                percent = row.get('Percent Owned') or row.get('Percent_Owned') or row.get('percent_owned')
                                
                                if owner_name:
                                    plant_data[plant_id]['owners'].append({
                                        'name': owner_name,
                                        'percent_owned': percent
                                    })
            
            logging.info(f"Successfully loaded EIA-860 data for {len(plant_data)} plants")
            
            # Save to cache
            try:
                with open(cache_file, 'w') as f:
                    json.dump(plant_data, f)
                logging.info(f"Saved EIA-860 data to cache: {cache_file}")
            except Exception as e:
                logging.warning(f"Failed to save cache: {e}")
            
            return plant_data
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download EIA-860 data: {e}")
        return {}
    except Exception as e:
        logging.error(f"Error processing EIA-860 data: {e}")
        import traceback
        traceback.print_exc()
        return {}


def get_plant_location_data(plant_ids):
    """
    Fetch location and balancing authority data for given plant IDs from operating-generator-capacity endpoint.
    
    Args:
        plant_ids (list): List of plant IDs to fetch location data for
    
    Returns:
        dict: Dictionary mapping plant IDs to their location and BA data
    """
    logging.info(f"Fetching location data for {len(plant_ids)} plants")
    
    # This endpoint provides BA information and other metadata
    params = {
        'frequency': 'monthly',
        'data[0]': 'nameplate-capacity-mw',
        'start': '2023-01',  # Use recent data
        'end': '2023-01',
        'sort[0][column]': 'plantid',
        'sort[0][direction]': 'asc',
        'offset': 0,
        'length': 5000
    }
    
    location_data = {}
    
    # Fetch data from API
    while True:
        data = make_eia_request(PLANT_LOCATION_ENDPOINT, params)
        
        if not data or 'response' not in data or 'data' not in data['response']:
            break
            
        records = data['response']['data']
        if not records:
            break
            
        # Extract location and BA data
        for record in records:
            plant_id = str(record.get('plantid', ''))
            
            if plant_id in plant_ids and plant_id not in location_data:
                location_data[plant_id] = {
                    'balancing_authority_code': record.get('balancing_authority_code'),
                    'balancing_authority_name': record.get('balancing-authority-name'),
                    'entity_name': record.get('entityName'),
                    'entity_id': record.get('entityid'),
                    'sector': record.get('sector'),
                    'technology': record.get('technology')
                }
        
        # Check if we've found all plants we're looking for
        if len(location_data) >= len(plant_ids):
            break
            
        if len(records) < 5000:
            break
            
        params['offset'] += 5000
        time.sleep(0.1)
    
    logging.info(f"Found location data for {len(location_data)} plants")
    return location_data


def get_plant_list_with_metadata(states=None, fuel_type=None):
    """
    Get list of available plants with metadata filtered by state and/or fuel type.
    
    Args:
        states (list): List of state abbreviations to filter by
        fuel_type (str): Fuel type code to filter by
    
    Returns:
        dict: Dictionary mapping plant IDs to their metadata (state, name)
    """
    logging.info(f"Fetching plant list with metadata (state={states}, fuel_type={fuel_type})")
    
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
    if states:
        params['facets[state][]'] = states
    if fuel_type:
        params['facets[fuel2002][]'] = fuel_type
    
    plant_metadata = {}
    
    # Fetch data from API
    while True:
        data = make_eia_request(PLANT_DATA_ENDPOINT, params)
        records = data.get('response', {}).get('data', []) if data else []
        
        if not records:
            break
            
        # Extract plant metadata
        for record in records:
            plant_id = str(record.get('plantCode', ''))
            # Skip if plant ID is not found or already in metadata
            if not plant_id or plant_id in plant_metadata:
                continue
                
            plant_metadata[plant_id] = {
                'state': record.get('state', 'Unknown'),
                'name': record.get('plantName', 'Unknown'),
                'state_desc': record.get('stateDescription', 'Unknown')
            }
        
        if len(records) < 5000:
            break
            
        params['offset'] += 5000
        time.sleep(TIME_BETWEEN_REQUESTS)
    
    return plant_metadata


def limit_plant_list(plant_metadata, states=None, limit=None):
    """
    Limit the number of plants per state in the plant metadata.
    
    Args:
        plant_metadata (dict): Dictionary mapping plant IDs to their metadata
        states (list): Optional list of states to filter by
        limit (int): Maximum number of plants per state
    
    Returns:
        dict: Limited dictionary of plant metadata
    """
    if not limit:
        return plant_metadata
        
    print(f"\nLimiting to {limit} plants per state...")
    
    # Group plants by state
    plants_by_state = {}
    for pid, meta in plant_metadata.items():
        state_code = meta.get('state')
        # If states specified, only include those states
        if states and state_code not in states:
            continue
            
        if state_code not in plants_by_state:
            plants_by_state[state_code] = []
        plants_by_state[state_code].append((pid, meta))
    
    # Take first N plants from each state
    limited_metadata = {}
    for state_code, plants in plants_by_state.items():
        for pid, meta in plants[:limit]:
            limited_metadata[pid] = meta
            
    return limited_metadata


def download_plant_data(plant_id, start_date, end_date, data_type='generation', 
                       output_dir='plant_data/raw', skip_existing=False, state=None,
                       location_data=None, eia860_data=None):
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
        location_data (dict): Optional location/BA data to merge with plant data
        eia860_data (dict): Optional EIA-860 data with lat/long and ownership info
    
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
        
        # Add location/BA data from operating-generator-capacity if available
        if location_data and plant_id in location_data:
            loc_info = location_data[plant_id]
            for key, value in loc_info.items():
                df[key] = value
        
        # Add EIA-860 data if available (lat/long, ownership, etc.)
        if eia860_data and plant_id in eia860_data:
            eia_info = eia860_data[plant_id]
            for key, value in eia_info.items():
                if key == 'owners':
                    # Convert owners list to a string representation
                    if value:
                        owner_strings = [f"{o['name']} ({o['percent_owned']}%)" for o in value if o['name']]
                        df['owners'] = '; '.join(owner_strings)
                    else:
                        df['owners'] = ''  # Empty string for no owners
                elif key in ['latitude', 'longitude'] and pd.notna(value):
                    df[key] = value
                else:
                    df[key] = value
            
            # Always add owners column even if empty
            if 'owners' not in df.columns:
                df['owners'] = ''
            
            # Add lat/long tuple column if both coordinates are available
            lat = eia_info.get('latitude')
            lng = eia_info.get('longitude')
            if pd.notna(lat) and pd.notna(lng):
                df['lat_lng_tuple'] = f"({lat}, {lng})"
            else:
                df['lat_lng_tuple'] = None
        
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
  # Download all plants in a state  
  python download_plant_data.py --states TX --start 2023-01 --end 2023-12
  
  # Download plants in multiple states (organized by state folders)
  python download_plant_data.py --states TX CA --years 2023
  
  # Download all plants with specific fuel type
  python download_plant_data.py --fuel NG --start 2023-01 --end 2023-12
  
  # Download plants in state with specific fuel type
  python download_plant_data.py --states CA --fuel SUN --start 2023-01 --end 2023-12
  
  # Download specific years
  python download_plant_data.py --states TX --years 2022 2023 2024
  
  # Download different data types (generation, consumption, receipts)
  python download_plant_data.py --states TX --start 2023-01 --end 2023-12 --data-type consumption
  
  # Skip existing files
  python download_plant_data.py --states TX --years 2023 --skip-existing
  
Note: Data is automatically enriched with:
  - Balancing authority assignments
  - Latitude/longitude coordinates
  - Ownership information
  - Additional plant characteristics from EIA-860
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
    parser.add_argument('--states', type=str, nargs='+', choices=STATES,
                       help='Download all plants in one or more states (2-letter codes)')
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
    args = parse_arguments()
    
    # Validate API key
    if not validate_api_key():
        return
    
    # Get relevant plants
    plant_metadata = get_plant_list_with_metadata(
        states=args.states,
        fuel_type=args.fuel
    )
    if not plant_metadata:
        return
        
    # Apply limit if specified before downloading 
    if args.limit:
        plant_metadata = limit_plant_list(plant_metadata, states=args.states, limit=args.limit)
    
    print("  - Fetching balancing authority data from API...")
    location_data = get_plant_location_data(list(plant_metadata.keys()))
    print(f"    Found BA data for {len(location_data)} plants")
    
    # Get detailed plant data from EIA-860 files using the most recent year from the date range
    year = int(args.end.split('-')[0] if args.end else args.years[-1] if args.years else 2023)
    eia860_data = download_eia860_plant_data(year)
    print(f"    Found EIA-860 data for {len(eia860_data)} plants")
    
    # Download data for found plants
    if args.years:
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
                    state=metadata.get('state'),
                    location_data=location_data,
                    eia860_data=eia860_data
                )
                time.sleep(TIME_BETWEEN_REQUESTS)  # Rate limiting
                
    elif args.start and args.end:
        print(f"\nDownloading {args.data_type} data from {args.start} to {args.end}")
        for plant_id, metadata in tqdm(plant_metadata.items(), desc="Plants"):
            download_plant_data(
                plant_id, args.start, args.end,
                data_type=args.data_type,
                output_dir=args.output,
                skip_existing=args.skip_existing,
                state=metadata.get('state'),
                location_data=location_data,
                eia860_data=eia860_data
            )
            time.sleep(TIME_BETWEEN_REQUESTS)  # Rate limiting
            
    else:
        print("Error: Must specify either --start/--end or --years")
        print("Use --help for examples")
        return
    
    print("\nDownload complete!")


if __name__ == "__main__":
    main()