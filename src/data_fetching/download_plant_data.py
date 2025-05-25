#!/usr/bin/env python3
"""
EIA Plant-Level Data Download Script

Downloads monthly generation data for individual power plants from the EIA API.
Supports flexible download options including by plant ID, state, fuel type, and year ranges.

Data Organization:
- Time-series data: Saved to plant_data/raw_plant_generation_data/STATE/{PLANT_ID}_{YEAR}_{data_type}.csv
- Plant metadata: Saved to plant_data/plant_lookup.csv (location, BA, ownership)

File naming format:
- Example: 1001_2023_generation.csv (Plant ID 1001, year 2023, generation data)

Naming conventions:
- plant_list: Basic plant info (ID, name, state) from initial API query
- complete_metadata: Enriched data including coordinates, BA, ownership
- location_ownership_data: Data from EIA-860 files (lat/long, owners)
- ba_data: Balancing authority assignments from operating-generator-capacity API
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
import json

TIME_BETWEEN_REQUESTS = 0.0

# Import shared utilities
from ..utils import (
    FUEL_TYPES, STATES, 
    validate_api_key, make_eia_request,
    EIA860_URL_PATTERN
)

# Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# EIA API endpoint for plant data
PLANT_DATA_ENDPOINT = "electricity/facility-fuel/data/"

# EIA API endpoint for plant location data (operating generator capacity includes lat/long)
PLANT_LOCATION_ENDPOINT = "electricity/operating-generator-capacity/data/"


def _download_eia860_zip(year):
    """Download EIA-860 zip file if not cached."""
    download_dir = 'plant_data/eia860_downloads'
    os.makedirs(download_dir, exist_ok=True)
    zip_path = os.path.join(download_dir, f'eia860_{year}.zip')
    
    if os.path.exists(zip_path):
        logging.info(f"Using cached EIA-860 zip from {zip_path}")
        return zip_path
    
    logging.info(f"Downloading EIA-860 data for year {year}")
    url = EIA860_URL_PATTERN.format(year=year)
    
    response = requests.get(url)
    response.raise_for_status()
    
    with open(zip_path, 'wb') as f:
        f.write(response.content)
    logging.info(f"Saved EIA-860 zip to {zip_path}")
    return zip_path


def _parse_plant_file(zipf, plant_file):
    """Parse plant location data from EIA-860 plant file."""
    if not plant_file:
        raise ValueError("No plant file provided")
        
    logging.info(f"Reading plant data from {plant_file}")
    
    with zipf.open(plant_file) as f:
        df = pd.read_excel(f, engine='openpyxl', skiprows=1)
    
    # Find plant ID column
    plant_id_col = None
    for col in ['Plant Code', 'Plant ID', 'PlantCode', 'PlantID']:
        if col in df.columns:
            plant_id_col = col
            break
    
    if not plant_id_col:
        raise ValueError(f"Could not find plant ID column in {plant_file}. Available: {list(df.columns)[:10]}")
    
    # Extract plant data
    plant_data = {}
    for _, row in df.iterrows():
        plant_id = str(row.get(plant_id_col, ''))
        if not plant_id or plant_id == 'nan':
            continue
            
        plant_data[plant_id] = {
            'latitude': row.get('Latitude'),
            'longitude': row.get('Longitude'),
            'county': row.get('County'),
            'zip_code': row.get('Zip') or row.get('Zip Code'),
            'street_address': row.get('Street Address'),
            'city': row.get('City'),
            'balancing_authority_code_eia': row.get('Balancing Authority Code'),
            'balancing_authority_name_eia': row.get('Balancing Authority Name'),
            'nerc_region': row.get('NERC Region'),
            'primary_purpose': row.get('Primary Purpose NAICS Code')
        }
    
    return plant_data


def _parse_owner_file(zipf, owner_file, plant_data):
    """Parse ownership data from EIA-860 owner file."""
    if not owner_file or not plant_data:
        return
        
    logging.info(f"Reading ownership data from {owner_file}")
    
    with zipf.open(owner_file) as f:
        df = pd.read_excel(f, engine='openpyxl', skiprows=1)
    
    # Find plant ID column
    plant_id_col = None
    for col in ['Plant Code', 'Plant ID', 'PlantCode', 'PlantID']:
        if col in df.columns:
            plant_id_col = col
            break
    
    if not plant_id_col:
        logging.warning(f"Could not find plant ID column in {owner_file}")
        return
    
    # Add ownership data
    for _, row in df.iterrows():
        plant_id = str(row.get(plant_id_col, ''))
        if not plant_id or plant_id == 'nan' or plant_id not in plant_data:
            continue
        
        if 'owners' not in plant_data[plant_id]:
            plant_data[plant_id]['owners'] = []
        
        owner_name = row.get('Owner Name')
        percent = row.get('Percent Owned')
        
        if owner_name:
            plant_data[plant_id]['owners'].append({
                'name': owner_name,
                'percent_owned': percent
            })


def fetch_eia860_location_ownership_data(year=2023):
    """
    Fetch location (lat/long) and ownership data from EIA-860 dataset.
    
    Args:
        year (int): Year of data to download
    
    Returns:
        dict: Dictionary mapping plant IDs to location/ownership data
    """
    # Download zip file
    try:
        zip_path = _download_eia860_zip(year)
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to download EIA-860 data: {e}")
        return {}
    
    # Open and process zip file
    with zipfile.ZipFile(zip_path) as z:
        # Find relevant files
        plant_file = next((filename for filename in z.namelist() 
                           if '2___Plant' in filename and filename.endswith('.xlsx')), None)
        owner_file = next((filename for filename in z.namelist() 
                           if '4___Owner' in filename and filename.endswith('.xlsx')), None)
        
        # Parse plant location data
        try:
            plant_data = _parse_plant_file(z, plant_file)
        except Exception as e:
            logging.error(f"Failed to parse plant file: {e}")
            return {}
        
        # Parse ownership data (optional - don't fail if missing)
        try:
            _parse_owner_file(z, owner_file, plant_data)
        except Exception as e:
            logging.warning(f"Failed to parse owner file (continuing without ownership data): {e}")
        
        logging.info(f"Successfully loaded EIA-860 data for {len(plant_data)} plants")
        return plant_data


def fetch_balancing_authority_data(plant_ids):
    """
    Fetch BA and entity data from operating-generator-capacity endpoint.
    """
    if not plant_ids:
        return {}
        
    params = {
        'frequency': 'monthly',
        'data[0]': 'nameplate-capacity-mw',
        'start': '2023-01',
        'end': '2023-01',
        'sort[0][column]': 'plantid',
        'sort[0][direction]': 'asc',
        'offset': 0,
        'length': 5000
    }
    
    ba_data = {}
    plant_id_set = set(plant_ids)
    
    while True:
        response = make_eia_request(PLANT_LOCATION_ENDPOINT, params)
        if not response:
            break
            
        records = response.get('response', {}).get('data', [])
        if not records:
            break
            
        for record in records:
            plant_id = str(record.get('plantid', ''))
            if plant_id not in plant_id_set or plant_id in ba_data:
                continue
                
            ba_data[plant_id] = {
                'balancing_authority_code': record.get('balancing_authority_code'),
                'balancing_authority_name': record.get('balancing-authority-name'),
                'entity_name': record.get('entityName'),
                'entity_id': record.get('entityid'),
                'sector': record.get('sector'),
                'technology': record.get('technology')
            }
        
        # Stop if we've found all plants or reached end of data
        if len(ba_data) >= len(plant_ids) or len(records) < 5000:
            break
            
        params['offset'] += 5000
        time.sleep(0.1)
    
    return ba_data


def get_plant_list(states=None, fuel_type=None):
    """
    Get basic list of plants filtered by state and/or fuel type.
    
    Args:
        states (list): List of state abbreviations to filter by
        fuel_type (str): Fuel type code to filter by
    
    Returns:
        dict: Dictionary mapping plant IDs to basic info (name, state)
    """
    logging.info(f"Fetching plant list (state={states}, fuel_type={fuel_type})")
    
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
    
    plants = {}
    
    # Fetch data from API
    while params['offset'] < 50000:  # Safety limit
        data = make_eia_request(PLANT_DATA_ENDPOINT, params)
        if not data:
            break
            
        records = data.get('response', {}).get('data', [])
        if not records:
            break
            
        # Extract basic plant info
        for record in records:
            plant_id = str(record.get('plantCode', ''))
            # Skip if plant ID is not found or already in list
            if not plant_id or plant_id in plants:
                continue
                
            plants[plant_id] = {
                'state': record.get('state', 'Unknown'),
                'name': record.get('plantName', 'Unknown'),
                'state_desc': record.get('stateDescription', 'Unknown')
            }
        
        if len(records) < params['length']:
            break
            
        params['offset'] += params['length']
        time.sleep(TIME_BETWEEN_REQUESTS)
    
    logging.info(f"Found {len(plants)} unique plants")
    return plants


def limit_plant_list(plant_list, states=None, limit=None):
    """
    Limit the number of plants per state.
    
    Args:
        plant_list (dict): Dictionary mapping plant IDs to basic info
        states (list): Optional list of states to filter by
        limit (int): Maximum number of plants per state
    
    Returns:
        dict: Limited dictionary of plants
    """
    if not limit:
        return plant_list
        
    print(f"\nLimiting to {limit} plants per state...")
    
    # Group plants by state
    plants_by_state = {}
    for plant_id, info in plant_list.items():
        state_code = info.get('state')
        # If states specified, only include those states
        if states and state_code not in states:
            continue
            
        if state_code not in plants_by_state:
            plants_by_state[state_code] = []
        plants_by_state[state_code].append((plant_id, info))
    
    # Take first N plants from each state
    limited_list = {}
    for state_code, plants in plants_by_state.items():
        for plant_id, info in plants[:limit]:
            limited_list[plant_id] = info
            
    return limited_list


def fetch_complete_plant_metadata(basic_plant_info, year=2023):
    """
    Enrich basic plant info with complete metadata from BA and EIA-860 sources.
    Main thing we're doing here is joining the BA data with the following files:
    The Plant file (2___Plant_*.xlsx) which has location data (lat/long, county, etc.) The Owner file (4___Owner_*.xlsx) which has ownership information
    
    Args:
        basic_plant_info (dict): Dictionary of plant_id -> {name, state, state_desc}
        year (int): Year for EIA-860 data
    
    Returns:
        pd.DataFrame: Complete plant metadata including coordinates, BA, ownership
    """
    plant_ids = list(basic_plant_info.keys())
    
    
    # 1. Get BA data from API
    ba_data = fetch_balancing_authority_data(plant_ids)
    print(f" found {len(ba_data)} plants")
    
    # 2. Get location and ownership data from EIA-860 (if available)
    try:
        location_ownership_data = fetch_eia860_location_ownership_data(year)
        matching_860 = sum(1 for pid in plant_ids if pid in location_ownership_data)
        print(f" found {matching_860} plants")
    except Exception as e:
        logging.warning(f"Could not fetch EIA-860 data for year {year}: {e}")
        logging.warning("Continuing without location/ownership data")
        location_ownership_data = {}
        print(f" EIA-860 data not available for year {year}")
    
    # 3. Combine all data sources
    records = []
    for plant_id, basic_info in basic_plant_info.items():
        record = {
            'plant_id': plant_id,
            'plant_name': basic_info.get('name'),
            'state': basic_info.get('state'),
            'state_name': basic_info.get('state_desc')
        }
        
        # Add BA data if available
        if plant_id in ba_data:
            record.update(ba_data[plant_id])
        
        # Add location/ownership data if available
        if plant_id in location_ownership_data:
            loc_own_info = location_ownership_data[plant_id]
            record.update({
                'latitude': loc_own_info.get('latitude'),
                'longitude': loc_own_info.get('longitude'),
                'county': loc_own_info.get('county'),
                'zip_code': loc_own_info.get('zip_code'),
                'street_address': loc_own_info.get('street_address'),
                'city': loc_own_info.get('city'),
                'balancing_authority_code_eia': loc_own_info.get('balancing_authority_code_eia'),
                'balancing_authority_name_eia': loc_own_info.get('balancing_authority_name_eia'),
                'nerc_region': loc_own_info.get('nerc_region'),
                'primary_purpose': loc_own_info.get('primary_purpose')
            })
            
            # Handle ownership data
            if 'owners' in loc_own_info and loc_own_info['owners']:
                owner_strings = [f"{o['name']} ({o['percent_owned']}%)" 
                               for o in loc_own_info['owners'] if o.get('name')]
                record['owners'] = '; '.join(owner_strings)
            
            # Create lat/long tuple
            if pd.notna(record.get('latitude')) and pd.notna(record.get('longitude')):
                record['lat_lng_tuple'] = f"({record['latitude']}, {record['longitude']})"
        
        record['last_updated'] = pd.Timestamp.now().strftime('%Y-%m-%d')
        records.append(record)
    
    return pd.DataFrame(records)


def update_plant_lookup_table(new_plant_df, output_dir='plant_data'):
    """
    Update or create the master plant lookup table.
    
    Args:
        new_plant_df (pd.DataFrame): New plant metadata to add/update
        output_dir (str): Directory containing plant_lookup.csv
    
    Returns:
        str: Path to the lookup file
    """
    lookup_file = os.path.join(output_dir, 'plant_lookup.csv')
    
    if os.path.exists(lookup_file):
        # Load existing and merge
        existing_df = pd.read_csv(lookup_file, dtype={'plant_id': str})
        
        # Remove plants we're updating from existing
        plant_ids_to_update = set(new_plant_df['plant_id'])
        kept_df = existing_df[~existing_df['plant_id'].isin(plant_ids_to_update)]
        
        # Combine and save
        final_df = pd.concat([kept_df, new_plant_df], ignore_index=True)
        final_df = final_df.sort_values('plant_id')
        
        print(f"\nUpdated {len(plant_ids_to_update)} plants in lookup table")
    else:
        final_df = new_plant_df.sort_values('plant_id')
        print(f"\nCreated new lookup table with {len(final_df)} plants")
    
    final_df.to_csv(lookup_file, index=False)
    
    # Show summary
    state_summary = final_df['state'].value_counts()
    print(f"Total: {len(final_df)} plants across {len(state_summary)} states")
    
    return lookup_file


def download_plant_data(plant_id, year, data_type='generation', 
                       output_dir='plant_data/raw_plant_generation_data', skip_existing=False, state=None):
    """
    Download time-series data for a specific plant for a given year.
    
    Args:
        plant_id (str): Plant ID to download
        year (int): Year to download data for
        data_type (str): Type of data to download ('generation', 'consumption', 'receipts')
        output_dir (str): Directory to save the data
        skip_existing (bool): Whether to skip if file exists
        state (str): State code for organizing output directory
    
    Returns:
        tuple: (status, df) where status is 'skipped', 'downloaded', or 'failed'
    """
    # Create state directory structure (no plant subdirectory)
    if state:
        save_dir = os.path.join(output_dir, state)
    else:
        save_dir = output_dir
    
    # New filename format: {PLANT_ID}_{YEAR}_generation.csv
    filename = f"{plant_id}_{year}_{data_type}.csv"
    output_file = os.path.join(save_dir, filename)
    
    # Check if file exists
    if skip_existing and os.path.exists(output_file):
        return 'skipped', pd.read_csv(output_file)
    
    # API parameters for full year
    start_date = f"{year}-01"
    end_date = f"{year}-12"
    
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
                logging.warning(f"No data found for plant {plant_id} in year {year}")
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
    
    # Exit early if no data found
    if not all_data:
        logging.warning(f"No data found for plant {plant_id} in year {year}")
        return 'failed', None
    
    os.makedirs(save_dir, exist_ok=True)
    
    df = pd.DataFrame(all_data)
    # Convert period to datetime for sorting
    df['period'] = pd.to_datetime(df['period'], format='%Y-%m') 
    # Sort by period (chronological order) and then by other columns for consistency
    df = df.sort_values(['period', 'fuel2002', 'primeMover'], na_position='last')
    # Convert period back to string format
    df['period'] = df['period'].dt.strftime('%Y-%m')
    df.to_csv(output_file, index=False)
    # logging.info(f"Saved {len(df)} records for plant {plant_id} to {output_file}")
    
    return 'downloaded', df


def download_plants_batch(plant_ids_with_state, year, data_type='generation',
                         output_dir='plant_data/raw_plant_generation_data', skip_existing=False,
                         batch_size=200):
    """
    Download time-series data for multiple plants in a single API request.
    
    Args:
        plant_ids_with_state (list): List of tuples (plant_id, state)
        year (int): Year to download data for
        data_type (str): Type of data to download
        output_dir (str): Directory to save the data
        skip_existing (bool): Whether to skip if file exists
        batch_size (int): Maximum number of plants per API request
    
    Returns:
        dict: Statistics with keys 'skipped', 'downloaded', 'failed'
    """
    stats = {'skipped': 0, 'downloaded': 0, 'failed': 0}
    
    # Check which files already exist
    plants_to_download = []
    for plant_id, state in plant_ids_with_state:
        save_dir = os.path.join(output_dir, state) if state else output_dir
        filename = f"{plant_id}_{year}_{data_type}.csv"
        output_file = os.path.join(save_dir, filename)
        
        if skip_existing and os.path.exists(output_file):
            stats['skipped'] += 1
        else:
            plants_to_download.append((plant_id, state))
    
    if not plants_to_download:
        return stats
    
    # Process in batches
    num_batches = (len(plants_to_download) + batch_size - 1) // batch_size
    
    for batch_idx, i in enumerate(range(0, len(plants_to_download), batch_size)):
        batch = plants_to_download[i:i + batch_size]
        plant_ids = [p[0] for p in batch]
        
        # Show progress
        print(f"  Batch {batch_idx + 1}/{num_batches}: Downloading {len(batch)} plants...", end='', flush=True)
        
        # API parameters for batch request
        start_date = f"{year}-01"
        end_date = f"{year}-12"
        
        params = {
            'frequency': 'monthly',
            'data[0]': data_type,
            'facets[plantCode][]': plant_ids,  # Multiple plant IDs!
            'start': start_date,
            'end': end_date,
            'sort[0][column]': 'period',
            'sort[0][direction]': 'asc',
            'offset': 0,
            'length': 5000
        }
        
        all_data = []
        
        # Fetch all data for this batch
        while True:
            data = make_eia_request(PLANT_DATA_ENDPOINT, params)
            
            if not data or 'response' not in data or 'data' not in data['response']:
                break
                
            records = data['response']['data']
            if not records:
                break
                
            all_data.extend(records)
            
            if len(records) < 5000:
                break
            else:
                params['offset'] += 5000
                
            time.sleep(TIME_BETWEEN_REQUESTS)
        
        # Group data by plant and save
        if all_data:
            df = pd.DataFrame(all_data)
            
            # Debug: Check what plant codes we actually got
            unique_plants = df['plantCode'].unique()
            print(f"\n  DEBUG: Requested {len(batch)} plants, got data for {len(unique_plants)} unique plants")
            if len(unique_plants) < 10:  # Only print if small number
                print(f"  Plant IDs in response: {sorted(unique_plants)}")
                print(f"  Plant IDs requested: {sorted([p[0] for p in batch][:10])}...")
            
            # Process each plant's data
            for plant_id, state in batch:
                # Convert both to string for comparison since API might return either strings or integers
                plant_df = df[df['plantCode'].astype(str) == str(plant_id)].copy()
                
                if plant_df.empty:
                    logging.warning(f"No data found for plant {plant_id} in year {year}")
                    stats['failed'] += 1
                    continue
                
                # Save plant data
                save_dir = os.path.join(output_dir, state) if state else output_dir
                os.makedirs(save_dir, exist_ok=True)
                
                filename = f"{plant_id}_{year}_{data_type}.csv"
                output_file = os.path.join(save_dir, filename)
                
                # Sort and save
                plant_df['period'] = pd.to_datetime(plant_df['period'], format='%Y-%m')
                plant_df = plant_df.sort_values(['period', 'fuel2002', 'primeMover'], na_position='last')
                plant_df['period'] = plant_df['period'].dt.strftime('%Y-%m')
                plant_df.to_csv(output_file, index=False)
                
                stats['downloaded'] += 1
        else:
            # No data for any plants in batch
            stats['failed'] += len(batch)
        
        # Update progress
        print(f" Done! (Downloaded: {sum(1 for p in batch if p[0] in [pid for pid, _ in batch if all_data])})")
    
    return stats


def load_and_merge_plant_data(csv_file, lookup_file='plant_data/plant_lookup.csv'):
    """
    Load time-series data and merge with plant metadata from lookup table.
    
    Args:
        csv_file (str): Path to time-series CSV file
        lookup_file (str): Path to plant lookup table (default: plant_data/plant_lookup.csv)
    
    Returns:
        pd.DataFrame: Merged dataframe with time-series data and metadata
    """
    # Load time-series data
    df = pd.read_csv(csv_file, dtype={'plantCode': str})
    
    # Load lookup table
    if not os.path.exists(lookup_file):
        logging.warning(f"Lookup file not found: {lookup_file}")
        return df
    
    lookup_df = pd.read_csv(lookup_file, dtype={'plant_id': str})
    
    # Merge on plant ID
    merged_df = df.merge(
        lookup_df, 
        left_on='plantCode', 
        right_on='plant_id', 
        how='left',
        suffixes=('', '_lookup')
    )
    
    # Drop duplicate plant_id column
    if 'plant_id' in merged_df.columns:
        merged_df = merged_df.drop('plant_id', axis=1)
    
    return merged_df


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
  # Download all plants in a state for years 2016-2023
  python download_plant_data.py --states TX --start 2016 --end 2023
  
  # Download plants in multiple states (organized by state folders)
  python download_plant_data.py --states TX CA --start 2020 --end 2023
  
  # Download all plants with specific fuel type
  python download_plant_data.py --fuel NG --start 2022 --end 2023
  
  # Download plants in state with specific fuel type
  python download_plant_data.py --states CA --fuel SUN --start 2018 --end 2023
  
  # Download different data types (generation, consumption, receipts)
  python download_plant_data.py --states TX --start 2020 --end 2023 --data-type consumption
  
  # Force download even if files exist
  python download_plant_data.py --states TX --start 2016 --end 2023 --force-download
  
  # Increase batch size for faster downloads (default: 200, max: 250)
  python download_plant_data.py --states TX CA --start 2020 --end 2023 --batch-size 250
  
Note: Data is automatically enriched with:
  - Balancing authority assignments
  - Latitude/longitude coordinates
  - Ownership information
  - Additional plant characteristics from EIA-860
        """
    )
    
    # Date options
    parser.add_argument('--start', type=int, required=True,
                       help='Start year (e.g., 2016)')
    parser.add_argument('--end', type=int, required=True,
                       help='End year (e.g., 2023)')
    
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
    parser.add_argument('--output', type=str, default='plant_data/raw_plant_generation_data',
                       help='Output directory (default: plant_data/raw_plant_generation_data)')
    parser.add_argument('--force-download', action='store_true',
                       help='Force download even if files already exist (default: skip existing files)')
    
    # Performance options
    parser.add_argument('--batch-size', type=int, default=200,
                       help='Number of plants to download per API request (default: 200, max: 250)')
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    
    # Validate API key
    if not validate_api_key():
        return
    
    # Get basic plant list
    plant_list = get_plant_list(
        states=args.states,
        fuel_type=args.fuel
    )
    if not plant_list:
        return
        
    # Apply limit if specified 
    if args.limit:
        plant_list = limit_plant_list(plant_list, states=args.states, limit=args.limit)
    
    # Enrich with complete metadata and save to lookup table (Use start year for EIA-860 data)
    complete_metadata_df = fetch_complete_plant_metadata(plant_list, args.start)
    base_dir = args.output.rsplit('/raw', 1)[0] if '/raw' in args.output else args.output
    update_plant_lookup_table(complete_metadata_df, base_dir)
    
    # Download time-series data for found plants
    print(f"\nDownloading {args.data_type} data from {args.start} to {args.end}")
    
    # Track download statistics
    total_stats = {'skipped': 0, 'downloaded': 0, 'failed': 0}
    
    # Prepare plant list with states
    plant_ids_with_state = [(plant_id, info.get('state')) for plant_id, info in plant_list.items()]
    
    # Loop through each year in the range
    for year in range(args.start, args.end + 1):
        print(f"\n--- Processing year {year} ---")
        
        # Use batch download (configurable plants per API request)
        year_stats = download_plants_batch(
            plant_ids_with_state,
            year,
            data_type=args.data_type,
            output_dir=args.output,
            skip_existing=not args.force_download,
            batch_size=args.batch_size
        )
        
        # Update total stats
        for key in year_stats:
            total_stats[key] += year_stats[key]
        
        # Print year summary
        year_total = len(plant_list)
        print(f"Year {year}: Downloaded: {year_stats['downloaded']}, Skipped: {year_stats['skipped']}, Failed: {year_stats['failed']}")
    
    # Print total summary
    total_files = len(plant_list) * (args.end - args.start + 1)
    print(f"\nDownload complete!")
    print(f"Total files processed: {total_files}")
    print(f"Skipped: {total_stats['skipped']} ({total_stats['skipped']/total_files*100:.1f}%)")
    print(f"Downloaded: {total_stats['downloaded']} ({total_stats['downloaded']/total_files*100:.1f}%)")
    print(f"Failed: {total_stats['failed']} ({total_stats['failed']/total_files*100:.1f}%)")


if __name__ == "__main__":
    main()